from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FilterObject:
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
    must_haves: list = field(default_factory=list)   # special requirements e.g. ["pool", "corner unit"]
    enable_telegram_outreach: bool = True
    # Resolved by GLM in Stage 1
    location_area: str = ""
    location_city: str = ""
    location_state: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


@dataclass
class RawListing:
    source: str
    url: str
    raw_text: str
    pre_parsed: dict = field(default_factory=dict)
    scraped_at: str = ""


@dataclass
class NormalizedListing:
    id: str
    session_id: str
    source_primary: str
    url: str
    title: str = ""
    price_rm: Optional[int] = None
    deposit_rm: Optional[int] = None
    location_raw: str = ""
    location_area: str = "unknown"
    location_city: str = "unknown"
    lat: Optional[float] = None
    lng: Optional[float] = None
    room_type: str = "unknown"
    furnished_status: str = "unknown"
    parking: str = "unknown"
    pet_friendly: str = "unknown"
    gender_restriction: str = "unknown"
    nearby_transport: list = field(default_factory=list)
    facilities: list = field(default_factory=list)
    contact_phone: Optional[str] = None
    contact_telegram: Optional[str] = None
    contact_email: Optional[str] = None
    source_language: str = "unknown"
    posted_date: Optional[str] = None
    description_original: str = ""
    description_en: str = ""
    images: list = field(default_factory=list)
    low_confidence_flags: list = field(default_factory=list)
    source_variants: list = field(default_factory=list)
    needs_verification: list = field(default_factory=list)  # must_haves not found in listing text


@dataclass
class ScoreResult:
    listing_id: str
    total: float
    breakdown: dict
    explanation: str = ""


@dataclass
class ProgressEvent:
    stage: str
    status: str  # 'started' | 'running' | 'complete' | 'failed'
    message: str
    timestamp: str = ""


@dataclass
class SessionState:
    session_id: str
    raw_filters: dict = field(default_factory=dict)
    filters: Optional[FilterObject] = None
    raw_listings: list[RawListing] = field(default_factory=list)
    normalized_listings: list[NormalizedListing] = field(default_factory=list)
    scraper_failures: list[dict] = field(default_factory=list)
    scores: dict[str, ScoreResult] = field(default_factory=dict)
    summary_report: str = ""
    outreach_drafts: dict[str, dict] = field(default_factory=dict)
    pipeline_status: str = "running"
    # Orchestrator trace: each tool call the top-level GLM agent made
    orchestrator_tool_calls: list[dict] = field(default_factory=list)
    # Clarification requests queued by ask_user tool
    clarification_queue: list[dict] = field(default_factory=list)
    clarification_responses: dict[str, str] = field(default_factory=dict)
    # Filter relaxation suggestions from relax_filters tool
    filter_relaxation_suggestions: list[str] = field(default_factory=list)
