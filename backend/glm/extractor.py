from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert at extracting structured data from Malaysian rental listing text.

Given a raw listing text and its source platform, extract the following fields and return ONLY valid JSON:

{
  "nearby_transport": [],   // list of transit station name strings, e.g. ["Taman Jaya MRT", "Kelana Jaya LRT", "KTM Kepong"]
                            // Include any mention of MRT/LRT/KTM/BRT/Monorail stations, walking distance or minutes to a station
                            // Capture the station name + line type (e.g. "Universiti LRT", not just "LRT")
                            // Also extract from Bahasa text, e.g. "dekat MRT Taman Connaught" → "Taman Connaught MRT"
  "facilities": [],         // list of amenity strings, e.g. ["WiFi", "Air-conditioning", "Washing machine", "Pool"]
  "gender_restriction": "", // "male", "female", "mixed", or null
  "furnished_status": "",   // "fully", "partially", "unfurnished", or null
  "room_type": "",          // "master", "single", "studio", "whole unit", or null
  "parking": "",            // "yes", "no", or null
  "pet_friendly": ""        // "yes", "no", or null
}

Rules:
- Return ONLY the JSON object, no explanation, no markdown fences
- Use null (not empty string) for fields you cannot determine
- nearby_transport: be aggressive — extract any station name you can identify, even if phrasing is vague
- nearby_transport: omit generic phrases like "near MRT" with no station name
- facilities: normalise to English even if listing is in Bahasa
"""


def _parse_json(raw: str) -> dict:
    content = raw.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    if not content.strip().startswith("{"):
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            content = m.group()
    return json.loads(content)


async def extract_listing_fields(raw_text: str, source: str, pre_parsed: dict) -> dict:
    """Call GLM to extract structured fields from raw listing text.

    Returns a dict of extracted fields. On failure returns {}.
    """
    from glm import client as glm_client

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Source: {source}\n\n{raw_text}",
        },
    ]

    try:
        response = await glm_client.chat(messages=messages)
        raw_content = response.choices[0].message.content.strip()
        extracted = _parse_json(raw_content)
        logger.debug("extractor(%s): %r", source, extracted)
        return extracted
    except Exception as exc:
        logger.warning("extractor failed for source=%s: %s", source, exc)
        return {}


def merge_extracted(pre_parsed: dict, extracted: dict) -> None:
    """Merge GLM-extracted fields into pre_parsed in-place.

    pre_parsed wins for all scalar fields already set.
    nearby_transport is unioned (GLM + regex, deduplicated).
    """
    if not extracted:
        return

    # Union nearby_transport from both sources
    existing_transport = pre_parsed.get("nearby_transport", [])
    glm_transport = extracted.get("nearby_transport") or []
    if glm_transport:
        seen = {s.lower() for s in existing_transport}
        for name in glm_transport:
            if isinstance(name, str) and name.lower() not in seen:
                existing_transport.append(name)
                seen.add(name.lower())
        pre_parsed["nearby_transport"] = existing_transport

    # Fill scalar gaps — only set if pre_parsed doesn't already have the value
    scalar_fields = [
        "facilities", "gender_restriction", "furnished_status",
        "room_type", "parking", "pet_friendly",
    ]
    for field in scalar_fields:
        if field not in pre_parsed or not pre_parsed[field]:
            value = extracted.get(field)
            if value:
                pre_parsed[field] = value
