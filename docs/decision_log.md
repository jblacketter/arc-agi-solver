# Decision Log

This log tracks important decisions made during the project.

<!-- Add new decisions at the top in reverse chronological order -->

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
