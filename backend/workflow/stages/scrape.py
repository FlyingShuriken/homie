from __future__ import annotations

from typing import AsyncGenerator

from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState


class ScrapeListingsStage(BaseStage):
    name = "scrape"
    start_message = "Gathering listings from rental platforms..."
    complete_message = "Data gathering complete."

    async def execute(self, state: SessionState) -> AsyncGenerator[ProgressEvent, None]:
        # Phase 1 stub: no live scraping yet.
        # Phase 2 will dispatch IbilikScraper and IPropertyScraper here.
        yield self._event("running", "Scraping ibilik.com... (stub)")
        yield self._event("running", "Scraping iProperty.com.my... (stub)")
        yield self._event("running", f"Collected {len(state.raw_listings)} raw listings.")
