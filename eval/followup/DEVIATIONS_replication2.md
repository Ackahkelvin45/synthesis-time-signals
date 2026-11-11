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
