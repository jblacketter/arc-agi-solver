"""Agent protocol and shared types for ARC-AGI-2 solvers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from arcsolver.agi2.types import Attempt, Task


@dataclass(frozen=True)
class CallUsage:
    """Token usage from a single Anthropic API call.

    Mirrors the four billing buckets Anthropic returns. All fields default
    to 0 so the SDK omitting an optional field doesn't break the sum.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class AgentTaskRun:
    """What an agent produced for one task: attempts plus the raw call records."""

    task_id: str
    attempts_per_test: list[list[Attempt]]
    calls: list[CallUsage] = field(default_factory=list)


class Agent(Protocol):
    """An ARC-AGI-2 agent.

    `solve(task)` returns `AgentTaskRun` with one inner list per test input,
    each holding up to 2 attempts (extras are scored-out by the scoring module).
    """

    name: str
    model: str

    def solve(self, task: Task) -> AgentTaskRun: ...


def grid_to_text(grid: Sequence[Sequence[int]]) -> str:
    """Render a grid as a compact JSON-style 2D array string."""
    return "[" + ", ".join("[" + ", ".join(str(c) for c in row) + "]" for row in grid) + "]"
