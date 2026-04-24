from __future__ import annotations

import json
import logging
import re
from typing import TypedDict

from glm import client as glm_client

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are Homie, a friendly and sharp AI rental assistant for Malaysia.
Your job is to help users find rental rooms through a natural conversation.
You extract rental requirements from what the user says and build a structured filter profile.

CONVERSATION STYLE:
- Short, conversational messages (2-4 sentences max)
- Warm but efficient — Malaysians appreciate directness
- Ask at most ONE clarifying question per turn
- You may write in English, Bahasa Malaysia, or Chinese depending on the user's preference
- Do not say "Great!" or "Absolutely!" — just respond naturally

FILTER EXTRACTION RULES:
- location: area name (e.g. "Cheras", "Petaling Jaya", "Subang Jaya") — REQUIRED to start search
- price_min: minimum budget in RM (infer 0 if not mentioned and price_max is given)
- price_max: maximum budget in RM — REQUIRED to start search
- room_type: "single" | "master" | "studio" | "whole_unit" | "any"
- furnished_status: "fully" | "partially" | "unfurnished" | "any"
- gender_restriction: "male" | "female" | "mixed" | "any"
- parking: true | false (default false)
- transport: transit name or keyword (e.g. "MRT Taman Connaught", "LRT", "bus")
- pet_friendly: true | false (default false)
- max_results: integer 5-100 (default 30)
- must_haves: array of special requirements user explicitly states (e.g. ["swimming pool", "corner unit", "gym", "aircond", "wifi"])

INFERENCE RULES (use these to fill fields without asking):
- "near MRT" → transport: "MRT"
- "under RM600" → price_min: 0, price_max: 600
- "budget 500 to 700" → price_min: 500, price_max: 700
- "female only" → gender_restriction: "female"
- "no parking needed" or "don't need parking" → parking: false
- "need parking" → parking: true
- Single mention of "aircond" or "WiFi" in must-haves context → add to must_haves
- Stretch budget suggestion: if user says "around RM600", set price_max to 660 (10% stretch) and mention it
- Location areas: resolve common abbreviations (PJ → Petaling Jaya, KL → Kuala Lumpur, SS2 → Petaling Jaya)

CONFIDENCE LEVELS (per field):
- "confirmed": user explicitly stated this value
- "inferred": you derived it from context (e.g. transport from "near MRT")
- "soft": you guessed based on weak signals
- "missing": not mentioned yet

READY TO SEARCH:
Set ready_to_search to true when BOTH location AND price_max are confirmed or inferred with high confidence.
Do NOT wait for all fields — start with the basics and let the search engine handle the rest.

SUGGESTED CHIPS:
Provide 2-3 short action chips the user can tap. Make them specific to the current state:
- If gender not set: "Female only", "Any gender"
- If transport not mentioned: "Near MRT", "Near LRT"
- If ready to search: "Start search now", "Widen budget by 20%", "Add must-haves"
- Keep chips under 5 words each

OUTPUT FORMAT (strict JSON, no markdown):
{
  "reply": "<your conversational reply>",
  "filters": {
    "location": "<string or null>",
    "price_min": <int or null>,
    "price_max": <int or null>,
    "room_type": "<string or null>",
    "furnished_status": "<string or null>",
    "gender_restriction": "<string or null>",
    "parking": <bool or null>,
    "transport": "<string or null>",
    "pet_friendly": <bool or null>,
    "max_results": <int>,
    "must_haves": [<string>, ...]
  },
  "confidence": {
    "location": "confirmed|inferred|soft|missing",
    "price": "confirmed|inferred|soft|missing",
    "room_type": "confirmed|inferred|soft|missing",
    "furnished_status": "confirmed|inferred|soft|missing",
    "gender_restriction": "confirmed|inferred|soft|missing",
    "parking": "confirmed|inferred|soft|missing",
    "transport": "confirmed|inferred|soft|missing",
    "must_haves": "confirmed|inferred|soft|missing"
  },
  "ready_to_search": <bool>,
  "suggested_chips": ["<chip1>", "<chip2>", "<chip3>"]
}

IMPORTANT: Return ONLY the JSON object. No markdown, no explanations outside the JSON."""


class ChatFilters(TypedDict, total=False):
    location: str | None
    price_min: int | None
    price_max: int | None
    room_type: str | None
    furnished_status: str | None
    gender_restriction: str | None
    parking: bool | None
    transport: str | None
    pet_friendly: bool | None
    max_results: int
    must_haves: list[str]


class ChatResponse(TypedDict):
    reply: str
    filters: ChatFilters
    confidence: dict[str, str]
    ready_to_search: bool
    suggested_chips: list[str]


_FALLBACK_RESPONSE: ChatResponse = {
    "reply": "Hi! I'm Homie. Tell me where you're looking and your budget — I'll find the best matches across ibilik, iProperty, and Facebook.",
    "filters": {"max_results": 30, "must_haves": []},
    "confidence": {
        "location": "missing",
        "price": "missing",
        "room_type": "missing",
        "furnished_status": "missing",
        "gender_restriction": "missing",
        "parking": "missing",
        "transport": "missing",
        "must_haves": "missing",
    },
    "ready_to_search": False,
    "suggested_chips": ["Single room", "Near MRT", "Under RM700"],
}


async def run_chat_turn(
    history: list[dict],
    message: str,
) -> ChatResponse:
    """Run one turn of the chat intake agent.

    Args:
        history: Prior conversation [{"role": "user"|"assistant", "content": str}, ...]
        message: The new user message

    Returns:
        ChatResponse with reply, extracted filters, confidence, and chips
    """
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    raw_content = ""
    try:
        response = await glm_client.chat(messages=messages)
        raw_content = response.choices[0].message.content.strip()
        logger.debug("chat_agent raw response: %r", raw_content[:200])

        content = raw_content

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # If still not valid JSON, try to extract the first {...} block
        if not content.strip().startswith("{"):
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                content = m.group()

        parsed: ChatResponse = json.loads(content)

        # Ensure required fields have defaults
        if "filters" not in parsed:
            parsed["filters"] = {}
        if "must_haves" not in parsed.get("filters", {}):
            parsed["filters"]["must_haves"] = []
        if "max_results" not in parsed.get("filters", {}):
            parsed["filters"]["max_results"] = 30
        if "confidence" not in parsed:
            parsed["confidence"] = {}
        if "suggested_chips" not in parsed:
            parsed["suggested_chips"] = []
        if "ready_to_search" not in parsed:
            parsed["ready_to_search"] = False

        return parsed

    except json.JSONDecodeError as exc:
        # Model returned plain text instead of JSON — use it as the reply
        logger.warning("chat_agent: JSONDecodeError (%s), raw=%r", exc, raw_content[:300])
        reply_text = raw_content.strip() if raw_content else _FALLBACK_RESPONSE["reply"]
        return {**_FALLBACK_RESPONSE, "reply": reply_text}

    except Exception as exc:
        logger.warning("chat_agent turn failed (%s), returning fallback", exc)
        return _FALLBACK_RESPONSE
