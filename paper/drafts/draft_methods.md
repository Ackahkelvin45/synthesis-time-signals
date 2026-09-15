# Draft: Sections 3 (Approach), 4 (Experimental design), 7 (Threats to validity). Third draft, 2026-09-15, revised to the blueprint.

---

## 3. Approach: a synthesis-time refinement loop for LLM-authored generators

The core idea is to hold a refinement loop fixed and vary one thing: what
the model is told about the last run. The loop takes a formal grammar and
a short adaptation note, asks a language model for a Hypothesis strategy
that generates strings in the grammar's language, runs the strategy against
the parser under sanitizers, summarises the run, asks the model for exactly
one change, and repeats. Figure 1 shows the loop. Every arm shares the
prompts, the guards that keep a broken generator from consuming the budget,
the repair paths, and the budget of five iterations of 500 executed inputs.
The arms differ along a single axis, the contents of the run summary and
the edit instruction derived from it: nothing beyond validity (A5 no
steering), a structural proxy that needs no instrumentation (C2 proxy),
measured branch coverage (C3s coverage), or measured coverage with the
names of the least-covered functions (C3n coverage+names). Table 1 sets
the four arms side by side; the subsections define the shared loop, the
guards, and then each signal.

![The refinement loop. Every arm shares the seed prompt, the guards, the repair paths and the budget; the arms differ only in what the run summary contains and the edit instruction derived from it.](figures/f0_loop.pdf)

**Table 1. The four arms and the follow-up condition.** Everything not listed is identical: the seed prompt, the adaptation note, the AST screen, the acceptance gate, the in-iteration repair, five iterations of 500 inputs, temperature 0.7.

| arm | what the model sees after a run | next-edit instruction | rollback and best iteration | repair after a gate failure |
|-----------|----------------------------|------------------------|------------------------|-------------------|
| A5 no steering | nothing ("no run feedback is provided") | "make it a better fuzzer for this grammar" | last working generator; no score | in place |
| C2 proxy | the structural summary of its own outputs and the parser's exit codes | one of: add or up-weight a production, generate deeper, fix a feature, broaden, revert | by proxy score | in place |
| C3s coverage | branch and region coverage of the reachable region, two numbers | "increase branch coverage" | by measured coverage | in place |
| C3n coverage+names | the two numbers and the five least-covered reachable functions by name | "cover function F" | by measured coverage | in place |
| C2′ re-seed repair (follow-up) | as C2 proxy | as C2 proxy | as C2 proxy | re-seed from the grammar with the failure text |

### 3.1 The shared loop

The grammar is the ANTLR grammars-v4 grammar for the format, used verbatim.
The adaptation note records where the library's accepted language deviates
from that grammar: json-parser accepts a trailing comma and duplicate keys,
tomlc99 accepts leading zeros and calendar-invalid dates. It is produced by
running a fixed set of hand-written probe inputs through the harness
against a strict reference parser, is human-authored, and is identical
across conditions. The seed prompt asks for a strategy that covers the
grammar's recursive productions with bounded recursion, deliberately
produces edge cases (empty containers, deep nesting near the parser's
limit, extreme numbers, escapes, near-valid malformed inputs), and returns
a string. The model never sees the parser's name, source, API, error
messages or coverage. Its observable world is the grammar, the note, the
exit-code class of each input it generated (valid, rejected, crash), its
own generated inputs, and the feedback the arm supplies. Five iterations,
500 executed inputs per iteration, temperature 0.7, no request seed.

### 3.2 Guards and repair paths, identical in every arm

The model is a high-variance author, so four guards keep a broken
generator from consuming the budget. An AST screen rejects disallowed
imports and attribute access before the module is executed. An acceptance
gate draws 90 inputs under three PRNG seeds and rejects a generator that
raises on any seed or has fewer than 5% of its inputs accepted by the
parser. One in-iteration repair re-prompt carries either the exception
text or the acceptance rate. And rollback returns to an earlier generator
when a change made things worse. A generator that fails the gate after its
repair is kept as the loop's current generator, because the registered
rule is that gated iterations count as they happened, and the next
iteration's prompt repairs it again.

Which repair prompt the model receives depends on how the generator
failed, and the distinction matters for Section 6. After a build
rejection, when the module does not import or fails the screen, the loop
discards the code and re-seeds from the grammar with the rejection text
appended. After a gate failure, when the module builds but raises on a
draw or produces too few accepted inputs, the loop re-prompts in place. It
shows the model its own failed module in full, states that no run feedback
is available, and instructs it to make exactly one change to fix the named
error and change nothing else. The replicate of Section 1.1 took the
second path five times.

