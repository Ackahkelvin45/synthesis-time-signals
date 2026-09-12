# Experiment matrix

The build spec for the evaluation. Every cell below is (target x condition x
seed x model); one cell = one run producing one row of metrics. The matrix is
tiered so Tier A alone yields a publishable multi-target evaluation and Tier B
adds the causal isolation a journal expects.

---

## Targets (multi-format; from the assignment's library list)

| # | Library | Format | Grammar (grammars-v4) | Status | Notes |
|---|---|---|---|---|---|
| T1 | json-parser | JSON | `json/JSON.g4` | **done** | current target; harness, notes, finding, all evals exist |
| T2 | parson | JSON | `json/JSON.g4` | **done** — `targets/parson/` harness + notes, 3 builds (default/control/roundtrip), transfer verified (classification, baseline, offline loop) | within-format comparison (same grammar, different code); probes auto-flag `duplicate_keys` as a parson-only deviation |
| T3 | inih | INI | `ini/` grammar | to add | flat format: tests that the approach is not JSON-specific |
| T4 | libcsv | CSV | `csv/CSV.g4` | to add | flat, quoting/escaping edge cases |
| T5 | tomlc99 **or** mxml | TOML / XML | `toml/` or `xml/` | to add | one nested non-JSON format; pick whichever grammar + harness is cleaner |

Rationale: two JSON targets give a within-format comparison; INI and CSV are
flat (recursion is not the point there, escaping is); one nested non-JSON
format tests generality of the depth-related signal components. Five targets
is the minimum for "evaluation" rather than "case study"; add the sixth only
if time allows.

Per target you need: vendored pinned source + `PROVENANCE.md`, a C harness
using the library's parse entry point, the sanitizer build (reuse
`harness/build.sh` pattern), and `grammar/<fmt>/adaptation-notes.md`. Budget
~0.5–1 day each.

---

## Conditions

### Core (Tier A) — answer RQ1, RQ2, RQ6

| Cond | Name | What runs | Isolates |
|---|---|---|---|
| C0 | random | `st.text()` baseline | lower bound |
| C1 | seed-only | the iteration-1 grammar-seeded strategy, no refinement | effect of grammar-seeding (C1 vs C0) |
| C2 | full loop | the evolved strategy after the budgeted refinement loop | effect of refinement beyond seeding (C2 vs C1) |

### Ablations (Tier B) — answer RQ3

Each = C2 with exactly one component disabled. Same budgets, same seeds.

| Cond | Disabled component | Tests the hypothesis that... |
|---|---|---|
| A1 | production-coverage steer | closing production gaps drives coverage |
| A2 | nesting-depth (cap-mass) steer | deep-nesting pressure drives coverage (note: T1 evidence says it may not) |
| A3 | novelty guardrail | the guardrail prevents quiet regression to bland inputs |
| A4 | single-feature probes (repair) | probes fix broken feature encodings that would otherwise stall acceptance |
| A5 | **no signal at all** ("naive refine") | the *signal* matters, not merely re-prompting the model |

A5 is the most important control: if A5 ~ C2, the whole signal design is not
earning its keep. Report it prominently either way.

Implementation: add boolean flags to `decide_refinement()` / `summarize()` in
`fuzz/loop/agent.py` (e.g., `--ablate production,capmass,novelty,probes,signal`);
A5 replaces the summary with a fixed "improve the strategy" prompt.

### Models (Tier B) — answer RQ5

| Model | Role |
|---|---|
| M1 deepseek-chat | done for T1; the high-variance author |
| M2 one stronger/other-family model | is the failure taxonomy model-specific? does a better author use the budget better? |
| M3 (optional) a second mid-tier model | robustness of guard/repair |

Run C1/C2 (and ideally the ablations) under each model. Keep the cost table.

---

## Seeds

- **20 seeds per cell** (up from 12) for tighter CIs. Same seed set under every
  condition and target -> randomized block design -> paired tests.
- Draws are seeded (`run_seed`, `database=None`) so cells reproduce.

## Budgets (held constant in every cell, so comparisons are fair)

- 500 examples per iteration; 5 iterations; per-input 5 s timeout; 10-min run
  cap. (Already enforced in `agent.py`.)
- Report cost (tokens, $) per cell.

---

## Metrics (one row per cell)

