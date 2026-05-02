from __future__ import annotations

import json
from pathlib import Path

import pytest

from config import settings
from glm.extractor import (
    apply_deterministic_extraction,
    extract_gender_restriction,
    merge_extracted,
)
from glm.tools.orchestrator_tools import build_tools_map
from workflow.state import RawListing, SessionState


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Female tenant preferred. Walking distance to MRT.", "female"),
        ("Room for rent in Cheras. Ladies only.", "female"),
        ("Bilik sewa untuk perempuan sahaja.", "female"),
        ("Single room, male only. No parking.", "male"),
        ("Prefer lelaki working adult.", "male"),
        ("Male/Female welcome.", "mixed"),
        ("Mixed gender ok.", "mixed"),
        ("Any gender can apply.", "mixed"),
        ("The owner is a female landlord. Single room available.", None),
    ],
)
def test_extract_gender_restriction(text: str, expected: str | None) -> None:
    assert extract_gender_restriction(text) == expected


def test_apply_deterministic_extraction_preserves_explicit_gender() -> None:
    pre_parsed = {"gender_restriction": "female"}

    apply_deterministic_extraction(pre_parsed, "Male only.")

    assert pre_parsed["gender_restriction"] == "female"


def test_merge_extracted_can_prefer_glm_gender() -> None:
    pre_parsed = {"gender_restriction": "mixed"}

    merge_extracted(
        pre_parsed,
        {"gender_restriction": "female"},
        prefer_extracted_fields={"gender_restriction"},
    )

    assert pre_parsed["gender_restriction"] == "female"


@pytest.mark.parametrize(
    ("fixture_name", "index", "expected"),
    [
        ("ibilik_seed.json", 0, "female"),
        ("ibilik_seed.json", 1, "mixed"),
        ("ibilik_seed.json", 2, "male"),
        ("ibilik_seed.json", 3, "female"),
        ("ibilik_seed.json", 5, "mixed"),
        ("iproperty_seed.json", 3, "female"),
        ("iproperty_seed.json", 5, "mixed"),
        ("facebook_seed.json", 0, "female"),
        ("facebook_seed.json", 1, "mixed"),
        ("facebook_seed.json", 4, "female"),
        ("facebook_seed.json", 5, "male"),
    ],
)
def test_seed_listing_gender_examples(
    fixture_name: str,
    index: int,
    expected: str,
) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / fixture_name
    row = json.loads(fixture_path.read_text(encoding="utf-8"))[index]
    pre_parsed = dict(row["pre_parsed"])

    apply_deterministic_extraction(pre_parsed, row["raw_text"])

    assert pre_parsed["gender_restriction"] == expected


@pytest.mark.asyncio
async def test_orchestrator_normalize_extracts_gender_before_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "glm_api_key", "")
    monkeypatch.setattr(settings, "google_maps_api_key", "")

    import db.helpers as db_helpers

    monkeypatch.setattr(db_helpers, "upsert_listings", lambda state: None)

    state = SessionState(session_id="gender-session")
    state.raw_listings = [
        RawListing(
            source="ibilik",
            url="https://example.test/listing-1",
            raw_text=(
                "Single Room Cheras | RM 650/month | "
                "Fully furnished. Female tenant preferred."
            ),
            pre_parsed={
                "title": "Single Room Cheras",
                "price_rm": 650,
                "description_original": "Fully furnished. Female tenant preferred.",
            },
        )
    ]
    events = []

    async def emit(event) -> None:
        events.append(event)

    tools = build_tools_map(state, emit)

    result = await tools["normalize_listings"](listing_ids=[])

    assert result["normalized"] == 1
    assert state.normalized_listings[0].gender_restriction == "female"


@pytest.mark.asyncio
async def test_orchestrator_normalize_prefers_glm_gender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "glm_api_key", "test-key")
    monkeypatch.setattr(settings, "google_maps_api_key", "")

    import db.helpers as db_helpers
    import glm.tools.orchestrator_tools as orchestrator_tools

    async def fake_extract_listing_fields(raw_text: str, source: str, pre_parsed: dict) -> dict:
        return {"gender_restriction": "female"}

    monkeypatch.setattr(db_helpers, "upsert_listings", lambda state: None)
    monkeypatch.setattr(
        orchestrator_tools,
        "extract_listing_fields",
        fake_extract_listing_fields,
    )

    state = SessionState(session_id="glm-gender-session")
    state.raw_listings = [
        RawListing(
            source="propertyguru",
            url="https://example.test/listing-2",
            raw_text="Single Room Cheras. Female tenant preferred.",
            pre_parsed={
                "title": "Single Room Cheras",
                "gender_restriction": "mixed",
            },
        )
    ]

    async def emit(event) -> None:
        pass

    tools = build_tools_map(state, emit)

    await tools["normalize_listings"](listing_ids=[])

    assert state.normalized_listings[0].gender_restriction == "female"
