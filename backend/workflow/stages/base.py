from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import AsyncGenerator

from workflow.state import ProgressEvent, SessionState


class BaseStage(ABC):
    name: str = "base"
    start_message: str = "Starting..."
    complete_message: str = "Done."
    critical: bool = False  # if True, a failure stops the entire pipeline

    def _event(self, status: str, message: str) -> ProgressEvent:
        return ProgressEvent(
            stage=self.name,
            status=status,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @abstractmethod
    async def execute(
        self, state: SessionState
    ) -> AsyncGenerator[ProgressEvent, None]:
        ...
