# Paper outline

Working title options (pick one, refine later):

1. *Steering Without a Compass: Making LLM-Authored Grammar Fuzzers Self-Improve Under a Blackbox Constraint*
2. *A Proxy Signal for Coverage-Free Refinement of LLM-Generated Test Generators*
3. *Grammar In, Crashes Out: Empirically Validating Feedback Signals for Agentic Blackbox Fuzzing*

**Venue target:** an empirical software-engineering journal under Springer Nature
(Empirical Software Engineering, Automated Software Engineering, or Software
Quality Journal). Fallback / stepping stone: a fuzzing or testing workshop, or an
arXiv preprint after Tier A.

**The one-sentence contribution.** When an LLM turns a formal grammar into a
property-based test generator and refines it from feedback, the coverage signal
real fuzzers steer by is unavailable in a blackbox setting; we design a
coverage-free proxy signal, show causally (multi-seed, ablated) which of its
components make the generator measurably improve, validate post hoc that the
blind signal tracks real coverage, and characterize how LLMs fail as strategy
authors and how to contain it.

**What the paper is NOT about.** It is not "we found a bug." The finding is a
supporting artifact. Reviewers will judge the methodology and the evidence.

---

## Research questions

| RQ | Question | Status | Evidence source |
|---|---|---|---|
| RQ1 Seeding | Does grammar-seeding reach more parser code than random input, across targets? | one target done | `eval/experiment.py` (B vs A) |
| RQ2 Refinement | Does the feedback loop improve the generator *beyond* seeding? By how much? | one target done | `eval/experiment.py` (C vs B, paired) |
| RQ3 Ablation | Which proxy-signal components cause the improvement? | **new** | ablation cells (see matrix) |
| RQ4 Validity | Does the blind proxy correlate with the coverage it cannot observe? | one target done | `eval/proxy_validation.py` |
| RQ5 LLM-as-author | How do LLMs fail at authoring strategies, and how robust is guard/repair across models? | taxonomy done, 1 model | report Appendix C; multi-model cells |
| RQ6 Bugs | What does it find across real targets, versus baselines? | 1 finding, 1 target | `crashes/`, per-target triage |

RQ3 is the scientific core. RQ1/RQ2 without RQ3 is "it works"; with RQ3 it is
"we know *why* it works". Plan the writing so RQ3 gets the most space.

---

## Section-by-section plan

### 1. Introduction
- Motivation: grammar-aware inputs reach code random bytes never do; LLMs can
  author grammar-driven generators cheaply; but refinement needs a signal, and
  the standard signal (coverage) is often unavailable (blackbox targets, binary-
  only, cost, or deliberately excluded).
- The problem statement: *what do you optimize toward when you cannot see
  coverage, and how do you know the loop is improving rather than just changing?*
- Contributions (numbered, map 1:1 to RQs). State them as claims the results
  section will discharge.
- Explicitly frame the honesty stance: single runs are max-of-noise; we report
  distributions and paired tests. (This is a differentiator; say it up front.)

### 2. Background
- Fuzzing: mutation vs generation; coverage-guided (AFL/libFuzzer) vs blackbox.
- Grammar-based generation (Grammarinator, Nautilus-style).
- Property-based testing and Hypothesis: strategies, `st.recursive`, shrinking.
- LLMs as test/strategy authors; the "two-level semantics" pitfall (strategy vs
  drawn value) that recurs in our failure taxonomy.
- Sanitizers as the crash oracle (ASan/UBSan; why `-fno-sanitize-recover`).
*(Available now: report §1 + Appendix A.)*

### 3. Approach
- 3.1 Pipeline: grammar (ANTLR grammars-v4) -> LLM -> Hypothesis strategy ->
  harness -> summarize -> refine -> repeat, within an iteration/cost budget.
- 3.2 Grammar-to-reality adaptation: documenting where a library's accepted
  language deviates from the formal grammar, and feeding that to the model.
- 3.3 **The proxy signal** (the heart): roles = primary steer (production
  coverage, nesting-depth mass), objective (crash signature), repair (single-
  feature probes = a controlled experiment replacing missing parser feedback),
  guardrail (accepted-structure novelty). Exactly one nameable edit per
  iteration so the next measurement is interpretable. Include the confounded
  first design and why it was abandoned.
