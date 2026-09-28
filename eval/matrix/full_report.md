# Stage 1 full report (registered structure, every arm)

Primary outcome `auc_branch_reach` (10^4 inputs x 20 fresh draw seeds per replicate; failed cells scored 0, so a collapsed replicate scores 0 and a seed generator that cannot draw scores 0). Unit = loop replicate. Bands: A12 >= 0.64 (or <= 0.36) practical; 0.56-0.64 (0.36-0.44) small; otherwise negligible. Confirmatory family per target: H1, H2s, H2n (Holm over the members run). C2R is a follow-up outside the family. Sources: eval/matrix/stage1.jsonl, eval/matrix/stage1c.jsonl, eval/matrix/day1.jsonl, eval/matrix/day2.jsonl.

## json-parser

### Per arm

- C2 final: 51.0 ± 19.3 (median 63.9); replicate means 63.6, 64.7, 58.3, 61.7, 65.5, 65.2, 0.0, 64.2, 66.3, 0.0
- C2: Δ(final − seed) = r1:-1.2, r2:-2.1, r3:-2.8, r4:-1.8, r5:+0.3, r6:-1.0, r7:+0.0, r8:-2.1, r9:+0.3, r10:+0.0; mean -1.02 ± 0.81; 2 up / 6 down / 2 zero of 10; sign-flip p = 0.0312
- C2 collapsed (final unusable, scored 0): 2 of 10 (rep7, rep10)
- A5 final: 63.7 ± 2.8 (median 64.6); replicate means 64.9, 66.8, 54.7, 59.6, 65.0, 67.3, 67.3, 64.3, 63.8, 63.1
- A5: Δ(final − seed) = r1:-0.3, r2:+0.4, r3:-1.4, r4:+0.2, r5:+0.4, r6:+1.6, r7:+0.5, r8:+3.2, r9:-0.3, r10:-2.9; mean +0.15 ± 1.16; 6 up / 4 down / 0 zero of 10; sign-flip p = 0.7676
- A5 collapsed (final unusable, scored 0): 0 of 10
- C3s final: 48.8 ± 18.7 (median 59.4); replicate means 68.0, 53.2, 57.8, 63.1, 64.1, 61.0, 56.5, 64.7, 0.0, 0.0
- C3s: Δ(final − seed) = r1:+0.7, r2:-5.7, r3:-3.2, r4:-1.2, r5:-1.2, r6:+0.7, r7:-5.4, r8:-0.7, r9:+0.0, r10:+0.0; mean -1.60 ± 1.70; 2 up / 6 down / 2 zero of 10; sign-flip p = 0.0625
- C3s collapsed (final unusable, scored 0): 2 of 10 (rep9, rep10)
- C3n final: 54.9 ± 14.0 (median 61.5); replicate means 62.6, 65.2, 59.1, 62.5, 64.2, 56.1, 63.6, 0.0, 60.4, 55.2
- C3n: Δ(final − seed) = r1:-0.7, r2:-0.1, r3:-5.1, r4:-3.1, r5:-1.4, r6:-2.8, r7:-2.9, r8:-63.1, r9:-6.3, r10:-6.5; mean -9.20 ± 13.62; 0 up / 10 down / 0 zero of 10; sign-flip p = 0.0020
- C3n collapsed (final unusable, scored 0): 1 of 10 (rep8)
- C2R final: 63.9 ± 1.3 (median 64.4); replicate means 64.2, 64.7, 60.8, 65.2, 63.5, 66.0, 62.6, 61.2, 65.1, 66.0
- C2R: Δ(final − seed) = r1:-1.2, r2:+0.0, r3:-3.6, r4:-1.8, r5:-1.3, r6:+1.9, r7:-3.9, r8:-3.7, r9:-0.4, r10:+0.7; mean -1.32 ± 1.40; 2 up / 7 down / 1 zero of 10; sign-flip p = 0.0742
- C2R collapsed (final unusable, scored 0): 0 of 10

### Confirmatory family

- H1: C2 vs A5: Δmean (C2 − A5) = -12.73; A12 = 0.36 [0.14, 0.63] → practical, favouring A5; permutation p = 0.2375; n = 10 vs 10; Holm-adjusted p = 0.7126
- H2s: C3s vs C2: Δmean (C3s − C2) = -2.11; A12 = 0.36 [0.11, 0.62] → practical, favouring C2; permutation p = 0.6714; n = 10 vs 10; Holm-adjusted p = 1.0000
- H2n: C3n vs C2: Δmean (C3n − C2) = +3.94; A12 = 0.36 [0.12, 0.63] → practical, favouring C2; permutation p = 0.9637; n = 10 vs 10; Holm-adjusted p = 1.0000

### Follow-up: C2R (repair by re-seed)

- C2R vs C2: Δmean (C2R − C2) = +12.98; A12 = 0.58 [0.32, 0.83] → small, favouring C2R; permutation p = 0.1936; n = 10 vs 10
- C2R vs A5: Δmean (C2R − A5) = +0.25; A12 = 0.46 [0.20, 0.74] → negligible; permutation p = 0.8688; n = 10 vs 10

