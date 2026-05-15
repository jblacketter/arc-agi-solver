"""Eval runner for ARC-AGI-2 agents.

Responsibilities:
- Validate preconditions (e.g. ANTHROPIC_API_KEY for LLM agents) **before**
  any side effects so a missing key never creates a half-written `results/`.
- Load tasks, run the agent on each, score the results.
- Stream per-call usage to `raw_responses.jsonl`; aggregate into `summary.json`
  and `per_task.json` at the end (or on cost-ceiling abort).
- Enforce a hard `--max-cost-usd` ceiling using the central pricing table.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arcsolver.agi2.agents.base import Agent, CallUsage
from arcsolver.agi2.dataset import Split, load_split
from arcsolver.agi2.pricing import call_cost_usd
from arcsolver.agi2.scoring import aggregate, score_task
from arcsolver.agi2.types import Task, TaskResult

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RESULTS_ROOT = REPO_ROOT / "results" / "agi2"

AgentFactory = Callable[[str], Agent]


@dataclass
class CostTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float = 0.0

    def add_call(self, usage: CallUsage, model: str) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cache_creation_input_tokens += usage.cache_creation_input_tokens
        self.cache_read_input_tokens += usage.cache_read_input_tokens
        self.cost_usd += call_cost_usd(
            model,
            input_tokens=usage.input_tokens,
            cache_creation_input_tokens=usage.cache_creation_input_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens,
            output_tokens=usage.output_tokens,
        )

    def cache_hit_ratio(self) -> float:
        denom = self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens
        if denom == 0:
            return 0.0
        return self.cache_read_input_tokens / denom


class CostCeilingExceeded(RuntimeError):
    """Raised internally when cumulative spend has exceeded `--max-cost-usd`."""


class MissingApiKey(RuntimeError):
    """Raised before any side effects when an LLM agent requires an env var
    that isn't set."""


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def make_result_dir(
    *, agent: str, split: str, limit: int | None, root: Path = RESULTS_ROOT
) -> Path:
    n = "all" if limit is None else str(limit)
    name = f"{_timestamp()}_{agent}_{split}_{n}"
    out = root / name
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("a") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _build_summary(
    *,
    agent_name: str,
    model: str,
    split: str,
    limit: int | None,
    results: list[TaskResult],
    totals: CostTotals,
    status: str,
    note: str | None = None,
) -> dict[str, Any]:
    agg = aggregate(results)
    summary: dict[str, Any] = {
        "status": status,
        "agent": agent_name,
        "model": model,
        "split": split,
        "limit": limit,
        "tasks_attempted": len(results),
        "tasks_solved": agg.tasks_solved,
        "test_inputs_total": agg.test_inputs_total,
        "test_inputs_solved": agg.test_inputs_solved,
        "score": agg.score,
        "tokens": {
            "input": totals.input_tokens,
            "output": totals.output_tokens,
            "cache_write": totals.cache_creation_input_tokens,
            "cache_read": totals.cache_read_input_tokens,
        },
        "cost_usd": round(totals.cost_usd, 6),
        "cache_hit_ratio": round(totals.cache_hit_ratio(), 6),
        "cache_hit_ratio_definition": (
            "cache_read / (input + cache_write + cache_read), "
            "fraction of total input tokens served from cache"
        ),
    }
    if note is not None:
        summary["note"] = note
    return summary


def _write_summary_and_per_task(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    results: list[TaskResult],
) -> None:
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    per_task = [
        {
            "task_id": r.task_id,
            "solved": r.solved,
            "test_inputs": [
                {
                    "solved": t.solved,
                    "attempts": [
                        {"grid": a.grid, "parse_error": a.parse_error} for a in t.attempts
                    ],
                }
                for t in r.test_results
            ],
        }
        for r in results
    ]
    (out_dir / "per_task.json").write_text(json.dumps(per_task, indent=2) + "\n")


def _check_api_key_for_agent(agent_name: str) -> None:
    """Fail fast — no side effects — when an LLM agent needs a key that isn't set."""
    if agent_name == "baseline_llm" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise MissingApiKey(
            "ANTHROPIC_API_KEY is not set, but agent 'baseline_llm' requires it. "
            "Set the env var (see .env.example) and try again. No results directory "
            "has been created and no API calls were made."
        )


def run_eval(
    *,
    agent_factory: AgentFactory,
    agent_name: str,
    model: str,
    split: Split,
    limit: int | None,
    max_cost_usd: float,
    results_root: Path = RESULTS_ROOT,
) -> tuple[Path, dict[str, Any]]:
    """Run an agent across a split and write a result directory.

    Returns `(result_dir, summary_dict)`. Raises `MissingApiKey` before
    creating any output if the agent needs an env var that isn't set.
    """
    _check_api_key_for_agent(agent_name)

    tasks: list[Task] = load_split(split, limit=limit)
    agent = agent_factory(model)
    if agent.model != model:
        # Factory must honor the requested model; surface mismatches loudly.
        raise RuntimeError(
            f"agent_factory returned an agent for model {agent.model!r}, expected {model!r}"
        )

    out_dir = make_result_dir(agent=agent_name, split=split, limit=limit, root=results_root)
    raw_path = out_dir / "raw_responses.jsonl"
    totals = CostTotals()
    results: list[TaskResult] = []

    aborted = False
    abort_note: str | None = None

    for task in tasks:
        run = agent.solve(task)
        # Stream the call usage immediately so a mid-run crash still leaves a trail.
        _write_jsonl(
            raw_path,
            ({"task_id": run.task_id, **asdict(call)} for call in run.calls),
        )
        for call in run.calls:
            totals.add_call(call, model)
        results.append(score_task(task, run.attempts_per_test))
        if totals.cost_usd > max_cost_usd:
            aborted = True
            abort_note = (
                f"Aborted after task {task.task_id}: cumulative cost "
                f"${totals.cost_usd:.4f} exceeded --max-cost-usd ${max_cost_usd:.2f}."
            )
            break

    status = "aborted_cost_ceiling" if aborted else "ok"
    summary = _build_summary(
        agent_name=agent_name,
        model=model,
        split=split,
        limit=limit,
        results=results,
        totals=totals,
        status=status,
        note=abort_note,
    )
    _write_summary_and_per_task(out_dir=out_dir, summary=summary, results=results)
    return out_dir, summary
