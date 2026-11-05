# Second pre-registered study: the shared-draft directions under the stated last-working rule

Status: FROZEN by the commit that adds it, together with the code it names, before any
run of the arms below (5 Nov 2026). That commit's hash is cited in the paper. No B6 or Q run existed when it was made.

Written 2026-11-05, after the first pre-registered replication (eval/followup/PLAN_replication.md, frozen at
3edb0af; results in eval/matrix/replication.md, commit 967f2f20). The hypotheses below come from the first
replication's data and from the exploratory follow-up of Section 5.11. They are tested here on new data: fresh
first drafts, fresh runs and fresh measurement. No run of the earlier studies is reused.

## 1. Why a second study

**What the first replication found.** None of H1 to H3 was supported. Seven of its 210 finals did not draw and
scored 0, and three of them decided the result.

**What caused the collapses.** All seven are an implementation error in the frozen code, found after the
analysis by reading the runs.

- The plan and the paper describe `--policy common` and `--policy menu` as: keep the last working generator and never repair in place.
- In fuzz/loop/agent.py, the fallback to the last working generator applied only when a generator failed to build.
- A generator that built but still failed the acceptance gate after its one in-iteration repair was kept. The next round was asked to fix it, which is in-place repair.
- 15 of the 210 runs had such a gated round. All 7 collapsed finals are a round-5 generator that had failed the gate.
- Section 5.11 is not affected in practice: none of its 116 runs had a gated round.

**What this study tests.** The two directions of Section 5.11 and of the first replication's surviving pairs:

- names below numbers;
- the proxy summary below no feedback.

It tests them under a loop that implements the stated rule, as `--policy strict`. Under that rule a final
should not be a gate-failed generator, so all pairs are analysed. No conditioning on survival is needed.

The first replication's result stands as run and is reported as run, with this error disclosed. The
equivalence hypothesis H3 is not repeated.

## 2. Fixed setting (unchanged from the first replication)

- **Model and dates.** deepseek-flash through the same client. The backend fingerprint is recorded per run. All runs fall in one window, arms interleaved by the batch runner.
- **Targets.** The three held-out parsers: parson, tomlc99, cjson. Same pinned builds and harnesses.
- **Loop.** Five rounds, the same guards, prompts and budgets, and the same plain edit instruction for every arm. The one in-iteration repair attempt after a failed acceptance gate is kept, as in every arm of every study.
- **Policy `strict`.** Identical to `common`, except that a generator still below the gate after that repair is discarded. The next round then refines the last working generator with the plain instruction. A build failure was already handled this way.
- **Measurement.** auc_branch_reach on the parse-reachable region, 20 draw seeds (0 to 19) of 10 000 inputs, eval/matrix.py.

## 3. Arms and runs

| arm | feedback | built as | runs |
|---|---|---|---|
| B6 | none; supplies first drafts | B5 (= the September A5 arm) | 24 per target, up to 30 |
| Q0 | none | R0, under `--policy strict` | 20 per target |
| Q1 | proxy summary | R1, under `--policy strict` | 20 per target |
| Q2 | coverage numbers | R2, under `--policy strict` | 20 per target |
| Q3 | coverage numbers and the five least-covered function names | R3, under `--policy strict` | 20 per target |

**Draft rule.** For each target, pair k (1 to 20) starts from the iteration-1 generator of the k-th B6
replicate, in replicate order, whose iteration-1 generator draws: all 20 seed cells (`run:B6-rep<j>:seed`) are
measured without error. Code: `replication_seeds.py --arm B6 --need 20`.

If a target has fewer than 20 drawing drafts after B6 reps 1 to 24, single further replicates (25, 26, and so on)
are run on that target only, up to 30. If it is still short after 30, the study stops for a decision. That
decision is recorded as a deviation before any Q run.

**Measured.** B6 first drafts (seed) and Q finals (final). B6 finals are run but not measured.

## 4. Confirmatory family

**Unit and statistic.** The unit is a replicate pair on a shared draft, all 20 pairs per target. A final that
does not draw on a seed scores 0 on that seed, as everywhere in the paper. The statistic is the mean over the
three targets of the per-target mean paired difference, in coverage points. It is tested by stratified sign
flips: 100 000 random flips, seed 0.