### Exploratory contrasts

- C2 vs A5, healthy only (exploratory): 63.7 (n 8) vs 63.7 (n 10); A12 = 0.45 [0.19, 0.72] → negligible; p = 0.9973
- C3s vs C2, healthy only (exploratory): 61.1 (n 8) vs 63.7 (n 8); A12 = 0.28 [0.05, 0.56] → practical, favouring C2; p = 0.1978
- C3n vs C2, healthy only (exploratory): 61.0 (n 9) vs 63.7 (n 8); A12 = 0.24 [0.04, 0.50] → practical, favouring C2; p = 0.0991
- C3s vs A5 (context): Δmean (C3s − A5) = -14.84; A12 = 0.25 [0.05, 0.50] → practical, favouring A5; permutation p = 0.0555; n = 10 vs 10
- C3n vs A5 (context): Δmean (C3n − A5) = -8.79; A12 = 0.23 [0.04, 0.48] → practical, favouring A5; permutation p = 0.0702; n = 10 vs 10
- C3n vs C3s (context): Δmean (C3n − C3s) = +6.05; A12 = 0.53 [0.27, 0.79] → negligible; permutation p = 0.6128; n = 10 vs 10

### Data integrity

- C2: rows 400, failed cells 80, runs 10
- A5: rows 400, failed cells 0, runs 10
- C3s: rows 400, failed cells 80, runs 10
- C3n: rows 400, failed cells 20, runs 10
- C2R: rows 400, failed cells 0, runs 10
- reachable_region_sha ['9939f23b25103648']; features_backend ['jvm']

### Mechanism: path after a gate event (log-only, exploratory)

| arm | path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|---|
| C2 | fallback refine (last working generator shown) | 1 | 1 of 1 | n/a |
| C2 | in-place | 8 | 0 of 8 | 0.97 (min 0.75, max 1.00) |
| C2 | (summary) | collapsed 2/10 | iteration-1 gate events 2 | in-iteration repair similarity 0.96 over 14 |
| A5 | in-place | 3 | 0 of 3 | 0.95 (min 0.89, max 0.99) |
| A5 | re-seed | 2 | 2 of 2 | 0.06 (min 0.06, max 0.06) |
| A5 | (summary) | collapsed 0/10 | iteration-1 gate events 2 | in-iteration repair similarity 0.94 over 5 |
| C3s | fallback refine (last working generator shown) | 1 | 0 of 1 | 0.96 (min 0.96, max 0.96) |
| C3s | in-place | 7 | 0 of 7 | 0.96 (min 0.89, max 1.00) |
| C3s | re-seed | 2 | 2 of 2 | 0.09 (min 0.09, max 0.09) |
| C3s | (summary) | collapsed 1/10 | iteration-1 gate events 4 | in-iteration repair similarity 0.96 over 12 |
| C3n | re-seed | 4 | 3 of 4 | 0.09 (min 0.07, max 0.13) |
| C3n | (summary) | collapsed 0/10 | iteration-1 gate events 3 | in-iteration repair similarity 0.99 over 1 |
| C2R | fallback refine (last working generator shown) | 2 | 2 of 2 | 0.80 (min 0.77, max 0.82) |
| C2R | re-seed | 4 | 2 of 4 | 0.08 (min 0.03, max 0.14) |
| C2R | (summary) | collapsed 0/10 | iteration-1 gate events 1 | in-iteration repair similarity 0.04 over 4 |

## parson

### Per arm

