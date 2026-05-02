from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from config import settings
from geocoding import geocode
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

        if settings.google_maps_api_key:
            yield self._event("running", "Geocoding listing locations...")
            sem = asyncio.Semaphore(_GEOCODE_CONCURRENCY)

            async def _bounded(listing):
                async with sem:
                    await _geocode_listing(listing)

            await asyncio.gather(*[_bounded(l) for l in state.raw_listings])
            yield self._event("running", "Geocoding complete.")
