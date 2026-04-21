from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

from glm import client as glm_client

logger = logging.getLogger(__name__)


class AgentMaxIterationsError(Exception):
    pass


async def run_glm_agent(
    system_prompt: str,
    user_message: str,
    tools: list[dict],
    tools_map: dict[str, Callable[..., Awaitable[Any]]],
    max_iterations: int = 10,
) -> str:
    """ReAct loop: Reason → Act (tool call) → Observe (result) → Repeat → Final answer.

    Args:
        system_prompt: Stage-specific system instructions for GLM.
        user_message:  The task description sent as the first user turn.
        tools:         OpenAI-format tool definitions passed to GLM.
        tools_map:     Dict mapping tool name → async callable implementation.
        max_iterations: Hard cap on loop iterations before raising.

    Returns:
        The final text content from GLM once it stops calling tools.
    """
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(max_iterations):
        logger.debug("GLM agent iteration %d/%d", iteration + 1, max_iterations)

        response = await glm_client.chat(
            messages=messages,
            tools=tools or None,
        )
        choice = response.choices[0]
        message = choice.message

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            # Append assistant turn with tool_calls
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            # Execute each tool call and append results
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    logger.warning("Malformed tool arguments for %s, using empty dict", tool_name)
                    args = {}

                if tool_name in tools_map:
                    try:
                        result = await tools_map[tool_name](**args)
                    except Exception as exc:
                        logger.error("Tool %s raised: %s", tool_name, exc)
                        result = {"error": str(exc)}
                else:
                    logger.warning("Unknown tool requested: %s", tool_name)
                    result = {"error": f"Unknown tool: {tool_name}"}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

        else:
            # GLM returned a final answer — exit the loop
            return message.content or ""

    raise AgentMaxIterationsError(
        f"GLM agent did not reach a final answer within {max_iterations} iterations."
    )