- C2 final: 60.9 ± 15.4 (median 67.1); replicate means 66.9, 67.3, 70.4, 66.6, 66.7, 0.0, 70.5, 67.3, 69.4, 63.9
- C2: Δ(final − seed) = r1:+1.0, r2:+1.4, r3:+1.0, r4:+0.0, r5:+1.5, r6:+0.0, r7:+1.8, r8:+0.9, r9:+1.4, r10:-0.1; mean +0.89 ± 0.50; 7 up / 1 down / 2 zero of 10; sign-flip p = 0.0156
- C2 collapsed (final unusable, scored 0): 1 of 10 (rep6)
- A5 final: 66.3 ± 1.6 (median 66.7); replicate means 66.5, 67.5, 66.9, 63.1, 67.7, 63.4, 66.2, 70.1, 67.9, 64.2
- A5: Δ(final − seed) = r1:+0.2, r2:-0.3, r3:-1.0, r4:+0.0, r5:+0.7, r6:+0.0, r7:+2.1, r8:+2.5, r9:+0.5, r10:+0.7; mean +0.54 ± 0.75; 7 up / 2 down / 1 zero of 10; sign-flip p = 0.1602
- A5 collapsed (final unusable, scored 0): 0 of 10
- C3s final: 69.1 ± 1.1 (median 69.4); replicate means 70.6, 69.0, 67.8, 69.8, 67.9, 71.4, 68.1, 69.9, 66.7, 70.1
- C3s: Δ(final − seed) = r1:+2.0, r2:-0.2, r3:+0.6, r4:+2.7, r5:+2.1, r6:+2.8, r7:+1.2, r8:-0.3, r9:+2.6, r10:+2.5; mean +1.59 ± 0.86; 8 up / 2 down / 0 zero of 10; sign-flip p = 0.0078
- C3s last working iteration where it differs from final (1 replicates): 68.6 ± 0.0 (median 68.6)
- C3s collapsed (final unusable, scored 0): 0 of 10
- C3n final: 66.0 ± 1.3 (median 65.8); replicate means 63.3, 65.6, 66.0, 65.0, 69.9, 67.0, 65.3, 67.3, 64.1, 66.1
- C3n: Δ(final − seed) = r1:-1.9, r2:-3.0, r3:-2.2, r4:+2.9, r5:+2.5, r6:+0.7, r7:+1.1, r8:+0.7, r9:-2.2, r10:-0.2; mean -0.16 ± 1.48; 5 up / 5 down / 0 zero of 10; sign-flip p = 0.7969
- C3n collapsed (final unusable, scored 0): 0 of 10
- M2C2 final: 62.9 ± 1.2 (median 62.9); replicate means 62.3, 63.0, 64.2, 66.1, 61.1, 60.4, 64.5, 61.6, 62.9, 63.3
- M2C2: Δ(final − seed) = r1:+0.5, r2:-0.3, r3:+64.2, r4:-0.1, r5:-1.5, r6:-0.5, r7:+4.4, r8:+0.9, r9:+0.0, r10:+2.7; mean +7.03 ± 14.41; 5 up / 4 down / 1 zero of 10; sign-flip p = 0.1680
- M2C2: seed failed but final works for rep3 (delta inflated by the whole final level); without them mean +0.67 ± 1.38, p = 0.3359, n = 9
- M2C2 last working iteration where it differs from final (5 replicates): 62.1 ± 1.9 (median 62.3)
- M2C2 collapsed (final unusable, scored 0): 0 of 10
- M2A5 final: 60.2 ± 2.2 (median 60.3); replicate means 62.8, 62.1, 65.0, 60.9, 59.6, 57.8, 58.8, 54.9, 57.3, 62.5
- M2A5: Δ(final − seed) = r1:+0.5, r2:-0.6, r3:-0.6, r4:-0.8, r5:+0.0, r6:-2.8, r7:-0.5, r8:-1.6, r9:-1.9, r10:-2.4; mean -1.06 ± 0.76; 1 up / 8 down / 1 zero of 10; sign-flip p = 0.0078
- M2A5 collapsed (final unusable, scored 0): 0 of 10
- M2C3s final: 62.0 ± 1.1 (median 62.2); replicate means 61.9, 64.6, 60.6, 62.9, 62.7, 59.1, 61.0, 62.4, 62.0, 62.9
- M2C3s: Δ(final − seed) = r1:-1.3, r2:+1.0, r3:-2.5, r4:-0.4, r5:+1.3, r6:+0.3, r7:+0.0, r8:-0.4, r9:+0.4, r10:+0.4; mean -0.12 ± 0.79; 5 up / 4 down / 1 zero of 10; sign-flip p = 0.7539
- M2C3s collapsed (final unusable, scored 0): 0 of 10

### Confirmatory family

- H1: C2 vs A5: Δmean (C2 − A5) = -5.46; A12 = 0.59 [0.32, 0.84] → small, favouring C2; permutation p = 0.8972; n = 10 vs 10; Holm-adjusted p = 1.0000
- H2s: C3s vs C2: Δmean (C3s − C2) = +8.25; A12 = 0.76 [0.52, 0.96] → practical, favouring C3s; permutation p = 0.0441; n = 10 vs 10; Holm-adjusted p = 0.1324
- H2n: C3n vs C2: Δmean (C3n − C2) = +5.09; A12 = 0.33 [0.09, 0.59] → practical, favouring C2; permutation p = 0.9562; n = 10 vs 10; Holm-adjusted p = 1.0000

### RQ5: the three-way under the second model (gpt-5-mini; exploratory, outside the family)

- M2 H1, M2C2 vs M2A5: Δmean (M2C2 − M2A5) = +2.77; A12 = 0.79 [0.56, 0.96] → practical, favouring M2C2; permutation p = 0.0222; n = 10 vs 10
- M2 H2s, M2C3s vs M2C2: Δmean (M2C3s − M2C2) = -0.92; A12 = 0.35 [0.12, 0.61] → practical, favouring M2C2; permutation p = 0.2162; n = 10 vs 10
- M2C3s vs M2A5 (context): Δmean (M2C3s − M2A5) = +1.85; A12 = 0.69 [0.42, 0.91] → practical, favouring M2C3s; permutation p = 0.1033; n = 10 vs 10
- cross-model, same arm: C2 vs M2C2: Δmean (C2 − M2C2) = -2.05; A12 = 0.87 [0.65, 1.00] → practical, favouring C2; permutation p = 1.0000; n = 10 vs 10
- cross-model, same arm: A5 vs M2A5: Δmean (A5 − M2A5) = +6.18; A12 = 0.97 [0.88, 1.00] → practical, favouring A5; permutation p = 0.0001; n = 10 vs 10
- cross-model, same arm: C3s vs M2C3s: Δmean (C3s − M2C3s) = +7.12; A12 = 1.00 [1.00, 1.00] → practical, favouring C3s; permutation p = 0.0000; n = 10 vs 10

