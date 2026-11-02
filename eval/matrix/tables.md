# Generated tables

## T1. Targets

| target | source | lines | functions | parse-reachable functions | grammar (grammars-v4) | ground-truth bug builds | role |
|-------|----------|-----|--------|----------|--------------|--------------|-----------|
| json-parser | json.c | 1057 | 10 | 9 | JSON.g4 | issue68, issue78 | development (in-sample) |
| parson | parson.c | 2486 | 144 | 40 | JSON.g4 | none | held out |
| cjson | cJSON.c | 3143 | 112 | 13 | JSON.g4 | cve-2023-53154 | held out (Stage 2) |
| tomlc99 | toml.c | 2392 | 82 | 53 | TomlLexer.g4, TomlParser.g4 | issue50, recursion | held out |

## T2. Final-generator level and refinement delta per target and arm

Primary outcome auc_branch_reach (10^4 inputs x 20 draw seeds per replicate; failed cells and collapsed finals score 0). Mean ± 95% CI over ten replicates (median); coll. = collapsed replicates (final unusable, scored 0); last working = the last working iteration's level where it differs from the final (n = replicates where it differs). Δ = final − seed per replicate, exact sign-flip test; up / down / zero count the replicates entering the test, and sum to ten minus seed failed; a collapsed replicate whose seed also failed enters as a zero delta, and one whose seed drew enters as a negative delta. Replicates whose seed generator failed but whose final works are excluded from Δ and counted under seed failed. json-parser is the development target (Section 5.1).

| target | arm | final | coll. | Δ final − seed | up / down / zero | sign-flip p | seed failed | last working |
|--------|--------------|-----------------|-----|--------------|-------|--------|-------|-----------|
| parson | C2 proxy | 60.9 ± 15.4 (67.1) | 1 | +0.89 ± 0.50 | 7 / 1 / 2 | 0.016 | 0 | - |
| parson | A5 no steering | 66.3 ± 1.6 (66.7) | 0 | +0.54 ± 0.75 | 7 / 2 / 1 | 0.160 | 0 | - |
| parson | C3s coverage | 69.1 ± 1.1 (69.4) | 0 | +1.59 ± 0.86 | 8 / 2 / 0 | 0.008 | 0 | 68.6 (n 1) |
| parson | C3n coverage+names | 66.0 ± 1.3 (65.8) | 0 | -0.16 ± 1.48 | 5 / 5 / 0 | 0.797 | 0 | - |
| parson | C2 proxy (gpt-5-mini) | 62.9 ± 1.2 (62.9) | 0 | +0.67 ± 1.38 | 4 / 4 / 1 | 0.336 | 1 | 62.1 (n 5) |
| parson | A5 no steering (gpt-5-mini) | 60.2 ± 2.2 (60.3) | 0 | -1.06 ± 0.76 | 1 / 8 / 1 | 0.008 | 0 | - |
| parson | C3s coverage (gpt-5-mini) | 62.0 ± 1.1 (62.2) | 0 | -0.12 ± 0.79 | 5 / 4 / 1 | 0.754 | 0 | - |
| tomlc99 | C2 proxy | 52.9 ± 13.9 (57.4) | 1 | -0.01 ± 1.10 | 2 / 4 / 3 | 1.000 | 1 | - |
| tomlc99 | A5 no steering | 60.2 ± 3.4 (59.8) | 0 | +1.80 ± 2.33 | 6 / 3 / 0 | 0.121 | 1 | - |
| tomlc99 | C3s coverage | 55.1 ± 14.1 (60.6) | 1 | +0.22 ± 0.61 | 5 / 1 / 4 | 0.438 | 0 | 50.7 (n 6) |
| tomlc99 | C3n coverage+names | 57.4 ± 3.7 (58.5) | 0 | -0.70 ± 0.96 | 0 / 3 / 6 | 0.250 | 1 | 51.2 (n 4) |
| tomlc99 | C2' re-seed repair | 59.3 ± 2.4 (60.3) | 0 | -1.41 ± 1.64 | 1 / 7 / 2 | 0.086 | 0 | 60.2 (n 3) |
| tomlc99 | C2 proxy (gpt-5-mini) | 51.8 ± 3.1 (51.0) | 0 | +0.51 ± 0.52 | 6 / 1 / 2 | 0.047 | 1 | 38.5 (n 3) |
| tomlc99 | A5 no steering (gpt-5-mini) | 52.5 ± 3.9 (50.6) | 0 | -0.64 ± 2.08 | 3 / 4 / 0 | 0.516 | 3 | - |
| tomlc99 | C3s coverage (gpt-5-mini) | 38.8 ± 17.1 (49.9) | 2 | -0.81 ± 1.88 | 3 / 4 / 3 | 0.422 | 0 | 38.3 (n 4) |
| cjson | C2 proxy | 61.8 ± 15.6 (68.3) | 1 | -0.51 ± 0.46 | 2 / 7 / 1 | 0.039 | 0 | 67.1 (n 1) |
| cjson | A5 no steering | 70.3 ± 1.6 (70.1) | 0 | +1.35 ± 1.69 | 6 / 3 / 1 | 0.113 | 0 | - |
| cjson | C3s coverage | 64.2 ± 16.2 (72.2) | 1 | +1.15 ± 2.10 | 6 / 2 / 1 | 0.234 | 1 | 71.7 (n 2) |
| cjson | C3n coverage+names | 66.6 ± 5.1 (68.8) | 0 | -3.28 ± 6.23 | 2 / 5 / 1 | 0.156 | 2 | 60.9 (n 1) |
| json-parser | C2 proxy | 51.0 ± 19.3 (63.9) | 2 | -1.02 ± 0.81 | 2 / 6 / 2 | 0.031 | 0 | - |
| json-parser | A5 no steering | 63.7 ± 2.8 (64.6) | 0 | +0.15 ± 1.16 | 6 / 4 / 0 | 0.768 | 0 | - |
| json-parser | C3s coverage | 48.8 ± 18.7 (59.4) | 2 | -1.60 ± 1.70 | 2 / 6 / 2 | 0.062 | 0 | - |
| json-parser | C3n coverage+names | 54.9 ± 14.0 (61.5) | 1 | -9.20 ± 13.62 | 0 / 10 / 0 | 0.002 | 0 | - |
| json-parser | C2' re-seed repair | 63.9 ± 1.3 (64.4) | 0 | -1.32 ± 1.40 | 2 / 7 / 1 | 0.074 | 0 | - |

