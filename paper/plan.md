# Master plan (v5): the whole picture

Date: 2026-09-12. Status: PLAN ONLY, no code changed, no runs launched.
Companion docs: paper/base-paper.md (anchor papers), paper/outline.md and
paper/experiment-matrix.md (to be rewritten from this plan once approved),
DECISIONS.md D1-D14 (history). This file replaces plan v2 and v4.

How this plan was built: base-paper search, an empirical-methods review, a
fuzzing-community review, and a web-verified survey of ground-truth bugs.
Facts marked "verified" were read from a primary page or checked by running
code, not recalled.

---------------------------------------------------------------------------
## 1. The paper in one paragraph

An LLM is handed a formal grammar and asked to write a Hypothesis generator
for a C parser, then to refine it over a few iterations. It never sees the
parser's source or its coverage. What feedback should drive that refinement?
We compare three loops that differ only in the signal: no steering, a cheap
structural proxy computed from the generator's own outputs, and a coverage
oracle. We measure, on held-out C parsers of three text formats, how much of
the coverage-oracle's benefit the blind proxy recovers, whether the proxy
ranks generators the way coverage does, how often each loop triggers known
sanitizer-detectable bugs at pinned pre-fix commits, and how the LLM fails
as a generator author across two model families. Every loop-level claim is
made over ten independent loop replicates and pre-registered.

Anchor: Vikram and Padhye 2026 (Gentoo) showed a strong white-box agent's
generators do not need coverage guidance at fuzz time. We study the other
corner: a cheap blind author at synthesis time. Their question is fuzz-time
guidance; ours is synthesis-time feedback. State that precisely.

Do NOT motivate the work with "coverage is unavailable". For self-compiled C
libraries it is not credible. Blackboxness is a property of the proxy (no
instrumentation, no source, portable); the coverage oracle is the reference.

---------------------------------------------------------------------------
## 2. Hypotheses and outcome measures (fixed at pre-registration)

H1  Proxy-steered loop (C2) beats the no-steering loop (A5).
H2  Coverage-steered loop (C3) beats the proxy loop (C2); the gap is the
    price of blindness.

Primary outcome (one, so there is no metric shopping):
  AUC of branch coverage of the parse-reachable region versus number of
  inputs, up to 10^4 inputs, for the loop's FINAL generator, drawn on fresh
  seeds never used inside the loop.

Secondary outcomes (labelled exploratory):
  branch coverage at fixed n (150, 1000); coverage at equal wall-clock
  (5 min, 30 min, generation time included); time-to-trigger of known bugs;
  accepted-structure novelty; acceptance rate; inputs per second; distinct
  inputs per cell; skips per cell.

Unit of analysis for any claim about the loop: the loop replicate. Draw
seeds average input noise for one fixed generator and are never counted as
replicates.

---------------------------------------------------------------------------
## 3. Research questions and what answers each

| RQ | Question | Answered by |
|---|---|---|
| RQ1 Seeding | Does an LLM-authored grammar-seeded generator reach more parser code than random text and than Grammarinator on the identical grammar? | C1 vs C0a, C1 vs C0b (defaults and depth-matched), per target, paired by draw seed, equal n and equal time both reported |
| RQ2 Signal (core) | Which synthesis-time signal makes refinement work: none, proxy, or coverage? | A5 vs C2 vs C3s vs C3n, 10 replicates each, per target; per-replicate final-minus-seed delta; A12 effect sizes with CIs; histogram of which refinement branch fired per iteration |
| RQ3 Validity | Does the proxy score rank generators the way coverage does? | Spearman between proxy score and primary outcome over all (replicate x iteration) strategies per target, n about 50; within-condition and pooled reported separately |
| RQ4 Bugs | Do the loops trigger known bugs, and does the signal matter for that? | Time/inputs-to-trigger per pinned bug build per final generator in a 30-min campaign; per-bug PoC positive control; new findings triaged and reported |
| RQ5 Author | How does the LLM fail as an author, and does model family change the RQ2 sign? | Failure taxonomy with frequencies over all runs; guard/repair/rollback event rates per replicate; the RQ2 three-way repeated under M2 on one held-out target |

Descriptive appendices, not RQs: cost (dollars, CPU-seconds, wall-clock per
run); the seeded-Hypothesis process-history reproducibility finding (D13).

