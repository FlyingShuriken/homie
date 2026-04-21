from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

from workflow.state import FilterObject, ProgressEvent, SessionState

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
        # Phase 1 stub — no live scraping yet (Phase 2).
        logger.info("run_scraper stub: source=%s max_results=%d", source, max_results)
        state.scraper_failures.append({
            "source": source,
            "reason": "stub — live scraping not yet implemented (Phase 2)",
        })
        return {
            "source": source,
            "listings_collected": 0,
            "failure": False,
            "message": f"Scraper stub for {source}: 0 listings returned (Phase 2 will implement live scraping).",
        }

    async def normalize_listings(listing_ids: list) -> dict:
        # Phase 1 stub.
        count = len(state.raw_listings)
        return {
            "normalized": 0,
            "duplicates_removed": 0,
            "message": f"Normalize stub: {count} raw listings pending (Phase 2 will implement GLM extraction).",
        }

    async def score_listings() -> dict:
        # Phase 1 stub.
        count = len(state.normalized_listings)
        return {
            "scored": count,
            "avg_score": 0.0,
            "low_score_count": 0,
            "message": f"Score stub: {count} listings scored (Phase 2 will implement 8-dimension scoring).",
        }

    async def generate_report() -> dict:
        count = len(state.normalized_listings)
        filters = state.filters
        location = filters.location if filters else "unknown"
        state.summary_report = (
            f"Search complete for {location}. "
            f"Found {count} listings. "
            "Full AI-generated analysis will be available once live scrapers are active."
        )
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
