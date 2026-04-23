from __future__ import annotations

import dataclasses
import importlib
import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Callable, Awaitable

from config import settings
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
                        "enum": ["ibilik", "iproperty", "facebook"],
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


# ── Tool implementations (Phase 1 stubs) ─────────────────────────────────────

def _score_explanation(breakdown: dict, total: float, listing: NormalizedListing, filters: FilterObject) -> str:
    parts = []
    if breakdown.get("price", 0) >= 25:
        parts.append("great price")
    elif breakdown.get("price", 0) < 5:
        parts.append("over budget")
    if breakdown.get("room_type", 0) == 15:
        parts.append(f"matches {filters.room_type} room type")
    elif breakdown.get("room_type", 0) == 0:
        parts.append("room type mismatch")
    if breakdown.get("location", 0) >= 18:
        parts.append("in target area")
    elif breakdown.get("location", 0) < 5:
        parts.append("outside target area")
    if breakdown.get("contact", 0) == 10:
        parts.append("contact info available")
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

        # ── Facebook: not implemented ─────────────────────────────────────────
        if source == "facebook":
            state.scraper_failures.append({
                "source": "facebook",
                "reason": "Facebook scraper not implemented",
            })
            return {
                "source": "facebook",
                "listings_collected": 0,
                "failure": False,
                "message": "Facebook scraper is not implemented. Skipping.",
            }

        # ── Live scraping dispatch ────────────────────────────────────────────
        scraper_map = {
            "ibilik": ("scrapers.ibilik", "IbilikScraper"),
            "iproperty": ("scrapers.iproperty", "IPropertyScraper"),
        }
        if source not in scraper_map:
            state.scraper_failures.append({"source": source, "reason": f"unknown source '{source}'"})
            return {
                "source": source,
                "listings_collected": 0,
                "failure": True,
                "message": f"Unknown scraper source: {source}",
            }

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
        added = 0
        for raw in state.raw_listings:
            if raw.url in seen_urls:
                continue
            seen_urls.add(raw.url)
            p = raw.pre_parsed
            state.normalized_listings.append(NormalizedListing(
                id=str(_uuid.uuid4()),
                session_id=state.session_id,
                source_primary=raw.source,
                url=raw.url,
                title=p.get("title", ""),
                price_rm=p.get("price_rm"),
                location_raw=p.get("location_raw", ""),
                location_area=p.get("location_area", p.get("location_city", "unknown")),
                location_city=p.get("location_city", "unknown"),
                lat=p.get("lat"),
                lng=p.get("lng"),
                room_type=p.get("room_type", "unknown"),
                contact_phone=p.get("contact_phone"),
                contact_telegram=p.get("contact_telegram"),
                description_original=p.get("description_original", ""),
                description_en=p.get("description_original", ""),
                images=p.get("images", []),
            ))
            added += 1

        duplicates = len(state.raw_listings) - added
        return {
            "normalized": added,
            "duplicates_removed": duplicates,
            "message": f"Normalized {added} listings ({duplicates} duplicates removed).",
        }

    async def score_listings() -> dict:
        filters = state.filters
        if not filters:
            return {"scored": 0, "avg_score": 0.0, "low_score_count": 0, "message": "No filters."}

        scores: list[float] = []
        low_count = 0

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

            # 8. Transport (5 pts)
            req_t = (filters.transport or "").lower()
            if not req_t:
                breakdown["transport"] = 5.0
            else:
                transport_text = " ".join(listing.nearby_transport).lower() + " " + (listing.location_raw or "").lower()
                breakdown["transport"] = 5.0 if any(w in transport_text for w in req_t.split()) else 0.0

            total = round(sum(breakdown.values()), 1)
            scores.append(total)
            if total < 35:
                low_count += 1

            state.scores[listing.id] = ScoreResult(
                listing_id=listing.id,
                total=total,
                breakdown=breakdown,
                explanation=_score_explanation(breakdown, total, listing, filters),
            )

        avg = round(sum(scores) / len(scores), 1) if scores else 0.0
        return {
            "scored": len(scores),
            "avg_score": avg,
            "low_score_count": low_count,
            "message": f"Scored {len(scores)} listings. Avg score: {avg}/100. {low_count} below threshold.",
        }

    async def generate_report() -> dict:
        count = len(state.normalized_listings)
        filters = state.filters
        location = filters.location if filters else "unknown"
        avg_price = None
        if state.normalized_listings:
            prices = [l.price_rm for l in state.normalized_listings if l.price_rm]
            if prices:
                avg_price = int(sum(prices) / len(prices))

        parts = [f"Found {count} rental listings in {location}."]
        if avg_price:
            parts.append(f"Average price: RM {avg_price}/month.")
        if state.scores:
            top = sorted(state.scores.values(), key=lambda s: s.total, reverse=True)[:3]
            parts.append(f"Top match score: {top[0].total}/100." if top else "")

        state.summary_report = " ".join(filter(None, parts))
        return {
            "report": state.summary_report,
            "message": "Report generated.",
        }

    async def prepare_outreach(listing_ids: list) -> dict:
        # Phase 1 stub.
        return {
            "drafts_prepared": 0,
            "message": "Outreach drafting stub (Phase 3 will implement GLM message drafting).",
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
        "relax_filters": relax_filters,
        "finish": finish,
    }
