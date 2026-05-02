from __future__ import annotations

import uuid
from typing import Any
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Float, Integer, String, Text, create_engine, inspect, or_
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def engine_options_for_url(database_url: str) -> dict[str, Any]:
    backend_name = make_url(database_url).get_backend_name()
    if backend_name == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def render_database_url_for_logs(database_url: str) -> str:
    return make_url(database_url).render_as_string(hide_password=True)


DATABASE_URL = normalize_database_url(settings.database_url)
DATABASE_URL_FOR_LOGS = render_database_url_for_logs(DATABASE_URL)

engine = create_engine(DATABASE_URL, **engine_options_for_url(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filters = Column(Text)
    summary_report = Column(Text, nullable=True)
    pipeline_status = Column(String, default="running")
    created_at = Column(String, default=_now)
    expires_at = Column(String, default=_expires)


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String)
    source_primary = Column(String)
    source_variants = Column(Text, default="[]")
    url = Column(Text)
    title = Column(Text)
    price_rm = Column(Integer, nullable=True)
    deposit_rm = Column(Integer, nullable=True)
    location_raw = Column(Text, nullable=True)
    location_area = Column(String, default="unknown")
    location_city = Column(String, default="unknown")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    room_type = Column(String, default="unknown")
    furnished_status = Column(String, default="unknown")
    parking = Column(String, default="unknown")
    pet_friendly = Column(String, default="unknown")
    gender_restriction = Column(String, default="unknown")
    nearby_transport = Column(Text, default="[]")
    transport_stops = Column(Text, default="[]")
    facilities = Column(Text, default="[]")
    contact_phone = Column(String, nullable=True)
    contact_telegram = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    source_language = Column(String, default="unknown")
    posted_date = Column(String, nullable=True)
    description_original = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    images = Column(Text, default="[]")
    low_confidence_flags = Column(Text, default="[]")
    needs_verification = Column(Text, default="[]")   # must_haves not mentioned in listing
    match_score = Column(Float, nullable=True)
    score_breakdown = Column(Text, nullable=True)
    score_breakdown_comments = Column(Text, nullable=True)
    score_explanation = Column(Text, nullable=True)
    outreach_status = Column(String, default="not_started")
    google_place_id = Column(String, nullable=True)
    google_place_name = Column(Text, nullable=True)
    google_maps_uri = Column(Text, nullable=True)
    google_rating = Column(Float, nullable=True)
    google_user_rating_count = Column(Integer, nullable=True)
    google_reviews_json = Column(Text, default="[]")
    google_place_match_confidence = Column(Float, nullable=True)
    google_place_fetched_at = Column(String, nullable=True)
    created_at = Column(String, default=_now)
    expires_at = Column(String, default=_expires)


class OutreachEvent(Base):
    __tablename__ = "outreach_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String)
    channel = Column(String)
    status = Column(String)
    draft_content = Column(Text, nullable=True)
    created_at = Column(String, default=_now)


class TelegramConversation(Base):
    __tablename__ = "telegram_conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String)
    session_id = Column(String)
    telegram_chat_id = Column(String, nullable=True)
    telegram_handle = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    status = Column(String, default="pending")   # pending|active|awaiting_reply|completed|failed
    conversation_history = Column(Text, default="[]")  # JSON [{role, content, ts}]
    outreach_goal = Column(String, default="ask_info")  # ask_info|negotiate_price|confirm_availability
    must_haves_to_verify = Column(Text, default="[]")   # JSON list
    created_at = Column(String, default=_now)
    updated_at = Column(String, default=_now)


def _migrate() -> None:
    """Add any columns/tables that were introduced after the initial schema.

    Uses SQLAlchemy inspection so it is safe across Postgres and SQLite.
    """
    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("listings")}
        migrations = [
            ("needs_verification", "TEXT DEFAULT '[]'"),
            ("source_language", "VARCHAR DEFAULT 'unknown'"),
            ("posted_date", "VARCHAR"),
            ("transport_stops", "TEXT DEFAULT '[]'"),
            ("google_place_id", "VARCHAR"),
            ("google_place_name", "TEXT"),
            ("google_maps_uri", "TEXT"),
            ("google_rating", "FLOAT"),
            ("google_user_rating_count", "INTEGER"),
            ("google_reviews_json", "TEXT DEFAULT '[]'"),
            ("google_place_match_confidence", "FLOAT"),
            ("google_place_fetched_at", "VARCHAR"),
            ("score_breakdown_comments", "TEXT"),
        ]
        for column_name, column_def in migrations:
            if column_name in existing:
                continue
            sql = f"ALTER TABLE listings ADD COLUMN {column_name} {column_def}"
            try:
                conn.exec_driver_sql(sql)
            except Exception as exc:
                # Non-fatal: log and continue (e.g. SQLite doesn't support IF NOT EXISTS)
                import logging as _logging
                _logging.getLogger(__name__).warning("Migration skipped (%s): %s", sql[:60], exc)


def cleanup_expired_records() -> None:
    now = _now()
    db = SessionLocal()
    try:
        expired_session_ids = [
            row.id for row in db.query(Session.id).filter(Session.expires_at < now)
        ]

        listing_filters = [Listing.expires_at < now]
        if expired_session_ids:
            listing_filters.append(Listing.session_id.in_(expired_session_ids))

        expired_listing_ids = [
            row.id
            for row in db.query(Listing.id).filter(or_(*listing_filters))
        ]

        if expired_listing_ids:
            db.query(OutreachEvent).filter(
                OutreachEvent.listing_id.in_(expired_listing_ids)
            ).delete(synchronize_session=False)
            db.query(TelegramConversation).filter(
                TelegramConversation.listing_id.in_(expired_listing_ids)
            ).delete(synchronize_session=False)

        if expired_session_ids:
            db.query(TelegramConversation).filter(
                TelegramConversation.session_id.in_(expired_session_ids)
            ).delete(synchronize_session=False)

        db.query(Listing).filter(or_(*listing_filters)).delete(
            synchronize_session=False
        )
        db.query(Session).filter(Session.expires_at < now).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "Expired record cleanup failed", exc_info=True
        )
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate()
    cleanup_expired_records()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
