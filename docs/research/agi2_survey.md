# ARC-AGI Approach Survey

**Cutoff date for sources:** 2026-05-15. **Author:** lead (claude). **Scope:** prior art relevant to Phase 4 (`agi2-solver`) of this project — what approaches have other people tried on ARC-AGI-1 and (where available) ARC-AGI-2, what scores did they reach, and what does each cost.

This survey backs the ADR in `docs/decision_log.md`. It is deliberately not exhaustive — it covers the families that show up repeatedly in prize write-ups and that we could realistically reproduce in our toolchain.

## Headline context

- **ARC-AGI-2 is materially harder than ARC-AGI-1.** Per the ARC Prize team's launch material, "none of the leading AI models have surpassed a 5% success rate on ARC-AGI-2 tasks, whereas comparable models routinely achieve between 20% and 50% on ARC-AGI-1." The benchmark targets symbolic interpretation, compositional reasoning, and context-dependent rule application — properties that DSL-brute-force was known to exploit in AGI-1 and that AGI-2 deliberately reduces. (Source: https://arcprize.org/blog/arc-agi-2-technical-report; arXiv 2505.11831.)
- **ARC Prize 2026 has a $2M purse across 3 tracks.** Kaggle hosts the active competitions (ARC-AGI-2, ARC-AGI-3). The leaderboard shows "only systems which required less than $10,000 to run" — compute-unbounded approaches like OpenAI's o3 demonstration (75.7% / 87.5% on AGI-1 semi-private/public eval) are excluded from prize eligibility but useful as ceilings. (Source: https://arcprize.org/leaderboard, https://arcprize.org/blog/oai-o3-pub-breakthrough.)
- **Open-source/published winning scores on ARC-AGI-1 (private eval) sit around 50%.** Best published scores on ARC-AGI-2 are in low single digits at survey time.

---

## 1. Pure-LLM transduction (prompt → grid)

**What:** Single LLM call per task. Prompt contains training examples + test input; model returns the predicted output grid. No code execution, no fine-tuning, no search. This is exactly what our Phase 2 `BaselineLLM` does.

