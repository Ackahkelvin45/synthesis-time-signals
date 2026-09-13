# Stage 1 H1 report (registered structure)

Primary outcome `auc_branch_reach` (10^4 inputs x 20 fresh draw seeds per replicate; failed cells scored 0). Unit = loop replicate. Bands: A12 >= 0.64 (or <= 0.36) practical; 0.56-0.64 (0.36-0.44) small; otherwise negligible. Source `eval/matrix/stage1.jsonl`.

## json-parser

### C2 vs A5 (registered analysis, all replicates)

- C2 final: 51.0 ± 19.3 (median 63.9); replicate means 63.6, 64.7, 58.3, 61.7, 65.5, 65.2, 0.0, 64.2, 66.3, 0.0
- A5 final: 63.7 ± 2.8 (median 64.6); replicate means 64.9, 66.8, 54.7, 59.6, 65.0, 67.3, 67.3, 64.3, 63.8, 63.1
- C2: per-replicate Δ(final − seed) = r1:-1.2, r2:-2.1, r3:-2.8, r4:-1.8, r5:+0.3, r6:-1.0, r7:+0.0, r8:-2.1, r9:+0.3, r10:+0.0; mean -1.02 ± 0.81; 2 positive / 6 negative / 2 zero of 10; sign-flip p = 0.0312
- A5: per-replicate Δ(final − seed) = r1:-0.3, r2:+0.4, r3:-1.4, r4:+0.2, r5:+0.4, r6:+1.6, r7:+0.5, r8:+3.2, r9:-0.3, r10:-2.9; mean +0.15 ± 1.16; 6 positive / 4 negative / 0 zero of 10; sign-flip p = 0.7676
- difference of means (C2 − A5) = -12.73; A12 = 0.36 (bootstrap 95% CI [0.14, 0.63]) → practical, favouring A5; permutation p = 0.2375; n = 10 vs 10
- unusable final generators (collapsed): C2 2 of 10 (rep7, rep10); A5 0 of 10

### Healthy-replicate contrast (exploratory: collapsed C2 replicates excluded)

- C2 healthy final: 63.7 ± 2.2 (median 64.5)
- C2 healthy: per-replicate Δ(final − seed) = r1:-1.2, r2:-2.1, r3:-2.8, r4:-1.8, r5:+0.3, r6:-1.0, r8:-2.1, r9:+0.3; mean -1.28 ± 0.94; 2 positive / 6 negative / 0 zero of 8; sign-flip p = 0.0312
- difference of means (C2 − A5) = +0.00; A12 = 0.45 (bootstrap 95% CI [0.19, 0.72]) → negligible; permutation p = 0.9973; n = 8 vs 10

### Data integrity

- matrix rows: 800 (expect 800 = 20 conditions x 20 seeds; final + seed), failed cells 80
- runs: C2 10, A5 10 (expect 10 each); reruns: stage1a: 20 ok, 8 failed rows (A5-rep10, A5-rep7, A5-rep8, A5-rep9, C2-rep10, C2-rep7, C2-rep8, C2-rep9; each rerun after a network outage, no tokens spent), served ['deepseek-flash']
- features_backend: ['jvm']; reachable_region_sha: ['9939f23b25103648']

## parson

### C2 vs A5 (registered analysis, all replicates)

- C2 final: 60.9 ± 15.4 (median 67.1); replicate means 66.9, 67.3, 70.4, 66.6, 66.7, 0.0, 70.5, 67.3, 69.4, 63.9
- A5 final: 66.3 ± 1.6 (median 66.7); replicate means 66.5, 67.5, 66.9, 63.1, 67.7, 63.4, 66.2, 70.1, 67.9, 64.2
- C2: per-replicate Δ(final − seed) = r1:+1.0, r2:+1.4, r3:+1.0, r4:+0.0, r5:+1.5, r6:+0.0, r7:+1.8, r8:+0.9, r9:+1.4, r10:-0.1; mean +0.89 ± 0.50; 7 positive / 1 negative / 2 zero of 10; sign-flip p = 0.0156
- A5: per-replicate Δ(final − seed) = r1:+0.2, r2:-0.3, r3:-1.0, r4:+0.0, r5:+0.7, r6:+0.0, r7:+2.1, r8:+2.5, r9:+0.5, r10:+0.7; mean +0.54 ± 0.75; 7 positive / 2 negative / 1 zero of 10; sign-flip p = 0.1602
- difference of means (C2 − A5) = -5.46; A12 = 0.59 (bootstrap 95% CI [0.32, 0.84]) → small, favouring C2; permutation p = 0.8972; n = 10 vs 10
- unusable final generators (collapsed): C2 1 of 10 (rep6); A5 0 of 10

