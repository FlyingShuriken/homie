from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper
from workflow.state import FilterObject, RawListing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.propertyguru.com.my"
DEFAULT_ROOM_URL = f"{BASE_URL}/property-for-rent/p/room-for-rent"
DEFAULT_GENERAL_URL = f"{BASE_URL}/property-for-rent/p/properties-for-malaysia-rent"

_CF_CHALLENGE_SIGNALS = ("cdn-cgi", "challenges.cloudflare.com")
_PRICE_RE = re.compile(r"RM\s*([\d,]+)")
_LISTED_ON_RE = re.compile(r"Listed on ([A-Za-z]{3} \d{1,2}, \d{4})", re.IGNORECASE)
_TRANSPORT_RE = re.compile(
    r"((?:MRT|LRT|KTM|BRT|MONO)\s+\d+\s+min\s+\([^)]+\)\s+from\s+.+?)(?=\s+Listed on|\s+Contact|\s+WhatsApp|$)",
    re.IGNORECASE,
)
_FEATURE_END_RE = re.compile(
    r"\b("
    r"Master Room|Common Room|Shared Room|Single Room|Medium Room|Room|Studio|"
    r"Service Residence|Condominium|Apartment|Flat|Terraced House|"
    r"Semi-Detached House|Bungalow|Residential Land|Listed on|Built:|"
    r"Available from|Ready to Move|MRT|LRT|KTM|BRT|MONO"
    r")\b",
    re.IGNORECASE,
)
_TRAILING_SIZE_RE = re.compile(
    r"(?:\s+\d+\+?\d*){1,4}\s+\d[\d,]*\s+sqft(?:\s+\([^)]+\))?(?:,\s*\d[\d,]*\s+sqft\s+\([^)]+\))?$",
    re.IGNORECASE,
)
_STATE_LIKE_PARTS = {
    "johor",
    "kedah",
    "kelantan",
    "melaka",
    "negeri sembilan",
    "pahang",
    "penang",
    "perak",
    "perlis",
    "pulau pinang",
    "putrajaya",
    "sabah",
    "sarawak",
    "selangor",
    "terengganu",
}
_LOCATION_ALIASES = {
    "pj": "petaling jaya",
    "kl": "kuala lumpur",
    "jb": "johor bahru",
}
_REGION_ROOM_URLS: list[tuple[list[str], str]] = [
    (["petaling jaya", "pj"], f"{BASE_URL}/property-for-rent/p/room-for-rent-in-petaling-jaya"),
    (["kuala lumpur", "kl"], f"{BASE_URL}/property-for-rent/p/rooms-for-rent-in-kuala-lumpur"),
    (
        [
            "selangor",
            "cheras",
            "subang",
            "sunway",
            "puchong",
            "kajang",
            "klang",
            "shah alam",
            "cyberjaya",
            "damansara",
            "seri kembangan",
            "ampang",
            "batu caves",
            "rawang",
            "setia alam",
        ],
        f"{BASE_URL}/property-for-rent/p/room-for-rent-in-selangor",
    ),
    (["johor bahru", "jb", "johor"], f"{BASE_URL}/property-for-rent/p/room-for-rent-in-johor-bahru"),
    (["penang", "george town", "georgetown"], f"{BASE_URL}/property-for-rent/p/room-for-rent-in-penang"),
]

_EXTRACT_JS = r"""
() => {
    const normalize = (value) => (value || "").replace(/\s+/g, " ").trim();

    const findImage = (anchor) => {
        let node = anchor;
        for (let depth = 0; depth < 4 && node; depth += 1, node = node.parentElement) {
            const imgs = Array.from(node.querySelectorAll("img[src]"));
            const match = imgs.find((img) => {
                const src = img.getAttribute("src") || "";
                const alt = (img.getAttribute("alt") || "").toLowerCase();
                if (!src || src.startsWith("data:")) return false;
                if (alt.includes("logo") || alt.includes("chevron")) return false;
                return true;
            });
            if (match) return match.src;
        }
        return "";
    };

    const bestByHref = new Map();
    for (const anchor of document.querySelectorAll("a[href*='/property-listing/']")) {
        const href = (anchor.href || "").split("?")[0];
        const text = normalize(anchor.innerText || anchor.textContent);
        if (!href || !text) continue;

        const candidate = {
            href,
            text,
            imgSrc: findImage(anchor),
            score: text.length,
        };

        const prev = bestByHref.get(href);
        if (!prev || candidate.score > prev.score) {
            bestByHref.set(href, candidate);
        }
    }

    return Array.from(bestByHref.values()).map(({ href, text, imgSrc }) => ({
        href,
        text,
        imgSrc,
    }));
}
"""


