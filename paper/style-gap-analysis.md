# Our paper against the blueprint (analysis only, 2026-09-15)

Source: paper/paper.md at commit cfc62aa (about 10,000 words, 13 sections).
Blueprint: paper/base-paper-style.md, section 17. No text was changed.

## A. Defects to fix regardless of style

1. The References section opens with an internal note ("The first seven
   entries were read ... MUST be checked against their sources before
   submission"). It is in the PDF.
2. Tables 3, 4, 5 and 6 are cited in the text (RQ1, taxonomy, branch-fired
   histogram, cost) but do not exist in the paper; they are files in the
   artifact. A journal reader cannot follow them.
3. The data-availability statement says the artifact repository is "named in
   Section 10"; Section 10 names no repository and no URL appears anywhere.
4. The reference list has ten entries, one of them "Zhang, et al. (2025).
   G2Fuzz." with no authors or title. The introduction cites one work.
5. The "does not claim" paragraph in the introduction says the paper does not
   claim "that the proxy is a poor approximation of coverage across
   generators"; the sentence reads as a double negative and the point (the
   proxy tracks coverage across generators but not within a run) is lost.
6. RQ2 is never labelled. Results subsections are titled RQ1, RQ3, RQ4, RQ5;
   the confirmatory family (H1, H2) is presented without an RQ number and the
   RQ list is never shown as a set.

## B. What already works

