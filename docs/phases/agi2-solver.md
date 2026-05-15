# Phase: agi2-solver

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
**What:** Implement an LLM-driven Python program-induction agent (`CodegenLLM`) as a new `Agent` subclass alongside `BaselineLLM`, with a sandboxed Python executor for running model-generated candidate programs against training pairs. Wire it into the existing CLI / runner / scoring stack from Phase 2. Produce a recorded AGI-2 eval score for the new agent and compare against the three published reference points (Phase 2 pure-LLM baseline, Greenblatt 50% on AGI-1, NVARC 24% on AGI-2).
**Why:** Phase 3's ADR (`docs/decision_log.md`, "Phase 4 will implement LLM-driven Python program induction") picked this family explicitly because code execution lets the agent verify hypotheses against training pairs — exactly the capability AGI-2 stresses — and the approach drops into our existing harness without infrastructure investment.
**Depends on:** Phase 3 (`agi2-approach`, complete) for the family pick; Phase 2 (`agi2-baseline`, harness complete; recorded number deferred) for the scoring/runner/cost-ceiling/pricing infrastructure. **The Phase 3 ADR's "run Phase 2 baseline before Phase 4" gating was amended in `docs/decision_log.md` (entry "Amend Phase 4 ADR gate — gate impl start, not plan approval") so this plan can be reviewed on design merits, with the baseline run becoming the impl cycle's first deliverable.**

## Scope

### In Scope
- **`src/arcsolver/agi2/agents/codegen_llm.py` (new):**
  - Class `CodegenLLM(Agent)` exposing the same `Agent` protocol as `BaselineLLM`.
  - Prompt: cache-controlled system block (reusable across calls) explaining the contract: write a Python function `def solve(grid: list[list[int]]) -> list[list[int]]`. User block gives the training pairs.
  - Sampling: configurable `n_samples` (default `3` for v0). Independent completions at `temperature=0.8` per sample. Each call's usage tracked in `CallUsage` the same as `BaselineLLM`.
  - Candidate evaluation: for each sampled program, run it on all training pairs via the sandboxed executor. Score = number of training pairs the program produces the expected output for.
  - Test-time inference: pick the candidate with the highest training-pair score (ties broken by first-seen); run that candidate on the test input(s). Each test input gets two attempts: (1) the best candidate's output, (2) the second-best candidate's output. If only one candidate compiles+runs, attempt 2 is `Attempt(grid=None, parse_error="only one viable candidate")`.
  - Per-task report includes: which candidate was picked, its training-pair score (e.g. 3/3, 2/3, 0/3), and the raw program text (for debuggability). These ride in a **typed `CodegenRunDetails` structure** carried on a new optional field of `AgentTaskRun` — see "Reporting shape" below. They explicitly do *not* ride on `AgentTaskRun.calls`, which stays scoped to API usage records.

