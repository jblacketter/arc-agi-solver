# Phase: agi2-approach

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
**What:** Survey the public ARC-AGI-2 (and AGI-1) literature and competition write-ups, characterize the existing families of approaches with their published scores and tradeoffs, then write an ADR in `docs/decision_log.md` selecting the direction Phase 4 (`agi2-solver`) will implement. No code is written or executed in this phase.
**Why:** The roadmap calls Phase 4 the "implement the chosen AGI-2 solver" phase, but "chosen" presupposes a deliberate choice. ARC-AGI is a hard, well-studied benchmark; building a custom approach without first reading the prior art guarantees we re-invent worse versions of things that already exist. One focused research phase now saves rework later.
**Depends on:** Phase 2 (`agi2-baseline`) — the scoring harness from Phase 2 is what we'll use to measure whatever Phase 4 builds. **Phase 2's recorded baseline number was deliberately deferred** (see `docs/decision_log.md`, entry "Defer the live ARC-AGI-2 baseline run"). This phase must either run that baseline first or write the ADR with explicit handling for the "no baseline yet" state.

## Scope

### In Scope
- **Literature/repo survey** at `docs/research/agi2_survey.md`:
  - At least four distinct families of approaches with summary descriptions, primary citation(s), known reported scores on ARC-AGI-1 and (if available) ARC-AGI-2, and a tradeoffs paragraph.
  - Candidate families to cover (minimum):
    1. **Pure-LLM, prompt-only** (single-shot transduction; what our Phase 2 baseline does).
    2. **LLM + Python code execution** (Greenblatt 2024 style: LLM generates many candidate Python programs; each runs on the training pairs; pick one that solves all train pairs).
    3. **Program synthesis over a hand-built DSL** (icecuber / arc-dsl style: enumerate compositions of grid-op primitives).
    4. **Test-time training / test-time fine-tuning** (Hodel et al. style: SFT a small model on the few-shot examples of each task at inference time).
  - Optional families if material is available: neuro-symbolic, transduction transformers, multi-model voting, hybrid approaches.
- **ADR entry in `docs/decision_log.md`** with the standard template fields:
  - Decision: which family Phase 4 will implement first.
  - Alternatives considered (the families surveyed) with their pros/cons.
  - Rationale: cost, compute, expected ceiling, fit with our existing harness, our team's leverage (LLM + Python + uv toolchain), and importantly **how we will measure Phase 4 success in the absence of a Phase 2 baseline number** — e.g. "use the published score for our chosen approach's reference implementation as the target" or "run Phase 2 baseline first as part of Phase 4 entry criteria".
  - Decided By: Lead + Reviewer + Human arbiter.
  - Follow-ups: any Phase 4 entry criteria the ADR creates (e.g. "Phase 4 starts by running the deferred Phase 2 baseline").
- **Update `docs/roadmap.md` Phase 4 entry** so its short description names the chosen family (currently it just says "Implement & tune the chosen AGI-2 solver").

### Out of Scope
- Any implementation work (no DSL primitives written, no LLM-program-search prototype, no fine-tuning). Phase 4 is for that.
- Any live API calls or LLM-driven research. The lead does the research using public-web sources and writes the survey by hand from what is read; the cost of this phase is human/lead time, not API tokens.
- Selecting Phase 5+ approaches.
- ARC-AGI-3 considerations (Phases 6+).

