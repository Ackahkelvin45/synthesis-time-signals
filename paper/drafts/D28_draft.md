
## D28 — The registered family completed for the journal submission; the result is heterogeneous, and the development target's steered arms are all one degenerate loop

**Why.** The user set a three-day journal deadline (2026-09-14 to 16) and
reopened spend. The cheapest additions that answer the most predictable
reviewer objections were run first: C3s on the two targets it was missing
(json-parser, parson), C3n on all three (completing the registered
confirmatory family {H1, H2s, H2n} on every target), and C2' on tomlc99 (a
second target for the mechanism's intervention). Then, CPU only: RQ3 (proxy
score vs measured coverage over every loop-internal strategy), RQ4
(30-minute ground-truth bug campaigns for every registered arm's finals),
the author-failure taxonomy, the design's sensitivity, and the cost table.

**Runs.** 60 live runs in three batches (day1a-c3s 20, day1b-c2r-toml 10,
day1c-c3n 30), every call served `deepseek-flash`, 0 backstop hits. One DNS
blip on the phone hotspot failed tomlc99 C3n-rep9 twice at its first API
call (no tokens); the overnight chain resumed the batch and it completed.
Spend: day1a 0.541, day1b 0.289, day1c 0.774 USD. All 120 registered Stage 1
runs are now done, plus 20 C2' follow-ups; 140 runs, 3.798 USD in total.

**Measurement.** Every final, seed, and the last working iteration where
it differs from the final, at 10^4 inputs x 20 draw seeds (2 560 new cells,
eval/matrix/day1.jsonl). For json-parser C3s-rep9 and rep10 no iteration
passed the drawability probe, so the matrix skipped their seed condition;
`eval/merge_fill.py` writes 20 explicit failed rows for such seeds (scored
0, the registered minimum) rather than dropping the replicate from the
paired delta.

**Provenance defect found while checking the oracle runs.** When an
iteration records a crash, agent.py's triage branch rewrites
`iter-N/stats.json` with a shorter dict that drops `coverage_in_loop`,
`proxy_score` and `summary_shown_to_model`. On json-parser every iteration
sees a crash (finding #1), so those fields are missing from every
json-parser iteration of every arm. The loop's behaviour was unaffected (it
steers on the live value; the surviving `score` field equals the coverage
under the C3 arms and the proxy otherwise) and the `summary` survives, so
RQ3 recomputes the proxy score from it. Verified by calling the in-loop
measurement directly on json-parser. Not fixed during the study (design
frozen); listed for the follow-up.

**Result, primary outcome (eval/matrix/full_report.md).** A12 with
bootstrap 95% CI; Holm within target over the three members.

| target | H1 C2 vs A5 | H2s C3s vs C2 | H2n C3n vs C2 |
|---|---|---|---|
| json-parser | 0.36 [0.14, 0.63] | 0.36 [0.11, 0.62] | 0.36 [0.12, 0.64] |
| parson | 0.59 [0.32, 0.84] | 0.76 [0.52, 0.96], p 0.044, Holm 0.13 | 0.33 [0.09, 0.59] |
| tomlc99 | 0.39 [0.14, 0.66] | 0.60 [0.35, 0.86] | 0.47 [0.21, 0.74] |

Nothing survives Holm. One cell is a detectable effect before correction:
on parson the coverage-scalar oracle beats its own seed (+1.59, 8 of 10 up,
sign-flip p 0.008), the proxy (A12 0.76) and no steering (A12 0.87 [0.68,
1.00], p 0.004). On the same target the named-function variant does not
(delta −0.16; A12 0.09 [0.00, 0.26] against C3s, exploratory): telling the
model which functions to cover did worse than telling it the number. On
tomlc99 every arm is null. This is the pre-registration's fourth outcome,
"mixed across targets, reported per target; heterogeneity is a finding",
and it replaces the D27 framing "no synthesis-time feedback moves it",
which was true of the cells run at that point.

**The development target's steered arms are one degenerate loop.** On
json-parser the default build aborts on every object input (finding #1), and
agent.py's crash branch takes priority over the signal: the next edit is
"intensify near crash" whenever the iteration saw a crash, `best` is
overwritten every iteration (`new_crash or sc > best_score`), and the
regression check requires `not new_crash`. Branch-fired histogram
(refinement instructions, iterations 2 to 5):

| target | C2 | C3s | C3n | C2R | A5 |
|---|---|---|---|---|---|
| json-parser | intensify_near_crash 31, fix 9 | intensify 30, fix 8, reseed 2 | intensify 36, reseed 4 | intensify 33, reseed 4, fix 2 | improve 35, raise_acc 3 |
| parson | broaden 16, nesting 12, revert 8, fix 4 | increase_branch_coverage 39, fix 1 | cover_function 39, reseed 1 | (not run) | improve 40 |
| tomlc99 | production 21, fix 8, reseed 5, revert 5 | increase_branch_coverage 27, fix 10, reseed 2, revert 1 | cover_function 27, revert 9, reseed 2, fix 2 | production 31, revert 4, reseed 3, nesting 2 | improve 38, reseed 2 |

On json-parser no steered arm ever rolled back (0 of 10 replicates in each
of C2, C3s, C3n) and the final is the last non-gated iteration in 8 to 10
of 10; on parson and tomlc99 C2 rolled back in 6 and 4 replicates and C3n
in 7. So the json-parser rows of the table compare four rounds of "mutate
structurally around the crashing input" against "improve", not signal
against signal; C3n's 0 up / 10 down there (p 0.002) is that loop, not the
function names. The pre-registration already reports json-parser separately
as the in-sample development target; every cross-target claim about signals
rests on parson and tomlc99 only, and the paper says so.

**C2'.** tomlc99: 0 of 10 collapsed (C2 1 of 10); A12 0.54 [0.28, 0.81] vs
C2; delta −1.41 (p 0.09). Over both C2' targets: 0 collapses in 20 runs vs
C2 3 in 20. Removes the failure mode on both targets; adds no coverage on
either.

**Taxonomy (eval/matrix/taxonomy.md).** 96 guard events over 140
replicates; largest classes: unparseable responses 17, strategy-vs-value
confusion 15, generic Python errors 14, the ExceptionGroup wrapper 13 (all
in C2), recursion/health-check 12 (10 in C3s). 33 of 140 seeds failed a
guard at iteration 1. tomlc99 46 events, json-parser 42, parson 8.

**RQ3 (eval/matrix/rq3_report.md).** 604 loop-internal strategies
measured (3 seeds x 1 000 inputs); Spearman rho, proxy vs primary outcome,
pooled: json-parser +0.08 [−0.06, +0.21], parson +0.37 [+0.23, +0.49],
tomlc99 +0.41 [+0.28, +0.52]; against in-loop coverage on the same 500
inputs +0.35, +0.17, +0.46; median within-replicate rho +0.10, 0.00, +0.35.
The proxy ranks generators roughly as coverage does and ranks one run's
iterations barely better than chance. One RQ3 cell was
recorded by hand: json-parser C3n-rep8 iteration 5 (the collapsed final,
which raises RecursionError on every example) at draw seed 2, after its
seeds 0 and 1 had each failed by DrawError after about 25 minutes of
exception churn and seed 2 had run 30 minutes; the row carries an
explanatory error string and scores 0 like the other two. No other cell
was touched.
**RQ4 (eval/matrix/rq4_report.md, 173 campaigns).** Triggered of 10: json-parser
issue 78 C2 3, A5 9, C3s 5, C3n 5 (C2 vs A5 Fisher p 0.02); issue 68-or-78
C2 4, A5 9, C3s 5, C3n 6; tomlc99 issue 50 C2 8, A5 9, C3s 9, C3n 9
(prereg predicted unreachable: WRONG; Grammarinator 1 of 1 at 10 969
inputs); recursion 0 everywhere (prereg right). Random text 0 of 1 on
every build in 3 to 7 M inputs; Grammarinator 0 on both json-parser bugs
in 5.6 to 10 M inputs (complete productions never truncate a literal).
cJSON CVE: baselines 0 of 1 each (LLM arms to follow). Two facts found while
checking the rows. (1) In 13 of 173 first-pass campaigns the positive
control itself timed out under the nine-worker load, campaign.py accepted
"timeout" as the bug's oracle signature, and the campaign then "triggered"
on the first load-induced timeout while the real crash signatures were
filed as "other". campaign.py now fails a control that times out; the 13
rows were dropped (first pass kept as eval/campaigns/rq4.first_pass.jsonl)
and rerun on four workers. The thousands of "timeout" entries among the
other signatures are the same load effect (5-second per-input limit) and
are reported as such. (2) json-parser's two bugs, both one-byte over-reads
at the end of the buffer inside json_parse_ex, normalise to the SAME crash
signature; the issue-78 pre-fix build contains only issue 78 (the issue-68
PoC is a clean reject there), but the issue-68 pre-fix build contains both
(the issue-78 PoC crashes it). The issue-78 row is therefore a single bug;
the issue-68 row measures either over-read and is reported as "issue 68 or
78". Every other crash signature seen in campaigns occurred on a pre-fix
source (old json-parser: a UBSan signed-integer overflow; old tomlc99: heap
over-reads in scan_string fixed upstream since); the pinned HEAD builds
produced none, so there are no new findings to triage.

**Sanity checks (plan E9).** Batch drift: seed-generator levels of the
day-1 batches against phases 1a/1b (identical seed prompt) give A12 0.43
to 0.61 with p > 0.15 on every target; no drift. Equal-time views
(eval/equal_time.py): every generator draws and runs its 10^4 inputs in
under five minutes, so the 5- and 30-minute views coincide with the
equal-n view; "run the seed longer" reduces to the curve's asymptote.
Random text (C0a) measured at 10^4 x 20 seeds on all three targets
(eval/matrix/fixed.jsonl): 26.4, 21.7, 17.1 AUC points; every healthy
LLM seed beats every random draw on every target (A12 1.00), so RQ1's
registered lower bound is established at 30 to 40 points.

**Sensitivity.** With ten replicates per arm and the healthy-replicate SD
(3.3, 2.2, 5.2 points), the registered test has 80% power at a shift of
4.5, 3.0 and 6.5 points (true A12 about 0.82). Effects in the lower half
of the registered "practical" band are not reliably detectable; every null
is "no detectable effect at this budget".

**Stage 2 and reference rows (day 2).** cJSON vendored as T5 (the plan's
v1.7.17 turned out to be the vulnerable release, found by the positive
control crashing the default build; pinned to v1.7.18 with v1.7.17 as the
CVE-2023-53154 bug build; 27 probes against Python json; 8 contract
tests). [cJSON runs and result.] AFL++ reference row via the official
Docker image (no Homebrew on this Mac): afl-clang-fast -O2 -lm, no
sanitizers, afl-fuzz defaults, one seed per format; the final queue is
replayed through the study's coverage build with a raw-bytes path added to
coverage_curve (string path unchanged). Pipeline check: 60 s on json-parser
gave 174 queue entries at 1 122 exec/s and 65.4% reachable-region branch
coverage. [Full row: 4 targets x 5 runs x 1 h, run overnight.] libexpat is
deferred to the revision. One-minute AFL smoke ran while the RQ4 campaigns
were in progress (load already about 58 on 11 cores from nine workers);
campaigns are time-budgeted, so machine load is a shared confound across
arms and is disclosed in threats.

**Prereg amendment (dated 2026-09-14).** C3s on json-parser and parson,
and all C3n, ran as blocks after phases 1a and 1b rather than interleaved;
C2' is a follow-up outside the family; the Holm family per target is now
the full {H1, H2s, H2n}. Stage 2 targets, the AFL++ reference row and M2
are deferred to revision.
