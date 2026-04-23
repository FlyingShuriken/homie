from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, TypeVar

from config import settings
from workflow.state import FilterObject, RawListing

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RetryMixin:
    async def _with_retry(
        self,
        coro_factory: Callable[[], Awaitable[T]],
        max_retries: int = 3,
    ) -> T:
        delays = [2 ** (i + 1) for i in range(max_retries)]  # [2, 4, 8]
        last_exc: Exception | None = None
        for attempt, delay in enumerate(delays, start=1):
            try:
                return await coro_factory()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    logger.warning(
                        "%s retry %d/%d after %ds — %s",
                        self.__class__.__name__, attempt, max_retries, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "%s all %d retries exhausted — %s",
                        self.__class__.__name__, max_retries, exc,
                    )
        raise last_exc  # type: ignore[misc]


class BaseScraper(RetryMixin, ABC):
    source: str = ""

    async def _random_delay(self) -> None:
        delay = random.uniform(
            settings.scraper_request_delay_min,
            settings.scraper_request_delay_max,
        )
        await asyncio.sleep(delay)

    @staticmethod
    def _location_slug(location: str) -> str:
        return location.strip().lower().replace(" ", "-")

    @abstractmethod
    async def scrape(
        self,
        filters: FilterObject,
        max_results: int,
    ) -> list[RawListing]:
        ...
