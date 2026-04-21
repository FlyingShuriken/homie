from __future__ import annotations

import dataclasses
from typing import AsyncGenerator

from workflow.stages.base import BaseStage
from workflow.state import FilterObject, ProgressEvent, SessionState


class ValidateFiltersStage(BaseStage):
    name = "validate"
    start_message = "Validating your search filters..."
    complete_message = "Filters validated."
    critical = True

    async def execute(self, state: SessionState) -> AsyncGenerator[ProgressEvent, None]:
        yield self._event("running", "Parsing filter inputs...")

        # Phase 1 stub: build FilterObject from raw_filters without GLM.
        # Phase 2 will replace this with the GLM agent loop.
        raw = state.raw_filters
        filter_fields = {f.name for f in dataclasses.fields(FilterObject)}
        valid_kwargs = {k: v for k, v in raw.items() if k in filter_fields}
        state.filters = FilterObject(**valid_kwargs)

        yield self._event("running", f"Location set to '{state.filters.location}', "
                          f"price range RM {state.filters.price_min}–{state.filters.price_max}.")
