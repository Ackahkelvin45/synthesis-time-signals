# Pre-registration draft (for OSF, with embargo)

Status: DRAFT written 2026-09-12, before any live replicate run. To be
registered on OSF before the first run of `eval/replicates.py`. Nothing in
this document is derived from replicate data; the two pilot runs (json-parser
2026-08-24, parson 2026-09-12) informed the design and are disclosed below.

## 1. Title (neutral, fixed at registration)

Synthesis-time feedback for LLM-authored grammar-based generators: a
replicated comparison of no steering, a structural proxy, and a coverage
oracle on C parsers.

## 2. Hypotheses

- H1. A refinement loop steered by the structural proxy (C2) yields
  generators with higher primary outcome than the same loop with no steering
  signal (A5).
- H2. A refinement loop steered by measured coverage (C3s; C3n) yields
  higher primary outcome than the proxy-steered loop (C2). The difference is
  reported as the price of blindness.
- Secondary, descriptive: RQ1 (seed vs random, seed vs Grammarinator on the
  identical grammar), RQ3 (proxy score vs coverage over loop strategies),
  RQ4 (time-to-trigger of ground-truth bugs), RQ5 (author failure taxonomy;
  the H1 three-way under a second model on one held-out target).

## 3. Primary outcome (single)

`auc_branch_reach`: the mean of cumulative branch coverage of the
parse-reachable region (eval/reachable/<target>.json, sha recorded per run
and per cell) at the log-spaced checkpoints 10, 30, 100, 150, 300, 1000,
3000, 10000 inputs, for the loop's FINAL generator, drawn on 20 fresh seeds
(0..19) that the loop never used internally. Every other metric is
exploratory and labelled so.

## 4. Conditions and targets

Targets (Stage 1): json-parser (development target, in-sample, reported
separately), parson (held-out, JSON), tomlc99 (held-out, TOML).
Loop conditions, 10 replicates each per target: C2 (proxy), A5 (no
steering; validity machinery kept: build screen, acceptance gate, one repair
re-prompt; rollback only to the last working generator), C3s (coverage
scalar), C3n (coverage with least-covered function names; white-box lite,
function names not anonymized). Fixed generators: random text (C0a),
Grammarinator defaults and depth-matched (C0b), each replicate's seed (C1).
Model: deepseek-chat, temperature 0.7, prompts anonymized; served model id
and system fingerprint logged per call; interleaved run order.

## 5. Budgets held constant

500 examples per iteration, 5 iterations; the 10-minute per-iteration and
40-minute per-run caps are safety stops and every hit is logged and
reported. Wall-clock, CPU seconds, tokens and dollars are outcomes.

## 6. What counts as the loop's output

