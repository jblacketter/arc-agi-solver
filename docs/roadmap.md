# Project Roadmap

## Overview
Build an open-source agent/solver that competes in the ARC Prize on Kaggle. The plan is to land a working baseline on **ARC-AGI-2** (grid transduction) first, then extend to **ARC-AGI-3** (interactive reasoning) using the same scoring and agent infrastructure where possible. Solution will be open-sourced under Apache-2.0 to be eligible for the open-source prize track.

**Tech Stack:** Python 3.11+, `uv` for dependency management, the `arc-agi` SDK, Anthropic Claude (initial baseline), `pytest` / `ruff` / `mypy`, eventual Kaggle submission packaging.

**Workflow:** Lead / Reviewer with Human Arbiter (see `tagteam.yaml`).

## Phases

### Phase 1: foundations
- **Status:** Not Started
- **Description:** Project scaffolding: Python env, package layout, license, `arc-agi` SDK installed, ARC-AGI-2 dataset downloaded, smoke test proves both AGI-2 task loading and AGI-3 env creation work end-to-end.
- **Key Deliverables:**
  - `pyproject.toml` (uv-managed), `src/arcsolver/` package skeleton, `tests/` with smoke test
  - `LICENSE` (Apache-2.0), `README.md`, `.gitignore`, initialized git repo with first commit
  - ARC-AGI-2 dataset present under `data/` (gitignored) with a documented fetch script
  - Smoke test loads one AGI-2 task and one AGI-3 env (`arc.make("ls20")`) without error

### Phase 2: agi2-baseline
- **Status:** Not Started
- **Description:** Build a scoring harness for ARC-AGI-2 and ship a minimal Claude-based baseline agent so we have a reproducible baseline score on the public eval split.
- **Key Deliverables:**
  - `arcsolver.agi2.scoring` module that reads tasks, runs an agent, and reports per-task + aggregate accuracy
  - `arcsolver.agi2.agents.baseline_llm` — minimal prompt-only Claude agent
  - Recorded baseline score in `docs/decision_log.md`

### Phase 3: agi2-approach
- **Status:** Not Started
- **Description:** Survey ARC-AGI-2 prior art (program synthesis, DSL search, test-time training, LLM + search, hybrid). Pick a direction with explicit tradeoffs.
- **Key Deliverables:**
  - Literature/repo survey notes under `docs/research/agi2_survey.md`
  - ADR in `docs/decision_log.md` selecting the approach and explaining why

### Phase 4: agi2-solver
- **Status:** Not Started
- **Description:** Implement and tune the chosen AGI-2 solver against the public eval split.
- **Key Deliverables:**
  - Solver implementation under `arcsolver.agi2.solvers.<approach>`
  - Eval report showing score improvement over the Phase 2 baseline

### Phase 5: agi2-submit
- **Status:** Not Started
- **Description:** Package the AGI-2 solver for Kaggle submission and post our first leaderboard score.
- **Key Deliverables:**
  - Kaggle-compatible submission notebook/script with runtime + dependency constraints handled
  - Local dry-run that mirrors the Kaggle environment
  - First leaderboard submission recorded

### Phase 6: agi3-port
- **Status:** Not Started
- **Description:** Extend the agent loop to the interactive ARC-AGI-3 environment SDK and establish a baseline score across the available games.
- **Key Deliverables:**
  - `arcsolver.agi3` package with an env-runner that drives `arc.make(...)` envs
  - Baseline (random + naive LLM) scores recorded for the public AGI-3 games

### Phase 7: agi3-solver
- **Status:** Not Started
- **Description:** Iterate on an AGI-3 approach (likely LLM tool-use + planning + memory) and improve over baseline.
- **Key Deliverables:**
  - Solver implementation under `arcsolver.agi3.solvers.<approach>`
  - Eval report across AGI-3 games

### Phase 8: agi3-submit
- **Status:** Not Started
- **Description:** Package the AGI-3 solver for the Kaggle ARC-AGI-3 leaderboard.
- **Key Deliverables:**
  - Kaggle-compatible submission for the AGI-3 track
  - First AGI-3 leaderboard submission recorded

## Decision Log
See `docs/decision_log.md`

## Getting Started
1. Use `/phase` to check current phase
2. Use `/plan create [phase]` to start planning
3. Use `/status` for project overview
