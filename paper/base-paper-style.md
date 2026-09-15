# Style study of the base paper (Vikram and Padhye, "Fuzzing with Agents? Generators Are All You Need", arXiv 2604.01442)

Purpose: a reference for the next writing pass. This file documents how the
base paper is written and organised. It proposes no wording for our paper.

## 1. Overall structure

Nine sections in a fixed ACM-style order: Abstract; 1 Introduction (with 1.1
Motivating Example and 1.2 Contributions); 2 Background (three numbered
subsections, one per concept the approach needs); 3 Approach (overview, then
one subsection per component); 4 Evaluation (setup with six numbered
sub-subsections, then one subsection per research question); 5 Related Work
(three themed paragraphs with run-in bold headings); 6 Threats to Validity
(construct, internal, external as run-in headings); 7 Discussion and
Conclusion (three run-in-headed paragraphs); 8 Data Availability; 9
Acknowledgments. Length is about 10,500 words including references; the body
is about 7,500.

The paper is built around one question, stated verbatim at the end of the
introduction's opening paragraphs in italics ("can agentic synthesis of
customized input generators obviate the need for coverage guidance and
mutation-based fuzzing?"), and everything after it is organised to answer
that question. The title is that question, compressed, with the answer
appended.

## 2. Section hierarchy and what each level does

- Numbered sections carry the paper's arc: problem, background, method,
  evidence, positioning, limits, meaning.
- Numbered subsections isolate one concept or one question each. In
  Background: 2.1 the fuzzing loop, 2.2 parametric generators, 2.3
  dominators. In Approach: 3.1 static ranking, 3.2 dynamic feedback, 3.3 the
  agent. In Evaluation: one subsection per RQ, titled "RQn: short noun
  phrase".
- Sub-subsections (4.1.1 to 4.1.6, 3.1.1) are used only for setup facts:
  baselines, benchmarks, duration, repetitions, metrics, scale. Each is a
  short labelled paragraph of two to five sentences.
- Run-in bold headings replace subsections where the content is a sequence of
  short themed paragraphs: in Related Work ("Automatic Fuzz Driver
  Synthesis.", "Large Language Models for Input Generation.",
  "LLM-Synthesized Input Generators."), in Threats ("Construct Validity."),
  in Discussion ("Generators are all you need.", "Agents and
  application-specific analysis.", "The future of agents and
  generator-based fuzzing."), and inside RQ sections ("Branch coverage.",
  "Execution speed.").
- Each RQ section opens by restating its question in italics as a standalone
  line, then one sentence on what was measured, then the evidence, then a
  boxed "Finding n:" statement of two sentences.

## 3. Writing style and tone

