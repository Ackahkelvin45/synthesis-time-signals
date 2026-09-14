# RQ1: LLM seed (C1) vs Grammarinator on the identical grammar (C0b)

Secondary, descriptive (pre-registration section 2). Primary outcome `auc_branch_reach`, 10^4 inputs, draw seeds 0..19; failed cells score 0. C1 = the 20 seed generators per target (the seeds of C2 rep1-10 and A5 rep1-10; identical seed prompt). C0b = Grammarinator 26.1 (pinned, eval/grammarinator.json). Sources `eval/matrix/stage1.jsonl`, `eval/matrix/fixed.jsonl`.

Reading guide. The generator is the unit for an authorship claim: the leading statistic is A12 of the 20 seed generators' means against Grammarinator's 20 draw values (P(a random LLM seed beats a random Grammarinator input set)), with a percentile-bootstrap CI and the registered bands. The plan-E7 form pairs by draw seed and averages the 20 generators within each seed; its CI carries draw noise only, not authoring variance, so its p-values overstate certainty and are shown for completeness. json-parser and parson share the JSON grammar and therefore receive byte-identical Grammarinator input sets; the depth-matched weight was calibrated on the json-parser pilot's seed (D21).

## json-parser

- Grammarinator defaults (C0b): 61.1 ± 0.6 (median 61.1, range 58.6-63.6) over 20 draw seeds
- Grammarinator depth-matched (C0b): 63.9 ± 0.8 (median 64.3, range 60.1-66.5) over 20 draw seeds
- random text (C0a): 26.4 ± 0.7 (median 26.1, range 23.8-29.3) over 20 draw seeds
- LLM seed (C1): 57.8 ± 9.3 (median 65.0, range 0.0-66.8) over 20 generators; 2 seed generator(s) whose every cell failed, scored 0: C2-rep10, C2-rep7 (all also collapsed at the final)
- context, C2 loop finals: 51.0 ± 19.3 (median 63.9, range 0.0-66.3) over 10 replicates; vs the stronger Grammarinator variant (grammarinator-deep): A12(C2 finals, C0b) = 0.41 [0.18, 0.66] → small, favouring C0b
- context, A5 loop finals: 63.7 ± 2.8 (median 64.6, range 54.7-67.3) over 10 replicates; vs the stronger Grammarinator variant (grammarinator-deep): A12(A5 finals, C0b) = 0.56 [0.30, 0.80] → small, favouring A5
- comparisons:
  - C1 vs Grammarinator defaults: A12(C1 generators, C0b draws) = 0.75 [0.56, 0.91] → practical, favouring C1; 16 of 20 seed generators above the C0b mean (61.1); plan-E7 form (paired by draw seed): C1 − C0b = -3.30 ± 0.63, sign-flip p = 0.0000
  - C1 vs Grammarinator defaults, failed seeds excluded (n = 18): A12(C1 generators, C0b draws) = 0.83 [0.66, 0.97] → practical, favouring C1; 16 of 18 seed generators above the C0b mean (61.1); plan-E7 form (paired by draw seed): C1 − C0b = +3.12 ± 0.63, sign-flip p = 0.0000
  - C1 vs Grammarinator depth-matched: A12(C1 generators, C0b draws) = 0.56 [0.37, 0.75] → negligible; 13 of 20 seed generators above the C0b mean (63.9); plan-E7 form (paired by draw seed): C1 − C0b = -6.16 ± 0.81, sign-flip p = 0.0000
  - C1 vs Grammarinator depth-matched, failed seeds excluded (n = 18): A12(C1 generators, C0b draws) = 0.62 [0.43, 0.80] → small, favouring C1; 13 of 18 seed generators above the C0b mean (63.9); plan-E7 form (paired by draw seed): C1 − C0b = +0.26 ± 0.81, sign-flip p = 0.5124
  - C1 vs random text: A12(C1 generators, C0a draws) = 0.90 [0.75, 1.00] → practical, favouring C1; 18 of 20 seed generators above the C0a mean (26.4); plan-E7 form (paired by draw seed): C1 − C0a = +31.36 ± 0.74, sign-flip p = 0.0000
  - C1 vs random text, failed seeds excluded (n = 18): A12(C1 generators, C0a draws) = 1.00 [1.00, 1.00] → practical, favouring C1; 18 of 18 seed generators above the C0a mean (26.4); plan-E7 form (paired by draw seed): C1 − C0a = +37.77 ± 0.74, sign-flip p = 0.0000
- exploratory, region AUC (`auc_region_reach`): C1 mean 59.3 (median 66.9); grammarinator 55.7; grammarinator-deep 58.4; random 32.5

## parson

