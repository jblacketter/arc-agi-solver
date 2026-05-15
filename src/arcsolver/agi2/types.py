"""Core dataclasses for ARC-AGI-2 tasks, predictions, and results.

These are intentionally local and minimal — we don't reuse the `arc-agi` SDK's
`Task`/`Grid` types because that SDK targets ARC-AGI-3 (interactive envs),
and its shapes don't fit the grid-transduction task model used here.

A `Grid` is a row-major 2D list of ints (color indices 0-9). Each ARC-AGI-2
task has a few training `Pair`s and one or more test inputs; the agent must
predict an output `Grid` for each test input (up to 2 attempts per test input
per Kaggle scoring rules).
"""

from __future__ import annotations

from dataclasses import dataclass, field

Grid = list[list[int]]


@dataclass(frozen=True)
class Pair:
    """A single (input, output) example from a task's `train` block, or a
    test pair whose `output` is held out as ground truth for scoring."""

    input: Grid
    output: Grid


@dataclass(frozen=True)
class Task:
    """An ARC-AGI-2 task: a few training pairs and one or more test pairs."""

    task_id: str
    train: list[Pair]
    test: list[Pair]


@dataclass(frozen=True)
class Attempt:
    """One agent attempt at a single test input.

    `grid` is None when the agent's raw response failed to parse; in that
    case `parse_error` carries a short description for the result report.
    """

    grid: Grid | None
    parse_error: str | None = None


@dataclass(frozen=True)
class TestInputResult:
    """Per-test-input scoring result: up to 2 attempts and whether either matched."""

    expected: Grid
    attempts: list[Attempt]
    solved: bool


@dataclass(frozen=True)
class TaskResult:
    """Per-task scoring result: all test inputs solved => task solved."""

    task_id: str
    test_results: list[TestInputResult]
    solved: bool


@dataclass
class AggregateResult:
    """Aggregate scoring across a set of tasks."""

    tasks_total: int
    tasks_solved: int
    test_inputs_total: int
    test_inputs_solved: int
    per_task: list[TaskResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_solved / self.tasks_total
