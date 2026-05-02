from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from config import settings
from geocoding import geocode
from glm.extractor import (
    apply_deterministic_extraction,
    extract_listing_fields,
    merge_extracted,
)
from malaysia_stations import build_alias_map
from transport import extract_transport_claims, extract_transport_stations

_ALIAS_MAP = build_alias_map()
from walking import get_walking_minutes
from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, RawListing, SessionState

logger = logging.getLogger(__name__)

_GEOCODE_CONCURRENCY = 10
_GLM_CONCURRENCY = 5
_GLM_BATCH_SIZE = 10


def run_transport_prepass(listing: RawListing) -> None:
    """Extract high-confidence transit names without an API call."""
    regex_stations = extract_transport_stations(listing.raw_text)
    if regex_stations:
        existing = listing.pre_parsed.get("nearby_transport", [])
        seen = {s.lower() for s in existing}
        for name in regex_stations:
            if name.lower() not in seen:
                existing.append(name)
                seen.add(name.lower())
        listing.pre_parsed["nearby_transport"] = existing


def run_deterministic_prepass(listing: RawListing) -> None:
    """Extract high-confidence fields without an API call."""
    run_transport_prepass(listing)
    apply_deterministic_extraction(listing.pre_parsed, listing.raw_text)


async def run_listing_extraction(listing: RawListing) -> None:
    """GLM extraction with deterministic fallback for model misses."""
    run_transport_prepass(listing)

    if settings.glm_api_key:
        extracted = await extract_listing_fields(
            listing.raw_text, listing.source, listing.pre_parsed
        )
        merge_extracted(
            listing.pre_parsed,
            extracted,
            prefer_extracted_fields={"gender_restriction"},
        )

    gender = listing.pre_parsed.get("gender_restriction")
    if isinstance(gender, str) and gender.strip().lower() not in ("", "unknown", "null", "none"):
        return

    apply_deterministic_extraction(listing.pre_parsed, listing.raw_text)


async def _geocode_listing(listing) -> None:
    if listing.pre_parsed.get("lat") and listing.pre_parsed.get("lng"):
        return

    title = listing.pre_parsed.get("title", listing.raw_text[:80])
    location_city = listing.pre_parsed.get("location_city", "")
    location_raw = listing.pre_parsed.get("location_raw", "")

    result = await geocode(
        settings.google_maps_api_key, title, location_city, location_raw
    )
    if result:
        listing.pre_parsed["lat"], listing.pre_parsed["lng"] = result
        logger.debug("Geocoded %r → %s", title, result)


async def _geocode_stations(listing) -> None:
    """Geocode each named transit station extracted into pre_parsed."""
    station_names = listing.pre_parsed.get("nearby_transport", [])
    if not station_names or not settings.google_maps_api_key:
        return

    stops = []
    for name in station_names:
        if "(nearby)" in name:
            continue
        result = await geocode(settings.google_maps_api_key, name, "Malaysia", "")
        if result:
            stops.append({"name": name, "lat": result[0], "lng": result[1]})
            logger.debug("Geocoded station %r → %s", name, result)

    listing.pre_parsed["transport_stops"] = stops


async def _verify_walk_claims(listing) -> None:
    """Attach claimed + actual walking time to each geocoded transport stop."""
    lat = listing.pre_parsed.get("lat")
    lng = listing.pre_parsed.get("lng")
    stops = listing.pre_parsed.get("transport_stops", [])
    if not lat or not lng or not stops:
        return

    claims = extract_transport_claims(listing.raw_text)
    claim_lookup: dict[str, dict] = {}
    for c in claims:
        claim_lookup[c["station_name"].lower()] = c

    def _match_claim(stop_name: str) -> dict | None:
        stop_lower = stop_name.lower()
        # resolve aliases: canonical stop name may be known by a code in the claim text
        canonical = _ALIAS_MAP.get(stop_lower, stop_lower)
        for key, claim in claim_lookup.items():
            # match by alias: if the claim names an alias that resolves to this stop
            claim_canonical = _ALIAS_MAP.get(key, key)
            if (key in stop_lower or stop_lower in key
                    or claim_canonical == canonical
                    or claim_canonical in canonical
                    or canonical in claim_canonical):
                return claim
        return None

    for stop in stops:
        stop_lat = stop.get("lat")
        stop_lng = stop.get("lng")
        if not stop_lat or not stop_lng:
            continue

        claim = _match_claim(stop["name"])
        if claim:
            stop["claimed_walk_minutes"] = claim["claimed_minutes"]
            stop["claimed_text"] = claim["claimed_text"]

        actual = await get_walking_minutes(
            settings.google_maps_api_key, lat, lng, stop_lat, stop_lng
        )
        if actual is not None:
            stop["actual_walk_minutes"] = actual
            claimed = stop.get("claimed_walk_minutes")
            stop["walk_verified"] = (claimed is None) or (actual <= claimed * 1.5)

            if claimed and actual > claimed * 1.5:
                flags = listing.pre_parsed.setdefault("low_confidence_flags", [])
                flags.append(
                    f"Claims {claimed}min walk to {stop['name']}, estimated ~{actual}min"
                )
            logger.debug("Walk verification %r: claimed=%s actual=%s", stop["name"], stop.get("claimed_walk_minutes"), actual)


class NormalizeListingsStage(BaseStage):
    name = "normalize"
    start_message = "Normalizing listings with GLM..."
    complete_message = "Normalization complete."

    async def execute(self, state: SessionState) -> AsyncGenerator[ProgressEvent, None]:
        count = len(state.raw_listings)
        yield self._event("running", f"Processing {count} raw listings...")

        # Phase 2: GLM extraction (regex pre-pass + GLM for gaps)
        if settings.glm_api_key:
            yield self._event("running", f"Extracting fields from {count} listings via GLM...")
            sem = asyncio.Semaphore(_GLM_CONCURRENCY)

            async def _bounded_extract(listing):
                async with sem:
                    await run_listing_extraction(listing)

            await asyncio.gather(*[_bounded_extract(l) for l in state.raw_listings])
            yield self._event("running", "Field extraction complete.")
        else:
            # Regex-only fallback when GLM not configured
            yield self._event("running", "Extracting deterministic listing fields...")
            for listing in state.raw_listings:
                run_deterministic_prepass(listing)

        # Geocode listing locations + transit stations
        if settings.google_maps_api_key:
            yield self._event("running", "Geocoding listing locations and transit stops...")
            geo_sem = asyncio.Semaphore(_GEOCODE_CONCURRENCY)

            async def _bounded_geo(listing):
                async with geo_sem:
                    await _geocode_listing(listing)
                    await _geocode_stations(listing)

            await asyncio.gather(*[_bounded_geo(l) for l in state.raw_listings])
            yield self._event("running", "Geocoding complete.")

        yield self._event("running", "Deduplicating listings across sources...")
