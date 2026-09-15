# Synthesis-time feedback for LLM-authored grammar-based generators: a
replicated comparison of no steering, a structural proxy, and a coverage
oracle on C parsers

## Abstract

Large language models can turn a formal grammar into an input generator
for a parser, and an agent can refine that generator over several rounds.
What feedback should drive the refinement? We compare three synthesis-time
signals in an otherwise identical loop: no steering, a structural proxy
computed from the generator's own outputs and the parser's exit codes (no
instrumentation, no source), and a coverage oracle that measures branch
coverage of the parser's reachable region each round, with and without the
names of the least-covered functions. The study is pre-registered, with one
primary outcome (the area under the branch-coverage curve to ten thousand
inputs on seeds the loop never saw), ten independent loop replicates per
cell, and four C parsers in two text formats. No comparison in the
confirmatory family survives correction. Five rounds of refinement move
the first-draft generator's coverage by one to two points: upward under
measured coverage on one held-out parser, within noise on the other two,
and never under the proxy or under no steering. Naming the functions to cover
did worse than giving the number. Whether the first draft beats
Grammarinator on the identical grammar depends on the target (a tie, ahead,
and clearly behind on TOML). The loop's one visible failure, an unusable
output generator, traces to its repair policy rather than its signal: shown
its own failed code the model resubmits it, recovering 2 times in 25;
re-seeded from the grammar it recovers 12 in 14, and a re-seeding loop
produced no unusable generator in twenty runs. On the development target a
crash-first rule silently made every steered arm one loop, a confound only
replication exposed. At three cents a run, the grammar-seeded first draft
is most of the result; we release every run, prompt, input-set hash and
script.

**Keywords.** fuzzing; grammar-based test generation; large language models; property-based testing; pre-registered study; replication.

## 1. Introduction

Grammar-based generation reaches parser code that random bytes never do:
random text covers 42% of json-parser's lines and a grammar-seeded
generator 83% (measured on the pilot target with the same coverage build;
artifact, DECISIONS D11). Writing such a generator by hand is tedious,
and recent work has language models write them from a grammar and then
refine them. Vikram and Padhye's Gentoo agent, with source access, coverage
reports and a strong model, produced generators that beat human-written
ones on four of seven Java libraries and gained little from coverage-guided
mutation at fuzz time: the structure encoded in the generator made
coverage guidance largely unnecessary (Vikram and Padhye, 2026).

That result concerns fuzz time and a white-box agent costing about ten
dollars per synthesis. We study the other corner: synthesis time, a cheap
model (about three cents per run), and no access to source, coverage or the
parser's error messages while the generator is written. In that regime the
question is what the refinement loop should be told. We test four answers,
holding everything else fixed: nothing beyond whether the generator runs
and produces inputs the parser accepts (A5); a structural proxy computed
from the generator's own outputs and the parser's exit codes, designed for
this setting (C2); measured branch coverage of the parser's reachable
region (C3s); and the same number with the names of the least-covered
functions (C3n). The proxy is the object of study; the oracle is the
ceiling it is measured against, not a claim that coverage is unavailable.

We pre-registered the design (hypotheses, one primary outcome, ten
replicates per cell, exclusion rules, analysis code, a neutral title)
before the first replicate run, froze it in version control, and report
every deviation. The unit of analysis is the loop replicate, because the
model is a high-variance author: 44 of our 180 first drafts failed a guard,
and the pilot's single-run 51-to-72 score trajectory did not reproduce.

Contributions.
1. A replicated, pre-registered comparison of four synthesis-time signals
   on four C parsers. No comparison survives correction; measured coverage
   produced a detectable gain on one held-out target before correction
   and beat the proxy, but not no steering, on a second; the proxy never
   did, and naming functions to cover did worse than the number (Section
   5).
2. The community baseline the LLM-generator literature usually omits:
   Grammarinator on the identical grammar against twenty LLM first drafts
   per target. LLM authorship is a tie, ahead, and clearly behind,
   depending on the target (Section 5.4).
3. A mechanism for the loop's only visible failure, unusable output
   generators: fixation under in-place repair, a three-path table over 80
   replicates that replicates under the oracle arms, and a pre-specified
   intervention (repair by re-seed) that removes the failure on two targets
   without changing coverage (Section 6).
4. A confound that replication exposed and single-run evaluations would
   not: on the development target a crash-first event rule turned every
   steered condition into the same loop (Section 5.1). Plus a failure
   taxonomy, the design's measured sensitivity, and an artifact with every
   run, prompt, input-set hash and script.

