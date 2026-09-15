# Revision plan (decided 2026-09-15; no text changed yet)

Inputs: paper/base-paper-style.md (blueprint), paper/style-gap-analysis.md
(gap analysis), the user's review of 2026-09-15. Source of truth for every
number: the run directories and eval/matrix reports at commit cfc62aa.

## Decision 1: motivating example = the repair-trace collapse (option A)

Evidence read from the run directories (runs/<target>/<arm>-rep<k>/iter-*/):

| replicate | iteration-1 gate error | code similarity iter k to k-1 (2..5) | outcome |
|---|---|---|---|
| parson C2-rep6 | TypeError: can only concatenate str (not "OneOfStrategy") to str | 0.999, 0.992, 1.000, 1.000 (173 to 177 lines) | gated at every iteration, collapsed |
| tomlc99 C2-rep3 | AttributeError: 'function' object has no attribute 'validate' | 1.000, 1.000, 1.000, 1.000 (385 lines, byte-identical) | collapsed |
| json-parser C2-rep7 | ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub-exceptions) | 0.752, 1.000, 1.000, 1.000 | collapsed |
| json-parser C2-rep10 | same ExceptionGroup message | 1.000 x 4 | collapsed |

Every iteration-2 to iteration-5 prompt in these runs ends with the same
instruction: the failed module in full, "No run feedback is provided.", and
"Make EXACTLY ONE change to the strategy: fix_generator_error, <error
text>". The model answered with the same module.

Why A over B (the parson coverage gain):

- It motivates the central question directly. The question is what the loop
  should tell the model; the example shows the loop telling the model the one
  thing that turned out to be harmful (its own failed code) and the model
  doing nothing useful with it. The parson gain motivates only the H2s
  cell.
- It is concrete at the level the base paper's example is: a real error
  message, a real instruction, a real similarity number, a real outcome, all
  in one replicate. The parson gain is a mean over ten replicates (+1.59,
  p 0.008) whose per-iteration in-loop scores rise from about 73 to about 77
  with no single edit that explains the gain; a code excerpt would have to be
  chosen after the fact and would not carry the result.
