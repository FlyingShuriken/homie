from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from workflow.state import NormalizedListing

logger = logging.getLogger(__name__)

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,places.types"
)
DETAILS_FIELD_MASK = "id,displayName,googleMapsUri,rating,userRatingCount,reviews"

MATCH_THRESHOLD = 0.45
MAX_REVIEWS = 3

_STOPWORDS = {
    "and",
    "apartment",
    "apt",
    "bilik",
    "condo",
    "condominium",
    "flat",
    "for",
    "fully",
    "furnished",
    "house",
    "kuala",
    "lumpur",
    "malaysia",
    "master",
    "month",
    "near",
    "partially",
    "private",
    "rent",
    "residence",
    "residences",
    "room",
    "sewa",
    "service",
    "single",
    "studio",
    "suite",
    "the",
    "unit",
    "whole",
}


@dataclass
class GooglePlaceReview:
    author_name: str = ""
    author_uri: str = ""
    author_photo_uri: str = ""
    rating: float | None = None
    relative_publish_time_description: str = ""
    text: str = ""
    google_maps_uri: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "author_name": self.author_name,
            "author_uri": self.author_uri,
            "author_photo_uri": self.author_photo_uri,
            "rating": self.rating,
            "relative_publish_time_description": self.relative_publish_time_description,
            "text": self.text,
            "google_maps_uri": self.google_maps_uri,
        }


@dataclass
class GooglePlaceEnrichment:
    place_id: str
    place_name: str = ""
    google_maps_uri: str = ""
    rating: float | None = None
    user_rating_count: int | None = None
    reviews: list[GooglePlaceReview] = field(default_factory=list)
    match_confidence: float = 0.0
    fetched_at: str = ""


async def enrich_listing_with_google_place(
    api_key: str,
    listing: NormalizedListing,
    *,
    client: httpx.AsyncClient | None = None,
) -> GooglePlaceEnrichment | None:
    if not api_key:
        return None

    query = build_text_query(listing)
    if not query:
        return None

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=10)

    try:
        places = await search_places(client, api_key, query, listing.lat, listing.lng)
        candidate = select_best_place(places, listing)
        if not candidate:
            return None

        place_id = candidate.get("id")
        if not isinstance(place_id, str) or not place_id:
            return None

        details = await get_place_details(client, api_key, place_id)
        if not details:
            return None

        return parse_place_details(
            details,
            match_confidence=float(candidate.get("_match_confidence", 0.0)),
        )
    except Exception as exc:
        logger.warning(
            "Google Places enrichment failed for listing %s: %s",
            listing.id,
            exc,
        )
        return None
    finally:
        if owns_client:
            await client.aclose()


async def search_places(
    client: httpx.AsyncClient,
    api_key: str,
    text_query: str,
    lat: float | None,
    lng: float | None,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {
        "textQuery": text_query,
        "languageCode": "en",
        "regionCode": "MY",
        "pageSize": 5,
    }
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 500.0,
            }
        }

    response = await client.post(
        TEXT_SEARCH_URL,
        json=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": SEARCH_FIELD_MASK,
        },
    )
    response.raise_for_status()
    data = response.json()
    places = data.get("places", [])
    return places if isinstance(places, list) else []


async def get_place_details(
    client: httpx.AsyncClient, api_key: str, place_id: str
) -> dict[str, Any] | None:
    response = await client.get(
        PLACE_DETAILS_URL.format(place_id=place_id),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": DETAILS_FIELD_MASK,
        },
        params={"languageCode": "en", "regionCode": "MY"},
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def apply_google_place_enrichment(
    listing: NormalizedListing, enrichment: GooglePlaceEnrichment
) -> None:
    listing.google_place_id = enrichment.place_id
    listing.google_place_name = enrichment.place_name
    listing.google_maps_uri = enrichment.google_maps_uri
    listing.google_rating = enrichment.rating
    listing.google_user_rating_count = enrichment.user_rating_count
    listing.google_reviews = [review.as_dict() for review in enrichment.reviews]
    listing.google_place_match_confidence = round(enrichment.match_confidence, 3)
    listing.google_place_fetched_at = enrichment.fetched_at


