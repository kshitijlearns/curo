"""LLMProvider: every language task in the catalog (MVP doc §10).

``run(task, input)`` validates the input against the task's schema, calls the model, and
validates the output against the task's output schema, so callers always get a typed,
schema-valid result whichever provider is behind it. ``version(task)`` is stored with every
output ("T2.v1:claude-haiku-…") so results can be traced and re-run.

``chat(input)`` is Ask Curo (T14): one turn of a conversation with tools, streamed as chunks
of text or tool calls. The assistant loop (services/assistant) runs the tools and calls it
again with their results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from curo.config import REPO_ROOT, get_settings
from curo.schemas.tasks import T14, ChatChunk, T14Input, TaskSpec

CAPTURE_PER_TASK = 5


class LLMError(Exception):
    pass


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def model_for(self, task: TaskSpec) -> str: ...

    @abstractmethod
    def _call(self, task: TaskSpec, data: BaseModel) -> dict[str, Any] | BaseModel: ...

    def run(self, task: TaskSpec, data: BaseModel | dict[str, Any]) -> Any:
        if not isinstance(data, task.input):
            data = task.input.model_validate(data)
        capture(task, data)
        out = self._call(task, data)
        if isinstance(out, BaseModel):
            out = out.model_dump()
        result = task.output.model_validate(out)
        from curo import usage  # the usage ledger: cost per creator and feature (PLAN_V2 §4.6)

        usage.record(
            self.name,
            self.model_for(task),
            task.id,
            usage.tokens(data.model_dump_json()),
            usage.tokens(result.model_dump_json()),
        )
        return result

    @abstractmethod
    def _chat(self, data: T14Input) -> Iterator[ChatChunk | dict[str, Any]]: ...

    def chat(self, data: T14Input | dict[str, Any]) -> Iterator[ChatChunk]:
        """One streamed turn of Ask Curo: text chunks, or tool calls (the turn then ends)."""
        if not isinstance(data, T14Input):
            data = T14Input.model_validate(data)
        capture(T14, data)
        for chunk in self._chat(data):
            yield chunk if isinstance(chunk, ChatChunk) else ChatChunk.model_validate(chunk)

    def chat_version(self) -> str:
        return self.version(T14)

    def run_batch(self, task: TaskSpec, items: list[BaseModel]) -> list[Any]:
        """Many independent calls (Claude's Message Batches API for nightly labelling)."""
        return [self.run(task, item) for item in items]

    def version(self, task: TaskSpec) -> str:
        return f"{task.tag}:{self.model_for(task)}"


def capture(task: TaskSpec, data: BaseModel) -> None:
    """Keep the first few inputs of each task when CAPTURE_TASK_INPUTS names a folder: real
    inputs for recording the real model's answers (tools/record_contracts.py claude)."""
    root = get_settings().capture_task_inputs
    if not root:
        return
    folder = (Path(root) if Path(root).is_absolute() else REPO_ROOT / root) / task.id
    folder.mkdir(parents=True, exist_ok=True)
    n = len(list(folder.glob("*.json")))
    if n < CAPTURE_PER_TASK:
        (folder / f"{n + 1}.json").write_text(data.model_dump_json(indent=2), encoding="utf-8")