- **`src/arcsolver/agi2/sandbox.py` (new — the sandboxed Python executor):**
  - `run_candidate(source: str, grid_in: Grid, *, timeout_s: float, memory_mb: int) -> SandboxResult` runs the candidate's `solve()` in a fresh **subprocess** (not `exec()`).
  - `SandboxResult` carries: `grid_out` (or None), `status` (`"ok"` / `"timeout"` / `"crashed"` / `"syntax_error"` / `"import_blocked"` / `"builtin_blocked"` / `"output_invalid"`), `error_message`, `wall_time_s`.
  - The subprocess uses `resource.setrlimit` (Unix) for `RLIMIT_CPU`, `RLIMIT_AS` (memory), and `RLIMIT_NOFILE` (files).
  - **Pre-execution AST allowlist** parses the source with `ast.parse` and rejects, with status `"import_blocked"` / `"builtin_blocked"`:
    - any `Import`/`ImportFrom` whose top-level module isn't in `{"math", "itertools", "functools", "collections", "copy"}`;
    - any `Name`/`Attribute` reference to a denied builtin in `{"open", "eval", "exec", "compile", "input", "breakpoint", "__import__", "globals", "locals", "vars", "exit", "quit"}`. The deny-list catches the easy accidental cases; the restricted-builtins step below catches them at runtime too.
  - **Restricted `__builtins__` in the subprocess.** When the runner script in the subprocess executes the candidate, it does so against a *small allowlisted `__builtins__` dict* (e.g. `{"len", "range", "enumerate", "zip", "map", "filter", "list", "tuple", "dict", "set", "frozenset", "str", "int", "float", "bool", "abs", "min", "max", "sum", "any", "all", "sorted", "reversed", "isinstance", "type", "True", "False", "None", "print"}`). Anything the candidate reaches for outside that dict raises `NameError`, which the subprocess catches and reports as `status="builtin_blocked"`. This is the layer that actually prevents `open()` / `__import__()` / `eval()` at runtime — the AST step is the fast no-op rejection; restricted `__builtins__` is the runtime backstop.
  - Wall-clock timeout via `subprocess.run(timeout=...)`.
  - **Threat model (documented):** this sandbox aims to make accidental file/process/network access hard in practice for benign-but-weird model-generated code. It is not security-grade — a determined adversarial program could escape via bytecode hacks, frame inspection, or other tricks. We are running our own machine, with a model we trust, against a public benchmark; the threat model is "Claude wrote weird code", not "Claude wrote malware." We document this so future maintainers don't mistake this for a real sandbox.
  - **Tests: at minimum one assertion per non-`ok` status value.** Including: candidate that tries `import os` (`import_blocked`), candidate that tries `open("/etc/passwd")` (`builtin_blocked`), candidate that tries `eval("...")` (`builtin_blocked`), candidate with an infinite loop (`timeout`), candidate raising `ZeroDivisionError` (`crashed`), candidate that returns a non-grid value (`output_invalid`), candidate with a syntax error (`syntax_error`), happy-path candidate (`ok`).

- **`src/arcsolver/agi2/agents/codegen_llm.py` integration:**
  - The agent constructs `SandboxResult`s for each candidate-on-training-pair execution.
  - On total failure (no candidate compiles or runs), the agent returns `Attempt(grid=None, parse_error=<reason>)` per test input, which scores as wrong.

- **Reporting shape (typed, not dict):**
  - Add three new dataclasses to `src/arcsolver/agi2/agents/base.py` (or a new `src/arcsolver/agi2/agents/codegen_details.py` if codex prefers physical separation):
    - `CodegenCandidate(source: str, train_pair_score: int, train_pair_total: int, sandbox_status: str, sandbox_error: str | None)`
    - `CodegenTestRun(test_index: int, selected_candidate_index: int | None, attempt_train_score_pairs: list[int])` — records, per test input, which candidate was used for attempt 1 and attempt 2.
    - `CodegenRunDetails(candidates: list[CodegenCandidate], per_test: list[CodegenTestRun])`
  - Add `extras: CodegenRunDetails | None = None` (default `None`) to `AgentTaskRun`. `BaselineLLM` leaves it `None`; `CodegenLLM` populates it.
  - Runner: when `extras` is non-`None`, serialize it as a sibling JSON blob in the result directory (`codegen_details.jsonl`, one record per task), so the raw API-usage stream in `raw_responses.jsonl` stays clean.
  - `summary.json` for codegen runs adds three aggregate fields: `candidates_per_task_mean`, `tasks_with_any_passing_candidate`, `tasks_with_all_train_pairs_passed_by_best`. These are the per-run diagnostics the Phase 4 results decision-log entry will reference.
  - Tests assert that `BaselineLLM` runs do not write `codegen_details.jsonl` and that `CodegenLLM` runs do.

- **CLI wiring (`src/arcsolver/agi2/__main__.py`):**
  - Extend `--agent` choices to include `codegen_llm`.
  - Add `--n-samples N` (default 3) and `--candidate-timeout-s F` (default 5.0) and `--candidate-memory-mb N` (default 256). These are codegen-specific but accepted globally (ignored by baseline_llm).

- **Tests (`tests/agi2/`):**
  - `test_sandbox.py` — pure executor tests with synthetic Python source strings. Covers each status. **No real LLM calls.**
  - `test_codegen_llm.py` — agent unit tests with the Anthropic SDK mocked, and the sandbox either mocked or used with deliberately-safe inline source strings. Covers: pick-best-by-train-score, parse-fail-on-all-candidates produces wrong attempts, ties resolved deterministically.
  - `test_runner.py` — extend with a case that exercises `codegen_llm` end-to-end via the runner with both the SDK and the sandbox stubbed.

