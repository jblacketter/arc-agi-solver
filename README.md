# arcsolver

An open-source effort to compete in the [ARC Prize](https://arcprize.org/) on Kaggle. The plan is to land a baseline on **ARC-AGI-2** (grid transduction) first, then extend to **ARC-AGI-3** (interactive reasoning) using shared infrastructure where possible.

See `docs/roadmap.md` for the full phase plan and `docs/phases/foundations.md` for the Phase 1 scope this README implements.

## Requirements

- macOS or Linux
- Python 3.12 (managed via `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [`just`](https://github.com/casey/just) — `brew install just` or `cargo install just`
- `git`

## Setup

```bash
just setup        # uv sync --extra dev (runtime + dev deps into .venv)
just fetch-data   # download ARC-AGI-2 dataset at the pinned commit
just check        # lint + typecheck + tests
```

The `fetch-data` step is required before `just test` will exercise the ARC-AGI-2 smoke case (it skips with a clear message until the data is present).

## Layout

```
src/arcsolver/
  agi2/        # ARC-AGI-2 (grid transduction) code (Phase 2+)
  agi3/        # ARC-AGI-3 (interactive) code (Phase 6+)
  common/      # shared utilities
scripts/
  fetch_agi2_data.py  # pinned-SHA dataset fetch
tests/
  test_smoke.py
docs/
  roadmap.md
  phases/foundations.md
  decision_log.md
```

The `data/` directory is created by `just fetch-data` and is gitignored.

## Running the AGI-2 baseline

Phase 2 ships a Claude-based baseline agent and a scoring harness. Offline checks (`just check`) don't touch the Anthropic API. To actually run the baseline you need `ANTHROPIC_API_KEY` set.

```bash
# 3-task live smoke (~$0.20 on Opus 4.7).
just eval-smoke

# Recorded baseline on 30 evaluation tasks (default --limit 30, ~$5-7 on Opus 4.7).
just eval

# Override flags by passing them through (max-cost ceiling, model, etc).
just eval --limit 10 --max-cost-usd 3
just eval --all --max-cost-usd 30      # full 120-task eval
just eval --model claude-sonnet-4-6     # cheaper alternative
```

Each run writes a directory under `results/agi2/<timestamp>_<agent>_<split>_<n>/`:
- `summary.json` — score, token counts, cache-hit ratio, cost
- `per_task.json` — per-task and per-test-input breakdown
- `raw_responses.jsonl` — per-API-call usage records

`--max-cost-usd` is a hard ceiling: if cumulative spend exceeds it mid-run, the runner aborts cleanly and writes a partial `summary.json` with `status: "aborted_cost_ceiling"`. **`just eval-smoke` and `just eval` cost real money.**

## Environment variables

Copy `.env.example` to `.env` and fill in as needed:

- `ANTHROPIC_API_KEY` — required from Phase 2 onward for Claude-based baselines
- `ARC_API_KEY` — required if the `arc_agi` SDK uses the hosted ARC-AGI-3 environments

## Workflow

This project uses the lead/reviewer tagteam workflow (`tagteam.yaml`). Plans and implementations go through review cycles before being accepted. Run `/handoff` (in Claude Code or codex) to act on the current cycle state.

## License

Apache-2.0. See [`LICENSE`](./LICENSE).
