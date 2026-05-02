from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


async def get_walking_minutes(
    api_key: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> int | None:
    """Return walking time in minutes between two coordinates, or None on failure."""
    params = {
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{dest_lat},{dest_lng}",
        "mode": "walking",
        "key": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(DISTANCE_MATRIX_URL, params=params)
            response.raise_for_status()
            data = response.json()
            element = data["rows"][0]["elements"][0]
            if element.get("status") != "OK":
                logger.debug("Distance Matrix non-OK status: %s", element.get("status"))
                return None
            seconds = element["duration"]["value"]
            return max(1, round(seconds / 60))
    except Exception as exc:
        logger.warning("get_walking_minutes failed: %s", exc)
        return None