---------------------------------------------------------------------------
## 4. Targets

Development target (in-sample; the proxy was designed on it; reported
separately): json-parser. Held-out targets carry every headline claim.

| Target | Format | Grammar | Ground-truth bug builds (verified) | Stage |
|---|---|---|---|---|
| json-parser | JSON | json/JSON.g4 | #68 heap OOB read: pre-fix b1b09b5, fix b42439a, input `{"[unull\uDC`; #78 heap OOB read: pre-fix 08f9746, fix cddc633, truncated literal at buffer end | 1 |
| parson 1.5.3 | JSON | json/JSON.g4 | none parse-reachable; coverage-only target | 1 |
| tomlc99 | TOML | toml/TomlLexer.g4 + TomlParser.g4 | #50 NULL deref: pre-fix c5d2e37, fix fd82018; #94/#95/#97 recursion stack overflow, unfixed at HEAD (CVE-2026-16634) | 1 |
| cJSON v1.7.17 | JSON | json/JSON.g4 | CVE-2023-53154 heap OOB read in parse_string, fix 3ef4e4e; needs cJSON_ParseWithLength on a non-NUL-terminated buffer | 2 |
| libexpat R_2_6_4 | XML | xml/XMLLexer.g4 + XMLParser.g4 | CVE-2024-8176 stack overflow via recursive entity expansion, fix 6d4ffe8 | 2 |