`final_strategy.py` written by the loop (the generator it holds after any
rollback). `run:<cond>-rep<k>:last` (the last working iteration) is reported
next to `final`. Gated or rolled-back iterations are counted as they
happened (they are the method's behaviour); they are never excluded. A run
whose directory lacks `final.json` is a failed run: deleted and rerun by the
driver; the count of such reruns is reported.

## 7. Analysis (implemented in eval/report.py; dry-run on synthetic data)

Unit of analysis: the loop replicate. Draw seeds are averaged within a
replicate first. Per target: H1 and H2 as differences of replicate means
with a two-sample permutation test (20 000 shuffles) and Vargha-Delaney A12
with a 5 000-resample percentile bootstrap CI; per-replicate delta
(final minus seed) with an exact sign-flip test. Cross-target: per-target
results plus the mean of per-target effects; seeds are never pooled.
Multiplicity: the confirmatory family is {H1, H2s, H2n} per target on the
primary outcome, Holm-corrected within target; targets are replication.

Practical-difference thresholds (Vargha-Delaney conventions): A12 >= 0.64
(or <= 0.36) with a bootstrap CI excluding 0.50 = a practical difference;
0.56 <= A12 < 0.64 = small; otherwise negligible.

## 8. Predictions written before the data

- C3 > C2 > A5: the proxy recovers a stated fraction of the oracle's gain.
- C2 ~ A5 < C3: structural steering does not earn its place; the paper
  reports it and the contribution becomes the validity/guard machinery
  analysis and the author-failure taxonomy.
- C2 ~ A5 ~ C3: refinement of any kind adds little at this budget; the
  paper's contribution becomes RQ1 (authorship vs grammar possession) and
  RQ5. If Grammarinator matches the LLM seed as well, the one-sentence
  claim becomes: "for small C parsers, a grammar is what matters; LLM
  authorship and blind refinement add little, and here is the measured
  size of 'little' with its uncertainty."
- Mixed across targets: reported per target; heterogeneity is a finding.
No outcome leads to abandoning the paper; the stop rule is that the design
is not changed after data collection begins.

A5 feedback disclosure. A5 does receive one kind of feedback: when a
generator fails the acceptance gate (fewer than 5% of a fixed 90-example
draw accepted, or the generator raises), the loop sends one repair re-prompt
carrying either the generator's exception text or its acceptance rate. This
is validity machinery, present identically in every loop condition: it
tells the model only whether its code runs and produces inputs the parser
accepts at all, never which productions, depths, structures or coverage the
inputs reached, so it cannot steer toward any target behaviour. The paper
names A5 "no steering signal", not "no feedback".

Exploratory-results guard. Any component ablation (A1-A4), any secondary
metric, and any per-target pattern outside the confirmatory family is
reported as exploratory, serves to generate hypotheses for future work, and
cannot be promoted to a headline claim regardless of how striking it looks.
The confirmatory family is fixed at registration and does not grow.

## 9. Ground-truth bugs and expectations

json-parser issue78 (`tru`) and issue68 (`"\uDCB`): expected reachable by
grammar-aware generators that emit truncated literals and escapes (the seed
prompt asks for near-valid malformed inputs). tomlc99 issue50
(`[0]\n0.0=[]\n+.\n`) and the recursion overflow (about 20 000 nested
levels, above the 2048 steer band): expected NOT to be reached by any
condition within 30 minutes; reported as such. Campaign builds: json-parser
bug builds disable only the pointer-overflow check (finding #1's idiom
predates the bugs); tomlc99 uses the full sanitizer set. Triggering is
decided by matching the PoC's crash signature, both measured in batch mode.

## 10. Compute-matched control for refinement

Every condition's generator is evaluated at the same 10 000 inputs on the
same curve, so "run the seed longer" is answered by the seed's own curve at
equal n. The loop's synthesis cost (2 500 executed inputs plus about 17 000
input and 17 000 output tokens, about $0.025) is reported next to every
effect; the equal-time views (5 and 30 minutes, generation time included)
use the persisted draw time of each input set.

## 11. Cost ceiling and run order (registered)

Stage 1 cells: 3 targets x 4 loop conditions x 10 replicates = 120 live
runs (fixed generators C0a, C0b and each replicate's seed cost no API
calls). Per-run cost from the two pilots: $0.024 and $0.023 (about 17k input
+ 17k output tokens at deepseek-chat prices), so 120 runs = $3.00. Failed
runs are rerun once; the driver logs every rerun. Registered Stage 1 ceiling:
$4.00 (planned runs plus up to about 40 reruns), inside a hard total cap of
$10.00 for all DeepSeek spend (Stage 2 adds 2 targets x 4 x 10 = 80 runs,
$2.00). Second model on the user's separate OpenAI balance (30 runs on
tomlc99). Compute: local for development; the official runs in the Docker
image.

Run order: the first dollar tests the riskiest claim. Phase 1a runs C2 and
A5 on json-parser, alternating C2/A5 for replicates 1..10 (20 runs, $0.50),
so H1 on the development target is answered first. Phase 1b runs everything
else interleaved (rep 1 of every remaining condition x target before rep 2,
conditions alternating within a rep). Within each phase the interleaving
keeps provider drift orthogonal to condition; the phase boundary is a
target/condition block that is disclosed here.

## 12. Disclosures

The json-parser pilot (legacy prompts, pre-oracle-fix) and the parson pilot
informed the design and are excluded from replicate statistics. A K=3,
n=300 glimpse on json-parser (DECISIONS D21) showed Grammarinator matching
the LLM seed on branch coverage; this was seen before registration and is
disclosed.
