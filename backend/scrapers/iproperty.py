from __future__ import annotations

import logging
from datetime import datetime, timezone

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from scrapers.base import BaseScraper
from workflow.state import FilterObject, RawListing

logger = logging.getLogger(__name__)

BASE_URL = "https://www.iproperty.com.my"
SEARCH_PATH = "/property-for-rent"

_CF_CHALLENGE_SIGNALS = ("cdn-cgi", "challenges.cloudflare.com")

_EXTRACT_JS = r"""
() => {
    const cards = document.querySelectorAll("[da-id='parent-listing-card-v2-regular']");
    return Array.from(cards).map(card => {
        const link = card.querySelector("a[href*='/property/']");
        const titleLocEl = card.querySelector(".title-location");
        const priceEl = card.querySelector(".price-title-wrapper");
        const gallery = card.querySelector("[da-id='listing-card-v2-gallery']");
        const imgEl = gallery
            ? gallery.querySelector("img[src*='img.iproperty']") || gallery.querySelector("img[src]")
            : null;

        const priceRaw = priceEl ? priceEl.innerText : '';
        const price = priceRaw.split('\n')[0].trim();

        const locRaw = titleLocEl ? titleLocEl.innerText : '';
        const locLines = locRaw.split('\n').filter(s => s.trim());
        const title = locLines[0] || '';
        const location = locLines.slice(1).join(', ');

        return {
            href: link ? link.href : '',
            title: title,
            location: location,
            price: price,
            imgSrc: imgEl ? imgEl.src : ''
        };
    });
}
"""


class IPropertyScraper(BaseScraper):
    source = "iproperty"

    async def scrape(self, filters: FilterObject, max_results: int) -> list[RawListing]:
        results: list[RawListing] = []

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

            page_num = 1
            while len(results) < max_results:
                url = self._build_url(filters, page_num)
                logger.info("IPropertyScraper page %d: %s", page_num, url)

                try:
                    cards = await self._with_retry(
                        lambda u=url: self._load_and_parse(page, u)
                    )
                except PlaywrightTimeout:
                    logger.warning("IPropertyScraper: timeout on page %d", page_num)
                    break
                except Exception as exc:
                    logger.error("IPropertyScraper page %d failed: %s", page_num, exc)
                    break

                if not cards:
                    break

                results.extend(cards[: max_results - len(results)])

                if not await self._has_next_page(page):
                    break

                page_num += 1
                await self._random_delay()

            await browser.close()

        logger.info("IPropertyScraper collected %d listings", len(results))
        return results

    def _build_url(self, filters: FilterObject, page: int) -> str:
        import urllib.parse

        location = filters.location_city or filters.location or "Kuala Lumpur"
        params: list[str] = [
            "listingType=rent",
            "isCommercial=false",
            f"page={page}",
            f"_freetextDisplay={urllib.parse.quote_plus(location)}",
        ]
        if filters.price_min:
            params.append(f"minPrice={filters.price_min}")
        if filters.price_max:
            params.append(f"maxPrice={filters.price_max}")

        return f"{BASE_URL}{SEARCH_PATH}?{'&'.join(params)}"

    async def _load_and_parse(self, page, url: str) -> list[RawListing]:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # If served a Cloudflare JS challenge, wait for it to auto-resolve
        if await self._is_cf_challenge(page):
            logger.info("IPropertyScraper: CF challenge detected, waiting for resolution…")
            try:
                await page.wait_for_url(
                    lambda u: not any(s in u for s in _CF_CHALLENGE_SIGNALS),
                    timeout=20000,
                )
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightTimeout:
                logger.warning("IPropertyScraper: CF challenge did not resolve in time")

        try:
            await page.wait_for_selector(
                "[da-id='parent-listing-card-v2-regular']",
                timeout=20000,
            )
        except PlaywrightTimeout:
            title = await page.title()
            logger.warning("IPropertyScraper: no listing cards on %s (title: %s)", url, title)
            return []

        return await self._extract_cards(page)

    async def _extract_cards(self, page) -> list[RawListing]:
        raw_cards: list[dict] = await page.evaluate(_EXTRACT_JS)

        listings: list[RawListing] = []
        for card in raw_cards:
            href = card.get("href", "")
            if not href:
                continue
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            title = card.get("title", "")
            price_text = card.get("price", "")
            location_raw = card.get("location", "")
            image = card.get("imgSrc", "")

            raw_text = " | ".join(filter(None, [title, price_text, location_raw]))

            pre_parsed: dict = {}
            if title:
                pre_parsed["title"] = title
            if location_raw:
                pre_parsed["location_raw"] = location_raw
            price_rm = self._parse_price(price_text)
            if price_rm is not None:
                pre_parsed["price_rm"] = price_rm
            if image and image.startswith("http") and "iproperty" in image:
                pre_parsed["images"] = [image]

            listings.append(RawListing(
                source="iproperty",
                url=url,
                raw_text=raw_text,
                pre_parsed=pre_parsed,
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ))

        return listings

    @staticmethod
    async def _is_cf_challenge(page) -> bool:
        try:
            url = page.url
            content = await page.content()
            return any(s in url for s in _CF_CHALLENGE_SIGNALS) or "challenges.cloudflare.com" in content
        except Exception:
            return False

    @staticmethod
    async def _has_next_page(page) -> bool:
        try:
            btn = await page.query_selector(
                "[data-testid='pagination-next']:not([disabled]), "
                "a[aria-label='Next page']:not([disabled])"
            )
            return btn is not None
        except Exception:
            return False

    @staticmethod
    def _parse_price(text: str) -> int | None:
        import re
        m = re.search(r"RM\s*([\d,]+)", text.replace(",", ""))
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None