**Reported performance:**
- ARC-AGI-1: GPT-4o reportedly ~5% on test set (per Greenblatt's writeup baseline); frontier reasoning models (o-series, claude with thinking) reach 20-30% with care. (Source: https://blog.redwoodresearch.org/p/getting-50-sota-on-arc-agi-with-gpt.)
- ARC-AGI-2: per ARC Prize team, <5% across all frontier models at AGI-2 launch.

**Cost / compute:** Cheapest of all approaches. One forward pass per attempt; with 2 attempts per test input, ~3 calls per task on average. Our recorded baseline (deferred) was projected at ~$5-7 for 30 tasks on Opus 4.7.

**Tradeoffs:**
- ✅ Trivial to implement (already done in Phase 2).
- ✅ Cheap; no GPU infra.
- ❌ Low ceiling, especially on ARC-AGI-2. Cannot test hypotheses by running code; cannot verify proposed transformations against training pairs.
- ❌ Pure transduction has been outperformed by every code-executing / search-based approach in the 2024 Kaggle competition.

---

## 2. LLM-driven program induction with Python execution (Greenblatt 2024)

**What:** LLM generates thousands of candidate Python programs that attempt the transformation. Each program is executed against the task's training pairs. Programs that solve all training pairs are kept; ties broken by majority vote on the test input. (Source: https://blog.redwoodresearch.org/p/getting-50-sota-on-arc-agi-with-gpt.)

**Implementation specifics from the writeup:**
- Model: GPT-4o.
- Sample count: ~8,000 per problem (~5,000 initial completions + ~3,000 revision attempts on the top 12 implementations).
- Prompting: image + multiple text representations (spreadsheet, connected-component notation, input/output diffs); separate prompts for size-changing vs size-preserving tasks.
- Revision: when no implementation passes all training pairs, show the model the failing output vs expected and ask for a fix.

**Reported performance:**
- ARC-AGI-1: 50% on a 100-problem public-test subset; 72% on training subset (used as a held-out validation). Prior SOTA at the time was ~34%.
- ARC-AGI-2: not reported.

**Cost / compute:** Author explicitly notes "1000x more runtime compute" than prior work and that the approach is "ineligible for the ARC-AGI prize" due to compute. With 8,000 samples per task at GPT-4o pricing (then ~$2.50/M input + $10/M output), a back-of-envelope estimate is ~$50-150 per task → $5,000-15,000 for a 100-task run. Bigger barrier than Phase 1/2 spent.

**Tradeoffs:**
- ✅ Highest published score in the pure-text-LLM family.
- ✅ Reuses our existing harness: the runner already runs an `Agent` per task. A code-execution agent slots in without redesign.
- ✅ Cost is a tunable dial — we can start at 1 sample/task and scale up.
- ⚠️ Cost-blows-up risk; needs strict per-task budget.
- ⚠️ Sandboxing: executing LLM-generated Python on untrusted code is a security risk. Need a subprocess-with-timeout or containerized executor.
- ❌ Not prize-eligible at Greenblatt's compute scale; we'd need a much-cheaper variant to actually win.

---

## 3. DSL program search (icecuber / top-quarks, 2020 winner)

**What:** A hand-built domain-specific language of grid operations (rotate, flip, color swap, flood fill, connected components, ...). Search the space of compositions of these primitives at increasing depth; if any composition matches the training pairs, apply it to the test input. (Source: https://github.com/top-quarks/ARC-solution.)

**Implementation specifics:**
- ~150 hand-coded primitives in the original; later forks have larger and smaller DSLs.
- Depth-bounded search (depth 2 / depth 3); 70 seconds at depth 2 on the author's machine, ~9 hours for the full test set at full depth.

**Reported performance:**
- ARC-AGI-1: 129/419 (~31%) on public eval at depth 2 per the repo README; the 2020 private-eval win was ~21% (the competition was harder; the winner only just edged out a 0% baseline).
- ARC-AGI-2: not reported. The ARC Prize team explicitly designed AGI-2 to reduce DSL-brute-forceability, so the expected ceiling is lower than on AGI-1.

**Cost / compute:** Effectively free per run (CPU only, hours not days). No LLM cost.

**Tradeoffs:**
- ✅ Cheapest at inference time.
- ✅ Deterministic and inspectable; we can read the program that solved each task.
- ❌ Massive up-front engineering cost to build and maintain the DSL (months, not days).
- ❌ ARC-AGI-2 was designed to be hard for this family; expected ceiling is poor.
- ❌ Doesn't reuse our existing LLM harness at all.

---

## 4. Test-time training / fine-tuning (Akyurek et al; Barbadillo Kaggle 2024)

**What:** At inference time, take the task's training pairs, expand them with augmentations (rotations / reflections / color permutations), and run a few gradient steps to fine-tune a small base LM on this expanded data. Then sample from the fine-tuned model for the test input. (Source: https://arxiv.org/abs/2411.07279 "The Surprising Effectiveness of Test-Time Training for Abstract Reasoning"; Barbadillo 2024 Kaggle solution https://github.com/ironbar/arc24.)

**Implementation specifics:**
- Base model: 8B-parameter LM (Akyurek et al). LoRA-style updates per task.
- Augmentation: rotation/reflection/color permutation expansion of the few training pairs.
- Inference: fine-tune for N steps on the per-task augmented set, then sample completions.

**Reported performance:**
- ARC-AGI-1 public validation: 53.0% with the 8B LM + TTT alone; 61.9% when ensembled with program-synthesis methods, matching "average human performance."
- ARC Prize 2024 (private eval): Barbadillo's TTT-based solution placed 2nd at 40%.
- ARC-AGI-2: not reported in the surveyed sources.

**Cost / compute:** GPU-heavy. Fine-tuning even a small LM per task takes minutes of GPU time × N tasks. Inference dollars are low (no API), but capex for GPUs is non-zero. The published Kaggle solutions all run within the $10k compute envelope.

**Tradeoffs:**
- ✅ Highest published open-source-friendly score on ARC-AGI-1.
- ✅ Prize-eligible (within $10k compute).
- ❌ Requires GPU infrastructure we don't have wired up. Phase 1's stack is Python + uv + an Anthropic API key — no model training pipeline, no GPU access.
- ❌ Material implementation effort: dataset augmentation, LoRA setup, per-task fine-tune loop, model serving.
- ❌ The "matches average human performance" claim is on ARC-AGI-1, not AGI-2.

---

## 5. Induction + Transduction combined (Li et al 2024)

**What:** Combine inductive program synthesis (LLM generates Python programs) with transduction (neural net outputs grid directly). The hybrid uses each approach's strengths on the tasks it's better at, with a routing/voting mechanism between them. (Source: https://arxiv.org/abs/2411.02272 "Combining Induction and Transduction for Abstract Reasoning".)

**Implementation specifics:** Not extracted in detail from the abstract. The Akyurek/Hodel TTT paper's 61.9% number came specifically from ensembling TTT (transduction) with program synthesis (induction), so the families' complementarity is well-attested.

**Reported performance:**
- ARC-AGI-1: 61.9% public val for the TTT+induction ensemble; comparable numbers from Li et al.
- ARC-AGI-2: not reported.

**Tradeoffs:**
- ✅ Highest measurable score family.
- ❌ Strict superset of two other families' complexity — has to implement both before the ensemble pays off.
- ❌ Implausible as a Phase 4 first attempt; more natural as a Phase 4+1 "combine the previous two" move.

---

## 6. Frontier reasoning models (OpenAI o3 / Anthropic with extended thinking)

**What:** Run the task on a frontier reasoning model that internally does extended chain-of-thought + tool use. Treat the model as a black box. (Source: https://arcprize.org/blog/oai-o3-pub-breakthrough.)

**Reported performance:**
- ARC-AGI-1 (o3): 75.7% on semi-private eval (high-efficiency mode); 87.5% on semi-private eval (low-efficiency mode); 91.5% on public eval. ARC Prize team interpretation: "deep learning-guided program search."
- ARC-AGI-2: ARC Prize team estimate is "under 30%" for o3 vs >95% for humans.

**Cost / compute:** Public reporting is sparse but compute costs are reportedly in the thousands-of-dollars-per-task range in low-efficiency mode. Prize-ineligible at that scale.

**Tradeoffs:**
- ✅ Highest absolute ceiling we know about today.
- ❌ Compute cost is the dealbreaker.
- ❌ Treats the most interesting problem (how to actually solve ARC) as a black box; nothing to improve on.
- ⚠️ Useful as a *reference ceiling*: "the best ARC solver we know about scores 75-90% on AGI-1; we're not going to beat o3 with our toolchain, but the gap shows headroom exists."

---

## Cross-cutting observations

- **The 2024 Kaggle winners' family was diverse:** ARChitects (LLM perspective methods, 53.5%), Barbadillo (TTT, 40%), and several induction-based teams. No single family dominated; the winning teams mixed techniques.
- **Code execution is a force multiplier.** Every approach with measurable >40% score on AGI-1 either runs LLM-generated code or runs a hand-built program (DSL search). Pure transduction without code execution caps out around 5-30%.
- **AGI-2 is essentially open.** No surveyed approach has reported a meaningful AGI-2 number (the 5% ceiling for frontier models is the public reference point). Phase 4's job is partly to *generate* that number for whatever family we pick.
- **No baseline number from us yet.** Phase 2 produced the harness but not the recorded score. The ADR must handle this.

## Closed-source / unreproducible references

These are cited so we know they exist, but we can't reproduce them as-is:
- OpenAI o3 demonstration on ARC-AGI-1 (no released code).
- Anthropic's internal eval numbers (no released ARC-specific solution).
- ARC Prize 2025/2026 Kaggle private submissions still under embargo at survey time.
