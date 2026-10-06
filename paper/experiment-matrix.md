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
- Input sets are reproducible by construction (`eval/cell.py`: history-fixed
  subprocess draw, cached and hashed; every row carries its input-set id).

## Loop replicates (design addition — learned from the parson run)

The loop itself is stochastic (the LLM), so "the evolved strategy" is ONE draw
of a high-variance process: the first parson run gated its first two
iterations on a Hypothesis-API mistake, peaked at iteration 4 and REVERTED at
iteration 5. Two consequences, both implemented:

- **What counts as the output.** The loop writes `final_strategy.py` +
  `final.json` (what it hands back after any revert). For older runs,
  `cell.final_strategy_path` reconstructs it from `evolution.md` by replaying
  the loop's own bookkeeping (verified: json-parser -> iter-5, parson ->
  iter-4). `seed` = the first WORKING iteration (json-parser -> iter-1
  repaired; parson -> iter-3), recorded in the condition label. The matrix and
  the experiment never read iter-1 / iter-5 blindly.
- **RQ2 needs loop replicates, not just draw seeds.** Draw seeds average out
  input noise for a FIXED generator; they cannot average out loop variance.
  Run >=3 loop replicates per target (`--run-name rep1..repN`), evaluate each
  replicate's seed/final as conditions (`run:repN:seed`, `run:repN:final`),
  and report RQ2 as the distribution of per-replicate paired deltas. Cost is
  cents per replicate; it is the difference between "one lucky run" and a
  claim about the method.

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
- **Absolute coverage is NOT comparable across targets.** A parse-only harness
  can never reach a library's serializer / mutation / query APIs, and how much
  of the file those occupy varies wildly: random text reaches ~42% of
  json-parser's `json.c` (small, parse-centric) but only ~5% of parson's
  `parson.c` (large API surface, mostly unreachable from parsing). So the
  paper compares **conditions within a target** (deltas, ratios, paired tests)
  and reports absolute % only as context. Consider also reporting coverage of
  the parse-reachable region (e.g., functions reachable from the entry point)
  as a normalized secondary metric.
- **Seeded Hypothesis draws depend on process history — inputs must be
  materialized and hashed.** Found by re-measurement, not assumed: identical
  inputs measured twice on one binary are bit-identical, and a seeded draw is
  reproducible across processes — but ONLY for an identical process history.
  Merely importing a module that decorates a `@given` test, or launching the
  interpreter differently, changes the sequence `@seed(n)` yields, so two eval
  scripts drawing "the same" seeded examples reported different coverage
  (42.2 / 42.6 / 43.6 line% on one binary — discrete levels, not noise). The
  fix (`eval/cell.py` + `eval/_draw.py`): every draw runs in a fresh
  interpreter with a fixed minimal history, is cached keyed by a hash of
  exactly (strategy source, n, seed), and every reported measurement carries
  that input-set id. A reviewer can then verify identical inputs by hash. Note
  this never affected the *internal* validity of a single experiment run (all
  its cells share one history and are paired by seed); it affected exact
  cross-script reproduction of the numbers. This belongs in the paper's
  reproducibility section — it is a trap other LLM-fuzzing papers using
  Hypothesis likely fall into.
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

1. **Target scaffold — DONE.** `fuzz/targets.py` (registry + binary naming
   rule), `targets/<name>/{harness.c, adaptation-notes.md}`, `build.sh
   TARGET=`, `agent.py --target` (per-target realities in the seed prompt,
   `runs/<target>/`), `runner.py` SKIP 10 + `roundtrip`. Proven on T2 (parson):
   classification matches every documented behavior; json-parser is
   byte-identical (85/85 tests, prompt text verified equal).
   **Also DONE — target-aware evals via ONE shared measurement:** `eval/cell.py`
   (coverage build per target, one-pass coverage + proxy metrics per cell);
   `coverage.py` / `experiment.py` / `proxy_validation.py` take `--target` and
   `--out`.
   **Also DONE — reproducible, hashed input sets:** strategies are passed by
   reference; every draw runs in a history-fixed subprocess (`eval/_draw.py`),
   is cached under `build/_inputs/` keyed by hash(strategy source, n, seed),
   and every measurement records its input-set id. Verified: six launch
   contexts that previously produced three different "seeded" input sets now
   produce one identical hash; `coverage.py` run twice is byte-identical and
   reproduces the committed 42.2% / 83.1% exactly. The random baseline's
   input-set id is identical across targets (true apples-to-apples).
2. **Ablation flags — DONE.** `agent.py --ablate production,capmass,novelty,
   probes,signal` (any subset) and `--run-name <sub>` (writes under
   `runs/<target>/<sub>/`). Budgets are never reallocated when a component is
   off, so conditions differ only in the signal. `signal` is the A5 control:
   no run summary, no score rollback, generic "improve" instruction — only the
   validity machinery (build screen, acceptance gate + repair) remains. Every
   run now writes `config.json` (target, ablations, model) and
   `final_strategy.py` + `final.json` (the loop's OUTPUT after any revert).
3. **Matrix runner — DONE** (`eval/matrix.py`): targets x conditions x seeds,
   one JSONL row per cell with its input-set id, resumable. Conditions
   `random | seed | evolved | run:<sub>:<seed|final|N>`.
4. **Aggregator — DONE** (`eval/report.py`): mean ± 95% CI per (target,
   condition); paired tests for RQ1/RQ2; the `run:*` family vs `evolved` with
   Holm correction within target; cross-target summary as mean of per-target
   deltas. Figures: still to add (tables first).
5. **Generalize `proxy_validation.py` — DONE** (`--target`, per-target output);
   the matrix runner will supersede its n=5 per-iteration view with n=K seeds.

---

## Definition of done per tier

- **Tier A done** when: T1–T5 each have a harness + notes; C0/C1/C2 x 20 seeds
  exist for all; RQ1/RQ2/RQ6 tables + the headline coverage figure render from
  `eval/report.py`; related-work and threats sections drafted. -> preprint /
  workshop-ready.
- **Tier B done** when: A1–A5 x 20 seeds on all targets; RQ3 figure with
  Holm-corrected p-values; RQ4 per-target correlations; at least M2 run with
  the RQ5 taxonomy table. -> journal-submittable.
