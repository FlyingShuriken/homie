from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from config import settings
from models.db import DATABASE_URL_FOR_LOGS, Listing as DBListing
from models.db import OutreachEvent, Session as DBSession, TelegramConversation
from models.db import SessionLocal, init_db
from glm.orchestrator import OrchestratorMaxIterationsError, run_orchestrator
from workflow.state import SessionState

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# In-process session store — sufficient for single-user hackathon demo
_session_states: dict[str, SessionState] = {}
_session_queues: dict[str, asyncio.Queue] = {}
_session_events: dict[str, list[dict]] = (
    {}
)  # replay buffer for late-joining SSE clients


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Homie backend started. DB: %s", DATABASE_URL_FOR_LOGS)
    # Start Telegram event handler in background if configured
    from telegram.client import is_configured
    if is_configured():
        try:
            from telegram.event_handler import register_event_handler
            asyncio.create_task(register_event_handler())
            logger.info("Telegram outreach agent started")
        except Exception as exc:
            logger.warning("Telegram startup failed (non-fatal): %s", exc)
    yield
    from telegram.client import stop_client
    await stop_client()


app = FastAPI(title="Homie API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────────


class FilterInput(BaseModel):
    location: str
    price_min: int
    price_max: int
    room_type: str = "any"
    furnished_status: str = "any"
    gender_restriction: str = "any"
    parking: bool = False
    transport: str = ""
    pet_friendly: bool = False
    max_results: int = 30
    must_haves: list[str] = []
    enable_telegram_outreach: bool = True

    @field_validator("price_min", "price_max")
    @classmethod
    def positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Price must be a positive integer.")
        return v

    @field_validator("price_max")
    @classmethod
    def max_gt_min(cls, v: int, info) -> int:
        price_min = info.data.get("price_min", 0)
        if v <= price_min:
            raise ValueError("price_max must be greater than price_min.")
        return v


class ChatMessageRequest(BaseModel):
    message: str
    history: list[dict] = []


class TelegramOutreachRequest(BaseModel):
    session_id: str
    listing_ids: list[str] = []  # empty = all contactable listings in session


class OutreachDraftRequest(BaseModel):
    session_id: str
    listing_ids: list[str]


class OutreachHandoffRequest(BaseModel):
    listing_id: str
    confirmed_draft: str


# ── Pipeline runner (background task) ─────────────────────────────────────────


async def _run_pipeline(
    session_id: str, state: SessionState, queue: asyncio.Queue
) -> None:
    async def emit(event) -> None:
        payload = {
            "stage": event.stage,
            "status": event.status,
            "message": event.message,
            "timestamp": event.timestamp,
        }
        _session_events.setdefault(session_id, []).append(payload)
        await queue.put(payload)

    try:
        await run_orchestrator(
            session_state=state,
            event_emitter=emit,
            max_iterations=settings.glm_orchestrator_max_iterations,
        )
    except OrchestratorMaxIterationsError as exc:
        logger.error(
            "Orchestrator hit iteration limit for session %s: %s", session_id, exc
        )
        state.pipeline_status = "partial"
        await emit(
            type(
                "E",
                (),
                {
                    "stage": "orchestrator",
                    "status": "failed",
                    "message": "Orchestrator reached iteration limit — partial results available.",
                    "timestamp": "",
                },
            )()
        )
    except Exception as exc:
        logger.error(
            "Pipeline crashed for session %s: %s", session_id, exc, exc_info=True
        )
        state.pipeline_status = "failed"
        await emit(
            type(
                "E",
                (),
                {
                    "stage": "orchestrator",
                    "status": "failed",
                    "message": f"Pipeline error — {exc}",
                    "timestamp": "",
                },
            )()
        )
    finally:
        await queue.put(None)  # sentinel — tells SSE consumer the stream is done

        # Update session status in DB (listings were already persisted incrementally by helpers)
        db = SessionLocal()
        try:
            db_session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if db_session:
                db_session.pipeline_status = state.pipeline_status
                db_session.summary_report = state.summary_report
                db.commit()
        finally:
            db.close()

        # Final upsert to catch any listings/scores not yet persisted
        from db.helpers import upsert_listings
        upsert_listings(state)


# ── Routes ────────────────────────────────────────────────────────────────────


@app.post("/api/search")
async def start_search(filters: FilterInput, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        db.add(DBSession(id=session_id, filters=filters.model_dump_json()))
        db.commit()
    finally:
        db.close()

    state = SessionState(session_id=session_id, raw_filters=filters.model_dump())
    queue: asyncio.Queue = asyncio.Queue()

    _session_states[session_id] = state
    _session_queues[session_id] = queue
    _session_events[session_id] = []

    background_tasks.add_task(_run_pipeline, session_id, state, queue)

    return {"session_id": session_id}


@app.get("/api/search/{session_id}/stream")
async def stream_progress(session_id: str):
    if session_id not in _session_queues:
        raise HTTPException(status_code=404, detail="Session not found.")

    queue = _session_queues[session_id]
    # Events already in the replay buffer are flushed first so late-joining clients
    # don't miss events that arrived before they connected.
    buffered = list(_session_events.get(session_id, []))

    async def generator() -> AsyncGenerator[dict, None]:
        for event in buffered:
            yield {"data": json.dumps(event)}

        while True:
            item = await queue.get()
            if item is None:
                break
            yield {"data": json.dumps(item)}

    return EventSourceResponse(generator())


@app.get("/api/search/{session_id}/results")
async def get_results(session_id: str):
    db = SessionLocal()
    try:
        db_session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found.")

        listings = db.query(DBListing).filter(DBListing.session_id == session_id).all()

        def _j(v: str | None) -> list | dict:
            if not v:
                return []
            try:
                return json.loads(v)
            except Exception:
                return []

        return {
            "session_id": session_id,
            "pipeline_status": db_session.pipeline_status,
            "summary_report": db_session.summary_report,
            "filters": _j(db_session.filters),
            "listings": [
                {
                    "id": l.id,
                    "source_primary": l.source_primary,
                    "source_variants": _j(l.source_variants),
                    "url": l.url,
                    "title": l.title,
                    "price_rm": l.price_rm,
                    "deposit_rm": l.deposit_rm,
                    "location_area": l.location_area,
                    "location_city": l.location_city,
                    "room_type": l.room_type,
                    "furnished_status": l.furnished_status,
                    "parking": l.parking,
                    "pet_friendly": l.pet_friendly,
                    "gender_restriction": l.gender_restriction,
                    "nearby_transport": _j(l.nearby_transport),
                    "facilities": _j(l.facilities),
                    "contact_phone": l.contact_phone,
                    "contact_telegram": l.contact_telegram,
                    "contact_email": l.contact_email,
                    "description_en": l.description_en,
                    "images": _j(l.images),
                    "low_confidence_flags": _j(l.low_confidence_flags),
                    "needs_verification": _j(l.needs_verification),
                    "match_score": l.match_score,
                    "score_breakdown": _j(l.score_breakdown),
                    "score_explanation": l.score_explanation,
                    "outreach_status": l.outreach_status,
                }
                for l in listings
            ],
        }
    finally:
        db.close()


@app.post("/api/outreach/draft")
async def request_outreach_drafts(body: OutreachDraftRequest):
    from glm import client as glm_client

    db = SessionLocal()
    try:
        session = db.query(DBSession).filter(DBSession.id == body.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        filters = json.loads(session.filters) if session.filters else {}
        drafts = []

        for listing_id in body.listing_ids:
            listing = db.query(DBListing).filter(DBListing.id == listing_id).first()
            if not listing:
                continue

            try:
                listing_context = {
                    "title": listing.title,
                    "price_rm": listing.price_rm,
                    "location": listing.location_area or listing.location_city,
                    "room_type": listing.room_type,
                    "furnished_status": listing.furnished_status,
                    "description": (listing.description_en or "")[:500],
                }
                response = await glm_client.chat(messages=[
                    {
                        "role": "system",
                        "content": (
                            "You draft professional rental inquiry messages for Malaysian renters. "
                            "Write 3-4 concise, polite sentences. Do not invent details. "
                            "Match the language register of the listing: use Bahasa Malaysia for BM listings, English otherwise. "
                            "Do not include a subject line or greeting header — just the message body."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Draft a rental inquiry for this listing:\n{json.dumps(listing_context)}\n\n"
                            f"Renter's preferences: {json.dumps(filters)}"
                        ),
                    },
                ])
                draft_text = response.choices[0].message.content.strip()
            except Exception as exc:
                logger.warning("GLM outreach draft failed for listing %s: %s", listing_id, exc)
                draft_text = (
                    f"Hello, I am interested in your listing '{listing.title}'. "
                    "Could you please share more details about the room availability and any terms? "
                    "Thank you."
                )

            db.add(OutreachEvent(
                listing_id=listing_id,
                channel="telegram_handoff" if listing.contact_telegram else "phone_manual",
                status="drafted",
                draft_content=draft_text,
            ))
            drafts.append({
                "listing_id": listing_id,
                "draft_text": draft_text,
                "has_telegram": bool(listing.contact_telegram),
                "contact_phone": listing.contact_phone,
            })

        db.commit()
        return {"drafts": drafts}
    finally:
        db.close()


@app.post("/api/outreach/handoff")
async def confirm_outreach_handoff(body: OutreachHandoffRequest):
    # Phase 3 stub — Telegram deep link generation is implemented in Phase 3.
    db = SessionLocal()
    try:
        listing = db.query(DBListing).filter(DBListing.id == body.listing_id).first()
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found.")

        event = OutreachEvent(
            listing_id=body.listing_id,
            channel="telegram_handoff" if listing.contact_telegram else "phone_manual",
            status="drafted",
            draft_content=body.confirmed_draft,
        )
        db.add(event)

        if listing.contact_telegram:
            import urllib.parse

            encoded = urllib.parse.quote(body.confirmed_draft)
            handle = listing.contact_telegram.lstrip("@")
            telegram_link = f"tg://resolve?domain={handle}&text={encoded}"
            listing.outreach_status = "opened_telegram"
            db.commit()
            return {"telegram_link": telegram_link}

        listing.outreach_status = "manual_only"
        db.commit()
        return {"phone_fallback": listing.contact_phone}
    finally:
        db.close()


@app.post("/api/chat/message")
async def chat_message(body: ChatMessageRequest):
    """Single turn of the chat intake agent. Returns reply + extracted filters."""
    from glm.chat_agent import run_chat_turn
    result = await run_chat_turn(history=body.history, message=body.message)
    return result


@app.post("/api/outreach/telegram/start")
async def start_telegram_outreach(body: TelegramOutreachRequest):
    """Start automated Telegram outreach for listings in a session."""
    from telegram.client import is_configured, send_message
    from telegram.phone_lookup import resolve_contact
    from telegram.outreach_agent import run_outreach_turn

    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Telegram not configured. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in .env",
        )

    db = SessionLocal()
    try:
        db_session = db.query(DBSession).filter(DBSession.id == body.session_id).first()
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found.")

        filters = json.loads(db_session.filters) if db_session.filters else {}

        # Build listing query
        q = db.query(DBListing).filter(DBListing.session_id == body.session_id)
        if body.listing_ids:
            q = q.filter(DBListing.id.in_(body.listing_ids))
        listings = q.all()

        results = []
        for listing in listings:
            if not (listing.contact_telegram or listing.contact_phone):
                results.append({"listing_id": listing.id, "status": "skipped", "reason": "no contact info"})
                continue

            # Resolve Telegram contact
            tg_handle = listing.contact_telegram
            tg_chat_id = None
            if tg_handle:
                tg_chat_id = tg_handle.lstrip("@")
            elif listing.contact_phone:
                resolved = await resolve_contact(listing.contact_phone)
                if resolved:
                    tg_chat_id = resolved
                else:
                    results.append({"listing_id": listing.id, "status": "skipped", "reason": "phone not on Telegram"})
                    continue

            # Check for existing conversation
            existing = (
                db.query(TelegramConversation)
                .filter(
                    TelegramConversation.listing_id == listing.id,
                    TelegramConversation.status.notin_(["completed", "failed"]),
                )
                .first()
            )
            if existing:
                results.append({"listing_id": listing.id, "status": "already_active"})
                continue

            must_haves_to_verify = json.loads(listing.needs_verification or "[]")
            listing_context = {
                "title": listing.title,
                "price_rm": listing.price_rm,
                "location": listing.location_area or listing.location_city,
                "room_type": listing.room_type,
            }

            # Generate opening message
            first_turn = await run_outreach_turn(
                conversation_history=[],
                incoming_message=None,
                listing_context=listing_context,
                user_filters=filters,
                must_haves_to_verify=must_haves_to_verify,
            )
            opening_msg = first_turn["reply"]

            # Create DB record
            conv = TelegramConversation(
                listing_id=listing.id,
                session_id=body.session_id,
                telegram_handle=tg_handle,
                telegram_chat_id=str(tg_chat_id) if tg_chat_id else None,
                phone_number=listing.contact_phone,
                status="awaiting_reply",
                conversation_history=json.dumps([
                    {"role": "assistant", "content": opening_msg}
                ]),
                must_haves_to_verify=json.dumps(must_haves_to_verify),
            )
            db.add(conv)

            # Send the message
            try:
                await send_message(tg_chat_id, opening_msg)
                results.append({"listing_id": listing.id, "status": "sent", "to": tg_chat_id})
                listing.outreach_status = "telegram_sent"
            except Exception as exc:
                logger.error("Failed to send Telegram to %s: %s", tg_chat_id, exc)
                conv.status = "failed"
                results.append({"listing_id": listing.id, "status": "failed", "reason": str(exc)})

        db.commit()
        return {"results": results}
    finally:
        db.close()


@app.get("/api/outreach/telegram/conversations/{session_id}")
async def get_telegram_conversations(session_id: str):
    """Get all Telegram conversations for a session."""
    db = SessionLocal()
    try:
        convs = (
            db.query(TelegramConversation)
            .filter(TelegramConversation.session_id == session_id)
            .all()
        )
        return {
            "conversations": [
                {
                    "id": c.id,
                    "listing_id": c.listing_id,
                    "telegram_handle": c.telegram_handle,
                    "status": c.status,
                    "history": json.loads(c.conversation_history or "[]"),
                    "must_haves_to_verify": json.loads(c.must_haves_to_verify or "[]"),
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
                for c in convs
            ]
        }
    finally:
        db.close()


@app.get("/api/facebook/status")
async def facebook_status():
    from auth.facebook_session import has_session
    return {"logged_in": has_session(settings.fb_cookies_path)}


@app.post("/api/facebook/login")
async def facebook_login():
    if not settings.fb_cookies_path:
        raise HTTPException(status_code=400, detail="FB_COOKIES_PATH is not configured.")

    from auth.facebook_session import save_cookies
    from playwright.async_api import async_playwright
    from playwright.async_api import TimeoutError as PWTimeout

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()
            await page.goto("https://www.facebook.com/login", timeout=30000)

            # Wait up to 5 minutes for the user to complete manual login
            try:
                await page.wait_for_selector('[data-pagelet="LeftRail"]', timeout=300000)
            except PWTimeout:
                await browser.close()
                raise HTTPException(status_code=408, detail="Login timed out after 5 minutes.")

            cookies = await context.cookies()
            save_cookies(cookies, settings.fb_cookies_path)
            await browser.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("facebook_login failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}")

    return {"success": True, "message": "Facebook session saved."}
