# Draft: Abstract, Section 1 (Introduction), Section 2 (Background, short), Section 8 (Related work), Section 9 (Conclusion). Second draft, 2026-09-14.



## Title (registered, neutral)

Synthesis-time feedback for LLM-authored grammar-based generators: a
replicated comparison of no steering, a structural proxy, and a coverage
oracle on C parsers

## Abstract (about 240 words)

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
cell, and three C parsers in two text formats. No comparison in the
confirmatory family survives correction. Five rounds of refinement move
the first-draft generator's coverage by one to two points: upward under
measured coverage on one held-out parser, not at all on the other, and
never under the proxy or under no steering. Naming the functions to cover
did worse than giving the number. Whether the first draft beats
Grammarinator on the identical grammar depends on the target (a tie, ahead,
and clearly behind on TOML). The loop's one visible failure, an unusable
output generator, traces to its repair policy rather than its signal: shown
its own failed code the model resubmits it, recovering 2 times in 21;
re-seeded from the grammar it recovers 7 in 9, and a re-seeding loop
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
model is a high-variance author: 33 of our 140 first drafts failed a guard,
and the pilot's single-run 51-to-72 score trajectory did not reproduce.

Contributions.
1. A replicated, pre-registered comparison of four synthesis-time signals
   on three C parsers. No comparison survives correction; measured coverage
   produced a detectable gain on one held-out target before correction,
   the proxy and no steering never did, and naming functions to cover did
   worse than the number (Section 5).
2. The community baseline the LLM-generator literature usually omits:
   Grammarinator on the identical grammar against twenty LLM first drafts
   per target. LLM authorship is a tie, ahead, and clearly behind,
   depending on the target (Section 5.4).
3. A mechanism for the loop's only visible failure, unusable output
   generators: fixation under in-place repair, a three-path table over 60
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

## 8. Related work

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

## 9. Conclusion

At a budget of five rounds and 2 500 executed inputs, with a cheap model
and no access to the parser, the generator an LLM writes from a grammar in
its first attempt is most of the generator you get. Telling it nothing or
structural facts about its own outputs changed the outcome by about one
point on the held-out parsers; measured coverage added one to two points on
one of them and nothing on the other; naming the functions to cover helped
less than the number. Whether that first attempt beats a mechanical
grammar generator depends on the grammar. The one way the loop visibly
fails, handing back a generator that cannot run, is a property of how it
repairs broken code, and a policy that never shows the model its own failed
code removes it. On the development target a crash-first rule made every
steered arm the same loop, which only ten replicates per cell could show.
Everything needed to check these statements is in the artifact. Three
extensions are pre-specified and costed: two more parsers (cJSON,
libexpat), a second model family, and an oracle that shows the model the
function it is asked to cover.

The use of large language models in this work is declared in Section 4.7.

## Statements and Declarations

**Competing interests.** The authors have no financial or non-financial
interests directly or indirectly related to this work.

**Funding.** No external funding was received. API usage was paid by the
authors (about 5 USD of DeepSeek credit and the OpenAI credit stated in
Section 5.10).

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
  fuzz testing. ACM CCS 2018.
- Padhye, R., Lemieux, C., Sen, K., Papadakis, M., and Le Traon, Y. (2019).
  Semantic fuzzing with Zest. ISSTA 2019.
- Park, S., and Yun, I. (2026). Agentic fuzzing: opportunities and
  challenges. https://doi.org/10.48550/arXiv.2605.10074
- Vikram, V., and Padhye, R. (2026). Fuzzing with agents? Generators are all
  you need. https://doi.org/10.48550/arXiv.2604.01442
- Xia, C. S., Paltenghi, M., Le Tian, J., Pradel, M., and Zhang, L. (2024).
  Fuzz4All: Universal fuzzing with large language models. ICSE 2024.
- Zhang, et al. (2025). G2Fuzz. USENIX Security 2025. https://doi.org/10.48550/arXiv.2501.19282
- Hodovan, R., and Kiss, A. (2018). Grammarinator: a grammar-based open
  source fuzzer. A-TEST 2018. (Tool used at version 26.1; the pinned
  generator and every parameter are in the artifact.)
- MacIver, D. R., Hatfield-Dodds, Z., et al. (2019). Hypothesis: a new
  approach to property-based testing. Journal of Open Source Software 4(43). https://doi.org/10.21105/joss.01891
