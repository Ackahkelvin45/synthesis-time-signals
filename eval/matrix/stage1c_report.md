# Stage 1 closing cells: C3s on tomlc99, C2R (repair by re-seed) on json-parser

Primary outcome `auc_branch_reach` (10^4 inputs x 20 fresh draw seeds per replicate; failed cells scored 0, so a collapsed replicate scores 0). Unit = loop replicate. Bands: A12 >= 0.64 (or <= 0.36) practical; 0.56-0.64 (0.36-0.44) small; otherwise negligible. Sources `eval/matrix/stage1.jsonl` (C2, A5), `eval/matrix/stage1c.jsonl` (C3s, C2R).

## tomlc99: C3s (coverage-scalar oracle) vs C2 and A5

### Per arm

- C3s final: 55.1 ± 14.1 (median 60.6); replicate means 67.6, 62.7, 59.2, 53.5, 58.3, 60.8, 60.3, 0.0, 64.6, 64.2
- C3s: per-replicate Δ(final − seed) = r1:+0.0, r2:+0.6, r3:-1.8, r4:+0.8, r5:+0.0, r6:+0.0, r7:+0.4, r8:+0.0, r9:+1.1, r10:+1.0; mean +0.22 ± 0.61; 5 positive / 1 negative / 4 zero of 10; sign-flip p = 0.4375
- C3s last working iteration (reported next to final, plan E1): 50.7 ± 26.2 (median 60.0)
- C3s unusable final generators (collapsed, scored 0): 1 of 10 (rep8)
- C2 final: 52.9 ± 13.9 (median 57.4); replicate means 57.7, 65.4, 0.0, 56.2, 57.2, 47.2, 60.7, 55.7, 63.9, 65.2
- C2: per-replicate Δ(final − seed) = r1:-0.6, r2:-1.3, r3:+0.0, r4:+0.0, r5:+3.4, r6:-0.3, r7:-1.5, r8:+0.0, r9:+63.9, r10:+0.2; mean +6.38 ± 14.49; 3 positive / 4 negative / 3 zero of 10; sign-flip p = 0.5156
- C2: seed generator failed but final works for rep9 (delta inflated by the whole final level); without them: mean -0.01 ± 1.10, sign-flip p = 1.0000, n = 9
- C2 unusable final generators (collapsed, scored 0): 1 of 10 (rep3)
- A5 final: 60.2 ± 3.4 (median 59.8); replicate means 50.6, 65.4, 64.8, 64.3, 56.1, 64.7, 57.2, 60.5, 58.9, 59.1
- A5: per-replicate Δ(final − seed) = r1:-0.9, r2:+1.1, r3:-0.9, r4:+6.3, r5:+1.1, r6:+7.1, r7:-1.0, r8:+0.7, r9:+2.7, r10:+59.1; mean +7.53 ± 13.11; 7 positive / 3 negative / 0 zero of 10; sign-flip p = 0.0605
- A5: seed generator failed but final works for rep10 (delta inflated by the whole final level); without them: mean +1.80 ± 2.33, sign-flip p = 0.1211, n = 9
- A5 unusable final generators (collapsed, scored 0): 0 of 10

### Between arms

- H2s (C3s vs C2, confirmatory): difference of means (C3s − C2) = +2.20; A12 = 0.60 (bootstrap 95% CI [0.35, 0.86]) → small, favouring C3s; permutation p = 0.6468; n = 10 vs 10; Holm-adjusted p over the family run on this target {H1, H2s} = 0.6468
- H1 (C2 vs A5, from the Stage 1 report, restated for the Holm family): difference of means (C2 − A5) = -7.25; A12 = 0.39 (bootstrap 95% CI [0.14, 0.66]) → small, favouring A5; permutation p = 0.2881; n = 10 vs 10; Holm-adjusted p = 0.5762
- C3s vs A5 (context, outside the registered family): difference of means (C3s − A5) = -5.05; A12 = 0.49 (bootstrap 95% CI [0.23, 0.76]) → negligible; permutation p = 0.6967; n = 10 vs 10
- healthy only (exploratory): C3s 61.2 (n 9) vs C2 58.8 (n 9); A12 = 0.63 [0.36, 0.89] → small, favouring C3s; permutation p = 0.3277
- healthy only (exploratory): C3s 61.2 (n 9) vs A5 60.2 (n 10); A12 = 0.54 [0.27, 0.80] → negligible; permutation p = 0.6063

### Data integrity

- C3s: matrix rows 520, failed cells 60
- C2: matrix rows 400, failed cells 60
- A5: matrix rows 400, failed cells 20
- reachable_region_sha ['d7be29f10279a4f2']; features_backend ['jvm']
- batch stage1c-tomlc99-c3s: 10 ok, 0 failed after rerun; served ['deepseek-flash']; mean wall 3.6 min

### Mechanism on tomlc99 (log-only, exploratory)

Path after each gate event (gated, build-rejected or mid-run error, followed by another iteration), whether the next iteration recovered, and the code similarity between the failed iteration and the next (1.0 = resubmitted unchanged; the fixation signature).

| arm | path after a gate event | cases | next iteration recovered | code similarity to the failed iteration |
|---|---|---|---|---|
| C3s | in-place | 10 | 1 of 10 | 1.00 (min 0.96, max 1.00) |
| C3s | re-seed | 2 | 2 of 2 | 0.02 (min 0.02, max 0.02) |
| C2 | in-place | 8 | 3 of 8 | 0.99 (min 0.92, max 1.00) |
| C2 | re-seed | 5 | 3 of 5 | 0.10 (min 0.08, max 0.11) |
| A5 | re-seed | 2 | 2 of 2 | 0.03 (min 0.02, max 0.04) |

- C3s: collapsed 1 of 10; iteration-1 gate events 4 (collapsed after one: 1); mean consecutive code similarity 0.874 over replicates; in-iteration repair similarity to the gated code 0.99 over 14 repairs (min 0.96)
- C2: collapsed 1 of 10; iteration-1 gate events 6 (collapsed after one: 1); mean consecutive code similarity 0.875 over replicates; in-iteration repair similarity to the gated code 1.00 over 6 repairs (min 1.00)
- A5: collapsed 0 of 10; iteration-1 gate events 2 (collapsed after one: 0); mean consecutive code similarity 0.904 over replicates; in-iteration repair similarity to the gated code 0.99 over 2 repairs (min 0.99)
- collapse C3s 1/10 vs C2 1/10: Fisher exact two-sided p = 1.0000

## Spend of the closing cells

- C3s tomlc99: 0.414 USD; C2R json-parser: 0.000 USD (est. from per-run token counts at .env prices)