## T3. RQ1: the LLM seed generators against random text and Grammarinator on the identical grammar

Primary outcome at 10^4 inputs, draw seeds 0..19. Fixed generators: mean over the 20 draw seeds. LLM seed: mean over the 20 seed generators of C2 and A5 (identical seed prompt), a generator whose every cell failed scoring 0; healthy = generators that drew on at least one seed. A12 = P(a healthy LLM seed generator's mean exceeds a Grammarinator input set's value) against the stronger Grammarinator variant, bootstrap 95% CI.

| target | random text | Grammarinator defaults | Grammarinator depth-matched | LLM seed (20) | healthy | A12 healthy seeds vs stronger Grammarinator |
|-----------|--------|----------|-----------|----------|------|----------------------|
| parson | 21.7 | 61.6 | 64.8 | 62.9 | 19 of 20 | 0.70 [0.51, 0.87] |
| tomlc99 | 17.1 | 65.1 | - | 49.6 | 17 of 20 | 0.13 [0.02, 0.28] |
| cjson | 36.0 | 61.6 | 65.0 | 65.6 | 19 of 20 | 0.94 [0.87, 0.99] |
| json-parser | 26.4 | 61.1 | 63.9 | 57.8 | 18 of 20 | 0.62 [0.43, 0.80] |

## T4. RQ5: guard events by cause class and arm

121 events over 180 completed replicates (four targets), coded from the recorded exception and rejection text by ordered regular expressions, first match wins; iterations without an event are not listed. Arm codes as in Table 1.

| cause | C2 | A5 | C3s | C3n | C2' | total |
|------------------------------|-----|-----|-----|-----|-----|------|
| syntax / unparseable response | 5 | 3 | 10 | 5 | 1 | 24 |
| strategy/value confusion (two-level semantics) | 12 | 2 | 7 | 3 | 0 | 24 |
| generic Python error (TypeError/ValueError/KeyError/NameError) | 5 | 3 | 4 | 2 | 4 | 18 |
| ExceptionGroup wrapper (sub-exceptions hidden) | 13 | 0 | 0 | 0 | 0 | 13 |
| recursion / Hypothesis health check | 1 | 0 | 10 | 2 | 0 | 13 |
| hallucinated Hypothesis API | 5 | 0 | 7 | 0 | 1 | 13 |
| low acceptance (valid code, invalid outputs) | 0 | 5 | 0 | 0 | 1 | 6 |
| wrong alphabet / characters argument | 0 | 0 | 4 | 0 | 1 | 5 |
| invalid strategy arguments | 1 | 0 | 1 | 1 | 0 | 3 |
| disallowed import or name (screen) | 0 | 0 | 1 | 0 | 1 | 2 |

