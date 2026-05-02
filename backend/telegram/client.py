from __future__ import annotations

import asyncio
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_client = None
_client_lock = asyncio.Lock()


def is_configured() -> bool:
    return bool(
        settings.telegram_api_id
        and settings.telegram_api_hash
        and settings.telegram_phone
    )


def is_authenticated() -> bool:
    """True if a saved session exists (client connected, or session file present)."""
    if _client is not None and _client.is_connected():
        return True
    import os

    path = settings.telegram_session_path
    if not path.endswith(".session"):
        path += ".session"
    return os.path.isfile(path) and os.path.getsize(path) > 0


async def get_client():
    """Return an authenticated Telethon TelegramClient, creating it if needed.

    On first call: starts the client and authenticates (OTP if session file absent).
    Subsequent calls return the cached singleton.
    """
    global _client
    if not is_configured():
        raise RuntimeError(
            "Telegram not configured. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, "
            "TELEGRAM_PHONE in backend/.env"
        )

    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client

        from telethon import TelegramClient

        client = TelegramClient(
            settings.telegram_session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

        async def _no_interactive_code():
            raise RuntimeError(
                "Telegram session requires interactive auth — run setup flow first."
            )

        await client.start(
            phone=settings.telegram_phone,
            code_callback=_no_interactive_code,
        )
        _client = client
        logger.info("Telethon client authenticated for %s", settings.telegram_phone)
        return client


async def stop_client() -> None:
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        _client = None
        logger.info("Telethon client disconnected")


async def send_message(chat_id: str | int, text: str) -> None:
    client = await get_client()
    await client.send_message(chat_id, text)
