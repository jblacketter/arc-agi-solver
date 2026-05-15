# Phase: agi2-baseline

## Status
- [ ] Planning
- [x] In Review
- [ ] Approved
- [ ] Implementation
- [ ] Implementation Review
- [ ] Complete

## Roles
- Lead: claude
- Reviewer: codex
- Arbiter: Human (jackblacketter)

## Summary
**What:** Stand up a reproducible scoring harness for ARC-AGI-2 (loads tasks, runs an agent, scores predictions against ground truth) and ship a minimal Claude-based baseline agent. End the phase with a recorded baseline score on a defined subset of the public evaluation split.
**Why:** Every later AGI-2 phase (approach selection, solver, submission) compares against a baseline number. Without a scoring harness we can't measure improvements; without a baseline number there's nothing to improve over. We need both before we touch any DSL or program synthesis.
**Depends on:** Phase 1 (foundations) — needs `data/agi2/`, `src/arcsolver/agi2/`, the `uv`/`just`/`pytest` toolchain, and `arcsolver` installable from src.

## Scope

### In Scope
- **Data + types module** at `src/arcsolver/agi2/dataset.py` and `src/arcsolver/agi2/types.py`:
  - Typed `Grid`, `Pair`, `Task`, `Prediction`, `Attempt`, `TaskResult` dataclasses (pure dicts + helpers — we don't need to depend on `arc-agi`'s `Task` here).
  - `load_task(path)`, `load_split("training"|"evaluation")` — read JSON from `data/agi2/`.
- **Scoring module** at `src/arcsolver/agi2/scoring.py`:
  - Pure functions `grids_equal(a, b)`, `score_task(task, attempts)`, `aggregate(results)`.
  - Per-task scoring matches the Kaggle ARC-AGI rule: each test input gets **up to 2 attempts**; a test input counts as solved if either attempt matches exactly; a task counts as solved iff **all** test inputs are solved.
- **Agent protocol** at `src/arcsolver/agi2/agents/base.py`:
  - `class Agent(Protocol)` with `def solve(task: Task) -> list[list[Attempt]]` (one list per test input, each list ≤ 2 attempts).
- **Baseline LLM agent** at `src/arcsolver/agi2/agents/baseline_llm.py`:
  - Uses the `anthropic` SDK with **Claude Opus 4.7** (`claude-opus-4-7`) as the default model. Opus is the strongest Claude available, so the recorded baseline number represents the upper bound of pure-LLM performance — giving Phase 4's "fancy" solver a meaningful target to beat. Model is overridable via `--model`.
  - Prompt: a fixed system message describing ARC-AGI-2, followed by the training pairs serialized as grids, then the test input and a request for the predicted output grid. **Two attempts per test input** (independent samples with `temperature=0.7`).
  - Response parser tolerates light formatting (markdown code fences, leading/trailing whitespace); on parse failure, that attempt counts as a wrong answer (no retry).
  - **Anthropic prompt caching** with `cache_control: {"type": "ephemeral"}` placed on the **reusable ARC-AGI instruction block** (and any few-shot example block that is identical across tasks), not just on a short system header. The per-task content (training pairs, test input) is uncached. Cache effectiveness is measured, not assumed (see Success Criteria).
- **Eval runner** at `src/arcsolver/agi2/runner.py` + thin CLI at `src/arcsolver/agi2/__main__.py`:
  - `python -m arcsolver.agi2 eval --agent baseline_llm --split evaluation [--limit N] [--seed S] [--model MODEL] [--output PATH]`.
  - Saves a JSON report under `results/agi2/<timestamp>_<agent>_<split>_<limit>/{summary.json,per_task.json,raw_responses.jsonl}`.
  - For every Anthropic API call, persists the full usage payload in `raw_responses.jsonl`: `input_tokens` (uncached input), `output_tokens`, `cache_creation_input_tokens` (cache writes), `cache_read_input_tokens` (cache reads), each defaulted to 0 when the SDK omits them. `summary.json` aggregates these and includes a cache-hit ratio defined as `cache_read_input_tokens / (input_tokens + cache_creation_input_tokens + cache_read_input_tokens)` — i.e. fraction of total input tokens served from cache. The chosen denominator is documented in `summary.json` next to the value.
  - **Cost is computed from a central pricing table** at `src/arcsolver/agi2/pricing.py`. Each model entry has four explicit USD/M-token fields: `input` (uncached), `cache_write` (applies to `cache_creation_input_tokens`, typically a small premium over `input`), `cache_read` (applies to `cache_read_input_tokens`, typically ~10% of `input`), and `output`. Cost is not estimated client-side from token counts alone; the table is the single source of truth and is also what `--max-cost-usd` checks against. Each of the four buckets is exercised by a unit test.
  - **Fail-fast on missing `ANTHROPIC_API_KEY`:** if the env var is unset and the chosen agent needs it, the runner exits non-zero with a clear message **before** creating any `results/...` directory or making any API calls.
  - Prints a one-line summary to stdout: `agent=baseline_llm model=claude-opus-4-7 split=evaluation tasks=30 solved=4 score=0.133 cost=$5.42 cache_hit=0.61`.