## T5. Which refinement instruction the loop issued, iterations 2 to 5, per target and arm

Counts over ten replicates x four refinements = 40 per cell, read from each run's evolution log. crash = "mutate structurally around the crashing input" (issued whenever the previous iteration saw a new crash signature, in every arm); signal = the arm's own edit (C2: add or up-weight a production, generate deeper, broaden, fix a feature; C3s: increase branch coverage; C3n: cover function F); improve = "make it a better fuzzer" (A5's only edit); revert = roll back the last edit; repair = the previous iteration was gated or its build was rejected, so the next prompt is a repair or a re-seed, not a refinement.

| target | arm | crash | signal | improve | revert | repair |
|-----------|--------------------|-----|------|-------|------|------|
| parson | C2 proxy | 0 | 28 | 0 | 8 | 4 |
| parson | A5 no steering | 0 | 0 | 40 | 0 | 0 |
| parson | C3s coverage | 0 | 39 | 0 | 0 | 1 |
| parson | C3n coverage+names | 0 | 39 | 0 | 0 | 1 |
| tomlc99 | C2 proxy | 0 | 22 | 0 | 5 | 13 |
| tomlc99 | A5 no steering | 0 | 0 | 38 | 0 | 2 |
| tomlc99 | C3s coverage | 0 | 27 | 0 | 1 | 12 |
| tomlc99 | C3n coverage+names | 0 | 27 | 0 | 9 | 4 |
| tomlc99 | C2' re-seed repair | 0 | 33 | 0 | 4 | 3 |
| cjson | C2 proxy | 0 | 32 | 0 | 0 | 8 |
| cjson | A5 no steering | 0 | 0 | 38 | 0 | 2 |
| cjson | C3s coverage | 0 | 32 | 0 | 0 | 8 |
| cjson | C3n coverage+names | 0 | 38 | 0 | 0 | 2 |
| json-parser | C2 proxy | 31 | 0 | 0 | 0 | 9 |
| json-parser | A5 no steering | 0 | 0 | 35 | 0 | 5 |
| json-parser | C3s coverage | 30 | 0 | 0 | 0 | 10 |
| json-parser | C3n coverage+names | 36 | 0 | 0 | 0 | 4 |
| json-parser | C2' re-seed repair | 33 | 0 | 0 | 1 | 6 |

## T6. Synthesis cost per run, by target and served model

Mean over every completed run; API charges and synthesis wall clock only. deepseek-flash rows pool the arms C2, A5, C3s, C3n and, on json-parser and tomlc99, C2' (180 runs); gpt-5-mini rows pool C2, A5 and C3s (60 runs). Measurement (10 200 cells), the bug campaigns and the AFL++ runs are local compute and are not costed; the hand work per target is described in Section 3.3. The per-arm table is in the artifact (eval/matrix/cost_table.md).

| target | served model | runs | LLM calls | tokens in | tokens out | USD per run | wall minutes |
|-----------|------|------|------|--------|--------|--------|--------|
| parson | deepseek-flash | 40 | 5.3 | 15496 | 16388 | 0.022 | 4.0 |
| parson | gpt-5-mini | 30 | 5.2 | 12932 | 20392 | 0.044 | 5.6 |
| tomlc99 | deepseek-flash | 50 | 5.6 | 24180 | 24103 | 0.033 | 3.9 |
| tomlc99 | gpt-5-mini | 30 | 5.8 | 22864 | 33180 | 0.072 | 11.8 |
| cjson | deepseek-flash | 40 | 5.5 | 14424 | 15444 | 0.021 | 4.2 |
| json-parser | deepseek-flash | 50 | 5.7 | 17451 | 18576 | 0.025 | 5.5 |
| all | both | 240 | | | | 0.034 (total 8.116) | 5.5 |