class CloudflareBlockedError(RuntimeError):
    pass


class PropertyGuruScraper(BaseScraper):
    source = "propertyguru"

    async def scrape(self, filters: FilterObject, max_results: int) -> list[RawListing]:
        results: list[RawListing] = []
        seen_urls: set[str] = set()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-GB",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            search_url, page_cards, require_location_match = await self._select_search_url(page, filters)
            if not search_url or not page_cards:
                logger.info("PropertyGuruScraper skipped: no usable search page after challenge handling")
                await browser.close()
                return []

            logger.info("PropertyGuruScraper using search URL: %s", search_url)

            while len(results) < max_results:
                for card in page_cards:
                    listing = self._parse_card(
                        card,
                        filters=filters,
                        require_location_match=require_location_match,
                    )
                    if not listing or listing.url in seen_urls:
                        continue
                    seen_urls.add(listing.url)
                    results.append(listing)
                    if len(results) >= max_results:
                        break

                if len(results) >= max_results:
                    break

                next_url = await self._next_page_url(page)
                if not next_url:
                    break

                logger.info("PropertyGuruScraper next page: %s", next_url)
                try:
                    page_cards = await self._with_retry(
                        lambda u=next_url: self._load_and_extract(page, u)
                    )
                except CloudflareBlockedError as exc:
                    logger.warning("PropertyGuruScraper pagination skipped after Cloudflare block: %s", exc)
                    break
                except PlaywrightTimeout:
                    logger.warning("PropertyGuruScraper: pagination timed out")
                    break
                except Exception as exc:
                    logger.warning("PropertyGuruScraper next page failed: %s", exc)
                    break

                if not page_cards:
                    break

                await self._random_delay()

            await browser.close()

        logger.info("PropertyGuruScraper collected %d listings", len(results))
        return results[:max_results]

    async def _select_search_url(
        self,
        page,
        filters: FilterObject,
    ) -> tuple[str, list[dict], bool]:
        slug = self._location_slug(filters.location_city or filters.location or "")
        fallback: tuple[str, list[dict], bool] | None = None

        for url in self._build_candidate_urls(filters):
            logger.info("PropertyGuruScraper trying candidate URL: %s", url)
            try:
                cards = await self._with_retry(lambda u=url: self._load_and_extract(page, u))
            except CloudflareBlockedError as exc:
                logger.warning("PropertyGuruScraper skipped after repeated Cloudflare blocks: %s", exc)
                return "", [], False
            except Exception as exc:
                logger.debug("PropertyGuruScraper candidate failed %s: %s", url, exc)
                continue

            if not cards:
                continue

            location_hits = sum(
                1 for card in cards
                if self._location_match_score(card.get("text", ""), filters) > 0
            )

            logger.info(
                "PropertyGuruScraper candidate %s yielded %d cards (%d location hits)",
                url,
                len(cards),
                location_hits,
            )

            if fallback is None:
                fallback = (url, cards, location_hits > 0)

            if location_hits > 0 or (slug and slug in url):
                return url, cards, location_hits > 0

        return fallback if fallback else ("", [], False)

    def _build_candidate_urls(self, filters: FilterObject) -> list[str]:
        location = filters.location_area or filters.location_city or filters.location or "kuala lumpur"
        slug = self._location_slug(location)
        candidates: list[str] = []

        room_candidates = [
            f"{BASE_URL}/property-for-rent/p/room-for-rent-in-{slug}",
            f"{BASE_URL}/property-for-rent/p/rooms-for-rent-in-{slug}",
        ]
        general_candidates = [
            f"{BASE_URL}/property-for-rent/p/{slug}",
            f"{BASE_URL}/property-for-rent/p/property-for-in-{slug}-rent",
            f"{BASE_URL}/property-for-rent/p/{slug}-rental",
        ]

        if filters.room_type in ("whole_unit", "studio"):
            candidates.extend(general_candidates)
        else:
            candidates.extend(room_candidates)
            candidates.extend(general_candidates)

        region_room_url = self._region_room_url(location)
        if region_room_url:
            candidates.append(region_room_url)

        candidates.append(DEFAULT_GENERAL_URL if filters.room_type in ("whole_unit", "studio") else DEFAULT_ROOM_URL)
        return list(dict.fromkeys(candidates))

    def _region_room_url(self, location: str) -> str:
        normalized = self._normalize_text(location)
        for keywords, url in _REGION_ROOM_URLS:
            if any(self._normalize_text(keyword) in normalized for keyword in keywords):
                return url
        return ""

    async def _load_and_extract(self, page, url: str) -> list[dict]:
        await self._load_page(page, url)
        return await self._extract_cards(page)

    async def _load_page(self, page, url: str) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if await self._is_cf_challenge(page):
            logger.warning("PropertyGuruScraper: Cloudflare challenge detected")
            await page.wait_for_timeout(5000)
            if await self._is_cf_challenge(page):
                raise CloudflareBlockedError(
                    "PropertyGuru blocked the scraper with a security verification page"
                )

        await page.wait_for_selector("a[href*='/property-listing/']", timeout=20000)

    async def _extract_cards(self, page) -> list[dict]:
        raw_cards: list[dict] = await page.evaluate(_EXTRACT_JS)
        return [
            card for card in raw_cards
            if self._looks_like_listing(card.get("text", ""))
        ]

    async def _next_page_url(self, page) -> str:
        try:
            return await page.evaluate(
                """() => {
                    const links = Array.from(document.querySelectorAll("a[href]"));
                    const next = links.find((link) => (link.textContent || "").trim() === "Next");
                    return next ? next.href : "";
                }"""
            )
        except Exception:
            return ""

    @staticmethod
    async def _is_cf_challenge(page) -> bool:
        try:
            url = page.url
            content = await page.content()
            title = (await page.title()).lower()
            lowered_content = content.lower()
            return (
                any(s in url for s in _CF_CHALLENGE_SIGNALS)
                or "challenges.cloudflare.com" in lowered_content
                or "just a moment" in title
                or "performing security verification" in lowered_content
                or "verify you are not a bot" in lowered_content
            )
        except Exception:
            return False

    def _parse_card(
        self,
        card: dict,
        filters: FilterObject,
        require_location_match: bool,
    ) -> RawListing | None:
        href = card.get("href", "").strip()
        text = self._clean_text(card.get("text", ""))
        if not href or not text or not self._looks_like_listing(text):
            return None

        if require_location_match and self._location_match_score(text, filters) == 0:
            return None

        price_rm = self._parse_price(text)
        if price_rm is not None:
            if filters.price_min and price_rm < filters.price_min:
                return None
            if filters.price_max and price_rm > filters.price_max:
                return None

        room_type = self._parse_room_type(text)
        if not self._room_type_matches(filters.room_type, room_type):
            return None

        location_raw = self._extract_location(text)
        title = self._extract_title(text) or location_raw.split(",")[0].strip()
        location_area, location_city = self._split_location_parts(location_raw, filters)

        pre_parsed: dict = {
            "title": title,
            "location_raw": location_raw,
            "location_area": location_area,
            "location_city": location_city,
            "description_original": text[:500],
        }

        if price_rm is not None:
            pre_parsed["price_rm"] = price_rm
        if room_type != "unknown":
            pre_parsed["room_type"] = room_type

        posted_date = self._parse_posted_date(text)
        if posted_date:
            pre_parsed["posted_date"] = posted_date

        gender = self._parse_gender(text)
        if gender:
            pre_parsed["gender_restriction"] = gender

        furnished_status = self._parse_furnished_status(text)
        if furnished_status:
            pre_parsed["furnished_status"] = furnished_status

        transport = self._parse_transport(text)
        if transport:
            pre_parsed["nearby_transport"] = [transport]

        image = card.get("imgSrc", "")
        if image.startswith("http"):
            pre_parsed["images"] = [image]

        return RawListing(
            source="propertyguru",
            url=href,
            raw_text=text[:500],
            pre_parsed=pre_parsed,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _looks_like_listing(text: str) -> bool:
        lowered = text.lower()
        return (
            "/mo" in lowered
            and "listed on" in lowered
            and "propertyguru" not in lowered
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def _location_terms(self, filters: FilterObject) -> list[str]:
        raw_values = [
            filters.location_area,
            filters.location_city,
            filters.location_state,
            filters.location,
        ]

        terms: list[str] = []
        for value in raw_values:
            if not value:
                continue
            normalized = self._normalize_text(value)
            if not normalized:
                continue
            terms.append(normalized)

            if normalized in _LOCATION_ALIASES:
                terms.append(_LOCATION_ALIASES[normalized])

            for token in normalized.split():
                if len(token) >= 3:
                    terms.append(_LOCATION_ALIASES.get(token, token))

        return list(dict.fromkeys(terms))

    def _location_match_score(self, text: str, filters: FilterObject) -> int:
        normalized_text = f" {self._normalize_text(text)} "
        score = 0
        for term in self._location_terms(filters):
            if f" {term} " in normalized_text:
                score += max(2, len(term.split()))
        return score

    @staticmethod
    def _parse_price(text: str) -> int | None:
        match = _PRICE_RE.search(text)
        if not match:
            return None
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None

    def _extract_title(self, text: str) -> str:
        price_match = _PRICE_RE.search(text)
        if not price_match:
            return text[:160]
        return text[: price_match.start()].strip(" -|")

    def _extract_location(self, text: str) -> str:
        price_match = _PRICE_RE.search(text)
        if not price_match:
            return ""

        tail = text[price_match.end():].strip()
        end_match = _FEATURE_END_RE.search(tail)
        segment = tail[: end_match.start()] if end_match else tail
        segment = _TRAILING_SIZE_RE.sub("", segment).strip(" ,|-")
        return segment[:220]

    def _split_location_parts(
        self,
        location_raw: str,
        filters: FilterObject,
    ) -> tuple[str, str]:
        parts = [
            self._clean_location_part(part)
            for part in location_raw.split(",")
            if part.strip()
        ]

        if not parts:
            fallback = filters.location_city or filters.location or "unknown"
            return fallback, fallback

        last = self._normalize_text(parts[-1])
        if len(parts) >= 2 and last in _STATE_LIKE_PARTS:
            city = parts[-2]
            area = parts[-3] if len(parts) >= 3 else parts[-2]
        elif len(parts) >= 2:
            city = parts[-1]
            area = parts[-2]
        else:
            city = filters.location_city or filters.location or parts[0]
            area = parts[0]

        if len(area) > 40 or any(ch.isdigit() for ch in area):
            area = city

        return area, city

    @staticmethod
    def _clean_location_part(part: str) -> str:
        cleaned = part.strip()
        cleaned = _TRAILING_SIZE_RE.sub("", cleaned).strip(" ,|-")
        return cleaned

    @staticmethod
    def _parse_posted_date(text: str) -> str | None:
        match = _LISTED_ON_RE.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _parse_transport(text: str) -> str | None:
        match = _TRANSPORT_RE.search(text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_gender(text: str) -> str | None:
        lowered = text.lower()
        has_female = "female" in lowered
        has_male = "male" in lowered
        if has_female and has_male:
            return "mixed"
        if has_female:
            return "female"
        if has_male:
            return "male"
        if "mixed" in lowered:
            return "mixed"
        return None

    @staticmethod
    def _parse_furnished_status(text: str) -> str | None:
        lowered = text.lower()
        if "fully furnished" in lowered:
            return "fully"
        if "partially furnished" in lowered:
            return "partially"
        if "unfurnished" in lowered:
            return "unfurnished"
        return None

    @staticmethod
    def _parse_room_type(text: str) -> str:
        lowered = text.lower()
        if "master room" in lowered or "master bedroom" in lowered:
            return "master"
        if "common room" in lowered or "single room" in lowered or "medium room" in lowered:
            return "single"
        if "shared room" in lowered:
            return "single"
        if re.search(r"\bstudio\b", lowered):
            return "studio"
        if re.search(r"\broom\b", lowered):
            return "single"
        if re.search(
            r"\b(service residence|condominium|apartment|flat|terraced house|semi-detached house|bungalow)\b",
            lowered,
        ):
            return "whole_unit"
        return "unknown"

    @staticmethod
    def _room_type_matches(desired: str, actual: str) -> bool:
        if desired in ("", "any", "unknown"):
            return True
        return desired == actual
