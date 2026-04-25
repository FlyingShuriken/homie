from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def resolve_contact(phone: str) -> Optional[str]:
    """Resolve a phone number to a Telegram user ID via contacts.ImportContacts.

    Imports the number as a temporary contact (which bypasses privacy settings),
    extracts the user ID, then immediately deletes the contact.
    Returns the user ID as a string, or None if the number has no Telegram account.
    """
    try:
        from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
        from telethon.tl.types import InputPhoneContact

        from telegram.client import get_client

        client = await get_client()

        # Normalize: strip spaces/dashes, ensure leading +
        normalized = "+" + phone.lstrip("+").replace(" ", "").replace("-", "")

        contact = InputPhoneContact(client_id=0, phone=normalized, first_name="tmp", last_name="")
        result = await client(ImportContactsRequest([contact]))

        if not result.users:
            logger.debug("phone_lookup: no Telegram account for %s", phone)
            return None

        user = result.users[0]
        user_id = str(user.id)
        logger.info("phone_lookup: resolved %s → %s (@%s)", phone, user_id, user.username)

        # Clean up — don't leave stale contacts on the account
        await client(DeleteContactsRequest(id=[user]))

        return user_id

    except Exception as exc:
        logger.debug("phone_lookup: could not resolve %s: %s", phone, exc)
    return None
