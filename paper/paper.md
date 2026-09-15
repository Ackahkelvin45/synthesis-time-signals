# Synthesis-time feedback for LLM-authored grammar-based generators: a
replicated comparison of no steering, a structural proxy, and a coverage
oracle on C parsers

## Abstract

A language model can turn a formal grammar into an input generator for a
parser, and a loop can ask it to refine that generator over several rounds.
What should the loop tell the model? Prior loops steer with coverage and are
evaluated in single runs with strong models. We ask what a synthesis-time
loop can be told when the model is cheap and blind to the parser, and
whether telling it anything helps. We compare four signals in an otherwise
identical loop: no steering, a structural proxy computed from the
generator's own outputs and the parser's exit codes, and a coverage oracle
that measures branch coverage of the parser's reachable region each round,
with and without the names of the least-covered functions. The study is
pre-registered, with one primary outcome, ten independent replicates per
cell, and four C parsers in two text formats. Four results. No comparison
in the confirmatory family survives correction; measured coverage produced
a detectable gain on one held-out parser before correction and beat the
proxy on a second, and naming the functions to cover did worse than giving
the number. Five rounds of refinement move the first draft by one to two
coverage points. Whether the first draft beats Grammarinator on the
identical grammar depends on the target: a tie, ahead, and clearly behind
on TOML. The loop's one visible failure, an unusable generator, traces to
its repair policy rather than its signal: shown its own failed code, the
model resubmits it, recovering 2 times in 25; re-seeded from the grammar
it recovers 12 in 14, and a re-seeding loop produced no unusable generator
in twenty runs. At three cents a run, the grammar-seeded first draft is
most of the result. We release every run, prompt, input-set hash and script.

**Keywords.** fuzzing; grammar-based test generation; large language models; property-based testing; pre-registered study; replication.

## 1. Introduction

Parsers of structured text are hard to fuzz with random bytes. Almost every
random input fails the first validation check, so the deeper parsing logic,
where the interesting bugs live, is rarely executed (Zalewski 2014; Böhme
et al. 2016). Grammar-based generation is the standard answer: a generator
that expands the format's grammar produces inputs that are in the language,
or close to it, and reaches code that mutation of raw bytes does not
(Hodován et al. 2018; Padhye et al. 2019). On the four parsers in this
paper, random text reaches 17 to 26 points of our coverage outcome and a
grammar-seeded generator 50 to 66 (Section 5.4). The cost of that gain is
authorship. A good generator encodes the format's structure and the
parser's quirks, and writing and maintaining one is work that most projects
never do.

Language models have made that authorship cheap. Recent systems have a
model write the generator from a grammar, a specification or the parser's
source, and then improve it over several rounds: ELFuzz evolves whole
generator programs under a coverage fitness (Chen et al. 2025), G2Fuzz has
the model write and rewrite Python generators for binary formats (Zhang et
al. 2025), and Gentoo gives a coding agent the library source, terminal
access and predicate-level coverage reports and lets it refine a Java
generator for an hour (Vikram and Padhye 2026). Gentoo's central finding is
about fuzz time: once a strong agent has encoded the target's structure
into the generator, coverage-guided mutation adds almost nothing on top.

Every one of these loops is driven by a signal. The model proposes a
generator, the loop runs it, summarises the run, and asks for a change, and
what the summary contains is the loop's design. The signal in prior work is
coverage in some form: edge coverage as a fitness, a stalled AFL++ run, a
list of unreached predicates. That choice carries an assumption that has
not been tested: that a synthesis-time loop needs a coverage-derived signal
at all, and that the refinement it drives is what separates the final
generator from the first draft. The evaluations that support it are single
or few runs with strong models, which cannot separate the effect of the
signal from the variance of the author.

The assumption matters in the regime most practitioners are in. They have
a grammar and a parser binary, not an instrumented build and a ten-dollar
agent. The generator is a short program written by a cheap model that never
sees the parser's source, its error messages or its coverage. The loop has
to steer it with whatever it can observe: whether the generator runs,
which of its inputs the parser accepts, and the generator's own outputs.
In that regime the question is what the loop should tell the model, and
whether telling it anything changes the generator it hands back.

We answer that question with a pre-registered, replicated comparison. The
loop is fixed: grammar in, Hypothesis strategy out, five rounds of one
change each, the same validity guards in every arm. Only the signal varies.
The model is told one of four things. Nothing beyond whether its
generator runs and produces accepted inputs (A5 no steering). A structural
proxy computed from the generator's own outputs and the parser's exit
codes, designed for this setting (C2 proxy). Measured branch coverage of
the parser's reachable region (C3s coverage). Or that number with the
names of the five least-covered functions (C3n coverage+names). The proxy
is the object of study; the oracle is the ceiling it is measured against.
Ten independent replicates per arm on four C parsers, with one registered
primary outcome and the analysis code frozen before the first run, give
the design enough power to detect a large effect and the honesty to report
a small one as what it is. The answer, in brief: no signal moves the first draft by more
than one to two coverage points, none survives correction, and the loop's
only visible failure comes from how it repairs broken code, not from what
it is told.

### 1.1 A motivating example

Consider replicate 6 of the proxy arm on parson, a JSON parser the model
never saw. The model's first draft was a 173-line Hypothesis strategy that
built deeply nested arrays by wrapping an inner value in brackets a chosen
number of times. The inner value was a strategy object, not a string, so
the first draw raised a TypeError: a string cannot be concatenated with a
strategy. The loop's acceptance gate caught it, and the next prompt showed
the model its own module in full with one instruction: make exactly one
change to fix this TypeError, change nothing else.

The model made one change. It re-wrapped an unrelated lambda over three
lines; the module was 99.9% identical to the failed one and raised the
same error. The following prompt was the same again. This time the model
rewrote the right function but left the strategy object where a string was
needed, and the error persisted. The last two rounds returned the module
byte for byte. After five iterations the loop handed back a generator that
could not draw a single input, and the replicate scored zero. In the
replicate that collapsed on tomlc99 the model resubmitted an identical
385-line module four times in a row.

Nothing in this trace depends on the steering signal. The proxy never got to
act, because a gated generator produces no run to summarise. What decided
the outcome was the repair path: the model was shown its own failed code
and asked to change one thing, and it anchored on what it had written. The
study's mechanism analysis finds this pattern in every collapsed replicate,
measures how often each repair path recovers, and tests the one change that
removes it (Section 6).

### 1.2 Contributions

We investigate whether a synthesis-time refinement loop for LLM-authored
generators needs a steering signal, and what a loop for a cheap, blind
model can be told. The design gives a fixed loop four signals, holds
everything else constant, and measures the final generator on fresh draws
the loop never saw, ten replicates per cell, on four C parsers of two text
formats, against random text and Grammarinator on the identical grammar.
Our evaluation yields four results. First, no comparison in the registered
family survives correction. Measured coverage produced a practical-band
gain on one held-out parser before correction (A12 0.76 against the proxy)
and beat the proxy but not no steering on a second; the proxy never beat
no steering. Naming the functions to cover did worse than giving the
number, suggesting that a cheap model can act on "do better" with a number
attached but not on the name of a function it has never seen (Section 5.2).
Second, five rounds of refinement move the first draft by one to two
coverage points in either direction, so the grammar-seeded first draft is
most of the generator the loop delivers. Whether that first draft beats
Grammarinator on the identical grammar depends on the target: a tie,
ahead, and clearly behind on TOML (Sections 5.3 and 5.4). Third, the loop's
only visible failure, an unusable generator, is a property of its repair
path and not of its signal. Shown its own failed code the model recovers 2
times in 25; re-seeded from the grammar it recovers 12 in 14; the pattern
holds under the oracle arms; and a pre-specified re-seeding loop produced
no unusable generator in 20 runs on two targets (Section 6). Fourth, on the
development target a crash-first event rule silently turned every steered
arm into the same loop, a confound that ten replicates per cell exposed and
a single-run evaluation would not have (Section 5.1). A failure taxonomy of
the author's errors, the design's measured sensitivity, ground-truth bug
campaigns, and an artifact with every run, prompt, input-set hash and
script complete the study.

