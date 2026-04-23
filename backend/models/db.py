from __future__ import annotations

import uuid
from typing import Any
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Float, Integer, String, Text, create_engine
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
    match_score = Column(Float, nullable=True)
    score_breakdown = Column(Text, nullable=True)
    score_explanation = Column(Text, nullable=True)
    outreach_status = Column(String, default="not_started")
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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
