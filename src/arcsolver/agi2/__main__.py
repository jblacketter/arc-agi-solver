"""CLI entry point: `python -m arcsolver.agi2 <subcommand>`.

Currently exposes:
- `eval` — run an agent against an ARC-AGI-2 split and write a result directory.

Add new subcommands as siblings (e.g. `solve-task`, `report`) without
restructuring.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from arcsolver.agi2.agents.base import Agent
from arcsolver.agi2.agents.baseline_llm import BaselineLLM
from arcsolver.agi2.pricing import DEFAULT_MODEL
from arcsolver.agi2.runner import RESULTS_ROOT, MissingApiKey, run_eval


def _baseline_llm_factory(model: str) -> Agent:
    return BaselineLLM(model=model)


_AGENTS = {
    "baseline_llm": _baseline_llm_factory,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="arcsolver.agi2")
    sub = p.add_subparsers(dest="cmd", required=True)

    ev = sub.add_parser("eval", help="run an agent against a split and score it")
    ev.add_argument(
        "--agent",
        required=True,
        choices=sorted(_AGENTS),
        help="which agent to run",
    )
    ev.add_argument(
        "--split",
        required=True,
        choices=["training", "evaluation"],
        help="which ARC-AGI-2 split to evaluate against",
    )
    ev.add_argument(
        "--limit",
        type=int,
        default=30,
        help="number of tasks to evaluate (default: 30). Use --all to run the full split.",
    )
    ev.add_argument(
        "--all",
        dest="all_tasks",
        action="store_true",
        help="evaluate the entire split (overrides --limit)",
    )
    ev.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model name (default: {DEFAULT_MODEL})",
    )
    ev.add_argument(
        "--max-cost-usd",
        type=float,
        default=15.0,
        help="hard ceiling on cumulative cost (USD) for this invocation",
    )
    ev.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(f"parent directory for the per-run result subdirectory (default: {RESULTS_ROOT})"),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "eval":
        limit: int | None = None if args.all_tasks else args.limit
        results_root: Path = args.output if args.output is not None else RESULTS_ROOT
        try:
            out_dir, summary = run_eval(
                agent_factory=_AGENTS[args.agent],
                agent_name=args.agent,
                model=args.model,
                split=args.split,
                limit=limit,
                max_cost_usd=args.max_cost_usd,
                results_root=results_root,
            )
        except MissingApiKey as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        _print_one_line_summary(summary, out_dir)
        return 0 if summary["status"] == "ok" else 3

    parser.error(f"unknown command {args.cmd!r}")
    return 1  # pragma: no cover


def _print_one_line_summary(summary: dict[str, Any], out_dir: Any) -> None:
    cache = summary.get("cache_hit_ratio", 0.0)
    print(
        f"agent={summary['agent']} model={summary['model']} "
        f"split={summary['split']} tasks={summary['tasks_attempted']} "
        f"solved={summary['tasks_solved']} score={summary['score']:.3f} "
        f"cost=${summary['cost_usd']:.4f} cache_hit={cache:.3f} "
        f"status={summary['status']} dir={out_dir}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