- The central question is stated early ("what the refinement loop should be
  told", introduction paragraph 2) and the answer is consistent across
  abstract, contributions, Section 6.4, discussion and conclusion.
- Rigor is visible and specific: pre-registration, one primary outcome, ten
  replicates, effect sizes with intervals, Holm, sensitivity, deviations
  listed with amounts spent.
- Surprises and failures are named and explained by mechanism: the
  development-target confound (5.1, "a mistake with a benefit"), Grammarinator
  beating every LLM condition on tomlc99, the wrong pre-registered prediction
  about issue 50, the collapsed replicates, the logging defect.
- Several results paragraphs already follow aggregate, spread, exception,
  mechanism (5.2 H2s, 5.4, 5.6 "Three results").
- Interpretation is attached to evidence in 5.4, 5.5, 5.6 and throughout the
  discussion; hedging is explicit ("suggests", "may", "cannot be
  distinguished").
- Subsection titles state findings ("5.3 Refinement moves the seed by one to
  two points"), which is the base paper's Finding box in another form.
- Related work is themed, moves from closest to broadest, and states the
  difference from Gentoo, ELFuzz and G2Fuzz explicitly.
- Threats are concrete and each one is either answered with a measurement
  (batch drift, equal time) or conceded (one model, logging defect).
- Discussion uses run-in bold headings and is analytical (three readings of
  the heterogeneity).
- Cost and scale are quantified.

## C. What is weak

Introduction and framing
- The funnel is three paragraphs. It opens with a coverage number from the
  pilot rather than the field's problem, reaches Gentoo in paragraph 1, and
  states the gap as a change of regime ("the other corner") rather than as an
  assumption prior work has not questioned. That assumption is stated only
  in related work ("neither asks whether the fitness is needed").
- One citation in the whole introduction; the base paper has a dozen in its
  first two paragraphs. Background context (structured-input fuzzing,
  grammar-based generation, LLM-written generators, agentic loops) is
  asserted without references.
- Contributions are a four-item numbered list with results packed into each
  item; item 4 is a grab-bag ("Plus a failure taxonomy ..."). No motivating
  example anywhere in the paper.
- The title states the comparison, not the answer. The abstract is one
  300-word paragraph carrying about twelve results; the four takeaways are
  not separated from the rest.

Background
- Two paragraphs, no subsections, no stated purpose. It describes
  Grammarinator and Hypothesis (needed), then the sanitizer harness and the
  coverage build (methods material). It never ends by pointing at what the
  approach needs. There is no background on synthesis-time refinement loops
  and their signals, which is the concept the whole paper rests on.

Approach
- No overview paragraph that states the core idea and the single axis along
  which arms differ before the components; 3.3 carries the axis implicitly.
- No figure of the loop and no configuration table; Table 1 is targets.
- The proxy, the object of study, is explained at one level (a list of
  features in prose). There is no formal statement of how the summary
  becomes a score and an edit, and no concrete instance (one iteration's
  summary and the edit it produced).
- Design decisions are justified in passing or not at all: the blind
  setting, "exactly one change", the gate thresholds, five rounds of 500
  inputs, the crash-first rule. There is no "we chose X over Y because"
  paragraph.
- 3.2 is a 170-word paragraph carrying four guards, two repair paths and the
  rule for gated iterations.

Experimental design
- No RQ list, no statement of how each RQ serves the central question. The
  registered RQ numbers (RQ1, RQ3, RQ4, RQ5 plus H1/H2) are used as labels
  without being introduced.
- 4.6's deviations paragraph is one 200-word sentence chain; the budget
  accounting reads as a ledger.

Results
- Section 5 opens with a pointer paragraph, then Table 1, Table 2 and
  Figure 1 before any argument. Table 1 (targets) belongs in 4.2.
- Figures are introduced by fragments ("Figure 3 and Table 2.", "Figure 5
  and eval/matrix/rq3_report.md.") rather than by a sentence that says what
  to look for.
- 5.3 is a list of deltas per target with one interpretive sentence at the
  end. 5.7 is a list of counts with one mechanism clause. 5.8 and 5.9 are
  fine as short paragraphs but are not tied back to the question.
- Density: mean sentence length 34 words; 77 of 239 body sentences exceed
  40 words; 11 are eight words or fewer. The base paper alternates 25-word
  sentences with 5-word verdicts. Paragraphs average 121 words with a
  maximum of 335 (the Internal threats paragraph).
- Parenthetical stacking: several sentences carry three or four bracketed
  qualifications (5.2 H1 paragraph, 5.3, 8 Internal).
- No end-of-RQ statement of the answer; the subsection title does that job
  at the top, but the reader leaves each subsection on a number.

Mechanism (Section 6)
- Strong content and a clear table. It opens cold with a bracketed
  provenance note; there is no bridge from 5.7 (the taxonomy) to 6.1 (the
  collapses), although the taxonomy is what motivates it. 6.3 opens with a
  fragment.

Discussion, conclusion, related work
- The discussion repeats numbers from Sections 5 and 6 (repair counts, cost)
  instead of only generalising them. The conclusion restates the abstract.
- Related work sits after threats; it is thin on LLM property-based-test
  generation and on evaluation-methodology references, and the introduction
  does not use it.
- "What Gentoo's thesis looks like from below" is the paper's broader
  pattern paragraph and is the best candidate for the discussion's opening
  thesis; it is currently fourth.

Voice and terminology
- Arms are named inconsistently across text, tables and figures: C2 /
  "proxy" / "C2 proxy"; C2R / C2' / "re-seed repair"; "coverage" / C3s /
  "coverage-scalar oracle". The base paper uses one fixed name per
  configuration everywhere.
- Some paragraphs are telegraphic (fragments as topic sentences); others
  editorialise ("does not earn its place"). The register moves between
  lab-notebook and essay.

## D. Structural changes to make before rewriting (conflicts with the blueprint)

1. Introduction: rebuild as a five- or six-paragraph funnel with
   citations: structured-input fuzzing and grammar-based generators; LLM
   and agent authorship of generators (Gentoo, ELFuzz, G2Fuzz); the
   assumption those loops share (a coverage-derived fitness at synthesis
   time, evaluated in single runs); the regime we study and why it is worth
   studying (cheap, blind, synthesis-time); the question; a short preview
   of the answer. Then the motivating example, then contributions as a
   paragraph with First/Second/Third/Fourth, each pairing a measurement
   with its interpretation and section pointer. Fold the "does not claim"
   paragraph into the contributions as explicit hedges.
2. Motivating example: one replicate's repair trace (a gate failure, the
   in-place repair prompt, the near-identical resubmission, the collapse)
   with the real similarity numbers, introduced in 1.1, referred to in 3.2
   when the repair paths are defined, and expanded in 6.1. Every number must
   be read from the run directory before it is written.
3. Background: three purposeful subsections. 2.1 Grammar-based generators
   and property-based strategies (ends with what an LLM-written strategy
   is and how it fails). 2.2 Synthesis-time refinement of generators and
   the signals prior loops use (ends with the untested assumption). 2.3
   Measuring a generator: coverage of the parse-reachable region and why
   replication is the unit (ends with the primary outcome). Move the
   sanitizer harness and coverage build to Section 4.
4. Approach: open with a core-idea paragraph naming the single differing
   axis; add a loop schematic (Figure) and a configuration table (arm,
   what the model sees, what decides rollback and best, edit vocabulary);
   present the proxy at three levels (prose, the score and decision rule,
   one recorded iteration's summary and edit); add a design-decision
   paragraph for the blind setting and the one-change edit, with the
   alternatives; keep the crash-first rule here but shorten 5.1.
5. Evaluation: list the RQs once with their link to the central question,
   keeping the registered numbers, and give the confirmatory family its RQ
   label. Order the results subsections by RQ number or state the
   presentation order explicitly. Move Table 1 to 4.2.
6. Results: every RQ subsection opens with the question, then one sentence
   on what was measured, introduces its figure with what to look for,
   argues aggregate, spread, exception, mechanism, and closes with a
   two-sentence answer. Rewrite 5.3 and 5.7 as arguments. Either bring
   Tables 3 to 6 into the paper (or a supplement) or drop the table numbers
   and describe the artifact files. Add a bridge sentence from 5.7 to
   Section 6.
7. Discussion: lead with the broader pattern (Gentoo from below), keep the
   three readings, drop repeated numbers, fold Cost into 5.8, end with
   "what would change the conclusion". Shorten the conclusion to a
   forward-looking half page that does not restate the abstract. Consider
   moving related work before threats and adding the missing themes and
   references; use those references in the introduction.
8. Terminology: fix one name per arm and use it identically in text, tables
   and figures (figure legends and Table 2 must be regenerated to match).
9. Sentence level, applied everywhere: split sentences over 40 words; add
   short verdict sentences at paragraph ends; one parenthetical per
   sentence; no fragments as topic sentences; first person plural for the
   study's actions.
10. Title: consider a title that carries the finding, as the pre-registered
    neutral title was a registration device and the paper may now state its
    result (record the change as a disclosed deviation if the registered
    title is kept as the running title).