- **Tests** at `tests/agi2/`:
  - `test_dataset.py` — load_task + load_split assert shape, count for `evaluation` (120).
  - `test_scoring.py` — `grids_equal`, `score_task` golden cases (all-match, partial-match, attempt-2-rescues, parse-failure).
  - `test_baseline_llm.py` — agent unit test with the `anthropic` client mocked at the SDK boundary so no live API calls run in CI.
- **Cost control:**
  - `--limit N` flag, default **`N=30`** for the first end-to-end run. Full eval (`--limit 120` or `--all`) is a deliberate operator action.
  - Token usage and cost (input + output) printed per-task and summarized.
  - Hard ceiling: runner aborts with a clear error if cumulative spend in a single invocation exceeds `--max-cost-usd` (default `$15`, sized for the Opus 4.7 default).
- **Recorded baseline:** appended to `docs/decision_log.md` with the date, model, limit, score, cost, and the path to the result directory. This is the canonical baseline number that Phases 3/4 will try to beat.
- **`.gitignore`:** add `results/` (per-run reports can be large; we record the headline number in `decision_log.md`).

### Out of Scope
- Any non-LLM approach (program synthesis, DSL search, test-time training) — those land in Phases 3/4.
- Tool-use, code execution, multi-step reasoning, planning loops — also Phase 4.
- ARC-AGI-3 (Phases 6+).
- Kaggle submission packaging (Phase 5).
- Running the full 120-task eval as part of the cycle deliverable — the harness must support it, but the baseline number we record can come from any explicit `--limit` (>=30) the human/lead picks.

