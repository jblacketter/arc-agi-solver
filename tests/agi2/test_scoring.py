"""Tests for arcsolver.agi2.scoring."""

from __future__ import annotations

import pytest

from arcsolver.agi2.scoring import (
    MAX_ATTEMPTS_PER_TEST_INPUT,
    aggregate,
    grids_equal,
    score_task,
)
from arcsolver.agi2.types import Attempt, Pair, Task


def _task(task_id: str, test_outputs: list[list[list[int]]]) -> Task:
    return Task(
        task_id=task_id,
        train=[Pair(input=[[0]], output=[[0]])],
        test=[Pair(input=[[0]], output=out) for out in test_outputs],
    )


def test_grids_equal_exact() -> None:
    assert grids_equal([[1, 2], [3, 4]], [[1, 2], [3, 4]])
    assert not grids_equal([[1, 2]], [[1, 2], [3, 4]])
    assert not grids_equal([[1]], [[2]])
    assert not grids_equal(None, [[1]])
    assert not grids_equal([[1]], None)


def test_score_task_both_attempts_wrong() -> None:
    task = _task("t1", [[[1, 1]]])
    attempts = [[Attempt(grid=[[0, 0]]), Attempt(grid=[[2, 2]])]]
    result = score_task(task, attempts)
    assert result.solved is False
    assert result.test_results[0].solved is False


def test_score_task_attempt2_rescues() -> None:
    task = _task("t1", [[[1, 1]]])
    attempts = [[Attempt(grid=[[0, 0]]), Attempt(grid=[[1, 1]])]]
    result = score_task(task, attempts)
    assert result.solved is True
    assert result.test_results[0].solved is True


def test_score_task_parse_failure_counts_wrong() -> None:
    task = _task("t1", [[[1, 1]]])
    attempts = [[Attempt(grid=None, parse_error="no grid found"), Attempt(grid=[[0]])]]
    result = score_task(task, attempts)
    assert result.solved is False


def test_score_task_multi_test_any_wrong_means_task_wrong() -> None:
    task = _task("t1", [[[1]], [[2]]])
    attempts = [
        [Attempt(grid=[[1]])],  # first test solved
        [Attempt(grid=[[9]])],  # second test wrong
    ]
    result = score_task(task, attempts)
    assert result.solved is False
    assert result.test_results[0].solved is True
    assert result.test_results[1].solved is False


def test_score_task_caps_extra_attempts() -> None:
    """Attempts past MAX_ATTEMPTS_PER_TEST_INPUT are ignored (not scored)."""
    assert MAX_ATTEMPTS_PER_TEST_INPUT == 2
    task = _task("t1", [[[1]]])
    attempts = [[Attempt(grid=[[0]]), Attempt(grid=[[0]]), Attempt(grid=[[1]])]]
    result = score_task(task, attempts)
    assert result.solved is False  # third attempt with [[1]] is ignored
    assert len(result.test_results[0].attempts) == 2


def test_score_task_attempts_length_mismatch_raises() -> None:
    task = _task("t1", [[[1]], [[2]]])
    with pytest.raises(ValueError, match="expected attempts for 2"):
        score_task(task, [[Attempt(grid=[[1]])]])


def test_aggregate() -> None:
    task1 = _task("t1", [[[1]]])
    task2 = _task("t2", [[[2]], [[3]]])
    r1 = score_task(task1, [[Attempt(grid=[[1]])]])
    r2 = score_task(task2, [[Attempt(grid=[[2]])], [Attempt(grid=[[9]])]])

    agg = aggregate([r1, r2])
    assert agg.tasks_total == 2
    assert agg.tasks_solved == 1
    assert agg.test_inputs_total == 3
    assert agg.test_inputs_solved == 2
    assert agg.score == 0.5
