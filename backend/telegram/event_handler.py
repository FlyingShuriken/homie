from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from models.db import Listing as DBListing, SessionLocal, TelegramConversation

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def handle_incoming_message(sender_id: str, text: str) -> None:
    """Route an incoming Telegram message to the right conversation agent."""
    db = SessionLocal()
    try:
        conv = (
            db.query(TelegramConversation)
            .filter(
                TelegramConversation.telegram_chat_id == str(sender_id),
                TelegramConversation.status.in_(["active", "awaiting_reply"]),
            )
            .order_by(TelegramConversation.created_at.desc())
            .first()
        )
        if not conv:
            logger.debug("handle_incoming: no active conversation for sender %s", sender_id)
            return

        history: list[dict] = json.loads(conv.conversation_history or "[]")

        # Fetch listing + session filters
        listing = db.query(DBListing).filter(DBListing.id == conv.listing_id).first()
        listing_context = {}
        user_filters: dict = {}
        if listing:
            listing_context = {
                "title": listing.title,
                "price_rm": listing.price_rm,
                "location": listing.location_area or listing.location_city,
                "room_type": listing.room_type,
            }

        must_haves_to_verify: list[str] = json.loads(conv.must_haves_to_verify or "[]")

        from telegram.outreach_agent import run_outreach_turn

        result = await run_outreach_turn(
            conversation_history=history,
            incoming_message=text,
            listing_context=listing_context,
            user_filters=user_filters,
            must_haves_to_verify=must_haves_to_verify,
        )

        reply_text = result["reply"]
        new_status = result["status"]

        # Append both sides to history
        history.append({"role": "assistant", "content": f"[Agent replied]: {text}"})
        if reply_text:
            history.append({"role": "assistant", "content": reply_text})

        conv.conversation_history = json.dumps(history)
        conv.status = new_status
        conv.updated_at = _now()
        db.commit()

        # Send reply via Telethon
        if reply_text:
            try:
                from telegram.client import send_message
                await send_message(int(sender_id), reply_text)
            except Exception as exc:
                logger.error("Failed to send Telegram reply to %s: %s", sender_id, exc)

    except Exception as exc:
        logger.error("handle_incoming_message error for sender %s: %s", sender_id, exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


async def register_event_handler() -> None:
    """Register a Telethon event handler for incoming private messages."""
    try:
        from telethon import events
        from telegram.client import get_client

        client = await get_client()

        @client.on(events.NewMessage(incoming=True))
        async def _on_message(event):
            if event.is_private:
                sender_id = str(event.sender_id)
                text = event.raw_text or ""
                logger.info("Telegram incoming from %s: %r", sender_id, text[:80])
                await handle_incoming_message(sender_id, text)

        logger.info("Telegram event handler registered")
    except Exception as exc:
        logger.warning("Could not register Telegram event handler: %s", exc)