- It is the paper's actionable finding and its only pre-specified
  intervention (C2', 0 collapses in 20 runs), so the example reappears in
  3.2 (the two repair paths), 5.7 (the taxonomy class), 6.1 (the four
  analysed collapses), 6.3 (the intervention) and the discussion.
- It does not pre-empt the confirmatory result. Leading with the parson gain
  would foreground the one cell that does not survive correction and would
  read as overclaiming.

Primary instance: parson C2-rep6 (an explicit TypeError, the
strategy-versus-value confusion that is the second-largest failure class,
similarity 0.999 at the first resubmission). Secondary instance for 6.1:
tomlc99 C2-rep3 (byte-identical resubmission four times). The ExceptionGroup
runs illustrate the empty-message variant in 5.7 and 6.1 as now.

Depth plan: introduction (1.1) gives the error, the instruction, the
resubmission and the outcome in prose, one similarity number; 3.2 names the
two repair paths and says which one this run took; 6.1 gives the
per-iteration table for the four analysed collapses; 6.3 shows what C2' did
on the same target.

## Decision 2: Tables 3 to 6 enter the main paper, condensed (option A)

What exists in the artifact:

- Table 3 (RQ1): no table exists; eval/matrix/rq1_report.md is prose bullets.
  A four-row table (target; random text; Grammarinator defaults;
  depth-matched; LLM seed mean; A12 healthy seeds vs the stronger
  variant) is the natural form and carries the RQ1 answer. Build it in
  eval/tables.py as T3 from fixed.jsonl and stage1.jsonl, so it is
  generated, not typed.
- Table 4 (taxonomy): eval/matrix/taxonomy.md has an 11-row by 7-column
  cause-by-arm table. Fits one column width. Include as generated.
- Table 5 (branch-fired histogram): exists only as a table in DECISIONS.md
  D28 (three targets by four arms, edit counts). It is the sole evidence
  for the development-target confound (5.1), which is contribution four.
  It must be in the paper. Generate it from the runs (evolution.md "next:"
  lines) in eval/tables.py as T5 rather than copying from D28, and extend
  to cJSON.
- Table 6 (cost): 18 rows by 10 columns is too wide for the column.
  Condense to one row per target (runs, mean USD, mean wall minutes, mean
  tokens in and out) plus the total, generated as T6; the per-arm table
  stays in the artifact.

Why A over B or C: each of the four carries a claim the text makes with
numbers (RQ1 answer, failure classes, the confound, cost), and a reader of a
journal paper cannot be sent to repository files for the evidence behind a
numbered claim. EMSE has no page limit that forces a supplement. Option C
(drop the numbers) would remove the evidence for 5.1 and 5.7 from the paper.

All four are inlined by eval/assemble_paper.py from eval/matrix/tables.md
like T1 and T2, so a regenerate rebuilds them.

## Revision order

Ordered so that each step's output is what the next step needs, and so that
the mandatory defects are fixed first.

1. Mandatory defects (no restructuring yet): delete the note in References;
   add the artifact URL to Data availability and Section 10 (user supplies
   the URL); complete the G2Fuzz entry from its USENIX page; label RQ2 and
   list the RQ set in 4.6; rewrite the "does not claim" paragraph as
   positive hedges. Rebuild, commit.
2. Terminology: fix the canonical arm names (one name each, code kept in
   parentheses at first mention only), update eval/tables.py, eval/figures.py
   labels and legends, regenerate Table 2 and Figures 1 to 6.
3. Tables 3, 5 and 6 as generated tables in eval/tables.py; Table 4 pulled
   from taxonomy.md; assemble_paper.py inlines T3 to T6 at markers.
4. Motivating example: read parson C2-rep6 and tomlc99 C2-rep3 in full
   (prompts, responses, stats), record every number used in a scratch note
   with its file path, then write 1.1.
5. Introduction funnel and contributions paragraph (uses the example from
   step 4 and the references from step 8; write the references first if
   step 8 has not run, then come back).
6. Background split into 2.1, 2.2, 2.3, each ending with what the approach
   needs; move the harness and coverage build to 4.2 and 4.4.
7. Approach: overview with the differing axis; loop schematic (new figure,
   drawn from the pipeline, hand-sketched style per the user's preference);
   configuration table (generated or hand-written; it is design, not data);
   proxy at three levels using one recorded iteration's summary (read from
   a run's stats.json and evolution.md); design-decision paragraph.
8. Related work: add the missing themes and references (LLM property-based
   test generation; evaluation methodology beyond Klees), check every entry
   against its source, then use them in the introduction. Keep it after the
   evaluation.
9. Evaluation section: RQ list once, with links to the central question and
   the confirmatory/exploratory label; Table 1 moved to 4.2; setup as
   labelled sub-subsections including scale arithmetic.
10. Results, one RQ subsection at a time in the question, measurement,
    figure, aggregate, spread, exception, mechanism, answer shape; 5.3 and
    5.7 rewritten as arguments; every figure introduced with what to look
    for; a two-sentence answer closing each subsection; the bridge from 5.7
    to Section 6; Cost folded into 5.8 with Table 6.
11. Section 6: open with the bridge, expand 6.1 with the example table, keep
    6.2 and 6.3, end 6.4 as the hand-off to the discussion.
12. Discussion reordered: broader pattern first, three readings, proxy,
    development target, repair policy without repeated numbers, what would
    change the conclusion. Conclusion cut to half a page, forward-looking.
13. Threats: keep; split the Internal paragraph into topic paragraphs;
    check every cross-reference after renumbering.
14. Sentence pass over the whole paper: split over 40 words where the
    sentence carries two ideas, one parenthetical per sentence, no fragment
    topic sentences, verdict sentences at paragraph ends, first person
    plural for the study's actions.
15. Title: keep the registered title as the running title; propose one
    finding-bearing display title for the user's decision, disclosed in
    4.1 as a presentation change, not a registration change.
16. Assemble, build, read the PDF page by page, run tests, commit, bundle.

Numbers rule for every step: a number enters the text only after it has been
read from a file in this session, and the file is named in the scratch note.