### Exploratory contrasts

- C2 vs A5, healthy only (exploratory): 67.7 (n 9) vs 66.3 (n 10); A12 = 0.66 [0.38, 0.89] → practical, favouring C2; p = 0.2134
- C3s vs C2, healthy only (exploratory): 69.1 (n 10) vs 67.7 (n 9); A12 = 0.73 [0.47, 0.94] → practical, favouring C3s; p = 0.0894
- C3n vs C2, healthy only (exploratory): 66.0 (n 10) vs 67.7 (n 9); A12 = 0.26 [0.04, 0.50] → practical, favouring C2; p = 0.0821
- C3s vs A5 (context): Δmean (C3s − A5) = +2.79; A12 = 0.87 [0.68, 1.00] → practical, favouring C3s; permutation p = 0.0038; n = 10 vs 10
- C3n vs A5 (context): Δmean (C3n − A5) = -0.37; A12 = 0.39 [0.14, 0.66] → small, favouring A5; permutation p = 0.6855; n = 10 vs 10
- C3n vs C3s (context): Δmean (C3n − C3s) = -3.16; A12 = 0.09 [0.00, 0.26] → practical, favouring C3s; permutation p = 0.0012; n = 10 vs 10

### Data integrity

- C2: rows 400, failed cells 40, runs 10
- A5: rows 400, failed cells 0, runs 10
- C3s: rows 420, failed cells 0, runs 10
- C3n: rows 400, failed cells 0, runs 10
- M2C2: rows 500, failed cells 20, runs 10
- M2A5: rows 400, failed cells 0, runs 10
- M2C3s: rows 400, failed cells 0, runs 10
- reachable_region_sha ['6f136bf56adebd27']; features_backend ['jvm']

### Mechanism: path after a gate event (log-only, exploratory)

| arm | path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|---|
| C2 | in-place | 4 | 0 of 4 | 1.00 (min 0.99, max 1.00) |
| C2 | (summary) | collapsed 1/10 | iteration-1 gate events 1 | in-iteration repair similarity 1.00 over 6 |
| A5 | no gate event followed by another iteration | 0 | - | - |
| A5 | (summary) | collapsed 0/10 | iteration-1 gate events 0 | in-iteration repair similarity 0.99 over 2 |
| C3s | in-place | 1 | 1 of 1 | 1.00 (min 1.00, max 1.00) |
| C3s | (summary) | collapsed 0/10 | iteration-1 gate events 1 | in-iteration repair similarity 0.99 over 3 |
| C3n | re-seed | 1 | 1 of 1 | n/a |
| C3n | (summary) | collapsed 0/10 | iteration-1 gate events 1 | no repairs |
| M2C2 | fallback refine (last working generator shown) | 1 | 1 of 1 | 0.92 (min 0.92, max 0.92) |
| M2C2 | in-place | 1 | 1 of 1 | 0.97 (min 0.97, max 0.97) |
| M2C2 | re-seed | 1 | 1 of 1 | n/a |
| M2C2 | (summary) | collapsed 0/10 | iteration-1 gate events 2 | in-iteration repair similarity 0.99 over 4 |
| M2A5 | fallback refine (last working generator shown) | 1 | 1 of 1 | 0.95 (min 0.95, max 0.95) |
| M2A5 | re-seed | 3 | 3 of 3 | 0.02 (min 0.02, max 0.02) |
| M2A5 | (summary) | collapsed 0/10 | iteration-1 gate events 3 | in-iteration repair similarity 1.00 over 1 |
| M2C3s | re-seed | 1 | 1 of 1 | 0.04 (min 0.04, max 0.04) |
| M2C3s | (summary) | collapsed 0/10 | iteration-1 gate events 1 | in-iteration repair similarity 1.00 over 2 |

## tomlc99

### Per arm

