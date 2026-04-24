from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def resolve_contact(phone: str) -> Optional[str]:
    """Try to find a Telegram entity (chat_id) for a phone number.

    Returns the Telegram user id as a string on success, None if not found or
    if the contact has privacy settings that block phone lookup.
    """
    try:
        from telegram.client import get_client

        client = await get_client()
        entity = await client.get_input_entity(phone)
        # entity.user_id for InputPeerUser, entity.channel_id for channels
        user_id = getattr(entity, "user_id", None) or getattr(entity, "channel_id", None)
        if user_id:
            logger.info("phone_lookup: resolved %s → %s", phone, user_id)
            return str(user_id)
    except Exception as exc:
        logger.debug("phone_lookup: could not resolve %s: %s", phone, exc)
    return None