Six ground-truth bugs, four targets, three formats. Open UBSan items on
json-parser (#186 = our finding #1, #185) are reported as standards
violations and never counted as bugs.

Dropped with reasons: inih and libcsv (no sanitizer-detectable bug history,
flat formats where the depth components are inert by construction); jansson
(recursion-only bug, would be a third extra JSON target); libyaml (good bugs,
no grammars-v4 grammar); mxml (no fix commit).

Per target we build: default sanitizer binary (ASan+UBSan, -O0,
-fno-sanitize-recover), coverage binary (clang -fprofile-instr-generate),
uninstrumented -O2 binary (timeout re-verification), and one sanitizer
binary per ground-truth bug commit. The parse-reachable region is defined
per target as the set of functions reachable from the harness entry point in
the static call graph, cross-checked against the union of everything any
condition ever covered.

---------------------------------------------------------------------------
## 5. Conditions

| Cond | Definition | Status |
|---|---|---|
| C0a | random st.text() | exists |
| C0b | Grammarinator on the same .g4, unicode charset, drawn via the generator class with seeded random; two settings: defaults, and depth matched to C1's empirical depth distribution | to build |
| C1 | LLM seed: iteration-1 generator from grammar + adaptation notes + requirements, before any refinement | exists |
| C2 | proxy-steered loop (production gap, depth mass, novelty guardrail, probe repair) | exists |
| A5 | no-steering control: no run summary, generic "improve" prompt, rollback to the last WORKING generator (never score-best); validity machinery (build screen, acceptance gate, repair) kept | fix needed: today gated iterations still select by proxy score |
| C3s | coverage-scalar oracle: the proxy score is replaced by parse-reachable branch coverage in gate, rollback and best-selection; the prompt sees only the number | to build |
| C3n | coverage-named oracle: C3s plus the list of least-covered reachable functions in the prompt (Gentoo-S analogue); white-box lite | to build |
| M2 | C2, A5, C3s under an OpenAI model on tomlc99 | to run |
| REF | AFL++ on the same coverage build, 1 h x 5 runs, as the community reference row (not a condition of the loop) | to build |

Cut (binding): human-written Hypothesis strategy (docs example is a straw
man; revive only if a Hypothesis-experienced person writes one from the same
brief under a 60-min time box); notes-free seed C1'; component ablations
A1-A4 (exploratory on json-parser only, after the branch-fired histogram
shows the components fire at all); no-guards A6 (Stage 2, one target, only if
we want the sentence "guards matter"); budget-sensitivity; prompt paraphrase.

---------------------------------------------------------------------------
## 6. Run protocol (what one loop replicate is)

- Budget: 5 iterations x 500 examples; per-iteration 10-min backstop; 40-min
  run safety stop. Budgets are by examples and iterations; wall-clock is an
  outcome, and every backstop event is logged and reported.
- Temperature 0.7, no request seed (stated). Prompts anonymized: no library
  name, no target identifier. The model observes: exit-code class per input,
  its own generated inputs, the gate/repair feedback, and under C2 the proxy
  summary, under C3 the coverage number (and names under C3n). Parser error
  messages are stripped in every condition (parson has none; json-parser's
  would be a per-target confound).
- Provenance per run: served model id and system fingerprint per call,
  timestamps, wall and CPU seconds per iteration, tokens and cost, config
  (target, condition, model, ablations), git commit, binary hashes.
- Output per run: final_strategy.py, final.json (source iteration, revert
  events), every iteration's strategy and stats, evolution.md.
- Order: interleaved across targets and conditions (json C2 rep1, toml C2
  rep1, parson C2 rep1, json A5 rep1, ...) so provider drift is orthogonal to
  treatment. Iteration-1 seeds across batches are the drift check.
- No concurrent CPU-heavy work while live runs execute (load-induced
  timeouts would become false crashes and change the loop's decisions).
- A run directory without final.json is a failed run: discarded and rerun by
  the driver; never reconstructed.

Run counts: 10 replicates x {C2, A5, C3s, C3n} x 3 targets = 120 (Stage 1);
+ 80 for cJSON and libexpat (Stage 2); + 30 for M2.

---------------------------------------------------------------------------
## 7. Evaluation pipeline (from raw runs to the paper)

Step E1  Generators. For each (target, condition, replicate) resolve the
  FINAL generator and also the LAST-iteration generator (reported side by
  side, so C3 cannot win by selecting the max of its own noisy metric). For
  C0a/C0b/C1 the generator is fixed.

Step E2  Input sets. For each generator and each of 20 fresh draw seeds
  (disjoint from the seeds the loop used internally), draw 10^4 inputs in a
  history-fixed subprocess; cache under build/_inputs keyed by
  hash(generator source, n, seed, runtime versions); record the id. Record
  generation wall time so equal-time views can be computed.

Step E3  Coverage curves. Feed each input set, in draw order, to the
  in-process coverage harness; record cumulative branch coverage of the
  parse-reachable region at n = 10, 30, 100, 150, 300, 1000, 3000, 10000.
  Compute AUC (primary), fixed-n points, and equal-time points (5 and
  30 min including generation). Also record region and line coverage,
  distinct inputs, skips, acceptance, novelty, inputs/sec.

Step E4  Bug campaigns. For each final generator and each ground-truth bug
  build, run a 30-min campaign (in-process harness, fresh seed per
  replicate); record first-trigger time and input index, or censoring at
  30 min. Before any campaign, the per-bug hand-written PoC must trigger
  through the same harness (positive control) or the bug is dropped from
  RQ4 and listed.

Step E5  Crash triage for new findings. Crash = sanitizer report or fatal
  signal. Bare nonzero exit = "unknown", hand-triaged. Timeouts are a separate
  bucket, counted only if reproduced on the -O2 uninstrumented build within
  a stated budget. UBSan findings split by check class; pointer-overflow and
  null-offset reported as standards violations. Dedup by normalized
  signature, shrink, verify, report to maintainers before publication.

Step E6  Loop-internal data. From each run: per-iteration proxy score,
  in-loop coverage (C3), which refinement branch fired, guard events
  (build-reject, gate, repair, rollback), tokens, time. From all runs: the
  failure taxonomy coding (two coders where feasible; report agreement).

Step E7  Statistics (eval/report.py, dry-run on synthetic data before
  pre-registration):
  - RQ1: per target, paired sign-flip permutation test and 95% CI over the
    20 draw seeds for C1 vs C0a and C1 vs C0b; equal-n and equal-time.
  - RQ2: per target, per replicate: delta_r = mean over seeds of
    (final - seed). One-sample sign-flip test + CI over the 10 delta_r
    (min two-sided p = 2/1024). Between conditions: two-sample permutation
    test on replicate means and Vargha-Delaney A12 with bootstrap CI for
    C2 vs A5 (H1) and C3s vs C2, C3n vs C2 (H2). Cross-target: per-target
    results plus the mean of per-target effects; seeds never pooled.
  - RQ3: Spearman rho with CI per target over (replicate x iteration)
    strategies; within-condition and pooled.
  - RQ4: survival curves per bug per condition; log-rank where n allows,
    otherwise descriptive; reached-vs-triggered with both denominators
    (all sanitizer-detectable bugs in the version window; harness-reachable
    subset).
  - RQ5: taxonomy frequency table per model; guard-event rates per
    replicate; the RQ2 tests repeated under M2.
  - Multiplicity: one primary metric; targets are replication, not extra
    tests; Holm only inside any exploratory ablation family.

Step E8  Tables and figures (generated, never hand-edited):
  T1 targets (LoC, reachable region size, bugs, grammar);
  T2 per-target RQ1 table; F1 coverage-vs-inputs curves by condition per
  target with replicate bands; F2 RQ2 forest plot of A12 per target
  (C2 vs A5, C3s vs C2, C3n vs C2); F3 per-replicate delta distributions;
  F4 branch-fired histogram; F5 RQ3 scatter proxy vs coverage per target;
  F6 RQ4 survival curves; T3 findings table; T4 taxonomy by model; T5 guard
  events; T6 cost; T7 Grammarinator and AFL++ reference rows at equal time.

Step E9  Sanity checks that must pass before writing results:
  identical inputs measured twice give identical coverage; input-set ids
  reproduce across two processes; C0a's input-set id is identical across
  targets; every run has final.json and a served-model fingerprint; the
  batch-drift check (iteration-1 seeds across batches) shows no shift;
  positive controls pass for every bug kept in RQ4.

---------------------------------------------------------------------------
## 8. Reading the results: what the paper says under each outcome

The design is pre-registered so every outcome is reportable:

- C3 > C2 > A5: the proxy recovers X% of the oracle's gain (X reported with
  CI); the remainder is the price of blindness. Main story.
- C2 ~ A5 < C3: steering needs coverage; the structural proxy does not earn
  its place. Report it, keep the validity/guard analysis and the taxonomy as
  the contribution; the title stays neutral.
- C2 ~ A5 ~ C3: Gentoo's finding extends downward to cheap blind authors:
  the generator's quality is set at seeding, and refinement of any kind adds
  little at this budget. RQ1 and RQ5 become the paper.
- Mixed across targets: report per target; the cross-target summary is the
  mean of per-target effects, and heterogeneity is a finding, not noise.
Any claim about "guards" requires the A6 condition; without it, the paper
does not make that claim.

---------------------------------------------------------------------------
## 9. Pre-registration

Register on OSF (with embargo) before the first replicate run: the
hypotheses, primary outcome, target set, conditions, replicate count, seed
policy, exclusion rules (failed runs, dropped bugs), the analysis code, and
a neutral title. Disclose that the json-parser and parson pilots informed
the design. Fixed n = 10 replicates, no optional stopping; the design is
framed as estimation with CIs, p-values secondary.

---------------------------------------------------------------------------
## 10. Infrastructure work, in order (no live runs before step 8)

1. Provenance: served model id, fingerprint, timestamps, wall/CPU per
   iteration into stats.json/final.json; config.json gains provider and
   git commit. Generic LLM_API_KEY fallback for OpenAI.
2. A5 fix: rollback to last working generator; refine prompt without the
   empty summary block; tests.
3. Prompt anonymization and error-message stripping; verify by diffing the
   rendered prompts for both targets.
4. In-process harness: LLVMFuzzerTestOneInput per target, batch runner (one
   process, directory of inputs, per-input result line), crash classification
   from sanitizer reports, timeout re-verification path, -O2 build target,
   Docker Linux x86-64 as the primary environment. The stdin exit-code
   wrapper stays for the loop.
5. Format-generic proxy: production set and recursive rules read from the
   .g4; per-format probes declared as human-authored; oracle optional.
6. C3s and C3n: score substitution and the named-function variant; in-loop
   coverage measured on the fixed gate draw.
7. Parse-reachable region: static call graph from the entry point,
   cross-checked against observed coverage; per-target function list
   committed.
8. Replicate driver: manifest, resumable, interleaved, discards partial runs,
   never overlaps with evaluation jobs. Runs detached (nohup, survives the
   session), logs to a file, and maintains a one-line status file
   (runs/<batch>/STATUS: "done 37/120, running toml A5 rep4, failed 0").
   Session rule: progress is checked by reading that one line only; raw logs
   and per-input files are never read into the assistant session. The same
   applies to matrix and report jobs: run in the background, read only the
   generated summary tables.
9. eval/report.py: replicate-level tests, A12 with bootstrap, AUC, survival,
   tables/figures; dry-run on synthetic data. Then OSF registration.
10. Grammarinator condition (generator-class draw, hashed generator file,
    depth matching).
11. tomlc99 harness + adaptation notes + ground-truth builds + PoC controls
    (Stage 1); cJSON and libexpat likewise (Stage 2). Needs the vendoring go.
12. Campaign runner (30 min per final generator per bug build) and the AFL++
    reference row.

---------------------------------------------------------------------------
## 11. Stages, schedule, definition of done

Stage 1 (preprint-ready): json-parser, parson, tomlc99; C0a, C0b, C1, C2,
A5, C3s, C3n; 10 replicates; campaigns on 4 bugs; M2 three-way on tomlc99;
AFL++ reference on all three.
Done when: F1-F6 and T1-T7 render from report.py for the three targets, the
sanity checks in E9 pass, and methods/results/threats are drafted.

Stage 2 (journal-ready): add cJSON and libexpat (6 bugs, XML); exploratory
A1-A4 on json-parser; optional A6 on one target; related work and
discussion finished; artifact packaged in a clean repository (this repo's
take-home wording stays out of the artifact).

Rough schedule at the current pace (sessions, not calendar days):
  weeks 1-3  steps 1-10 (infrastructure), OSF registration
  week 4     Stage 1 runs in the background (about 150 runs; up to 40 min
             each worst case; realistically several days of wall-clock),
             Grammarinator and AFL++ rows, campaigns
  week 5     evaluation pass, sanity checks, first results draft
  weeks 6-7  Stage 2 targets, runs, campaigns
  week 8     full draft, internal review, submission of the preprint

---------------------------------------------------------------------------
## 12. Budget (hard cap $10 on DeepSeek; OpenAI from the user's balance)

Per run about 17k input + 17k output tokens.
  DeepSeek Stage 1: 120 runs x $0.025 = $3.00
  DeepSeek Stage 2:  80 runs x $0.025 = $2.00
  M2 OpenAI:         30 runs on tomlc99, model TBD by the user from the
                     published price page and their balance
  Margin for reruns: $5.00 of the DeepSeek cap
Compute: local machine for development; Docker for the official runs;
AFL++ reference 3 targets x 5 runs x 1 h = 15 CPU-hours.

---------------------------------------------------------------------------
## 13. Risks of getting stuck, and the pre-decided mitigation

| Risk | Mitigation |
|---|---|
| Scope creep | The cut list in section 5 is binding; anything added must displace something |
| Format-generic proxy becomes a rewrite | Only productions and depth are read from the .g4; probes stay hand-written per format and are declared as such |
| A ground-truth bug is not triggerable through the harness | PoC positive control is built first; a bug without a passing control is dropped from RQ4 and listed |
| Coverage saturates at iteration 1 | Primary outcome is AUC on the parse-reachable region; headroom is checked per target before runs |
| Provider model drift mid-batch | Interleaving plus logged fingerprints; if the served model changes, the batch is split and reported as two |
| Runs too slow | Budgets are by examples; the in-process harness removes per-input process spawn; the driver runs unattended in the background |
| libexpat harness complexity | Stage 2 only; the entity-expansion bug needs no handlers, so the harness is XML_Parse on the buffer |
| Reviewer says "toy" | AFL++ reference row, libexpat as a real-world target, time-based curves, ground-truth bugs, 10 replicates, pre-registration |
| Take-home wording in the artifact | The paper artifact is a fresh clean repository; this repo remains the working history |

---------------------------------------------------------------------------
## 14. Decisions still open (answer with a numbered yes/no)

1. Reframing: coverage oracle as reference, drop "coverage unavailable".
2. Target set and vendoring go: json-parser, parson, tomlc99 (Stage 1);
   cJSON, libexpat (Stage 2).
3. OSF pre-registration with embargo before the first run.
4. In-process harness rewrite (about a week; unlocks the metric and AFL++).
5. Commit paper/base-paper.md and this plan now, or hold.
6. OpenAI model name for M2 (or the balance, and I compute the run count).