- C2 final: 52.9 ± 13.9 (median 57.4); replicate means 57.7, 65.4, 0.0, 56.2, 57.2, 47.2, 60.7, 55.7, 63.9, 65.2
- C2: Δ(final − seed) = r1:-0.6, r2:-1.3, r3:+0.0, r4:+0.0, r5:+3.4, r6:-0.3, r7:-1.5, r8:+0.0, r9:+63.9, r10:+0.2; mean +6.38 ± 14.49; 3 up / 4 down / 3 zero of 10; sign-flip p = 0.5156
- C2: seed failed but final works for rep9 (delta inflated by the whole final level); without them mean -0.01 ± 1.10, p = 1.0000, n = 9
- C2 collapsed (final unusable, scored 0): 1 of 10 (rep3)
- A5 final: 60.2 ± 3.4 (median 59.8); replicate means 50.6, 65.4, 64.8, 64.3, 56.1, 64.7, 57.2, 60.5, 58.9, 59.1
- A5: Δ(final − seed) = r1:-0.9, r2:+1.1, r3:-0.9, r4:+6.3, r5:+1.1, r6:+7.1, r7:-1.0, r8:+0.7, r9:+2.7, r10:+59.1; mean +7.53 ± 13.11; 7 up / 3 down / 0 zero of 10; sign-flip p = 0.0605
- A5: seed failed but final works for rep10 (delta inflated by the whole final level); without them mean +1.80 ± 2.33, p = 0.1211, n = 9
- A5 collapsed (final unusable, scored 0): 0 of 10
- C3s final: 55.1 ± 14.1 (median 60.6); replicate means 67.6, 62.7, 59.2, 53.5, 58.3, 60.8, 60.3, 0.0, 64.6, 64.2
- C3s: Δ(final − seed) = r1:+0.0, r2:+0.6, r3:-1.8, r4:+0.8, r5:+0.0, r6:+0.0, r7:+0.4, r8:+0.0, r9:+1.1, r10:+1.0; mean +0.22 ± 0.61; 5 up / 1 down / 4 zero of 10; sign-flip p = 0.4375
- C3s last working iteration where it differs from final (6 replicates): 50.7 ± 26.2 (median 60.0)
- C3s collapsed (final unusable, scored 0): 1 of 10 (rep8)
- C3n final: 57.4 ± 3.7 (median 58.5); replicate means 53.1, 60.7, 48.1, 56.2, 51.2, 60.5, 63.7, 56.4, 61.6, 62.2
- C3n: Δ(final − seed) = r1:-3.0, r2:+0.0, r3:+0.0, r4:+0.0, r5:-0.6, r6:+0.0, r7:+0.0, r8:+0.0, r9:-2.8, r10:+62.2; mean +5.59 ± 14.25; 1 up / 3 down / 6 zero of 10; sign-flip p = 1.0000
- C3n: seed failed but final works for rep10 (delta inflated by the whole final level); without them mean -0.70 ± 0.96, p = 0.2500, n = 9
- C3n last working iteration where it differs from final (4 replicates): 51.2 ± 9.3 (median 50.9)
- C3n collapsed (final unusable, scored 0): 0 of 10
- C2R final: 59.3 ± 2.4 (median 60.3); replicate means 59.5, 64.2, 54.6, 55.7, 62.7, 61.3, 61.1, 61.4, 55.8, 56.5
- C2R: Δ(final − seed) = r1:-0.8, r2:+0.0, r3:-1.1, r4:-1.7, r5:-1.1, r6:-0.6, r7:+0.0, r8:+1.9, r9:-5.3, r10:-5.4; mean -1.41 ± 1.64; 1 up / 7 down / 2 zero of 10; sign-flip p = 0.0859
- C2R last working iteration where it differs from final (3 replicates): 60.2 ± 8.1 (median 61.8)
- C2R collapsed (final unusable, scored 0): 0 of 10
- M2C2 final: 51.8 ± 3.1 (median 51.0); replicate means 49.9, 54.6, 46.9, 46.2, 50.8, 54.1, 48.0, 59.1, 56.7, 51.2
- M2C2: Δ(final − seed) = r1:+49.9, r2:+0.0, r3:+0.0, r4:+0.6, r5:-0.1, r6:+1.5, r7:+1.6, r8:+0.0, r9:+0.8, r10:+0.1; mean +5.45 ± 11.18; 7 up / 1 down / 2 zero of 10; sign-flip p = 0.0234
- M2C2: seed failed but final works for rep1 (delta inflated by the whole final level); without them mean +0.51 ± 0.52, p = 0.0469, n = 9
- M2C2 last working iteration where it differs from final (3 replicates): 38.5 ± 83.2 (median 54.6)
- M2C2 collapsed (final unusable, scored 0): 0 of 10
- M2A5 final: 52.5 ± 3.9 (median 50.6); replicate means 51.8, 48.4, 59.5, 49.3, 56.7, 47.6, 47.3, 49.8, 63.0, 51.4
- M2A5: Δ(final − seed) = r1:+51.8, r2:-0.3, r3:+1.8, r4:+49.3, r5:-4.8, r6:+47.6, r7:+1.0, r8:-2.0, r9:+0.9, r10:-1.1; mean +14.42 ± 17.39; 6 up / 4 down / 0 zero of 10; sign-flip p = 0.1875
- M2A5: seed failed but final works for rep1, rep4, rep6 (delta inflated by the whole final level); without them mean -0.64 ± 2.08, p = 0.5156, n = 7
- M2A5 collapsed (final unusable, scored 0): 0 of 10
- M2C3s final: 38.8 ± 17.1 (median 49.9); replicate means 53.1, 57.9, 63.5, 43.5, 47.6, 17.1, 52.7, 0.0, 52.3, 0.0
- M2C3s: Δ(final − seed) = r1:-0.1, r2:+1.8, r3:-0.7, r4:-7.1, r5:-3.6, r6:+0.0, r7:+1.1, r8:+0.0, r9:+0.6, r10:+0.0; mean -0.81 ± 1.88; 3 up / 4 down / 3 zero of 10; sign-flip p = 0.4219
- M2C3s last working iteration where it differs from final (4 replicates): 38.3 ± 41.6 (median 48.2)
- M2C3s collapsed (final unusable, scored 0): 2 of 10 (rep8, rep10)

