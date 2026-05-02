from __future__ import annotations

import asyncio
import json
import logging
import types
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sse_starlette.sse import EventSourceResponse

from config import settings
from models.db import DATABASE_URL_FOR_LOGS, Listing as DBListing
from models.db import OutreachEvent, Session as DBSession, TelegramConversation
from models.db import SessionLocal, cleanup_expired_records, init_db
from glm.orchestrator import OrchestratorMaxIterationsError, run_orchestrator
from workflow.state import SessionState

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# In-process session store — sufficient for single-user hackathon demo
_session_states: dict[str, SessionState] = {}
_session_queues: dict[str, asyncio.Queue] = {}
_SESSION_EVENT_MAX = 50  # cap replay buffer to last N sessions
_session_events: OrderedDict[str, list[dict]] = (
    OrderedDict()
)  # replay buffer for late-joining SSE clients

# Telegram setup state — stores pending Telethon client + code hash between configure and verify calls
_tg_setup_state: dict[str, dict] = {}  # keyed by phone number


def get_runtime_capabilities() -> dict[str, bool]:
    from telegram.client import is_configured

    return {"telegram_outreach": is_configured()}


def _json_or_default(
    value: str | None, default: list | dict | None = None
) -> list | dict:
    if default is None:
        default = []
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def serialize_google_place(listing: DBListing) -> dict[str, Any] | None:
    if not any(
        [
            listing.google_place_id,
            listing.google_place_name,
            listing.google_rating is not None,
            listing.google_user_rating_count is not None,
        ]
    ):
        return None

    reviews = _json_or_default(listing.google_reviews_json)
    return {
        "place_id": listing.google_place_id,
        "name": listing.google_place_name,
        "google_maps_uri": listing.google_maps_uri,
        "rating": listing.google_rating,
        "user_rating_count": listing.google_user_rating_count,
        "reviews": reviews if isinstance(reviews, list) else [],
        "match_confidence": listing.google_place_match_confidence,
        "fetched_at": listing.google_place_fetched_at,
    }


def serialize_listing_response(listing: DBListing) -> dict[str, Any]:
    return {
        "id": listing.id,
        "source_primary": listing.source_primary,
        "source_variants": _json_or_default(listing.source_variants),
        "url": listing.url,
        "title": listing.title,
        "price_rm": listing.price_rm,
        "deposit_rm": listing.deposit_rm,
        "location_area": listing.location_area,
        "location_city": listing.location_city,
        "room_type": listing.room_type,
        "furnished_status": listing.furnished_status,
        "parking": listing.parking,
        "pet_friendly": listing.pet_friendly,
        "gender_restriction": listing.gender_restriction,
        "nearby_transport": _json_or_default(listing.nearby_transport),
        "transport_stops": _json_or_default(listing.transport_stops),
        "facilities": _json_or_default(listing.facilities),
        "contact_phone": listing.contact_phone,
        "contact_telegram": listing.contact_telegram,
        "contact_email": listing.contact_email,
        "description_en": listing.description_en,
        "images": _json_or_default(listing.images),
        "low_confidence_flags": _json_or_default(listing.low_confidence_flags),
        "needs_verification": _json_or_default(listing.needs_verification),
        "match_score": listing.match_score,
        "score_breakdown": _json_or_default(listing.score_breakdown),
        "score_explanation": listing.score_explanation,
        "outreach_status": listing.outreach_status,
        "lat": listing.lat,
        "lng": listing.lng,
        "google_place": serialize_google_place(listing),
    }


async def _start_telegram():
    from telegram.client import is_configured, get_client
    from telegram.event_handler import register_event_handler

    if not is_configured():
        return
    try:
        await get_client()
        await register_event_handler()
        logger.info("Telegram event handler registered on startup")
    except Exception as exc:
        logger.warning("Telegram event handler startup failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Homie backend started. DB: %s", DATABASE_URL_FOR_LOGS)
    asyncio.create_task(_start_telegram())
    yield
    from telegram.client import stop_client

    await stop_client()


