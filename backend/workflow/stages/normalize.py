from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from config import settings
from geocoding import geocode
from glm.extractor import extract_listing_fields, merge_extracted
from transport import extract_transport_stations
from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState

logger = logging.getLogger(__name__)

_GEOCODE_CONCURRENCY = 10
_GLM_CONCURRENCY = 5
_GLM_BATCH_SIZE = 10


async def _run_extraction(listing) -> None:
    """Regex pre-pass then GLM extraction, merged into pre_parsed."""
    # Regex pre-pass: fast, no API cost
    regex_stations = extract_transport_stations(listing.raw_text)
    if regex_stations:
        existing = listing.pre_parsed.get("nearby_transport", [])
        seen = {s.lower() for s in existing}
        for name in regex_stations:
            if name.lower() not in seen:
                existing.append(name)
                seen.add(name.lower())
        listing.pre_parsed["nearby_transport"] = existing

    # GLM extraction: fills gaps + catches natural-language transit mentions
    extracted = await extract_listing_fields(
        listing.raw_text, listing.source, listing.pre_parsed
    )
    merge_extracted(listing.pre_parsed, extracted)


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
                    await _run_extraction(listing)

            await asyncio.gather(*[_bounded_extract(l) for l in state.raw_listings])
            yield self._event("running", "Field extraction complete.")
        else:
            # Regex-only fallback when GLM not configured
            yield self._event("running", "Extracting transport stations (regex fallback)...")
            for listing in state.raw_listings:
                regex_stations = extract_transport_stations(listing.raw_text)
                if regex_stations:
                    listing.pre_parsed.setdefault("nearby_transport", [])
                    seen = {s.lower() for s in listing.pre_parsed["nearby_transport"]}
                    for name in regex_stations:
                        if name.lower() not in seen:
                            listing.pre_parsed["nearby_transport"].append(name)
                            seen.add(name.lower())

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
