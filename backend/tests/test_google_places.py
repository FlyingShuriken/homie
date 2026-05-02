from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from main import serialize_listing_response
from places import (
    apply_google_place_enrichment,
    enrich_listing_with_google_place,
    select_best_place,
)
from workflow.state import NormalizedListing


def _listing() -> NormalizedListing:
    return NormalizedListing(
        id="listing-1",
        session_id="session-1",
        source_primary="propertyguru",
        url="https://example.test/listing",
        title="The Robertson for rent",
        location_raw="The Robertson, Bukit Bintang, Kuala Lumpur",
        location_area="The Robertson",
        location_city="Kuala Lumpur",
        lat=3.1459,
        lng=101.7048,
    )


@pytest.mark.asyncio
async def test_enrich_listing_with_google_place_maps_details_response() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1/places:searchText":
            assert request.headers["X-Goog-FieldMask"]
            payload = json.loads(request.content.decode())
            assert payload["locationBias"]["circle"]["radius"] == 500.0
            return httpx.Response(
                200,
                json={
                    "places": [
                        {
                            "id": "place-robertson",
                            "displayName": {"text": "The Robertson Kuala Lumpur"},
                            "formattedAddress": "Bukit Bintang, Kuala Lumpur",
                            "location": {
                                "latitude": 3.146,
                                "longitude": 101.7049,
                            },
                        }
                    ]
                },
            )

        if request.url.path == "/v1/places/place-robertson":
            return httpx.Response(
                200,
                json={
                    "id": "place-robertson",
                    "displayName": {"text": "The Robertson Kuala Lumpur"},
                    "googleMapsUri": "https://maps.google.com/?cid=123",
                    "rating": 4.3,
                    "userRatingCount": 128,
                    "reviews": [
                        {
                            "authorAttribution": {
                                "displayName": "Alicia Tan",
                                "uri": "https://maps.google.com/profile/alicia",
                                "photoUri": "https://example.test/photo.jpg",
                            },
                            "rating": 5,
                            "relativePublishTimeDescription": "2 months ago",
                            "text": {"text": "Clean lobby and good security."},
                            "googleMapsUri": "https://maps.google.com/review/1",
                        }
                    ],
                },
            )

        raise AssertionError(f"Unexpected request path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://places.googleapis.com",
    ) as client:
        result = await enrich_listing_with_google_place(
            "test-key", _listing(), client=client
        )

    assert result is not None
    assert result.place_id == "place-robertson"
    assert result.rating == 4.3
    assert result.user_rating_count == 128
    assert result.reviews[0].author_name == "Alicia Tan"
    assert calls == ["/v1/places:searchText", "/v1/places/place-robertson"]


def test_select_best_place_rejects_low_confidence_match() -> None:
    candidate = select_best_place(
        [
            {
                "id": "wrong-place",
                "displayName": {"text": "Sunway Pyramid"},
                "formattedAddress": "Bandar Sunway, Selangor",
                "location": {"latitude": 3.073, "longitude": 101.607},
            }
        ],
        _listing(),
    )

    assert candidate is None


def test_apply_enrichment_and_serialize_listing_response() -> None:
    listing = _listing()

    enrichment = SimpleNamespace(
        place_id="place-robertson",
        place_name="The Robertson Kuala Lumpur",
        google_maps_uri="https://maps.google.com/?cid=123",
        rating=4.3,
        user_rating_count=128,
        reviews=[SimpleNamespace(as_dict=lambda: {"author_name": "Alicia", "text": "Good"})],
        match_confidence=0.86,
        fetched_at="2026-05-02T00:00:00+00:00",
    )
    apply_google_place_enrichment(listing, enrichment)

    row = SimpleNamespace(
        id=listing.id,
        source_primary=listing.source_primary,
        source_variants="[]",
        url=listing.url,
        title=listing.title,
        price_rm=None,
        deposit_rm=None,
        location_area=listing.location_area,
        location_city=listing.location_city,
        room_type="unknown",
        furnished_status="unknown",
        parking="unknown",
        pet_friendly="unknown",
        gender_restriction="unknown",
        nearby_transport="[]",
        transport_stops="[]",
        facilities="[]",
        contact_phone=None,
        contact_telegram=None,
        contact_email=None,
        description_en="",
        images="[]",
        low_confidence_flags="[]",
        needs_verification="[]",
        match_score=None,
        score_breakdown=None,
        score_breakdown_comments=None,
        score_explanation=None,
        outreach_status="not_started",
        lat=listing.lat,
        lng=listing.lng,
        google_place_id=listing.google_place_id,
        google_place_name=listing.google_place_name,
        google_maps_uri=listing.google_maps_uri,
        google_rating=listing.google_rating,
        google_user_rating_count=listing.google_user_rating_count,
        google_reviews_json=json.dumps(listing.google_reviews),
        google_place_match_confidence=listing.google_place_match_confidence,
        google_place_fetched_at=listing.google_place_fetched_at,
    )

    payload = serialize_listing_response(row)

    assert payload["google_place"]["place_id"] == "place-robertson"
    assert payload["google_place"]["rating"] == 4.3
    assert payload["google_place"]["reviews"] == [{"author_name": "Alicia", "text": "Good"}]
