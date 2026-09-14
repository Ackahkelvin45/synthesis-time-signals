# Draft: Section 5 (Results) and Section 6 (Mechanism), second draft



## 5. Results

Table 2 (generated from eval/matrix/full_report.md) gives, per target and
arm, the final generator's level on the primary outcome (mean and 95% CI
over ten replicates, median), the number of collapsed replicates, the
per-replicate delta against the seed, and the last working iteration's
level where it differs from the final. Figure 1 shows the coverage curves,
Figure 2 the between-arm effect sizes, Figure 3 the deltas.

<!-- TABLE:T1 -->

<!-- TABLE:T2 -->

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

![Vargha-Delaney A12 with bootstrap 95% CI for every between-arm contrast run, per target; the shaded bands are the registered negligible and small ranges.](figures/f2_forest.pdf)

H1 is null on all three targets, with the point estimate favouring no
steering on two of them; the mean differences there are driven by the
proxy arm's collapsed replicates (two, one and one), which score zero as
registered, and among usable generators the two arms are indistinguishable
on every target (json-parser 63.7 vs 63.7; parson A12 0.66 [0.38, 0.89];
tomlc99 0.43 [0.16, 0.71]).

H2s is null on tomlc99 and on the development target. On parson the
coverage-scalar oracle is the one cell in the family with a detectable
effect before correction: its finals reach 69.1 ± 1.1 against the proxy's
60.9 ± 15.4 (67.7 among usable generators) and no steering's 66.3 ± 1.6,
A12 0.76 against the proxy and 0.87 [0.68, 1.00] (p 0.004) against no
steering, and every one of its ten replicates produced a usable generator.
Holm over the three-member family takes the p to 0.13, so by the
registered rule the family is null on parson too; the cell is reported as
what it is, a practical-band effect on one target that the design's
correction does not confirm.

H2n is null on all three targets, and on parson the named-function variant
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
(10 of 10 down, p 0.002), C2' −1.32; no steering is within noise. Five
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
depth-calibrated (Section 7).

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
the pinned HEAD builds produced none, so there are no new findings.

### 5.7 RQ5: how the author fails

Ninety-six guard events across 140 replicates (Table 4; eval/matrix/
taxonomy.md). The largest classes are unparseable responses (17),
strategy-versus-value confusion (15: concatenating a strategy object to a
string, calling a strategy as a value), generic Python errors (14), and
Hypothesis's ExceptionGroup wrapper (13, all in the proxy arm), whose
message names no exception, line or construct because the loop's error
formatter forwards the wrapper rather than its sub-exceptions, so those
repair prompts carried no information. Recursion and health-check failures
(12) cluster in the coverage-scalar arm (10). Thirty-three of 140 seeds
failed at least one guard at iteration 1. By target: tomlc99 46 events,
json-parser 42, parson 8; the two-file, mode-based TOML grammar is the
harder authoring task and the one where Grammarinator wins.

### 5.8 Cost

Table 6 (eval/matrix/cost_table.md). 140 runs, 3.80 USD in total; a run
costs 0.019 to 0.041 USD (mean 0.027) and 3.6 to 9.4 minutes of wall clock
(mean 4.5), with 14 000 to 31 000 tokens in and about the same out. Every
call was served by deepseek-flash. Gentoo reports 7.5 to 12.8 USD per
synthesis; twenty independent seeds on one target cost less than one of
theirs.

### 5.9 Sensitivity of the design

With ten replicates per arm and the between-replicate SD of usable
generators (3.3, 2.2 and 5.2 AUC points on json-parser, parson and
tomlc99), the registered permutation test reaches 80% power at a mean
shift of 4.5, 3.0 and 6.5 points, a true A12 of about 0.82. Effects in the
lower half of the registered practical band (0.64 to 0.80) are not
reliably detectable by this design, so every null above reads "no
detectable effect at this budget". Collapsed replicates, which score zero,
raise the SD to 14 to 20 points and dominate every between-arm mean
difference in Table 2.

## 6. Mechanism: collapse is fixation, and the repair path decides recovery

Exploratory (pre-registration, exploratory-results guard); generated from
the logs after the confirmatory analysis.

### 6.1 The collapsed replicates resubmit their own code

Eight replicates across the registered arms ended with a generator that
raised on every draw (proxy: json-parser 7 and 10, parson 6, tomlc99 3;
C3s: json-parser 9 and 10, tomlc99 8; C3n: json-parser 8). In the four
proxy-arm cases analysed first, the model received the same repair
instruction at iterations 2 to 5 and answered with code 98.4% similar to
the previous iteration; three of the four returned byte-identical modules
on at least two consecutive iterations. Two received the empty
ExceptionGroup message; two received an explicit TypeError or
AttributeError and still resubmitted.

### 6.2 Recovery is a property of the path, not the arm

After a gate event the loop takes one of three paths, decided by what the
next prompt shows the model. Pooled over the 60 proxy and no-steering
replicates:

| path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|
| in place: the failed code with "make exactly one change" | 21 (C2 18, A5 3) | 2 of 21 | 0.98 (min 0.75) |
| fallback: the last working generator | 3 (C2 3) | 2 of 3 | 0.95 |
| re-seed from the grammar with the failure text | 9 (C2 5, A5 4) | 7 of 9 | 0.07 (0.02 to 0.11) |

The pattern holds under the oracle arms, pooled over their 60
replicates: in place 3 of 19 recovered at similarity 0.96 to 1.00, re-seed
10 of 11 at 0.02 to 0.15, fallback 1 of 2 (eval/matrix/full_report.md,
per-target tables). In-iteration repairs, which always show the failed code,
resubmit near-identical code in every in-place arm (mean similarity 0.94
to 1.00). Both arms use the identical seed prompt and guards, so the
iteration-1 gate incidence is sampling variation of one process; within
the proxy arm an iteration-1 gate predicts collapse (4 of 4 collapsed had
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
