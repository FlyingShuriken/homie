from __future__ import annotations

from typing import AsyncGenerator

from workflow.stages.base import BaseStage
from workflow.state import ProgressEvent, SessionState


class GenerateReportStage(BaseStage):
    name = "report"
    start_message = "Generating summary report..."
    complete_message = "Report ready."

    async def execute(self, state: SessionState) -> AsyncGenerator[ProgressEvent, None]:
        # Phase 1 stub: no GLM report generation yet.
        # Phase 2 will call run_glm_agent with get_session_stats + generate_summary_report tools.
        count = len(state.normalized_listings)
        state.summary_report = (
            f"Search complete. Found {count} listings matching your filters. "
            "Full AI-generated report will be available in Phase 2."
        )
        yield self._event("running", "Compiling search statistics... (stub)")
