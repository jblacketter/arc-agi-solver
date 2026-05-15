# Decision Log

This log tracks important decisions made during the project.

<!-- Add new decisions at the top in reverse chronological order -->

---

## 2026-05-15: Amend Phase 4 ADR gate — gate impl start, not plan approval

**Decision:** Amend the previous Phase 4 ADR. The gating clause "Phase 4 plan cannot be approved without that entry" is replaced with: **"Phase 4 implementation start cannot begin without that entry. The Phase 4 *plan* may be reviewed and approved on its design merits; the impl cycle's first deliverable is to run `just eval --limit 30 --max-cost-usd 10 --agent baseline_llm --split evaluation` and append the result entry to this decision log, before any new code is written under `src/arcsolver/agi2/agents/codegen_llm.py` or `src/arcsolver/agi2/sandbox.py`."**

**Context:** The earlier ADR's gate at plan-approval time is in tension with how plan vs impl review actually work in this project: a plan is design+rationale, an impl is the code+tests+evidence. Gating the design review on a measurement makes the workflow brittle (you can't even discuss the design until you spend money). Codex's Phase 4 plan-review correctly flagged that the original wording could not be overridden by reviewer interpretation — so this entry makes the change explicit instead.

**Alternatives Considered:**
- Keep the original gate: would force a baseline run before Phase 4 design discussion, which is exactly the workflow brittleness above.
- Drop the gate entirely: would lose the "must have a real number before we ship code" property, which is the whole point of the gate.
- Move the gate to impl start (chosen): preserves the property, enables design review without forcing premature spend.

**Rationale:** A plan that hand-waves "we'll measure later" is the failure mode the gate exists to prevent. Tying the gate to impl-start, not plan-approval, prevents that without blocking design conversations.

**Decided By:** Human (jackblacketter) authorized "Start Phase 4 planning despite the gating (zero cost)" in this session; lead (claude) formalizing as an ADR amendment; reviewer (codex) requested the formal amendment in Phase 4 plan-review Round 1.

**Phase:** agi2-solver (amends the previous agi2-approach ADR)

**Follow-ups:**
- Phase 4 plan can be approved on design merits per this amended gate.
- Phase 4 impl Round 1 must start by running the baseline and appending its result to this log. If the human waives the live run a second time, an explicit waiver entry is appended (same precedent as the existing "Defer the live ARC-AGI-2 baseline run" entry below).
- The original ADR's text is preserved for audit (not retroactively edited); this amendment supersedes it.

---

## 2026-05-15: Phase 4 will implement LLM-driven Python program induction (Greenblatt-style, cost-tuned)

**Decision:** Phase 4 (`agi2-solver`) implements a new agent family alongside `baseline_llm`: an LLM-driven **program-induction agent** that asks Claude to write a Python `solve(grid) -> grid` function for each task, executes the candidate against the training pairs in a sandboxed subprocess, retries on failure up to a sample budget, and returns the candidate's output on the test inputs as its attempt. The Phase 4 v0 is **deliberately cost-tuned**: small default sample count (e.g. 3 attempts/task), strict `--max-cost-usd` ceiling reused from Phase 2, and an explicit per-task wall-clock timeout on the sandboxed executor. Later iterations can scale samples up the cost curve, but v0 must produce a measurable score within the same single-digit-dollar budget as Phase 2's planned baseline.

**Context:** The Phase 3 survey at `docs/research/agi2_survey.md` covers six approach families with published scores from both ARC Prize 2024 (AGI-1 winners) and ARC Prize 2025 (the first run of the AGI-2 leaderboard, all winners open-source). We picked one for Phase 4.

**Alternatives Considered:**
The five tradeoff axes from the Phase 3 plan, scored across the six surveyed families. The "Expected ARC-AGI-2 ceiling" column now reflects 2025 Kaggle results where available:

| Family | Expected ARC-AGI-2 ceiling | Cost per eval run | Fit with our harness | Effort to v0 (person-days) | Failure mode legibility |
|---|---|---|---|---|---|
| 1. Pure-LLM transduction | <5% (consistent with 2024 launch claims, no 2025 top-5 entry) | $5-15 | ✅ already built | 0 (done in Phase 2) | trivial — wrong grid |
| **2. LLM + Python codegen (Greenblatt-style)** | **unknown on AGI-2; 50% on AGI-1; absent from 2025 top-5** | **$5-50 tunable** | **✅ slot-in agent** | **~3-5** | **legible (program fails on training pairs)** |
| 3. DSL program search (icecuber) | low (AGI-2 designed against this) | ~free CPU | ❌ full rewrite | 30+ (build the DSL) | legible but exhaustive |
| 4. Test-time training (NVARC / MindsAI / Barbadillo) | **measured: 6.5-24.0% on AGI-2 (NVARC 1st)** | ~free $ in Kaggle env; cloud-GPU $ outside it | ❌ need GPU + fine-tune pipeline | 14+ + GPU infra | hard (overfit / collapse) |
| 5. 2D-aware diffusion / custom LM (ARChitects 2025) | **measured: 16.5% on AGI-2 (2nd)** | similar to (4) | ❌❌ entire custom training stack | 30+ + GPU + diffusion expertise | hard (training stability) |
| 6. Frontier reasoning model (o3, etc.) | estimated <30%; ineligible | $1000s/task | ✅ but pointless | 0 | n/a — black box |

**Rationale (the five tradeoff axes, in detail):**

The 2025 leaderboard makes the honest framing of this decision: TTT (NVARC, MindsAI) and custom-architecture LMs (ARChitects-2025 diffusion) are the empirically-winning families on ARC-AGI-2. We are deliberately *not* picking the winning family for Phase 4. Here's why that's the right call for our v0:

1. **Expected score ceiling on ARC-AGI-2.** TTT has a measured ceiling (24.0% NVARC), which codegen does not — codegen was absent from the 2025 top-5. The honest interpretation is that codegen's AGI-2 ceiling is *unknown*, somewhere between the Phase 2 pure-LLM floor (<5%) and the TTT ceiling (24%). That is precisely the information gap Phase 4 should close: produce the first credible measurement of code-execution+verification on AGI-2 with our toolchain. If codegen v0 lands at say 8%, we know whether the cost/effort to climb to NVARC-tier TTT is worth it for us specifically.
2. **Cost per eval run.** The Greenblatt result used ~8,000 samples/task; we cannot afford that. The same algorithm at 3-5 samples/task is within our existing $15 ceiling — and crucially, the *sample count is a knob*. We start cheap, measure, scale up only if the cost-vs-score trade looks favorable. By contrast, TTT inside Kaggle was $0.20/task in their compute envelope; outside Kaggle (where we'd actually run), reproducing it needs cloud GPU access that costs ~$1-3/hr per A100-class device, plus the multi-day fine-tune-pipeline build to use it.
3. **Fit with existing harness.** Codegen is a drop-in `Agent` subclass next to `BaselineLLM`. It reuses the runner, scoring, pricing, JSONL writer, and cost-ceiling logic from Phase 2 verbatim. The only new piece is a sandboxed Python executor. By contrast, TTT (4) and diffusion (5) both require infrastructure (model serving, LoRA training loop, augmentation pipeline, possibly synthetic-data generation) that does not exist in this repo and that would dominate Phase 4 time spent on plumbing rather than on the reasoning problem itself.
4. **Implementation effort.** ~3-5 person-days to a codegen v0: prompt template (1d), sandboxed executor (1-2d), tests (1d), wire-up + first eval run (1d). TTT v0 is 14+ person-days *after* we have GPU access we don't currently have. Reproducing NVARC's specific stack (Qwen3 + Unsloth + LoRA + TRM components + synthetic data) realistically takes 3-6 weeks for someone learning the stack.
5. **Failure mode legibility.** When a codegen attempt fails, we have a Python program in hand that demonstrably did not match the training pairs — a debuggable artifact. By contrast, when a TTT model produces a wrong grid, we have a slightly-fine-tuned LM and not much to inspect. The legibility property matters for *deciding what to do next*: if codegen fails systematically on a class of tasks, that tells us something specific about where the approach struggles, which informs Phase 5+ moves.

**Why not the alternatives, with 2025 evidence factored in:**
- Pure-LLM (1) is Phase 2's contribution; redoing it as Phase 4 makes no sense.
- DSL (3) is on the wrong side of the AGI-2 design change and absent from the 2025 top-5. No live candidate.
- **TTT (4) is the strongest family by measured AGI-2 score, but we do not have the GPU/training infrastructure to start there in v0.** It is the natural Phase 4+N follow-up. NVARC's notebook is open-source, so "reproduce NVARC, then improve" is a viable future path — but it's a Phase 5 or Phase 6 move, not a Phase 4 v0.
- **2D-aware diffusion (5)** requires entirely custom model-training expertise. Out of scope for a small open-source effort in its current shape; revisit only if Phase 4+N TTT proves out and we want to push further.
- Induction+Transduction ensemble: a Phase 6+ move combining codegen (2) + TTT (4). Premature today.
- Frontier (6) ineligible.

**No-baseline-yet handling (this is a required choice per the Phase 3 plan):**
Both (a) and (b) from the plan apply, and (b) is updated with the 2025 numbers:
- **(a) Make running the deferred Phase 2 baseline a Phase 4 entry criterion.** Phase 4's plan will list "run `just eval --limit 30 --max-cost-usd 10` and record the result in this decision log" as the first step before any codegen code is written. That gives us a real same-machine, same-eval-set comparison.
- **(b) Adopt three published reference points** rather than one, given the 2025 data: Greenblatt 50% on AGI-1 public eval (codegen family's high-water mark on the easier benchmark), **NVARC 24.0% on AGI-2 private eval** (the family-agnostic 2025 ceiling we're not trying to beat in v0), and a Phase 2 pure-LLM number once we run it (the floor codegen needs to clear to justify itself). Phase 4 success is "codegen v0 score >> Phase 2 pure-LLM score, with a documented gap to NVARC that informs Phase 5 direction" — not "match NVARC."

**Decided By:** Lead (claude), pending reviewer (codex) approval in the Phase 3 plan cycle. Human (jackblacketter) has direction-set authority over the overall pick.

**Phase:** agi2-approach

**Follow-ups:**
- **Before Phase 4 starts:** run `just eval --limit 30 --max-cost-usd 10 --agent baseline_llm --split evaluation`. Record the result (score, cost, result-dir path) as a new entry in this decision log. Phase 4 plan cannot be approved without that entry, per (a) above.
- **Phase 4 plan must include:** a sandboxed Python executor design (subprocess + ulimits / restricted import list / wall-clock timeout — not raw `exec()`); a sample-budget knob; cost-ceiling reuse from Phase 2; the three-way published-reference comparison (Phase 2 baseline / Greenblatt 50% / NVARC 24%).
- **Phase 5 explicit options (NOT scope for Phase 4):**
  1. **Reproduce NVARC's open-source 2025 Kaggle notebook** as a starting point for our own TTT work. The notebook is at `kaggle.com/code/gregkamradt/arc2-qwen3-unsloth-flash-lora-batch8-queue-trm2`. This becomes a strong option *if* Phase 4 codegen materially underperforms TTT and we acquire GPU access.
  2. **Build TTT from scratch** on top of an open-source small LM (Qwen, Llama, etc.) without the NVARC scaffolding. Higher leverage, much higher cost.
  3. **Stay in the codegen family and scale** sample count / use stronger verifier loops. Cheaper, but bounded by codegen's not-yet-measured AGI-2 ceiling.
- **Closed door:** DSL search and frontier-model-only approaches are NOT Phase 4 candidates; revisit only if Phase 4 + Phase 5 both underperform.

---

## 2026-05-15: Defer the live ARC-AGI-2 baseline run to a later session

**Decision:** Phase 2 (`agi2-baseline`) closes without executing the planned live `eval-smoke` (3 tasks, ~$0.30) and the planned recorded baseline run (`--limit 30` on `evaluation`, ~$5-7 on Opus 4.7). The runner and harness are fully implemented and unit-tested offline; running the live API calls is a one-line operator action (`just eval-smoke` / `just eval`) deferred to a future session.

**Context:** Codex's Phase 2 impl review correctly flagged that the approved plan's success criteria include both a live smoke and a recorded baseline number, and that closing the phase without them needs an explicit human-approved waiver so Phase 3/4 don't assume a baseline number exists.

**Alternatives Considered:**
- Run both live and record the headline number now: clean closure but immediate ~$6 spend before the operator has reviewed the diff.
- Run smoke only ($0.30): partial closure, doesn't actually produce a baseline number.
- Defer both with no waiver: leaves Phase 2 in an ambiguous state.

**Rationale:** Human (jackblacketter) explicitly chose "Skip live calls; submit impl based on offline gate only" when asked in this session. Recording the choice here makes it durable so future sessions and Phase 3/4 plans know there is no baseline number yet — they must either run one or pick a different reference point.

**Decided By:** Human (jackblacketter), surfaced by lead (claude) and confirmed by reviewer (codex) request.

**Phase:** agi2-baseline

**Follow-ups:**
- Before starting Phase 3 (`agi2-approach`): run `just eval --limit 30 --max-cost-usd 10` and record the resulting score/cost/result-dir path here as a new entry. Until that entry exists, Phase 3's ADR must explicitly note that no measured Phase 2 baseline exists yet.

---

## 2026-05-15: Drop planned `--seed` flag from the AGI-2 eval CLI

**Decision:** The CLI implemented by `src/arcsolver/agi2/__main__.py` exposes `--agent`, `--split`, `--limit`, `--all`, `--model`, `--max-cost-usd`, and `--output`. The originally planned `--seed S` flag is intentionally not implemented.

**Context:** The Phase 2 plan listed `[--seed S]` in the CLI surface (alongside `--output PATH`). Codex's impl review flagged the mismatch between the planned and actual CLI. `--output PATH` was added because it's genuinely useful for redirecting result reports.

**Alternatives Considered:**
- Implement `--seed` against the Anthropic API: the Messages API does not expose a determinism seed, and Anthropic does not guarantee determinism even at `temperature=0`. The flag would be misleading.
- Implement `--seed` to control which tasks `--limit` selects: the runner currently uses "first N sorted by filename" rather than random sampling. A seed only matters once we shuffle. We can revisit if/when sampling becomes useful.

**Rationale:** A flag whose only purpose is to satisfy a planning artifact, without affecting observable behavior, is worse than no flag.

**Decided By:** Lead (claude), pending reviewer (codex) sign-off in the Phase 2 impl cycle.

**Phase:** agi2-baseline

**Follow-ups:**
- If we add task shuffling in Phase 3+ (`--shuffle`, sampled subsets), reintroduce `--seed` then with a real binding.

---

## [YYYY-MM-DD]: [Decision Title]

**Decision:** [Clear statement of what was decided]

**Context:** [Why this decision was needed]

**Alternatives Considered:**
- [Option 1]: [Pros/cons]
- [Option 2]: [Pros/cons]

**Rationale:** [Why this option was chosen]

**Decided By:** [{{lead}} / {{reviewer}} / Human / Consensus]

**Phase:** [Which phase this relates to]

**Follow-ups:**
- [Any actions triggered by this decision]