### Healthy-replicate contrast (exploratory: collapsed C2 replicates excluded)

- C2 healthy final: 67.7 ± 1.6 (median 67.3)
- C2 healthy: per-replicate Δ(final − seed) = r1:+1.0, r2:+1.4, r3:+1.0, r4:+0.0, r5:+1.5, r7:+1.8, r8:+0.9, r9:+1.4, r10:-0.1; mean +0.99 ± 0.51; 7 positive / 1 negative / 1 zero of 9; sign-flip p = 0.0156
- difference of means (C2 − A5) = +1.30; A12 = 0.66 (bootstrap 95% CI [0.38, 0.89]) → practical, favouring C2; permutation p = 0.2134; n = 9 vs 10

### Data integrity

- matrix rows: 800 (expect 800 = 20 conditions x 20 seeds; final + seed), failed cells 40
- runs: C2 10, A5 10 (expect 10 each); reruns: stage1b-parson: 20 ok, 0 failed rows, served ['deepseek-flash']
- features_backend: ['jvm']; reachable_region_sha: ['6f136bf56adebd27']

## tomlc99

### C2 vs A5 (registered analysis, all replicates)

- C2 final: 52.9 ± 13.9 (median 57.4); replicate means 57.7, 65.4, 0.0, 56.2, 57.2, 47.2, 60.7, 55.7, 63.9, 65.2
- A5 final: 60.2 ± 3.4 (median 59.8); replicate means 50.6, 65.4, 64.8, 64.3, 56.1, 64.7, 57.2, 60.5, 58.9, 59.1
- C2: per-replicate Δ(final − seed) = r1:-0.6, r2:-1.3, r3:+0.0, r4:+0.0, r5:+3.4, r6:-0.3, r7:-1.5, r8:+0.0, r9:+63.9, r10:+0.2; mean +6.38 ± 14.49; 3 positive / 4 negative / 3 zero of 10; sign-flip p = 0.5156
- A5: per-replicate Δ(final − seed) = r1:-0.9, r2:+1.1, r3:-0.9, r4:+6.3, r5:+1.1, r6:+7.1, r7:-1.0, r8:+0.7, r9:+2.7, r10:+59.1; mean +7.53 ± 13.11; 7 positive / 3 negative / 0 zero of 10; sign-flip p = 0.0605
- difference of means (C2 − A5) = -7.25; A12 = 0.39 (bootstrap 95% CI [0.14, 0.66]) → small, favouring A5; permutation p = 0.2881; n = 10 vs 10
- unusable final generators (collapsed): C2 1 of 10 (rep3); A5 0 of 10

### Healthy-replicate contrast (exploratory: collapsed C2 replicates excluded)

- C2 healthy final: 58.8 ± 4.5 (median 57.7)
- C2 healthy: per-replicate Δ(final − seed) = r1:-0.6, r2:-1.3, r4:+0.0, r5:+3.4, r6:-0.3, r7:-1.5, r8:+0.0, r9:+63.9, r10:+0.2; mean +7.09 ± 16.45; 3 positive / 4 negative / 2 zero of 9; sign-flip p = 0.5156
- difference of means (C2 − A5) = -1.37; A12 = 0.43 (bootstrap 95% CI [0.16, 0.71]) → small, favouring A5; permutation p = 0.5782; n = 9 vs 10

### Data integrity

- matrix rows: 800 (expect 800 = 20 conditions x 20 seeds; final + seed), failed cells 80
- runs: C2 10, A5 10 (expect 10 each); reruns: stage1b-tomlc99: 20 ok, 0 failed rows, served ['deepseek-flash']
- features_backend: ['jvm']; reachable_region_sha: ['d7be29f10279a4f2']

## Stage 1 spend

- per target (est. from per-run token counts at .env prices): {'json-parser': 0.515, 'parson': 0.408, 'tomlc99': 0.623}
- total 1.546 USD of the registered 4.00 USD Stage 1 ceiling (10.00 USD hard cap)
