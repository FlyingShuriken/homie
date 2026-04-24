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
from models.db import OutreachEvent, Session as DBSession
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
    yield


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

        db = SessionLocal()
        try:
            db_session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if db_session:
                db_session.pipeline_status = state.pipeline_status
                db_session.summary_report = state.summary_report
                db.commit()

            # Persist normalized listings + scores
            for listing in state.normalized_listings:
                score = state.scores.get(listing.id)
                db.add(
                    DBListing(
                        id=listing.id,
                        session_id=listing.session_id,
                        source_primary=listing.source_primary,
                        source_variants=json.dumps(listing.source_variants),
                        url=listing.url,
                        title=listing.title,
                        price_rm=listing.price_rm,
                        deposit_rm=listing.deposit_rm,
                        location_raw=listing.location_raw,
                        location_area=listing.location_area,
                        location_city=listing.location_city,
                        lat=listing.lat,
                        lng=listing.lng,
                        room_type=listing.room_type,
                        furnished_status=listing.furnished_status,
                        parking=listing.parking,
                        pet_friendly=listing.pet_friendly,
                        gender_restriction=listing.gender_restriction,
                        nearby_transport=json.dumps(listing.nearby_transport),
                        facilities=json.dumps(listing.facilities),
                        contact_phone=listing.contact_phone,
                        contact_telegram=listing.contact_telegram,
                        contact_email=listing.contact_email,
                        description_original=listing.description_original,
                        description_en=listing.description_en,
                        images=json.dumps(listing.images),
                        low_confidence_flags=json.dumps(listing.low_confidence_flags),
                        match_score=score.total if score else None,
                        score_breakdown=json.dumps(score.breakdown) if score else None,
                        score_explanation=score.explanation if score else None,
                    )
                )
            if state.normalized_listings:
                db.commit()
                logger.info(
                    "Persisted %d listings for session %s",
                    len(state.normalized_listings),
                    session_id,
                )
        finally:
            db.close()


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
