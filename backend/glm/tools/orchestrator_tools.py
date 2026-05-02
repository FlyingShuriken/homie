from __future__ import annotations

import dataclasses
import asyncio
import importlib
import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Callable, Awaitable

from config import settings
from glm import client as glm_client
from glm.extractor import (
    apply_deterministic_extraction,
    extract_listing_fields,
    merge_extracted,
)
from places import apply_google_place_enrichment, enrich_listing_with_google_place
from transport import extract_transport_claims, extract_transport_stations
from walking import get_walking_minutes
from workflow.state import FilterObject, NormalizedListing, ProgressEvent, RawListing, ScoreResult, SessionState

logger = logging.getLogger(__name__)


# ── Tool JSON definitions (sent to GLM API) ───────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "validate_filters",
            "description": "Parse and validate the user's raw filter inputs. Resolves ambiguous location strings to canonical area names. Must be the first tool called.",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_input": {
                        "type": "object",
                        "description": "The raw filter inputs from the user (location, price_min, price_max, room_type, etc.)",
                    }
                },
                "required": ["raw_input"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_scraper",
            "description": "Execute a scraper for a specific rental platform and collect raw listings. Call once per source you want to include.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["ibilik", "iproperty", "propertyguru", "facebook"],
                        "description": "The rental platform to scrape.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of listings to fetch from this source.",
                    },
                },
                "required": ["source", "max_results"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "normalize_listings",
            "description": "Extract structured fields from raw listings, translate non-English content, and deduplicate. Call after scraping is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of raw listings to normalize. Pass an empty array to normalize all pending raw listings.",
                    }
                },
                "required": ["listing_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_listings",
            "description": "Score all normalized listings against the user's filters using the 8-dimension deterministic scoring algorithm. Returns aggregate score statistics.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate a plain-language summary report of the search findings. Call after scoring is complete.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_outreach",
            "description": "Draft professional inquiry messages for selected listings and prepare Telegram deep links or phone fallbacks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of listings to prepare outreach for.",
                    }
                },
                "required": ["listing_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Pause the workflow and ask the user a clarifying question before continuing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The clarifying question to ask the user.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Brief explanation of why this clarification is needed.",
                    },
                },
                "required": ["question", "context"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relax_filters",
            "description": "Suggest filter relaxation to the user when results are poor (avg_score < 35 or too few listings found).",
            "parameters": {
                "type": "object",
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific, actionable filter relaxation suggestions (e.g. 'Expand price range to RM 900', 'Include nearby area Ampang').",
                    }
                },
                "required": ["suggestions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_transport_claims",
            "description": (
                "Verify walking distance claims in listing descriptions against Google Maps actual walking times. "
                "Call after score_listings with the top listing IDs. Updates transport_stops with "
                "actual_walk_minutes and walk_verified, and adds low_confidence_flags for inaccurate claims."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "listing_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of top listings to verify. Pass top 10 by score.",
                    }
                },
                "required": ["listing_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Mark the workflow as complete. Always call this as the final step after generate_report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "One-sentence summary of what was accomplished.",
                    }
                },
                "required": ["summary"],
            },
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def _score_explanation_fallback(breakdown: dict, total: float) -> str:
    """Rule-based fallback when GLM batch call fails."""
    parts = []
    if breakdown.get("price", 0) >= 25:
        parts.append("great price")
    elif breakdown.get("price", 0) < 5:
        parts.append("over budget")
    if breakdown.get("room_type", 0) == 15:
        parts.append("room type matches")
    elif breakdown.get("room_type", 0) == 0:
        parts.append("room type mismatch")
    if breakdown.get("location", 0) >= 18:
        parts.append("in target area")
    elif breakdown.get("location", 0) < 5:
        parts.append("outside target area")
    return f"Score {total}/100 — " + (", ".join(parts) if parts else "no strong signals")


