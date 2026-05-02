from __future__ import annotations

import json
import logging
import re

from malaysia_stations import build_station_reference

logger = logging.getLogger(__name__)

_STATION_REF = build_station_reference()

_SYSTEM_PROMPT = f"""You are an expert at extracting structured data from Malaysian rental listing text.

Below is the complete list of Malaysian public transit stations for reference:
<stations>
{_STATION_REF}
</stations>

Given a raw listing text and its source platform, extract the following fields and return ONLY valid JSON:

{{
  "nearby_transport": [],   // list of transit station name strings matched against the station list above
                            // Format: "<Station Name> <Line Type>", e.g. ["Taman Jaya LRT", "Taman Connaught MRT", "KL Sentral KTM"]
                            // Match station names even if slightly abbreviated or misspelled in the listing
                            // Also extract from Bahasa text, e.g. "dekat MRT Taman Connaught" → "Taman Connaught MRT"
                            // Also extract bracket/symbol-wrapped formats, e.g. "【MRT】Surian Station" → "Surian MRT"
                            // Also extract ALL-CAPS station names, e.g. "MRT SURIAN" → "Surian MRT"
                            // Only include stations from the reference list above — do not invent station names
  "facilities": [],         // list of amenity strings, e.g. ["WiFi", "Air-conditioning", "Washing machine", "Pool"]
  "gender_restriction": "", // "male", "female", "mixed", or null
  "furnished_status": "",   // "fully", "partially", "unfurnished", or null
  "room_type": "",          // "master", "single", "studio", "whole unit", or null
  "parking": "",            // "yes", "no", or null
  "pet_friendly": ""        // "yes", "no", or null
}}

Rules:
- Return ONLY the JSON object, no explanation, no markdown fences
- Use null (not empty string) for fields you cannot determine
- nearby_transport: match against the station reference list — prefer exact names, allow close matches
- nearby_transport: if the listing says "near MRT" with no station name, return empty list
- facilities: normalise to English even if listing is in Bahasa
- gender_restriction: extract the target tenant eligibility/preference only, not the landlord's gender or a casual occupant mention
- gender_restriction: "female only", "female preferred", "ladies only", "untuk perempuan sahaja" → "female"
- gender_restriction: "male only", "male preferred", "lelaki sahaja" → "male"
- gender_restriction: "male/female welcome", "mixed gender", "any gender" → "mixed"
- gender_restriction: if gender is not stated as a tenant eligibility/preference, return null
"""

_MISSING_VALUES = {"", "unknown", "null", "none"}

_FEMALE_TERMS = (
    r"(?:female|females|lady|ladies|girl|girls|woman|women|perempuan|wanita)"
)
_MALE_TERMS = (
    r"(?:male|males|gentleman|gentlemen|guy|guys|boy|boys|man|men|lelaki|laki[-\s]*laki)"
)
_TENANT_TERMS = (
    r"(?:tenant|tenants|housemate|housemates|roommate|roommates|student|students|"
    r"working adult|working adults|occupant|occupants|penyewa|penghuni)"
)
_TERM_SEP = r"(?:\s+|-)"

_MIXED_GENDER_PATTERNS = [
    re.compile(rf"\b{_MALE_TERMS}\s*(?:/|&|\+|-|or|and|atau|dan)\s*{_FEMALE_TERMS}\b", re.IGNORECASE),
    re.compile(rf"\b{_FEMALE_TERMS}\s*(?:/|&|\+|-|or|and|atau|dan)\s*{_MALE_TERMS}\b", re.IGNORECASE),
    re.compile(r"\b(?:mixed|any|all)\s+genders?\b", re.IGNORECASE),
    re.compile(r"\b(?:both|all)\s+(?:male\s+and\s+female|female\s+and\s+male|genders?)\b", re.IGNORECASE),
    re.compile(r"\bmixed\b(?!\s+(?:development|commercial|use))", re.IGNORECASE),
]

_FEMALE_GENDER_PATTERNS = [
    re.compile(rf"\b{_FEMALE_TERMS}{_TERM_SEP}(?:only|sahaja|shj|preferred|welcome|tenant|tenants|housemate|housemates|roommate|roommates|student|students)\b", re.IGNORECASE),
    re.compile(rf"\b(?:only|prefer|prefers|preferred|looking\s+for|for|untuk|accepting|suitable\s+for|available\s+for|wanted)\s+(?:{_TENANT_TERMS}\s+)?{_FEMALE_TERMS}\b", re.IGNORECASE),
    re.compile(rf"\b{_TENANT_TERMS}{_TERM_SEP}(?:must\s+be\s+)?{_FEMALE_TERMS}\b", re.IGNORECASE),
]

_MALE_GENDER_PATTERNS = [
    re.compile(rf"\b{_MALE_TERMS}{_TERM_SEP}(?:only|sahaja|shj|preferred|welcome|tenant|tenants|housemate|housemates|roommate|roommates|student|students)\b", re.IGNORECASE),
    re.compile(rf"\b(?:only|prefer|prefers|preferred|looking\s+for|for|untuk|accepting|suitable\s+for|available\s+for|wanted)\s+(?:{_TENANT_TERMS}\s+)?{_MALE_TERMS}\b", re.IGNORECASE),
    re.compile(rf"\b{_TENANT_TERMS}{_TERM_SEP}(?:must\s+be\s+)?{_MALE_TERMS}\b", re.IGNORECASE),
]


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


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _MISSING_VALUES
    return not bool(value)


def extract_gender_restriction(text: str) -> str | None:
    """Infer tenant gender eligibility/preference from listing text."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return None

    if any(pattern.search(normalized) for pattern in _MIXED_GENDER_PATTERNS):
        return "mixed"

    has_female = any(pattern.search(normalized) for pattern in _FEMALE_GENDER_PATTERNS)
    has_male = any(pattern.search(normalized) for pattern in _MALE_GENDER_PATTERNS)

    if has_female and has_male:
        return "mixed"
    if has_female:
        return "female"
    if has_male:
        return "male"
    return None


def apply_deterministic_extraction(pre_parsed: dict, raw_text: str) -> None:
    """Fill high-confidence fields that can be detected without a model call."""
    if _is_missing_value(pre_parsed.get("gender_restriction")):
        gender = extract_gender_restriction(raw_text)
        if gender:
            pre_parsed["gender_restriction"] = gender


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


def merge_extracted(
    pre_parsed: dict,
    extracted: dict,
    prefer_extracted_fields: set[str] | None = None,
) -> None:
    """Merge GLM-extracted fields into pre_parsed in-place.

    pre_parsed wins for scalar fields already set unless field override is requested.
    nearby_transport is unioned (GLM + regex, deduplicated).
    """
    if not extracted:
        return
    if prefer_extracted_fields is None:
        prefer_extracted_fields = set()

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
        value = extracted.get(field)
        if not value:
            continue
        if field in prefer_extracted_fields:
            if not _is_missing_value(value):
                pre_parsed[field] = value
            continue
        if field not in pre_parsed or _is_missing_value(pre_parsed[field]):
            pre_parsed[field] = value