Three limits on these claims are stated now and argued later. The loops
found no bug that the seeds' class of generator does not also find, and on
the development target the proxy loop found the known bugs less often than
no steering did (Section 5.6). The proxy does track coverage when different
generators are compared (rho about 0.4 on the held-out targets), but not
when one run's own iterations are compared, which is where the loop uses
it (Section 5.5). And every null result is a null at this budget and with
this model; Section 5.9 states what effect size the design could have
detected.

## 2. Background

### 2.1 Grammar-based generators and property-based strategies

A grammar-based generator produces inputs by expanding a grammar's
productions, so every output is in the language or one edit away from it.
Grammarinator is the standard tool for ANTLR grammars: it compiles a .g4
file into a generator class and samples derivations under a depth limit and
alternative weights (Hodován et al. 2018). It is the baseline the
LLM-generator literature is expected to beat on the same grammar, and the
one we use. Property-based testing libraries reach the same goal from the
other direction. In QuickCheck's lineage (Claessen and Hughes 2000) the
developer writes a generator as a small program that describes how to draw
values, and the library draws from it under a seed. In Hypothesis (MacIver
et al. 2019) that program is a strategy, composed from primitives such as
text, integers, lists and bounded recursion, and drawn by a runtime that
also handles shrinking and health checks.

The generators in this paper are Hypothesis strategies written by a
language model. Two properties of that setting recur in the results. A
strategy is an object that draws values, not a value, and confusing the two
is one of the model's most frequent errors: the example of Section 1.1
concatenated a strategy to a string. And a strategy that raises on some
draws still runs on others, so "usable" is a matter of degree, which the
measurement's draw protocol handles by dropping raising chunks and counting
them. What the approach needs from this concept is a generator that is a
short program, judged by whether it draws and by what the parser says about
what it draws.

### 2.2 Refinement loops and their signals

An LLM-authored generator is rarely used as written. The systems of Section
1 wrap authorship in a loop: the model proposes a generator, the loop runs
it against the target, summarises the run, and asks the model for a change.
Everything the model learns about the target after its first draft arrives
through that summary, so the summary's contents are the loop's steering
signal and the main design decision. ELFuzz scores each generator variant
by the edge coverage of the inputs it produces and keeps the fitter one
(Chen et al. 2025). G2Fuzz re-invokes the model when the coverage-guided
fuzzer stalls (Zhang et al. 2025). Gentoo shows the agent which
high-dominance predicates its inputs fail to satisfy (Vikram and Padhye
2026). Each signal is coverage in some form, and each requires an
instrumented build of the target.

A loop has two other parts that decide what the model is told. When the
proposed generator does not run, the loop must repair it, and the repair
prompt is also a signal: it can show the model its own failed code, or the
failure text alone. And when a change makes the generator worse, the loop
must decide whether to keep or discard it, which needs a score. Prior work
folds all three into coverage. Our approach keeps the loop, the guards and
the repair prompts identical across arms and varies only what the summary
contains, from nothing, through a proxy that needs no instrumentation, to
measured coverage.

### 2.3 Measuring a generator, and why the replicate is the unit

A generator's quality is the code it reaches. We measure branch coverage
of the parser's parse-reachable region, the functions reachable from the
harness entry point in the static call graph, so that unreachable
utilities do not dilute the denominator. We summarise the coverage curve
by its area up to ten thousand inputs on draw seeds the loop never used,
so that a generator is credited for how fast it reaches code as well as
how much. Coverage is a proxy for bug-finding power; Section 5.6 tests
that link on four known bugs.

The unit of analysis is the loop replicate, not the draw, because the
model is a high-variance author: 44 of our 180 first drafts failed a guard,
and the pilot's single-run score trajectory did not reproduce. Fuzzing
evaluations that compare configurations from one run each are unreliable
for the same reason (Klees et al. 2018; Böhme et al. 2022), and the remedy
is the same: independent repetitions, an effect size with an interval, and
a test that does not assume a distribution (Arcuri and Briand 2011). We
use the Vargha-Delaney A12 statistic (Vargha and Delaney 2000), a
permutation test on the difference of replicate means, and Holm's
correction within each target's confirmatory family. What the approach
needs from this section is one primary outcome fixed before the first run
and a design whose sensitivity can be stated next to every null.

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

**Table 2. Targets**

| target | source | lines | functions | parse-reachable functions | grammar (grammars-v4) | ground-truth bug builds | role |
|-------|----------|-----|--------|----------|--------------|--------------|-----------|
| json-parser | json.c | 1057 | 10 | 9 | JSON.g4 | issue68, issue78 | development (in-sample) |
| parson | parson.c | 2486 | 144 | 40 | JSON.g4 | none | held out |
| cjson | cJSON.c | 3143 | 112 | 13 | JSON.g4 | cve-2023-53154 | held out (Stage 2) |
| tomlc99 | toml.c | 2392 | 82 | 53 | TomlLexer.g4, TomlParser.g4 | issue50, recursion | held out |


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

## 5. Results

Section 4 registered five questions. We answer the confirmatory one first,
RQ2, because everything else is read in its light: 5.1 explains why the
development target's rows test no signal, 5.2 gives the family and 5.3 the
refinement delta. RQ1 (5.4), RQ3 (5.5), RQ4 (5.6) and RQ5 (5.7) follow,
then cost (5.8) and the design's sensitivity (5.9). Table 3 holds the
per-arm numbers every subsection draws on: for each target and arm the
final generator's level on the primary outcome, the number of collapsed
replicates, the per-replicate delta against the seed, and the last working
iteration's level where it differs from the final. Figure 2 shows the
coverage curves behind those numbers. Each subsection ends with its answer.

**Table 3. Final-generator level and refinement delta per target and arm**

Primary outcome auc_branch_reach (10^4 inputs x 20 draw seeds per replicate; failed cells and collapsed finals score 0). Mean ± 95% CI over ten replicates (median); coll. = collapsed replicates; last working = the last working iteration's level where it differs from the final (n = replicates where it differs). Δ = final − seed per replicate, exact sign-flip test; replicates whose seed generator failed but whose final works are excluded from Δ and counted under seed failed.