- Plain declarative academic prose in the first person plural ("We
  investigate", "We evaluate", "We hypothesize", "We deliberately chose").
  "We" appears in nearly every paragraph of the approach and evaluation, and
  is absent from background paragraphs, which are written as settled fact.
- Present tense throughout for the system and the results ("Gentoo
  constructs", "Coverage improves in 74% of runs"); past tense only for
  actions of the study ("4 runs failed to produce a compilable generator").
- Vocabulary is technical and consistent. Terms are introduced once with a
  definition and then reused verbatim: "predicate", "branch dominance score",
  "predicate coverage report", "parametric generator", "havoc effect". Each
  system configuration has a fixed name (Gentoo-Base, Gentoo-S, Gentoo-L)
  used identically in text, tables and figures.
- Hedged where the evidence is indirect, and the hedge is explicit: "We
  hypothesize that", "suggesting that", "This suggests", "We cannot fully
  attribute". Unhedged where the number is measured.
- Occasional evaluative adjectives to steer the reader, always followed by
  the reason: "The ChocoPy result is surprising.", "The BCEL result is an
  instructive failure case.", "Despite this elegant combination", "This
  contrast has a natural explanation."
- No rhetorical questions in the body except the one motivating question
  and the four RQs.

## 4. Paragraph structure and length

- Typical body paragraph: four to seven sentences, 90 to 160 words.
  Background and approach paragraphs are longer (up to nine sentences); the
  evaluation setup paragraphs are the shortest (two to four).
- Almost every paragraph opens with a topic sentence that states its claim
  or its subject, then supports it, then closes with a sentence that either
  draws the consequence or hands off to the next paragraph. Example, page 2:
  opens "A complementary line of work focuses on building heavyweight ...
  generators", gives CSmith and SQLancer as instances, states what they
  achieve, then ends with "The limitation, however, is that such generators
  require substantial manual effort to write and are tightly coupled to a
  single target." That last sentence is the hook for the next paragraph on
  LLMs.
- One idea per paragraph. When a second idea appears, it gets a new
  paragraph, often signalled by "Notably", "By contrast", "Even so".
- Result paragraphs have a fixed internal shape: the aggregate number first,
  then the per-benchmark spread, then the exception, then the reason for the
  exception. Example, RQ1: "In 6 out of 7 benchmarks ... In 4 of those ...
  The exception is BCEL ... as discussed below, the human BCEL generator
  uses ...".

## 5. Sentence construction and rhythm

- Sentences average about 25 words, but the paper alternates long
  explanatory sentences with short verdict sentences. "The ChocoPy result is
  surprising." (5 words) is followed by a 30-word sentence of evidence.
  "Generators are all you need." opens the discussion.
- Heavy use of the colon to attach a definition or an instance to a claim:
  "inputs that are both structurally valid and semantically meaningful:
  inputs that are too random are rejected early ... while inputs that are
  too simple fail to reach ...". Colons appear several times per page and
  are the main device for moving from abstract to concrete inside one
  sentence.
- Parenthetical clarifications in parentheses, kept short: "(4 statistically
  significant)", "(using Claude Opus 4.5 via AWS Bedrock)", "(e.g., int +
  int)". Numbers that qualify a claim ride inside the sentence rather than
  in a separate one.
- Dashes (en-dash with spaces) are used sparingly for asides in results
  paragraphs; commas and colons do most of the work.
- Lists inside sentences are three items long by default ("compilers,
  parsers, or serialization libraries"; "with statements, labeled
  statements, hashbang lines, and destructuring patterns"), and enumerated
  lists with (1), (2), (3) are used exactly twice: the three requirements for
  synthesis and the two metrics.
- Numbers are written with the comparison built in: "+2% (ChocoPy) to +148%
  (Commons)", "9804 branches versus 7323", "798 inputs took the low-value
  branch (line 207) while only 24 took the high-value branch (line 208), out
  of 822".

## 6. How ideas are introduced, developed and concluded

- Introduction by funnel: the field (fuzzing), the fundamental challenge
  (valid and meaningful inputs), the standard answer (greybox), the refined
  answer (parametric generators), the opposite answer (heavyweight
  generators, no coverage guidance), the new enabler (LLM agents), then the
  question. Six paragraphs, each one step narrower, each ending where the
  next begins.
- A concrete motivating example (1.1) with a real code fragment and a
  specific predicate, used to make the abstract challenge tangible and to
  plant the hypothesis ("We hypothesize that a specialized input generator
  should encode this logic directly"). The same example (ChocoPy TypeChecker,
  line 206/207/208, 798 versus 24 inputs) is reused in Section 3 (Figure 4)
  and again in the RQ2 discussion (Figure 6), so the reader meets one
  running example three times at increasing depth.
- The contributions paragraph (1.2) restates the problem as three
  requirements, names the mechanism, names the system and its three
  configurations, and then previews the evaluation and its "three main
  takeaways" with the actual numbers. The reader knows every result before
  Section 2.
- Background sections end by pointing at the approach: 2.2 ends
  "Understanding which program predicates block deeper exploration, and
  targeting generation toward satisfying them, is the natural next step."
  2.3 opens with the need ("we need a principled way to rank them") and
  closes with the deliverable ("By ranking predicates by dominance score, we
  can identify ...").
- Each RQ closes with a boxed Finding that restates the answer and its main
  qualification in two sentences.
- The discussion opens with the thesis as a four-word heading and then
  widens in three steps: what the result means for fuzzing, what it
  exemplifies about agents, what may come next.

## 7. Transitions

Within paragraphs, transitions are lexical, not signposted: the last noun
phrase of one sentence becomes the subject of the next ("... to produce a new
candidate input x'. The program is executed on x' under instrumentation ...
If x' exercises at least one branch ... it is added to the pool and becomes
eligible for future mutation. This saving criterion ensures ..."). "This",
"These", "The same", "Such" at sentence starts carry the thread.

Between paragraphs, the paper uses four recurring devices:

1. Contrast openers: "A complementary line of work", "By contrast", "The
   exception is", "Despite this similarity in outcome", "We do not observe".
2. Consequence openers: "This contrast has a natural explanation.", "This
   suggests", "This illustrates a limitation".
3. Example openers that name the benchmark first: "The Rhino benchmark
   illustrates this clearly.", "The Commons benchmark illustrates this
   directly.", "The Commons Compress benchmark illustrates a successful
   refinement."
4. Forward pointers at paragraph ends: "as discussed below", "is the natural
   next step", "Figure 4 illustrates the two data structures passed to the
   agent".

Between sections, the last sentence of a section either names the need the
next section fills (end of 2.2, end of 2.3) or the first sentence of the
next section restates the previous section's conclusion in one clause
before moving on (Section 3 opens by repeating the three requirements from
1.2; Section 4's RQ4 opens "As shown in Figure 5, Gentoo-S and Gentoo-L
achieve broadly comparable final coverage", which was RQ3's result).

## 8. Problem, gap and contributions

- The problem is stated as a tension between two existing solutions
  (lightweight generators plus coverage guidance versus heavyweight
  generators without it), each with a named limitation (havoc effect;
  manual effort and single-target coupling).
- The gap is stated as an assumption prior work has not questioned: "these
  approaches use LLMs to improve components within the mutation-based
  fuzzing paradigm, still operating on the assumption that the coverage
  guidance loop itself is necessary." The gap is one sentence and it is an
  assumption, not a missing feature.
- Contributions are not a bulleted list. They are a paragraph that names the
  mechanism, the system, the configurations, the benchmarks, the baselines,
  and then three takeaways with numbers ("First ... Second ... Third ...").
  Each takeaway pairs a measurement with an interpretation introduced by
  "suggesting", "supporting the hypothesis", "indicating".

## 9. Related work

- Placed after the evaluation, not before it, so the reader compares with
  results in hand.
- Three themed paragraphs ordered from least to most similar: fuzz driver
  synthesis, LLMs for input generation, LLM-synthesized generators. Each
  paragraph is a chain of one-sentence summaries ("UTopia [27] extracts
  ...", "PromptFuzz [40] runs ...", "CKGFuzzer [62] introduces ...") with a
  verb that says what the tool does, and closes by relating the group to
  this paper.
- The closest works (ELFuzz, G2Fuzz) get the most space and an explicit
  two-point difference statement: "Gentoo differs in two key ways: ... ; and
  ...". Then what those works did not evaluate, which is exactly what this
  paper evaluates.

## 10. Method explanation

- Overview first, components second. Section 3 opens with the "core idea"
  in one sentence built around "three things", names the system, then
  describes the three configurations in one paragraph by how they differ
  along a single axis ("differ in how the gap is measured and communicated
  to the agent").
- Every mechanism is explained at three levels: prose, a formal or
  structured statement (the dominance score formula; the JSON predicate
  records in Figure 4), and a concrete instance with real numbers (line 206,
  scores 10 and 40, 798 versus 24).
- Design decisions are justified in a separate short paragraph that starts
  "We deliberately chose", giving the alternative that was rejected and why.
- Implementation facts (WALA, Claude Agent SDK, 2-minute fuzzing sessions)
  are stated in one clause each, inline, not in a separate implementation
  section.
- A table (Table 1) summarises the configurations along the axis that
  differs, with the shared parts stated once in the caption.

## 11. Evaluation and results presentation

- Setup is a checklist: techniques and baselines, benchmarks, duration,
  repetitions, metrics, scale. Scale is computed in the text ("3 x 7 x 5 =
  105 agent synthesis runs ... 280 three-hour fuzzing experiments ... 39
  CPU-days") and failures are counted there too ("4 runs failed").
- Cost is reported in dollars per synthesis, in the baselines paragraph.
- One figure per RQ, referenced by name in the first sentence of the
  evidence paragraph. Figures are normalised so that one line (the human
  baseline, or iteration 1) is the reference and everything else is a ratio
  to it. Statistical significance is marked in the figure (asterisk, filled
  versus hollow markers) and defined in the caption. Captions are two to
  three sentences: what is plotted, how to read it, and the headline ("In 4
  out of 7 benchmarks, at least one agent-based approach significantly
  higher coverage").
- Tables carry the raw numbers with mean and standard deviation, and their
  captions say what the number reflects ("reflecting the throughput cost of
  more complex generators").
- Results text does not repeat the table; it reads the table for the reader:
  aggregate, range, exceptions, mechanism behind the exception.
- Each RQ has one to three case studies, each anchored on one benchmark,
  each explaining a result by what the generator's code actually does ("The
  human generator maintains a live list of declared class names and selects
  a previously-declared class as the superclass"). Negative and surprising
  results get the longest case studies (BCEL, ChocoPy, Closure regression).
- A code figure (Figure 6) shows an excerpt of a synthesized generator to
  make the mechanism concrete, with a caption that states the trade-off the
  code embodies.

## 12. Interpretation and discussion of results

- Interpretation follows evidence in the same paragraph, introduced by
  "suggesting", "This suggests", "This contrast has a natural explanation",
  "We hypothesize". The paper never leaves a number uninterpreted and never
  interprets without a number in the preceding sentence.
- Alternative explanations are raised by the authors themselves before a
  reviewer can ("An agent may improve coverage between iterations for
  reasons unrelated to predicate feedback"), and either answered or
  explicitly conceded ("We cannot fully attribute").
- The Findings boxes are the paper's interpretive spine; the discussion
  section does not restate them but generalises them.
- Limitations are stated in the results where they occur ("This illustrates
  a limitation: predicate feedback may lead the agent to optimize in the
  wrong direction when the signal is ambiguous") and again, grouped, in
  Threats.

## 13. Conclusion

- Combined with discussion. Three paragraphs, each with a thesis-style
  run-in heading. First: the direct claim and its practical consequence
  ("a shift in focus from fuzzer engineering to generator synthesis").
  Second: the broader pattern the result exemplifies. Third: the outlook,
  hedged with "We hope to see" and "potentially". No summary of the
  sections, no repetition of numbers.

## 14. Level of technical detail

- Enough to reimplement the mechanism (formula, data formats, tools, time
  budgets, prompts summarised in a table) but no code walkthroughs of the
  system itself; code appears only as short illustrative excerpts.
- Statistics are named once (Mann-Whitney U, p < 0.05) and then referred to
  by marker. Effect sizes are reported as percentages relative to a
  baseline, not as standardised measures.
- Every specific claim has a number or a citation attached in the same
  sentence.

## 15. Coherence devices

- One running example (ChocoPy) from introduction to results.
- Fixed names for configurations, benchmarks and artefacts, used
  identically everywhere.
- The four RQs are listed once, then each becomes a subsection title, then
  each gets a Finding box; the abstract and contributions preview the same
  three or four results in the same order.
- Figures are numbered in order of first mention and every figure is
  mentioned in prose.
- Cross-references are by section or figure number and are frequent ("from
  Section 2", "in the format described in Section 3.1.1", "As shown in
  Figure 5").

## 16. Recurring patterns that make it convincing

- Claim, number, exception, mechanism: every result paragraph.
- Concrete before abstract in examples, abstract before concrete in method.
- Naming the surprise ("surprising", "instructive failure case") and then
  explaining it, which reads as candour and pre-empts the reviewer.
- Reporting what did not work (BCEL, Closure regression, four failed runs)
  in the same register as what did.
- Quantifying scale and cost so the reader can judge the evidence.
- Ending each unit (paragraph, subsection, RQ) with a sentence that says
  what it means, so nothing is left for the reader to conclude alone.

## 17. Blueprint to adopt in the next pass

Structure
1. Front-load the question in the introduction and answer it in the title,
   abstract, contributions and discussion, in the same words each time.
2. Introduction as a funnel of five or six paragraphs, each ending where the
   next begins; then a motivating example with real code and real numbers;
   then a contributions paragraph that previews the results with numbers.
3. Background subsections that each end by naming what the approach needs.
4. Approach: overview paragraph with the core idea and the axis along which
   conditions differ; one subsection per component; prose, then formal
   statement, then instance; a "we deliberately chose" paragraph for the
   main design decision; a configuration table.
5. Evaluation: labelled setup sub-subsections (baselines, targets,
   budgets, repetitions, metrics, scale with arithmetic and failure counts),
   then one subsection per RQ, each opening with the question in italics,
   one figure, evidence in the order aggregate, spread, exception,
   mechanism, then a boxed Finding.
6. Related work after the evaluation, themed paragraphs ordered by
   closeness, closest works given a two-point difference statement.
7. Threats as three run-in headings; each threat answered or conceded.
8. Discussion and conclusion merged: thesis heading, broader pattern,
   outlook. No section summary.

Paragraphs and sentences
9. Topic sentence, support, consequence or hand-off. Four to seven
   sentences.
10. Alternate long explanatory sentences with short verdict sentences.
11. Use colons to go from claim to instance within a sentence; use
    parentheses for the qualifying number.
12. One running example reused at increasing depth.
13. Attach a number or a citation to every specific claim in the same
    sentence.

Transitions
14. Lexical chaining: the object of one sentence is the subject of the next.
15. Paragraph openers from a small set: contrast ("By contrast", "The
    exception is"), consequence ("This suggests"), named example ("The X
    benchmark illustrates"), and forward pointers at paragraph ends.
16. Section boundaries: end with the need the next section meets, or open by
    restating the previous conclusion in one clause.

Results and interpretation
17. Read the figure for the reader; never restate the table.
18. Interpretation in the same paragraph as the evidence, introduced by
    "suggesting" or "This suggests"; hedges explicit and proportionate.
19. Name surprises and failures as such, then explain them by mechanism.
20. Finding boxes as the interpretive spine, two sentences each: the answer,
    then the qualification.
