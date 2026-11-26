# Deviations from PLAN_replication2.md

Recorded before the analysis runs, as section 6 requires.

## 1. Launcher hang after phase-1 measurement (found 2026-11-09)

- **What happened.** Phase 1 completed as planned: 72 B6 runs (pass 1 cut by a network drop, 18 rerun in pass 2), then 1 440 draft cells measured with the one re-measurement of error cells, finished 2026-11-06 13:30Z. The launcher then stopped moving. Its no-sleep assertion (`caffeinate ... &`) was a background job of the script, and the bare `wait` after measurement waited on it, while caffeinate waited on the script. Nothing ran from 2026-11-06 13:30Z to 2026-11-09 07:00Z.
- **Effect on data.** None. No Q run existed. No measurement was repeated.
- **Fix (eval/followup/replication2_run.sh, committed after the freeze).** caffeinate runs in a subshell. Each measured file gets a `.done` marker when its one re-measurement is finished, and the launcher skips a marked file, so the relaunch does not re-measure the phase-1 error cells a second time; the six phase-1 files were marked by hand before the relaunch. The batch loop also waits for a balance of 0.5 USD before each pass, so a mid-study 402 stalls instead of consuming the eight passes.
- **Draft rule, applied as written.** Non-drawing drafts: tomlc99 reps 5, 7 and 20; parson reps 15 and 22; cjson rep 13 (one seed cell errored twice). Rep 7 of tomlc99 was not measured at all because none of its five generators draws, so the matrix resolver has no seed strategy for it; it is excluded by the rule in the same way as a draft whose cells error. Drawing drafts: parson 22, tomlc99 21, cjson 23. No extra B6 replicate was needed.
- **Dates.** Phase 2 therefore ran from 2026-11-09, not 2026-11-06. The window stays within one week and all Q arms are interleaved by the batch runner as planned.

## 2. Launcher killed during phase 2 (found 2026-11-11)

- **What happened.** The relaunched launcher ran Q pass 1 and started pass 2 at 2026-11-10 06:01Z. Its last run finished 2026-11-10 09:21Z; the launcher process was then gone, with no host reboot and no STATUS line of its own, so it was killed from outside (most likely with the terminal session that started it). 166 of 240 Q finals existed; the batch runner's lock was stale.
- **Effect on data.** None. Finished runs are kept; run directories without final.json are deleted and rerun from the start, as the plan's interrupted-run rule says. No cell had been measured.
- **Fix.** Relaunched 2026-11-11 in its own process session (detached from any terminal) with the unchanged launcher, which resumes from the existing finals.

## 3. Phase-2 balance gate lowered on the resume (2026-11-11)

The launcher's 3.5 USD gate before the arms batch was sized for 240 runs. On the 2026-11-11 resume 74 runs remained (about 1 USD) and the balance was 3.25 USD, so the gate was lowered to 1.0 USD. The per-pass 0.5 USD check is unchanged. No effect on the runs or their analysis.

## 4. Draft rule: the code accepted replicates whose iteration 1 produced no working generator (found 2026-11-13)

- **What happened.** After eight passes, four runs were still missing: tomlc99 pairs 19 in all four arms. Their shared draft, runs/tomlc99/B6-rep22/iter-1/strategy.py, does not exist: that replicate's first two generators were rejected at build, so iteration 1 wrote no strategy file. The draft rule's code had accepted replicate 22 because the measured `seed` condition is the earliest iteration that draws (eval/cell.py, seed_strategy_path), here iteration 3, and its 20 cells had no error.
- **Scope.** The same mismatch between the rule as written ("the iteration-1 generator draws") and the rule as computed affects other pairs whose iteration-1 file exists but did not build or draw: in this study parson pairs 4 and 16, tomlc99 pairs 4, 8, 12 and 15, cjson pairs 6 and 12 (in all but parson pair 4 the shared draft was rejected at build or gated in iteration 1 of every arm, so each arm's round 2 repaired the same broken draft). In the first replication (PLAN_replication.md), parson pair 10 and cjson pair 9 are the same case. Within a pair the four arms still share one draft and one history up to the first feedback, so the paired contrasts are unaffected; what differs from the plan's text is that these pairs begin by repairing the draft rather than refining it.
- **Decision.** The study keeps the rule as computed for the 59 pairs that ran, so no finished run is relabelled or discarded. Pair 19 of tomlc99 takes replicate 24, the only unused tomlc99 replicate whose iteration-1 cells all draw (replicate 23 is already pair 20). Under the rule as written, tomlc99 would have had only 16 drawing drafts of 23 and needed further B6 replicates; parson 20 and cjson 21.
- **Code.** replication_seeds.py gains `--require-iter1`, off by default so both studies' mappings are reproducible; with it the rule as written is computed. replication2_report.py adds one descriptive line: the number of pairs per target whose shared draft failed at iteration 1. No contrast is added.
- **For the paper.** The draft rule is described as computed, and the counts above are reported with the second study.

## 5. Host restart during phase-2 measurement (found 2026-11-20)

- **What happened.** All 240 Q finals were complete on 2026-11-13. Measurement started at 13:00Z, and the host restarted at 18:12Z with 2 271 of 4 800 cells written. Nothing ran from then until 2026-11-20.
- **Effect on data.** None. eval/matrix.py appends one cell per line and skips cells already present, so the relaunch measures only the missing cells. The cells already written, error cells included, were measured once under the same parallel setting. They go through the one re-measurement of error cells exactly as planned. No cell value was read before the relaunch: only line and error counts.
- **Disk.** The regenerable draw cache (build/_inputs) was cleared to make room. Cached draws are reproducible from the strategy file, n and seed (eval/_draw.py), and cells already present are never redrawn.

## 6. Memory cap on draws (found 2026-11-26)

- **What happened.** The host restarted again on 2026-11-20 at 18:25Z, 18 minutes after the measurement resumed. A JetsamEvent report (memory exhaustion) at 18:08:48Z names a single Python process of about 10 GB as the largest process. The cause is one final, parson Q3-rep16. Its generator draws no input and grows without bound: its macOS memory footprint passes 40 GB within 30 seconds, while its resident size stays near 3 GB. Its first five seeds had each ended at the 900 s draw timeout. The restart on 2026-11-13 happened while the same final was being measured, and is probably the same cause.
- **Fix (eval/cell.py, after the freeze).** A watchdog thread ends any draw whose footprint, as top reports it, passes 6 GB. The draw then raises DrawError("draw exceeded 6 GB of memory"). Below the cap nothing changes: the same subprocess, the same 900 s timeout and the same output. On a normal final the old and new paths give byte-identical inputs (checked on cjson Q0-rep1, 2 000 inputs), and eval/test_eval.py passes 44 of 44. Normal draws use well under 1 GB.
- **Effect on data.** parson Q3-rep16 is a collapsed final either way, since every one of its draws errors, before and after the fix. Its seeds after the fifth now error in seconds rather than at 900 s or by taking the host down. No other cell measured so far reached the cap: none of them errored on memory, and the host stayed up through 2 271 cells. No cell value was read: only line and error counts, and the two suspect finals' memory during a draw.
