from __future__ import annotations

import re

_TRANSIT_TYPES = r"(?:MRT|LRT|KTM|BRT|Monorail|ERL|Rapid\s*KL|MRT2|Putrajaya\s*Line)"

# "MRT 5 min (Taman Jaya) from ..." → capture name in parens
_PG_RE = re.compile(
    r"(?:MRT|LRT|KTM|BRT|MONO)\s+\d+\s+min\s+\(([^)]+)\)",
    re.IGNORECASE,
)

# "near Taman Jaya MRT" / "walking distance to Kelana Jaya LRT"
_NEAR_RE = re.compile(
    r"(?:near|close to|nearby|walking distance to|next to|opposite)\s+([\w\s]+?)\s+" + _TRANSIT_TYPES,
    re.IGNORECASE,
)

# "5 min to Taman Connaught MRT" / "10 minutes from Cheras LRT"
_MIN_RE = re.compile(
    r"\d+\s*min(?:utes?)?\s+(?:to|from|walk(?:ing)?\s+to)\s+([\w\s]+?)\s+" + _TRANSIT_TYPES,
    re.IGNORECASE,
)

# "MRT Taman Jaya" / "LRT Kelana Jaya" / "MRT SURIAN" — transit type before station name
_PREFIX_RE = re.compile(
    _TRANSIT_TYPES + r"\s+((?:[A-Za-z][A-Za-z]+\s*){1,4})",
)

# Amenity code fallbacks
_AMENITY_MAP = {
    "near-mrt": "MRT (nearby)",
    "near-lrt": "LRT (nearby)",
    "near-ktm": "KTM (nearby)",
    "near-lrt-mrt": "LRT/MRT (nearby)",
    "near-ktm-lrt": "KTM/LRT (nearby)",
}

# Short noise words that are unlikely to be a real station name
_NOISE = {"the", "a", "an", "this", "that", "station", "stop", "line", "terminal"}


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().strip(",.")


def _is_valid(name: str) -> bool:
    words = name.lower().split()
    return len(words) >= 1 and not all(w in _NOISE for w in words) and len(name) >= 3


_PG_MINUTES_RE = re.compile(
    r"(?:MRT|LRT|KTM|BRT|MONO)\s+(\d+)\s+min\s+\(([^)]+)\)",
    re.IGNORECASE,
)
_MIN_CLAIMED_RE = re.compile(
    r"(\d+)\s*min(?:utes?)?\s+(?:to|from|walk(?:ing)?\s+to)\s+([\w\s]+?)\s+(" + _TRANSIT_TYPES[3:-1] + r")",
    re.IGNORECASE,
)
# "8 Mins walking distance to LRT USJ 21" — transit type before station name
_MIN_PREFIX_CLAIMED_RE = re.compile(
    r"(\d+)\s*min(?:utes?|s)?\s+walk(?:ing)?\s+(?:distance\s+)?(?:to\s+)?(?:MRT|LRT|KTM|BRT|Monorail)\s+([\w\s\d]+?)(?=\s*\n|\s*,|\s*\.|\s{2,}|$)",
    re.IGNORECASE,
)


def extract_transport_claims(text: str) -> list[dict]:
    """Return list of {station_name, claimed_minutes, claimed_text} for explicit time claims."""
    results: list[dict] = []
    seen: set[tuple] = set()

    for m in _PG_MINUTES_RE.finditer(text):
        minutes = int(m.group(1))
        name = _clean(m.group(2))
        key = (name.lower(), minutes)
        if key not in seen and _is_valid(name):
            seen.add(key)
            results.append({"station_name": name, "claimed_minutes": minutes, "claimed_text": m.group(0)})

    for m in _MIN_CLAIMED_RE.finditer(text):
        minutes = int(m.group(1))
        name = _clean(m.group(2))
        key = (name.lower(), minutes)
        if key not in seen and _is_valid(name):
            seen.add(key)
            results.append({"station_name": name, "claimed_minutes": minutes, "claimed_text": m.group(0)})

    for m in _MIN_PREFIX_CLAIMED_RE.finditer(text):
        minutes = int(m.group(1))
        name = _clean(m.group(2))
        key = (name.lower(), minutes)
        if key not in seen and _is_valid(name):
            seen.add(key)
            results.append({"station_name": name, "claimed_minutes": minutes, "claimed_text": m.group(0)})

    return results


def extract_transport_stations(text: str) -> list[str]:
    """Return deduplicated transit station name strings extracted from listing text."""
    results: list[str] = []

    for m in _PG_RE.finditer(text):
        results.append(_clean(m.group(1)))

    for m in _NEAR_RE.finditer(text):
        results.append(_clean(m.group(1)))

    for m in _MIN_RE.finditer(text):
        results.append(_clean(m.group(1)))

    for m in _PREFIX_RE.finditer(text):
        results.append(_clean(m.group(1)))

    # Amenity code fallbacks (from ibilik)
    for code, label in _AMENITY_MAP.items():
        if code in text.lower() and label not in results:
            results.append(label)

    seen: set[str] = set()
    deduped: list[str] = []
    for name in results:
        key = name.lower()
        if key not in seen and _is_valid(name):
            seen.add(key)
            deduped.append(name)

    return deduped
