# Project task runner. Run `just` to list available recipes.

default:
    @just --list

# Install dependencies (runtime + dev) into a uv-managed venv.
setup:
    uv sync --extra dev

# Run the test suite.
test:
    uv run pytest

# Lint + format check.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Type-check the library code.
typecheck:
    uv run mypy src/arcsolver

# Fetch the ARC-AGI-2 dataset at the pinned commit (see scripts/fetch_agi2_data.py).
fetch-data:
    uv run python scripts/fetch_agi2_data.py

# Quick all-checks gate (no data fetch, no network).
check: lint typecheck test

# === ARC-AGI-2 baseline ====================================================
# These hit the live Anthropic API and cost real money. They are intentionally
# NOT part of `just check` and the CI gate.

# Tiny live smoke (3 training tasks, $1 ceiling). Useful for sanity-checking
# the end-to-end agent on a real API call. Requires ANTHROPIC_API_KEY.
eval-smoke:
    uv run python -m arcsolver.agi2 eval --agent baseline_llm --split training --limit 3 --max-cost-usd 1

# Run the baseline against the public evaluation split. Default --limit 30
# (~$5-7 on Opus 4.7 with prompt caching). Pass --all for the full 120-task run.
eval *ARGS:
    uv run python -m arcsolver.agi2 eval --agent baseline_llm --split evaluation {{ARGS}}
