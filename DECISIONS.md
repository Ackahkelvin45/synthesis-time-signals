# Design decisions & critique log

Every major setup decision was proposed with reasoning, then challenged by an
independent critic before being accepted. This log records each decision, the
strongest challenge, and how it was resolved — so the *why* behind the project
is auditable.

## D1 — Target library & pinned version

- **Proposed:** parson `1.5.3 @ ba29f4e` (latest release) as the target.
- **Critique:** the latest release is the most *hardened* commit; a "0 crashes"
  result there is uninterpretable — it can't distinguish a working pipeline from
  a broken one. Need a **positive control**: a target known to crash.
- **Resolved:** keep 1.5.3 as the honest exploratory target, **and** add a
  positive control. Investigation showed parson's historical overflow bugs
  (#133, #204) are in the *serialization* path and need multi-GB inputs — not
  reachable by a small-input parse-only harness — so instead of pinning an old
  commit (which also risks overfitting the fuzzer to one known bug), the
  positive control is a **synthetic macro-guarded injected bug**
  (`-DPOSITIVE_CONTROL`). Email Prof. D'Amorim for the real assigned commit.

## D2 — Harness design

- **Proposed:** read stdin → NUL-terminate → `json_parse_string` → free;
  exit 0 = valid, 2 = reject; sanitizer aborts = crash; parse-only.
- **Critique:** (a) `json_parse_file` does NOT dodge embedded-NUL truncation —
  both entry points walk a NUL-terminated `char*`, so reject NUL inputs
  explicitly. (b) UBSan does not abort by default — MUST build with
  `-fno-sanitize-recover=all` or a UB input exits 0 and is misread as valid.
  (c) Skipping serialization is an acceptable scope cut but is real lost surface.
- **Resolved:** adopted all three. Harness rejects embedded-NUL (exit 2) and
  caps input size; `-fno-sanitize-recover=all` is in the build; added an
  optional `-DROUNDTRIP` mode (parse→serialize→free) to reach serializer surface.

## D3 — Build & sanitizer configuration

- **Proposed:** clang `-fsanitize=address,undefined -fno-sanitize-recover=all
  -O1`; vendor parson by copying source + PROVENANCE.
- **Critique:** prefer **`-O0`** so the optimizer can't fold away the UB we want
  to observe; add `UBSAN_OPTIONS=print_stacktrace=1` (UBSan gives no trace
  otherwise) and `ASAN_OPTIONS` extras; **LSan is unsupported on macOS/arm64**
  (leaks won't be caught) — document it; parson is MIT so copy `LICENSE`
  verbatim. Vendoring-by-copy endorsed over submodule.
- **Resolved:** adopted `-O0`, the richer sanitizer options (in `runner.py`),
  LICENSE copy, and the documented LSan limitation. A Linux repro path is noted
  as a grader-parity follow-up.

## D4 — Project layout & tooling

- **Proposed:** `vendor/ harness/ grammar/ fuzz/ crashes/ docs/`, Python +
  Hypothesis via `requirements.txt`.
- **Critique:** missing a home for the committed **per-iteration LLM
  artifacts** (prompts/responses/evolved strategies/stats) and the token/$
  accounting; no top-level README or single entrypoint; unpinned Hypothesis is a
  reproducibility liability; the loop must support an **offline `--replay`** so a
  grader reproduces findings without spending API money.
- **Resolved:** added `runs/` (committed iteration evidence + `evolution.md` +
  `cost.md`), `README.md`, one `run.sh` entrypoint, **pinned** `hypothesis`,
  `.gitignore` for secrets, and a `--replay` mode + env-only API key in
  `fuzz/loop/agent.py`. `crashes/<sig>/` holds input, minimized input,
  sanitizer report, exit code, and `repro.sh` per unique signature.

## D5 — Proxy signal for the agentic loop (no coverage instrumentation)

- **Proposed:** three co-equal steering signals — acceptance rate bucketed by
  generated structure, structural coverage + depth, crash signatures — with the
  differential oracle as a findings channel. Carried the hard constraint that
  parson returns NULL with no error message, so "why was it rejected" has no
  parser-side source.
- **Critique:** (a) **acceptance-bucketed-by-structure is statistically
  confounded** — multi-feature inputs can't attribute a rejection to one feature
  without parser feedback, so one broken feature poisons several buckets;
  (b) that signal churns against structural-coverage (both say "fix a feature");
  (c) **5 iterations can't act on three signals in parallel** — sequence and
  optimize one first (coverage/depth); (d) the loop "fails quietly" (acceptance
  rises while diversity narrows) with no guardrail; (e) add cap-distance to 2048.
- **Resolved (with one nuance).** Replaced confounded bucketing with
  **single-feature probes** (`fuzz/probes.py`) for unambiguous attribution;
  made coverage/depth/cap-distance the **primary** steer and probes a **repair**
  signal; added a **novelty guardrail** (acceptance↑ + distinct-accepted↓ →
  revert). `decide_refinement()` emits exactly ONE nameable edit per iteration
  with a fixed priority, proven actionable offline in `fuzz/test_signal.py`
  (each signal → a distinct action; guardrail reverts only on quiet failure).
  Nuance kept over the critic: probes stay for repair, not cut entirely.
- **Bonus finding:** the probe design surfaced a THIRD parson deviation
  (duplicate keys rejected); the **oracle disambiguation** in `classify_probes`
  correctly labels it a *finding*, not a generator bug — vindicating keeping the
  oracle wired in.

## D6 — Live loop + LLM provider (DeepSeek)

- **Proposed:** provider-agnostic `call_llm` (DeepSeek default via an
  OpenAI-compatible endpoint, stdlib-only, MOCK mode for offline runs),
  `seed_prompt`/`refine_prompt` from the grammar + adaptation notes, safe
  extraction of model code, and a real `run_live` committing per-iteration
  artifacts. DeepSeek chosen because the assignment is provider-agnostic and it
  fits the small/mid-tier ~$5 budget.
- **Critique (live-loop critic):** (F1) `run_strategy` caught only
  `AssertionError`, so any draw-time error killed the whole loop; (F2) a
  type-checking-but-garbage strategy burned a full 500-example iteration —
  the n=40 acceptance check only *warned*; (F3) `revert_last_edit` was a label
  with **no rollback**, and a 'both-down' regression wasn't caught at all;
  (F4) the $5 cap can't bind (runs cost cents) and there was **no wall-clock
  guard**, so one deep-nesting iteration could blow the 10-min cap; (F5) the
  `screen_code` denylist was trivially bypassable and `_productions_in` used
  substring matching, so `null`/`true` inside any text emptied `productions_gap`
  and silently defeated the primary steering signal.
- **Resolved (all must-fixes adopted):** broad exception handling ->
  `GeneratorError` so a bad generator fails one iteration, not the loop (F1);
  acceptance is now a **gate** with one in-iteration repair re-prompt before
  spending the full run (F2); **real rollback** to the best-scoring strategy via
  a `_score`, with a tolerance band against jitter (F3); **per-run (10-min) and
  overall (40-min) wall-clock caps** added to the run and `StopController` (F4);
  `screen_code` is now an **AST import-allowlist** (blocks `from os import
  system`, `getattr`, dunder access) and productions are detected
  **structurally via `json.loads`** (added the missing `number` production) (F5).
  Nice-to-have (full process isolation of model code) deferred but documented:
  the AST screen is a footgun-guard, not a sandbox — run the loop in a throwaway
  environment.

## D7 — Crash triage & dedup normalization (Step 5)

- **Proposed:** signature = `bug_class | top-3 function-name frames` from the
  sanitizer report (not the signal, since ASan collapses all faults to SIGABRT);
  signature-preserving delta-debug (ddmin) minimizer complementing Hypothesis's
  shrinker; verify by standalone re-run; save one folder per signature. Proven
  on a synthetic multi-bug harness (dedup groups variants, splits distinct bugs,
  minimizes to the marker, verifies).
- **Critique (triage-design critic):** architecture sound, but (1) **UBSan
  over-splits** — `split(":")[0]` leaves operand data (`index 5…` vs `index 7…`)
  in the signature, splitting one bug into many (verified live); (2)
  **under-splitting** — bare libc interceptor frames (`memcpy`) weren't filtered
  so the site could be an interceptor, and a `?`-frame fallback merged all bugs
  of a class; (3) **no flakiness guard** — the representative was the shortest
  raw input even if it reproduced flakily; (4) `repro.sh` set no sanitizer env,
  so a manual UBSan re-run wouldn't match the saved signature.
- **Resolved (all must/should-fixes adopted):** UBSan kind is **canonicalized**
  (strip digits/quoted types/`[...]`); interceptor frames filtered and a
  **SUMMARY-site fallback** replaces the `?` merge magnet; a **flakiness guard**
  picks the shortest input reproducing ≥2/3 (else `low_confidence`, unminimized);
  `repro.sh` exports the sanitizer env. Locked with 4 regression tests in
  `fuzz/test_triage.py` (now 14 assertions).

## D8 — Full adversarial audit (assignment · plan · code · tests · safety)

A five-critic review audited the whole project against the assignment, the
recorded decisions, the code, the tests, and a grader/security walkthrough.
It found real defects that all previous suites had passed over. Adopted:

**Assignment compliance**
- **Two-page report was missing entirely** — the largest graded artifact. Added
  `docs/report.md` (design / findings / challenges).
- **No crash deliverable** — the assignment requires findings *or* a documented
  "none found + why + what next". Added `crashes/FINDINGS.md`.
- **500-examples-per-iteration was exceeded** (~660–700: main run + gate +
  probes). The budget is now split across everything an iteration sends to the
  harness and measured at exactly 500.
- `runs/` held a MOCK run that read like a real one. Mock artifacts are now
  self-labelling in three places (`stats.json:mode`, a `MOCK_RUN.md` per
  iteration, a banner in `evolution.md`).

**Correctness (each verified by execution, each now regression-tested)**
- `decide_refinement` raised `KeyError` when a gated iteration passed `{}` as the
  previous summary — killing the run *before* `cost.md` was written.
- A failed first iteration left `current_code = None`, so the model was sent the
  literal text `None` as "the current strategy", silently burning every later
  iteration. The loop now re-seeds whenever it has no usable strategy.
- `revert_last_edit` was a **no-op**: `best_code` was overwritten one line before
  the revert used it. `best` also ratcheted *down* (57→54→51…) because every
  non-regressed iteration overwrote it. Now the edit is decided before `best` is
  mutated, and `best` only ever improves.
- A crash returned `_score = 1e6`, making the tolerance band ~1e5 so every later
  iteration counted as a regression — the loop froze on the first crash. Crash
  dominance is now a separate flag, not a term in the scalar.
- **The primary steering signal was self-defeating**: production detection used
  recursive `json.loads`, which raised `RecursionError` on inputs deeper than
  ~1000 — exactly what `cap_distance` steers toward. Those inputs contributed
  zero productions and collapsed into one novelty bucket, so the loop penalised
  the very edit it had just requested. Walk is now iterative with a raised parse
  limit; deep inputs score *higher*, as intended.
- `FlakyFailure` (a crash that doesn't reproduce identically during shrinking)
  was being converted into "broken generator" and discarded. Timeouts are the
  flakiest crash class and the assignment counts them as crashes — now kept.
- `extract_strategy` took the *last* fence, so a trailing ```bash block won over
  the real code. Now prefers the longest python-tagged block and strips the tag.
- `oracle_accepts` let `RecursionError` escape on deep input; the loop then
  blamed the model for the harness's own limitation.

**Safety**
- `screen_code`'s allowlist was **bypassed** by
  `hypothesis.internal.escalation.os.system(...)` (demonstrated executing during
  review). Blocked submodules and dangerous attribute names are now rejected too.
  It remains a footgun-guard, not a sandbox — the honest framing is kept.
- The API key (loaded from `.env` into the environment) was passed to every one
  of thousands of harness subprocesses. `run_once` now passes a minimal env
  allowlist.

**Portability / hygiene**
- `assert_real_target` was documented as "Enforced" but called only from a test —
  the live loop could have triaged the positive control's synthetic bug as a real
  parson finding. `run_live` now calls it.
- Tests hardcoded `clang`; they honor `CC` now (the grader is likely on Linux),
  and Linux runtime frame names were added to the triage frame filter.
- `run.sh` gained a venv guard, and stale assertion counts were removed from the
  docs rather than restated.

**Not adopted:** a package refactor to remove `sys.path` manipulation (invasive
for the benefit; the monotonic-growth bug was fixed instead), and splitting
`agent.py` (the one defensible seam, the signal block, already has its own test
file and clean boundary — revisit only if it grows).

Regression coverage for all of the above: `fuzz/test_loop.py` (36 assertions).

### D8 addendum — post-refinement audit (Phase 7)

An independent auditor re-checked the refined state against the assignment and
re-tested every D8 claim. It confirmed 10 of 11 fixes and found three things the
first pass missed, all now fixed:

- **A NEW `screen_code` bypass.** The `ImportFrom` handler validated only the
  *module*, not the imported *names*, so `from hypothesis import internal` and
  `from hypothesis.database import DirectoryBasedExampleDatabase` passed — the
  latter writes files at import time (demonstrated executing). Imported names are
  now screened, and `hypothesis.database` is a blocked submodule. Six regression
  tests were added, plus three asserting legitimate strategies (`st.composite`,
  `st.recursive`) still pass, so the guard cannot be tightened into uselessness.
- **A false claim in our own `crashes/FINDINGS.md`** — it said the mock loop ran
  "5 iterations × 500 examples" when the committed evidence showed far fewer
  (the README's example command uses a small `--max-examples`, and the budget
  split floors the main run). Rewritten to state exactly what was run, and to
  say plainly that a null result from a small non-adversarial sample is **not**
  evidence that parson is crash-free.
- **An internal contradiction in `docs/report.md`** — it credited the
  differential oracle with all three parson deviations, but the duplicate-key
  one (parson *stricter*) came from the probes; the oracle only disambiguated it.

Two assignment requirements the first pass had left partial were also completed:
**per-input logging** (Step 4.3 — `runs/iter-N/per_input_log.jsonl` records
outcome, exit code, signal, and sanitizer output per input) and **crash
signatures in the LLM summary** (Step 4.4 — accumulated across iterations so the
model can steer toward known crash regions instead of rediscovering them).

**Standing limitation → resolved, with a newly-scoped one (see D9):** the loop has
now been run live against DeepSeek; `runs/` holds a real run (`mode: deepseek-chat`,
non-zero spend in `runs/cost.md`), so strategy *authoring and directed editing* are
demonstrated. What remains honestly bounded: per-iteration score *improvement* is
within measurement noise at the 500-example budget — quantified in D9, not hidden —
and full signal-averaging over seeds is recorded there as future work.

## D9 — Live run, the critique that broke the "evolution" claim, and the reproducibility fix

**What was done.** With an API key in place, the loop was run live against DeepSeek
(`deepseek-chat`), replacing the MOCK artifacts in `runs/` that D8's standing
limitation flagged. Real spend, real model-authored code executed under `screen_code`.

**First finding — the loop never evolved (plumbing bugs, not model incapacity).**
The first live run stalled at 0% acceptance across all 5 iterations. Two
diagnostic-plumbing bugs were the cause: *(Path A)* on a build rejection with no
baseline, `current_code` collapsed to `None`, so the next iteration re-sent a
byte-identical seed prompt and discarded the captured error — the model repeated a
hallucinated `st.json_strings()` three times; *(Path C)* `safe_validate` swallowed a
generator exception and returned acceptance `0.0`, so the repair prompt said "emit
more valid JSON" when the code was actually throwing. Both fixed (error fed into the
re-seed; real exception propagated and the repair routed at it). With only these two
fixes the loop gets off 0% in **4/4 runs** and authors valid `st.recursive`
strategies unaided.

**Critique that mattered — "real evolution" was max-of-noise.** An independent critic,
plus an isolated experiment, attacked the "directed evolution" reading and won (each
fact re-verified by replay): the runs were **unseeded with a live example DB**, so
replaying the *identical* committed strategy spread scores ±7–11 pts and never
reproduced the recorded "best 62.9" (it averaged ~50–55); the "best" iteration and
its successor are statistically identical, while the iteration the loop *reverted* had
the **highest** mean score; the next *action* is non-deterministic on identical code
(a `productions_gap` that flips); one committed strategy (iter-2) **raises on most
seeds** and passed only via a lucky single-seed gate; and the recorded novelty revert
was noise-triggered and partly **circular** — steering toward the nesting cap floods
the accepted set with one-fingerprint deep arrays, mechanically lowering novelty, so
the loop reverted the model for delivering what it asked for (same class of
self-defeating-signal bug as the RecursionError one in D5).

**Resolution (scoped, not overclaimed).** Reproducibility is now first-class:
`run_strategy` takes a `run_seed` and disables the example DB (`database=None`), so
runs reproduce on demand while the loop stays random by default (a fuzzer wants input
diversity); evaluation reports mean±std over seeds. Two cheap, evidence-warranted
robustness fixes: **noise-tolerance on the quiet-failure revert** (needs a real
acceptance rise *and* a >~2σ novelty drop, not jitter) and a **multi-seed acceptance
gate** (a strategy must survive several seeds — verified to now catch iter-2).
Deferred as explicit future work: averaging the whole steering signal over seeds so
the *action* is stable, and redesigning novelty so it doesn't fight the cap steer.

**What is / isn't claimed now.** Reproducible and real: gets off 0%, authors valid
strategies unaided, makes directed one-change edits matching the requested action,
steers `cap_mass` reliably, detects the `duplicate_keys` deviation. **Not** claimed:
any specific score trajectory, "best score held," or that iterations measurably
*improve* the strategy — those are within measurement noise at this budget, and the
report says so.

**Critique process (D9), for the record.** The plumbing bugs, the reproducibility
flaw, and the novelty/cap-mass circularity were all caught by an independent critic
subagent challenging a claim I was ready to believe, then confirmed by re-execution
(replaying committed strategies with fixed seeds), never by reading code. This is the
third time the adversarial loop changed a conclusion (cf. D5's RecursionError, D8's
`screen_code` bypass).

## D10 — Switching target to json-parser, and the first real finding

**Trigger.** Two things unblocked at once. Prof. D'Amorim confirmed by email that
(a) using a **recent commit is fine** — dissolving the "wrong pinned commit"
worry in D1/D9 — and (b) **parson was not mandatory**. Since parson's latest
release is heavily hardened and produced zero findings across all prior work, the
second remark was taken as a nudge to pick a target where the fuzzer can actually
find something.

**Decision.** Switch to **json-parser** (udp/json-parser, `8ac4477`), the other C
JSON library on the assignment list. This was the maximally reuse-preserving
move: the ANTLR JSON grammar, the Hypothesis strategy scaffolding, the
differential oracle, the triage pipeline, the proxy-signal design, and the 85
tests all transfer. Only the C harness entry point, the build, and the vendored
source changed. Any non-JSON library (INI/CSV/TOML/XML) would have meant a new
grammar and a from-scratch adaptation.

**Immediate payoff — Finding #1 (real).** The very first structured input aborts:
json-parser executes `NULL + n` pointer arithmetic at `json.c:437` during its
first (memory-measuring) pass over object members. UBSan flags it
(`applying non-zero offset to null pointer`); it is UBSan-only (ASan-only exits 0),
so it is a standards-violation UB, not memory corruption — but the assignment's
mandated `-fsanitize=undefined` and Step 5.1 count it as a crash. Triaged through
the real pipeline: deduped 4→1, shrunk to `{""` (3 bytes), verified. Full detail
in `crashes/FINDINGS.md`.

**Judgment call — the `hunt` build.** Finding #1 fires on essentially every
object, masking the object path under the full-sanitizer build. Rather than stop
at one shallow bug, a `hunt` build disables **only** `-fno-sanitize=pointer-overflow`
(the single check the idiom trips), keeping every other ASan/UBSan check live, so
the loop can parse objects and hunt deeper. The accepted trade-off — it would also
hide a *different* real pointer-overflow — is documented in `build.sh` and
re-confirmed on the `default` build. `assert_real_target` was widened to accept
`hunt` (still refusing the synthetic `control` build).

**Critique applied.** The obvious objection — "you suppressed a bug to claim
'nothing else', that's hiding evidence" — is why the suppression is surgical (one
check, not UBSan-wide), documented, and paired with the finding it suppresses
being reported *first and in full*. Independent re-probing (numbers, NUL/control
bytes, surrogates, trailing commas, deep nesting) and the live loop both found no
second signature; deep nesting is provably not a vector because json-parser is
iterative, not recursive.

**Incidental upgrades over parson.** json-parser's `json_parse_ex` takes a length,
so embedded NUL is now *tested* faithfully (the parson exit-10 NUL-skip is gone),
and it returns an error string on rejection (a "why rejected" signal parson never
gave). It is parse-only, so the round-trip harness mode was dropped.

**Honest note on the loop run (and a cherry-pick I disclose).** The committed run
(`runs/`, deepseek-chat, real spend) is a clean 5/5-iteration evolution — score
51→60→72→73→72, novelty 16→34, cap-mass moving 0.0→0.36 exactly when the nesting
steer fired. But across the live runs I saw under this setup, the count of
iterations that produced a *working* strategy ranged from **0 to 5**: one run
rolled back four of five iterations on model-authored Hypothesis-API bugs
(tuple/str confusion, strategy-vs-int comparisons), another produced zero. The
committed run is a **favorable draw**, kept because it best exhibits the intended
behavior *and* demonstrates the Step-4.4 reject-reason feed — and I flag that
plainly in the report rather than presenting it as typical. This is exactly the
max-of-noise trap D9's critique warned about, so the spread, not the good run, is
the honest result: `deepseek-chat` is a high-variance strategy author, and the
loop's rollback/repair *machinery* is what's dependable. Two incidental fixes fell
out of this: `llm.py` gained bounded retry/backoff (a transient network reset had
killed a run), and a one-line prompt note about the `st.tuples` pitfall (generic
API guidance, not answer-seeding) reduced but did not remove the model bugs.

**Closing two spec gaps the parson target had masked.** Because parson returned no
error string, the LLM summary never carried "a sample of parser error messages"
(Step 4.4) and the per-input log never recorded a reject reason (Step 4.3) — both
justified then. json-parser's `json_parse_ex` *does* return an error, so both are
now wired: the harness surfaces it on stderr, `run_strategy` logs it per input,
and `summarize` feeds the top reject reasons back to the model (visible in the
committed refine prompts).

## D11 — From an anecdotal run to a measured claim: the multi-seed experiment

**Trigger.** D9 established that the single committed run's 51→72 "evolution" is
max-of-noise: replaying the identical strategies unseeded spread scores ±7–11 pts,
so no per-iteration *improvement* could be honestly claimed. That left the
assignment's graded core (Step 4.5–4.6, "the loop improves the generator") only
partially demonstrated — the loop authored valid strategies and made directed
edits, but whether refinement *helped* was unproven.

**Decision.** Rather than re-run the live loop and gamble on another favorable
draw, settle the question with a controlled experiment on *fixed* generators
(`eval/experiment.py`). Three conditions — random baseline, the grammar **seed**
(iter-1, no refinement), the **evolved** generator (iter-5) — each measured over
**K=12 independent PRNG seeds** at N=150 examples. One pass over the coverage
build yields region/line/branch coverage AND acceptance/novelty/cap-mass on the
same inputs. This is a **randomized block design** (every seed run under every
condition), so the correct test is **paired**: a sign-flip permutation test on the
per-seed differences, enumerated **exactly** (2¹²=4096 relabelings). Report
mean ± 95% CI and the paired-difference CI (the right CI for a comparison, not the
marginal-CI overlap).

**Critique applied (statistics).** The first cut used an *unpaired* permutation
test — wrong for this design, and it ignores the seed as a blocking variable,
losing power and mis-estimating the null. Switched to the paired sign-flip test;
it is both more correct and more powerful, and at K=12 it is exact, not sampled.

**Result.**
- **Seeding (B vs A):** +34.4 region / +37.9 branch / +14.1 novelty, paired
  p≈0.0005 — the core premise holds decisively.
- **Refinement beyond seeding (C vs B):** +2.5 region / +2.3 branch / +3.2
  novelty, **every 95% CI excludes zero**, paired p<0.02. Small but real. The
  evolved generator also reaches deep nesting the seed never did (cap-mass
  0→0.22) and trades raw acceptance (0.75→0.61) for diversity — the guardrail's
  intended behaviour.

**What is now claimed (vs D9).** D9 could claim only: gets off 0%, authors valid
strategies, lands one directed edit. D11 adds a *measured, distribution-backed*
claim that **refinement improves on the grammar seed** (modestly, significantly),
without over-claiming any single-run trajectory — that remains noise. The
`eval/proxy_validation.py` audit (novelty↔branch-coverage ρ≈+0.9) independently
supports why novelty was the right thing to steer by. Neither eval steers the
loop; both are measurement-only, honoring the no-coverage-instrumentation rule.

## D12 — The `unmask` build: hunting past finding #1 without a blind spot

**Trigger.** Finding #1 aborts on every object, so the `hunt` build (global
`-fno-sanitize=pointer-overflow`) was the only way to reach the object path — but
it hides *any* other pointer-overflow, a documented blind spot. FINDINGS.md listed
"surgically suppress finding #1 at just that site" as future work.

**Investigation.** The obvious surgical move — `__attribute__((no_sanitize))` on
the offending function — turns out to be **no narrower than `hunt`**: `json_parse_ex`
is monolithic (the entire parser is one function, json.c:255–996), so a
function-scoped suppression blinds pointer-overflow across the whole parser.

**Decision.** Do it at the line, not the function. `harness/apply_unmask.py`
rewrites *only* finding #1's two `NULL + n` sites (`chars[0] += n` and the
`_reserved.object_mem` sibling) to integer arithmetic on the same pointer-sized
storage (`*(size_t*)&field += n`). The stored bytes are **bit-identical**, so
behaviour is unchanged, but the arithmetic is well-defined — so the object path
runs clean under the **full** sanitizer set with `pointer-overflow` LIVE
everywhere else. The pinned `vendor/` source is never touched (patched copy in
`build/_patched/`); `assert_real_target` accepts `unmask` alongside `hunt`.

**Critique applied (patch-artifact risk).** A crash on a patched binary could be a
patch artifact rather than a real bug. Mitigation: the patch is provably
value-preserving (integer vs pointer arithmetic over the same bytes), it is a
2-line diff auditable in one glance, and `{""` still traps on `default` (fidelity
confirmed). Any ASan issue it surfaced would be unrelated to the arithmetic change
anyway.

**Result — no second signature.** The evolved generator over 800 examples, a
curated object-path adversarial set, and a first-pass memory-measurement stress
(objects 100 000 deep, 500 000 members wide, 200 000 duplicate keys) all parse
cleanly — no abort, no timeout. json-parser's iterative two-pass design handles
these without overflow. So finding #1 is, within this budget, the one
sanitizer-detectable issue on the parse-only surface — now established without the
`hunt` build's blind spot.

## D13 — Seeded Hypothesis draws depend on process history: found, fixed, re-measured

**Trigger.** Making the evals target-aware (paper Tier A) meant refactoring
`coverage.py` / `experiment.py` / `proxy_validation.py` onto one shared
measurement (`eval/cell.py`). The refactored `coverage.py` reported 42.6 / 81.5
line% where the committed file said 42.2 / 83.1. A refactor is not supposed to
change a measurement.

**Investigation (each step by execution, each hypothesis tested before believed).**
- Not the measurement: identical inputs on one binary, measured twice by the same
  function -> bit-identical (42.17 twice; 0 crashes; 400 profraws each).
- Not the compiler: `CC` unset, both build commands identical.
- Not `PYTHONHASHSEED`: draws identical across processes for any hash seed.
- Not "residual noise" (an earlier guess, wrong): the discrete levels 42.17 /
  42.60 / 43.61 were each perfectly reproducible in their own context.
- The cause: a seeded Hypothesis draw is reproducible across processes ONLY for
  an identical process history. Merely `import baseline_strategy` (which
  decorates a `@given` test at import), or launching via stdin vs a file,
  changes the sequence `@seed(0)` yields (D-1..D-4: every context reproduced
  3/3, but contexts differed from each other). Each eval script therefore drew a
  different, deterministic input set. (Side finding: the sequence also depends
  on the test function's qualname.)

**Fix.** `eval/_draw.py` draws in a fresh interpreter with a fixed minimal
history; `cell.draw_examples` takes strategy REFERENCES (never live objects),
caches each set under `build/_inputs/` keyed by hash(strategy source, n, seed),
and every measurement records its input-set id. Verified: six launch contexts
that previously gave three hashes now give one; `coverage.py` run twice is
byte-identical and reproduces the committed 42.2 / 83.1 exactly (the isolated
history coincides with the original script's).

**Re-measurement outcome (claims robust, numbers updated everywhere).** With
reproducible draws: seeding +34.4 region / +37.9 branch / +14.1 novelty
(p=0.0005); refinement beyond the seed +2.5 region (CI [+0.9,+4.1], p=0.0068),
+2.3 branch (p=0.012), +3.2 novelty (p=0.011) — every CI excludes zero. Proxy
correlations unchanged in story (novelty↔branch +0.9, acceptance -0.9,
cap-mass -0.5). The seed row was identical before/after; the drift lived in
the random-baseline and evolved draws, exactly as the mechanism predicts.

**What this does and does not mean.** The INTERNAL validity of any single
experiment run was never affected (all its cells share one history and are
paired by seed). What was affected is exact cross-script reproduction of the
numbers — which is precisely what a reviewer re-running an artifact does. This
is a trap any Hypothesis-based LLM-fuzzing evaluation can fall into; it goes in
the paper's reproducibility section as a contribution, not a footnote.

## D14 — First live run on a second target, and what "the loop's output" means

**Run.** The loop ran live against parson (T2) with the same protocol as
json-parser (default parse harness, 5 iterations, deepseek-chat, $0.023).
Iterations 1 and 2 were gated: the model passed multi-character escape strings
as a Hypothesis `alphabet` (InvalidArgument) and its repair repeated the same
mistake — a new entry for the LLM-as-author failure taxonomy (Appendix C).
Iteration 3 was the first working generator, iteration 4 the best (score
56.6), and iteration 5 regressed (43.3) so the loop rolled back. The probes
flagged `duplicate_keys` as a parson-only deviation every iteration, unprompted.

**Design gap it exposed.** The evaluations read "evolved" as literally
`iter-5/strategy.py` and "seed" as `iter-1`. On this run both are wrong: the
loop's output is the rolled-back iteration 4, and iteration 1 never ran. On the
json-parser run the naive reading happened to be right (iter-5 was accepted,
iter-1's repair worked), which is why it went unnoticed.

**Fix.** The loop now writes `final_strategy.py` + `final.json` (the strategy
it hands back after any revert, with its source iteration) and `config.json`
(target, ablations, model). For runs made before that, `cell.final_strategy_path`
reconstructs the output from `evolution.md` by replaying run_live's own
bookkeeping — current = this iteration unless it reverted (then the best so
far); gated iterations still advance current; best updates after — and
`cell.seed_strategy_path` returns the first iteration that actually draws.
Verified against both runs (json-parser: iter-1 repaired / iter-5, so every
committed number stands; parson: iter-3 / iter-4). `matrix.py` and
`experiment.py` resolve conditions only this way.

**Consequence for the paper.** Draw seeds average out input noise for a fixed
generator but cannot average out the loop's own variance; RQ2 must be reported
over >=3 loop replicates per target (`--run-name repN`), as a distribution of
per-replicate paired deltas. Recorded in paper/experiment-matrix.md.

**Also landed.** `--ablate` (production, capmass, novelty, probes, signal — the
last being the "no signal at all" control) with budgets held constant across
conditions; the matrix runner (`eval/matrix.py`, resumable, input-set ids per
row) and aggregator (`eval/report.py`, paired tests, Holm-corrected ablation
family, cross-target summary).

## D15 — Paper infrastructure, step 1-3: provenance, a clean A5 control, anonymized prompts

**Context.** The master plan (paper/plan.md v5) forbids launching replicate
runs until three fixes land, because runs made before them would have to be
discarded. All three are in; no live run has been made yet.

**Provenance.** `llm.chat()` now fills a per-call record: the model id the
provider actually SERVED (aliases such as `deepseek-chat` float),
`system_fingerprint`, request id, latency, UTC timestamp, tokens.
`StopController.calls` keeps them; every iteration writes
`iter-N/provenance.json` (wall s, CPU s including harness children, the calls
it made, any 10-min backstop hits); `config.json` records provider URL,
requested model, prompt mode, git commit, Python and Hypothesis versions,
platform, host, start time; `final.json` is written for EVERY completed run
(a missing file means the run died; the replicate driver keys on that) and
carries totals: iterations, stop reason, tokens, cost, served models,
fingerprints, wall/CPU seconds, backstop hits, and the selection rule.

**A5 was not signal-free.** On a rejected build or a mid-run generator error
the loop fell back to `best_code`, which is chosen by the proxy score, so the
"no steering" control still used proxy-based SELECTION on exactly the
iterations where it matters. Under `--ablate signal` the fallback is now the
last WORKING generator (`selection: last_working` in final.json). The refine
prompt under A5 no longer carries an empty `{}` summary block; it says "No
run feedback is provided." Name the condition "no steering signal", not "no
feedback": the validity machinery (build screen, acceptance gate, repair)
stays, by design.

**Anonymized prompts (default), legacy mode kept.** The model used to see the
library's name, its API function names and its error strings, which differ
per target (parson returns no message) and are a memorization risk. In the
default `anon` mode the realities block, the adaptation notes, the section
header, and crash signatures shown to the model are scrubbed (library name
-> "the parser", parse API -> "the parse function", source file ->
"target.c"), and the parser's reject-reason strings are withheld from the
model while still logged in stats.json (`summary` = full, and
`summary_shown_to_model` = what the prompt carried). `--legacy-prompts`
reproduces the pilot runs' text byte-for-byte (tested). Consequence: the two
committed pilot runs (json-parser, parson) are legacy-mode and are reported
as pilots, never as replicates.

**Verified by execution.** 97/97 tests (12 new); mock runs of both a
no-steering and a steered loop produce final.json, per-iteration
provenance.json, and prompt files containing no identifier. Not exercised:
the A5 fallback path itself needs a failing generator, which the mock cannot
produce; reviewed by reading, to be confirmed on the first live gated run.

## D16 — Paper infrastructure, step 4: in-process harness (batch mode, coverage curves, o2 build)

**Why.** A fuzzing reviewer will not accept per-process stdin runs with a
fixed-n coverage snapshot as a measurement; the paper's primary outcome is a
coverage-vs-inputs curve to 10^4 inputs, and the reference row is AFL++.
Process-per-input made both impractical (800 spawns for one coverage.py run).

**What.** `harness/driver.h` is now the shared driver: each target's
harness.c defines only `harness_parse(buf, len, msg, msgcap)`. The driver
provides (1) the unchanged stdin/exit-code mode (the loop and triage use it;
contract verified: `{""` aborts under UBSan, `[1,2]` exits 0, `{` exits 2
with its reason), (2) `--batch`: length-prefixed inputs on stdin, one
`R <index> <code> [<msg>]` line per input, an in-process `alarm()` timeout
(exit 124), and under `-DCOVERAGE_BUILD` cumulative profile flushes at
`--checkpoints` plus a final flush at exit or on a fatal signal, (3)
`LLVMFuzzerTestOneInput` for libFuzzer/AFL++ (untested on this macOS
toolchain; exercised in Docker later). `fuzz/runner.run_many` drives batch
mode with the SAME classification rule as run_once, restarts the harness
after a death (sanitizer report read from stderr, the dead input classified,
next index resumes in a new profile segment), and keeps a runner-side
timeout as a backstop. `eval/cell.coverage_curve` merges segment profiles
per checkpoint. `MODE=o2` builds the uninstrumented -O2 binary on which a
timeout must reproduce before it is called a hang. The positive-control
build gains a `__HANG__` marker so the timeout path is testable.

**Verified.** Batch outcomes equal run_once outcomes on a mixed list with two
mid-batch crashes and a hang; `coverage.py` reproduces the committed 42.2 /
83.1 line% byte-for-byte through the new path (1.8 s instead of 800
spawns); a 300-input parson curve is monotone; 104/104 tests (7 new).

## D17 — Paper infrastructure, step 5: the proxy is now grammar-derived and format-generic

**Why.** The reviewers' sharpest methodological objection: the proxy was
JSON-specific in code (a `json.loads` walk for productions, bracket counting
for depth), so "the same method, held out on TOML/XML" would have been a new
signal per format. That is not a held-out evaluation.

**What.** `fuzz/formats.py` derives the three structural features from the
SAME ANTLR grammar the model is given: an ANTLR 4.13.2 Python parser is
generated from `grammar/<FMT>.g4` into `grammar/gen/<fmt>/` (committed, so
reviewers need no Java; `grammar/gen.sh` regenerates). A STRICT parse (bail
on any lexer or parser error; the default ANTLR behaviour recovers and would
count garbage as parsed) yields productions = parser rules + named
non-skipped tokens + word-like literals visited, depth = recursion depth of
the most-recursive rule minus one (equals bracket depth for JSON), and the
novelty fingerprint = (productions, depth band). `PRODS`, the universe the
production-gap steer closes, is read from the generated parser. Deep inputs
parse in a worker thread with a 512 MB stack. The per-target deep-nesting
band moved into `fuzz/targets.py` (`cap_band`). Probes and the differential
oracle remain per-format and are declared as the human-authored part.

**Consequences, stated.** Production names are now the grammar's own
(`obj`, `arr`, `STRING`, `NUMBER`, `true`, ...; `json`/`value`/`pair` are
always present when anything parses). Depth is measured only on
grammar-valid inputs: a target-accepted input the grammar rejects (a
deviation such as a trailing comma) now has depth 0 where bracket counting
gave its real depth. The committed pilot numbers in docs/ and eval/*.md were
measured with the old features and are superseded by the matrix pass.

**Verified.** 2000-deep arrays and 1800-deep objects parse in 30-50 ms; 500
ordinary inputs in 90 ms; trailing-comma and truncated literals yield no
productions as before; 105/105 tests; a mock parson loop steers on `obj`.

## D18 — Paper infrastructure, step 6: the coverage-oracle conditions C3s and C3n

**Why.** The reviewers rejected "hand the model a coverage number and call it
the oracle": with the proxy still choosing the action, doing the rollback
and picking the best iteration, that is proxy steering with a comment, and
it would read C3 ~ C2 as "the proxy recovers coverage". The oracle must
replace the proxy at every place the proxy acts.

**What.** `agent.py --oracle coverage_scalar|coverage_named`. After each
full run the iteration's own inputs are measured on the coverage build
(`eval/cell.measure_for_loop`: one batch pass, branch/region/line % plus the
least-covered functions from `llvm-cov -show-functions`). Branch coverage
then IS the score: it drives the regression check, the best-selection and
the rollback exactly as the proxy score did (same tolerance band), and the
next action is `increase_branch_coverage` (scalar) or `cover_function <name>`
(named). The refine prompt carries only the coverage view: the two numbers
under C3s, plus the least-covered function names under C3n. C3n is
white-box lite (the Gentoo-S analogue) and its function names are NOT
anonymized; say so in the paper. `--oracle` cannot be combined with
`--ablate`. Every iteration's stats.json records BOTH `coverage_in_loop` and
`proxy_score`, so every oracle run also yields RQ3 validity data (proxy
score vs coverage over the same generator) at no extra cost. final.json's
selection rule reads `coverage_best_with_revert`.

**Verified.** Mock C3n run on json-parser: score = 16.67 (branch %), action
`cover_function (hex_value ...)`, iteration-2 prompt says "measured with
instrumentation" and carries `branch_coverage_pct`; 111/111 tests (6 new).

## D19 — Paper infrastructure, step 7: the parse-reachable region is the primary metric's denominator

**Why.** Whole-file coverage is not comparable across targets: random text
reaches ~42% of json-parser's json.c but ~13% of parson's parson.c, because a
parse-only harness can never touch parson's serializer, query and mutation
APIs. The matrix doc admitted this; now it is operational.

**Definition.** `eval/reach.py`: reachable = STATIC (functions of the target
source reachable from `harness_parse` in the direct call graph extracted
from clang's LLVM IR of library + harness) UNION OBSERVED (functions with a
covered region in any profile handed in; this closes the function-pointer
gap, which is real: json-parser's allocator hooks are only reached through
`settings.mem_alloc`). The list, with its provenance and the unreachable
complement, is committed under `eval/reachable/<target>.json`. json-parser:
9/10 functions (only the unused `json_parse` wrapper is outside). parson:
40/144. The evaluation's sanity check (plan E9) must fail if any cell ever
covers a function outside the list; that forces regeneration and a note.

**Measurement.** `cell.coverage_curve` reports `*_reach` totals alongside
whole-file totals via llvm-cov's `-name-regex` (honoured only with
`-show-functions`). Found by checking numbers, not by reading docs: llvm-cov
lists static functions as `file.c:name`, so an anchored name regex silently
dropped every static function from the restricted totals. The regex now
admits the prefix, and a test asserts that restricting to ALL functions
reproduces the whole-file totals exactly. The coverage oracle (C3) steers on
the reachable-region branch coverage when the list exists.

**Effect on identical inputs.** parson: 13.4% branch (file) vs 43.5%
(reachable region); json-parser: 40.9% vs 40.9% (the excluded wrapper has no
branches). `eval/test_eval.py` (15 checks) is now the fifth suite in
`./run.sh test`; 126/126.

## D20 — Paper infrastructure, steps 8-9: replicate driver, curve/AUC cells, replicate-level statistics

**Driver** (`eval/replicates.py`): interleaved order (rep 1 of every condition
x target before rep 2; conditions alternate within a rep) so provider drift
is orthogonal to treatment; resumable (final.json = done; a run directory
without it is deleted and rerun, never reconstructed); a lock file that
`eval/matrix.py` refuses to run against (load-induced timeouts would be
misread as crashes and change the loop's decisions); a manifest with argv,
exit code, wall time and served models per run; a one-line STATUS file,
which is the only thing the assistant session reads during a batch.

**Cells** (`cell.measure_curve_cell`, `matrix.py`): each (target, condition,
seed) cell now draws n=10^4 inputs (default) and records the coverage curve
at log-spaced checkpoints 10..10^4, its area (mean over the checkpoints,
i.e. the area on a log-n axis; `auc_branch_reach` is the pre-registered
primary outcome), final-n coverage whole-file and reachable-region, proxy
metrics, distinct inputs, skips, and draw vs run wall time (for the
equal-time views). Condition `run:<sub>:last` (last working iteration) is
reported next to `final` so an oracle condition cannot win by selecting the
max of its own noisy metric.

**Statistics** (`report.py`): the replicate is the unit. Per loop condition
(C2, A5, C3s, C3n): draw seeds are averaged within a replicate, then
final-level mean ± CI over replicates, the last-iteration mean, per-replicate
Δ(final − seed) with an exact sign-flip test, and H1/H2 as difference of
replicate means with a two-sample permutation test and Vargha-Delaney A12
with a percentile-bootstrap CI. Replicate runs are excluded from the Holm
ablation family. Verified on synthetic data with known effects (C2 = seed+3,
A5 = seed+0.2, C3s = seed+5, replicate noise 1): H1 A12 0.98, p 1e-4; H2
A12 0.92, p 5e-4; the C2 row shows 10 replicates and Δ≈+3. A tiny real
matrix pass (both pilots, n=60) produces curves, AUCs and timings; 127/127.

## D21 — Paper infrastructure, step 10: the Grammarinator baseline (C0b), and a first glimpse

**Why.** ELFuzz and G2Fuzz benchmark against Grammarinator on the same ANTLR
grammar; without it, "LLM seed vs random text" conflates having a grammar
with LLM authorship.

**What.** `grammarinator==26.1` (pinned). The generator is produced by
`grammarinator-process grammar/JSON.g4 -Ddot=any_unicode_char` (the default
charset for negated classes is printable ASCII, which would have made the
baseline weaker than the LLM seed on string handling by construction). It
lives under build/ (regenerable) but its sha256 and every generation
parameter are pinned in `eval/grammarinator.json`; `cell.grammarinator_generator`
regenerates it when missing and REFUSES to run on a hash mismatch. Draws
(`eval/_draw.py`) drive the generator class directly with `DefaultModel`
and a seeded `random` in a fresh process (not GeneratorTool, which adds
unseeded choices and mutators); no Hypothesis is involved. The input-set id
hashes the generator bytes, the grammarinator and Python versions and the
pin. Two variants: `grammarinator` (defaults: uniform alternatives,
unlimited depth; terminates because the recursion is subcritical, mean
grammar depth 0.19) and `grammarinator-deep` (the obj/arr alternatives of
`value` up-weighted x5 via `WeightedModel`, calibrated so the mean depth,
0.71, matches the json-parser pilot's C1 seed generator, 0.73). A pitfall
found by execution: `RuleSize(depth=D)` leaves `tokens=0`, which collapses
output to four trivial values; the token limit must be set to infinity.

**Glimpse (K=3 seeds, n=300, json-parser, NOT a result).** Grammarinator on
the same grammar reaches about the same branch coverage as the LLM seed
(65.6-66.5% vs 62.5-65.4%) with higher novelty (30-35 vs 17-18), while the
seed leads on region coverage (66-68% vs 61%). If the full matrix (n=10^4,
20 seeds, reachable-region AUC) confirms it, RQ1's "LLM authorship" claim
narrows to region coverage or disappears on this target, and the paper says
so. This is why the baseline exists.

**Verified.** Draws identical across two fresh processes; different seeds
differ; every draw is grammar-valid; deep > defaults in mean depth; sha256
matches the pin; 134/134 tests.

## D22 — Paper infrastructure, step 11 (part 1): tomlc99, the first non-JSON target, with ground truth

**Vendored** (vendor/tomlc99/PROVENANCE.md): toml.c/toml.h at
`29076df` (2026-01-30; the upstream repo is marked obsolete, which makes it
a stable artifact), MIT. Grammar: grammars-v4 `toml/TomlLexer.g4` +
`TomlParser.g4` at `8af0d4c26c`. Ground-truth bug builds under
`vendor/tomlc99-bugs/`: `issue50/` = the pre-fix source at `c5d2e37` (fix
`fd82018`, a two-line NULL check in `parse_keyval`); the recursion
stack-overflow (#94/#95/#97, CVE-2026-16634) is UNFIXED at HEAD, so the
default build is its bug build. `harness/build.sh MODE=bug-<name>` compiles
the same harness against `vendor/<target>-bugs/<name>/` with the full
sanitizer set; `assert_real_target` still refuses it as a source of loop
findings.

**Positive controls, verified by execution.** The issue-50 PoC
(`[0]\n0.0=[]\n+.\n`) SEGVs the pre-fix build and is a clean REJECT ("bad
key") on HEAD; the recursion PoC (100 000 nested arrays) is a sanitizer
`stack-overflow` on HEAD; depth 2048 (the steer band) is VALID for arrays
and inline tables; ~20 000 levels overflow. Both PoCs live in
`fuzz/targets.py["tomlc99"]["bugs"]` and are asserted in test_pipeline.

**Adaptation notes** (targets/tomlc99/adaptation-notes.md) were produced by
running 50 hand-written inputs through the harness against `tomllib` as the
strict oracle: tomlc99 is MORE LENIENT on leading zeros (007), `1.`/`.5`,
raw control characters in strings and comments, a trailing comma in an
inline table, and calendar-invalid dates; it matches strict behaviour on
duplicate keys/tables, newlines in inline tables, invalid escapes,
non-ASCII bare keys. None of the leniencies trips a sanitizer.

**Format-generic pieces that this target forced.** (1) Multi-file grammars:
the seed prompt concatenates every file in the registry's `grammars`. (2)
Per-format probes and oracle registries (`probes.probes_for`,
`oracle.oracle_for`): TOML gets the same six probe ROLES realised in TOML
syntax (declared as the human-authored part) and `tomllib` as the strict
oracle; a format without a reference parser simply collects no divergences.
(3) Anonymization patterns for tomlc99 (library name, successor name, parse
API, source file, CVE and issue numbers). (4) Named punctuation tokens
(TOML's `L_BRACKET`, `EQUALS`, ...) are excluded from the production
universe like JSON's implicit literals: syntax, not coverable productions
(TOML: 53 -> 44 productions).

**The JVM feature server.** The Python ANTLR runtime costs ~1.3 ms per
nesting level on the TOML grammar (an adaptive-prediction decision at every
level; JSON is 80x cheaper), which would make deep inputs cost seconds each
and the 10^4-input matrix cells infeasible. `harness/FeatureServer.java`
runs the SAME grammars (Java twins generated by `grammar/gen.sh`, same
ANTLR 4.13.2, so rule indices and token types are identical) on the JVM and
reports only raw facts per input (ok, recursion depth, distinct rule
indices, distinct token types) over a pipe; all naming and filtering stays
in Python. `harness/build_java.sh` compiles it; `formats.py` uses it when
built and falls back to the Python runtime otherwise (`FORMATS_PY=1`
forces the fallback). Parity on a mixed corpus (deep, invalid, both
formats): identical; 2.3 s -> 0.42 s including JVM start-up. Docker will
need a JDK; noted for step 4's container.

**Verified.** 158/158 tests (24 new: tomlc99 contract and both PoCs, TOML
prompt anonymization and both grammar files present, probe/oracle
registries, JVM/Python parity). A 200-input TOML replay runs the whole
summarizer in 14 s.

## D23 — Paper infrastructure, step 12: ground-truth bug campaigns (RQ4), and json-parser's two bugs

**json-parser bugs.** Two one-byte heap over-reads at the end of the input,
now usable as ground truth (vendor/json-parser-bugs/PROVENANCE.md):
issue78 (`tru`, a truncated literal) and issue68 (`"\uDCB`, a `\u` escape
truncated after three hex digits). The documented issue-68 reproducer did not
crash; a search over truncated escapes found the working input. Both crash
their pre-fix build and are clean REJECTs on the fixed HEAD. Because the
over-read is one byte PAST the input, the json-parser harness now hands
`json_parse_ex` a buffer of EXACTLY the input length (the driver's
NUL-terminated buffer had masked them). The bug builds compile with
`-fno-sanitize=pointer-overflow` only (finding #1's NULL-offset idiom
predates these commits and would abort first).

**Campaign runner** (`eval/campaign.py`, plan step 12). Per (target, bug,
generator, seed): draw batches from the generator and feed the pre-fix build
until the bug's OWN crash signature appears (Magma-style: triggered is decided
by signature match, not "any crash"), the time budget expires, or the input
budget is exhausted; record inputs/time-to-trigger or censoring, plus every
other crash signature (candidate new findings). The oracle signature is
established by running the bug's PoC first; a PoC that does not crash is a
failed positive control and the bug is dropped with a note. Both the control
and the campaign classify through BATCH mode (run_many), so the driver's
entry-point frame is identical in both signatures (a stdin-vs-batch frame
mismatch first made a real trigger look like a miss).

**Verified.** Positive controls pass for json-parser issue68/issue78 and
tomlc99 issue50; a campaign whose generator emits the PoC triggers on the
first input and records inputs/time; a builtin-text campaign censors cleanly
when the budget runs out. 164/164 tests (6 new). Deferred to the Docker
step: a JDK in the image (the JVM feature server) and AFL++ for the reference
row (neither is installed locally; the Docker daemon is currently down).

## D24 — Pre-spend review: 20 questions answered by execution; four gaps fixed

A second reviewer pass (before any live run) asked 20 verifiable questions.
Answers with evidence are in the session record; the four that exposed real
gaps and their fixes:

- **The generic requirements head was JSON-flavoured for every format**
  ("obj/arr productions", "empty {} and []", "missing colons") and reached
  the TOML prompt. Now `_requirements_head(fmt)`: JSON keeps the pilots'
  byte-identical text; every other format gets a neutral head. A test scans
  the rendered tomlc99 prompt for those JSON-isms.
- **Cached input sets reported zero draw time**, which would have corrupted
  the equal-time views. The first draw's wall time is now persisted next to
  the cached set (`<id>.meta.json`); `cell.draw_seconds` returns it and the
  matrix row uses it.
- **The feature backend (JVM vs Python) was not recorded.** `config.json`
  and every `iter-N/provenance.json` now carry `features_backend`, so a
  mid-run fallback is visible per iteration; matrix rows carry it too.
- **The parse-reachable region was committed but not pinned per run.**
  `reachable_region_sha` (sha256 prefix of eval/reachable/<target>.json) is
  in `config.json` and in every matrix row, so any post-hoc change to the
  region definition is detectable in the data.

Also: `paper/preregistration.md` drafted (hypotheses, single primary
outcome, conditions, budgets, loop-output definition, exclusion rules,
analysis with A12 thresholds, predictions under every outcome, bug
reachability expectations, the compute-matched argument, cost ceiling,
disclosures). A git bundle of `main` + `paper/multi-target` was written to
~/agentic_fuzzing-backup-2026-09-12.bundle as an off-repo backup (the branch
stays unpushed per the grading-period rule). 167/167 tests.

## D25 — Phase 1a ran; the draw protocol had to become failure-tolerant

**Phase 1a (live, 2026-09-12 12:37-15:40 UTC).** 20 runs (C2 and A5 alternating on
json-parser, replicates 1-10), all five iterations each, total $0.515 against
the $0.50 estimate, zero backstop hits. Every one of the ~110 API calls was
SERVED as `deepseek-flash` although `deepseek-chat` was requested; the
provenance fields caught it, it was constant across the batch, and the paper
reports the served id. A ~15-minute DNS outage at 14:15 failed eight runs at
the first API call (no spend); the driver was resumed at 14:31 and reran
them; the manifest keeps both the failure rows and the reruns.

**What the first measurement exposed.** One replicate's output generator
(C2-rep7) raises on every draw: the model repeated the same broken construct
(`strategy + str`) in all five iterations, every iteration was gated at
acceptance 0.00, and by the registered rule (gated iterations count as they
happened) the loop's output is that unusable generator. Hypothesis aborts a
whole draw at the first exception, so under the original draw path this
replicate, and any generator with a rare raising branch, would have KILLED a
matrix shard instead of being measured.

**Draw protocol v3** (`eval/_draw.py`; input-set ids carry `draw=v3`, so
every set is re-drawn and no pre-v3 cache is reused): the n examples are
drawn in chunks of 100 under derived seeds (seed*1000 + chunk); a chunk whose
generator raises is dropped and counted (`draw_failures`, persisted with the
set and carried in every matrix row); a successful chunk that returns fewer
than requested means the strategy space is exhausted and the draw is
complete (small generators, e.g. a single-value strategy); a generator that
cannot fill the set within 3x the needed chunks raises `DrawError`. The
matrix records such a cell with its error and continues; the report scores a
failed cell as the MINIMUM on every metric and shows failed-cell counts per
condition. Tolerance is about one raising example in 300; generator
fragility is thereby a measured secondary quantity (RQ5), not a lost
replicate. Shrinking is off (generate phase only). Hypothesis favours
boundary values, which the fragile-generator test had to respect.

**Two of my own mistakes, recorded because they cost time.** (1) A wait loop
passed a pid list as one unsplit zsh variable, so `kill -0` failed and the
loop reported four healthy shards as dead; their logs looked empty only
because stdout was block-buffered. Matrix progress now flushes, and shards
run under `eval/run_shards.sh` (one detached supervisor, automatic resume,
one-line STATUS). (2) A zsh `for spec in ...; set -- $spec` loop did not split
either, so three generators were "diagnosed" with an IndexError that was
`_draw.py` missing its seed argument; re-checked with correct arguments, all
three draw cleanly. Only C2-rep7 is broken.

**Also.** `build_coverage_binary` is idempotent (parallel shards no longer
race on the compile); macOS has no `timeout` binary (use a perl alarm).

## D26 — Phase 1a result: H1 is null on json-parser; refinement does not improve on the seed

Registered analysis (paper/preregistration.md, frozen at 4762bad), primary
outcome `auc_branch_reach` (10^4 inputs x 20 fresh seeds per replicate),
failed cells scored 0. Data: eval/matrix/stage1a.jsonl (800 cells), report
eval/matrix/stage1a_report.md.

| | C2 proxy | A5 no steering |
|---|---|---|
| final, replicate means (10) | 51.0 ± 19.3 (median 63.9) | 63.7 ± 2.8 (median 64.6) |
| unusable output generators | 2 (rep7, rep10: gated at 0.00 on all 5 iterations) | 0 |
| Δ final − seed per replicate | −1.0 ± 0.8, sign-flip p = 0.031, 2/10 positive | +0.1 ± 1.2, p = 0.77, 6/10 positive |

H1 (C2 vs A5): Δmean −12.7, Vargha-Delaney A12 = 0.36 (bootstrap 95% CI
[0.14, 0.63]), permutation p = 0.24. Not a practical difference by the
registered thresholds; the point estimate favours the control. Among usable
generators the conditions are indistinguishable (exploratory: C2 63.69 over
8 vs A5 63.68 over 10). Neither loop improves on its own seed: the proxy
steer's per-replicate delta is small and NEGATIVE (8 of the 8 usable
replicates went down, typically by 1-3 points), the control's is noise.

Reading, per the pre-registered predictions: on this target the structural
steering signal does not earn its place, and refinement of any kind adds
nothing beyond the seed at this budget. The mean difference between
conditions is entirely the two replicates where the proxy loop's model
repeated a broken construct five times and the loop handed back an unusable
generator; the control never did, but with n = 10 per arm that asymmetry
(2/10 vs 0/10) is not itself established. The H1-null contingency governs
phase 1b. Caveats: one target, the in-sample development target, whose
default build aborts on every object (finding #1); the held-out targets are
where the question is properly answered. Served model for every call:
deepseek-flash. Cost of phase 1a: $0.515.

**Addendum to D26 (2026-09-13): the served model.** On every call in phase
1a where `deepseek-chat` was requested, the provider's response reported
`model: deepseek-flash`. DeepSeek's public pricing page (api-docs.deepseek.com,
read 2026-09-13, no API calls spent) lists only `deepseek-flash`
(DeepSeek-V4.1-Flash) and `deepseek-v4-pro`, does not list `deepseek-chat`
at all, and says of other retired names that their "requests are served by
the DeepSeek-V4.1-Flash model and billed at the Flash price"; the legacy
`deepseek-chat` alias is evidently handled the same way. This applies
RETROACTIVELY: the two pilots (2026-08-24, 2026-09-12) recorded only the
requested alias, so the model behind every previously reported effect number
is unknown but was in all likelihood the same routed Flash model; the paper
reports the served id (`deepseek-flash`, DeepSeek-V4.1-Flash) throughout and
states this caveat for the pilots. Flash list prices ($0.15-0.30 in,
$0.60-1.20 out per million tokens, off-peak vs peak) bracket the `.env`
estimates (0.27 / 1.10), so reported costs are close to the peak rate;
actual spend is reconciled against the provider dashboard by the user.

## D27 — Stage 1 closed: at this budget the seed is everything; no synthesis-time feedback moves it

**Summary.** Across three C parsers and four loop arms (proxy C2, no steering
A5, coverage oracle C3s, proxy with repair by re-seed C2R), 10 replicates per
cell, no loop improves on its own seed and no arm beats another on the
registered primary outcome (`auc_branch_reach`). H1 (C2 vs A5) is null on
json-parser, parson and tomlc99 (D26 and eval/matrix/h1_report.md). H2s (C3s
vs C2) is null on tomlc99. What differs between arms is only whether a loop
occasionally hands back an unusable generator, and that is a property of the
repair path, not of the steering signal. The registered third prediction
holds: C2 ~ A5 ~ C3, "refinement of any kind adds little at this budget".
Served model on every call: `deepseek-flash`. All DeepSeek spend is now
stopped permanently (user decision).

Three closing cells were run in the order the user set after D26.

**1. Grammarinator at full n (C0b, no API cost).** 10^4 inputs x 20 draw seeds
on all three targets (defaults and depth-matched on the JSON targets; the
pinned TOML deep variant equals defaults), 100 cells, 0 failed; report
eval/matrix/rq1_report.md (eval/rq1_report.py). The generator is the unit of
an authorship claim, so the leading statistic is A12 of the 20 LLM seed
generators per target against Grammarinator's 20 draw values; the plan-E7
pairing by draw seed carries draw noise only and overstates certainty (shown,
caveated). Healthy seeds vs the stronger Grammarinator variant: json-parser
A12 0.62 [0.43, 0.80] (ties depth-matched), parson 0.70 [0.51, 0.87] (LLM
ahead), tomlc99 0.13 [0.02, 0.28] (Grammarinator decisively ahead: 2 of 17
healthy seeds above it). On tomlc99 Grammarinator also beats every loop final
(A12 0.14 vs A5, 0.13 vs C2). So "LLM authorship beats having the grammar" is
target-dependent: it holds on parson, is a tie on json-parser, and reverses
on the one non-JSON target. tomlc99 has THREE failed seed generators
(A5-rep10, C2-rep3, C2-rep9); two (A5-rep10, C2-rep9) end with a working
final and inflate that target's final-minus-seed deltas by the whole final
level (the paper must flag this); C2-rep3 also collapses at the final.

**2. C3s on tomlc99 (the decisive cell).** 10 replicates, 0 reruns, 0.414 USD
(above the 0.25 USD estimate: more tokens per call and more repair calls than
the Stage 1 tomlc99 runs; flagged to the user during the batch). H2s C3s vs
C2: A12 0.60 [0.35, 0.86], permutation p 0.65, Holm over the family actually
run on this target {H1, H2s} 0.65. C3s vs A5: A12 0.49. C3s per-replicate
delta +0.22 (sign-flip p 0.44); 1 of 10 collapsed. The coverage oracle does
not rescue refinement, so the proxy is not the specific failure: at this
budget no synthesis-time feedback moves the seed. The last-working-iteration
level is reported next to final (plan E1). Report eval/matrix/stage1c_report.md
(eval/stage1c_report.py).

**3. C2' repair by re-seed on json-parser.** `agent.py --repair reseed`
(driver name C2R, commit cca50d8): the model is never shown failed code; the
in-iteration repair and every prompt while the held generator is a failed one
is the grammar seed prompt with the failure text. Default path unchanged
(scripted-LLM tests). The ExceptionGroup formatter defect was left as is.
Result: 0 of 10 collapsed (C2 2 of 10; Fisher p 0.47, not established);
final 63.9 ± 1.3 vs C2 51.0 ± 19.3; A12 vs C2 0.58 [0.32, 0.83] (small, CI
includes 0.5; the whole mean difference is C2's two zeros), healthy-only
A12 0.47; vs A5 0.46. Per-replicate delta -1.32 (2 positive / 7 negative,
p 0.07): like every other arm, it does not beat its seed. Fixation signature:
in-iteration repair similarity to the gated code 0.04 (C2 0.96, A5 0.94);
mean consecutive code similarity 0.72 (C2 0.89, A5 0.92). Re-seeding removes
the anchoring and the collapse with it, and adds no coverage.

**Mechanism, strengthened and corrected.** The mechanism note's two-path
table classified the path by the next edit instruction, so three cases where
the loop fell back to its last WORKING generator after a build rejection or
mid-run error were counted as in-place. Classified by what the next prompt
shows, pooled C2+A5 over 60 replicates: in-place (failed code shown) 21
cases, 2 recovered, similarity 0.98; fallback refine 3, 2 recovered; re-seed
9, 7 recovered, similarity 0.07 (0.02-0.11). Correction section appended to
paper/mechanism-note.md. The pattern replicates under the oracle (tomlc99
C3s: in-place 1 of 10 recovered at 1.00; re-seed 2 of 2). In-iteration
repairs resubmit near-identical code (0.96-1.00) in every in-place arm.

**Deviations from the registered design, disclosed.** C3n was not run; C3s
was run on tomlc99 only (not on all three targets); both closing cells ran as
blocks after phases 1a/1b rather than interleaved, so provider drift is not
orthogonal to them (the served id was constant). C2R is a follow-up
condition outside the confirmatory family. The Holm family on tomlc99 is
{H1, H2s}. Docker, the AFL++ reference row, bug campaigns (RQ4), M2 and
Stage 2 were not run.

**Network outages during C2R.** This machine was on a phone hotspot (resolver
172.20.10.1); two DNS outages (about 16:00-16:04 and 16:27-16:31 UTC) failed
reps 5, 6 and 7. The driver's one retry also failed each time (DNS still
down); following the D25 precedent the batch was resumed once DNS was stable
and the three runs completed. The manifest keeps all 5 failed rows. Two
failed attempts had spent tokens before the outage (rep 5, about 1 call; rep
6's first rerun, about 4 calls) and were discarded as partial runs per the
registered rule; their token records were deleted with the run directories,
so their cost is estimated from the log at the batch's 0.0045 USD per call:
about 0.03 USD. No outage touched a completed run.

**Spend.** Recorded (per-run final.json at .env prices): phases 1a/1b 1.546,
C3s 0.414, C2R 0.233; Stage 1 total 2.193 USD, plus about 0.03 USD in
discarded partial attempts, of the 4.00 ceiling (10.00 hard cap). Actual
spend is reconciled against the provider dashboard by the user.

## D28 — The registered family completed for the journal submission; the result is heterogeneous, and the development target's steered arms are all one degenerate loop

**Why.** The user set a three-day journal deadline (2026-09-14 to 16) and
reopened spend. The cheapest additions that answer the most predictable
reviewer objections were run first: C3s on the two targets it was missing
(json-parser, parson), C3n on all three (completing the registered
confirmatory family {H1, H2s, H2n} on every target), and C2' on tomlc99 (a
second target for the mechanism's intervention). Then, CPU only: RQ3 (proxy
score vs measured coverage over every loop-internal strategy), RQ4
(30-minute ground-truth bug campaigns for every registered arm's finals),
the author-failure taxonomy, the design's sensitivity, and the cost table.

**Runs.** 60 live runs in three batches (day1a-c3s 20, day1b-c2r-toml 10,
day1c-c3n 30), every call served `deepseek-flash`, 0 backstop hits. One DNS
blip on the phone hotspot failed tomlc99 C3n-rep9 twice at its first API
call (no tokens); the overnight chain resumed the batch and it completed.
Spend: day1a 0.541, day1b 0.289, day1c 0.774 USD. All 120 registered Stage 1
runs are now done, plus 20 C2' follow-ups; 140 runs, 3.798 USD in total.

**Measurement.** Every final, seed, and the last working iteration where
it differs from the final, at 10^4 inputs x 20 draw seeds (2 560 new cells,
eval/matrix/day1.jsonl). For json-parser C3s-rep9 and rep10 no iteration
passed the drawability probe, so the matrix skipped their seed condition;
`eval/merge_fill.py` writes 20 explicit failed rows for such seeds (scored
0, the registered minimum) rather than dropping the replicate from the
paired delta.

**Provenance defect found while checking the oracle runs.** When an
iteration records a crash, agent.py's triage branch rewrites
`iter-N/stats.json` with a shorter dict that drops `coverage_in_loop`,
`proxy_score` and `summary_shown_to_model`. On json-parser every iteration
sees a crash (finding #1), so those fields are missing from every
json-parser iteration of every arm. The loop's behaviour was unaffected (it
steers on the live value; the surviving `score` field equals the coverage
under the C3 arms and the proxy otherwise) and the `summary` survives, so
RQ3 recomputes the proxy score from it. Verified by calling the in-loop
measurement directly on json-parser. Not fixed during the study (design
frozen); listed for the follow-up.

**Result, primary outcome (eval/matrix/full_report.md).** A12 with
bootstrap 95% CI; Holm within target over the three members.

| target | H1 C2 vs A5 | H2s C3s vs C2 | H2n C3n vs C2 |
|---|---|---|---|
| json-parser | 0.36 [0.14, 0.63] | 0.36 [0.11, 0.62] | 0.36 [0.12, 0.64] |
| parson | 0.59 [0.32, 0.84] | 0.76 [0.52, 0.96], p 0.044, Holm 0.13 | 0.33 [0.09, 0.59] |
| tomlc99 | 0.39 [0.14, 0.66] | 0.60 [0.35, 0.86] | 0.47 [0.21, 0.74] |

Nothing survives Holm. One cell is a detectable effect before correction:
on parson the coverage-scalar oracle beats its own seed (+1.59, 8 of 10 up,
sign-flip p 0.008), the proxy (A12 0.76) and no steering (A12 0.87 [0.68,
1.00], p 0.004). On the same target the named-function variant does not
(delta −0.16; A12 0.09 [0.00, 0.26] against C3s, exploratory): telling the
model which functions to cover did worse than telling it the number. On
tomlc99 every arm is null. This is the pre-registration's fourth outcome,
"mixed across targets, reported per target; heterogeneity is a finding",
and it replaces the D27 framing "no synthesis-time feedback moves it",
which was true of the cells run at that point.

**The development target's steered arms are one degenerate loop.** On
json-parser the default build aborts on every object input (finding #1), and
agent.py's crash branch takes priority over the signal: the next edit is
"intensify near crash" whenever the iteration saw a crash, `best` is
overwritten every iteration (`new_crash or sc > best_score`), and the
regression check requires `not new_crash`. Branch-fired histogram
(refinement instructions, iterations 2 to 5):

| target | C2 | C3s | C3n | C2R | A5 |
|---|---|---|---|---|---|
| json-parser | intensify_near_crash 31, fix 9 | intensify 30, fix 8, reseed 2 | intensify 36, reseed 4 | intensify 33, reseed 4, fix 2 | improve 35, raise_acc 3 |
| parson | broaden 16, nesting 12, revert 8, fix 4 | increase_branch_coverage 39, fix 1 | cover_function 39, reseed 1 | (not run) | improve 40 |
| tomlc99 | production 21, fix 8, reseed 5, revert 5 | increase_branch_coverage 27, fix 10, reseed 2, revert 1 | cover_function 27, revert 9, reseed 2, fix 2 | production 31, revert 4, reseed 3, nesting 2 | improve 38, reseed 2 |

On json-parser no steered arm ever rolled back (0 of 10 replicates in each
of C2, C3s, C3n) and the final is the last non-gated iteration in 8 to 10
of 10; on parson and tomlc99 C2 rolled back in 6 and 4 replicates and C3n
in 7. So the json-parser rows of the table compare four rounds of "mutate
structurally around the crashing input" against "improve", not signal
against signal; C3n's 0 up / 10 down there (p 0.002) is that loop, not the
function names. The pre-registration already reports json-parser separately
as the in-sample development target; every cross-target claim about signals
rests on parson and tomlc99 only, and the paper says so.

**C2'.** tomlc99: 0 of 10 collapsed (C2 1 of 10); A12 0.54 [0.28, 0.81] vs
C2; delta −1.41 (p 0.09). Over both C2' targets: 0 collapses in 20 runs vs
C2 3 in 20. Removes the failure mode on both targets; adds no coverage on
either.

**Taxonomy (eval/matrix/taxonomy.md).** 96 guard events over 140
replicates; largest classes: unparseable responses 17, strategy-vs-value
confusion 15, generic Python errors 14, the ExceptionGroup wrapper 13 (all
in C2), recursion/health-check 12 (10 in C3s). 33 of 140 seeds failed a
guard at iteration 1. tomlc99 46 events, json-parser 42, parson 8.

**RQ3 (eval/matrix/rq3_report.md).** 604 loop-internal strategies
measured (3 seeds x 1 000 inputs); Spearman rho, proxy vs primary outcome,
pooled: json-parser +0.08 [−0.06, +0.21], parson +0.37 [+0.23, +0.49],
tomlc99 +0.41 [+0.28, +0.52]; against in-loop coverage on the same 500
inputs +0.35, +0.17, +0.46; median within-replicate rho +0.10, 0.00, +0.35.
The proxy ranks generators roughly as coverage does and ranks one run's
iterations barely better than chance. One RQ3 cell was
recorded by hand: json-parser C3n-rep8 iteration 5 (the collapsed final,
which raises RecursionError on every example) at draw seed 2, after its
seeds 0 and 1 had each failed by DrawError after about 25 minutes of
exception churn and seed 2 had run 30 minutes; the row carries an
explanatory error string and scores 0 like the other two. No other cell
was touched.
**RQ4 (eval/matrix/rq4_report.md, 173 campaigns).** Triggered of 10: json-parser
issue 78 C2 3, A5 9, C3s 5, C3n 5 (C2 vs A5 Fisher p 0.02); issue 68-or-78
C2 4, A5 9, C3s 5, C3n 6; tomlc99 issue 50 C2 8, A5 9, C3s 9, C3n 9
(prereg predicted unreachable: WRONG; Grammarinator 1 of 1 at 10 969
inputs); recursion 0 everywhere (prereg right). Random text 0 of 1 on
every build in 3 to 7 M inputs; Grammarinator 0 on both json-parser bugs
in 5.6 to 10 M inputs (complete productions never truncate a literal).
cJSON CVE: baselines 0 of 1 each (LLM arms to follow). Two facts found while
checking the rows. (1) In 13 of 173 first-pass campaigns the positive
control itself timed out under the nine-worker load, campaign.py accepted
"timeout" as the bug's oracle signature, and the campaign then "triggered"
on the first load-induced timeout while the real crash signatures were
filed as "other". campaign.py now fails a control that times out; the 13
rows were dropped (first pass kept as eval/campaigns/rq4.first_pass.jsonl)
and rerun on four workers. The thousands of "timeout" entries among the
other signatures are the same load effect (5-second per-input limit) and
are reported as such. (2) json-parser's two bugs, both one-byte over-reads
at the end of the buffer inside json_parse_ex, normalise to the SAME crash
signature; the issue-78 pre-fix build contains only issue 78 (the issue-68
PoC is a clean reject there), but the issue-68 pre-fix build contains both
(the issue-78 PoC crashes it). The issue-78 row is therefore a single bug;
the issue-68 row measures either over-read and is reported as "issue 68 or
78". Every other crash signature seen in campaigns occurred on a pre-fix
source (old json-parser: a UBSan signed-integer overflow; old tomlc99: heap
over-reads in scan_string fixed upstream since); the pinned HEAD builds
produced none, so there are no new findings to triage.

**Sanity checks (plan E9).** Batch drift: seed-generator levels of the
day-1 batches against phases 1a/1b (identical seed prompt) give A12 0.43
to 0.61 with p > 0.15 on every target; no drift. Equal-time views
(eval/equal_time.py): every generator draws and runs its 10^4 inputs in
under five minutes, so the 5- and 30-minute views coincide with the
equal-n view; "run the seed longer" reduces to the curve's asymptote.
Random text (C0a) measured at 10^4 x 20 seeds on all three targets
(eval/matrix/fixed.jsonl): 26.4, 21.7, 17.1 AUC points; every healthy
LLM seed beats every random draw on every target (A12 1.00), so RQ1's
registered lower bound is established at 30 to 40 points.

**Sensitivity.** With ten replicates per arm and the healthy-replicate SD
(3.3, 2.2, 5.2 points), the registered test has 80% power at a shift of
4.5, 3.0 and 6.5 points (true A12 about 0.82). Effects in the lower half
of the registered "practical" band are not reliably detectable; every null
is "no detectable effect at this budget".

**Stage 2 and reference rows (day 2).** cJSON vendored as T5 (the plan's
v1.7.17 turned out to be the vulnerable release, found by the positive
control crashing the default build; pinned to v1.7.18 with v1.7.17 as the
CVE-2023-53154 bug build; 27 probes against Python json; 8 contract
tests). cJSON live batch (day2-cjson): 40 runs, all served deepseek-flash,
0 backstop hits, 0.835 USD, mean 4.1 min. The manifest keeps 93 failed
attempts, none of which spent tokens: 35 were HTTP 401s after the user
added an OpenAI key to .env under the name LLM_API_KEY, which the loop
prefers over DEEPSEEK_API_KEY (renamed to OPENAI_API_KEY; the loop never
saw the OpenAI key again); the rest were two DNS outages on the phone
hotspot, after which the batch was resumed under a driver stage that now
waits for name resolution and resumes up to eight times. One cJSON
generator (the C3n-rep2 final) draws its 10^4 inputs in 785 to 890 s, at
the edge of the protocol's 900 s draw limit: of its first eleven draw seeds
five succeeded and six timed out, and the remaining seeds took the same
two hours to measure. For about fifteen minutes nine of its cells had been
written by hand as timed out on the assumption that every seed would fail;
the per-seed outcomes showed a mixture, the rows were deleted and the
cells measured under the protocol. No hand-written cell remains in the
cJSON data. Result (eval/matrix/full_report.md, cjson): H1 A12 0.25
[0.06, 0.49], p 0.046, Holm 0.14, favouring no steering, 0.28 among usable
generators; H2s A12 0.78 [0.52, 0.98], p 0.49 (one collapse each side),
0.84 [0.60, 1.00], p 0.017 among usable; C3s vs A5 0.62 [0.35, 0.88], p
0.83; H2n 0.54. Collapses C2 1, C3s 1, A5 0, C3n 0. Deltas C2 -0.51 (p
0.039), A5 +1.35, C3s +1.15 (n 9), C3n -3.28 (n 8; rep2's final is the
slow generator above, 6 of 20 cells timed out, mean 48.0). Repair paths on
cJSON: C2 in place 0 of 4, re-seed 4 of 4; C3s in place 2 of 4, re-seed 1
of 4; C3n in place 2 of 2. cJSON's fixed references, RQ3 cells and
campaigns were not measured before the cutoff (below).
AFL++ reference row via the official
Docker image (no Homebrew on this Mac): afl-clang-fast -O2 -lm, no
sanitizers, afl-fuzz defaults, one seed per format; the final queue is
replayed through the study's coverage build with a raw-bytes path added to
coverage_curve (string path unchanged). Pipeline check: 60 s on json-parser
gave 174 queue entries at 1 122 exec/s and 65.4% reachable-region branch
coverage. The full row (4 targets x 5 runs x 1 h) did not run before the
cutoff (below). libexpat is
deferred to the revision. One-minute AFL smoke ran while the RQ4 campaigns
were in progress (load already about 58 on 11 cores from nine workers);
campaigns are time-budgeted, so machine load is a shared confound across
arms and is disclosed in threats.

**M2, the second model.** gpt-5-mini via the OpenAI API (served id
gpt-5-mini-2025-08-07 on the smoke call), arms C2, A5 and C3s on tomlc99,
ten replicates each, run names M2C2/M2A5/M2C3s so they sit beside the
DeepSeek runs. Deviation from the registered loop settings: the gpt-5
family accepts only its default temperature (a 0.7 request is rejected
with HTTP 400), so M2 runs at the model's default of 1.0; the client omits
the field under LLM_TEMPERATURE=default and records "default" per call.
Prices for the cost table: 0.25 USD per million input tokens and 2.00 per
million output tokens, standard tier, OpenAI developer docs read
2026-09-14; reasoning tokens are billed as output and are included in the
recorded completion counts. At the cutoff 18 of 30 M2 runs had completed
(6 per arm; 6 more had failed at a DNS drop at 01:00 UTC and were queued
for rerun) and none was measured. M2 is excluded from every table in the
submission (the taxonomy and cost tables were regenerated with ARMS
restricted to the five DeepSeek arms) and the runs stay in
runs/tomlc99/M2*/ for the revision. Spend so far about 1.4 USD of OpenAI
credit.

**Prereg amendment (dated 2026-09-14).** C3s on json-parser and parson,
and all C3n, ran as blocks after phases 1a and 1b rather than interleaved;
C2' is a follow-up outside the family; the Holm family per target is now
the full {H1, H2s, H2n}. Stage 2 targets, the AFL++ reference row and M2
are deferred to revision.

**Submission cutoff (2026-09-15, 01:05 UTC).** The deadline turned out to
be 2026-09-15 10:00 UTC, not the 16th. At that point the cJSON measurement
was complete (four arms, 1 680 rows, eval/matrix/day2.jsonl) and the M2
batch stood at 18 of 30. The overnight chain (M2 measurement, cJSON RQ3
cells, AFL++ row and replay, cJSON campaigns) could not finish in the nine
hours left, so the paper was frozen on the complete data: Stage 1 (140
runs) plus cJSON (40 runs), 180 runs and 4.63 USD. The chains were left
running at the user's request; whatever they produce goes into the
revision, not this submission. Excluded and disclosed in Section 4.6:
cJSON RQ1 references, RQ3 cells and campaigns; libexpat; AFL++; M2.

## D29 — Paper revised to a communication blueprint drawn from the base paper (2026-09-15)

**Why.** The user asked for the paper to reach the base paper's level of
organisation and flow without copying it. A style study of Vikram and
Padhye (paper/base-paper-style.md), a gap analysis of our draft
(paper/style-gap-analysis.md) and a revision plan with two decisions
(paper/revision-plan.md) preceded the rewrite.

**Decisions.** Motivating example = the collapsed proxy replicate parson
C2-rep6 (numbers read from runs/parson/C2-rep6/iter-*/; scratch note kept
with file paths). Tables 3 to 6 of the old draft enter the paper as
generated tables (eval/tables.py T3 to T6, inlined by
eval/assemble_paper.py in order of appearance, after the hand-written
configuration table). A loop schematic (paper/figures/f0_loop) is new.
Canonical arm names (C2 proxy, A5 no steering, C3s coverage, C3n
coverage+names, C2′ re-seed repair) are used identically in prose, tables
and figures. The registered title is kept; a finding-bearing display title
is proposed to the author separately and, if adopted, is disclosed in 4.1
as a presentation change.

**What changed in the text.** Introduction rebuilt as a funnel with an
assumption-shaped gap, a motivating example and a contributions
paragraph; background split into three purposeful subsections; approach
opens with the differing axis and explains the proxy at three levels with
one recorded iteration (parson C2-rep2, iteration 1 to 2); a
design-decision subsection; RQ list in 4.6; every results subsection in
question, measurement, figure, aggregate, spread, exception, mechanism,
answer form with a closing Finding; bridge from 5.7 to Section 6;
discussion led by the broader pattern; conclusion shortened; related work
gains the LLM-property-based-testing and evaluation-methodology themes.
Mandatory fixes: internal note removed from References, G2Fuzz entry
completed, RQ2 labelled, "does not claim" paragraph rewritten, artifact
URL placeholder pending the user. No number was written that was not read
from a file in the session; the DOIs added from standard references
(Claessen and Hughes, Arcuri and Briand, Vargha and Delaney, Fuzz4All)
resolve at doi.org and the author checks their titles.

**Numbers.** 15.4k words, 36 pages in svjour3; mean sentence length 34 to
27 words; sentences over 40 words 77 of 239 to 67 of 460.
