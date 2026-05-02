from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


async def get_walking_minutes(
    api_key: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> int | None:
    """Return walking time in minutes between two coordinates, or None on failure."""
    payload = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
        "travelMode": "WALK",
        "computeAlternativeRoutes": False,
    }
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(_ROUTES_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            routes = data.get("routes")
            if not routes:
                logger.debug("Routes API returned no routes")
                return None
            duration_str = routes[0].get("duration", "")
            # duration is like "293s"
            seconds = int(duration_str.rstrip("s"))
            return max(1, round(seconds / 60))
    except Exception as exc:
        logger.warning("get_walking_minutes failed: %s", exc)
        return None
