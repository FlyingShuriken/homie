from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from config import settings
from geocoding import geocode
from transport import extract_transport_stations
from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState

logger = logging.getLogger(__name__)

_GEOCODE_CONCURRENCY = 10


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
    """Extract transit station names from raw text and geocode each one."""
    station_names = extract_transport_stations(listing.raw_text)

    # Merge with any already-extracted names from pre_parsed
    existing = listing.pre_parsed.get("nearby_transport", [])
    for name in existing:
        extracted = extract_transport_stations(name)
        station_names = list(dict.fromkeys(station_names + extracted))

    listing.pre_parsed["nearby_transport"] = station_names

    if not settings.google_maps_api_key:
        return

    stops = []
    for name in station_names:
        # Skip generic fallback labels — they don't geocode to a useful location
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
        # Phase 1 stub: no GLM extraction yet.
        # Phase 2 will batch raw_listings into groups of 10 and call run_glm_agent.
        count = len(state.raw_listings)
        yield self._event("running", f"Processing {count} raw listings... (stub)")
        yield self._event("running", "Deduplicating listings across sources... (stub)")

        sem = asyncio.Semaphore(_GEOCODE_CONCURRENCY)

        async def _bounded_listing(listing):
            async with sem:
                await _geocode_listing(listing)

        async def _bounded_stations(listing):
            async with sem:
                await _geocode_stations(listing)

        yield self._event("running", "Extracting transport stations from listings...")
        await asyncio.gather(*[_bounded_stations(l) for l in state.raw_listings])

        if settings.google_maps_api_key:
            yield self._event("running", "Geocoding listing locations...")
            await asyncio.gather(*[_bounded_listing(l) for l in state.raw_listings])
            yield self._event("running", "Geocoding complete.")
