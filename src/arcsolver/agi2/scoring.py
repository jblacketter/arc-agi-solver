"""Pure scoring functions for ARC-AGI-2 predictions.

Scoring rule (matches the Kaggle ARC-AGI competition):
- Each test input gets up to 2 attempts.
- A test input is solved if any attempt matches the expected grid exactly.
- A task is solved iff ALL of its test inputs are solved.
"""

from __future__ import annotations

from collections.abc import Sequence

from arcsolver.agi2.types import (
    AggregateResult,
    Attempt,
    Grid,
    Task,
    TaskResult,
    TestInputResult,
)

MAX_ATTEMPTS_PER_TEST_INPUT = 2


def grids_equal(a: Grid | None, b: Grid | None) -> bool:
    """Exact-match grid comparison. None never matches anything."""
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    return all(row_a == row_b for row_a, row_b in zip(a, b, strict=True))


def score_task(task: Task, attempts_per_test: Sequence[Sequence[Attempt]]) -> TaskResult:
    """Score a single task.

    `attempts_per_test[i]` holds up to `MAX_ATTEMPTS_PER_TEST_INPUT` attempts
    for `task.test[i]`. Extra attempts past the cap are ignored (not scored).
    """
    if len(attempts_per_test) != len(task.test):
        raise ValueError(
            f"task {task.task_id}: expected attempts for {len(task.test)} test "
            f"inputs, got {len(attempts_per_test)}"
        )

    test_results: list[TestInputResult] = []
    for test_pair, attempts in zip(task.test, attempts_per_test, strict=True):
        capped = list(attempts[:MAX_ATTEMPTS_PER_TEST_INPUT])
        solved = any(grids_equal(a.grid, test_pair.output) for a in capped)
        test_results.append(
            TestInputResult(expected=test_pair.output, attempts=capped, solved=solved)
        )

    task_solved = all(r.solved for r in test_results)
    return TaskResult(task_id=task.task_id, test_results=test_results, solved=task_solved)


def aggregate(results: Sequence[TaskResult]) -> AggregateResult:
    """Aggregate per-task results into a single summary."""
    tasks_total = len(results)
    tasks_solved = sum(1 for r in results if r.solved)
    test_inputs_total = sum(len(r.test_results) for r in results)
    test_inputs_solved = sum(1 for r in results for t in r.test_results if t.solved)
    return AggregateResult(
        tasks_total=tasks_total,
        tasks_solved=tasks_solved,
        test_inputs_total=test_inputs_total,
        test_inputs_solved=test_inputs_solved,
        per_task=list(results),
    )