### Confirmatory family

- H1: C2 vs A5: Δmean (C2 − A5) = -7.25; A12 = 0.39 [0.14, 0.66] → small, favouring A5; permutation p = 0.2881; n = 10 vs 10; Holm-adjusted p = 0.8643
- H2s: C3s vs C2: Δmean (C3s − C2) = +2.20; A12 = 0.60 [0.35, 0.86] → small, favouring C3s; permutation p = 0.6468; n = 10 vs 10; Holm-adjusted p = 1.0000
- H2n: C3n vs C2: Δmean (C3n − C2) = +4.46; A12 = 0.47 [0.21, 0.74] → negligible; permutation p = 0.7106; n = 10 vs 10; Holm-adjusted p = 1.0000

### Follow-up: C2R (repair by re-seed)

- C2R vs C2: Δmean (C2R − C2) = +6.37; A12 = 0.54 [0.28, 0.81] → negligible; permutation p = 0.4140; n = 10 vs 10
- C2R vs A5: Δmean (C2R − A5) = -0.87; A12 = 0.40 [0.15, 0.68] → small, favouring A5; permutation p = 0.6471; n = 10 vs 10

### RQ5: the three-way under the second model (gpt-5-mini; exploratory, outside the family)

- M2 H1, M2C2 vs M2A5: Δmean (M2C2 − M2A5) = -0.73; A12 = 0.46 [0.20, 0.74] → negligible; permutation p = 0.7404; n = 10 vs 10
- M2 H2s, M2C3s vs M2C2: Δmean (M2C3s − M2C2) = -12.97; A12 = 0.39 [0.14, 0.66] → small, favouring M2C2; permutation p = 0.1428; n = 10 vs 10
- M2C3s vs M2A5 (context): Δmean (M2C3s − M2A5) = -13.70; A12 = 0.41 [0.16, 0.68] → small, favouring M2A5; permutation p = 0.1222; n = 10 vs 10
- cross-model, same arm: C2 vs M2C2: Δmean (C2 − M2C2) = +1.16; A12 = 0.76 [0.50, 0.97] → practical, favouring C2; permutation p = 0.9512; n = 10 vs 10
- cross-model, same arm: A5 vs M2A5: Δmean (A5 − M2A5) = +7.68; A12 = 0.85 [0.65, 0.98] → practical, favouring A5; permutation p = 0.0050; n = 10 vs 10
- cross-model, same arm: C3s vs M2C3s: Δmean (C3s − M2C3s) = +16.33; A12 = 0.84 [0.62, 1.00] → practical, favouring C3s; permutation p = 0.1028; n = 10 vs 10

### Exploratory contrasts

- C2 vs A5, healthy only (exploratory): 58.8 (n 9) vs 60.2 (n 10); A12 = 0.43 [0.16, 0.71] → small, favouring A5; p = 0.5782
- C3s vs C2, healthy only (exploratory): 61.2 (n 9) vs 58.8 (n 9); A12 = 0.63 [0.36, 0.89] → small, favouring C3s; p = 0.3277
- C3n vs C2, healthy only (exploratory): 57.4 (n 10) vs 58.8 (n 9); A12 = 0.41 [0.16, 0.70] → small, favouring C2; p = 0.5780
- C3s vs A5 (context): Δmean (C3s − A5) = -5.05; A12 = 0.49 [0.23, 0.76] → negligible; permutation p = 0.6967; n = 10 vs 10
- C3n vs A5 (context): Δmean (C3n − A5) = -2.79; A12 = 0.35 [0.12, 0.62] → practical, favouring A5; permutation p = 0.2289; n = 10 vs 10
- C3n vs C3s (context): Δmean (C3n − C3s) = +2.26; A12 = 0.36 [0.13, 0.64] → practical, favouring C3s; permutation p = 0.9548; n = 10 vs 10

### Data integrity

- C2: rows 400, failed cells 60, runs 10
- A5: rows 400, failed cells 20, runs 10
- C3s: rows 520, failed cells 60, runs 10
- C3n: rows 480, failed cells 20, runs 10
- C2R: rows 460, failed cells 0, runs 10
- M2C2: rows 460, failed cells 42, runs 10
- M2A5: rows 400, failed cells 62, runs 10
- M2C3s: rows 480, failed cells 103, runs 10
- reachable_region_sha ['d7be29f10279a4f2']; features_backend ['jvm']

### Mechanism: path after a gate event (log-only, exploratory)