One more rule matters for reading the results. A crash is the loop's
highest-priority event. When an iteration's run produced a new crash
signature, the next edit is "mutate structurally around the crashing
input" regardless of the arm, that iteration becomes the best so far, and
the regression check is skipped, because the loop must not roll back away
from a crash. On a parser whose default build crashes on every object
input, which the development target does (Section 4.2), this rule fires
every iteration; Section 5.1 reports what that did to every steered arm
there.

### 3.3 The proxy signal (C2 proxy)

The proxy is a structural summary of the generator's own outputs and the
parser's verdicts, computed without instrumentation or source. The
intuition is that a generator which produces every grammar production in
accepted inputs, produces many distinct accepted structures, and pushes
nesting toward the parser's depth limit is exploring the parser, and that
these facts can be read from the inputs and the exit codes alone.

Concretely, after each run the loop parses every generated input with the
format's own feature extractor and records five things about the accepted
inputs. The set of grammar productions that appeared; the production
universe minus that set is the production gap. The number of distinct
accepted structure fingerprints, where a fingerprint is the set of
productions present and a bucketed nesting depth; the count is the
novelty. The fraction of accepted inputs whose nesting depth falls in the
deep band below the parser's limit, the cap mass. The acceptance rate. And
six single-feature probes, each a valid baseline input perturbed by
exactly one feature and run against the parser and a strict reference.
The score is

score = 5 x (productions accepted) + novelty + 20 x cap mass,

and it drives rollback and best-iteration selection: an iteration whose
score falls more than max(2, 10% of the best score) below the best is
rolled back. A fixed decision procedure maps the summary to one named
edit, in priority order. Revert the last edit if acceptance rose by more
than 0.05 while novelty fell by more than 4, the signature of a generator
that got blander. Otherwise add or up-weight the first production in the
gap. Otherwise generate nesting toward the deep band if the cap mass is
below 0.05. Otherwise fix the feature whose probe the parser accepted less
than 20% of the time. Otherwise broaden exploration. The crash rule of
Section 3.2 sits above all of these.

A recorded iteration shows the procedure at work. In replicate 2 of the
proxy arm on parson, the first draft's run produced 210 accepted and 140
rejected inputs (acceptance 0.60), all ten productions of the JSON grammar
in accepted inputs (gap empty), 24 distinct accepted structures, and 1.9%
of accepted inputs in the deep band, for a score of 74.4. The gap was
empty and the cap mass was below the 0.05 target, so the instruction for
iteration 2 was "generate nesting toward the cap, target depth 1500 to
2048". The model's change raised acceptance to 0.72 but cut the novelty to
16, the score fell to 66.5, below the tolerance band around 74.4, and the
loop rolled back to the first draft. The proxy has no access to the
parser's coverage; Section 5.5 measures how well it tracks it.

### 3.4 The control and the oracle signals

**A5 no steering.** The model receives no run summary; the refine prompt
says that no run feedback is provided and asks it to make the strategy a
better fuzzer for this grammar. Rollback is to the last working generator,
never to a score-best one, because there is no score. A5 does receive the
validity feedback of Section 3.2, so it is named "no steering", not "no
feedback".

**C3s coverage and C3n coverage+names.** The proxy score is replaced,
everywhere the proxy acts, by branch coverage of the parse-reachable
region measured on the iteration's 500 inputs with an instrumented build.
Under C3s the model sees two numbers, branch and region coverage, and the
instruction "increase branch coverage; reach parser code the current inputs
never execute". Under C3n it additionally sees the five least-covered
reachable functions by name and the instruction "cover function F", where
F has 0% branch coverage; names are not anonymised, so this arm is
white-box in the smallest possible way. Both arms record the proxy summary
as well, which yields the RQ3 validity data at no extra cost.

**C2′ re-seed repair (follow-up).** Identical to C2 proxy except that a
generator failing the gate is never shown back to the model: the
in-iteration repair, and every prompt while the held generator is a failed
one, is the grammar seed prompt with the failure text appended. Added
after the mechanism analysis of Section 6 and outside the registered
confirmatory family.

### 3.5 Design decisions

