from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from scrapers.base import BaseScraper
from workflow.state import FilterObject, RawListing

logger = logging.getLogger(__name__)

API_BASE = "https://prod-api.ibilik.com/api/v1/client/listings"
LISTING_BASE = "https://www.ibilik.com/room"

HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.ibilik.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

ROOM_TYPE_MAP = {
    "single": "SINGLE",
    "master": "MASTER",
    "studio": "STUDIO",
    "whole_unit": "WHOLE_UNIT",
}


def _transport_amenities(transport: str) -> list[str]:
    if not transport:
        return []
    t = transport.lower()
    amenities: list[str] = []
    if "mrt" in t:
        amenities += ["near-mrt", "near-lrt-mrt"]
    if "lrt" in t:
        amenities += ["near-lrt", "near-ktm-lrt"]
    if "ktm" in t:
        amenities += ["near-ktm", "near-ktm-lrt"]
    if not amenities:
        amenities = ["near-mrt", "near-lrt", "near-ktm"]
    return list(dict.fromkeys(amenities))


def _gender_preferences(gender: str) -> list[str]:
    if gender == "female":
        return ["single-female"]
    if gender == "male":
        return ["single-male"]
    return []


class IbilikScraper(BaseScraper):
    source = "ibilik"

    async def scrape(self, filters: FilterObject, max_results: int) -> list[RawListing]:
        results: list[RawListing] = []
        page = 1

        async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
            loc_filter_key, loc_filter_val = await self._resolve_location(
                client, filters.location_city or filters.location or "kuala-lumpur"
            )
            logger.info("IbilikScraper resolved location: %s=%s", loc_filter_key, loc_filter_val)

            while len(results) < max_results:
                params = self._build_params(
                    filters, page, min(15, max_results - len(results)),
                    loc_filter_key, loc_filter_val,
                )
                logger.info("IbilikScraper API page %d", page)

                try:
                    data = await self._with_retry(lambda p=params, c=client: self._fetch(c, p))
                except Exception as exc:
                    logger.error("IbilikScraper API failed: %s", exc)
                    break

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    listing = self._parse_item(item)
                    if listing:
                        results.append(listing)

                pagination = data.get("pagination", {})
                if page >= pagination.get("totalPages", 1):
                    break

                page += 1
                await self._random_delay()

        logger.info("IbilikScraper collected %d listings", len(results))
        return results[:max_results]

    async def _resolve_location(
        self, client: httpx.AsyncClient, location: str
    ) -> tuple[str, str]:
        """Try city → area → state in order, return the filter key+value that has results."""
        slug = self._location_slug(location)
        for filter_key in ("filter[city]", "filter[area]", "filter[state]"):
            try:
                resp = await client.get(API_BASE, params={
                    "limit": 1, "page": 1,
                    filter_key: slug,
                    "filter[types]": "ROOM",
                })
                data = resp.json()
                if data.get("pagination", {}).get("totalItems", 0) > 0:
                    return filter_key, slug
            except Exception:
                pass
        # No results under any level — fall back to city (will return empty gracefully)
        return "filter[city]", slug

    def _build_params(
        self, filters: FilterObject, page: int, limit: int,
        loc_key: str, loc_val: str,
    ) -> dict:
        params: dict = {
            "limit": limit,
            "page": page,
            "sortBy": "published_at",
            "sortDirection": "desc",
            loc_key: loc_val,
            "filter[types]": "ROOM",
        }
        if filters.price_min:
            params["filter[minPrice]"] = filters.price_min
        if filters.price_max:
            params["filter[maxPrice]"] = filters.price_max

        room_type = ROOM_TYPE_MAP.get(filters.room_type)
        if room_type:
            params["filter[roomTypes]"] = room_type

        amenities = _transport_amenities(filters.transport)
        if amenities:
            params["filter[amenities]"] = ",".join(amenities)

        prefs = _gender_preferences(filters.gender_restriction)
        if prefs:
            params["filter[preferences]"] = ",".join(prefs)

        return params

    async def _fetch(self, client: httpx.AsyncClient, params: dict) -> dict:
        resp = await client.get(API_BASE, params=params)
        resp.raise_for_status()
        return resp.json()

    def _parse_item(self, item: dict) -> RawListing | None:
        try:
            listing_id = item.get("id", "")
            slug = item.get("slug", "")
            url = f"{LISTING_BASE}/{listing_id}/{slug}"

            locale = (item.get("locales") or {}).get("en-US", {})
            title = locale.get("title", "").strip()
            description = locale.get("description", "").strip()[:500]

            # Price from ratePlans
            price_rm: int | None = None
            for plan in item.get("ratePlans") or []:
                if plan.get("chargeUnit") == "PER_MONTH":
                    price_rm = int(plan["chargeAmount"])
                    break

            # Location
            area_name = ((item.get("area") or {}).get("locales") or {}).get("en-US", {}).get("name", "")
            city_name = ((item.get("city") or {}).get("locales") or {}).get("en-US", {}).get("name", "")
            state_name = ((item.get("state") or {}).get("locales") or {}).get("en-US", {}).get("name", "")
            location_raw = ", ".join(filter(None, [area_name, city_name, state_name]))
            lat = item.get("latitude")
            lng = item.get("longitude")

            # Room type
            room_info = item.get("longTermRoomRentalListing") or {}
            room_type_raw = room_info.get("roomType", "")

            # Contact
            contact_phone: str | None = None
            contact_telegram: str | None = None
            for ci in item.get("contactInformation") or []:
                contact = ci.get("contact") or {}
                ctype = contact.get("contactType", "")
                cval = contact.get("contactValue", "")
                if ctype == "PHONE" and not contact_phone:
                    contact_phone = cval
                elif ctype in ("TELEGRAM", "WHATSAPP") and not contact_telegram:
                    contact_telegram = cval

            # Images
            images = [
                img["url"] for img in (item.get("images") or [])
                if img.get("url")
            ]

            # Amenity codes for raw_text context
            amenity_names = [
                (a.get("amenity") or {}).get("code", "")
                for a in (item.get("amenities") or [])
            ]

            raw_text = " | ".join(filter(None, [
                title,
                f"RM {price_rm}/month" if price_rm else "",
                location_raw,
                room_type_raw,
                " ".join(amenity_names),
                description[:200],
            ]))

            pre_parsed: dict = {
                "title": title,
                "location_raw": location_raw,
                "location_area": area_name,
                "location_city": city_name,
                "description_original": description,
            }
            if price_rm is not None:
                pre_parsed["price_rm"] = price_rm
            if lat:
                pre_parsed["lat"] = lat
            if lng:
                pre_parsed["lng"] = lng
            if room_type_raw:
                pre_parsed["room_type"] = room_type_raw.lower()
            if contact_phone:
                pre_parsed["contact_phone"] = contact_phone
            if contact_telegram:
                pre_parsed["contact_telegram"] = contact_telegram
            if images:
                pre_parsed["images"] = images

            return RawListing(
                source="ibilik",
                url=url,
                raw_text=raw_text,
                pre_parsed=pre_parsed,
                scraped_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as exc:
            logger.debug("IbilikScraper parse error: %s", exc)
            return None
