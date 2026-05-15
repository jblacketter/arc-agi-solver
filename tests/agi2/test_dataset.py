"""Tests for arcsolver.agi2.dataset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arcsolver.agi2.dataset import DATA_DIR, load_split, load_task


def test_load_task_shape(tmp_path: Path) -> None:
    raw = {
        "train": [{"input": [[1, 2], [3, 4]], "output": [[4, 3], [2, 1]]}],
        "test": [{"input": [[0, 0]], "output": [[0, 0]]}],
    }
    p = tmp_path / "abc123.json"
    p.write_text(json.dumps(raw))

    task = load_task(p)
    assert task.task_id == "abc123"
    assert len(task.train) == 1
    assert task.train[0].input == [[1, 2], [3, 4]]
    assert task.train[0].output == [[4, 3], [2, 1]]
    assert len(task.test) == 1


def test_load_task_rejects_malformed(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"train": []}))  # missing 'test'
    with pytest.raises(ValueError, match="train"):
        load_task(p)


def test_load_evaluation_split_full_count() -> None:
    """The evaluation split must contain exactly 120 tasks (Phase 1 invariant).

    Skips cleanly when data hasn't been fetched yet.
    """
    eval_dir = DATA_DIR / "evaluation"
    if not eval_dir.exists():
        pytest.skip("ARC-AGI-2 evaluation data not fetched yet — run `just fetch-data`.")
    tasks = load_split("evaluation")
    assert len(tasks) == 120, f"expected 120 evaluation tasks, got {len(tasks)}"


def test_load_split_limit() -> None:
    eval_dir = DATA_DIR / "evaluation"
    if not eval_dir.exists():
        pytest.skip("ARC-AGI-2 evaluation data not fetched yet.")
    tasks = load_split("evaluation", limit=3)
    assert len(tasks) == 3


def test_load_split_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("arcsolver.agi2.dataset.DATA_DIR", tmp_path / "nope")
    with pytest.raises(FileNotFoundError, match="not found"):
        load_split("training")