## Technical Approach
- **Don't reuse `arc_agi`'s `Task`/`Grid` types.** The current `arc-agi==0.9.8` package is the AGI-3 SDK; its `Task` type is shaped for env interaction, not for transduction. A small, local dataclass layer is simpler and won't drift with SDK churn.
- **Scoring is pure and synchronous.** All API-touching code lives in the agent. Scoring only sees `(task, list_of_attempts)`. This makes tests fast and makes alternate agents (Phases 3/4) drop-in replacements.
- **Anthropic SDK with prompt caching.** `cache_control` is attached to the reusable ARC-AGI instruction block (substantial — task description, encoding format, attempt rules) so the cache breakpoint sits on a block large enough to be worth caching. Per-task content (training pairs, test input) stays uncached. Actual cache effectiveness is measured per run and surfaced in `summary.json` — we don't claim a fixed savings rate.
- **Two attempts per test input matches Kaggle scoring.** Each attempt is an independent completion at `temperature=0.7` (so the second attempt isn't an exact duplicate of the first). Identical attempts after parse are de-duplicated for the cost report.
- **Failure modes are wrong answers, not exceptions.** If the LLM returns un-parseable output, the attempt is recorded as `Attempt(grid=None, parse_error=...)` and counts as wrong. The runner does not retry; we don't want hidden cost from silent retries.
- **CLI structure:** one entry point (`python -m arcsolver.agi2`), one subcommand for now (`eval`), structured for future siblings (`solve-task`, `report`, etc.) without restructuring.
- **Test isolation from the Anthropic API.** `tests/agi2/test_baseline_llm.py` uses `monkeypatch` to swap `anthropic.Anthropic` with a fake that returns canned responses. Tests run offline in `just check`. A separate `just eval-smoke` recipe runs the agent against 3 training tasks with a real API call; it's opt-in and not part of the gate.

## Files to Create/Modify
- `src/arcsolver/agi2/__init__.py` — re-export public API (`load_task`, `load_split`, `Agent`, `BaselineLLM`, `evaluate`)
- `src/arcsolver/agi2/__main__.py` — CLI entry point
- `src/arcsolver/agi2/types.py`
- `src/arcsolver/agi2/dataset.py`
- `src/arcsolver/agi2/scoring.py`
- `src/arcsolver/agi2/runner.py`
- `src/arcsolver/agi2/pricing.py` — model → {input, cached_input, output} USD/M-tokens
- `tests/agi2/test_pricing.py`
- `tests/agi2/test_runner.py` — fail-fast on missing API key, cost-ceiling abort behavior
- `src/arcsolver/agi2/agents/__init__.py`
- `src/arcsolver/agi2/agents/base.py`
- `src/arcsolver/agi2/agents/baseline_llm.py`
- `tests/agi2/__init__.py`
- `tests/agi2/test_dataset.py`
- `tests/agi2/test_scoring.py`
- `tests/agi2/test_baseline_llm.py`
- `justfile` — add `eval` and `eval-smoke` recipes
- `.gitignore` — add `results/`
- `docs/decision_log.md` — record baseline number at end of impl
- `README.md` — short section on running the baseline locally

## Success Criteria
- [ ] `just check` (lint + typecheck + test) passes from a clean clone after `uv sync --extra dev`
- [ ] `tests/agi2/test_dataset.py` asserts `len(load_split("evaluation")) == 120` (when data is present; skips cleanly when not)
- [ ] `tests/agi2/test_scoring.py` covers: both-attempts-wrong, attempt-2-rescues, parse-failure, multi-test-input task (any-test-wrong → task wrong)
- [ ] `tests/agi2/test_baseline_llm.py` runs offline (no `anthropic.Anthropic` instantiated against the real network)
- [ ] `python -m arcsolver.agi2 eval --agent baseline_llm --split evaluation --limit 3 --max-cost-usd 1` runs end-to-end against the live Anthropic API and writes `results/agi2/<...>/summary.json`. This live check is **opt-in and not part of `just check`** — it lives behind `just eval-smoke` and the README documents that it costs real money.
- [ ] With `ANTHROPIC_API_KEY` unset, the same `python -m arcsolver.agi2 eval --agent baseline_llm ...` invocation exits non-zero with a clear error message and creates **no** `results/...` directory, no `raw_responses.jsonl`, and makes no Anthropic API call. Covered by a `tests/agi2/test_runner.py` case that asserts the failure mode.
- [ ] `raw_responses.jsonl` records `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens` (when reported by the SDK) for every API call. `summary.json` includes aggregate token counts, the cache-hit ratio, the model name, and the total cost computed from `src/arcsolver/agi2/pricing.py`.
- [ ] `src/arcsolver/agi2/pricing.py` has unit-tested entries for `claude-opus-4-7` and at least one Sonnet model. Each entry has four explicit USD/M-token rates: `input`, `cache_write`, `cache_read`, `output`. The pricing tests cover all four buckets independently and assert the per-call cost formula handles a mix of cached and uncached input on the same call. Cost computations in tests use this table — there are no hardcoded prices anywhere else.
- [ ] `--max-cost-usd` is enforced from the central pricing table (not from an estimate). A runner unit test asserts that exceeding the ceiling aborts the run cleanly and writes a partial `summary.json` flagged `status: "aborted_cost_ceiling"` (so the operator can still see what was spent).
- [ ] A recorded baseline run (`--limit >= 30`) is captured in `docs/decision_log.md` with: date, model, limit, score, cost, result-directory path
- [ ] `mypy --strict` clean across `src/arcsolver/agi2/`

## Open Questions
- **Default limit for the recorded baseline:** `--limit 30` (estimated cost on Opus 4.7: ~$5-7 with prompt caching; full 120 would be ~$20-30). Codex/human may want `--limit 120` for the full headline number despite the cost.

**Resolved before submission:**
- Default model → **Claude Opus 4.7** (`claude-opus-4-7`). Chosen so the recorded baseline is the upper-bound pure-LLM number; Phase 4's solver work has a clearer "did the fancy approach actually beat the best LLM-only approach" comparison. Trade-off: ~5x cost vs Sonnet for the same task count.
- **Where to source `ANTHROPIC_API_KEY` in CI:** out of scope for this phase since CI isn't wired yet, but the runner reads from env (`os.environ["ANTHROPIC_API_KEY"]`) and fails fast with a clear message if unset.

## Risks
- **Cost overrun (real risk on Opus).** Mitigation: `--max-cost-usd` hard ceiling, default `$15`. Per-task cost reporting in stdout so the operator sees spend in real time. Default `--limit 30`. Prompt-caching usage is recorded in `summary.json` (cache writes, cache reads, hit ratio); expected savings are not assumed — the recorded run is the source of truth. Each `python -m arcsolver.agi2 eval` invocation enforces its own ceiling — no implicit cross-run accumulation.
- **Prompt format that doesn't survive non-trivial tasks.** Mitigation: parse failures count as wrong answers (not retries), so cost is bounded. Phase 3 (approach selection) explicitly revisits prompt format.
- **Claude API changes (rate limits, model deprecation).** Mitigation: model name is a CLI flag; the default (`claude-opus-4-7`) lives as a single constant alongside the pricing table, so flipping the default is a one-line change.
- **`anthropic` SDK behavior changes between versions.** Mitigation: version pinned in `uv.lock` (Phase 1 already locked it). Tests mock at the `anthropic.Anthropic` boundary so SDK shape changes surface as test failures.
- **A test that hits live Anthropic by accident.** Mitigation: `just check` does NOT include `just eval-smoke`. CI gates run `just check` only. The eval-smoke recipe documents that it costs real money.
