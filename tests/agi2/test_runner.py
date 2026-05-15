"""Tests for the eval runner.

Covers the two behaviors codex specifically asked for:
1. Fail fast on missing API key — no result directory, no API call.
2. Cost-ceiling abort — partial summary written with status=aborted_cost_ceiling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arcsolver.agi2.agents.base import AgentTaskRun, CallUsage
from arcsolver.agi2.runner import MissingApiKey, run_eval
from arcsolver.agi2.types import Attempt, Task


class _FakeAgent:
    """A scripted agent whose attempts and per-call usage are predetermined."""

    name = "baseline_llm"

    def __init__(
        self, model: str, *, attempt_grid: list[list[int]] | None, per_call_usage: CallUsage
    ) -> None:
        self.model = model
        self._attempt_grid = attempt_grid
        self._per_call_usage = per_call_usage

    def solve(self, task: Task) -> AgentTaskRun:
        attempts_per_test: list[list[Attempt]] = []
        calls: list[CallUsage] = []
        for _ in task.test:
            attempts_per_test.append(
                [
                    Attempt(grid=self._attempt_grid),
                    Attempt(grid=self._attempt_grid),
                ]
            )
            calls.extend([self._per_call_usage, self._per_call_usage])
        return AgentTaskRun(
            task_id=task.task_id,
            attempts_per_test=attempts_per_test,
            calls=calls,
        )


def _fake_tasks(tmp_path: Path, n: int) -> Path:
    """Write n synthetic task files into a fake `data/agi2/training/` tree."""
    train_dir = tmp_path / "training"
    train_dir.mkdir(parents=True)
    for i in range(n):
        (train_dir / f"task_{i:03d}.json").write_text(
            json.dumps(
                {
                    "train": [{"input": [[0]], "output": [[1]]}],
                    "test": [{"input": [[0]], "output": [[1]]}],
                }
            )
        )
    return tmp_path


def test_runner_fails_fast_on_missing_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No API key + LLM agent => MissingApiKey before any side effects."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("arcsolver.agi2.dataset.DATA_DIR", _fake_tasks(tmp_path, n=2))
    results_root = tmp_path / "results"

    with pytest.raises(MissingApiKey, match="ANTHROPIC_API_KEY"):
        run_eval(
            agent_factory=lambda model: _FakeAgent(
                model, attempt_grid=[[1]], per_call_usage=CallUsage()
            ),
            agent_name="baseline_llm",
            model="claude-opus-4-7",
            split="training",
            limit=2,
            max_cost_usd=10.0,
            results_root=results_root,
        )

    # No directory should have been created.
    assert not results_root.exists() or not any(results_root.iterdir())


def test_runner_writes_summary_and_per_task_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr("arcsolver.agi2.dataset.DATA_DIR", _fake_tasks(tmp_path, n=3))
    results_root = tmp_path / "results"

    out_dir, summary = run_eval(
        agent_factory=lambda model: _FakeAgent(
            model,
            attempt_grid=[[1]],
            per_call_usage=CallUsage(input_tokens=100, output_tokens=10),
        ),
        agent_name="baseline_llm",
        model="claude-opus-4-7",
        split="training",
        limit=3,
        max_cost_usd=10.0,
        results_root=results_root,
    )

    assert summary["status"] == "ok"
    assert summary["tasks_attempted"] == 3
    assert summary["tasks_solved"] == 3  # fake agent always returns [[1]] which matches
    assert summary["score"] == 1.0
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "per_task.json").exists()
    assert (out_dir / "raw_responses.jsonl").exists()


def test_runner_aborts_at_cost_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pricey usage payload trips the ceiling; partial summary is written."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr("arcsolver.agi2.dataset.DATA_DIR", _fake_tasks(tmp_path, n=5))
    results_root = tmp_path / "results"

    # 2M output tokens per call. Opus 4.7 = $25/M output. Two calls per task
    # => $100 per task. Ceiling $30 => abort after first task.
    pricey = CallUsage(output_tokens=2_000_000)

    out_dir, summary = run_eval(
        agent_factory=lambda model: _FakeAgent(model, attempt_grid=[[1]], per_call_usage=pricey),
        agent_name="baseline_llm",
        model="claude-opus-4-7",
        split="training",
        limit=5,
        max_cost_usd=30.0,
        results_root=results_root,
    )

    assert summary["status"] == "aborted_cost_ceiling"
    assert summary["tasks_attempted"] == 1
    assert "exceeded --max-cost-usd" in summary["note"]
    assert (out_dir / "summary.json").exists()
    # raw_responses should also have rows from the aborted task.
    raw = (out_dir / "raw_responses.jsonl").read_text().splitlines()
    assert len(raw) == 2  # two calls before the abort check fired


def test_runner_reports_cache_hit_ratio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setattr("arcsolver.agi2.dataset.DATA_DIR", _fake_tasks(tmp_path, n=2))
    results_root = tmp_path / "results"

    usage = CallUsage(
        input_tokens=100,
        output_tokens=10,
        cache_creation_input_tokens=200,
        cache_read_input_tokens=700,
    )
    _, summary = run_eval(
        agent_factory=lambda model: _FakeAgent(model, attempt_grid=[[1]], per_call_usage=usage),
        agent_name="baseline_llm",
        model="claude-opus-4-7",
        split="training",
        limit=2,
        max_cost_usd=10.0,
        results_root=results_root,
    )
    # 700 / (100 + 200 + 700) = 0.7 across every call; aggregate stays 0.7.
    assert summary["cache_hit_ratio"] == 0.7