app = FastAPI(title="Homie API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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


class TelegramConfigureRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str


class TelegramVerifyRequest(BaseModel):
    phone: str
    code: str
    password: str = ""  # 2FA password, only required if account has it enabled


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
            types.SimpleNamespace(
                stage="orchestrator",
                status="failed",
                message="Orchestrator reached iteration limit — partial results available.",
                timestamp="",
            )
        )
    except Exception as exc:
        logger.error(
            "Pipeline crashed for session %s: %s", session_id, exc, exc_info=True
        )
        state.pipeline_status = "failed"
        await emit(
            types.SimpleNamespace(
                stage="orchestrator",
                status="failed",
                message=f"Pipeline error — {exc}",
                timestamp="",
            )
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

        # Evict the queue from memory; keep events for late SSE replay but cap total sessions
        _session_queues.pop(session_id, None)
        if session_id not in _session_events:
            _session_events[session_id] = []
        _session_events.move_to_end(session_id)
        while len(_session_events) > _SESSION_EVENT_MAX:
            _session_events.popitem(last=False)


# ── Routes ────────────────────────────────────────────────────────────────────


@app.post("/api/search")
async def start_search(filters: FilterInput, background_tasks: BackgroundTasks):
    cleanup_expired_records()
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


@app.get("/api/search/{session_id}/fb_status")
async def fb_status(session_id: str):
    state = _session_states.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"fb_login_required": getattr(state, "fb_login_required", False)}


@app.get("/api/search/{session_id}/results")
async def get_results(session_id: str):
    db = SessionLocal()
    try:
        db_session = db.query(DBSession).filter(DBSession.id == session_id).first()
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found.")

        listings = db.query(DBListing).filter(DBListing.session_id == session_id).all()

        return {
            "session_id": session_id,
            "pipeline_status": db_session.pipeline_status,
            "summary_report": db_session.summary_report,
            "capabilities": get_runtime_capabilities(),
            "filters": _json_or_default(db_session.filters, default={}),
            "listings": [serialize_listing_response(l) for l in listings],
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
                response = await glm_client.chat(
                    messages=[
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
                    ]
                )
                draft_text = response.choices[0].message.content.strip()
            except Exception as exc:
                logger.warning(
                    "GLM outreach draft failed for listing %s: %s", listing_id, exc
                )
                draft_text = (
                    f"Hello, I am interested in your listing '{listing.title}'. "
                    "Could you please share more details about the room availability and any terms? "
                    "Thank you."
                )

            db.add(
                OutreachEvent(
                    listing_id=listing_id,
                    channel=(
                        "telegram_handoff"
                        if listing.contact_telegram
                        else "phone_manual"
                    ),
                    status="drafted",
                    draft_content=draft_text,
                )
            )
            drafts.append(
                {
                    "listing_id": listing_id,
                    "draft_text": draft_text,
                    "has_telegram": bool(listing.contact_telegram),
                    "contact_phone": listing.contact_phone,
                }
            )

        db.commit()
        return {"drafts": drafts}
    finally:
        db.close()


@app.post("/api/outreach/handoff")
async def confirm_outreach_handoff(body: OutreachHandoffRequest):
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
    """Send outreach drafts to the demo account for presentation purposes."""
    from telegram.client import is_configured, send_message
    from telegram.outreach_agent import run_outreach_turn

    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Telegram not configured. Use the setup flow to connect your account.",
        )

    db = SessionLocal()
    try:
        db_session = db.query(DBSession).filter(DBSession.id == body.session_id).first()
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found.")

        filters = json.loads(db_session.filters) if db_session.filters else {}

        q = db.query(DBListing).filter(DBListing.session_id == body.session_id)
        if body.listing_ids:
            q = q.filter(DBListing.id.in_(body.listing_ids))
        listings = q.all()

        # Resolve demo target to numeric Telegram user ID once (needed to match incoming sender_id)
        from telegram.client import get_client

        tg_client = await get_client()
        try:
            entity = await tg_client.get_entity(settings.telegram_demo_target)
            demo_chat_id = str(entity.id)
        except Exception as exc:
            logger.error("Could not resolve telegram_demo_target to entity: %s", exc)
            raise HTTPException(
                status_code=503, detail="Could not resolve Telegram demo target."
            )

        results = []
        for listing in listings:
            listing_context = {
                "title": listing.title,
                "price_rm": listing.price_rm,
                "location": listing.location_area or listing.location_city,
                "room_type": listing.room_type,
            }
            must_haves_to_verify = json.loads(listing.needs_verification or "[]")

            first_turn = await run_outreach_turn(
                conversation_history=[],
                incoming_message=None,
                listing_context=listing_context,
                user_filters=filters,
                must_haves_to_verify=must_haves_to_verify,
            )
            opening_msg = first_turn["reply"]

            # All messages go to the demo account instead of actual landlords
            demo_msg = f"[Demo — listing: {listing.title}]\n\n{opening_msg}"
            try:
                await send_message(settings.telegram_demo_target, demo_msg)
                listing.outreach_status = "telegram_sent"

                # Create conversation record so the event handler can route replies
                conv = TelegramConversation(
                    listing_id=listing.id,
                    session_id=body.session_id,
                    telegram_chat_id=demo_chat_id,
                    telegram_handle=settings.telegram_demo_target,
                    status="awaiting_reply",
                    conversation_history=json.dumps(
                        [{"role": "assistant", "content": demo_msg}]
                    ),
                    must_haves_to_verify=json.dumps(must_haves_to_verify),
                )
                db.add(conv)

                results.append(
                    {
                        "listing_id": listing.id,
                        "status": "sent",
                        "to": settings.telegram_demo_target,
                    }
                )
            except Exception as exc:
                logger.error("Failed to send demo Telegram: %s", exc)
                results.append(
                    {"listing_id": listing.id, "status": "failed", "reason": str(exc)}
                )

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