| arm | path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|---|
| C2 | fallback refine (last working generator shown) | 2 | 1 of 2 | 0.95 (min 0.92, max 0.98) |
| C2 | in-place | 6 | 2 of 6 | 1.00 (min 0.99, max 1.00) |
| C2 | re-seed | 5 | 3 of 5 | 0.10 (min 0.08, max 0.11) |
| C2 | (summary) | collapsed 1/10 | iteration-1 gate events 6 | in-iteration repair similarity 1.00 over 6 |
| A5 | re-seed | 2 | 2 of 2 | 0.03 (min 0.02, max 0.04) |
| A5 | (summary) | collapsed 0/10 | iteration-1 gate events 2 | in-iteration repair similarity 0.99 over 2 |
| C3s | in-place | 10 | 1 of 10 | 1.00 (min 0.96, max 1.00) |
| C3s | re-seed | 2 | 2 of 2 | 0.02 (min 0.02, max 0.02) |
| C3s | (summary) | collapsed 1/10 | iteration-1 gate events 4 | in-iteration repair similarity 0.99 over 14 |
| C3n | fallback refine (last working generator shown) | 1 | 1 of 1 | n/a |
| C3n | in-place | 1 | 1 of 1 | 0.82 (min 0.82, max 0.82) |
| C3n | re-seed | 2 | 2 of 2 | 0.09 (min 0.02, max 0.15) |
| C3n | (summary) | collapsed 0/10 | iteration-1 gate events 3 | in-iteration repair similarity 1.00 over 3 |
| C2R | re-seed | 3 | 3 of 3 | 0.03 (min 0.03, max 0.03) |
| C2R | (summary) | collapsed 0/10 | iteration-1 gate events 3 | in-iteration repair similarity 0.05 over 3 |
| M2C2 | fallback refine (last working generator shown) | 1 | 1 of 1 | 0.99 (min 0.99, max 0.99) |
| M2C2 | in-place | 5 | 3 of 5 | 0.97 (min 0.84, max 1.00) |
| M2C2 | re-seed | 8 | 4 of 8 | 0.03 (min 0.03, max 0.03) |
| M2C2 | (summary) | collapsed 0/10 | iteration-1 gate events 5 | in-iteration repair similarity 0.99 over 12 |
| M2A5 | fallback refine (last working generator shown) | 2 | 2 of 2 | n/a |
| M2A5 | in-place | 6 | 4 of 6 | 0.97 (min 0.93, max 1.00) |
| M2A5 | re-seed | 9 | 2 of 9 | n/a |
| M2A5 | (summary) | collapsed 0/10 | iteration-1 gate events 6 | in-iteration repair similarity 0.99 over 7 |
| M2C3s | in-place | 3 | 0 of 3 | 1.00 (min 1.00, max 1.00) |
| M2C3s | re-seed | 11 | 3 of 11 | 0.06 (min 0.06, max 0.06) |
| M2C3s | (summary) | collapsed 0/10 | iteration-1 gate events 5 | in-iteration repair similarity 0.99 over 4 |

## cjson

### Per arm

- C2 final: 61.8 ± 15.6 (median 68.3); replicate means 0.0, 66.9, 67.6, 71.4, 66.8, 69.7, 70.3, 67.0, 69.0, 69.1
- C2: Δ(final − seed) = r1:+0.0, r2:+0.0, r3:-0.9, r4:-1.8, r5:-0.4, r6:-0.4, r7:-1.1, r8:-0.7, r9:+0.5, r10:-0.4; mean -0.51 ± 0.46; 2 up / 7 down / 1 zero of 10; sign-flip p = 0.0391
- C2 last working iteration where it differs from final (1 replicates): 67.1 ± 0.0 (median 67.1)
- C2 collapsed (final unusable, scored 0): 1 of 10 (rep1)
- A5 final: 70.3 ± 1.6 (median 70.1); replicate means 73.1, 70.0, 72.5, 68.5, 65.8, 69.6, 72.0, 70.2, 69.0, 72.1
- A5: Δ(final − seed) = r1:+6.4, r2:-0.4, r3:+4.3, r4:+0.1, r5:-0.7, r6:+0.4, r7:-0.3, r8:+0.0, r9:+2.6, r10:+1.0; mean +1.35 ± 1.69; 6 up / 3 down / 1 zero of 10; sign-flip p = 0.1133
- A5 collapsed (final unusable, scored 0): 0 of 10
- C3s final: 64.2 ± 16.2 (median 72.2); replicate means 72.2, 69.5, 71.4, 72.7, 72.6, 65.4, 72.2, 0.0, 73.7, 72.6
- C3s: Δ(final − seed) = r1:+1.9, r2:-1.3, r3:+1.6, r4:+72.7, r5:+4.8, r6:-4.5, r7:+2.4, r8:+0.0, r9:+2.8, r10:+2.7; mean +8.30 ± 16.26; 7 up / 2 down / 1 zero of 10; sign-flip p = 0.1172
- C3s: seed failed but final works for rep4 (delta inflated by the whole final level); without them mean +1.15 ± 2.10, p = 0.2344, n = 9
- C3s last working iteration where it differs from final (2 replicates): 71.7 ± 9.1 (median 71.7)
- C3s collapsed (final unusable, scored 0): 1 of 10 (rep8)
- C3n final: 66.6 ± 5.1 (median 68.8); replicate means 72.9, 48.0, 69.1, 68.6, 70.4, 70.6, 68.2, 66.0, 62.7, 69.5
- C3n: Δ(final − seed) = r1:+72.9, r2:-21.4, r3:+69.1, r4:+0.0, r5:-0.6, r6:-0.8, r7:+0.3, r8:+0.9, r9:-3.9, r10:-0.8; mean +11.57 ± 22.87; 4 up / 5 down / 1 zero of 10; sign-flip p = 0.4648
- C3n: seed failed but final works for rep1, rep3 (delta inflated by the whole final level); without them mean -3.28 ± 6.23, p = 0.1562, n = 8
- C3n last working iteration where it differs from final (1 replicates): 60.9 ± 0.0 (median 60.9)
- C3n collapsed (final unusable, scored 0): 0 of 10

