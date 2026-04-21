from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

from glm import client as glm_client
from workflow.state import ProgressEvent, SessionState

logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM_PROMPT = """You are the orchestration agent for Homie, an AI-powered rental search system for Malaysia.

Your role is to drive a complete rental search workflow by calling tools in the right sequence, evaluating intermediate results, and adapting your decisions based on what you observe. You decide what to do at every step — the pipeline shape is not fixed.

WORKFLOW TOOLS AVAILABLE:
- validate_filters: Parse and resolve the user's raw filter inputs. Always call this first.
- run_scraper: Scrape a rental platform. Sources: "ibilik", "iproperty", "facebook".
- normalize_listings: Extract, translate, and deduplicate the raw listings collected so far.
- score_listings: Score all normalized listings against the user's filters. Returns aggregate stats.
- generate_report: Generate a plain-language summary of the search findings.
- prepare_outreach: Draft inquiry messages for listings with contact info.
- ask_user: Pause the workflow and ask the user a clarifying question.
- relax_filters: Suggest filter relaxation to the user if results are poor.
- finish: Mark the workflow complete. Always call this last.

DECISION GUIDELINES:
1. Call validate_filters first with the raw user input.
2. Decide which scrapers to run based on the filter context:
   - Room searches (single/master, budget under RM 1200): prioritise ibilik, also try iproperty.
   - Unit/studio searches: try both iproperty and ibilik.
   - If filters are unspecific: run both ibilik and iproperty.
3. After scraping, call normalize_listings.
4. After normalization, call score_listings.
5. If avg_score is below 35 and low_score_count is high, call relax_filters with specific suggestions before finishing.
6. Call generate_report, then finish.

IMPORTANT: If scrapers return 0 results (this can happen in stub/demo mode), proceed to normalize and score anyway — do not retry indefinitely. Always call finish to complete the session."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestratorMaxIterationsError(Exception):
    pass


async def run_orchestrator(
    session_state: SessionState,
    event_emitter: Callable[[ProgressEvent], Awaitable[None]],
    max_iterations: int = 30,
) -> SessionState:
    """Top-level GLM ReAct loop that drives the entire rental search workflow.

    GLM receives the current SessionState and a set of stage-level tools, reasons
    about what to do next, and emits tool calls until it calls finish().
    """
    from glm.tools.orchestrator_tools import TOOL_DEFINITIONS, build_tools_map

    tools_map = build_tools_map(session_state, event_emitter)

    await event_emitter(ProgressEvent(
        stage="orchestrator",
        status="started",
        message="GLM orchestrator started — reasoning over search workflow.",
        timestamp=_now(),
    ))

    user_message = (
        f"New rental search session started.\n\n"
        f"Session ID: {session_state.session_id}\n"
        f"User's raw filter input:\n{json.dumps(session_state.raw_filters, indent=2)}\n\n"
        f"Begin the workflow by calling validate_filters with the raw input above."
    )

    messages: list[dict] = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(max_iterations):
        logger.debug("Orchestrator iteration %d/%d", iteration + 1, max_iterations)

        response = await glm_client.chat(messages=messages, tools=TOOL_DEFINITIONS)
        choice = response.choices[0]
        message = choice.message

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    logger.warning("Malformed tool args for %s, using empty dict", tool_name)
                    args = {}

                await event_emitter(ProgressEvent(
                    stage="orchestrator",
                    status="running",
                    message=f"GLM → {tool_name}",
                    timestamp=_now(),
                ))

                if tool_name in tools_map:
                    try:
                        result = await tools_map[tool_name](**args)
                    except Exception as exc:
                        logger.error("Orchestrator tool %s raised: %s", tool_name, exc)
                        result = {"error": str(exc)}
                else:
                    logger.warning("Unknown orchestrator tool: %s", tool_name)
                    result = {"error": f"Unknown tool: {tool_name}"}

                session_state.orchestrator_tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                    "timestamp": _now(),
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

                if tool_name == "finish":
                    await event_emitter(ProgressEvent(
                        stage="orchestrator",
                        status="complete",
                        message="Workflow complete.",
                        timestamp=_now(),
                    ))
                    return session_state

        else:
            # GLM returned text without a tool call — treat as unexpected finish
            logger.warning("Orchestrator received text response without tool call: %s", message.content)
            session_state.pipeline_status = "complete"
            await event_emitter(ProgressEvent(
                stage="orchestrator",
                status="complete",
                message="Workflow complete.",
                timestamp=_now(),
            ))
            return session_state

    raise OrchestratorMaxIterationsError(
        f"Orchestrator exceeded {max_iterations} iterations without calling finish."
    )