- Grammarinator defaults (C0b): 61.6 ± 0.8 (median 61.6, range 57.9-64.3) over 20 draw seeds
- Grammarinator depth-matched (C0b): 64.8 ± 0.8 (median 65.1, range 61.2-67.2) over 20 draw seeds
- random text (C0a): 21.7 ± 0.8 (median 21.6, range 18.0-24.7) over 20 draw seeds
- LLM seed (C1): 62.9 ± 7.0 (median 66.3, range 0.0-69.4) over 20 generators; 1 seed generator(s) whose every cell failed, scored 0: C2-rep6 (all also collapsed at the final)
- context, C2 loop finals: 60.9 ± 15.4 (median 67.1, range 0.0-70.5) over 10 replicates; vs the stronger Grammarinator variant (grammarinator-deep): A12(C2 finals, C0b) = 0.80 [0.53, 0.99] → practical, favouring C2
- context, A5 loop finals: 66.3 ± 1.6 (median 66.7, range 63.1-70.1) over 10 replicates; vs the stronger Grammarinator variant (grammarinator-deep): A12(A5 finals, C0b) = 0.71 [0.45, 0.92] → practical, favouring A5
- comparisons:
  - C1 vs Grammarinator defaults: A12(C1 generators, C0b draws) = 0.92 [0.80, 0.99] → practical, favouring C1; 19 of 20 seed generators above the C0b mean (61.6); plan-E7 form (paired by draw seed): C1 − C0b = +1.33 ± 0.77, sign-flip p = 0.0014
  - C1 vs Grammarinator defaults, failed seeds excluded (n = 19): A12(C1 generators, C0b draws) = 0.97 [0.91, 1.00] → practical, favouring C1; 19 of 19 seed generators above the C0b mean (61.6); plan-E7 form (paired by draw seed): C1 − C0b = +4.64 ± 0.77, sign-flip p = 0.0000
  - C1 vs Grammarinator depth-matched: A12(C1 generators, C0b draws) = 0.67 [0.48, 0.83] → practical, favouring C1; 14 of 20 seed generators above the C0b mean (64.8); plan-E7 form (paired by draw seed): C1 − C0b = -1.86 ± 0.81, sign-flip p = 0.0003
  - C1 vs Grammarinator depth-matched, failed seeds excluded (n = 19): A12(C1 generators, C0b draws) = 0.70 [0.51, 0.87] → practical, favouring C1; 14 of 19 seed generators above the C0b mean (64.8); plan-E7 form (paired by draw seed): C1 − C0b = +1.45 ± 0.82, sign-flip p = 0.0008
  - C1 vs random text: A12(C1 generators, C0a draws) = 0.95 [0.85, 1.00] → practical, favouring C1; 19 of 20 seed generators above the C0a mean (21.7); plan-E7 form (paired by draw seed): C1 − C0a = +41.18 ± 0.81, sign-flip p = 0.0000
  - C1 vs random text, failed seeds excluded (n = 19): A12(C1 generators, C0a draws) = 1.00 [1.00, 1.00] → practical, favouring C1; 19 of 19 seed generators above the C0a mean (21.7); plan-E7 form (paired by draw seed): C1 − C0a = +44.49 ± 0.82, sign-flip p = 0.0000
- exploratory, region AUC (`auc_region_reach`): C1 mean 73.5 (median 77.7); grammarinator 72.5; grammarinator-deep 76.3; random 24.3

## tomlc99

- Grammarinator defaults (C0b): 65.1 ± 0.9 (median 65.2, range 59.7-67.8) over 20 draw seeds
- Grammarinator depth-matched: not measured; the pinned TOML variant is identical to defaults (deep_weight 1.0, no single recursive value rule; eval/grammarinator.json)
- random text (C0a): 17.1 ± 0.4 (median 16.8, range 15.6-19.0) over 20 draw seeds
- LLM seed (C1): 49.6 ± 10.2 (median 56.9, range 0.0-66.6) over 20 generators; 3 seed generator(s) whose every cell failed, scored 0: A5-rep10, C2-rep3, C2-rep9 (of these, A5-rep10, C2-rep9 ended with a working final, so their final-minus-seed delta is inflated by the whole final level; the rest also collapsed at the final, delta 0)
- context, C2 loop finals: 52.9 ± 13.9 (median 57.4, range 0.0-65.4) over 10 replicates; vs the stronger Grammarinator variant (grammarinator): A12(C2 finals, C0b) = 0.13 [0.01, 0.30] → practical, favouring C0b
- context, A5 loop finals: 60.2 ± 3.4 (median 59.8, range 50.6-65.4) over 10 replicates; vs the stronger Grammarinator variant (grammarinator): A12(A5 finals, C0b) = 0.14 [0.03, 0.30] → practical, favouring C0b
- comparisons:
  - C1 vs Grammarinator defaults: A12(C1 generators, C0b draws) = 0.11 [0.01, 0.23] → practical, favouring C0b; 2 of 20 seed generators above the C0b mean (65.1); plan-E7 form (paired by draw seed): C1 − C0b = -15.54 ± 0.87, sign-flip p = 0.0000
  - C1 vs Grammarinator defaults, failed seeds excluded (n = 17): A12(C1 generators, C0b draws) = 0.13 [0.02, 0.28] → practical, favouring C0b; 2 of 17 seed generators above the C0b mean (65.1); plan-E7 form (paired by draw seed): C1 − C0b = -6.79 ± 0.86, sign-flip p = 0.0000
  - C1 vs random text: A12(C1 generators, C0a draws) = 0.85 [0.70, 1.00] → practical, favouring C1; 17 of 20 seed generators above the C0a mean (17.1); plan-E7 form (paired by draw seed): C1 − C0a = +32.49 ± 0.43, sign-flip p = 0.0000
  - C1 vs random text, failed seeds excluded (n = 17): A12(C1 generators, C0a draws) = 1.00 [1.00, 1.00] → practical, favouring C1; 17 of 17 seed generators above the C0a mean (17.1); plan-E7 form (paired by draw seed): C1 − C0a = +41.24 ± 0.43, sign-flip p = 0.0000
- exploratory, region AUC (`auc_region_reach`): C1 mean 51.5 (median 59.3); grammarinator 67.2; random 17.7