| target | arm | final | coll. | Δ final − seed | up / down | sign-flip p | seed failed | last working |
|--------|--------------|-----------------|-----|--------------|-------|--------|-------|-----------|
| json-parser | C2 proxy | 51.0 ± 19.3 (63.9) | 2 | -1.02 ± 0.81 | 2 / 6 | 0.031 | 0 | - |
| json-parser | A5 no steering | 63.7 ± 2.8 (64.6) | 0 | +0.15 ± 1.16 | 6 / 4 | 0.768 | 0 | - |
| json-parser | C3s coverage | 48.8 ± 18.7 (59.4) | 2 | -1.60 ± 1.70 | 2 / 6 | 0.062 | 0 | - |
| json-parser | C3n coverage+names | 54.9 ± 14.0 (61.5) | 1 | -9.20 ± 13.62 | 0 / 10 | 0.002 | 0 | - |
| json-parser | C2′ re-seed repair | 63.9 ± 1.3 (64.4) | 0 | -1.32 ± 1.40 | 2 / 7 | 0.074 | 0 | - |
| parson | C2 proxy | 60.9 ± 15.4 (67.1) | 1 | +0.89 ± 0.50 | 7 / 1 | 0.016 | 0 | - |
| parson | A5 no steering | 66.3 ± 1.6 (66.7) | 0 | +0.54 ± 0.75 | 7 / 2 | 0.160 | 0 | - |
| parson | C3s coverage | 69.1 ± 1.1 (69.4) | 0 | +1.59 ± 0.86 | 8 / 2 | 0.008 | 0 | 68.6 (n 1) |
| parson | C3n coverage+names | 66.0 ± 1.3 (65.8) | 0 | -0.16 ± 1.48 | 5 / 5 | 0.797 | 0 | - |
| tomlc99 | C2 proxy | 52.9 ± 13.9 (57.4) | 1 | -0.01 ± 1.10 | 2 / 4 | 1.000 | 1 | - |
| tomlc99 | A5 no steering | 60.2 ± 3.4 (59.8) | 0 | +1.80 ± 2.33 | 6 / 3 | 0.121 | 1 | - |
| tomlc99 | C3s coverage | 55.1 ± 14.1 (60.6) | 1 | +0.22 ± 0.61 | 5 / 1 | 0.438 | 0 | 50.7 (n 6) |
| tomlc99 | C3n coverage+names | 57.4 ± 3.7 (58.5) | 0 | -0.70 ± 0.96 | 0 / 3 | 0.250 | 1 | 51.2 (n 4) |
| tomlc99 | C2′ re-seed repair | 59.3 ± 2.4 (60.3) | 0 | -1.41 ± 1.64 | 1 / 7 | 0.086 | 0 | 60.2 (n 3) |
| cjson | C2 proxy | 61.8 ± 15.6 (68.3) | 1 | -0.51 ± 0.46 | 2 / 7 | 0.039 | 0 | 67.1 (n 1) |
| cjson | A5 no steering | 70.3 ± 1.6 (70.1) | 0 | +1.35 ± 1.69 | 6 / 3 | 0.113 | 0 | - |
| cjson | C3s coverage | 64.2 ± 16.2 (72.2) | 1 | +1.15 ± 2.10 | 6 / 2 | 0.234 | 1 | 71.7 (n 2) |
| cjson | C3n coverage+names | 66.6 ± 5.1 (68.8) | 0 | -3.28 ± 6.23 | 2 / 5 | 0.156 | 2 | 60.9 (n 1) |


![Branch coverage of the parse-reachable region against inputs drawn, per target and arm: median over replicates with the interquartile band; the seed mean and the stronger Grammarinator variant as dashed and dotted lines.](figures/f1_curves.pdf)

### 5.1 The development target's steered arms are one loop, read first

json-parser's default build aborts on every object input, a
standards-violating NULL-offset idiom found by the pilot, and the loop
treats a crash as its highest-priority event (Section 3.2). On json-parser
every iteration therefore sees a crash. Table 4 counts which refinement
instruction each arm issued over its forty refinements per target, and the
json-parser rows are unlike the others. The proxy arm issued its own edits
0 times in 40, and the oracle arms issued "increase branch coverage" or
"cover function" 0 times. Every steered arm issued "mutate around the
crash" 30 to 36 times, with the remainder being repairs. No steered arm rolled
back in any of its ten replicates. On the three held-out targets the same
arms issued their intended edits 22 to 39 times in 40, and the proxy arm
rolled back 8, 5 and 0 times on parson, tomlc99 and cJSON, the
named-function arm 9 times on tomlc99.

**Table 4. Which refinement instruction the loop issued, iterations 2 to 5, per target and arm**

Counts over ten replicates x four refinements = 40 per cell, read from each run's evolution log. crash = "mutate structurally around the crashing input" (issued whenever the previous iteration saw a new crash signature, in every arm); signal = the arm's own edit (C2: add or up-weight a production, generate deeper, broaden, fix a feature; C3s: increase branch coverage; C3n: cover function F); improve = "make it a better fuzzer" (A5's only edit); revert = roll back the last edit; repair = the previous iteration was gated or its build was rejected, so the next prompt is a repair or a re-seed, not a refinement.

| target | arm | crash | signal | improve | revert | repair |
|-----------|--------------------|-----|------|-------|------|------|
| json-parser | C2 proxy | 31 | 0 | 0 | 0 | 9 |
| json-parser | A5 no steering | 0 | 0 | 35 | 0 | 5 |
| json-parser | C3s coverage | 30 | 0 | 0 | 0 | 10 |
| json-parser | C3n coverage+names | 36 | 0 | 0 | 0 | 4 |
| json-parser | C2′ re-seed repair | 33 | 0 | 0 | 1 | 6 |
| parson | C2 proxy | 0 | 28 | 0 | 8 | 4 |
| parson | A5 no steering | 0 | 0 | 40 | 0 | 0 |
| parson | C3s coverage | 0 | 39 | 0 | 0 | 1 |
| parson | C3n coverage+names | 0 | 39 | 0 | 0 | 1 |
| tomlc99 | C2 proxy | 0 | 22 | 0 | 5 | 13 |
| tomlc99 | A5 no steering | 0 | 0 | 38 | 0 | 2 |
| tomlc99 | C3s coverage | 0 | 27 | 0 | 1 | 12 |
| tomlc99 | C3n coverage+names | 0 | 27 | 0 | 9 | 4 |
| tomlc99 | C2′ re-seed repair | 0 | 33 | 0 | 4 | 3 |
| cjson | C2 proxy | 0 | 32 | 0 | 0 | 8 |
| cjson | A5 no steering | 0 | 0 | 38 | 0 | 2 |
| cjson | C3s coverage | 0 | 32 | 0 | 0 | 8 |
| cjson | C3n coverage+names | 0 | 38 | 0 | 0 | 2 |


The consequence is that the json-parser rows of every table below compare
four rounds of one fixed instruction against "improve", not one signal
against another. They are reported because the pre-registration requires
it and because json-parser is the in-sample target the proxy was designed
on, but every claim about signals in this paper rests on parson, tomlc99
and cJSON. Section 7 returns to what this confound says about loop design.

### 5.2 RQ2, the confirmatory family: no result survives correction; one target shows a detectable oracle effect

Which of the four signals makes refinement work? The family per target is
H1, the proxy against no steering, and H2, the coverage oracle with and
without names against the proxy, on the final generator's primary outcome
over ten replicates. Figure 3 shows every contrast's A12 with its
bootstrap interval against the registered bands; the table gives the
numbers with permutation and Holm-corrected p-values.

| target | H1: C2 proxy vs A5 no steering | H2s: C3s coverage vs C2 proxy | H2n: C3n coverage+names vs C2 proxy |
|---|---|---|---|
| json-parser (see 5.1) | 0.36 [0.14, 0.63], p 0.24 | 0.36 [0.11, 0.62], p 0.67 | 0.36 [0.12, 0.64], p 0.96 |
| parson | 0.59 [0.32, 0.84], p 0.90 | 0.76 [0.52, 0.96], p 0.044, Holm 0.13 | 0.33 [0.09, 0.59], p 0.96 |
| tomlc99 | 0.39 [0.14, 0.66], p 0.29 | 0.60 [0.35, 0.86], p 0.65 | 0.47 [0.21, 0.74], p 0.71 |
| cjson (Stage 2, Section 4.6) | 0.25 [0.06, 0.49], p 0.046, Holm 0.14 | 0.78 [0.52, 0.98], p 0.49 | 0.54 [0.28, 0.80], p 0.74 |

![Vargha-Delaney A12 with bootstrap 95% CI for every between-arm contrast run, per target; the shaded bands are the registered negligible and small ranges.](figures/f2_forest.pdf)

The aggregate is a null. Across four targets and twelve registered
contrasts, no p-value survives Holm's correction within its family. H1 is
null on every target, and its point estimate favours no steering on three
of four. The mean differences behind H1 are driven by the proxy arm's
collapsed replicates, two on json-parser and one on each other target,
which score zero as registered; among usable generators the two arms are
indistinguishable on the three Stage 1 targets (json-parser 63.7 against
63.7; parson A12 0.66 [0.38, 0.89]; tomlc99 0.43 [0.16, 0.71]). cJSON is
the one target where the proxy arm sits below no steering among usable
generators as well (68.7 against 70.3, A12 0.28 [0.07, 0.53], p 0.09), and
its H1 reaches p 0.046 before correction and 0.14 after.

The spread is in H2s. On the development target and on tomlc99 the
coverage oracle does no better than the proxy. On parson it is the one
cell in the family with a detectable effect before correction. Its finals
reach 69.1 ± 1.1 against the proxy's 60.9 ± 15.4 (67.7 among usable
generators) and no steering's 66.3 ± 1.6. A12 is 0.76 against the proxy
and 0.87 [0.68, 1.00] (p 0.004) against no steering, and every one of its
ten replicates produced a usable generator. Holm over the three-member family
takes its p to 0.13, so by the registered rule the family is null on parson
too. cJSON repeats the pattern in a weaker form: A12 0.78 [0.52, 0.98]
against the proxy, 0.84 [0.60, 1.00] (p 0.017) among usable generators,
with the permutation p on the mean difference at 0.49 because each arm
has one collapsed replicate. Against no steering the same arm is A12 0.62
[0.35, 0.88], p 0.83. On cJSON, measured coverage beats the proxy and does
not detectably beat leaving the model alone.

