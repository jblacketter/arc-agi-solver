# Phase: foundations

## Status
- [ ] Planning
- [x] In Review (Round 4 — plan re-correction after stale-install red herring)
- [ ] Approved
- [ ] Implementation
- [ ] Implementation Review
- [ ] Complete

## Roles
- Lead: claude
- Reviewer: codex
- Arbiter: Human (jackblacketter)

## Summary
**What:** Stand up the project skeleton: Python toolchain, package layout, ARC-AGI-2 dataset acquisition from the official GitHub repo, and a smoke test that exercises both ARC-AGI-2 (JSON task load) and ARC-AGI-3 (`arc_agi.Arcade().make("ls20")`).
**Why:** Every later phase (baseline, solver, submission) depends on a reproducible local environment and the ability to load tasks/envs. Doing this once, cleanly, prevents cross-phase rework. Also unblocks open-sourcing the repo (LICENSE, README, git init).
**Depends on:** None — this is Phase 1.

## Round 4 — what changed and why (mea culpa)
Round 3 was based on a stale install. I had `arc-agi==0.0.7` resolved in the venv, which is an old "dataset toolkit" version of the package, and I built the Round 3 plan around its API (`ARC2Training.download()`, no `Arcade`). When I later added `arc-agi-3` to the deps, uv re-resolved and upgraded `arc-agi` to **0.9.8 — the current ARC-AGI-3 SDK that the docs.arcprize.org quickstart actually documents**. The 0.0.7 version is a defunct earlier package, not the current one.

Verified by hand against the running venv:

- `arc-agi 0.9.8` (`requires_python = ">=3.12"`) exposes `Arcade`, `EnvironmentWrapper`, `LocalEnvironmentWrapper`, `ScorecardManager`, etc. The docs.arcprize.org quickstart code works as written.
- `arc_agi.Arcade()` obtains an anonymous API key automatically if `ARC_API_KEY` isn't set; `arc.make("ls20")` returns a `LocalEnvironmentWrapper` (not `None`) and downloads game code into `environment_files/<game>/<version>/` on first use.
- `Arcade.make` is typed `Optional[EnvironmentWrapper]` — `is not None` remains the right assertion.
- No `ARC2Training.download()` exists in 0.9.8. AGI-2 dataset acquisition is back to cloning `arcprize/ARC-AGI-2` (Round 1/2 plan was right).
- `arc-agi-3` (separate PyPI package) is a higher-level agent-templates SDK (`Agent` ABC, `AVAILABLE_AGENTS`). We do **not** need it in Phase 1; if we adopt the templates later it can be added as a Phase-6+ dependency.

Net effect: this Round 4 plan is essentially the Round 2 plan, plus a Python 3.12 floor and a `.gitignore` for the new SDK working dirs.

## Scope

### In Scope
- Initialize git repository at the project root and create an initial commit
- `pyproject.toml` managed by `uv`, pinned to Python `>=3.12,<3.14` (required by `arc-agi>=0.9.8`)
- **Runtime dependencies** in `[project.dependencies]`: `arc-agi>=0.9.8`, `anthropic`, `requests`
- **Dev dependencies** in `[project.optional-dependencies].dev`: `pytest`, `ruff`, `mypy`. Installed via `uv sync --extra dev` (mirrored in the `justfile` and README).
- Source layout: `src/arcsolver/__init__.py`, with submodule placeholders `agi2/`, `agi3/`, `common/`
- `tests/` directory with `tests/test_smoke.py`
- `scripts/fetch_agi2_data.py` — idempotent fetch of ARC-AGI-2 training + evaluation JSON from the official `arcprize/ARC-AGI-2` GitHub repo. Pins an immutable upstream revision (specific commit SHA) as a module-level constant, fetches that exact revision, and aborts with a clear error if the fetched tree's task counts don't match the expected 1000 training + 120 evaluation files.
- `data/` directory, gitignored, populated by the fetch script
- `environment_files/` and `recordings/` added to `.gitignore` — these are SDK working dirs created by `Arcade()` on first run.
- `LICENSE` (Apache-2.0)
- `README.md` covering: project goal, install (`uv sync --extra dev`), how to fetch data, how to run smoke test, license
- `.gitignore` covering Python build artifacts, virtualenv dirs, `data/`, `.env`, `environment_files/`, `recordings/`, IDE files
- `justfile` with `setup`, `test`, `lint`, `typecheck`, `fetch-data` targets
- Smoke test composed of two cases:
  - **AGI-2 case** (hermetic once data is fetched): loads one ARC-AGI-2 task JSON from `data/agi2/training/`, asserts top-level keys `{"train", "test"}` exist and that `train` is a non-empty list.
  - **AGI-3 case**: imports `arc_agi` (`pytest.importorskip("arc_agi")`); constructs `arc_agi.Arcade().make("ls20")` and asserts the result is **not `None`**. Skips with an explicit reason only on: SDK import failure, missing `ARC_API_KEY` *if the SDK requires it* (current 0.9.8 falls back to an anonymous key, so this skip-path is defensive), and a documented "environment unavailable" error from the SDK. Any other exception or a `None` return is a test failure, not a skip.

