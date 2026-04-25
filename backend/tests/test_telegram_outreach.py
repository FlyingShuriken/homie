"""
Manual integration test — sends a demo outreach message to the configured target.

Run with:
    uv run python -m tests.test_telegram_outreach

Requires TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, TELEGRAM_DEMO_TARGET
and a valid session file (run the frontend setup flow first).
"""
from __future__ import annotations

import asyncio
import sys
import os

# Run from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import settings
from telegram.client import is_configured, send_message, stop_client
from telegram.outreach_agent import run_outreach_turn

DEMO_TARGET = settings.telegram_demo_target

SAMPLE_LISTING = {
    "title": "Master Room @ Ara Damansara, near LRT",
    "price_rm": 950,
    "location": "Ara Damansara, Petaling Jaya",
    "room_type": "master",
}

SAMPLE_FILTERS = {
    "price_min": 700,
    "price_max": 1100,
    "location": "Petaling Jaya",
    "room_type": "master",
    "furnished_status": "fully",
    "parking": True,
}

MUST_HAVES = ["WiFi included", "no smoking policy"]


async def main() -> None:
    if not DEMO_TARGET:
        print("ERROR: TELEGRAM_DEMO_TARGET is not set in backend/.env")
        sys.exit(1)

    if not is_configured():
        print("ERROR: Telegram not configured. Set TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE in backend/.env")
        sys.exit(1)

    print("Generating outreach message via GLM...")
    turn = await run_outreach_turn(
        conversation_history=[],
        incoming_message=None,
        listing_context=SAMPLE_LISTING,
        user_filters=SAMPLE_FILTERS,
        must_haves_to_verify=MUST_HAVES,
    )

    print(f"\n--- Generated message ---\n{turn['reply']}\n")
    print(f"Status: {turn['status']}")
    print(f"Notes:  {turn['notes']}\n")

    demo_msg = f"[Demo — listing: {SAMPLE_LISTING['title']}]\n\n{turn['reply']}"

    print(f"Sending to @{DEMO_TARGET}...")
    await send_message(DEMO_TARGET, demo_msg)
    print("Sent.")

    await stop_client()


if __name__ == "__main__":
    asyncio.run(main())