def build_tools_map(
    state: SessionState,
    event_emitter: Callable[[ProgressEvent], Awaitable[None]],
) -> dict[str, Callable]:
    """Return a tools_map dict with closures over state and event_emitter."""

    async def validate_filters(raw_input: dict) -> dict:
        filter_fields = {f.name for f in dataclasses.fields(FilterObject)}
        valid_kwargs = {k: v for k, v in raw_input.items() if k in filter_fields}
        state.filters = FilterObject(**valid_kwargs)
        return {
            "status": "ok",
            "filters": dataclasses.asdict(state.filters),
            "clarifications_needed": [],
            "message": (
                f"Filters validated. Location: {state.filters.location}, "
                f"price RM {state.filters.price_min}–{state.filters.price_max}, "
                f"room type: {state.filters.room_type}."
            ),
        }

    async def run_scraper(source: str, max_results: int) -> dict:
        if state.filters is None:
            state.scraper_failures.append({"source": source, "reason": "filters not validated"})
            return {
                "source": source,
                "listings_collected": 0,
                "failure": True,
                "message": "validate_filters must be called before run_scraper.",
            }

        # ── DEMO_SEED: return fixture data instead of live scraping ──────────
        if settings.demo_seed:
            fixture_map = {
                "ibilik": "ibilik_seed.json",
                "iproperty": "iproperty_seed.json",
                "propertyguru": "propertyguru_seed.json",
                "facebook": "facebook_seed.json",
            }
            if source not in fixture_map:
                state.scraper_failures.append({
                    "source": source,
                    "reason": f"demo_seed: no fixture for '{source}'",
                })
                return {
                    "source": source,
                    "listings_collected": 0,
                    "failure": True,
                    "message": f"No fixture for '{source}' in demo_seed mode.",
                }
            fixture_path = (
                pathlib.Path(__file__).parent.parent.parent
                / "tests" / "fixtures" / fixture_map[source]
            )
            try:
                raw_data: list[dict] = json.loads(fixture_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                logger.error("demo_seed fixture load failed for %s: %s", source, exc)
                state.scraper_failures.append({"source": source, "reason": str(exc)})
                return {
                    "source": source,
                    "listings_collected": 0,
                    "failure": True,
                    "message": f"Fixture load error: {exc}",
                }
            for item in raw_data:
                state.raw_listings.append(RawListing(
                    source=item["source"],
                    url=item["url"],
                    raw_text=item["raw_text"],
                    pre_parsed=item.get("pre_parsed", {}),
                    scraped_at=item.get("scraped_at", ""),
                ))
            n = len(raw_data)
            logger.info("demo_seed: loaded %d fixtures for %s", n, source)
            return {
                "source": source,
                "listings_collected": n,
                "failure": False,
                "message": f"demo_seed: loaded {n} fixture listings for {source}.",
            }

        # ── Live scraping dispatch ────────────────────────────────────────────
        scraper_map = {
            "ibilik": ("scrapers.ibilik", "IbilikScraper"),
            "iproperty": ("scrapers.iproperty", "IPropertyScraper"),
            "propertyguru": ("scrapers.propertyguru", "PropertyGuruScraper"),
            "facebook": ("scrapers.facebook", "FacebookScraper"),
        }
        if source not in scraper_map:
            state.scraper_failures.append({"source": source, "reason": f"unknown source '{source}'"})
            return {
                "source": source,
                "listings_collected": 0,
                "failure": True,
                "message": f"Unknown scraper source: {source}",
            }

        if source == "facebook":
            from auth.facebook_session import has_session
            state.fb_login_required = bool(
                settings.fb_cookies_path and not has_session(settings.fb_cookies_path)
            )
            if state.fb_login_required:
                await event_emitter(ProgressEvent(
                    stage="fb_login_required",
                    status="started",
                    message="Connect Facebook to unlock post search results.",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ))

        module_name, class_name = scraper_map[source]
        module = importlib.import_module(module_name)
        scraper = getattr(module, class_name)()
        effective_max = min(max_results, settings.max_listings_per_source)

        try:
            listings = await scraper.scrape(filters=state.filters, max_results=effective_max)
        except Exception as exc:
            logger.error("run_scraper[%s] raised: %s", source, exc, exc_info=True)
            state.scraper_failures.append({"source": source, "reason": str(exc)})
            return {
                "source": source,
                "listings_collected": 0,
                "failure": True,
                "message": f"Scraper error: {exc}",
            }

        state.raw_listings.extend(listings)
        n = len(listings)
        logger.info("run_scraper[%s] collected %d listings", source, n)

        return {
            "source": source,
            "listings_collected": n,
            "failure": False,
            "message": f"Scraped {n} listings from {source}.",
        }

    async def normalize_listings(listing_ids: list) -> dict:
        import uuid as _uuid

        seen_urls: set[str] = {n.url for n in state.normalized_listings}
        pending_raw: list[RawListing] = []
        for raw in state.raw_listings:
            if raw.url in seen_urls:
                continue
            seen_urls.add(raw.url)
            pending_raw.append(raw)

        if pending_raw:
            await event_emitter(ProgressEvent(
                stage="normalize",
                status="running",
                message=(
                    f"Extracting fields from {len(pending_raw)} listings..."
                    if settings.glm_api_key
                    else f"Extracting deterministic fields from {len(pending_raw)} listings..."
                ),
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            sem = asyncio.Semaphore(5)

            async def _extract(raw: RawListing) -> None:
                async with sem:
                    regex_stations = extract_transport_stations(raw.raw_text)
                    if regex_stations:
                        existing = raw.pre_parsed.get("nearby_transport", [])
                        seen = {s.lower() for s in existing}
                        for name in regex_stations:
                            if name.lower() not in seen:
                                existing.append(name)
                                seen.add(name.lower())
                        raw.pre_parsed["nearby_transport"] = existing

                    if settings.glm_api_key:
                        extracted = await extract_listing_fields(
                            raw.raw_text, raw.source, raw.pre_parsed
                        )
                        merge_extracted(
                            raw.pre_parsed,
                            extracted,
                            prefer_extracted_fields={"gender_restriction"},
                        )

                    apply_deterministic_extraction(raw.pre_parsed, raw.raw_text)

            await asyncio.gather(*[_extract(raw) for raw in pending_raw])

        new_listings: list[NormalizedListing] = []
        added = 0
        for raw in pending_raw:
            p = raw.pre_parsed
            normalized = NormalizedListing(
                id=str(_uuid.uuid4()),
                session_id=state.session_id,
                source_primary=raw.source,
                url=raw.url,
                title=p.get("title", ""),
                price_rm=p.get("price_rm"),
                deposit_rm=p.get("deposit_rm"),
                location_raw=p.get("location_raw", ""),
                location_area=p.get("location_area", p.get("location_city", "unknown")),
                location_city=p.get("location_city", "unknown"),
                lat=p.get("lat"),
                lng=p.get("lng"),
                room_type=p.get("room_type", "unknown"),
                furnished_status=p.get("furnished_status", "unknown"),
                parking=p.get("parking", "unknown"),
                pet_friendly=p.get("pet_friendly", "unknown"),
                gender_restriction=p.get("gender_restriction", "unknown"),
                facilities=p.get("facilities", []),
                contact_phone=p.get("contact_phone"),
                contact_telegram=p.get("contact_telegram"),
                contact_email=p.get("contact_email"),
                source_language=p.get("source_language", "unknown"),
                posted_date=p.get("posted_date"),
                description_original=p.get("description_original", ""),
                description_en=p.get("description_en", p.get("description_original", "")),
                images=p.get("images", []),
                low_confidence_flags=p.get("low_confidence_flags", []),
                nearby_transport=p.get("nearby_transport", []),
                transport_stops=p.get("transport_stops", []),
                needs_verification=p.get("needs_verification", []),
            )
            state.normalized_listings.append(normalized)
            new_listings.append(normalized)
            added += 1

        duplicates = len(state.raw_listings) - added

        enriched = 0
        if settings.google_maps_api_key and new_listings:
            await event_emitter(ProgressEvent(
                stage="normalize",
                status="running",
                message="Fetching Google Places ratings and reviews...",
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            sem = asyncio.Semaphore(5)

            async def _enrich(listing: NormalizedListing) -> None:
                nonlocal enriched
                async with sem:
                    result = await enrich_listing_with_google_place(
                        settings.google_maps_api_key, listing
                    )
                    if result:
                        apply_google_place_enrichment(listing, result)
                        enriched += 1

            await asyncio.gather(*[_enrich(listing) for listing in new_listings])

        # Persist to DB immediately so listings survive a server restart
        from db.helpers import upsert_listings
        upsert_listings(state)

        return {
            "normalized": added,
            "duplicates_removed": duplicates,
            "google_places_enriched": enriched,
            "message": (
                f"Normalized {added} listings ({duplicates} duplicates removed). "
                f"Google Places enriched {enriched} listings."
            ),
        }

    async def score_listings() -> dict:
        filters = state.filters
        if not filters:
            return {"scored": 0, "avg_score": 0.0, "low_score_count": 0, "message": "No filters."}

        scores: list[float] = []

        for listing in state.normalized_listings:
            breakdown: dict[str, float] = {}

            # 1. Price (30 pts) — proportional within budget
            if listing.price_rm is not None and filters.price_min is not None and filters.price_max is not None:
                lo, hi = filters.price_min, filters.price_max
                p = listing.price_rm
                if lo <= p <= hi:
                    # Score highest near lo, lowest near hi
                    breakdown["price"] = round(30 * (1 - (p - lo) / max(hi - lo, 1)), 1)
                elif p < lo:
                    breakdown["price"] = 20.0  # below budget is fine
                else:
                    # Over budget — partial credit if within 20%
                    over = (p - hi) / max(hi, 1)
                    breakdown["price"] = round(max(0, 10 * (1 - over / 0.2)), 1)
            else:
                breakdown["price"] = 15.0  # unknown price, neutral

            # 2. Room type (15 pts)
            req = (filters.room_type or "any").lower()
            got = (listing.room_type or "unknown").lower()
            if req == "any" or got == "unknown":
                breakdown["room_type"] = 10.0
            elif req == got:
                breakdown["room_type"] = 15.0
            else:
                breakdown["room_type"] = 0.0

            # 3. Location (20 pts) — text match
            loc_needle = (filters.location or "").lower()
            loc_hay = (listing.location_raw + " " + listing.location_city + " " + listing.location_area).lower()
            if loc_needle and loc_needle in loc_hay:
                breakdown["location"] = 20.0
            elif loc_needle:
                # Partial word overlap
                words = [w for w in loc_needle.split() if len(w) > 2]
                matched = sum(1 for w in words if w in loc_hay)
                breakdown["location"] = round(20 * matched / max(len(words), 1), 1)
            else:
                breakdown["location"] = 10.0

            # 4. Contact info (10 pts)
            has_contact = bool(listing.contact_phone or listing.contact_telegram)
            breakdown["contact"] = 10.0 if has_contact else 0.0

            # 5. Images (5 pts)
            breakdown["images"] = 5.0 if listing.images else 0.0

            # 6. Furnished status (10 pts)
            req_f = (filters.furnished_status or "any").lower()
            got_f = (listing.furnished_status or "unknown").lower()
            if req_f == "any" or got_f == "unknown":
                breakdown["furnished"] = 7.0
            elif req_f == got_f:
                breakdown["furnished"] = 10.0
            else:
                breakdown["furnished"] = 2.0

            # 7. Gender restriction (5 pts)
            req_g = (filters.gender_restriction or "any").lower()
            got_g = (listing.gender_restriction or "unknown").lower()
            if req_g == "any" or got_g in ("any", "unknown", "mixed"):
                breakdown["gender"] = 5.0
            elif req_g == got_g:
                breakdown["gender"] = 5.0
            else:
                breakdown["gender"] = 0.0

            # 8. Transport (5 pts) — graded by actual walking time
            req_t = (filters.transport or "").lower()
            if not req_t:
                breakdown["transport"] = 5.0
            else:
                transport_text = " ".join(listing.nearby_transport).lower() + " " + (listing.location_raw or "").lower()
                name_match = any(w in transport_text for w in req_t.split())
                if not name_match:
                    breakdown["transport"] = 0.0
                else:
                    walk_times = [
                        s.get("actual_walk_minutes")
                        for s in (listing.transport_stops or [])
                        if s.get("actual_walk_minutes") is not None
                    ]
                    if not walk_times:
                        breakdown["transport"] = 3.0
                    else:
                        best = min(walk_times)
                        if best <= 10:
                            breakdown["transport"] = 5.0
                        elif best <= 20:
                            breakdown["transport"] = 3.0
                        elif best <= 30:
                            breakdown["transport"] = 1.0
                        else:
                            breakdown["transport"] = 0.0

            total = round(sum(breakdown.values()), 1)
            scores.append(total)

            state.scores[listing.id] = ScoreResult(
                listing_id=listing.id,
                total=total,
                breakdown=breakdown,
                explanation=_score_explanation_fallback(breakdown, total),
            )

        # ── Pass 2 + Explanations: single combined GLM call per chunk ────────
        # Only enrich the top-N listings by base score — lower-ranked ones keep
        # the rule-based fallback explanation and no must_haves bonus.
        ENRICH_TOP_N = 20
        CHUNK_SIZE = 10

        must_haves = (state.filters.must_haves if state.filters else []) or []
        filters_summary = {
            "location": filters.location,
            "price_min": filters.price_min,
            "price_max": filters.price_max,
            "room_type": filters.room_type,
        }

        # Sort by base score descending, take top N
        top_listings = sorted(
            [l for l in state.normalized_listings if l.id in state.scores],
            key=lambda l: state.scores[l.id].total,
            reverse=True,
        )[:ENRICH_TOP_N]

        chunks = [top_listings[i:i+CHUNK_SIZE] for i in range(0, len(top_listings), CHUNK_SIZE)]
        total_enriched = 0

        for chunk in chunks:
            try:
                payload = [
                    {
                        "listing_id": l.id,
                        "title": (l.title or "")[:60],
                        "price_rm": l.price_rm,
                        "location": l.location_area,
                        "room_type": l.room_type,
                        "match_score": round(state.scores[l.id].total, 1),
                        "breakdown": state.scores[l.id].breakdown,
                        "description": (l.description_en or "")[:200],
                        "facilities": l.facilities[:8],  # cap list size
                    }
                    for l in chunk
                ]

                must_haves_instruction = ""
                if must_haves:
                    must_haves_instruction = (
                        f'\nAlso check each listing for these must-have features: {json.dumps(must_haves)}.\n'
                        f'For each must-have return "confirmed", "denied", or "unknown".\n'
                        f'Include a "must_haves" key in each listing result.\n'
                    )

                prompt = (
                    f"User filters: {json.dumps(filters_summary)}\n"
                    f"{must_haves_instruction}\n"
                    f"For each listing:\n"
                    f"  1. Write a 2-3 sentence explanation that opens with the top match reason (use actual price, area name, room type), calls out the biggest mismatch or risk if any, and flags any must-have that could not be confirmed.\n"
                    f"  2. Write a short comment (max 10 words) for each score dimension that was evaluated. Be specific — e.g. 'RM 1,200, within your RM 1,500 budget' or 'Cheras, you wanted Bangsar'.\n"
                    f"  3. If must-haves provided, check each one.\n"
                    f"Avoid generic phrases. Use concrete values from the listing.\n\n"
                    f"Score dimensions present per listing are the keys in their breakdown object.\n\n"
                    f"Listings:\n{json.dumps(payload)}\n\n"
                    f"Return ONLY JSON (no markdown):\n"
                    f'{{"listing_id": {{"explanation": "...", "breakdown_comments": {{"dimension": "short comment"}}, "must_haves": {{"feature": "confirmed|denied|unknown"}}}}}}'
                )

                response = await glm_client.chat(messages=[
                    {"role": "system", "content": "You explain Malaysian rental listings to users searching for a home. Be specific, honest, and concise. Return only valid JSON, no markdown."},
                    {"role": "user", "content": prompt},
                ])
                content = response.choices[0].message.content.strip()
                if content.startswith("```"):
                    lines = content.splitlines()
                    content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

                import re as _re
                if not content.startswith("{"):
                    m = _re.search(r"\{[\s\S]*\}", content)
                    if m:
                        content = m.group()

                results: dict[str, dict] = json.loads(content)

                for listing in chunk:
                    row = results.get(listing.id, {})
                    # Apply explanation
                    if explanation := row.get("explanation"):
                        state.scores[listing.id].explanation = str(explanation)
                    # Apply per-dimension comments
                    if comments := row.get("breakdown_comments"):
                        if isinstance(comments, dict):
                            state.scores[listing.id].breakdown_comments = comments
                    # Apply must_haves bonus
                    if must_haves and (mh_row := row.get("must_haves", {})):
                        bonus = 0.0
                        needs_verify: list[str] = []
                        for req, status in mh_row.items():
                            if status == "confirmed":
                                bonus += 8.0
                            elif status == "denied":
                                bonus -= 10.0
                            else:
                                needs_verify.append(req)
                        listing.needs_verification = needs_verify
                        if bonus != 0:
                            s = state.scores[listing.id]
                            s.breakdown["special_requirements"] = round(bonus, 1)
                            s.total = round(max(0.0, min(100.0, s.total + bonus)), 1)

                total_enriched += len(results)
            except Exception as exc:
                logger.warning("GLM enrich chunk failed (%s), keeping fallbacks", exc)

        logger.info("GLM enriched %d/%d listings (top-%d)", total_enriched, len(state.normalized_listings), ENRICH_TOP_N)

        # Persist scores to DB immediately
        from db.helpers import update_listing_scores
        update_listing_scores(state)

        final_scores = [score.total for score in state.scores.values()]
        final_avg = round(sum(final_scores) / len(final_scores), 1) if final_scores else 0.0
        final_low_count = sum(1 for score in final_scores if score < 35)

        return {
            "scored": len(final_scores),
            "avg_score": final_avg,
            "low_score_count": final_low_count,
            "message": f"Scored {len(final_scores)} listings. Avg score: {final_avg}/100. {final_low_count} below threshold.",
        }

    async def generate_report() -> dict:
        count = len(state.normalized_listings)
        filters = state.filters
        location = filters.location if filters else "unknown"
        prices = [l.price_rm for l in state.normalized_listings if l.price_rm]
        avg_price = int(sum(prices) / len(prices)) if prices else None
        top_scores = sorted(state.scores.values(), key=lambda s: s.total, reverse=True)[:3]

        # Fallback template in case GLM fails
        fallback_parts = [f"Found {count} rental listings in {location}."]
        if avg_price:
            fallback_parts.append(f"Average price: RM {avg_price}/month.")
        if top_scores:
            fallback_parts.append(f"Top match score: {top_scores[0].total}/100.")
        fallback_report = " ".join(fallback_parts)

        try:
            stats = {
                "total_listings": count,
                "location": location,
                "avg_price_rm": avg_price,
                "top_match_scores": [round(s.total, 1) for s in top_scores],
                "price_range_rm": {"min": filters.price_min, "max": filters.price_max} if filters else None,
                "room_type_requested": filters.room_type if filters else None,
                "sources": list({l.source_primary for l in state.normalized_listings}),
            }
            response = await glm_client.chat(messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate concise, informative summary reports for a Malaysian rental search app. "
                        "Write 2-4 sentences in plain English. Mention total listings found, location, average price "
                        "if available, and one notable observation (e.g. which area has the best matches, "
                        "or whether prices are within the budget). Do not invent data not provided."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Generate a summary report for this rental search:\n{json.dumps(stats)}",
                },
            ])
            state.summary_report = response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("GLM report generation failed (%s), using template", exc)
            state.summary_report = fallback_report

        return {"report": state.summary_report, "message": "Report generated."}

    async def prepare_outreach(listing_ids: list) -> dict:
        # Outreach drafting is on-demand via POST /api/outreach/draft when the user selects a listing.
        contactable = sum(
            1 for l in state.normalized_listings
            if l.id in listing_ids and (l.contact_telegram or l.contact_phone)
        )
        return {
            "drafts_prepared": 0,
            "contactable_listings": contactable,
            "message": f"{contactable} listings have contact info. Use the dashboard to prepare inquiry messages.",
        }

    async def ask_user(question: str, context: str) -> dict:
        # Phase 1 stub — auto-answer with empty string, real pause logic in Phase 2.
        state.clarification_queue.append({"question": question, "context": context})
        await event_emitter(ProgressEvent(
            stage="orchestrator",
            status="running",
            message=f"GLM asks: {question}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        return {
            "answered": False,
            "answer": "",
            "message": "Clarification queued (Phase 2 will implement user pause/resume).",
        }

    async def verify_transport_claims(listing_ids: list) -> dict:
        if not settings.google_maps_api_key:
            return {"verified": 0, "flagged": 0, "message": "Skipped — no Google Maps API key configured."}

        id_set = set(listing_ids)
        targets = [l for l in state.normalized_listings if l.id in id_set]
        verified_count = 0
        flagged_count = 0

        for listing in targets:
            if not listing.lat or not listing.lng or not listing.transport_stops:
                continue

            desc_text = listing.description_en or listing.description_original or ""
            claims = extract_transport_claims(desc_text)
            claim_lookup = {c["station_name"].lower(): c for c in claims}

            def _match_claim(stop_name: str) -> dict | None:
                sl = stop_name.lower()
                for key, claim in claim_lookup.items():
                    if key in sl or sl in key:
                        return claim
                return None

            for stop in listing.transport_stops:
                if not stop.get("lat") or not stop.get("lng"):
                    continue

                claim = _match_claim(stop["name"])
                if claim:
                    stop["claimed_walk_minutes"] = claim["claimed_minutes"]
                    stop["claimed_text"] = claim["claimed_text"]

                actual = await get_walking_minutes(
                    settings.google_maps_api_key,
                    listing.lat, listing.lng,
                    stop["lat"], stop["lng"],
                )
                if actual is not None:
                    stop["actual_walk_minutes"] = actual
                    claimed = stop.get("claimed_walk_minutes")
                    stop["walk_verified"] = (claimed is None) or (actual <= claimed * 1.5)

                    if claimed and actual > claimed * 1.5:
                        listing.low_confidence_flags.append(
                            f"Claims {claimed}min walk to {stop['name']}, estimated ~{actual}min"
                        )
                        flagged_count += 1

                    verified_count += 1

            await event_emitter(ProgressEvent(
                stage="verify",
                status="running",
                message=f"Verified transport claims for: {listing.title[:50]}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

        from db.helpers import upsert_listings
        upsert_listings(state)

        return {
            "verified": verified_count,
            "flagged": flagged_count,
            "message": (
                f"Verified {verified_count} transport stops across {len(targets)} listings. "
                f"{flagged_count} inaccurate claim(s) flagged."
            ),
        }

    async def relax_filters(suggestions: list) -> dict:
        state.filter_relaxation_suggestions = suggestions
        await event_emitter(ProgressEvent(
            stage="orchestrator",
            status="running",
            message=f"GLM suggests: {'; '.join(suggestions)}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        return {
            "accepted": False,
            "suggestions": suggestions,
            "message": "Filter relaxation suggestions surfaced to user.",
        }

    async def finish(summary: str) -> dict:
        state.pipeline_status = "complete"
        if not state.summary_report:
            state.summary_report = summary
        return {"status": "complete", "message": summary}

    return {
        "validate_filters": validate_filters,
        "run_scraper": run_scraper,
        "normalize_listings": normalize_listings,
        "score_listings": score_listings,
        "generate_report": generate_report,
        "prepare_outreach": prepare_outreach,
        "ask_user": ask_user,
        "verify_transport_claims": verify_transport_claims,
        "relax_filters": relax_filters,
        "finish": finish,
    }