- **`docs/decision_log.md`:** append two new entries when this phase completes — the deferred Phase 2 baseline result (after we run it; see Open Question 1) and a Phase 4 results entry capturing the codegen v0 score, cost, and comparison to the three reference points.

- **`README.md`:** short paragraph documenting `just eval --agent codegen_llm`.

- **`justfile`:** add an `eval-codegen` recipe with sensible defaults.

### Out of Scope
- Revision / retry-on-failure prompting (Greenblatt-style "show the model what failed and ask for a fix"). This is a clear v0+1 follow-up — note it in the Phase 4 results decision-log entry as the next direction if codegen is competitive.
- Multiple text representations / spreadsheet notation / connected-component features from the Greenblatt writeup. v0 ships plain grid-as-JSON; richer representations are v0+N.
- Majority voting across many candidates (Greenblatt used thousands; we use single-digit). Out of scope for v0.
- Test-time training, diffusion LMs, or any custom-architecture work. Already decided in Phase 3 ADR as Phase 5+ options.
- ARC-AGI-3 (Phases 6+).
- Kaggle submission packaging (Phase 5).

## Technical Approach

- **Sandbox via subprocess, not `exec()`.** `exec()` shares state with the parent process; a runaway loop or `os.system` call would block / damage the runner. Subprocess + `resource.setrlimit` + `subprocess.run(timeout=...)` is the standard pattern and gives us memory + CPU + wall-clock containment. Subprocess overhead is ~50-100ms per candidate-on-pair call; with 3 candidates × 3-5 training pairs that's ~0.5-1.5s of sandbox overhead per task. Acceptable.
- **AST import-allowlist before subprocess launch.** Catches the easy cases (`import os`) without paying subprocess cost. Will not catch obfuscated imports (`getattr(__builtins__, '__import__')(...)`), but our threat model is "Claude wrote weird code", not adversarial.
- **Prompt design.** Single cache-controlled system block (cached across calls) + per-task user message. System block specifies the function signature, the grid encoding, and that the function must return only a grid (no `print`, no I/O). Asks for the function body only, with no markdown fences and no preamble. Parser strips fences and pulls out the first `def solve(...)` block.
- **Sample budget.** v0 default is `n_samples=3` per task. Cost estimate on Opus 4.7 with caching: ~$0.30-0.50/task at v0 budget; for 30 tasks that's $9-15, comparable to Phase 2's projected baseline. Knob is exposed; later phases can scale up.
- **Test attempts:** the agent gets up to 2 attempts per test input (Kaggle rule). We use the *two best candidates by training-pair score*. This is intentionally different from "two independent completions of the same prompt" — it leverages the program-induction structure (some candidates are demonstrably better on training pairs than others).
- **Cost accounting:** sandbox CPU time is *not* a billed quantity. Cost reporting reuses Phase 2's `pricing.py`. The runner's `--max-cost-usd` ceiling applies to API spend only; sandbox compute is bounded by `--candidate-timeout-s` and `--candidate-memory-mb`.
- **Failure-mode legibility (key property from the ADR):** when no sampled candidate matches any training pair, the per-task report records each candidate's source + status + best train-pair score. We can run a follow-up analysis pass to characterize where codegen v0 fails systematically.

## Files to Create/Modify
- `src/arcsolver/agi2/agents/codegen_llm.py` — new
- `src/arcsolver/agi2/sandbox.py` — new
- `src/arcsolver/agi2/__main__.py` — extend `--agent` choices + new flags
- `src/arcsolver/agi2/agents/base.py` — add typed `CodegenCandidate`, `CodegenTestRun`, `CodegenRunDetails` dataclasses and optional `extras: CodegenRunDetails | None` field on `AgentTaskRun`
- `src/arcsolver/agi2/runner.py` — write `codegen_details.jsonl` alongside `raw_responses.jsonl` when `extras` is populated; add three codegen-aggregate fields to `summary.json`
- `tests/agi2/test_sandbox.py` — new
- `tests/agi2/test_codegen_llm.py` — new
- `tests/agi2/test_runner.py` — extend with one end-to-end codegen path
- `justfile` — `eval-codegen` recipe
- `README.md` — codegen agent paragraph
- `docs/decision_log.md` — append Phase 2 baseline result entry + Phase 4 results entry (at impl time)

