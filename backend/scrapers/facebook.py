from __future__ import annotations

import logging
import re
import urllib.parse
from datetime import datetime, timezone

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from auth.facebook_session import has_session, load_cookies
from config import settings
from scrapers.base import BaseScraper
from workflow.state import FilterObject, RawListing

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"(?:RM|MYR)\s?([\d,]+)", re.IGNORECASE)
_PHONE_RE = re.compile(r"(\+?6?01[0-9]{7,9})")
_TELEGRAM_RE = re.compile(r"(?:@|t\.me/)(\w{4,})")
_RENTAL_KEYWORDS = {"room", "bilik", "sewa", "rent", "master", "single", "studio"}

_ROOM_KEYWORDS = {
    "master room": "master",
    "master bedroom": "master",
    "single room": "single",
    "single bedroom": "single",
    "studio": "studio",
    "whole unit": "whole_unit",
    "entire unit": "whole_unit",
    "bilik master": "master",
    "bilik single": "single",
}

# Verified working Facebook Marketplace city slugs (tested 2026-04).
# Only slugs that serve Malaysian listings are listed; everything else
# falls back to kualalumpur (40-mile radius covers the Klang Valley).
_LOCATION_SLUG_MAP: list[tuple[list[str], str]] = [
    (["shah alam", "klang", "subang"], "shahalam"),
    (["johor", "jb", "johor bahru"], "johorbahru"),
    (["kota kinabalu", "kk", "sabah"], "kotakinabalu"),
    (["ipoh", "perak"], "ipoh"),
    (["kuching", "sarawak"], "kuching"),
    # Petaling Jaya / Subang / Sunway are within KL's 40-mile radius
]
_DEFAULT_SLUG = "kualalumpur"

_MARKETPLACE_EXTRACT_JS = r"""
() => {
    const seen = new Set();
    const items = [];
    for (const a of document.querySelectorAll('a[href*="/marketplace/item/"]')) {
        const href = a.href.split('?')[0];
        if (!href || seen.has(href)) continue;
        seen.add(href);
        const text = (a.innerText || a.textContent || '').trim();
        const img = a.querySelector('img');
        items.push({ href, text, imgSrc: img ? img.src : '' });
    }
    return items;
}
"""


def _location_to_slug(location: str) -> str:
    lower = location.lower()
    for keywords, slug in _LOCATION_SLUG_MAP:
        if any(kw in lower for kw in keywords):
            return slug
    return _DEFAULT_SLUG