| | hypothesis | prediction | test |
|---|---|---|---|
| K1 | names below numbers | Q3 minus Q2 < 0 | one-sided sign flip |
| K2 | proxy summary below no feedback | Q1 minus Q0 < 0 | one-sided sign flip |

Holm correction at alpha 0.05 over K1 and K2. A hypothesis is supported if its Holm-adjusted p is below 0.05.
The estimate and 95% bootstrap interval (stratified, 10 000 resamples) are reported for both, supported or not.

## 5. Secondary and descriptive (outside the family)

- **Secondary.** K1 and K2 over pairs with neither final collapsed (a final is collapsed if any of its 20 cells errors after the one re-measurement). Estimates, intervals and uncorrected one-sided p.
- **Descriptive.**
  - Q2 minus Q0.
  - Collapsed finals per arm and target.
  - Gated iterations and gate fallbacks per arm.
  - For each collapsed final: inputs drawn and failed chunks.
  - The backend fingerprint of every run.

No other contrast is computed for the paper.

## 6. Execution rules

- **Lock.** No measurement while loop runs are active (build/.runs.lock).
- **Parallel measurement.** Measurement runs in up to six parallel processes, one per target and half of the replicates. Each writes its own file. Parallel and sequential measurement give identical values (checked 2026-10-30).
- **Error cells.** Error cells are moved to replication2_first_errors.jsonl and re-measured once, alone. A cell that errors again keeps its error.
- **Interrupted runs.** A run that fails for an infrastructure reason is discarded and rerun from the start. Infrastructure reasons are network, API balance, a provider error with no response, or a host restart. Every case is in the batch manifests.
- **Sleep.** The launcher holds a no-sleep assertion while it runs.
- **No interim looks.** No Q contrast is computed before every Q cell is measured. Monitoring reads only the one-line STATUS files.
- **One analysis.** replication2_report.py runs once. Its output, eval/matrix/replication2.md, is reported in full.
- **Deviations.** Any deviation is written to eval/followup/DEVIATIONS_replication2.md before the analysis runs.
- **Launcher.** eval/followup/replication2_run.sh runs every step above in order.

## 7. Power and limits, stated before the data

Power was estimated by resampling the first replication's pairs with neither final collapsed. That is the
closest available proxy for pairs under the strict rule. One-sided test at 0.025 for Holm over two; 400
simulations per setting.

| hypothesis | effect as observed | half that effect |
|---|---|---|
| K1, 20 pairs per target | near 1.00 | 0.88 |
| K2, 20 pairs per target | near 1.00 | 0.65 |

Effects observed in a post-hoc subset usually shrink, so the half-size column is the planning figure.

A generator can still pass the gate and fail at 10 000 inputs. Such a final scores 0 and is reported. It
would lower power, which section 5's secondary analysis shows.

**Whatever the result,** sections 4 and 5 are reported as computed, in the paper and the artifact.

## 8. Budget

At about 0.013 USD per run, about 312 runs cost about 4.10 USD, plus about 0.50 USD for reruns.

The launcher waits for a DeepSeek balance of at least 1.5 USD before phase 1 and 3.5 USD before phase 2.

Wall clock is about 6 h of B6 runs and 8 h of their measurement, then about 18 h of Q runs and about 12 h of
measurement.

## 9. Code frozen with this plan

- **fuzz/loop/agent.py.** `--policy strict`. `common` and `menu` are unchanged, so earlier runs stay reproducible.
- **eval/followup/test_strict_policy.py.** An offline check with a scripted model, no API call. It passes before the freeze. It shows that:
  - `common` keeps a gate-failed round-5 generator;
  - `strict` returns round 4's;
  - after a gate-failed middle round, `strict` refines the last working generator with the plain instruction.
- **eval/replicates.py.** Conditions B6 and Q0 to Q3. Q arms take their draft from replication2_seeds.json.
- **eval/followup/replication_seeds.py.** `--arm`, `--need` and `--out`. With the defaults it gives the first study's rule, checked identical on that study's data.
- **eval/followup/replication2_report.py.** The analysis of sections 4 and 5. Checked on duplicated first-study data relabelled as Q arms; that check is not a result.
- **eval/followup/replication2_run.sh.** The launcher.
