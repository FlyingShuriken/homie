from __future__ import annotations

from typing import AsyncGenerator

from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState


class PrepareOutreachStage(BaseStage):
    name = "outreach"
    start_message = "Preparing contact assistance..."
    complete_message = "Contact assistance ready."

    async def execute(self, state: SessionState) -> AsyncGenerator[ProgressEvent, None]:
        # Phase 1 stub: no GLM drafting yet.
        # Phase 2/3 will call run_glm_agent with get_listing_context + draft_inquiry_message tools,
        # then build Telegram deep links or phone fallbacks.
        count = sum(
            1 for l in state.normalized_listings
            if l.contact_telegram or l.contact_phone
        )
        yield self._event("running", f"Identified {count} listings with contact info. (stub)")
