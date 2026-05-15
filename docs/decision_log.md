# Decision Log

This log tracks important decisions made during the project.

<!-- Add new decisions at the top in reverse chronological order -->

---

## 2026-05-15: Phase 4 will implement LLM-driven Python program induction (Greenblatt-style, cost-tuned)

**Decision:** Phase 4 (`agi2-solver`) implements a new agent family alongside `baseline_llm`: an LLM-driven **program-induction agent** that asks Claude to write a Python `solve(grid) -> grid` function for each task, executes the candidate against the training pairs in a sandboxed subprocess, retries on failure up to a sample budget, and returns the candidate's output on the test inputs as its attempt. The Phase 4 v0 is **deliberately cost-tuned**: small default sample count (e.g. 3 attempts/task), strict `--max-cost-usd` ceiling reused from Phase 2, and an explicit per-task wall-clock timeout on the sandboxed executor. Later iterations can scale samples up the cost curve, but v0 must produce a measurable score within the same single-digit-dollar budget as Phase 2's planned baseline.

**Context:** The Phase 3 survey at `docs/research/agi2_survey.md` covers six approach families. We picked one for Phase 4.

**Alternatives Considered:**
The five tradeoff axes from the Phase 3 plan, scored across the six surveyed families. Lower scores below mean "worse fit for Phase 4 right now":

| Family | Expected ARC-AGI-2 ceiling | Cost per eval run | Fit with our harness | Effort to v0 (person-days) | Failure mode legibility |
|---|---|---|---|---|---|
| 1. Pure-LLM transduction | <5% (already known) | $5-15 | ✅ already built | 0 (done in Phase 2) | trivial — wrong grid |
| **2. LLM + Python codegen (Greenblatt)** | **moderate (5-15%?)** | **$5-50 tunable** | **✅ slot-in agent** | **~3-5** | **legible (program fails on training pairs)** |
| 3. DSL program search (icecuber) | low (AGI-2 designed against this) | ~free CPU | ❌ full rewrite | 30+ (build the DSL) | legible but exhaustive |
| 4. Test-time training (Hodel/Barbadillo) | unknown; high on AGI-1 | ~free $, GPU capex | ❌ need GPU pipeline | 7-14 + GPU infra | hard (overfit / collapse) |
| 5. Induction + Transduction ensemble | highest measured (61.9% AGI-1) | sum of (2)+(4) | ❌ both above | 14+ | hardest |
| 6. Frontier reasoning model (o3, etc.) | <30% (estimated) | $1000s/task | ✅ but pointless | 0 | n/a — black box |

**Rationale (the five tradeoff axes, in detail):**
1. **Expected score ceiling on ARC-AGI-2.** No family has a measured AGI-2 number; we are picking on AGI-1 evidence and AGI-2's structural changes. Greenblatt-style codegen scored 50% on AGI-1 public eval — the second-highest open-source ceiling we found. AGI-2 likely halves or worse that on the public eval, but code execution lets the agent verify hypotheses against training pairs, which is exactly the capability AGI-2 stresses (compositional rule application). We won't beat o3, but we don't need to — Kaggle prize eligibility requires <$10k compute, which excludes o3 and gives our family room.
2. **Cost per eval run.** The Greenblatt result used ~8,000 samples/task, which we cannot afford. But the same algorithm at 3-5 samples/task is well under our existing $15 ceiling — and crucially, the *sample count is a knob*. We start cheap, measure, and scale up only if the cost vs score trade looks favorable. Compare with TTT, where the cost is GPU capex we don't have.
3. **Fit with existing harness.** Codegen is a drop-in `Agent` subclass next to `BaselineLLM`. Reuses the runner, scoring, pricing, JSONL writer, and cost-ceiling logic from Phase 2 verbatim. The only new piece is a sandboxed Python executor. By contrast, DSL search and TTT both require infrastructure (DSL engine; GPU + fine-tune loop) that does not exist in this repo.
4. **Implementation effort.** ~3-5 person-days to a v0: prompt template (1d), sandboxed executor (1-2d), tests (1d), wire-up + first eval run (1d). Compare TTT (7-14 days *after* GPU access), DSL (30+ days to a real DSL).
5. **Failure mode legibility.** When a codegen attempt fails, we have a Python program in hand that demonstrably did not match the training pairs. That's a debuggable artifact, unlike a low transduction score where we don't know whether the model misunderstood the task or just sampled poorly. The legibility property is itself useful for Phase 3-to-Phase 4 hand-off: if codegen fails systematically on a class of tasks, we know what the next research move should be.

**Why not the alternatives:**
- Pure-LLM (1) is Phase 2's contribution; doesn't make sense to redo it as Phase 4.
- DSL (3) is on the wrong side of the AGI-2 design change. The ARC Prize team's own framing of AGI-2 ("less brute-forcible") rules this out as a Phase 4 v0.
- TTT (4) is the strongest candidate by score, but the infrastructure cost (GPUs, fine-tune loop) is prohibitive for our toolchain right now. **We don't drop this — it's the natural Phase 4+N follow-up once codegen plateaus and we have evidence the marginal cost is worth it.**
- Induction+Transduction (5) is a Phase 5+ move that combines (2) + (4). Premature today.
- Frontier (6) ineligible.

**No-baseline-yet handling (this is a required choice per the Phase 3 plan):**
Both (a) and (b) from the plan apply:
- **(a) Make running the deferred Phase 2 baseline a Phase 4 entry criterion.** Phase 4's plan will list "run `just eval --limit 30 --max-cost-usd 10` and record the result in this decision log" as the first step before any codegen code is written. That gives us a real same-machine, same-eval-set comparison.
- **(b) Adopt Greenblatt's 50% ARC-AGI-1 public-eval score as the published reference ceiling** for our chosen family. Phase 4 success criteria will explicitly compare against this number (with a caveat that our split is AGI-2 not AGI-1, so the absolute target is lower; the comparison is "are we in the same family as the published number, or have we systematically underbuilt the approach").

**Decided By:** Lead (claude), pending reviewer (codex) approval in the Phase 3 plan cycle. Human (jackblacketter) has direction-set authority over the overall pick.

**Phase:** agi2-approach

**Follow-ups:**
- **Before Phase 4 starts:** run `just eval --limit 30 --max-cost-usd 10 --agent baseline_llm --split evaluation`. Record the result (score, cost, result-dir path) as a new entry in this decision log. Phase 4 plan cannot be approved without that entry, per (a) above.
- **Phase 4 plan must include:** a sandboxed Python executor design (subprocess + ulimits / restricted import list / wall-clock timeout — not raw `exec()`); a sample-budget knob; cost-ceiling reuse from Phase 2; the published-reference comparison.
- **Phase 4+N option (NOT scope for Phase 4):** test-time training as a follow-on if Phase 4's codegen approach plateaus and we have GPU access.
- **Closed door:** DSL search and frontier-model-only approaches are NOT Phase 4 candidates; revisit only if Phase 4 + follow-on both underperform.

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