### Confirmatory family

- H1: C2 vs A5: Δmean (C2 − A5) = -8.49; A12 = 0.25 [0.06, 0.49] → practical, favouring A5; permutation p = 0.0455; n = 10 vs 10; Holm-adjusted p = 0.1366
- H2s: C3s vs C2: Δmean (C3s − C2) = +2.44; A12 = 0.78 [0.52, 0.98] → practical, favouring C3s; permutation p = 0.4856; n = 10 vs 10; Holm-adjusted p = 0.9712
- H2n: C3n vs C2: Δmean (C3n − C2) = +4.80; A12 = 0.54 [0.28, 0.80] → negligible; permutation p = 0.7358; n = 10 vs 10; Holm-adjusted p = 0.9712

### Exploratory contrasts

- C2 vs A5, healthy only (exploratory): 68.7 (n 9) vs 70.3 (n 10); A12 = 0.28 [0.07, 0.53] → practical, favouring A5; p = 0.0923
- C3s vs C2, healthy only (exploratory): 71.4 (n 9) vs 68.7 (n 9); A12 = 0.84 [0.60, 1.00] → practical, favouring C3s; p = 0.0168
- C3n vs C2, healthy only (exploratory): 66.6 (n 10) vs 68.7 (n 9); A12 = 0.49 [0.22, 0.77] → negligible; p = 0.5351
- C3s vs A5 (context): Δmean (C3s − A5) = -6.05; A12 = 0.62 [0.35, 0.88] → small, favouring C3s; permutation p = 0.8314; n = 10 vs 10
- C3n vs A5 (context): Δmean (C3n − A5) = -3.69; A12 = 0.31 [0.09, 0.58] → practical, favouring A5; permutation p = 0.1007; n = 10 vs 10
- C3n vs C3s (context): Δmean (C3n − C3s) = +2.36; A12 = 0.28 [0.04, 0.54] → practical, favouring C3s; permutation p = 0.9866; n = 10 vs 10

### Data integrity

- C2: rows 420, failed cells 40, runs 10
- A5: rows 400, failed cells 0, runs 10
- C3s: rows 440, failed cells 60, runs 10
- C3n: rows 420, failed cells 46, runs 10
- reachable_region_sha ['fe1b1274d6b61daf']; features_backend ['jvm']

### Mechanism: path after a gate event (log-only, exploratory)

| arm | path | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|---|
| C2 | in-place | 4 | 0 of 4 | 1.00 (min 1.00, max 1.00) |
| C2 | re-seed | 4 | 4 of 4 | 0.06 (min 0.04, max 0.07) |
| C2 | (summary) | collapsed 1/10 | iteration-1 gate events 5 | in-iteration repair similarity 1.00 over 6 |
| A5 | fallback refine (last working generator shown) | 1 | 1 of 1 | n/a |
| A5 | re-seed | 1 | 1 of 1 | 0.05 (min 0.05, max 0.05) |
| A5 | (summary) | collapsed 0/10 | iteration-1 gate events 1 | in-iteration repair similarity 0.98 over 2 |
| C3s | in-place | 4 | 2 of 4 | 0.99 (min 0.98, max 1.00) |
| C3s | re-seed | 4 | 1 of 4 | 0.11 (min 0.11, max 0.11) |
| C3s | (summary) | collapsed 0/10 | iteration-1 gate events 3 | in-iteration repair similarity 1.00 over 9 |
| C3n | in-place | 2 | 2 of 2 | 0.96 (min 0.93, max 0.99) |
| C3n | (summary) | collapsed 0/10 | iteration-1 gate events 2 | in-iteration repair similarity 0.98 over 4 |

## Spend (per-run final.json at .env prices)

- json-parser: {'C2': 0.305, 'A5': 0.21, 'C3s': 0.278, 'C3n': 0.231, 'C2R': 0.233}
- parson: {'C2': 0.214, 'A5': 0.194, 'C3s': 0.263, 'C3n': 0.218, 'M2C2': 0.438, 'M2A5': 0.441, 'M2C3s': 0.441}
- tomlc99: {'C2': 0.321, 'A5': 0.302, 'C3s': 0.414, 'C3n': 0.326, 'C2R': 0.289, 'M2C2': 0.738, 'M2A5': 0.76, 'M2C3s': 0.664}
- cjson: {'C2': 0.194, 'A5': 0.177, 'C3s': 0.232, 'C3n': 0.232}
- total 8.115 USD
