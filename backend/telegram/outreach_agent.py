from __future__ import annotations

import json
import logging
from typing import Optional

from glm import client as glm_client

logger = logging.getLogger(__name__)

OUTREACH_SYSTEM_PROMPT = """You are a polite, professional Malaysian tenant reaching out to a property agent on behalf of a renter.
Keep messages SHORT (2-4 sentences) — Malaysians prefer WhatsApp-style brevity.
Be friendly and respectful. Do not be aggressive or pushy.

Your goals (in priority order):
1. Confirm the unit is still available
2. Ask about any unverified must-haves (e.g. "does the unit have a swimming pool?")
3. If the asking price is above the renter's budget, try a gentle negotiation
4. Confirm move-in date flexibility

LANGUAGE: Match the agent's language. Start in English, switch to Bahasa Malaysia or Chinese if the agent replies in those languages.

STOPPING CONDITIONS:
- If availability is confirmed and all must_haves are verified: set status to "completed"
- If the agent says the unit is taken or not available: set status to "completed"
- If no reply after 2 follow-ups: set status to "failed"
- If negotiation is successful or clearly impossible: set status to "completed"

OUTPUT (strict JSON, no markdown):
{
  "reply": "<your message to send to the agent>",
  "status": "active|awaiting_reply|completed|failed",
  "notes": "<brief internal note about conversation state>"
}"""


async def run_outreach_turn(
    conversation_history: list[dict],
    incoming_message: Optional[str],
    listing_context: dict,
    user_filters: dict,
    must_haves_to_verify: list[str],
) -> dict:
    """Generate the next outreach message for a listing conversation.

    Args:
        conversation_history: Prior [{role, content}] exchanges
        incoming_message: Latest reply from property agent (None for first turn)
        listing_context: {title, price_rm, location, room_type, contact_*}
        user_filters: The renter's filter preferences
        must_haves_to_verify: Special requirements not confirmed in listing text

    Returns:
        {"reply": str, "status": str, "notes": str}
    """
    context_block = (
        f"Listing: {listing_context.get('title', 'N/A')}\n"
        f"Price: RM {listing_context.get('price_rm', '?')}/month\n"
        f"Location: {listing_context.get('location', '?')}\n"
        f"Room type: {listing_context.get('room_type', '?')}\n"
        f"Renter budget: RM {user_filters.get('price_min', 0)} – RM {user_filters.get('price_max', '?')}\n"
    )
    if must_haves_to_verify:
        context_block += f"Must verify: {', '.join(must_haves_to_verify)}\n"

    messages = [
        {"role": "system", "content": OUTREACH_SYSTEM_PROMPT + "\n\nContext:\n" + context_block}
    ]

    # Replay conversation history
    messages.extend(conversation_history)

    # Add incoming agent reply (if any)
    if incoming_message:
        messages.append({"role": "user", "content": f"[Agent replied]: {incoming_message}"})
    else:
        messages.append({
            "role": "user",
            "content": "Send the initial outreach message to this property agent.",
        })

    try:
        response = await glm_client.chat(messages=messages)
        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        parsed = json.loads(content)
        return {
            "reply": parsed.get("reply", ""),
            "status": parsed.get("status", "awaiting_reply"),
            "notes": parsed.get("notes", ""),
        }
    except Exception as exc:
        logger.error("outreach_agent turn failed: %s", exc, exc_info=True)
        # Fallback to a safe opening message
        if not conversation_history:
            return {
                "reply": f"Hi, I saw your listing for '{listing_context.get('title', 'the room')}'. Is it still available? Thank you.",
                "status": "awaiting_reply",
                "notes": "fallback opening message",
            }
        return {
            "reply": "",
            "status": "failed",
            "notes": f"GLM error: {exc}",
        }