- 3.4 Guard/repair machinery: AST screen, acceptance gate, multi-seed gate,
  in-iteration repair, rollback with noise tolerance. Frame as: the model is
  high-variance; the machinery is what is dependable.
- 3.5 Triage: signature normalization (report-based, not signal-based, because
  ASan collapses to SIGABRT), Hypothesis shrinking + ddmin, verification.
*(Available now: report §1, Appendix B, DECISIONS.md D5–D8. This section is
mostly written; it needs tightening and figures.)*

### 4. Experimental design
- Targets (multi-format), conditions, seeds, models, metrics: **see
  `experiment-matrix.md`**.
- Statistical method: randomized block design (same seeds under every
  condition) -> paired sign-flip permutation tests; mean +/- 95% CI; effect
  sizes; correction for the ablation family.
- Budgets held constant across conditions (examples/iteration, iterations,
  wall-clock) so comparisons are fair.
- Reproducibility: seeds, committed artifacts, Docker; target an artifact badge.

### 5. Results (one subsection per RQ)
- RQ1/RQ2: per-target table + aggregate; the headline figure is coverage by
  condition with CIs across targets.
- RQ3: ablation deltas per component, per target (the key figure).
- RQ4: proxy-component vs coverage correlations across targets.
- RQ5: failure-mode taxonomy with frequencies across models; guard hit rates;
  iterations-that-produced-a-working-strategy distribution.
- RQ6: findings per target (deduped, minimized, verified), with severity
  honestly classed (e.g., UBSan-only idiom vs memory corruption).

### 6. Discussion
- What the signal design teaches (which components earned their place; the
  self-defeating-signal traps: RecursionError penalizing deep inputs, novelty
  fighting the depth steer, max-of-noise).
- Cost: dollars and tokens per unit of coverage gained.
- When to prefer this over coverage-guided fuzzing (blackbox, no
  instrumentation, cheap targets) and when not.

### 7. Threats to validity
- Internal: seed noise (mitigated by design), measurement-only coverage build
  differing from the sanitizer build, patch-artifact risk of the `unmask` build.
- External: target set and formats, grammar source (one repo), model set.
- Construct: coverage as a proxy for bug-finding power; "crash" including
  benign UB by policy.
*(Available now: scattered across DECISIONS.md; consolidate.)*

### 8. Related work
Areas to position against (verify every citation with a real literature
search; do not cite from memory):
- LLM-driven fuzzing / generation (e.g., Fuzz4All, TitanFuzz and successors).
- Grammar-based fuzzers (Grammarinator, Nautilus, Superion-style).
- Coverage-guided and feedback-directed generation, incl. property-based +
  feedback (Zest / FuzzChick-style).
- Property-based testing foundations (QuickCheck, Hypothesis).
- LLM test generation and its reliability/hallucination studies.
State the gap: prior LLM fuzzing largely assumes coverage or reports single
runs; we study the coverage-free signal itself and isolate its effect causally.

### 9. Conclusion + artifact availability
- Repository, Docker, seeds, committed runs, `./run.sh eval`.
- AI-assistance disclosure line (required by the venue; state tools used and for
  what).

---

## Figures and tables to produce

1. Pipeline diagram (approach).
2. Coverage by condition, per target, with 95% CIs (RQ1/RQ2 headline).
3. Ablation deltas per signal component, per target (RQ3 key figure).
4. Proxy-component vs coverage correlation heatmap across targets (RQ4).
5. Failure-mode taxonomy table with per-model frequencies (RQ5).
6. Findings table: target, signature, minimized size, class, verified (RQ6).
7. Cost table: tokens/$ per condition.

---

## What already exists vs what must be built

| Exists (reuse) | Must build |
|---|---|
| grammar->LLM->Hypothesis loop (`fuzz/loop/agent.py`) | per-target harness + build + grammar for 4 more targets |
| proxy signal + `decide_refinement` | ablation flags in `decide_refinement` / `summarize` |
| triage pipeline | matrix runner over targets x conditions x seeds x models |
| `eval/experiment.py` (multi-seed paired test) | generalize to all targets/conditions + aggregate |
| `eval/proxy_validation.py` | generalize across targets |
| failure taxonomy (Appendix C) | run 1–2 more models, tabulate frequencies |
| DECISIONS.md (threats, design rationale) | consolidated related-work + threats sections |
| Docker reproducibility | figures/tables generator |