def parse_place_details(
    details: dict[str, Any], *, match_confidence: float
) -> GooglePlaceEnrichment | None:
    place_id = details.get("id")
    if not isinstance(place_id, str) or not place_id:
        return None

    display_name = details.get("displayName") or {}
    place_name = display_name.get("text", "") if isinstance(display_name, dict) else ""
    raw_reviews = details.get("reviews", [])
    reviews = [
        parsed
        for review in raw_reviews[:MAX_REVIEWS]
        if isinstance(review, dict)
        if (parsed := parse_review(review)) is not None
    ]

    rating = _number_or_none(details.get("rating"))
    count = details.get("userRatingCount")

    return GooglePlaceEnrichment(
        place_id=place_id,
        place_name=place_name,
        google_maps_uri=str(details.get("googleMapsUri") or ""),
        rating=rating,
        user_rating_count=count if isinstance(count, int) else None,
        reviews=reviews,
        match_confidence=match_confidence,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def parse_review(review: dict[str, Any]) -> GooglePlaceReview | None:
    author = review.get("authorAttribution") or {}
    text = review.get("text") or {}
    review_text = text.get("text", "") if isinstance(text, dict) else ""
    if not review_text and not author:
        return None

    return GooglePlaceReview(
        author_name=str(author.get("displayName") or "")
        if isinstance(author, dict)
        else "",
        author_uri=str(author.get("uri") or "") if isinstance(author, dict) else "",
        author_photo_uri=str(author.get("photoUri") or "")
        if isinstance(author, dict)
        else "",
        rating=_number_or_none(review.get("rating")),
        relative_publish_time_description=str(
            review.get("relativePublishTimeDescription") or ""
        ),
        text=review_text,
        google_maps_uri=str(review.get("googleMapsUri") or ""),
    )


def select_best_place(
    places: list[dict[str, Any]], listing: NormalizedListing
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = 0.0

    for place in places:
        if not isinstance(place, dict):
            continue
        score = match_confidence(place, listing)
        if score > best_score:
            best = place
            best_score = score

    if not best or best_score < MATCH_THRESHOLD:
        return None

    best["_match_confidence"] = round(best_score, 3)
    return best


def match_confidence(place: dict[str, Any], listing: NormalizedListing) -> float:
    expected = " ".join(
        filter(None, [listing.location_area, listing.title, listing.location_raw])
    )
    expected_tokens = _meaningful_tokens(expected)

    display_name = _localized_text(place.get("displayName"))
    address = str(place.get("formattedAddress") or "")
    candidate_text = f"{display_name} {address}"
    candidate_tokens = _meaningful_tokens(candidate_text)

    if not expected_tokens or not candidate_tokens:
        return 0.0

    overlap = len(expected_tokens & candidate_tokens) / max(len(expected_tokens), 1)
    score = min(0.55, overlap * 0.55)

    expected_compact = _compact(listing.location_area or listing.title)
    candidate_compact = _compact(display_name)
    if expected_compact and candidate_compact and (
        expected_compact in candidate_compact or candidate_compact in expected_compact
    ):
        score = max(score, 0.55)

    city = _compact(listing.location_city)
    if city and city in _compact(address):
        score += 0.1

    distance_km = _distance_to_place_km(place, listing)
    if distance_km is not None:
        if distance_km <= 0.5:
            score += 0.3
        elif distance_km <= 1.0:
            score += 0.2
        elif distance_km <= 2.0:
            score += 0.1
        elif distance_km > 5.0:
            score -= 0.25

    return max(0.0, min(1.0, score))


def build_text_query(listing: NormalizedListing) -> str:
    city = listing.location_city if listing.location_city != "unknown" else ""
    area = listing.location_area if listing.location_area != "unknown" else ""

    if area:
        return ", ".join(filter(None, [area, city, "Malaysia"]))

    if listing.title:
        cleaned = _clean_listing_title(listing.title)
        return ", ".join(filter(None, [cleaned, city, "Malaysia"]))

    if listing.location_raw:
        return f"{listing.location_raw}, Malaysia"

    return ""


def _clean_listing_title(title: str) -> str:
    cleaned = re.split(r"\bfor\s+rent\b|\brent\b|\|", title, maxsplit=1, flags=re.I)[0]
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-/")
    return cleaned[:120]


def _localized_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "")
    return str(value or "")


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _compact(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _distance_to_place_km(
    place: dict[str, Any], listing: NormalizedListing
) -> float | None:
    if listing.lat is None or listing.lng is None:
        return None
    loc = place.get("location")
    if not isinstance(loc, dict):
        return None
    lat = _number_or_none(loc.get("latitude"))
    lng = _number_or_none(loc.get("longitude"))
    if lat is None or lng is None:
        return None
    return _haversine_km(listing.lat, listing.lng, lat, lng)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))