## Technical Approach
- **Research method (zero-cost, web-only):** Lead reads public sources — Anthropic / ARC Prize blog posts, Kaggle competition discussion forums, top-N solution write-ups, the ARC-AGI papers by Chollet, public GitHub repos of past winners, the ARC Prize 2024 retrospective. For each source consulted, the survey notes the URL or repo and the date accessed.
- **Survey format:** flat Markdown, one section per approach family, ~100-300 words each + table of (approach, reported AGI-1 score, reported AGI-2 score, implementation cost estimate in person-days, primary dependency: LLM-API / local-compute / both).
- **Tradeoff axes the ADR must explicitly compare** (so the decision is defensible later):
  1. **Expected score ceiling** on public AGI-2 eval given the published evidence.
  2. **Cost per eval run** in $ (LLM calls) and wall-clock (any local compute / fine-tuning).
  3. **Fit with what we already have** in `src/arcsolver/agi2/` (does this approach reuse the harness, or require a redesign?).
  4. **Implementation effort** in person-days to a measurable v0.
  5. **Failure mode**: what does "this didn't work" look like, and how would we know quickly?
- **"No baseline number yet" handling.** The ADR must explicitly choose one of:
  1. Make running the deferred Phase 2 baseline a Phase 4 entry-criterion (so Phase 4 starts with a real number to beat).
  2. Adopt a published reference score for the chosen approach as the target (and note its source + caveats).
  3. Both.
  This avoids Phase 4 silently inheriting an unmeasured premise.
- **Execution boundary.** No live API calls, no live eval spend, no implementation or prototype execution, and no mutations under `src/`, `tests/`, `scripts/`, or `data/`. Local read/verification commands are allowed and expected: `just check`, `just lint`, `just typecheck`, `just test`, `git diff` / `git log` / `git status`, `rg` / `grep`, and the `tagteam` handoff CLI. The only files this phase writes to are `docs/research/agi2_survey.md`, `docs/decision_log.md`, `docs/roadmap.md`, and `docs/phases/agi2-approach.md` (status checkboxes).

## Files to Create/Modify
- `docs/research/agi2_survey.md` — new (survey contents)
- `docs/decision_log.md` — append ADR for the chosen approach
- `docs/roadmap.md` — Phase 4 description updated to name the chosen family
- `docs/phases/agi2-approach.md` — status checkbox updates as the phase progresses

## Success Criteria
- [ ] `docs/research/agi2_survey.md` exists and covers at least the four candidate families listed in Scope, each with: short description, primary citation/URL, reported AGI-1 score (if available), reported AGI-2 score (if available), tradeoff paragraph.
- [ ] `docs/decision_log.md` has a new ADR entry with: Decision, Context, Alternatives Considered (every surveyed family), Rationale that explicitly addresses each of the five tradeoff axes above, the chosen approach for "no-baseline-yet" handling, Decided By, Phase, Follow-ups.
- [ ] `docs/roadmap.md` Phase 4 description names the chosen approach family in one phrase.
- [ ] No new code files. No live API calls. No mutations under `src/`, `tests/`, `scripts/`, or `data/`.
- [ ] `just check` continues to pass (no regressions to Phases 1-2 work).

## Open Questions
- **Are we committing to one approach for Phase 4, or scoping Phase 4 to compare two?** Lead's default: pick one. Comparing two doubles the Phase 4 cost without doubling the information yield, given how different the approaches are.
- **Should the survey include closed-source / unpublished approaches** (e.g. winning Kaggle submissions whose code isn't released)? Lead's default: cite them with a clear "code unavailable" note so the reader knows the published score is the upper-bound reference, not something we can replicate directly.

## Risks
- **Survey drift** — research phase expands indefinitely. Mitigation: hard limit of one "round" of survey writing per review cycle; if codex requests more sources, add them as a delta, not a rewrite.
- **Picking the popular approach rather than the right one.** Mitigation: the five tradeoff axes are the gate; the ADR has to score every surveyed approach on all five before picking. Just-listing-them is not enough.
- **No measurable baseline.** Already a flagged risk from Phase 2. The ADR's "no-baseline-yet handling" requirement is the mitigation.
- **Stale public information** — ARC Prize 2025 / 2026 may have new approaches not yet widely written up. Mitigation: explicitly include the ARC Prize 2025 retrospective / blog if it exists, and note the cutoff date of the survey at the top of `agi2_survey.md`.