The exception in the family is H2n, and it runs the wrong way. Telling the
model which functions were least covered never beat the proxy (A12 0.33 to
0.54 on the held-out targets), and on parson it is clearly below the
scalar oracle, A12 0.09 [0.00, 0.26], p 0.001, in an exploratory contrast
outside the family. A cheap model can apparently act on "do better" with a
number attached, but not on "cover function F" when F is a name whose body
it has never seen; Section 7 takes this reading further.

**Finding 1.** No comparison in the registered family survives correction
on any of four targets, and the proxy never beats no steering. Measured
coverage is the only signal with a detectable effect before correction, on
one held-out parser and against the proxy on a second, and naming the
functions to cover did worse than giving the number.

### 5.3 RQ2, the refinement delta: five rounds move the seed by one to two points, in either direction

The family compares arms with each other. Whether any arm improves its own
first draft is a different question, answered by the per-replicate delta
between the final and the seed generator on the same twenty draw seeds.
Figure 4 plots every replicate's delta by target and arm, with the arm mean
as a bar; Table 3 gives the means, the up and down counts and the sign-flip
p. Replicates whose seed generator could not draw at all are set aside,
because their delta is the whole final level and says nothing about
refinement; Table 3 counts them.

![Per-replicate change of the primary outcome from seed to final, per target and arm; bar = arm mean, dotted = mean without the off-scale replicates (triangles: a failed seed generator above, a collapsed final below).](figures/f3_deltas.pdf)

The aggregate is small. On the three held-out targets every arm's mean
delta lies between −3.3 and +1.8 points on a scale where the seeds sit at
50 to 70, and about half are within one point of zero. The one arm that moves its
seed upward with a consistent sign is the coverage scalar on parson, +1.59
± 0.86 (8 of 10 up, sign-flip p 0.008). The proxy on parson also moves up,
+0.89 ± 0.50 (7 up, p 0.016). No steering (+0.54, p 0.16) and the
named-function oracle (−0.16, 5 up, 5 down) are within noise there. On
tomlc99 every arm is within noise once the flagged replicates are set aside:
proxy −0.01, no steering +1.80, coverage +0.22, coverage+names −0.70, C2′
−1.41. On cJSON the proxy moves its seed down, −0.51 ± 0.46 (2 up, 7 down, p
0.039). No steering moves up within noise, +1.35 ± 1.69 (p 0.11), as does
the coverage scalar, +1.15 ± 2.10 over the nine replicates whose seed drew
(p 0.23). The named-function oracle is −3.28 ± 6.23 over eight replicates,
one of which lost 21 points to a final whose draws time out (Section 8).

The exception is the development target, and it moves every steered arm
down: proxy −1.02 (p 0.03), coverage −1.60 (p 0.06), coverage+names −9.2
with its collapse and −0.1 to −6.5 without it (10 of 10 down, p 0.002),
C2′ −1.32, while no steering is within noise. The mechanism is the one
of 5.1: four rounds of mutating around a crash that every object input
already reaches narrow the generator, and the primary outcome is measured
on the whole reachable region.

**Finding 2.** Five rounds of feedback change the seed's coverage by one to
two points on the held-out targets, upward with a consistent sign only
under measured coverage on parson. The grammar-seeded first draft is most
of the generator the loop delivers.

### 5.4 RQ1: whether the first draft beats the grammar alone depends on the target

Does the model's first draft beat random text and Grammarinator on the
identical grammar? Table 5 and Figure 5 set the twenty seed generators per
target (the seeds of the proxy and no-steering replicates, which share one
seed prompt) against the two fixed references, each measured on the same
twenty draw seeds. The unit is the generator: A12 is the probability that a
random healthy LLM seed generator's mean exceeds a random Grammarinator
input set's value.

![The twenty LLM seed generators per target against random text and Grammarinator on the identical grammar, each over 20 draw seeds.](figures/f4_rq1.pdf)

**Table 5. RQ1: the LLM seed generators against random text and Grammarinator on the identical grammar**

Primary outcome at 10^4 inputs, draw seeds 0..19. Fixed generators: mean over the 20 draw seeds. LLM seed: mean over the 20 seed generators of C2 and A5 (identical seed prompt), a generator whose every cell failed scoring 0; healthy = generators that drew on at least one seed. A12 = P(a healthy LLM seed generator's mean exceeds a Grammarinator input set's value) against the stronger Grammarinator variant, bootstrap 95% CI.

| target | random text | Grammarinator defaults | Grammarinator depth-matched | LLM seed (20) | healthy | A12 healthy seeds vs stronger Grammarinator |
|-----------|--------|----------|-----------|----------|------|----------------------|
| json-parser | 26.4 | 61.1 | 63.9 | 57.8 | 18 of 20 | 0.62 [0.43, 0.80] |
| parson | 21.7 | 61.6 | 64.8 | 62.9 | 19 of 20 | 0.70 [0.51, 0.87] |
| tomlc99 | 17.1 | 65.1 | - | 49.6 | 17 of 20 | 0.13 [0.02, 0.28] |
| cjson | not measured | not measured | - | 65.6 | 19 of 20 | not measured |


The registered lower bound first. Random text, Hypothesis's plain text
strategy with no grammar, reaches 26.4, 21.7 and 17.1 points on
json-parser, parson and tomlc99, and every healthy LLM seed generator beats
every random draw on every target (A12 1.00). Having the grammar is worth
30 to 40 points, and everything else in this section is about the
remaining few.

