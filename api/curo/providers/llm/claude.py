"""Claude implementation of LLMProvider — NOT IMPLEMENTED YET (needs ANTHROPIC_API_KEY).

The calls are stubs; the parsers below are real. They read the Messages API's response
format (documented and stable), so the contract tests can check recorded responses now
(tests/test_contracts.py, tools/record_contracts.py) and the implementation reuses them.

TODO when the key arrives (see docs/INTEGRATION.md):
1. The official SDK: ``pip install -e "api[live]"`` (anthropic 1.x). ``anthropic.Anthropic(
   api_key=ANTHROPIC_API_KEY)``. Model by tier: "main" → CLAUDE_MODEL_MAIN
   (claude-sonnet-5-5), "fast" → CLAUDE_MODEL_FAST.
2. Structured output: ``client.messages.parse(model=…, max_tokens=16000, system=
   curo.prompts.load(task), messages=[{"role": "user", "content": data.model_dump_json()}],
   output_format=task.output)``. Read it with ``parse_message(task, response.to_dict())``
   (or ``response.parsed_output``). NOT forced tool use: claude-sonnet-5-5 answers
   ``tool_choice`` "tool"/"any" with a 400. No ``temperature``/``top_p`` (the 1.x SDK
   removed them; Sonnet 5.5 rejects non-default values).
3. Effort: ``output_config={"effort": …}``: start at "medium" for the Studio's writing
   tasks and "low" for T2/T3/T4/T8/T13 labelling, then tune against recorded outputs.
4. Refusals: ``stop_reason == "refusal"`` → LLMError (parse_message raises it); every caller
   already falls back to its template. Consider the server-side fallbacks beta for Sonnet
   (``fallbacks="default"`` with ``betas=["server-side-fallback-2026-07-01"]`` on
   ``client.beta.messages``).
5. Retry once on a validation error with the error appended, then raise LLMError.
6. Prompt caching: ``cache_control`` on the system prompt and on the creator's evidence pack
   (Studio tasks), so repeated calls in one session are cheap. Check
   ``usage.cache_read_input_tokens``.
7. run_batch → Message Batches API for the nightly T3 labelling and the Simulator's T19 batches
   (``client.messages.batches``); results arrive in any order: key them by custom_id.
8. _chat (T14, Ask Curo): ``client.messages.stream(…, tools=to_claude_tools(data),
   system=chat_system(data), messages=to_claude_messages(data))`` with tool_choice auto;
   yield ChatChunk(type="text") per text delta and ChatChunk(type="tool_call") per finished
   tool_use block (``parse_chat_message`` reads a whole message the same way). The loop sends
   tool results back, so mind preserved thinking: either replay each assistant turn's content
   blocks exactly as returned (keep them on the ChatTurn), or send
   ``thinking={"type": "between_tools"}`` (Sonnet 5.5, effort "high" or lower).
9. Record real responses with tools/record_contracts.py; tests/test_contracts.py replays them.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from curo.schemas.tasks import ChatChunk, T14Input, TaskSpec, ToolCall

from .base import LLMError, LLMProvider

_TODO = "Claude provider not implemented yet: set LLM_PROVIDER=mock (see INTEGRATION.md)"


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model_main: str, model_fast: str, model_agents: str = ""):
        self.api_key = api_key
        self.models = {
            "main": model_main,
            "fast": model_fast,
            "agents": model_agents or model_fast,
        }

    def model_for(self, task: TaskSpec) -> str:
        return self.models.get(task.tier, self.models["main"])

    def _call(self, task, data):
        raise NotImplementedError(_TODO)

    def _chat(self, data):
        raise NotImplementedError(_TODO)


# ---------------------------------------------------------------- reading Claude's answers


def _check_stop(raw: dict[str, Any]) -> None:
    stop = raw.get("stop_reason")
    if stop == "refusal":
        category = (raw.get("stop_details") or {}).get("category")
        raise LLMError(f"Claude declined the request ({category or 'no category'})")
    if stop == "max_tokens":
        raise LLMError("Claude's answer was cut off at max_tokens")


def parse_message(task: TaskSpec, raw: dict[str, Any]) -> BaseModel:
    """A structured-output response (``output_config.format`` / ``messages.parse``): its
    text block is the task's output as JSON."""
    _check_stop(raw)
    text = next((b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text"), "")
    try:
        return task.output.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMError(f"{task.tag} answer doesn't match its schema: {exc}") from exc


def parse_chat_message(raw: dict[str, Any]) -> list[ChatChunk]:
    """One Ask Curo turn: its words and the tools it asks for, in order. Thinking blocks are
    the model's own and aren't shown."""
    _check_stop(raw)
    out: list[ChatChunk] = []
    for block in raw.get("content", []):
        if block.get("type") == "text" and block.get("text"):
            out.append(ChatChunk(type="text", text=block["text"]))
        elif block.get("type") == "tool_use":
            call = ToolCall(id=block["id"], name=block["name"], args=block.get("input") or {})
            out.append(ChatChunk(type="tool_call", call=call))
    return out


# ---------------------------------------------------------------- writing Ask Curo's request


def chat_system(data: T14Input, prompt: str) -> str:
    system = f"{prompt}\n\nScreen context (JSON):\n{data.context.model_dump_json()}"
    if data.retry_note:
        system += f"\n\nYour last reply was held back: {data.retry_note}"
    return system


def to_claude_tools(data: T14Input) -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in data.tools
    ]


def to_claude_messages(data: T14Input) -> list[dict[str, Any]]:
    """CURO's turns in the Messages API's shape. A tool's results answer in one user message
    (several results from one turn go together, as the API expects)."""
    out: list[dict[str, Any]] = []
    for turn in data.messages:
        if turn.role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": turn.tool_call_id,
                "content": turn.content,
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        elif turn.role == "assistant":
            blocks: list[dict[str, Any]] = (
                [{"type": "text", "text": turn.content}] if turn.content else []
            )
            blocks += [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.args}
                for c in turn.tool_calls
            ]
            out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": "user", "content": turn.content})
    return out
