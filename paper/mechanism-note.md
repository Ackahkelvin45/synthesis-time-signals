# Mechanism note: why the proxy loop hands back unusable generators (2026-09-13)

Log-only analysis of all 60 stage-1 replicates (30 C2, 30 A5; json-parser,
parson, tomlc99). Script: eval/mechanism.py; per-replicate data:
eval/mechanism.jsonl; generated tables: eval/mechanism.md. No runs, no API
calls. This is a hypothesis-generating analysis outside the confirmatory
family (pre-registration, exploratory guard); it will be written up as the
paper's mechanism section.

## Finding 1. Collapse is fixation, and the fixation is total

The four collapsed C2 replicates (json-parser rep7, rep10; parson rep6;
tomlc99 rep3) received the SAME repair instruction at iterations 2, 3, 4 and
5 (one distinct instruction across the four refinements, versus 2.46 in the
26 healthy C2 replicates) and answered it with code 98.4% similar to the
previous iteration (0.984 mean consecutive similarity; three of the four
returned byte-identical modules on at least two consecutive iterations). The
model did not change what the error told it to change; it resubmitted.

Two flavours. In both json-parser cases the error text the model received
was Hypothesis's wrapper, "ExceptionGroup: Hypothesis found 2 distinct
failures. (2 sub-exceptions)", which names no exception, line or construct:
the repair prompt carried no information, and the loop's error formatter
(`_fmt_gen_error`) passes the group's message rather than its
sub-exceptions. In the parson and tomlc99 cases the error was explicit
(`TypeError: can only concatenate str (not "OneOfStrategy") to str`;
`AttributeError: 'function' object has no attribute 'validate...'`) and the
model still resubmitted the same code. So an uninformative error guarantees
fixation, and an informative one does not prevent it.

## Finding 2. The repair PATH, not the steering arm, decides recovery

After a gate event the loop takes one of two paths. A build rejection
(the module does not import or fails the AST screen) discards the code and
RE-SEEDS from the grammar with the rejection appended. A gated generator (it
builds but fewer than 5% of gate draws are accepted, or it raises while
drawing) is kept as the current code and re-prompted IN PLACE: "Make EXACTLY
ONE change: fix_generator_error — <error>". Across both arms:

| path after a gate event | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|
| in-place repair | 24 (C2 21, A5 3) | 4 of 24 | 0.98 (min 0.75) |
| re-seed | 9 (C2 5, A5 4) | 7 of 9 | 0.04-0.10 |

Recovery is a property of the path: the in-place path almost never works
and the re-seed path usually does, in both arms. This is the mechanism.
The "exactly one change" framing plus the already-broken code anchors the
model on its own output; a fresh prompt does not.

## Finding 3. Why C2 collapsed and A5 did not: mostly chance, one real asymmetry

Both arms use the identical seed prompt at iteration 1 and the identical
gate/repair machinery, so the iteration-1 gate incidence (C2 9/30, A5 4/30)
is sampling variation of the same process. Given an iteration-1 gate,
collapse followed 4 of 9 times in C2 and 0 of 4 in A5; three of A5's four
early gates were build rejections (re-seed path) and one was an in-place
gate that recovered. The cross-arm collapse rate (4/30 vs 0/30, Fisher
p = 0.11) is not established, and the mechanism analysis says it should not
be expected to be: the arms differ in steering, and steering never runs on a
gated iteration. Within C2, an iteration-1 gate predicts collapse (4/4 vs
5/26 among the healthy, Fisher p = 0.0046); the five that recovered from an
iteration-1 gate were all tomlc99 and four of the five went through the
re-seed path.

## What this changes

- The collapse rate is a property of the validity machinery's repair path
  and of the error text it carries; it belongs in the paper as the
  mechanism, with the two-path table above as the key exhibit.
- Two loop defects are now documented: (a) `_fmt_gen_error` forwards an
  ExceptionGroup's wrapper message instead of its sub-exceptions; (b) the
  in-place repair path anchors the model on broken code. Neither is changed
  during Stage 1 (design frozen); both are candidates for a registered
  follow-up condition ("repair by re-seed") rather than a silent fix.
- For the primary analysis nothing changes: collapsed replicates score 0 as
  registered, and H1 is reported per target with and without them
  (the latter exploratory).

## Correction (2026-09-13, DECISIONS D27)

The two-path table above classified the path by the next edit instruction,
so every `fix_generator_error` counted as in-place. Three of those 24 cases
followed a build rejection or a mid-run error after which the loop fell back
to its last WORKING generator: the model was shown working code, not the
failed code. `eval/stage1c_report.py` now classifies by what the next prompt
contains (a seed prompt; the failed iteration's own code; or neither).
Corrected, same 60 replicates:

| path after a gate event | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|
| in-place (failed code shown) | 21 (C2 18, A5 3) | 2 of 21 | 0.98 (min 0.75) |
| fallback refine (last working generator shown) | 3 (C2 3) | 2 of 3 | 0.95 (0.92-0.98) |
| re-seed | 9 (C2 5, A5 4) | 7 of 9 | 0.07 (0.02-0.11) |

The finding sharpens: shown its own failed code, the model recovers about one
time in ten. In-iteration repairs (same iteration, repair re-prompt on the
gated code) resubmit near-identical code in every arm (0.96-1.00). The
follow-up condition C2' (repair by re-seed) was run; see D27.