We chose a blind, single-edit loop over an open-ended agent for two
reasons. The first is attribution. An agent with terminal access and
source interleaves reading, running and editing in an order it chooses,
and that freedom is a strength when the goal is the best generator, but it
makes the effect of any one signal inseparable from everything else the
agent did. A loop that shows the model one summary and asks for one named
change makes the signal the only thing that differs between arms, which is
what a comparison needs. The second is the regime. The proxy exists
because a practitioner with a grammar and a parser binary has no
instrumented build; a loop that could read source or coverage would not
test whether that practitioner's loop can be steered.

We chose the crash-first rule, the in-place repair and the gate thresholds
before the first replicate and did not change them afterwards, because the
design was frozen at registration. Two of them turned out to matter more
than the signal: the crash rule turned every steered arm on the development
target into the same loop (Section 5.1), and the in-place repair is the
mechanism behind every collapsed replicate (Section 6). We report both as
findings rather than fixing them, and the one intervention we did run,
C2′, was pre-specified after the mechanism analysis and is reported
outside the family.

## 4. Experimental design

Section 3 fixed the loop and named the axis along which its arms differ.
This section states how the comparison was registered, on which parsers,
with what outcome, and how it is analysed.

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
run after the Stage 1 analysis, Section 4.6). Table 2 gives their sizes.
cJSON v1.7.18 is parsed through its length-taking entry point with an
exact-length buffer, so that the harness can reach the over-read of
Section 4.5 in the bug build; its adaptation note and prompts are
anonymised so that no library name reaches the model.

<!-- TABLE:T1 -->

Each target has three kinds of build. The loop uses a sanitizer build,
AddressSanitizer and UndefinedBehaviorSanitizer at -O0 with recovery
disabled, so any detected memory or undefined-behaviour error aborts the
process; the harness reports valid, rejected, skipped or crashed by exit
code, and the loop never sees the parser's own error text. Measurement uses
a separate coverage build with clang's source-based instrumentation, which
the loop never touches except under the oracle arms, where it supplies the
in-loop coverage number. json-parser, tomlc99 and cJSON also have
sanitizer builds at pinned pre-fix commits of known bugs (Section 4.5).
Absolute coverage is not comparable across targets; every comparison is
within a target.

The primary outcome's denominator is the parse-reachable region: the
functions reachable from the harness entry point in the static call graph,
unioned with any function observed covered by any condition. It is committed
per target and its hash is recorded in every run and every measurement.

### 4.3 Conditions, replicates, and order