What the paper does not claim: that any loop finds bugs its seed does not
(Section 5.6: the ground-truth bugs are found by the seeds' class of
generator, and the proxy loop found them less often than no steering on
the development target), that the proxy is a poor
approximation of coverage across generators (Section 5.5: rho about 0.4 on
the held-out targets, though near zero across one run's own iterations), or that the nulls would survive a larger
budget or a stronger model (Section 7).

## 2. Background

A grammar-based generator produces inputs by expanding a grammar's
productions, so every output is in the language, or close to it. The
classical tool for ANTLR grammars is Grammarinator, which compiles a .g4
file into a generator class and samples derivations with configurable
depth and alternative weights; it is the baseline the LLM-fuzzing
literature is expected to beat and the one we use. Property-based testing
libraries approach the same job from the other side: a Hypothesis strategy
is a small program that describes how to draw values, composed from
primitives (text, integers, lists, recursion with a leaf budget), and
Hypothesis draws from it under a seed. The generators in this paper are
Hypothesis strategies written by a language model. Two properties of that
setting recur in the results: a strategy is an object that draws values,
not a value, and confusing the two is one of the model's most frequent
errors (Section 5.7); and a strategy that raises on some draws still runs
on others, so "usable" is a matter of degree, which the measurement's draw
protocol handles by dropping raising chunks and counting them.

The crash oracle is the sanitizer pair AddressSanitizer and
UndefinedBehaviorSanitizer with recovery disabled, so any detected memory or
undefined-behaviour error aborts the process; the harness reports valid,
rejected, skipped or crashed by exit code, and the loop never sees the
parser's own error text. The reference feedback against which the proxy is
judged is branch coverage of the parser's parse-reachable functions,
measured with clang's source-based instrumentation on a separate build;
this is the signal coverage-guided fuzzers such as AFL++ steer by at fuzz
time, and here it is used at synthesis time as the oracle arm.

## 3. Approach: a synthesis-time refinement loop for LLM-authored generators

### 3.1 Pipeline

The loop takes a formal grammar and a short adaptation note, asks a language
model to write a Hypothesis strategy (a Python program that generates strings
in the grammar's language), runs the strategy against the parser under
sanitizers, summarises the run, asks the model for exactly one change, and
repeats. Five iterations, 500 executed inputs per iteration, temperature 0.7,
no request seed. The model never sees the parser's name, source, API, error
messages, or coverage. Its observable world is the grammar, the note, the
exit-code class of each input it generated (valid, rejected, crash), its own
generated inputs, and the feedback the condition supplies.

The grammar is the ANTLR grammars-v4 grammar for the format, used verbatim.
The adaptation note records where the library's accepted language deviates
from that grammar (json-parser accepts a trailing comma and duplicate keys;
tomlc99 accepts leading zeros and calendar-invalid dates), produced by running
a fixed set of hand-written probe inputs through the harness against a strict
reference parser. The note is human-authored and identical across conditions.

### 3.2 Validity machinery (present in every loop condition)

The model is a high-variance author. Four guards, identical in every arm,
keep a broken generator from consuming the budget: an AST screen that rejects
disallowed imports and attribute access before the module is executed; an
acceptance gate that draws 90 inputs under three PRNG seeds and rejects a
generator that raises on any seed or has fewer than 5% of its inputs accepted
by the parser; one in-iteration repair re-prompt carrying either the
exception text or the acceptance rate; and rollback. A generator that fails
the gate after its repair is kept as the loop's current generator (the
registered rule: gated iterations count as they happened), and the next
iteration's prompt repairs it again. The two repair paths matter for Section
6: after a build rejection (the module does not import or fails the screen)
the loop discards the code and re-seeds from the grammar with the rejection
text appended; after a gate failure (the module builds but fails the gate) the
loop re-prompts in place, showing the model its own failed code with the
instruction "make exactly one change".

One more rule matters for reading the results. A crash is the loop's
highest-priority event: when an iteration's run produced a new crash
signature, the next edit is "mutate structurally around the crashing
input" regardless of the condition, that iteration becomes the best so far,
and the regression check is skipped (the loop must not roll back away from
a crash). On a parser whose default build crashes on every object input,
which the development target does (Section 4.2), this rule fires every
iteration; Section 5.1 reports what that did to every steered arm there.

### 3.3 The steering signals (what differs between arms)

**Proxy (C2).** A structural summary computed from the generator's own
outputs and the parser's exit codes, with no instrumentation: the set of
grammar productions present in accepted inputs against the grammar's
production universe (the production gap), the share of accepted inputs whose
nesting depth falls in a deep band, the number of distinct accepted structure
fingerprints (novelty), the acceptance rate, and six single-feature probes
(a valid baseline perturbed by exactly one feature, run against the parser
and a strict reference). A fixed decision procedure maps the summary to one
named edit per iteration (add a production, generate deeper, fix a feature,
revert). The proxy score drives regression rollback and best-iteration
selection.

**No steering (A5).** The model receives no run summary; the refine prompt
says only "make it a better fuzzer for this grammar". Rollback is to the last
working generator, never to a score-best one, because there is no score. A5
does receive the validity feedback of Section 3.2, so it is named "no
steering signal", not "no feedback".

**Coverage oracle (C3s, C3n).** The proxy score is replaced, everywhere the
proxy acts, by branch coverage of the parse-reachable region measured on the
iteration's 500 inputs with an instrumented build. Under C3s the model sees
only the coverage number; under C3n it additionally sees the five least
covered reachable functions by name (white-box lite; names are not
anonymised). The next edit is "increase branch coverage" (C3s) or "cover
function F" (C3n). Both conditions record the proxy summary as well, which
yields the RQ3 validity data at no extra cost.

**Repair by re-seed (C2', follow-up).** Identical to C2 except that a
generator failing the gate is never shown back to the model: the in-iteration
repair, and every prompt while the held generator is a failed one, is the
grammar seed prompt with the failure text appended. Added after the Stage 1
mechanism analysis (Section 6) and outside the registered confirmatory family.

## 4. Experimental design

### 4.1 Pre-registration and its amendments

The hypotheses, single primary outcome, target set, conditions, replicate
count, exclusion rules, analysis code and a neutral title were frozen in the
repository (commit 4762bad) before the first replicate run; the design was
not registered on a public registry, and the git history serves as the
timestamp. Deviations are disclosed in Section 4.6.

### 4.2 Targets

Four C parsers, three grammars, two formats: json-parser (JSON; the
development target, on which the proxy was designed, reported separately),
parson (JSON; held out), tomlc99 (TOML; held out), and cJSON (JSON; held
out; the first of the two Stage 2 targets named in the pre-registration,
run after the Stage 1 analysis, Section 4.6). cJSON v1.7.18 is parsed
through its length-taking entry point with an exact-length buffer, so that
the harness can reach the over-read of Section 4.5 in the bug build; its
adaptation note and prompts are anonymised so that no library name reaches
the model. Each has a sanitizer build
(ASan and UBSan, -O0, no recovery) used by the loop, a coverage build used
only for measurement, and, for json-parser, tomlc99 and cJSON, sanitizer
builds at pinned pre-fix commits of known bugs (Section 4.5). Absolute coverage is not
comparable across targets; every comparison is within a target.

The primary outcome's denominator is the parse-reachable region: the
functions reachable from the harness entry point in the static call graph,
unioned with any function observed covered by any condition. It is committed
per target and its hash is recorded in every run and every measurement.

### 4.3 Conditions, replicates, and order

Loop conditions C2, A5, C3s and C3n, ten independent replicates each per
target (160 runs), plus C2' on json-parser and tomlc99 (20 runs). Fixed
generators, measured on the three Stage 1 targets: random text,
Grammarinator 26.1 on the identical grammar (defaults, and with recursive
alternatives up-weighted to match the mean nesting depth of the development
target's pilot seed), and each replicate's own seed generator. Model:
deepseek-chat as requested; the provider served deepseek-flash
(DeepSeek-V4.1-Flash) on every call, recorded per call, and the paper reports
the served identifier. Run order was interleaved within each phase so that
provider drift is orthogonal to treatment; the phase boundaries are disclosed.

### 4.4 Primary outcome and measurement

`auc_branch_reach`: the mean of cumulative branch coverage of the
parse-reachable region at the log-spaced checkpoints 10, 30, 100, 150, 300,
1000, 3000 and 10 000 inputs, for the loop's final generator, drawn on 20
fresh PRNG seeds the loop never used. Inputs are drawn in a history-fixed
subprocess and cached under a hash of (generator source, n, seed, runtime
versions), so every measurement is reproducible and identified. A generator
that cannot produce its input set (it raises on every draw) is a failed cell
and scores the minimum; a replicate whose final generator fails on all 20
seeds is "collapsed" and scores zero in the primary analysis, as registered.
The last working iteration is reported next to the final so that an oracle
condition cannot win by selecting the maximum of its own noisy metric. All
other metrics (region and line coverage, fixed-n and equal-time points,
acceptance, novelty, inputs per second) are exploratory.

### 4.5 Ground-truth bugs

json-parser issue 78 (a truncated literal at the end of the buffer) and issue
68 (a \u escape truncated after three hex digits), both one-byte heap
over-reads at pinned pre-fix commits; tomlc99 issue 50 (a NULL dereference in
key-value parsing) and its unfixed recursion stack overflow. Each bug's
hand-written proof of concept must crash the pre-fix build through the same
batch harness (positive control) or the bug is dropped. A campaign feeds a
generator's inputs to the pre-fix build for 30 minutes and records the first
input whose normalised crash signature matches the proof of concept's, or
censoring. A control that times out (machine load) is a failed control,
not an oracle, and the campaign is rerun on a quiet machine. Two facts
about the json-parser pair are stated with the results: both bugs
normalise to the same signature, and the issue-68 pre-fix build also
contains issue 78, so that row measures either over-read. cJSON
(Stage 2) adds CVE-2023-53154, a one-byte over-read after a trailing comma
reachable only through the length-taking API, with v1.7.17 as its bug
build. The pre-registration predicted the two tomlc99 bugs would not be
reached by any condition within the budget.

### 4.6 Analysis

The unit of analysis is the loop replicate; draw seeds are averaged within a
replicate first. Per target: H1 (C2 vs A5) and H2 (C3s vs C2, C3n vs C2) as
differences of replicate means with a two-sample permutation test (20 000
shuffles) and Vargha-Delaney A12 with a 5 000-resample percentile bootstrap
interval, Holm-corrected within target over the confirmatory family; the
per-replicate delta (final minus seed) with an exact sign-flip test. Bands,
fixed at registration: A12 at or beyond 0.64 (or 0.36) with an interval
excluding 0.5 is a practical difference; 0.56 to 0.64 small; otherwise
negligible. Targets are replications, not pooled. Everything outside the
confirmatory family (RQ1, RQ3, RQ4, the mechanism analysis, C2') is
exploratory and is labelled so in every table.

**Deviations from the registered design.** C3s on json-parser and parson,
and C3n on all three Stage 1 targets, were run as blocks after phases 1a and 1b
rather than interleaved with them, so provider drift is not orthogonal to
those cells (the served model identifier was constant across every batch);
C2' was added after the mechanism analysis and is outside the confirmatory
family. The first Stage 2 target, cJSON, was run in full (four arms, ten
replicates) after the Stage 1 analysis, as the registration's Stage 2
allows, and is reported in every table beside the Stage 1 targets; its
fixed references (RQ1), its RQ3 cells and its bug campaigns were not
measured before the submission cutoff. The second Stage 2 target
(libexpat), the AFL++ reference row and the second model (gpt-5-mini on
tomlc99, arms C2, A5 and C3s) were not completed: the second model's batch
stood at 18 of 30 runs when the submission was frozen, and those runs are
excluded from every table and kept in the artifact. The registered Stage 1
budget was 4.00 USD; 3.80 USD was spent on the 140 Stage 1 and C2' runs
and 0.84 USD on the 40 cJSON runs (4.63 USD in total), plus about 0.03
USD on attempts discarded after network failures and about 1.4 USD of
OpenAI credit on the excluded second-model runs.

### 4.7 Use of large language models

Large language models were used in two distinct roles. As the object of
study, the generators evaluated in this paper were written by the DeepSeek
model named in Section 4.3, under
the prompts released in the artifact; that use is the experiment. As an
assistant during the research, an AI coding assistant (Claude, Anthropic)
was used for writing and refactoring the evaluation and analysis code, for
running and monitoring the experiment batches, for drafting text that the
authors then revised, and for checking numbers against the generated
reports. The experimental design, the pre-registration, the interpretation
of the results and the final text are the authors' own; the authors have
verified every number in the paper against the committed data; no AI tool
is an author of this work.

## 5. Results

Table 2 (generated from eval/matrix/full_report.md) gives, per target and
arm, the final generator's level on the primary outcome (mean and 95% CI
over ten replicates, median), the number of collapsed replicates, the
per-replicate delta against the seed, and the last working iteration's
level where it differs from the final. Figure 1 shows the coverage curves,
Figure 2 the between-arm effect sizes, Figure 3 the deltas.

**Table 1. Targets**

| target | source | lines | functions | parse-reachable functions | grammar (grammars-v4) | ground-truth bug builds | role |
|-------|----------|-----|--------|----------|--------------|--------------|-----------|
| json-parser | json.c | 1057 | 10 | 9 | JSON.g4 | issue68, issue78 | development (in-sample) |
| parson | parson.c | 2486 | 144 | 40 | JSON.g4 | none | held out |
| cjson | cJSON.c | 3143 | 112 | 13 | JSON.g4 | cve-2023-53154 | held out (Stage 2) |
| tomlc99 | toml.c | 2392 | 82 | 53 | TomlLexer.g4, TomlParser.g4 | issue50, recursion | held out |


**Table 2. Final-generator level and refinement delta per target and arm**

Primary outcome auc_branch_reach (10^4 inputs x 20 draw seeds per replicate; failed cells and collapsed finals score 0). Mean ± 95% CI over ten replicates (median); coll. = collapsed replicates; last working = the last working iteration's level where it differs from the final (n = replicates where it differs). Δ = final − seed per replicate, exact sign-flip test; replicates whose seed generator failed but whose final works are excluded from Δ and counted under seed failed.

| target | arm | final | coll. | Δ final − seed | up / down | sign-flip p | seed failed | last working |
|--------|--------------|-----------------|-----|--------------|-------|--------|-------|-----------|
| json-parser | C2 proxy | 51.0 ± 19.3 (63.9) | 2 | -1.02 ± 0.81 | 2 / 6 | 0.031 | 0 | - |
| json-parser | A5 no steering | 63.7 ± 2.8 (64.6) | 0 | +0.15 ± 1.16 | 6 / 4 | 0.768 | 0 | - |
| json-parser | C3s coverage | 48.8 ± 18.7 (59.4) | 2 | -1.60 ± 1.70 | 2 / 6 | 0.062 | 0 | - |
| json-parser | C3n coverage + names | 54.9 ± 14.0 (61.5) | 1 | -9.20 ± 13.62 | 0 / 10 | 0.002 | 0 | - |
| json-parser | C2R C2' re-seed repair | 63.9 ± 1.3 (64.4) | 0 | -1.32 ± 1.40 | 2 / 7 | 0.074 | 0 | - |
| parson | C2 proxy | 60.9 ± 15.4 (67.1) | 1 | +0.89 ± 0.50 | 7 / 1 | 0.016 | 0 | - |
| parson | A5 no steering | 66.3 ± 1.6 (66.7) | 0 | +0.54 ± 0.75 | 7 / 2 | 0.160 | 0 | - |
| parson | C3s coverage | 69.1 ± 1.1 (69.4) | 0 | +1.59 ± 0.86 | 8 / 2 | 0.008 | 0 | 68.6 (n 1) |
| parson | C3n coverage + names | 66.0 ± 1.3 (65.8) | 0 | -0.16 ± 1.48 | 5 / 5 | 0.797 | 0 | - |
| tomlc99 | C2 proxy | 52.9 ± 13.9 (57.4) | 1 | -0.01 ± 1.10 | 2 / 4 | 1.000 | 1 | - |
| tomlc99 | A5 no steering | 60.2 ± 3.4 (59.8) | 0 | +1.80 ± 2.33 | 6 / 3 | 0.121 | 1 | - |
| tomlc99 | C3s coverage | 55.1 ± 14.1 (60.6) | 1 | +0.22 ± 0.61 | 5 / 1 | 0.438 | 0 | 50.7 (n 6) |
| tomlc99 | C3n coverage + names | 57.4 ± 3.7 (58.5) | 0 | -0.70 ± 0.96 | 0 / 3 | 0.250 | 1 | 51.2 (n 4) |
| tomlc99 | C2R C2' re-seed repair | 59.3 ± 2.4 (60.3) | 0 | -1.41 ± 1.64 | 1 / 7 | 0.086 | 0 | 60.2 (n 3) |
| cjson | C2 proxy | 61.8 ± 15.6 (68.3) | 1 | -0.51 ± 0.46 | 2 / 7 | 0.039 | 0 | 67.1 (n 1) |
| cjson | A5 no steering | 70.3 ± 1.6 (70.1) | 0 | +1.35 ± 1.69 | 6 / 3 | 0.113 | 0 | - |
| cjson | C3s coverage | 64.2 ± 16.2 (72.2) | 1 | +1.15 ± 2.10 | 6 / 2 | 0.234 | 1 | 71.7 (n 2) |
| cjson | C3n coverage + names | 66.6 ± 5.1 (68.8) | 0 | -3.28 ± 6.23 | 2 / 5 | 0.156 | 2 | 60.9 (n 1) |


![Branch coverage of the parse-reachable region against inputs drawn, per target and arm: median over replicates with the interquartile band; the seed mean and the stronger Grammarinator variant as dashed and dotted lines.](figures/f1_curves.pdf)

### 5.1 A note on the development target, read first

json-parser's default build aborts on every object input (a
standards-violating NULL-offset idiom, finding #1 of the pilot), and the
loop treats a crash as the highest-priority event: whenever an iteration
saw one, the next edit is "mutate structurally around the crashing input",
the iteration becomes the new best, and the regression check is skipped.
On json-parser every iteration sees one. The branch-fired histogram (Table
5) shows the consequence: on json-parser the proxy arm issued its
production or depth edits 0 times in 40 refinements, the oracle arms issued
"increase branch coverage" or "cover function" 0 times, and every steered
arm issued "intensify near crash" 30 to 36 times; no steered arm rolled
back in any of its ten replicates. On parson and tomlc99 the same arms
issued their intended edits (C3s 39 and 27 times, C3n 39 and 27, C2 its
production and nesting edits) and rolled back in 4 to 7 replicates. The
json-parser rows below therefore compare four rounds of one fixed
instruction against "improve"; they are reported because the
pre-registration requires it and because they are the in-sample target the
proxy was designed on, but every claim about signals in this paper rests on
parson and tomlc99.

### 5.2 The confirmatory family: no result survives correction; one target shows a detectable oracle effect

Vargha-Delaney A12 of the final level, ten replicates per arm, bootstrap
95% CI, permutation p, Holm within target over {H1, H2s, H2n}:

| target | H1: proxy vs no steering | H2s: coverage vs proxy | H2n: coverage with names vs proxy |
|---|---|---|---|
| json-parser (see 5.1) | 0.36 [0.14, 0.63], p 0.24 | 0.36 [0.11, 0.62], p 0.67 | 0.36 [0.12, 0.64], p 0.96 |
| parson | 0.59 [0.32, 0.84], p 0.90 | 0.76 [0.52, 0.96], p 0.044, Holm 0.13 | 0.33 [0.09, 0.59], p 0.96 |
| tomlc99 | 0.39 [0.14, 0.66], p 0.29 | 0.60 [0.35, 0.86], p 0.65 | 0.47 [0.21, 0.74], p 0.71 |
| cjson (Stage 2, Section 4.6) | 0.25 [0.06, 0.49], p 0.046, Holm 0.14 | 0.78 [0.52, 0.98], p 0.49 | 0.54 [0.28, 0.80], p 0.74 |

![Vargha-Delaney A12 with bootstrap 95% CI for every between-arm contrast run, per target; the shaded bands are the registered negligible and small ranges.](figures/f2_forest.pdf)

H1 is null on all four targets after correction, with the point estimate
favouring no steering on three of them; the mean differences are driven by
the proxy arm's collapsed replicates (two, one, one and one), which score
zero as registered, and among usable generators the two arms are
indistinguishable on the three Stage 1 targets (json-parser 63.7 vs 63.7;
parson A12 0.66 [0.38, 0.89]; tomlc99 0.43 [0.16, 0.71]). cJSON, the
fourth target, run after the Stage 1 analysis (Section 4.6), is the one
target where the proxy arm also sits below no steering among usable
generators (68.7 vs 70.3, A12 0.28 [0.07, 0.53], p 0.09): A12 0.25 [0.06,
0.49] before correction, p 0.046, Holm 0.14.

H2s is null on tomlc99 and on the development target. On parson the
coverage-scalar oracle is the one cell in the family with a detectable
effect before correction: its finals reach 69.1 ± 1.1 against the proxy's
60.9 ± 15.4 (67.7 among usable generators) and no steering's 66.3 ± 1.6,
A12 0.76 against the proxy and 0.87 [0.68, 1.00] (p 0.004) against no
steering, and every one of its ten replicates produced a usable generator.
Holm over the three-member family takes the p to 0.13, so by the
registered rule the family is null on parson too; the cell is reported as
what it is, a practical-band effect on one target that the design's
correction does not confirm. cJSON repeats the parson pattern in a weaker
form: the coverage-scalar finals reach 64.2 ± 16.2 (median 72.2; 71.4
among usable generators) against the proxy's 61.8 ± 15.6 (68.7 usable),
A12 0.78 [0.52, 0.98], and 0.84 [0.60, 1.00] (p 0.017) among usable
generators; the permutation p on the mean difference is 0.49 because each
arm has one collapsed replicate. Against no steering (70.3 ± 1.6) the same
arm is A12 0.62 [0.35, 0.88], p 0.83, so on cJSON measured coverage beats
the proxy and does not detectably beat leaving the model alone.

H2n is null on all four targets (cJSON A12 0.54 [0.28, 0.80]; 0.28 [0.04,
0.54] against the scalar oracle), and on parson the named-function variant
is clearly below the scalar one (A12 0.09 [0.00, 0.26], p 0.001, an
exploratory contrast outside the family): telling the model which
functions were least covered did worse than telling it the number.

### 5.3 Refinement moves the seed by one to two points, in either direction

![Per-replicate change of the primary outcome from seed to final, per target and arm; bar = arm mean, dotted = mean without the off-scale replicates (triangles: a failed seed generator above, a collapsed final below).](figures/f3_deltas.pdf)

Figure 3 and Table 2. On parson the coverage-scalar oracle improves on its
seed by +1.59 ± 0.86 points (8 of 10 up, sign-flip p 0.008) and the proxy
by +0.89 ± 0.50 (7 up, p 0.016); no steering is within noise (+0.54, p
0.16) and the named-function oracle is within noise (−0.16, 5 up, 5 down).
On tomlc99 every arm is within noise once the replicates whose seed
generator failed and whose final works are set aside (they inflate the
delta by the whole final level and are flagged in Table 2): proxy −0.01,
no steering +1.80, C3s +0.22, C3n −0.70, C2' −1.41. On json-parser the
degenerate loop of 5.1 moves every steered arm down: proxy −1.02 (p 0.03),
C3s −1.60 (p 0.06), C3n −9.2 with its collapse and −0.1 to −6.5 without it
(10 of 10 down, p 0.002), C2' −1.32; no steering is within noise. On cJSON
the proxy moves its seed down by −0.51 ± 0.46 (2 up, 7 down, p 0.039), no
steering +1.35 ± 1.69 (p 0.11), the coverage scalar +1.15 ± 2.10 over the
nine replicates whose seed drew (p 0.23), and the named-function oracle
−3.28 ± 6.23 over eight, one of which lost 21 points to a final whose
draws time out (Section 8). Five
rounds of feedback change the seed's coverage by one to two points on the
held-out targets, upward only under measured coverage on parson.

### 5.4 RQ1: whether LLM authorship beats the grammar alone depends on the target

![The twenty LLM seed generators per target against random text and Grammarinator on the identical grammar, each over 20 draw seeds.](figures/f4_rq1.pdf)

Figure 4 and Table 3. The registered lower bound first: random text
(Hypothesis's st.text(), no grammar) reaches 26.4, 21.7 and 17.1 AUC
points on json-parser, parson and tomlc99, and every healthy LLM seed
generator beats every random draw on every target (A12 1.00); having the
grammar is worth 30 to 40 points, and everything below is about the
remaining few. The unit is the generator: A12 of the twenty LLM seed
generators' means against Grammarinator's twenty draw values on the
identical grammar. Healthy seeds against the stronger Grammarinator
variant: json-parser 0.62 [0.43, 0.80] (a tie with the depth-matched
variant; 0.83 [0.66, 0.97] against defaults); parson 0.70 [0.51, 0.87];
tomlc99 0.13 [0.02, 0.28], with 2 of 17 healthy seeds above Grammarinator's
mean. On tomlc99 Grammarinator also beats every loop arm's finals (A12 0.14
against no steering, 0.13 against the proxy) and, in Figure 1, the oracle
arms only reach it at 10 000 inputs. Three of twenty tomlc99 seed
generators could not draw at all. The TOML Grammarinator was not
depth-calibrated (Section 7). cJSON's fixed references (random text and
Grammarinator on the JSON grammar, byte-identical to the json-parser and
parson input sets) were not measured before the submission cutoff (Section
4.6); cJSON has no RQ1 row and no equal-time view.

### 5.5 RQ3: the proxy tracks coverage across generators, not across a run's own iterations

![Proxy score recorded by the loop against the measured primary outcome of the same iteration's generator, one point per loop-internal strategy, coloured by arm.](figures/f5_rq3.pdf)

Figure 5 and eval/matrix/rq3_report.md. Every loop-internal strategy that
ran (604 across the five arms) was measured on three fresh draw seeds at
1 000 inputs and paired with the proxy score the loop recorded for it.
Pooled over arms, Spearman rho between the proxy and the primary outcome is
+0.08 [−0.06, +0.21] on json-parser (n 208), +0.37 [+0.23, +0.49] on parson
(192) and +0.41 [+0.28, +0.52] on tomlc99 (204): a weak-to-moderate
monotone relation on the held-out targets, none on the development target.
Under the coverage arms the loop also recorded branch coverage on the same
500 inputs the proxy was computed from, which removes measurement noise:
rho +0.35, +0.17 and +0.46. The granularity that matters to the loop is
within one run, where the proxy decides which iteration is best and whether
to roll back; there the median within-replicate rho is +0.10, +0.00 and
+0.35 (23, 18 and 28 of 43, 38 and 44 replicates positive). The proxy
orders different generators the way coverage does, roughly; it does not
reliably order five variants of the same generator, which is the job it
was given. The correlation is strongest inside the no-steering arm (+0.55,
+0.59 on parson and tomlc99), whose iterations vary most, and weakest inside
the steered arms, whose iterations the steer keeps within a narrow band.

### 5.6 RQ4: ground-truth bugs

![Fraction of an arm's campaigns that had triggered the bug after n inputs, per ground-truth bug; baselines dashed and dotted.](figures/f6_rq4.pdf)

Figure 6 and eval/matrix/rq4_report.md. Each arm's ten final generators
ran a 30-minute campaign against each pre-fix build; a campaign counts as
triggered when an input's normalised crash signature matches the proof of
concept's. Two facts shape the reading. json-parser's two bugs, both
one-byte over-reads at the end of the buffer inside json_parse_ex,
normalise to the same signature, and the issue-68 pre-fix build also
contains issue 78 (its proof of concept crashes there), so the issue-78 row
is one bug and the issue-68 row measures either over-read. And a first pass
of the campaigns ran nine at a time under heavy load, which made 13
positive controls time out; those 13 were rerun on a quiet machine after
the runner was changed to fail a timed-out control (Section 4.6).

| bug | proxy | no steering | coverage | coverage + names | random text | Grammarinator |
|---|---|---|---|---|---|---|
| json-parser issue 78 | 3 of 10 | 9 of 10 | 5 of 10 | 5 of 10 | 0 (3.0 M inputs) | 0 (6 to 10 M) |
| json-parser issue 68 or 78 | 4 of 10 | 9 of 10 | 5 of 10 | 6 of 10 | 0 (3.0 M) | 0 (5.6 to 10 M) |
| tomlc99 issue 50 | 8 of 10 | 9 of 10 | 9 of 10 | 9 of 10 | 0 (6.2 M) | 1 of 1 (10 969 inputs) |
| tomlc99 recursion | 0 | 0 | 0 | 0 | 0 | 0 |

Three results. First, the pre-registration predicted that neither tomlc99
bug would be reached within the budget; issue 50, a NULL dereference on a
key-value line, was reached by 8 to 9 of 10 replicates in every arm, in a
median of 4 000 to 45 000 inputs, and by Grammarinator after 10 969. The
prediction was wrong about that bug and right about the recursion overflow,
which needs about 20 000 nesting levels and was reached by nothing in 0.4
to 6 million inputs. Second, on json-parser the no-steering arm's
generators triggered both bugs in 9 of 10 campaigns and the proxy arm's in
3 and 4 (issue 78: Fisher p 0.02); the oracle arms sit between. The proxy
arm's collapsed finals count as never triggering (two of its ten), but the
gap remains among usable generators (3 of 8 against 9 of 10 on issue 78).
On this target the proxy arm's degenerate loop (Section 5.1) spent its
rounds mutating around the finding-#1 crash, which every object input
already reaches, and its finals emit fewer of the truncated literals and
escapes the two bugs need. Third, random text triggered nothing in 3 to 7
million inputs on any build, and Grammarinator triggered nothing on
json-parser in 5.6 to 10 million: a grammar-driven generator emits complete
productions, and both json-parser bugs need a value cut off at the end of
the buffer, which the LLM seeds emit because the prompt asks for near-valid
malformed inputs. Every other crash signature seen in the campaigns
occurred on a pre-fix source (a known UBSan integer overflow in old
json-parser; scan_string over-reads in old tomlc99, fixed upstream since);
the pinned HEAD builds produced none, so there are no new findings. The
cJSON campaigns (CVE-2023-53154, Section 4.5) were not run before the
submission cutoff; the bug build, its positive control and the campaign
driver are in the artifact.

### 5.7 RQ5: how the author fails

One hundred and twenty-one guard events across 180 replicates (four
targets, the four registered arms and C2'; Table 4; eval/matrix/
taxonomy.md). The largest classes are unparseable responses (24),
strategy-versus-value confusion (24: concatenating a strategy object to a
string, calling a strategy as a value), generic Python errors (18),
Hypothesis's ExceptionGroup wrapper (13, all in the proxy arm), whose
message names no exception, line or construct because the loop's error
formatter forwards the wrapper rather than its sub-exceptions, so those
repair prompts carried no information, recursion and health-check failures
(13, of which 10 in the coverage-scalar arm) and hallucinated Hypothesis
API names (13). Forty-four of 180 seeds failed at least one guard at
iteration 1. By target: tomlc99 46 events, json-parser 42, cJSON 25,
parson 8; the two-file, mode-based TOML grammar is the harder authoring
task and the one where Grammarinator wins.

### 5.8 Cost

Table 6 (eval/matrix/cost_table.md). 180 runs, 4.63 USD in total; a run
costs 0.018 to 0.041 USD (mean 0.026) and 3.6 to 9.4 minutes of wall clock
(mean 4.4), with 12 000 to 31 000 tokens in and about the same out. Every
call was served by deepseek-flash. Gentoo reports 7.5 to 12.8 USD per
synthesis; twenty independent seeds on one target cost less than one of
theirs.

### 5.9 Sensitivity of the design

With ten replicates per arm and the between-replicate SD of usable
generators (3.3, 2.2, 5.2 and 2.2 AUC points on json-parser, parson,
tomlc99 and cJSON), the registered permutation test reaches 80% power at
a mean shift of 4.5, 3.0, 6.5 and 3.0 points, a true A12 of about 0.82. Effects in the
lower half of the registered practical band (0.64 to 0.80) are not
reliably detectable by this design, so every null above reads "no
detectable effect at this budget". Collapsed replicates, which score zero,
raise the SD to 14 to 20 points and dominate every between-arm mean
difference in Table 2.

## 6. Mechanism: collapse is fixation, and the repair path decides recovery

Exploratory (pre-registration, exploratory-results guard); generated from
the logs after the confirmatory analysis.

### 6.1 The collapsed replicates resubmit their own code

Ten replicates across the registered arms ended with a generator that
raised on every draw (proxy: json-parser 7 and 10, parson 6, tomlc99 3,
cJSON 1; C3s: json-parser 9 and 10, tomlc99 8, cJSON 8; C3n: json-parser
8). In the four
proxy-arm cases analysed first, the model received the same repair
instruction at iterations 2 to 5 and answered with code 98.4% similar to
the previous iteration; three of the four returned byte-identical modules
on at least two consecutive iterations. Two received the empty
ExceptionGroup message; two received an explicit TypeError or
AttributeError and still resubmitted.

### 6.2 Recovery is a property of the path, not the arm

After a gate event the loop takes one of three paths, decided by what the
next prompt shows the model. Pooled over the 80 proxy and no-steering
replicates on the four targets:

| path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|
| in place: the failed code with "make exactly one change" | 25 (C2 22, A5 3) | 2 of 25 | 0.98 (min 0.75) |
| fallback: the last working generator | 4 (C2 3, A5 1) | 3 of 4 | 0.95 |
| re-seed from the grammar with the failure text | 14 (C2 9, A5 5) | 12 of 14 | 0.07 (0.02 to 0.11) |

The pattern holds under the oracle arms, pooled over their 80
replicates: in place 7 of 25 recovered at similarity 0.93 to 1.00, re-seed
11 of 15 at 0.02 to 0.15, fallback 1 of 2 (eval/matrix/full_report.md,
per-target tables). In-iteration repairs, which always show the failed code,
resubmit near-identical code in every in-place arm (mean similarity 0.94
to 1.00). Both arms use the identical seed prompt and guards, so the
iteration-1 gate incidence is sampling variation of one process; within
the proxy arm on the three Stage 1 targets an iteration-1 gate predicts
collapse (4 of 4 collapsed had
one, 5 of 26 healthy; Fisher p 0.005).

### 6.3 C2': repair by re-seed, on two targets

The one pre-specified test of the mechanism. json-parser: 0 of 10 collapsed
(proxy 2 of 10); final 63.9 ± 1.3; A12 0.58 [0.32, 0.83] against the proxy,
0.47 among usable generators, 0.46 against no steering. tomlc99: 0 of 10
collapsed (proxy 1 of 10); final 59.3 ± 2.4; A12 0.54 [0.28, 0.81] against
the proxy, 0.40 against no steering. Over both targets 0 collapses in 20
runs against the proxy's 3 in 20. In-iteration repair similarity to the
gated code 0.04 (proxy 0.96). Re-seeding removes the anchoring and, with
it, the unusable outputs; it adds no coverage on either target. The
ExceptionGroup formatter was left unchanged, so the result isolates the
repair path.

### 6.4 What this changes

Whether a loop occasionally hands back an unusable generator is decided by
its repair policy, which every arm shares, not by the steering signal; the
signal, on the two targets where it acted at all, moved coverage by one to
two points and only the measured-coverage scalar moved it upward, on one
target. The practical advice for a loop of this shape is therefore about
the repair path (never show the model its own failed code; re-seed with
the failure text) before it is about the signal.

## 7. Discussion

**What the heterogeneity says.** The pre-registration listed four outcomes
and this is the fourth: the same three signals, in the same loop, with the
same model, produced a detectable gain on one held-out parser (parson,
under measured coverage), a gain against the proxy but not against no
steering on a second (cJSON), nothing on the third (tomlc99), and nothing
attributable to any signal on the development target, where the crash
rule made every steered arm the same loop. Three readings are consistent
with that and the study separates them only partly. (1) Headroom: the seed
already reaches 60 to 70% of reachable branches, and the branches left may
need inputs a grammar-derived generator does not naturally produce. parson
is the target with the most reachable functions (40 of 144) and the one
where the oracle found something to do; tomlc99's remaining branches are
error paths a TOML grammar does not describe. (2) Author: the cheap model
failed a guard in 44 of 180 seeds, and on tomlc99 its seeds lose to a
mechanical generator, so on that target there may be nothing for a signal
to improve. (3) The signal's form: the scalar helped on parson and the
named-function variant did not, which suggests the model can act on "do
better" with a number attached but not on "cover function X" when X is a
name it has never seen the body of. The second model, whose runs were
under way when this submission was frozen, tests (2); a larger-budget arm tests (1); a C3n variant that shows
the function's source would test (3), and is the natural next condition.

**The proxy is not vindicated and not condemned.** It cannot be
distinguished from no steering on any target, so it does not earn its
place. But it is also not the reason refinement fails: on tomlc99 the
oracle does no better, and on parson the oracle's gain is one to two
points, so the ceiling the proxy was meant to approximate is itself low.
Section 5.5 measures how well it tracks coverage: moderately across
generators (rho 0.4 on the held-out targets), barely within a run's own
iterations (median rho 0.0 to 0.35), which is where the loop uses it. What the proxy arm
did have, uniquely, was the ExceptionGroup repair message (13 events, all
its own) and the collapses that went with it; Section 6 shows both to be
properties of the repair path.

**The development target.** Designing the proxy on a parser whose default
build crashes on every object was a mistake with a benefit. The mistake:
on that target no steering signal ever acted, so its rows in the family
test nothing about signals, and a reader who skipped Section 5.1 would
misread its C3n row as "naming functions is harmful". The benefit: it is a
clean demonstration that a loop's event priority (crash before signal)
can silently turn every condition into one condition, which is the kind of
confound a single-run evaluation never reveals and a replicated one does.
The pre-registration's decision to report the development target
separately is what kept it from contaminating the held-out claims.

**What Gentoo's thesis looks like from below.** Gentoo found that a strong
white-box agent's generators do not need coverage guidance at fuzz time.
Our cheap blind author's generators do not benefit from a blind signal at
synthesis time, and benefit from measured coverage on one held-out target
in three, and against the proxy only on a second.
The common reading is that the grammar, plus whatever the model knows about
the format, fixes most of the generator's reach at the first attempt. That
reading has a sharp limit on tomlc99, where a mechanical generator from the
same grammar beat every LLM condition.

**Repair policy as the actionable finding.** Every agentic loop that lets a
model fix its own code has a repair path, and ours shows a clean,
replicated failure of the "here is your code, change one thing" pattern:
the model anchors on its own output and resubmits it, recovering 2 times in
25. Re-seeding with the failure text recovers 12 in 14, and a loop that
always re-seeds produced no unusable generator in 20 runs on two targets.
This is exploratory in the registered sense and the collapse-count
difference is not established at ten replicates per cell, but the two-path
table is over 80 replicates, it replicates under the oracle arms, and its
direction is not subtle.

**Cost.** A run costs about three cents and five minutes. On the three
held-out targets it buys at most two points of coverage, and only under
measured coverage on one of them. Twenty independent seeds cost less than
one Gentoo synthesis and, on tomlc99, would be better spent on the grammar
and the adaptation note than on any refinement.

**What would change the conclusion.** A practical effect that this design
missed would need to be below about A12 0.8 (Section 5.9). A second model
family, a larger budget, a C3n that shows function bodies, and parsers with
more unreached branches are the four cheapest ways to look for it; the
second model's runs were under way when this submission was frozen
(Section 4.6), and it and the remaining Stage 2 parser are pre-specified
for the revision.

## 8. Threats to validity

**Construct.** Coverage of the parse-reachable region stands in for
bug-finding power; Section 5.4 tests the link directly on four ground-truth
bugs, but only four. "Crash" includes UBSan-detected undefined behaviour by
policy; the development target's default build aborts on every object input
for that reason (a standards violation at json.c:437), which is why it is
reported separately and why its bug builds disable that single check.

**Internal.** The loop's sanitizer build and the measurement's coverage build
are different binaries of the same source; a generator is measured on the
latter only. The served model differed from the requested alias on every call
and was constant across all batches; the two pilots that informed the design
recorded only the alias. Network outages failed four runs at their first API call across two
batches; each was rerun under the registered rule and every attempt is in
the manifest. A defect in the loop's logging, found while checking the
oracle runs, drops the recorded coverage and proxy values from an
iteration's stats file when that iteration saw a crash; on the development
target that is every iteration. The loop's behaviour was unaffected (it
steers on the live value, and the surviving score field equals it), the
run summary survives, and the RQ3 analysis recomputes the proxy score from
it; the defect is left in place because the design is frozen and is listed
for the follow-up. Draw times were measured under varying machine load; they matter little,
because every generator produces and runs its 10 000 inputs in under five
minutes, so the equal-time views coincide with the equal-n view. The
batch-drift check (seed levels of later batches against earlier ones, same
prompt) shows no shift: A12 0.43 to 0.61, p > 0.15, on every target. One cJSON
final generator (C3n replicate 2) draws its 10 000 inputs in 785 to 890 s
against the protocol's 900 s draw limit; 6 of its 20 cells timed out and
score 0 as registered, which is why that replicate's mean is 48.0 in Table
2 and why the C3n row on cJSON carries the widest interval. The bug
campaigns are time-budgeted and ran nine at a time on an eleven-core machine
under heavy load; the load was shared by every arm, so it compresses every
campaign's input count alike, but inputs-to-trigger is the more reliable of
the two trigger measures and is the one reported first.

**External.** Four small C parsers of two text formats (three of them JSON);
one model family;
one grammar source; five iterations of 500 inputs. The nulls are "no
detectable effect at this budget", and the design's sensitivity is stated
next to each (with ten replicates per arm at the observed variance, the registered test
reaches 80% power at a true A12 of about 0.82; Section 5.9). The Grammarinator depth-matched variant was
calibrated on the development target's pilot; the TOML variant was not
depth-calibrated, so on tomlc99 the Grammarinator row is the defaults only.

**Statistical.** Ten replicates per cell was fixed at registration; the
intervals are wide and are reported everywhere the point estimate is. The
mechanism analysis (Section 6) is exploratory and post hoc; C2' is its only
pre-specified test and it was run on two targets.

## 9. Related work

**Agents that write generators.** Gentoo (Vikram and Padhye, 2026) has a
Claude agent with terminal access, library source and JQF tooling
synthesise Java generators in three configurations (raw fuzzing output;
static dominator analysis with per-branch coverage; agent-ranked
predicates); five repetitions per configuration, one-hour synthesis cap,
three-hour campaigns, Mann-Whitney at 0.05. Agent generators beat
human-written ones on four of seven libraries, and coverage-guided mutation
added only −0.1% to +2.0% for them versus about 40% for human generators.
Our A5 arm is a direct probe of their thesis in the opposite regime (blind,
cheap, synthesis-time). Their stated threats (Java only, one model,
possible memorisation of library source, fixed-time campaigns) motivated
our C targets, sanitizers, anonymised prompts and input-count budgets; one
model remains a threat we share.

**Evolving fuzzers with an LLM.** ELFuzz (Chen, Dolan-Gavitt and Lin,
USENIX Security 2025) evolves whole fuzzer programs under an edge-coverage
fitness with CodeLlama-13B over 20 to 55 hours per target, against
Grammarinator, ISLa, ISLa with ISLearn and GLADE on jsoncpp, libxml2, re2,
SQLite, CPython, cvc5 and librsvg, ten repetitions, no significance tests.
G2Fuzz (Zhang et al., USENIX Security 2025) has the LLM write and mutate
Python generators for binary formats, hybridised with AFL++. Both use
coverage as the fitness; neither asks whether the fitness is needed. Both
expect Grammarinator on the same grammar as the baseline, which is why it
is ours.

**LLMs producing inputs rather than generators.** Fuzz4All (Xia et al.,
ICSE 2024) prompts a model for inputs directly with an autoprompting loop,
on compilers. Ackerman and Cybenko (FUZZING 2023, registered report) fuzz
parsers from specification ambiguity. Park and Yun (2026) survey agentic
fuzzing and criticise single extended runs as evaluation; our replicate
design and Section 5.1 are an answer to that criticism.

**Evaluation methodology.** Klees et al. (CCS 2018) set the repetition and
statistics bar for fuzzing evaluations; we follow it with ten replicates,
effect sizes with bootstrap intervals, permutation tests and a
pre-registered analysis, and we add the design's measured sensitivity,
which they recommend and evaluations rarely report.

## 10. Conclusion

At a budget of five rounds and 2 500 executed inputs, with a cheap model
and no access to the parser, the generator an LLM writes from a grammar in
its first attempt is most of the generator you get. Telling it nothing or
structural facts about its own outputs changed the outcome by about one
point on the held-out parsers; measured coverage added one to two points on
one of them and nothing detectable on the other two; naming the functions to cover helped
less than the number. Whether that first attempt beats a mechanical
grammar generator depends on the grammar. The one way the loop visibly
fails, handing back a generator that cannot run, is a property of how it
repairs broken code, and a policy that never shows the model its own failed
code removes it. On the development target a crash-first rule made every
steered arm the same loop, which only ten replicates per cell could show.
Everything needed to check these statements is in the artifact. Three
extensions are pre-specified and costed: one more parser (libexpat), a
second model family (whose runs were under way when this submission was
frozen and are excluded from it, Section 4.6), and an oracle that shows
the model the function it is asked to cover.

The use of large language models in this work is declared in Section 4.7.

## Statements and Declarations

**Competing interests.** The authors have no financial or non-financial
interests directly or indirectly related to this work.

**Funding.** No external funding was received. API usage was paid by the
authors (about 5 USD of DeepSeek credit, and about 1.4 USD of OpenAI
credit on second-model runs that are excluded from this submission,
Section 4.6).

**Data availability.** Every run (prompts, responses, generators,
per-iteration statistics, provenance), every measured cell with its
input-set hash, the campaign rows, the analysis scripts that produce every
table and figure, the pre-registration and its amendment history, and the
vendored parser sources at their pinned commits are in the artifact
repository named in Section 10; the git history is the timestamp of the
pre-registration.

**Ethics.** The study involved no human participants and no animals.

**Use of large language models.** Declared in Section 4.7.

## References

The first seven entries were read from the paper's page during the
literature pass recorded in paper/base-paper.md and carry identifiers. The
last three are standard method and tool references added from memory and
MUST be checked against their sources before submission.

- Ackerman, J., and Cybenko, G. (2023). Large language models for fuzzing
  parsers (registered report). FUZZING 2023. ACM. https://doi.org/10.1145/3605157.3605173
- Chen, C., Dolan-Gavitt, B., and Lin, Z. (2025). ELFuzz: Efficient input
  generation via LLM-driven synthesis over fuzzer space. USENIX Security
  2025. https://doi.org/10.48550/arXiv.2506.10323
- Klees, G., Ruef, A., Cooper, B., Wei, S., and Hicks, M. (2018). Evaluating
  fuzz testing. ACM CCS 2018. https://doi.org/10.1145/3243734.3243804
- Padhye, R., Lemieux, C., Sen, K., Papadakis, M., and Le Traon, Y. (2019).
  Semantic fuzzing with Zest. ISSTA 2019.
- Park, S., and Yun, I. (2026). Agentic fuzzing: opportunities and
  challenges. https://doi.org/10.48550/arXiv.2605.10074
- Vikram, V., and Padhye, R. (2026). Fuzzing with agents? Generators are all
  you need. https://doi.org/10.48550/arXiv.2604.01442
- Xia, C. S., Paltenghi, M., Le Tian, J., Pradel, M., and Zhang, L. (2024).
  Fuzz4All: Universal fuzzing with large language models. ICSE 2024.
- Zhang, et al. (2025). G2Fuzz. USENIX Security 2025. https://doi.org/10.48550/arXiv.2501.19282
- Hodovan, R., Kiss, A., and Gyimothy, T. (2018). Grammarinator: a
  grammar-based open source fuzzer. A-TEST 2018.
  https://doi.org/10.1145/3278186.3278193 (Tool used at version 26.1; the pinned
  generator and every parameter are in the artifact.)
- MacIver, D. R., Hatfield-Dodds, Z., et al. (2019). Hypothesis: a new
  approach to property-based testing. Journal of Open Source Software 4(43). https://doi.org/10.21105/joss.01891

