# Pre-registered replication of the shared-seed follow-up, with a backend bridge

Status: FROZEN. It is frozen by the commit that adds it, together with the code it names, before any
run of the arms below. That commit's hash is cited in the paper. No B5, R or E run exists when it is made.

Written 2026-11-02, after the exploratory shared-seed follow-up (Section 5.11 of manuscript v17;
eval/matrix/shared_seed.md). The directions tested below come from that follow-up. The data here are new:
fresh first drafts, fresh runs, fresh measurement. The SF runs are not reused.

## 1. Purpose

The shared-seed follow-up was exploratory and uncorrected, and it ran on a later provider backend than the
September study. This replication tests its three main readings as a pre-specified confirmatory family. It
measures the backend change directly, and explores two questions the follow-up left open: whether showing
a function's source helps where its name hurt, and whether the proxy's information helps under the proxy's
own edit vocabulary.

## 2. Fixed setting

- Model: deepseek-flash through api.deepseek.com, the same configuration as every earlier deepseek-flash run.
  The served identifier and backend fingerprint are recorded per call. A change of fingerprint during the
  batch is reported, not acted on.
- Targets: parson, tomlc99, cJSON (the held-out parsers). json-parser is not used.
- Loop: five rounds, the same guards, prompts and budgets as the September study, except as stated per arm.
- Measurement: auc_branch_reach on the parse-reachable region, 20 draw seeds (0 to 19) of 10 000 inputs, the
  same eval/matrix.py protocol. A replicate's value is the mean over its 20 seeds. A generator that does not
  draw scores 0 on that seed, as everywhere in the paper.

## 3. Arms and runs

| arm | role | feedback | edit instruction | selection | runs |
|---|---|---|---|---|---|
| B5 | bridge, and source of the shared drafts | none | the September no-steering arm, unchanged (`--ablate signal`) | as September A5 | 12 per target |
| R0 | confirmatory | none | common: "make it a better fuzzer for this grammar, using the run feedback above where it is given" | last working | 10 per target |
| R1 | confirmatory | proxy summary | common | last working | 10 per target |
| R2 | confirmatory | branch and region coverage numbers | common | last working | 10 per target |
| R3 | confirmatory | numbers and the five least-covered functions' names | common | last working | 10 per target |
| R4 | exploratory | as R3, plus the source of the least-covered function (first 80 lines) | common | last working | 10 per target |
| E0 | exploratory | none | menu: the proxy's four content edits, model chooses one and names it | last working | 10 per target |
| E1 | exploratory | proxy summary | menu | last working | 10 per target |

Every R and E run starts from a shared draft. Its iteration 1 is a byte copy of that draft, with no model call.

**Draft rule.** Replication replicate k on a target takes the iteration-1 generator of the k-th B5 replicate,
in replicate order, whose iteration-1 generator draws: all 20 seed cells measure without error. If fewer
than 10 of 12 draw on a target, B5 replicates 13, 14 and 15 are run on that target, in order, until 10 draw.
If 15 are not enough, the target is reported with the pairs it has and the shortfall is stated.
eval/followup/replication_seeds.py applies the rule and writes eval/followup/replication_seeds.json.

**Order.** Phase 1 runs B5. Then every B5 seed and final is measured, and the draft rule is applied. Phase 2
runs R0 to R4, E0 and E1, replicate-major, then by arm, then by target (eval/replicates.py plan order).

Total: 36 to 45 B5 runs and 210 R and E runs.

## 4. Confirmatory family

The unit is the replicate pair: two arms started from the same shared draft. The difference is arm minus
arm in coverage points. The statistic is the mean over the three targets of the per-target mean
difference, with each target weighted equally. Tests are stratified sign-flip permutation tests: signs are
flipped independently within pairs, 100 000 random flips, seed 0. The three p values are Holm-adjusted at
alpha 0.05.

- **H1.** Names hurt: R3 minus R2 is less than 0. One-sided.
- **H2.** The proxy summary hurts: R1 minus R0 is less than 0. One-sided.
- **H3.** Coverage numbers are equivalent to no feedback within 2 coverage points: R2 minus R0 lies in
  (-2, +2). Two one-sided tests (TOST), and the p value is the larger of the two. The bound is the two-point
  scale the paper already uses for a refinement that "rarely moves a draft more than two coverage points"
  (Section 5.3). It is fixed here, before the data.

Each hypothesis is reported with the pooled mean, a stratified bootstrap 95% interval (and the 90% interval
for H3), the per-target means and the up, down and zero counts. A hypothesis is supported if its Holm p is
below 0.05, and the decision is printed by the script. Nothing else is confirmatory.

**Power.** This is estimated by resampling the exploratory pairs, 10 pairs per target. It comes out at about
1.0 for H1 and 0.99 for H2, and the H3 90% interval is about ±0.9 points. These estimates are optimistic,
because they reuse the effects that suggested the hypotheses.

## 5. Bridge (secondary, outside the family)

B5 replicates 1 to 10 are compared with September A5 replicates 1 to 10, per target, for first drafts and
for finals. The table gives the difference in means, a 95% bootstrap interval and A12. Interpretation is
fixed in advance. If every interval lies inside ±2 points, the backend change is negligible at the paper's
resolution. Otherwise the paper reports the shift and limits cross-batch statements to the targets where it
holds.

## 6. Exploratory (uncorrected, labelled as such)

- R4 minus R3, and R4 minus R2: does a function's source help where its name hurt.
- E1 minus E0: does the proxy's information help under the proxy's own edit vocabulary.
- E0 minus R0, and E1 minus R1: the menu against the plain instruction.
- The frequency of each menu choice, from the "EDIT:" line of each refinement response.

The real proxy chooses its edit by rule from its own signal. The menu lets the model choose, so the E arms
approximate the proxy's vocabulary and do not reproduce its decision procedure. The paper says so.

## 7. Execution rules

- **Lock.** No measurement while a loop run is active (build/.runs.lock), as before.
- **Parallel measurement.** Up to three eval/matrix.py processes may run at once on disjoint conditions. On
  2026-11-02, cached and fresh draws measured in parallel matched sequential measurement exactly.
- **Errors.** A cell that errors, whatever the cause, is re-measured once, alone, after the parallel pass,
  and the second result stands. Both rows are kept (eval/matrix/replication_first_errors.jsonl). A generator
  that genuinely cannot draw errors twice and scores 0, as before.
- **Launcher.** eval/followup/replication_run.sh runs every step above in order.
- **Interrupted runs.** A run that fails for an infrastructure reason (network, API balance, a provider
  error with no response) is discarded and rerun from the start. This has been the rule since 2026-10-30,
  and every case is listed in the batch manifests.
- **No interim looks.** No R or E contrast is computed before every R and E cell is measured.
  eval/followup/replication_report.py runs once, on the complete data.
- **Deviations.** Any departure from this plan is written to eval/followup/DEVIATIONS_replication.md before
  the analysis runs, and is reported in the paper.

## 8. Budget

At about 0.02 USD per run, the total is about 5 USD. R4's prompts are longer. Wall clock is about 3 h of
phase 1 runs and about 3 h of measurement, then about 14 h of phase 2 runs and about 10 h of measurement.

## 9. Code frozen with this plan

- fuzz/loop/agent.py: `--policy menu`, `--oracle coverage_body`, and the `--seed-from` and `--policy common`
  options of the earlier follow-up.
- eval/replicates.py: conditions B5, R0 to R4, E0 and E1.
- eval/followup/replication_seeds.py, eval/followup/replication_report.py and eval/followup/replication_run.sh.
- eval/matrix.py and eval/cell.py: the measurement used throughout.
