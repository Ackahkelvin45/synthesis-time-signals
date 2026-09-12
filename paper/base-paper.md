# Base paper and positioning

Literature pass done 2026-09-12 (web search + abstract/full-text reads; every
claim below was read from the paper page, not recalled). Purpose: pick the
anchor paper(s) the write-up positions against, and adjust the experiment
plan before spending more on runs.

## Recommendation

**Primary base paper: Vikram and Padhye, "Fuzzing with Agents? Generators Are
All You Need", arXiv 2604.01442 (April 2026, CMU).**

**Secondary: Chen, Dolan-Gavitt, Lin, "ELFuzz: Efficient Input Generation via
LLM-driven Synthesis Over Fuzzer Space", USENIX Security 2025 (arXiv
2506.10323).** Plus Zhang et al., "G2Fuzz" (USENIX Security 2025, arXiv
2501.19282) as the sibling.

Framing/background: Fuzz4All (Xia et al., ICSE 2024), Zest (Padhye et al.,
ISSTA 2019), Ackerman and Cybenko, "LLMs for Fuzzing Parsers" (FUZZING 2023
registered report), Park and Yun, "Agentic Fuzzing: Opportunities and
Challenges" (arXiv 2605.10074, May 2026), Klees et al., "Evaluating Fuzz
Testing" (CCS 2018) for the statistics protocol.

## Why Gentoo is the anchor

Same object of study as ours: an LLM iteratively synthesizes and refines an
input **generator** (not inputs), and the paper asks whether coverage feedback
is needed at all. Key facts (read from the full text):

- Agent: Claude Opus 4.5 via the Claude Agent SDK, terminal access, library
  source code, JQF tooling. Three configs: Base (raw fuzzing output only),
  S (static dominator analysis + per-branch coverage reports), L (agent ranks
  predicates from source + same coverage reports).
- Targets: 7 Java libraries (BCEL, Bouncy Castle, Closure, Commons Compress,
  Gson, Rhino, ChocoPy). Baselines: human-written Zest/JQF generators.
- Protocol: 5 repetitions per config, 1 h synthesis cap, 3 h fuzz campaign per
  generator, Mann-Whitney U at p<0.05, mean and SD. Cost $7.5 to $12.8 per
  synthesis run.
- Results: agent generators beat human generators on 4 of 7 (significant).
  Coverage-guided mutation adds only -0.1% to +2.0% for agent generators (not
  significant) versus about +40% for human generators. Their conclusion:
  "structural and semantic logic encoded in the agent generators makes
  coverage guidance largely unnecessary."
- Threats they state: Java/JQF only, one model, possible memorization of
  library source, fixed-time campaigns.

## Where we differ (the gap statement, rewritten)

Gentoo's agent is white-box and expensive: it reads the library source, runs
the fuzzer itself, and gets predicate-level coverage reports, at roughly ten
dollars per synthesis. We study the opposite corner:

1. **Blackbox at synthesis time.** No source, no coverage, no instrumentation.
   The only specification is the formal grammar plus an empirically derived
   note of where the library deviates from it. The model sees exit codes and
   its own generated inputs.
2. **Cheap author.** deepseek-chat at about two cents per five-iteration run,
   three orders of magnitude below Gentoo. Whether a weak author needs
   structured feedback is an open question their setup cannot answer.
3. **The signal itself is the subject.** Gentoo asks whether coverage helps at
   fuzz time. We ask what a refinement loop should optimize when coverage is
   unavailable, and decompose the proxy signal causally (production gap,
   depth mass, novelty guardrail, probe repair) against a no-signal control.
4. **C targets with sanitizers**, multi-format (JSON, INI, CSV, TOML), which
   is exactly the external-validity gap they list.
5. **Reproducibility of the evaluation itself**: the seeded-Hypothesis
   process-history finding (DECISIONS D13) has no counterpart in their paper.

The sharpest way to state the paper: Gentoo says a strong agent does not need
coverage at fuzz time. We test whether a weak, blind author needs structured
feedback at synthesis time. Our A5 (no-signal) control is a direct probe of
their thesis in the blackbox regime. Either outcome is a result:

- A5 ~ C2: their finding extends downward to cheap blind authors; the paper
  becomes a replication plus a validity/guard study (what still matters is
  the acceptance gate, repair, and rollback, not the steer).
- C2 > A5 (and specific ablations explain it): structured feedback matters
  once the author cannot see source or coverage, which bounds their claim.

## What ELFuzz and G2Fuzz contribute to our design

- **ELFuzz** evolves whole fuzzer programs under an edge-coverage fitness
  (CodeLlama-13B, 20 to 55 h synthesis per target). Baselines: Grammarinator
  with ANTLR4 grammars, ISLa, ISLa+ISLearn, GLADE. Targets: jsoncpp, libxml2,
  re2, SQLite, CPython, cvc5, librsvg. Protocol: 10-minute generation, 24 h
  AFL++ mutation, 10 repetitions, mean and SD, no significance tests.
- **G2Fuzz** has the LLM write and mutate Python input generators for
  non-textual formats (TIFF, MP4, PDF), hybridized with AFL++; baselines
  AFL++, Fuzztruction, FormatFuzzer.

Two consequences for us:

1. **We are missing the expected external baseline.** Both papers' community
   expects Grammarinator on the same ANTLR grammar. Our C0 (random text) vs C1
   (LLM seed) conflates "having a grammar" with "LLM authorship". Add
   **C0b = Grammarinator over the identical JSON.g4** so RQ1 can separate the
   two. This is a bigger gap than target count.
2. **Repetition bar.** Gentoo uses 5 loop repetitions, ELFuzz 10 fuzzing
   repetitions. Plan 5 loop replicates per target rather than 3; cost is
   still cents.

## Other papers checked and why they are not the anchor

- Fuzz4All (ICSE 2024): LLM produces inputs, not generators; compiler targets;
  autoprompting loop. Cite as the input-generation line.
- Ackerman and Cybenko (FUZZING 2023): registered report, LLM parser fuzzing
  via spec ambiguity; early and small. Cite for parser focus.
- Park and Yun (May 2026): position paper on agentic fuzzing; useful for the
  "single extended run" evaluation critique and the harness-engineering
  challenge. Not an empirical anchor.
- Zhong et al. arXiv 2410.21806 ("LLM-based JSON parser fuzzing"): withdrawn
  by the authors as a submission test. No overlap risk.
- ReFuzzer, FunFuzz, CKGFuzzer, PromptFuzz, LibLMFuzz: driver or program
  generation with coverage or compile feedback; related-work only.

## Changes to paper/outline.md and experiment-matrix.md (to apply)

- Title/contribution: foreground the blackbox, cheap-author regime and the
  signal ablation as a test of the "generators are all you need" thesis.
- Related work section: rewrite around Gentoo, ELFuzz, G2Fuzz; drop the
  "verify from memory" placeholders.
- Conditions: add C0b Grammarinator (same grammar, no LLM).
- Loop replicates: 5 per target, not 3; keep paired sign-flip tests within
  target, add Mann-Whitney across replicates to match the anchor's protocol.
- Cost table: report our per-run cost next to Gentoo's ($7.5 to $12.8) and
  ELFuzz's GPU hours; it is a selling point.
- Threats: one model (same as Gentoo); mitigate with M2 as planned.

Sources: arXiv 2604.01442 (html full text), arXiv 2506.10323 (html full
text), arXiv 2501.19282 (abstract), arXiv 2308.04748, ACM 10.1145/3605157.3605173,
arXiv 2605.10074, arXiv 2410.21806 (withdrawal notice).