@app.get("/api/telegram/status")
async def telegram_status():
    from telegram.client import is_configured, is_authenticated

    return {"configured": is_configured(), "authenticated": is_authenticated()}


@app.post("/api/telegram/configure")
async def telegram_configure(body: TelegramConfigureRequest):
    """Save Telegram credentials to .env, then send an OTP to the phone number."""
    import pathlib
    import re
    from telethon import TelegramClient

    # Write/update .env file so credentials survive restarts
    env_path = pathlib.Path(__file__).parent / ".env"
    env_text = env_path.read_text() if env_path.exists() else ""

    def _set_var(text: str, key: str, value: str) -> str:
        pattern = rf"^{key}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, text, re.MULTILINE):
            return re.sub(pattern, replacement, text, flags=re.MULTILINE)
        return text + f"\n{replacement}"

    env_text = _set_var(env_text, "TELEGRAM_API_ID", str(body.api_id))
    env_text = _set_var(env_text, "TELEGRAM_API_HASH", body.api_hash)
    env_text = _set_var(env_text, "TELEGRAM_PHONE", body.phone)
    env_path.write_text(env_text)

    # Hot-reload the settings singleton so is_configured() reflects the new values
    settings.telegram_api_id = body.api_id
    settings.telegram_api_hash = body.api_hash
    settings.telegram_phone = body.phone

    # Disconnect any stale client for this phone from a previous configure attempt
    existing = _tg_setup_state.pop(body.phone, None)
    if existing:
        try:
            await existing["client"].disconnect()
        except Exception:
            pass

    # Create a temporary client just for OTP setup (not the production singleton)
    client = TelegramClient(
        settings.telegram_session_path,
        body.api_id,
        body.api_hash,
    )
    await client.connect()

    if await client.is_user_authorized():
        await client.disconnect()
        return {"otp_sent": False, "already_authorized": True}

    sent = await client.send_code_request(body.phone)
    _tg_setup_state[body.phone] = {
        "client": client,
        "phone_code_hash": sent.phone_code_hash,
    }
    return {"otp_sent": True, "already_authorized": False}


@app.post("/api/telegram/verify")
async def telegram_verify(body: TelegramVerifyRequest):
    """Complete Telegram sign-in with the OTP (and optional 2FA password)."""
    from telethon.errors import SessionPasswordNeededError

    state = _tg_setup_state.get(body.phone)
    if not state:
        raise HTTPException(
            status_code=400,
            detail="No pending setup for this phone. Call /api/telegram/configure first.",
        )

    client = state["client"]
    phone_code_hash = state["phone_code_hash"]

    try:
        await client.sign_in(
            phone=body.phone,
            code=body.code,
            phone_code_hash=phone_code_hash,
        )
    except SessionPasswordNeededError:
        if not body.password:
            raise HTTPException(status_code=422, detail="two_factor_required")
        await client.sign_in(password=body.password)

    await client.disconnect()
    del _tg_setup_state[body.phone]

    # Start the production singleton and event handler now that the session file exists
    try:
        from telegram.client import get_client
        from telegram.event_handler import register_event_handler

        await get_client()
        asyncio.create_task(register_event_handler())
        logger.info("Telegram client and event handler started after frontend setup")
    except Exception as exc:
        logger.warning("Production client start after setup failed: %s", exc)

    return {"success": True}


@app.get("/api/facebook/status")
async def facebook_status():
    from auth.facebook_session import has_session

    return {"logged_in": has_session(settings.fb_cookies_path)}


@app.post("/api/facebook/login")
async def facebook_login():
    if not settings.fb_cookies_path:
        raise HTTPException(
            status_code=400, detail="FB_COOKIES_PATH is not configured."
        )

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
                await page.wait_for_selector(
                    '[data-pagelet="LeftRail"]', timeout=300000
                )
            except PWTimeout:
                await browser.close()
                raise HTTPException(
                    status_code=408, detail="Login timed out after 5 minutes."
                )

            cookies = await context.cookies()
            save_cookies(cookies, settings.fb_cookies_path)
            await browser.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("facebook_login failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}")

    return {"success": True, "message": "Facebook session saved."}