class FacebookScraper(BaseScraper):
    source = "facebook"

    async def scrape(self, filters: FilterObject, max_results: int) -> list[RawListing]:
        fb_session = has_session(settings.fb_cookies_path)
        marketplace_max = max_results // 2 if fb_session else max_results

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
                locale="en-US",
            )
            if fb_session:
                await context.add_cookies(load_cookies(settings.fb_cookies_path))
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            results: list[RawListing] = []
            try:
                marketplace = await self._scrape_marketplace(page, filters, marketplace_max)
                results.extend(marketplace)
                logger.info("FacebookScraper marketplace: %d listings", len(marketplace))
            except Exception as exc:
                logger.warning("FacebookScraper marketplace failed: %s", exc)

            if fb_session:
                remaining = max_results - len(results)
                if remaining > 0:
                    try:
                        posts = await self._scrape_posts(page, filters, remaining)
                        results.extend(posts)
                        logger.info("FacebookScraper posts: %d listings", len(posts))
                    except Exception as exc:
                        logger.warning("FacebookScraper posts failed: %s", exc)

            await browser.close()

        logger.info("FacebookScraper total: %d listings", len(results))
        return results[:max_results]

    async def _scrape_marketplace(self, page, filters: FilterObject, max_results: int) -> list[RawListing]:
        location = filters.location or "Kuala Lumpur"
        slug = _location_to_slug(location)

        room_prefix = ""
        if filters.room_type and filters.room_type not in ("any", "unknown"):
            room_prefix = filters.room_type.replace("_", " ") + " "

        query = f"{room_prefix}room for rent"
        params: dict[str, str] = {
            "query": query,
            "category_id": "propertyrentals",
        }
        if filters.price_min:
            params["minPrice"] = str(filters.price_min)
        if filters.price_max:
            params["maxPrice"] = str(filters.price_max)

        url = f"https://www.facebook.com/marketplace/{slug}/search/?" + urllib.parse.urlencode(params)
        logger.info("FacebookScraper URL: %s", url)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeout:
            logger.warning("FacebookScraper: page load timed out")
            return []

        await self._dismiss_login_overlay(page)

        try:
            await page.wait_for_selector('a[href*="/marketplace/item/"]', timeout=10000)
        except PlaywrightTimeout:
            logger.warning("FacebookScraper: no listing cards appeared")
            return []

        seen_urls: set[str] = set()
        results: list[RawListing] = []

        for _ in range(5):
            raw_cards: list[dict] = await page.evaluate(_MARKETPLACE_EXTRACT_JS)
            for card in raw_cards:
                href = card.get("href", "")
                if not href or not href.startswith("http") or href in seen_urls:
                    continue
                seen_urls.add(href)
                text = card.get("text", "")
                # Skip California results that slip through
                if any(ca in text for ca in (", CA\n", "San Francisco", "Los Angeles", "Oakland")):
                    continue
                pre_parsed = self._parse_marketplace_card(text, card.get("imgSrc", ""), filters)
                if not self._price_in_range(pre_parsed.get("price_rm"), filters):
                    continue
                results.append(RawListing(
                    source="facebook",
                    url=href,
                    raw_text=text,
                    pre_parsed=pre_parsed,
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                ))
                if len(results) >= max_results:
                    break

            if len(results) >= max_results:
                break
            await page.evaluate("window.scrollBy(0, 1200)")
            await self._random_delay()

        return results

    def _parse_marketplace_card(self, text: str, img: str, filters: FilterObject) -> dict:
        pre_parsed: dict = {}
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for line in lines:
            if not _PRICE_RE.search(line) and len(line) > 3:
                pre_parsed["title"] = line[:150]
                break

        price_rm = self._parse_price(text)
        if price_rm is not None:
            pre_parsed["price_rm"] = price_rm

        if len(lines) >= 2:
            pre_parsed["location_raw"] = lines[-1][:100]

        pre_parsed["description_original"] = text[:500]

        if img and img.startswith("http") and "fbcdn" in img:
            pre_parsed["images"] = [img]

        phone_m = _PHONE_RE.search(text)
        if phone_m:
            pre_parsed["contact_phone"] = phone_m.group(1)

        tg_m = _TELEGRAM_RE.search(text)
        if tg_m:
            pre_parsed["contact_telegram"] = f"@{tg_m.group(1)}"

        room_type = self._infer_room_type(text)
        if room_type:
            pre_parsed["room_type"] = room_type

        return pre_parsed

    async def _scrape_posts(self, page, filters: FilterObject, max_results: int) -> list[RawListing]:
        location = filters.location or "Kuala Lumpur"
        room_prefix = ""
        if filters.room_type and filters.room_type not in ("any", "unknown"):
            room_prefix = filters.room_type.replace("_", " ") + " "

        queries = [
            f"{room_prefix}room for rent {location}",
            f"bilik sewa {location}",
        ]

        seen_urls: set[str] = set()
        results: list[RawListing] = []

        for query in queries:
            if len(results) >= max_results:
                break
            url = "https://www.facebook.com/search/posts/?q=" + urllib.parse.quote(query)
            logger.info("FacebookScraper posts URL: %s", url)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeout:
                logger.warning("FacebookScraper posts: page load timed out for query %r", query)
                continue

            await self._dismiss_login_overlay(page)

            try:
                await page.wait_for_selector('[role="article"]', timeout=10000)
            except PlaywrightTimeout:
                logger.warning("FacebookScraper posts: no articles found for query %r", query)
                continue

            for _ in range(3):
                articles = await page.query_selector_all('[role="article"]')
                for article in articles:
                    text = (await article.inner_text() or "").strip()
                    if len(text) < 20 or not self._looks_like_rental(text):
                        continue

                    post_url = None
                    for sel in ('a[href*="/permalink/"]', 'a[href*="story_fbid"]', 'a[href*="?fbid="]'):
                        el = await article.query_selector(sel)
                        if el:
                            href = await el.get_attribute("href") or ""
                            if href:
                                post_url = href.split("?")[0] if "/permalink/" in href else href
                                break

                    if not post_url or post_url in seen_urls:
                        continue
                    seen_urls.add(post_url)

                    pre_parsed = self._parse_post_text(text)
                    if not self._price_in_range(pre_parsed.get("price_rm"), filters):
                        continue

                    results.append(RawListing(
                        source="facebook",
                        url=post_url,
                        raw_text=text,
                        pre_parsed=pre_parsed,
                        scraped_at=datetime.now(timezone.utc).isoformat(),
                    ))
                    if len(results) >= max_results:
                        break

                if len(results) >= max_results:
                    break
                await page.evaluate("window.scrollBy(0, 1200)")
                await self._random_delay()

        return results

    def _parse_post_text(self, text: str) -> dict:
        pre_parsed: dict = {}
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for line in lines:
            if not _PRICE_RE.search(line) and len(line) > 3:
                pre_parsed["title"] = line[:150]
                break

        price_rm = self._parse_price(text)
        if price_rm is not None:
            pre_parsed["price_rm"] = price_rm

        pre_parsed["description_original"] = text[:500]

        phone_m = _PHONE_RE.search(text)
        if phone_m:
            pre_parsed["contact_phone"] = phone_m.group(1)

        tg_m = _TELEGRAM_RE.search(text)
        if tg_m:
            pre_parsed["contact_telegram"] = f"@{tg_m.group(1)}"

        room_type = self._infer_room_type(text)
        if room_type:
            pre_parsed["room_type"] = room_type

        return pre_parsed

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _dismiss_login_overlay(self, page) -> None:
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except Exception:
            pass
        try:
            close_btn = await page.query_selector('[aria-label="Close"]')
            if close_btn:
                await close_btn.click()
                await page.wait_for_timeout(300)
        except Exception:
            pass
        try:
            await page.evaluate(
                "document.querySelectorAll('[role=\"dialog\"]').forEach(e => e.remove());"
                "document.body.style.overflow='auto';"
                "document.body.style.height='auto';"
            )
        except Exception:
            pass

    @staticmethod
    def _looks_like_rental(text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in _RENTAL_KEYWORDS) and _PRICE_RE.search(text) is not None

    @staticmethod
    def _parse_price(text: str) -> int | None:
        m = _PRICE_RE.search(text)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    @staticmethod
    def _infer_room_type(text: str) -> str | None:
        lower = text.lower()
        for keyword, room_type in _ROOM_KEYWORDS.items():
            if keyword in lower:
                return room_type
        return None

    @staticmethod
    def _price_in_range(price_rm: int | None, filters: FilterObject) -> bool:
        if price_rm is None:
            return True
        if filters.price_max and price_rm > filters.price_max * 1.3:
            return False
        if filters.price_min and price_rm < filters.price_min * 0.4:
            return False
        return True
