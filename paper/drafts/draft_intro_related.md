# Draft: Abstract, Section 1 (Introduction), Section 2 (Background), Section 8 (Related work), Section 9 (Conclusion). Third draft, 2026-09-15, revised to the blueprint. No em-dashes.

## Title (registered, neutral)

Synthesis-time feedback for LLM-authored grammar-based generators: a
replicated comparison of no steering, a structural proxy, and a coverage
oracle on C parsers

## Abstract (about 240 words)

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

## 8. Related work

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

## 9. Conclusion

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