## Success Criteria
- [ ] `just check` (lint + mypy --strict + pytest) passes from a clean clone.
- [ ] `tests/agi2/test_sandbox.py` covers each `SandboxResult.status` value (`ok` / `timeout` / `crashed` / `syntax_error` / `import_blocked` / `builtin_blocked` / `output_invalid`). The `builtin_blocked` test case includes at least one assertion each for `open(...)` and `eval(...)` source. No real LLM calls.
- [ ] `tests/agi2/test_codegen_llm.py` covers: pick-best-by-train-score, all-candidates-fail produces wrong attempts (not exceptions), deterministic tie-breaking. SDK fully mocked.
- [ ] `python -m arcsolver.agi2 eval --agent codegen_llm --split evaluation --limit 3 --max-cost-usd 1 --n-samples 3` runs end-to-end against the live Anthropic API and produces a valid `summary.json` whose `agent` field is `codegen_llm`. Behind `just eval-codegen-smoke`; NOT part of `just check`. (Marked deferred at impl-submit time if the human waives — same precedent as Phase 2.)
- [ ] **Before impl is submitted for review, two decision-log entries are appended**:
  1. The deferred Phase 2 baseline result (or an explicit "still deferred" waiver entry — see Open Question 1).
  2. A Phase 4 results entry comparing the codegen v0 score to the three published reference points (Phase 2 pure-LLM number when known, Greenblatt 50% AGI-1, NVARC 24% AGI-2). The entry explicitly states what the next-direction call is (more samples / Greenblatt-style revision loop / pivot to TTT).
- [ ] mypy --strict clean across the new modules.
- [ ] No mutations to `pricing.py` (Phase 4 doesn't change the pricing table).

## Open Questions

**Resolved in Round 2 (Phase 4 plan):**
- **ADR gate.** Amended in `docs/decision_log.md` entry "Amend Phase 4 ADR gate — gate impl start, not plan approval". Plan now approvable on design merits; impl cycle's first deliverable is the baseline run.
- **Sample budget v0 default:** `n_samples=3`. Codex accepted.
- **Sandbox memory limit:** 256 MB. Codex accepted.
- **Reporting shape:** typed `CodegenRunDetails` dataclass on `AgentTaskRun.extras`, written to a sibling `codegen_details.jsonl`. Not a `dict[str, Any]`.

**Open going into impl:**
- None blocking. Implementation-time micro-decisions (exact subprocess interface, exact builtin allowlist contents, exact aggregate field names in `summary.json`) are lead's call within the constraints above; reviewer will challenge during impl review if anything is off.

## Risks
- **Sandbox escape via obfuscated builtins or bytecode tricks.** Mitigation: layered defense — AST allow-list catches the obvious cases at parse time (`import os`, `open(...)`), restricted `__builtins__` catches them again at runtime, and `resource.setrlimit` bounds the worst-case blast radius (CPU / memory / file descriptors). Documented threat model: this sandbox aims at "Claude wrote weird code that shouldn't touch the filesystem," not "Claude wrote malware." Adversarial bytecode injection is explicitly out of scope.
- **Sandbox compute cost.** Subprocess + rlimit + AST walk per candidate is non-trivial. Mitigation: the v0 sample budget is small (3-5); the math says <2s sandbox overhead per task. Tests assert wall-clock budgets on the sandbox path.
- **Cost overrun.** Mitigation: reuse Phase 2's `--max-cost-usd` ceiling unchanged. With `n_samples=3` and 30 tasks, projected cost is $9-15 — well below the existing $15 default ceiling. Tests confirm the runner aborts cleanly if exceeded.
- **Codegen v0 underperforms Phase 2 baseline.** Possible — codegen requires the model to produce a working Python program, which is a stronger demand than producing a grid directly. Mitigation: the Phase 4 results decision-log entry must compare against the Phase 2 baseline and *explicitly state the call to action* if codegen v0 doesn't beat it (likely: bump samples; if still no improvement, the ADR's "Phase 5 = reproduce NVARC" option becomes more attractive).
- **Anthropic API or model deprecation between Phase 4 plan-review and impl-review.** Mitigation: `pricing.py` already supports multiple models; the default is a single constant, easy to flip.
- **Subprocess + rlimits on macOS is less robust than Linux.** Mitigation: documented in the sandbox module docstring; tests still assert behavior on whatever platform `just test` runs on, but we don't claim full parity across platforms. CI (Phase 5+) will validate on Linux.
