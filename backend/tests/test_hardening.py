from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import main
from config import settings
from models import db as db_models


@pytest.mark.asyncio
async def test_stream_progress_replays_completed_session_without_queue() -> None:
    session_id = "completed-session"
    event = {
        "stage": "finish",
        "status": "complete",
        "message": "Workflow complete.",
        "timestamp": "2026-05-02T00:00:00+00:00",
    }

    main._session_queues.pop(session_id, None)
    main._session_events[session_id] = [event]
    try:
        response = await main.stream_progress(session_id)
        events = [item async for item in response.body_iterator]

        assert [json.loads(item["data"]) for item in events] == [event]
    finally:
        main._session_events.pop(session_id, None)


@pytest.mark.asyncio
async def test_stream_progress_returns_404_for_unknown_session() -> None:
    with pytest.raises(HTTPException) as exc:
        await main.stream_progress("missing-session")

    assert exc.value.status_code == 404


def test_runtime_capabilities_require_demo_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_api_id", 123)
    monkeypatch.setattr(settings, "telegram_api_hash", "hash")
    monkeypatch.setattr(settings, "telegram_phone", "+60123456789")
    monkeypatch.setattr(settings, "telegram_demo_target", "")

    assert main.get_runtime_capabilities()["telegram_outreach"] is False

    monkeypatch.setattr(settings, "telegram_demo_target", "@homie_demo")

    capabilities = main.get_runtime_capabilities()
    assert capabilities["telegram_outreach"] is True
    assert capabilities["telegram_demo_outreach"] is True


def _request(token: str = "") -> Request:
    headers = []
    if token:
        headers.append((b"x-homie-admin-token", token.encode()))
    return Request({"type": "http", "headers": headers})


@pytest.mark.asyncio
async def test_telegram_status_exposes_runtime_setup_without_admin_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_runtime_telegram_setup", True)
    monkeypatch.setattr(settings, "homie_admin_api_token", "")

    status = await main.telegram_status()

    assert status["runtime_setup_enabled"] is True
    assert status["operator_token_required"] is False


@pytest.mark.asyncio
async def test_runtime_telegram_setup_requires_demo_target_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_runtime_telegram_setup", True)
    monkeypatch.setattr(settings, "homie_admin_api_token", "")
    monkeypatch.setattr(settings, "telegram_demo_target", "")

    with pytest.raises(HTTPException) as exc:
        await main.telegram_configure(
            main.TelegramConfigureRequest(
                api_id=123,
                api_hash="hash",
                phone="+60123456789",
            ),
            _request(),
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "Telegram demo target is required for runtime setup."


@pytest.mark.asyncio
async def test_runtime_telegram_setup_enforces_configured_operator_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_runtime_telegram_setup", True)
    monkeypatch.setattr(settings, "homie_admin_api_token", "secret")
    monkeypatch.setattr(settings, "telegram_demo_target", "@homie_demo")

    with pytest.raises(HTTPException) as exc:
        await main.telegram_configure(
            main.TelegramConfigureRequest(
                api_id=123,
                api_hash="hash",
                phone="+60123456789",
            ),
            _request(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Operator token required."


def test_cleanup_expired_records_removes_related_outreach_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_models.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_models, "SessionLocal", testing_session_local)

    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    db = testing_session_local()
    try:
        db.add(
            db_models.Session(
                id="expired-session",
                filters="{}",
                pipeline_status="complete",
                expires_at=expired,
            )
        )
        db.add(
            db_models.Listing(
                id="expired-listing",
                session_id="expired-session",
                source_primary="ibilik",
                url="https://example.test/expired",
                title="Expired listing",
                expires_at=future,
            )
        )
        db.add(
            db_models.OutreachEvent(
                listing_id="expired-listing",
                channel="telegram_demo",
                status="sent",
            )
        )
        db.add(
            db_models.TelegramConversation(
                listing_id="expired-listing",
                session_id="expired-session",
                telegram_chat_id="123",
            )
        )
        db.add(
            db_models.Session(
                id="active-session",
                filters="{}",
                pipeline_status="complete",
                expires_at=future,
            )
        )
        db.add(
            db_models.Listing(
                id="active-listing",
                session_id="active-session",
                source_primary="ibilik",
                url="https://example.test/active",
                title="Active listing",
                expires_at=future,
            )
        )
        db.add(
            db_models.OutreachEvent(
                listing_id="active-listing",
                channel="telegram_demo",
                status="sent",
            )
        )
        db.commit()
    finally:
        db.close()

    db_models.cleanup_expired_records()

    db = testing_session_local()
    try:
        assert db.get(db_models.Session, "expired-session") is None
        assert db.get(db_models.Listing, "expired-listing") is None
        assert (
            db.query(db_models.OutreachEvent)
            .filter(db_models.OutreachEvent.listing_id == "expired-listing")
            .count()
            == 0
        )
        assert (
            db.query(db_models.TelegramConversation)
            .filter(db_models.TelegramConversation.session_id == "expired-session")
            .count()
            == 0
        )

        assert db.get(db_models.Session, "active-session") is not None
        assert db.get(db_models.Listing, "active-listing") is not None
        assert (
            db.query(db_models.OutreachEvent)
            .filter(db_models.OutreachEvent.listing_id == "active-listing")
            .count()
            == 1
        )
    finally:
        db.close()


@pytest.mark.asyncio
async def test_outreach_handoff_reports_demo_state_not_direct_telegram_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_models.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(main, "SessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "telegram_demo_target", "@homie_demo")

    db = testing_session_local()
    try:
        db.add(
            db_models.Listing(
                id="listing-with-telegram",
                session_id="session-1",
                source_primary="ibilik",
                url="https://example.test/listing",
                title="Demo listing",
                contact_telegram="@landlord",
                contact_phone="0123456789",
            )
        )
        db.commit()
    finally:
        db.close()

    response = await main.confirm_outreach_handoff(
        main.OutreachHandoffRequest(
            listing_id="listing-with-telegram",
            confirmed_draft="Hello, is this room available?",
        )
    )

    assert "telegram_link" not in response
    assert response == {
        "telegram_demo_target": "@homie_demo",
        "status": "demo_draft_ready",
        "phone_fallback": "0123456789",
    }

    db = testing_session_local()
    try:
        listing = db.get(db_models.Listing, "listing-with-telegram")
        assert listing is not None
        assert listing.outreach_status == "demo_draft_ready"
        event = db.query(db_models.OutreachEvent).one()
        assert event.channel == "telegram_demo"
        assert event.status == "draft_confirmed"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_telegram_demo_outreach_respects_session_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_models.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(main, "SessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "telegram_api_id", 123)
    monkeypatch.setattr(settings, "telegram_api_hash", "hash")
    monkeypatch.setattr(settings, "telegram_phone", "+60123456789")
    monkeypatch.setattr(settings, "telegram_demo_target", "@homie_demo")

    db = testing_session_local()
    try:
        db.add(
            db_models.Session(
                id="telegram-disabled-session",
                filters='{"enable_telegram_outreach": false}',
                pipeline_status="complete",
            )
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(HTTPException) as exc:
        await main.start_telegram_outreach(
            main.TelegramOutreachRequest(session_id="telegram-disabled-session")
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Telegram demo outreach is disabled for this session."