### Out of Scope
- Any agent logic, prompting, or solver code (Phase 2+)
- Any scoring harness (Phase 2)
- `arc-agi-3` agent-template adoption (Phase 6+ if useful)
- CI configuration (deferred; we'll add GitHub Actions once the repo is pushed)
- Pushing to GitHub (lead will surface a recommended repo name; human handles `gh repo create`)

## Technical Approach
- **Package manager: `uv`.** Fast resolution, reproducible `uv.lock` (committed).
- **Python 3.12+** because `arc-agi>=0.9.8` requires it. Pinned via `.python-version`.
- **src-layout** keeps tests honest and matches modern Python packaging.
- **Data fetch as a script, not a build step.** The fetch script clones `arcprize/ARC-AGI-2` at a pinned commit SHA into a temp dir (`git clone` + `git checkout <SHA>`, not `--depth=1 --branch`, so the SHA is authoritative), copies the JSON files into `data/agi2/`, and verifies counts (1000 training, 120 evaluation) before declaring success. The pinned SHA lives as a `_PINNED_REV` constant at the top of the script.
- **Smoke test split into two cases.** AGI-2 case is hermetic once data is fetched. AGI-3 case calls `Arcade().make("ls20")` and asserts not-None; the SDK's anonymous-key fallback means it usually works without `ARC_API_KEY`, but we keep narrow documented skip-paths for SDK import failure, explicit "environment unavailable" exceptions, and any API-key requirement that surfaces.
- **Task runner: `justfile`**. **Lint/format: `ruff`**. **Types: `mypy` --strict** on `src/arcsolver/`.
- **Anthropic SDK pulled in now** even though Phase 1 doesn't use it, so the lockfile is stable across phases.

## Files to Create/Modify
- `pyproject.toml` — project metadata, deps, ruff/mypy/pytest config
- `uv.lock` — committed lockfile (generated)
- `.python-version` — pin to `3.12`
- `src/arcsolver/__init__.py` — package marker, version string
- `src/arcsolver/agi2/__init__.py`, `src/arcsolver/agi3/__init__.py`, `src/arcsolver/common/__init__.py` — submodule placeholders
- `tests/__init__.py`, `tests/test_smoke.py`
- `scripts/fetch_agi2_data.py`
- `justfile`
- `LICENSE` — Apache-2.0 (copyright "Jack Blacketter")
- `README.md`
- `.gitignore`
- `.env.example` — placeholders for `ANTHROPIC_API_KEY`, `ARC_API_KEY`

## Success Criteria
- [ ] `git log` shows at least one commit; `git status` clean
- [ ] `uv sync --extra dev` succeeds from a clean clone (verified by removing `.venv` and re-running)
- [ ] `just test` runs `pytest` and passes
- [ ] `just lint` passes (`ruff check` + `ruff format --check`)
- [ ] `just typecheck` passes (`mypy src/arcsolver`)
- [ ] `scripts/fetch_agi2_data.py` defines a `_PINNED_REV` constant containing a 40-char commit SHA of `arcprize/ARC-AGI-2`, and the fetch logic checks out exactly that SHA
- [ ] `just fetch-data` populates `data/agi2/training/*.json` (exactly **1000** files) and `data/agi2/evaluation/*.json` (exactly **120** files); the script aborts with a non-zero exit and a clear error if either count is wrong
- [ ] Smoke test loads `data/agi2/training/<first task>.json` and asserts top-level keys `{"train", "test"}` exist and `train` is a non-empty list
- [ ] Smoke test imports `arc_agi`, calls `arc_agi.Arcade().make("ls20")`, and asserts the result is not `None`. The test skips only on documented unavailable-environment / missing-SDK / missing-API-key conditions; any other failure mode fails the test.
- [ ] `README.md` documents install (`uv sync --extra dev`) + data fetch + smoke test commands and includes the license notice

## Open Questions
- Preferred GitHub repo name? Default: `arcprize-solver` under `jblacketter`. Confirm before Phase 1 closes.

**Resolved in Round 2:**
- Dev vs runtime dependency split → decided in favor of splitting. Runtime: `arc-agi`, `anthropic`, `requests`. Dev (`[project.optional-dependencies].dev`): `pytest`, `ruff`, `mypy`. Rationale: keeps Phase 5 submission packaging lean.

**Resolved in Round 4 (Round 3 reverted):**
- AGI-2 data source → official `arcprize/ARC-AGI-2` GitHub repo, fetched via `git clone` + checkout of a pinned `_PINNED_REV` SHA. (Round 3's plan to use `ARC2Training.download()` was based on a stale `arc-agi==0.0.7` install; the current `arc-agi>=0.9.8` is the AGI-3 SDK and does not expose that method.)
- AGI-3 smoke test → `arc_agi.Arcade().make("ls20") is not None`, matching docs.arcprize.org and `arc-agi 0.9.8`'s actual API.
- Python floor → `>=3.12,<3.14` (required by `arc-agi>=0.9.8`).
- `arc-agi-3` is **not** a Phase 1 dependency; reconsider when/if we adopt its agent templates in Phase 6+.

## Risks
- **`arc-agi-2` upstream repo restructures.** Mitigation: SHA pinning is an explicit deliverable; the fetch script fails loudly at the count check if upstream drifts.
- **`arc-agi` SDK API changes between 0.9.8 and the next release.** Mitigation: `uv.lock` pins the exact version; bumping it is a deliberate decision, not a silent upgrade. The smoke test exercises the `Arcade().make()` contract so an API change shows up as a test failure.
- **`uv` or `just` not installed on the dev machine.** Mitigation: README documents `curl -LsSf https://astral.sh/uv/install.sh | sh` and `brew install just`.
- **Apache-2.0 vs other OSI license for ARC Prize open-source eligibility.** Mitigation: ARC Prize rules accept any OSI-approved license; Apache-2.0 is the most common in this ecosystem.