Loop conditions C2 proxy, A5 no steering, C3s coverage and C3n
coverage+names, ten independent replicates each per target (160 runs), plus
C2′ re-seed repair on json-parser and tomlc99 (20 runs). Fixed generators,
measured on the three Stage 1 targets: random text, Grammarinator 26.1 on
the identical grammar (defaults, and with recursive alternatives up-weighted
to match the mean nesting depth of the development target's pilot seed),
and each replicate's own seed generator. Model: deepseek-chat as requested;
the provider served deepseek-flash (DeepSeek-V4.1-Flash) on every call,
recorded per call, and the paper reports the served identifier. Run order
was interleaved within each phase so that provider drift is orthogonal to
treatment; the phase boundaries are disclosed. In total the study comprises
180 loop runs, 4.63 USD of API spend, 7 560 measurement cells of ten
thousand inputs each, 604 loop-internal strategies measured for RQ3,
and 173 thirty-minute bug campaigns.

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

### 4.6 Research questions and analysis

The central question, what a synthesis-time refinement loop should tell a
cheap, blind model, is split into five registered questions. RQ2 is the
confirmatory core; the others are secondary and descriptive, and are
labelled exploratory in every table.

- RQ1 (authorship against the grammar alone): does the model's first-draft
  generator beat random text and Grammarinator on the identical grammar?
  Measured on the primary outcome at the seed.
- RQ2 (the signal; confirmatory): which of the four signals makes refinement
  work? H1 compares the proxy with no steering, H2 compares the coverage
  oracle, with and without function names, with the proxy; the per-replicate
  final-minus-seed delta says whether any arm moves its own seed.
- RQ3 (proxy validity): does the proxy score track measured coverage, across
  generators and within one run's iterations?
- RQ4 (bugs): do the final generators reach known bugs within a fixed
  budget, and do the fixed generators?
- RQ5 (the author): how does the model fail, and what does the loop do
  about it? The mechanism analysis of Section 6 grows out of RQ5.

The unit of analysis is the loop replicate; draw seeds are averaged within a
replicate first. Per target: H1 (C2 vs A5) and H2 (C3s vs C2, C3n vs C2) as
differences of replicate means with a two-sample permutation test (20 000
shuffles) and Vargha-Delaney A12 with a 5 000-resample percentile bootstrap
interval, Holm-corrected within target over the confirmatory family; the
per-replicate delta (final minus seed) with an exact sign-flip test. Bands,
fixed at registration: A12 at or beyond 0.64 (or 0.36) with an interval
excluding 0.5 is a practical difference; 0.56 to 0.64 small; otherwise
negligible. Targets are replications, not pooled. Everything outside the
confirmatory family (RQ1, RQ3, RQ4, the mechanism analysis, C2′) is
exploratory and is labelled so in every table.

**Deviations from the registered design.** C3s on json-parser and parson,
and C3n on all three Stage 1 targets, were run as blocks after phases 1a and 1b
rather than interleaved with them, so provider drift is not orthogonal to
those cells (the served model identifier was constant across every batch);
C2′ was added after the mechanism analysis and is outside the confirmatory
family. The first Stage 2 target, cJSON, was run in full (four arms, ten
replicates) after the Stage 1 analysis, as the registration's Stage 2
allows, and is reported in every table beside the Stage 1 targets; its
fixed references (RQ1), its RQ3 cells and its bug campaigns were not
measured before the submission cutoff. The second Stage 2 target
(libexpat), the AFL++ reference row and the second model (gpt-5-mini on
tomlc99, arms C2, A5 and C3s) were not completed: the second model's batch
stood at 18 of 30 runs when the submission was frozen, and those runs are
excluded from every table and kept in the artifact. The registered Stage 1
budget was 4.00 USD; 3.80 USD was spent on the 140 Stage 1 and C2′ runs
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

## 7. Threats to validity

**Construct.** Coverage of the parse-reachable region stands in for
bug-finding power; Section 5.6 tests the link directly on four ground-truth
bugs, but only four. "Crash" includes UBSan-detected undefined behaviour by
policy; the development target's default build aborts on every object input
for that reason (a standards violation at json.c:437), which is why it is
reported separately and why its bug builds disable that single check.

**Internal.** The loop's sanitizer build and the measurement's coverage build
are different binaries of the same source; a generator is measured on the
latter only. The served model differed from the requested alias on every call
and was constant across all batches; the two pilots that informed the design
recorded only the alias. Network outages failed four runs at their first API
call across two batches; each was rerun under the registered rule and every
attempt is in the manifest.

A defect in the loop's logging, found while checking the oracle runs, drops
the recorded coverage and proxy values from an iteration's stats file when
that iteration saw a crash; on the development target that is every
iteration. The loop's behaviour was unaffected, because it steers on the
live value and the surviving score field equals it, the run summary
survives, and the RQ3 analysis recomputes the proxy score from it. The
defect is left in place because the design is frozen and is listed for the
follow-up.

Machine load is the remaining internal threat. Draw times were measured
under varying load; they matter little, because every generator produces
and runs its 10 000 inputs in under five minutes, so the equal-time views
coincide with the equal-n view. The batch-drift check (seed levels of later
batches against earlier ones, same prompt) shows no shift: A12 0.43 to
0.61, p > 0.15, on every target. One cJSON final generator (C3n replicate
2) draws its 10 000 inputs in 785 to 890 s against the protocol's 900 s
draw limit; 6 of its 20 cells timed out and score 0 as registered, which is
why that replicate's mean is 48.0 in Table 3 and why the C3n row on cJSON
carries the widest interval. The bug campaigns are time-budgeted and ran
nine at a time on an eleven-core machine under heavy load; the load was
shared by every arm, so it compresses every campaign's input count alike,
but inputs-to-trigger is the more reliable of the two trigger measures and
is the one reported first.

**External.** Four small C parsers of two text formats (three of them JSON);
one model family; one grammar source; five iterations of 500 inputs. The
nulls are "no detectable effect at this budget", and the design's
sensitivity is stated next to each (with ten replicates per arm at the
observed variance, the registered test reaches 80% power at a true A12 of
about 0.82; Section 5.9). The Grammarinator depth-matched variant was
calibrated on the development target's pilot; the TOML variant was not
depth-calibrated, so on tomlc99 the Grammarinator row is the defaults only.

**Statistical.** Ten replicates per cell was fixed at registration; the
intervals are wide and are reported everywhere the point estimate is. The
mechanism analysis (Section 6) is exploratory and post hoc; C2′ is its only
pre-specified test and it was run on two targets.
