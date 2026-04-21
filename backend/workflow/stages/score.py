from __future__ import annotations

from typing import AsyncGenerator

from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState


class ScoreListingsStage(BaseStage):
    name = "score"
    start_message = "Scoring listings against your filters..."
    complete_message = "Scoring complete."

    async def execute(self, state: SessionState) -> AsyncGenerator[ProgressEvent, None]:
        # Phase 1 stub: no scoring yet.
        # Phase 2 will run ScoringEngine on each NormalizedListing,
        # then call run_glm_agent for natural-language explanations.
        count = len(state.normalized_listings)
        yield self._event("running", f"Scoring {count} listings across 8 dimensions... (stub)")
        yield self._event("running", "Generating score explanations with GLM... (stub)")
