# Draft: Sections 3 (Approach), 4 (Experimental design), 7 (Threats to validity)



---

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

Three C parsers, three grammars, two formats: json-parser (JSON; the
development target, on which the proxy was designed, reported separately),
parson (JSON; held out), tomlc99 (TOML; held out). Each has a sanitizer build
(ASan and UBSan, -O0, no recovery) used by the loop, a coverage build used
only for measurement, and, for json-parser and tomlc99, sanitizer builds at
pinned pre-fix commits of known bugs (Section 4.5). Absolute coverage is not
comparable across targets; every comparison is within a target.

The primary outcome's denominator is the parse-reachable region: the
functions reachable from the harness entry point in the static call graph,
unioned with any function observed covered by any condition. It is committed
per target and its hash is recorded in every run and every measurement.

### 4.3 Conditions, replicates, and order

Loop conditions C2, A5, C3s and C3n, ten independent replicates each per
target (120 runs), plus C2' on json-parser and tomlc99 (20 runs). Fixed generators: random text,
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
and C3n on all three targets, were run as blocks after phases 1a and 1b
rather than interleaved with them, so provider drift is not orthogonal to
those cells (the served model identifier was constant across every batch);
C2' was added after the mechanism analysis and is outside the confirmatory
family; Stage 2 targets, the AFL++ reference row and the second model were
not run for this submission. The registered Stage 1 budget was 4.00 USD;
3.80 USD was spent on 140 runs, plus about 0.03 USD on attempts discarded
after network failures.

## 7. Threats to validity

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
prompt) shows no shift: A12 0.43 to 0.61, p > 0.15, on every target. The bug
campaigns are time-budgeted and ran nine at a time on an eleven-core machine
under heavy load; the load was shared by every arm, so it compresses every
campaign's input count alike, but inputs-to-trigger is the more reliable of
the two trigger measures and is the one reported first.

**External.** Three small C parsers of two text formats; one model family;
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
