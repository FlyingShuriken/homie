from __future__ import annotations

import asyncio
import logging
from typing import Any

from zhipuai import ZhipuAI

from config import settings

logger = logging.getLogger(__name__)

# Single shared client instance
_client: ZhipuAI | None = None


def get_client() -> ZhipuAI:
    global _client
    if _client is None:
        if not settings.glm_api_key:
            raise RuntimeError(
                "GLM_API_KEY is not set. Add it to backend/.env before making GLM calls."
            )
        _client = ZhipuAI(api_key=settings.glm_api_key)
    return _client


async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> Any:
    """Async wrapper around the synchronous ZhipuAI chat.completions.create call.

    Runs in a thread-pool executor so it does not block the event loop.
    Retries once after GLM_RETRY_DELAY_SECONDS on any exception.
    """
    client = get_client()

    kwargs: dict[str, Any] = {
        "model": settings.glm_model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    for attempt in range(2):
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create, **kwargs
            )
            logger.debug(
                "GLM call ok | model=%s | finish=%s",
                settings.glm_model,
                response.choices[0].finish_reason,
            )
            return response
        except Exception as exc:
            if attempt == 0:
                logger.warning("GLM call failed (%s), retrying in %ds…", exc, settings.glm_retry_delay_seconds)
                await asyncio.sleep(settings.glm_retry_delay_seconds)
            else:
                logger.error("GLM call failed after retry: %s", exc)
                raise
