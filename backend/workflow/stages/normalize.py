from __future__ import annotations

from typing import AsyncGenerator

from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState


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
