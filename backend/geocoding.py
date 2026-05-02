from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def geocode(
    api_key: str,
    title: str,
    location_city: str,
    location_raw: str,
) -> tuple[float, float] | None:
    if not api_key:
        return None

    async with httpx.AsyncClient(timeout=10) as client:
        # Try precise query first: building name + city
        result = await _query(client, api_key, f"{title}, {location_city}, Malaysia")
        if result:
            return result

        # Fallback: area-level using location_raw
        if location_raw:
            result = await _query(client, api_key, f"{location_raw}, Malaysia")
            if result:
                return result

    return None


async def _query(
    client: httpx.AsyncClient, api_key: str, address: str
) -> tuple[float, float] | None:
    try:
        resp = await client.get(
            GEOCODING_URL, params={"address": address, "key": api_key}
        )
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception as exc:
        logger.warning("Geocoding failed for %r: %s", address, exc)
    return None
