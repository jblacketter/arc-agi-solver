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

# Quick all-checks gate (no data fetch).
check: lint typecheck test