Against Grammarinator the answer changes with the target. On json-parser
the healthy seeds tie the depth-matched variant, A12 0.62 [0.43, 0.80], and
beat the defaults, 0.83 [0.66, 0.97]. On parson they are ahead, 0.70 [0.51,
0.87]. On tomlc99 they are clearly behind, 0.13 [0.02, 0.28], with 2 of 17
healthy seeds above Grammarinator's mean; Grammarinator also beats every
loop arm's finals there (A12 0.14 against no steering, 0.13 against the
proxy), and in Figure 2 the oracle arms only reach its curve at 10 000
inputs. Three of twenty tomlc99 seed generators could not draw at all.

The tomlc99 exception has a plausible mechanism and one caveat. The TOML
grammar is two files with lexer modes, the harder authoring task in our
set; it is also the target with the most guard events (Section 5.7), and
the model's seeds lose there to a mechanical expansion of the same grammar.
The caveat is that the TOML Grammarinator was not depth-calibrated (Section
8), so the comparison is against its defaults only. cJSON's fixed
references were not measured before the submission cutoff (Section 4.6), so
cJSON has no RQ1 row.

**Finding 3.** LLM authorship beats random text everywhere and beats the
grammar's own expansion on the two JSON targets measured, by a tie and by
a practical margin; on TOML it loses to Grammarinator clearly, at the seed
and after refinement.

### 5.5 RQ3: the proxy tracks coverage across generators, not across a run's own iterations

Does the proxy score track measured coverage? Every loop-internal strategy
that ran, 604 across the five arms on the three Stage 1 targets, was
measured on three fresh draw seeds at 1 000 inputs and paired with the
proxy score the loop recorded for it. Figure 6 plots the pairs, one point
per strategy, coloured by arm; the question is whether the cloud has a
monotone trend, and whether the points of one replicate do.

