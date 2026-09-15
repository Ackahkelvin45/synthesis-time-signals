# Draft: Section 5 (Results) and Section 6 (Mechanism), third draft, 2026-09-15, revised to the blueprint.

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

<!-- TABLE:T2 -->

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

<!-- TABLE:T5 -->

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

<!-- TABLE:T3 -->

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

<!-- TABLE:T4 -->

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

<!-- TABLE:T6 -->

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
