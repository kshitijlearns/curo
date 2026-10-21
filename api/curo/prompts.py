"""Versioned prompt files for the AI tasks (``api/prompts/<ID>_<name>.v<version>.md``).

Real providers send these; mocks don't need them, but every task must have one (tested), so
switching a provider on never finds a missing prompt.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from curo.schemas.tasks import TaskSpec

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@cache
def load(spec: TaskSpec) -> str:
    path = PROMPTS_DIR / spec.prompt_file
    if not path.exists():
        raise FileNotFoundError(f"missing prompt for {spec.tag}: {path}")
    return path.read_text(encoding="utf-8")