![Proxy score recorded by the loop against the measured primary outcome of the same iteration's generator, one point per loop-internal strategy, coloured by arm.](figures/f5_rq3.pdf)

Across generators the relation is weak to moderate. Pooled over arms,
Spearman rho between the proxy and the primary outcome is +0.08 [−0.06,
+0.21] on json-parser (n 208), +0.37 [+0.23, +0.49] on parson (192) and
+0.41 [+0.28, +0.52] on tomlc99 (204): a monotone relation on the held-out
targets, none on the development target. Under the coverage arms the loop
also recorded branch coverage on the same 500 inputs the proxy was computed
from, which removes measurement noise: rho +0.35, +0.17 and +0.46.

Within a run the relation disappears, and that is the granularity that
matters. The loop uses the proxy to decide which of one replicate's five
iterations is best and whether to roll back, and there the median
within-replicate rho is +0.10, +0.00 and +0.35 (23, 18 and 28 of 43, 38
and 44 replicates positive). The correlation is strongest inside the
no-steering arm (+0.55 and +0.59 on parson and tomlc99), whose iterations
vary most, and weakest inside the steered arms, whose iterations the steer
keeps within a narrow band, so the proxy has least to order exactly where
it is asked to order.

**Finding 4.** The proxy orders different generators roughly the way
coverage does (rho about 0.4 on the held-out targets), and does not
reliably order five variants of the same generator, which is the job the
loop gives it.

### 5.6 RQ4: ground-truth bugs

Do the final generators reach known bugs within a fixed budget? Each arm's
ten final generators ran a 30-minute campaign against each pre-fix build;
a campaign counts as triggered when an input's normalised crash signature
matches the proof of concept's. Figure 7 shows, per bug, the fraction of an
arm's campaigns that had triggered it after n inputs, with the fixed
references dashed; the table counts triggered campaigns.

![Fraction of an arm's campaigns that had triggered the bug after n inputs, per ground-truth bug; baselines dashed and dotted.](figures/f6_rq4.pdf)

| bug | C2 proxy | A5 no steering | C3s coverage | C3n coverage+names | random text | Grammarinator |
|---|---|---|---|---|---|---|
| json-parser issue 78 | 3 of 10 | 9 of 10 | 5 of 10 | 5 of 10 | 0 (3.0 M inputs) | 0 (6 to 10 M) |
| json-parser issue 68 or 78 | 4 of 10 | 9 of 10 | 5 of 10 | 6 of 10 | 0 (3.0 M) | 0 (5.6 to 10 M) |
| tomlc99 issue 50 | 8 of 10 | 9 of 10 | 9 of 10 | 9 of 10 | 0 (6.2 M) | 1 of 1 (10 969 inputs) |
| tomlc99 recursion | 0 | 0 | 0 | 0 | 0 | 0 |

Two facts shape the reading. json-parser's two bugs, both one-byte
over-reads at the end of the buffer inside the same function, normalise to
the same signature, and the issue-68 pre-fix build also contains issue 78,
so the issue-78 row is one bug and the issue-68 row measures either
over-read. And a first pass of the campaigns ran nine at a time under heavy
load, which made 13 positive controls time out; those 13 were rerun on a
quiet machine after the runner was changed to fail a timed-out control.

The aggregate is that reachable bugs are reached by every LLM arm. The
pre-registration predicted that neither tomlc99 bug would be reached within
the budget; issue 50, a NULL dereference on a key-value line, was reached by
8 to 9 of 10 replicates in every arm, in a median of 4 000 to 45 000
inputs, and by Grammarinator after 10 969. The prediction was wrong about
that bug and right about the recursion overflow, which needs about 20 000
nesting levels and was reached by nothing in 0.4 to 6 million inputs.

The spread is on json-parser, and it separates the arms in the direction
of 5.1. The no-steering arm's generators triggered both bugs in 9 of 10
campaigns and the proxy arm's in 3 and 4 (issue 78: Fisher p 0.02); the
oracle arms sit between. The proxy arm's two collapsed finals count as
never triggering, but the gap remains among usable generators (3 of 8
against 9 of 10 on issue 78). The mechanism is the degenerate loop: the
proxy arm spent its rounds mutating around the finding-#1 crash, which
every object input already reaches, and its finals emit fewer of the
truncated literals and escapes the two bugs need.

The exception is the fixed references. Random text triggered nothing in 3
to 7 million inputs on any build, and Grammarinator triggered nothing on
json-parser in 5.6 to 10 million. A grammar-driven generator emits complete
productions, and both json-parser bugs need a value cut off at the end of
the buffer, which the LLM seeds emit because the prompt asks for near-valid
malformed inputs. Every other crash signature seen in the campaigns
occurred on a pre-fix source, a known UBSan integer overflow in old
json-parser and scan_string over-reads in old tomlc99, fixed upstream
since; the pinned HEAD builds produced none, so there are no new findings.
The cJSON campaigns (CVE-2023-53154, Section 4.5) were not run before the
submission cutoff; the bug build, its positive control and the campaign
driver are in the artifact.

**Finding 5.** The known bugs are found by the seeds' class of generator,
not by refinement: every LLM arm reaches issue 50, no fixed reference
reaches the json-parser bugs, and on the development target the proxy loop
found them less often than no steering did.

### 5.7 RQ5: how the author fails

How does the model fail, and what does the loop do about it? Every guard
event in the 180 replicates of the five DeepSeek arms was coded from its
recorded exception or rejection text into a cause class; Table 6 gives the
classes by arm.

**Table 6. RQ5: guard events by cause class and arm**

121 events over 180 completed replicates (four targets), coded from the recorded exception and rejection text by ordered regular expressions, first match wins; iterations without an event are not listed. Arm codes as in Table 1.

| cause | C2 | A5 | C3s | C3n | C2′ | total |
|------------------------------|-----|-----|-----|-----|-----|------|
| syntax / unparseable response | 5 | 3 | 10 | 5 | 1 | 24 |
| strategy/value confusion (two-level semantics) | 12 | 2 | 7 | 3 | 0 | 24 |
| generic Python error (TypeError/ValueError/KeyError/NameError) | 5 | 3 | 4 | 2 | 4 | 18 |
| ExceptionGroup wrapper (sub-exceptions hidden) | 13 | 0 | 0 | 0 | 0 | 13 |
| recursion / Hypothesis health check | 1 | 0 | 10 | 2 | 0 | 13 |
| hallucinated Hypothesis API | 5 | 0 | 7 | 0 | 1 | 13 |
| low acceptance (valid code, invalid outputs) | 0 | 5 | 0 | 0 | 1 | 6 |
| wrong alphabet / characters argument | 0 | 0 | 4 | 0 | 1 | 5 |
| invalid strategy arguments | 1 | 0 | 1 | 1 | 0 | 3 |
| disallowed import or name (screen) | 0 | 0 | 1 | 0 | 1 | 2 |


The aggregate is 121 events over 180 replicates, and 44 of the 180 first
drafts failed at least one guard. The largest classes are unparseable
responses (24) and strategy-versus-value confusion (24): concatenating a
strategy object to a string, or calling a strategy as a value, the error of
Section 1.1. Generic Python errors (18), hallucinated Hypothesis API names
(13) and recursion or health-check failures (13, ten of them in the
coverage-scalar arm, whose "reach code the inputs never execute"
instruction invites deeper recursion) follow. By target, tomlc99 has 46
events, json-parser 42, cJSON 25 and parson 8; the two-file, mode-based
TOML grammar is the harder authoring task and the one where Grammarinator
wins (Section 5.4).

One class belongs to a single arm. Hypothesis's ExceptionGroup wrapper
accounts for 13 events, all in the proxy arm, and its message names no
exception, line or construct, because the loop's error formatter forwards
the wrapper rather than its sub-exceptions; those repair prompts carried no
information. The proxy arm is also the arm with the most collapsed
replicates (five of the ten across the four targets). Whether the empty
message, or something the arms share, is what turns a first-draft error
into a generator that never recovers is a question the taxonomy cannot
answer, because it counts events and not what the model did next. Section
6 follows the collapsed replicates iteration by iteration.

**Finding 6.** The cheap model fails a guard in about a quarter of its
first drafts, mostly by returning unparseable code or by confusing a
strategy with a value; the failures cluster on the harder grammar and on
the arm whose instruction invites recursion.

### 5.8 Cost

Table 7 gives the cost per run by target. The 180 runs cost 4.63 USD in
total; a run costs 0.018 to 0.041 USD (mean 0.026) and 3.6 to 9.4 minutes
of wall clock (mean 4.4), with 12 000 to 31 000 tokens in and about the
same out, and every call was served by deepseek-flash. Gentoo reports 7.5
to 12.8 USD per synthesis, so twenty independent first drafts on one
target cost less than one of theirs. On the three held-out targets a run
buys at most two points of coverage over its own first draft, and only
under measured coverage on one of them; on tomlc99, where Grammarinator
wins at the seed, the same three cents would be better spent on the
grammar and the adaptation note than on any refinement.

**Table 7. Synthesis cost per run, by target**

Mean over every completed run of the five DeepSeek arms (C2, A5, C3s, C3n, C2′); every call served by deepseek-flash; the per-arm table is in the artifact (eval/matrix/cost_table.md).

| target | runs | LLM calls | tokens in | tokens out | USD per run | wall minutes |
|-----------|------|------|--------|--------|--------|--------|
| json-parser | 50 | 5.7 | 17451 | 18576 | 0.025 | 5.5 |
| parson | 40 | 5.3 | 15496 | 16388 | 0.022 | 4.0 |
| tomlc99 | 50 | 5.6 | 24180 | 24103 | 0.033 | 3.9 |
| cjson | 40 | 5.5 | 14424 | 15444 | 0.021 | 4.2 |
| all | 180 | | | | 0.026 (total 4.633) | 4.4 |


### 5.9 Sensitivity of the design

With ten replicates per arm and the between-replicate SD of usable
generators (3.3, 2.2, 5.2 and 2.2 AUC points on json-parser, parson,
tomlc99 and cJSON), the registered permutation test reaches 80% power at
a mean shift of 4.5, 3.0, 6.5 and 3.0 points, a true A12 of about 0.82.
Effects in the lower half of the registered practical band (0.64 to 0.80)
are not reliably detectable by this design, so every null above reads "no
detectable effect at this budget". Collapsed replicates, which score zero,
raise the SD to 14 to 20 points and dominate every between-arm mean
difference in Table 3; the next section explains where they come from.

## 6. Mechanism: collapse is fixation, and the repair path decides recovery

Section 5.7 counted the author's failures and left one question open: why
a first-draft error sometimes becomes a generator that never recovers. This
section reads the collapsed replicates iteration by iteration and then
pools every gate event by the path the loop took after it. It is
exploratory in the registered sense, generated from the logs after the
confirmatory analysis, with one pre-specified test at the end.

### 6.1 The collapsed replicates resubmit their own code

Ten replicates across the registered arms ended with a generator that
raised on every draw. In the proxy arm they are json-parser 7 and 10,
parson 6, tomlc99 3 and cJSON 1; in the coverage-scalar arm json-parser 9
and 10, tomlc99 8 and cJSON 8; in the named-function arm json-parser 8.
The four proxy-arm cases on the Stage 1 targets were analysed first, and
the example of Section 1.1 is one of them. The table gives, for each, the
iteration-1 error and the similarity of every resubmitted module to the
one before it.

| replicate | iteration-1 error | similarity of iterations 2, 3, 4, 5 to the previous module |
|---|---|---|
| parson C2-rep6 (Section 1.1) | TypeError: can only concatenate str (not "OneOfStrategy") to str | 0.999, 0.992, 1.000, 1.000 |
| tomlc99 C2-rep3 | AttributeError: 'function' object has no attribute 'validate' | 1.000, 1.000, 1.000, 1.000 |
| json-parser C2-rep7 | ExceptionGroup: Hypothesis found 2 distinct failures (2 sub-exceptions) | 0.752, 1.000, 1.000, 1.000 |
| json-parser C2-rep10 | the same ExceptionGroup message | 1.000, 1.000, 1.000, 1.000 |

The pattern is the same in all four. The model received the same in-place
repair instruction at iterations 2 to 5, with its own failed module in
full, and answered with code 98.4% similar to the previous iteration on
average, and all four returned byte-identical modules on at least two
consecutive iterations (three of them from iteration 2 onward). The empty ExceptionGroup message explains two of
the four, but the other two received an explicit TypeError or
AttributeError that names the construct, and still resubmitted. In the
parson case the one change the model did make touched the right function
on iteration 3 and left the strategy object where a string was needed. An
explicit error message is therefore not sufficient for recovery under this
repair path; the next subsection asks what is.

### 6.2 Recovery is a property of the path, not the arm

After a gate event the loop takes one of three paths, decided by what the
next prompt shows the model (Section 3.2). Pooled over the 80 proxy and
no-steering replicates on the four targets:

| path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|
| in place: the failed code with "make exactly one change" | 25 (C2 22, A5 3) | 2 of 25 | 0.98 (min 0.75) |
| fallback: the last working generator | 4 (C2 3, A5 1) | 3 of 4 | 0.95 |
| re-seed from the grammar with the failure text | 14 (C2 9, A5 5) | 12 of 14 | 0.07 (0.02 to 0.11) |

The pattern holds under the oracle arms, pooled over their 80 replicates:
in place 7 of 25 recovered at similarity 0.93 to 1.00, re-seed 11 of 15 at
0.02 to 0.15, fallback 1 of 2. In-iteration repairs, which always show the
failed code, resubmit near-identical code in every in-place arm (mean
similarity 0.94 to 1.00). The two paths differ in what the model is shown,
not in what went wrong: a build rejection and a gate failure are both
first-draft errors of the classes in Table 6, and the loop's routing of
one to a re-seed and the other to an in-place repair is an accident of its
design. Both arms use the identical seed prompt and guards, so the
iteration-1 gate incidence is sampling variation of one process; within the
proxy arm on the three Stage 1 targets an iteration-1 gate predicts
collapse (4 of 4 collapsed had one, 5 of 26 healthy; Fisher p 0.005).

### 6.3 C2′: repair by re-seed, on two targets

The one pre-specified test of the mechanism replaces the in-place repair
with a re-seed from the grammar and the failure text, and changes nothing
else. On json-parser 0 of 10 replicates collapsed (proxy 2 of 10); the
final reached 63.9 ± 1.3; A12 0.58 [0.32, 0.83] against the proxy, 0.47
among usable generators, 0.46 against no steering. On tomlc99 0 of 10
collapsed (proxy 1 of 10); final 59.3 ± 2.4; A12 0.54 [0.28, 0.81] against
the proxy, 0.40 against no steering. Over both targets, 0 collapses in 20
runs against the proxy's 3 in 20, and the in-iteration repair's similarity
to the gated code fell from 0.96 to 0.04. Re-seeding removes the anchoring
and, with it, the unusable outputs; it adds no coverage on either target.
The ExceptionGroup formatter was left unchanged, so the result isolates
the repair path.

### 6.4 What this changes

Whether a loop occasionally hands back an unusable generator is decided by
its repair policy, which every arm shares, not by the steering signal. The
signal, on the three targets where it acted at all, moved coverage by one
to two points, and only the measured-coverage scalar moved it upward, on
one target. The practical advice for a loop of this shape is therefore
about the repair path before it is about the signal: never show the model
its own failed code; re-seed with the failure text. The discussion asks
what the whole pattern, small signal effects and a decisive repair path,
says about where a synthesis-time loop's leverage lies.

## 7. Discussion

**What the heterogeneity says.** Gentoo's thesis is that a generator which
encodes the target's structure needs little help from the fuzzer that runs
it (Vikram and Padhye 2026). Seen from below, with a cheap model that never
reads the parser, the same thesis appears at synthesis time: the grammar,
plus whatever the model knows about the format, fixes most of the
generator's reach at the first attempt, and five rounds of any signal move
it by one or two points. The pre-registration listed four possible
outcomes and this is the fourth, a result that differs by target. The same
signals, in the same loop, with the same model, produced a detectable gain
on one held-out parser (parson, under measured coverage), a gain against
the proxy but not against no steering on a second (cJSON), nothing on the
third (tomlc99), and nothing attributable to any signal on the development
target. That reading has a
sharp limit on tomlc99, where a mechanical expansion of the same grammar
beat every LLM condition at the seed and after refinement, so the first
attempt is most of the result only where the model's first attempt is
good.

Three readings are consistent with the heterogeneity, and the study
separates them only partly. The first is headroom. The seed already
reaches 60 to 70% of reachable branches, and the branches left may need
inputs a grammar-derived generator does not naturally produce. parson has
the most reachable functions of the four targets (40 of 144) and is the
one where the oracle found something to do; tomlc99's remaining branches
are error paths a TOML grammar does not describe. The second is
the author: the model failed a guard in 44 of 180 first drafts, and on
tomlc99 its seeds lose to a mechanical generator, so on that target there
may be nothing for a signal to improve. The third is the signal's form:
the scalar helped on parson and the named-function variant did not, which
suggests the model can act on "do better" with a number attached but not
on "cover function X" when X is a name whose body it has never seen. A
second model tests the second reading, a larger budget the first, and a
C3n variant that shows the function's source the third; the last is the
natural next condition.

**The proxy is not vindicated and not condemned.** It cannot be
distinguished from no steering on any target, so it does not earn its
place. But it is also not the reason refinement fails: on tomlc99 the
oracle does no better, and on parson the oracle's gain is one to two
points, so the ceiling the proxy was meant to approximate is itself low.
Section 5.5 measured how well it tracks that ceiling: moderately across
generators, barely within a run's own iterations, which is where the loop
uses it. What the proxy arm did have, uniquely, was the empty
ExceptionGroup repair message and the collapses that went with it, and
Section 6 shows both to be properties of the repair path rather than of
the signal.

**Repair policy as the actionable finding.** Every agentic loop that lets a
model fix its own code has a repair path, and ours shows a clean,
replicated failure of the "here is your code, change one thing" pattern:
the model anchors on its own output and resubmits it, and an explicit
error message does not break the anchor. Re-seeding with the failure text
does, and a loop that always re-seeds produced no unusable generator on
two targets. This is exploratory in the registered sense and the
collapse-count difference is not established at ten replicates per cell,
but the three-path table is over 80 replicates, it replicates under the
oracle arms, and its direction is not subtle. For loop design the
implication is an ordering: fix the repair path, then the first draft,
then ask whether a signal is worth its instrumentation.

**The development target.** Designing the proxy on a parser whose default
build crashes on every object was a mistake with a benefit. The mistake:
on that target no steering signal ever acted, so its rows in the family
test nothing about signals, and a reader who skipped Section 5.1 would
misread its C3n row as "naming functions is harmful". The benefit: it is a
clean demonstration that a loop's event priority, crash before signal, can
silently turn every condition into one condition, which is the kind of
confound a single-run evaluation never reveals and a replicated one does.
The pre-registration's decision to report the development target
separately is what kept it from contaminating the held-out claims, and the
same rule, one event priority above the signal, exists in every loop that
treats a crash as its objective.

**What would change the conclusion.** A practical effect that this design
missed would need to be below about A12 0.8 (Section 5.9). A second model
family, a larger budget, a C3n that shows function bodies, and parsers with
more unreached branches are the four cheapest ways to look for it. The
second model's runs were under way when this submission was frozen
(Section 4.6), and it and the remaining Stage 2 parser are pre-specified
for the revision.

## 8. Threats to validity

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

## 9. Related work

**Language models that produce inputs directly.** Fuzz4All prompts a model
for test inputs with an autoprompting loop and fuzzes compilers with the
inputs themselves (Xia et al. 2024). Ackerman and Cybenko (2023) have a
model read a format specification and produce seeds and generators for
parsers, in a registered report. Jiang et al. (2024) survey this line and
name its recurring limits, insufficient diversity and limited validity;
our failure taxonomy (Section 5.7) measures both for generator authorship.
These systems ask the model for inputs; ours asks it for a program that
produces inputs, which is drawn ten thousand times per measurement and can
be steered by what it produces.

**Language models that write property-based tests.** Vikram et al. (2023)
ask whether models can write good property-based tests and find the
generators competent but the properties weak; Maaz et al. (2025) run an
agent that writes property-based tests across the Python ecosystem and
finds bugs. Both share our object, a Hypothesis strategy written by a
model, and neither steers the strategy after it is written or compares
signals.

**Evaluation methodology.** Klees et al. (2018) set the repetition and
statistics bar for fuzzing evaluations, and Böhme et al. (2022) show how
unreliable a coverage comparison from few runs is. Park and Yun (2026)
survey agentic fuzzing and criticise single extended runs as its dominant
evaluation. We follow the first two with ten replicates, effect sizes with
bootstrap intervals, permutation tests and a pre-registered analysis, and
Section 5.1 is a concrete instance of the third's criticism: a confound
that only replication exposed. We add the design's measured sensitivity,
which Klees et al. recommend and evaluations rarely report.

**Loops that evolve generators with a model.** ELFuzz evolves whole fuzzer
programs under an edge-coverage fitness with CodeLlama-13B over 20 to 55
hours per target, against Grammarinator, ISLa and GLADE on seven targets,
ten repetitions, no significance tests (Chen et al. 2025). G2Fuzz has the
model write and mutate Python generators for binary formats and re-invokes
it when AFL++ stalls (Zhang et al. 2025). Both use coverage as the fitness
and neither asks whether the fitness is needed; both take Grammarinator on
the same grammar as the baseline, which is why it is ours.

**Agents that write generators.** Gentoo is the closest work (Vikram and
Padhye 2026). A Claude agent with terminal access, library source and JQF
tooling synthesises Java generators in three configurations: raw fuzzing
output only, static dominator analysis with per-branch coverage reports,
and agent-ranked predicates with the same reports. Five repetitions per
configuration, a one-hour synthesis cap, three-hour campaigns and
Mann-Whitney tests give the result that agent generators beat human-written
ones on four of seven libraries and that coverage-guided mutation adds
almost nothing to them at fuzz time. Our study differs in three ways. It
asks the question at synthesis time rather than fuzz time: whether the loop
that writes the generator needs coverage, not whether the fuzzer that runs
it does. It works in the opposite regime, a cheap model that never sees
source, error messages or coverage, at three cents a run against their ten
dollars, and adds a signal that needs no instrumentation. And it replaces
five repetitions with a pre-registered design of ten replicates per cell,
a single primary outcome and a correction over the family, which is what
let it separate a signal effect from the author's variance and expose the
confound of Section 5.1. Their stated threats, Java only, one model,
possible memorisation of library source and fixed-time campaigns,
motivated our C targets, anonymised prompts and input-count budgets; one
model remains a threat we share.

## 10. Conclusion

At a budget of five rounds and 2 500 executed inputs, with a cheap model
and no access to the parser, the generator a model writes from a grammar in
its first attempt is most of the generator the loop delivers. Telling the
model nothing, or structural facts about its own outputs, changed that
generator by about one coverage point on the held-out parsers; measured
coverage added one to two points on one of them and nothing detectable on
the other two; naming the functions to cover helped less than giving the
number. What decided whether the loop handed back a usable generator at all
was its repair path, and a policy that never shows the model its own failed
code removed that failure without changing coverage.

Two directions follow. For loop design, the evidence points at the repair
path and the first draft before the signal: re-seed on failure, spend the
budget on the grammar and the adaptation note, and treat a synthesis-time
signal as a hypothesis to test rather than a component to assume. For
evaluation, the development target shows how an event rule can turn every
condition into one condition without any visible error, and only replicated
runs with a registered outcome made it visible. Three extensions are
pre-specified and costed: a second model family, whose runs were under way
when this submission was frozen and are excluded from it (Section 4.6); a
second Stage 2 parser; and an oracle that shows the model the body of the
function it is asked to cover. Everything needed to check these statements
is in the artifact.

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
repository at [artifact URL to be inserted]; the git history is the
timestamp of the pre-registration.

**Ethics.** The study involved no human participants and no animals.

**Use of large language models.** Declared in Section 4.7.

## References

- Ackerman, J., and Cybenko, G. (2023). Large language models for fuzzing
  parsers (registered report). FUZZING 2023. ACM. https://doi.org/10.1145/3605157.3605173
- Arcuri, A., and Briand, L. (2011). A practical guide for using statistical
  tests to assess randomized algorithms in software engineering. ICSE 2011.
  https://doi.org/10.1145/1985793.1985795
- Böhme, M., Pham, V.-T., and Roychoudhury, A. (2016). Coverage-based greybox
  fuzzing as Markov chain. ACM CCS 2016. https://doi.org/10.1145/2976749.2978428
- Böhme, M., Szekeres, L., and Metzman, J. (2022). On the reliability of
  coverage-based fuzzer benchmarking. ICSE 2022. https://doi.org/10.1145/3510003.3510230
- Chen, C., Dolan-Gavitt, B., and Lin, Z. (2025). ELFuzz: Efficient input
  generation via LLM-driven synthesis over fuzzer space. USENIX Security
  2025. https://doi.org/10.48550/arXiv.2506.10323
- Claessen, K., and Hughes, J. (2000). QuickCheck: a lightweight tool for
  random testing of Haskell programs. ICFP 2000. https://doi.org/10.1145/351240.351266
- Hodovan, R., Kiss, A., and Gyimothy, T. (2018). Grammarinator: a
  grammar-based open source fuzzer. A-TEST 2018.
  https://doi.org/10.1145/3278186.3278193 (Tool used at version 26.1; the pinned
  generator and every parameter are in the artifact.)
- Jiang, Y., Liang, J., Ma, F., Chen, Y., Zhou, C., Shen, Y., Wu, Z., Fu, J.,
  Wang, M., Li, S., and Zhang, Q. (2024). When fuzzing meets LLMs:
  challenges and opportunities. FSE 2024 Companion. https://doi.org/10.1145/3663529.3663784
- Klees, G., Ruef, A., Cooper, B., Wei, S., and Hicks, M. (2018). Evaluating
  fuzz testing. ACM CCS 2018. https://doi.org/10.1145/3243734.3243804
- Maaz, M., DeVoe, L., Hatfield-Dodds, Z., and Carlini, N. (2025). Agentic
  property-based testing: finding bugs across the Python ecosystem.
  https://doi.org/10.48550/arXiv.2510.09907
- MacIver, D. R., Hatfield-Dodds, Z., et al. (2019). Hypothesis: a new
  approach to property-based testing. Journal of Open Source Software 4(43). https://doi.org/10.21105/joss.01891
- Padhye, R., Lemieux, C., Sen, K., Papadakis, M., and Le Traon, Y. (2019).
  Semantic fuzzing with Zest. ISSTA 2019. https://doi.org/10.1145/3293882.3330576
- Park, S., and Yun, I. (2026). Agentic fuzzing: opportunities and
  challenges. https://doi.org/10.48550/arXiv.2605.10074
- Vargha, A., and Delaney, H. D. (2000). A critique and improvement of the CL
  common language effect size statistics of McGraw and Wong. Journal of
  Educational and Behavioral Statistics 25(2), 101-132.
  https://doi.org/10.3102/10769986025002101
- Vikram, V., Lemieux, C., Sunshine, J., and Padhye, R. (2023). Can large
  language models write good property-based tests?
  https://doi.org/10.48550/arXiv.2307.04346
- Vikram, V., and Padhye, R. (2026). Fuzzing with agents? Generators are all
  you need. https://doi.org/10.48550/arXiv.2604.01442
- Xia, C. S., Paltenghi, M., Le Tian, J., Pradel, M., and Zhang, L. (2024).
  Fuzz4All: Universal fuzzing with large language models. ICSE 2024.
  https://doi.org/10.1145/3597503.3639121
- Zalewski, M. (2014). American Fuzzy Lop. https://lcamtuf.coredump.cx/afl/
- Zhang, K., Li, Z., Wu, D., Wang, S., and Xia, X. (2025). Low-cost and
  comprehensive non-textual input fuzzing with LLM-synthesized input
  generators. USENIX Security 2025. https://doi.org/10.48550/arXiv.2501.19282