| Metric | Source | Used for |
|---|---|---|
| region / line / branch coverage of the target's C source | coverage build (`eval/coverage.py` path) | RQ1–RQ4 primary outcome (branch/region preferred; line saturates) |
| acceptance rate | harness exit codes | signal behaviour, guardrail analysis |
| accepted-structure novelty | `summarize()` | RQ4 correlation; guardrail |
| cap-mass (deep-nesting share) | `summarize()` | RQ3/RQ4 (nested formats only) |
| unique crash signatures (deduped) | triage pipeline | RQ6 |
| iterations that produced a working strategy (0–5) | loop log | RQ5 robustness |
| guard events (build-reject, gate, repair, rollback) | loop log | RQ5 |
| tokens in/out, est. $ | `runs/cost.md` | cost table |

Compute coverage and the proxy metrics from the **same** seeded input set per
cell (as `experiment.py` already does), so they are comparable.

---

## Statistical plan

- Per target, per comparison: **paired sign-flip permutation test** on the
  per-seed differences (exact at n<=20), plus the paired-difference 95% CI.
  (Implemented in `eval/experiment.py::paired_perm_test`.)
- Report mean +/- 95% CI per cell (t-interval; `ci95`).
- Effect size: paired mean difference with CI (already), optionally Cliff's
  delta.
- **Multiple comparisons:** the ablation family (A1–A5 vs C2) has five tests per
  target; apply Holm–Bonferroni within the family and say so.
- Aggregate across targets by reporting per-target results **and** a summary
  (e.g., mean of per-target deltas); do not pool seeds across targets as if
  they were one population.
- RQ4: Spearman rho per proxy component vs branch/region coverage, per target
  (`eval/proxy_validation.py`); with 5 targets x 20 seeds the per-target n is
  20, far better than the current n=5.

---

## RQ -> cells map

| RQ | Cells needed | Tier |
|---|---|---|
| RQ1 seeding | C0, C1 on T1–T5 | A |
| RQ2 refinement | C1, C2 on T1–T5 | A |
| RQ6 bugs | C2 triage on T1–T5 (+ C0/C1 for comparison) | A |
| RQ3 ablation | A1–A5 vs C2 on T1–T5 | B |
| RQ4 validity | proxy vs coverage on all C2 cells | B (cheap once A exists) |
| RQ5 LLM-as-author | C1/C2 (+ ablations) under M1–M2(3) | B |

---

## Cell count and cost (order of magnitude)

- Tier A: 5 targets x 3 conditions x 20 seeds = **300 cells** (M1 only). LLM
  cost is dominated by C2's refinement runs; at current per-run cost (cents)
  this is a few dollars. Compute is dominated by coverage runs (fast per input).
- Tier B ablations: 5 targets x 5 ablations x 20 seeds = **500 cells**.
- Tier B multi-model: roughly doubles the C1/C2 (and optionally ablation)
  cells per extra model.

Automate all of it with a matrix runner (below); never run cells by hand.

---

## Infrastructure to build (in order)

1. **Target scaffold**: a per-target directory convention
   (`targets/<name>/{harness.c, build.sh, PROVENANCE.md, grammar.g4,
   adaptation-notes.md}`) so `agent.py`, `runner.py`, and the evals take a
   `--target` instead of assuming json-parser. Prove it on T2 (parson) first.
2. **Ablation flags** in `agent.py` (`--ablate ...`) incl. the A5 naive-refine
   prompt.
3. **Matrix runner** (`eval/matrix.py`): iterates targets x conditions x seeds
   x models, calls the existing pieces, writes one row per cell to a single
   CSV/JSONL, resumable (skip cells already done).
4. **Aggregator + figures** (`eval/report.py`): reads the matrix output, runs
   the statistical plan, emits the per-RQ tables and figures for the paper.
5. **Generalize** `proxy_validation.py` to run per target from the matrix
   output.

---

## Definition of done per tier

- **Tier A done** when: T1–T5 each have a harness + notes; C0/C1/C2 x 20 seeds
  exist for all; RQ1/RQ2/RQ6 tables + the headline coverage figure render from
  `eval/report.py`; related-work and threats sections drafted. -> preprint /
  workshop-ready.
- **Tier B done** when: A1–A5 x 20 seeds on all targets; RQ3 figure with
  Holm-corrected p-values; RQ4 per-target correlations; at least M2 run with
  the RQ5 taxonomy table. -> journal-submittable.
