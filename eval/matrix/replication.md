# Pre-registered replication: results

Unit: replicate pair on a shared draft. Statistic: mean over parson, tomlc99, cjson of the per-target mean paired difference, coverage points. Sign-flip tests with 100000 random flips, seed 0. Per-target cells: mean (up/down/zero).

## Confirmatory family (Holm, alpha 0.05)

| hypothesis | contrast | pairs | pooled mean [95% CI] | 90% CI | parson | tomlc99 | cjson | p | Holm p | decision |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 | numbers and names minus numbers | 30 | +1.63 [-2.99, +7.98] | [-2.70, +6.63] | +5.78 (3/6/1) | +1.40 (3/7/0) | -2.30 (2/8/0) | 0.7335 | 1.0000 | not supported |
| H2 | proxy summary minus no feedback | 30 | +0.49 [-2.60, +5.55] | [-2.39, +4.97] | +5.65 (3/7/0) | -3.73 (1/9/0) | -0.44 (3/7/0) | 0.5001 | 1.0000 | not supported |
| H3 | coverage numbers minus no feedback | 30 | -1.12 [-8.54, +5.77] | [-7.67, +5.06] | +0.67 (6/4/0) | -5.64 (4/6/0) | +1.61 (7/3/0) | 0.4812 | 1.0000 | not supported (equivalence within ±2.0) |

## Bridge (secondary): current backend B5 against September A5, unpaired

| target | what | September A5 mean (n) | B5 mean (n) | B5 minus A5 [95% CI] | A12 (B5 vs A5) |
|---|---|---|---|---|---|
| parson | seed | 65.8 (10) | 59.7 (10) | -6.09 [-20.08, +1.84] | 0.51 |
| parson | final | 66.3 (10) | 49.5 (10) | -16.85 [-35.52, -0.55] | 0.43 |
| tomlc99 | seed | 52.6 (10) | 57.9 (8) | +5.31 [-4.29, +18.71] | 0.54 |
| tomlc99 | final | 60.2 (10) | 48.0 (10) | -12.19 [-29.61, +0.99] | 0.37 |
| cjson | seed | 68.9 (10) | 61.8 (10) | -7.16 [-21.47, +0.99] | 0.37 |
| cjson | final | 70.3 (10) | 62.6 (10) | -7.71 [-22.23, +0.45] | 0.33 |

## Exploratory (uncorrected)

| contrast | pairs | pooled mean [95% CI] | parson | tomlc99 | cjson | two-sided p |
|---|---|---|---|---|---|---|
| numbers, names and source minus numbers and names | 30 | -2.16 [-7.51, +1.10] | -6.37 (4/6/0) | -0.77 (5/5/0) | +0.66 (6/4/0) | 0.6341 |
| numbers, names and source minus numbers | 30 | -0.54 [-7.75, +6.99] | -0.59 (5/5/0) | +0.63 (1/9/0) | -1.65 (2/8/0) | 0.9823 |
| menu: proxy summary minus no feedback | 30 | +6.78 [+0.09, +14.12] | +14.20 (7/3/0) | -0.97 (5/5/0) | +7.10 (6/4/0) | 0.1449 |
| no feedback: menu minus plain instruction | 30 | -6.05 [-14.96, +2.68] | -8.21 (2/8/0) | -1.58 (4/5/1) | -8.34 (3/7/0) | 0.1285 |
| proxy summary: menu minus plain instruction | 30 | +0.24 [-0.46, +0.89] | +0.34 (7/3/0) | +1.17 (7/3/0) | -0.80 (3/7/0) | 0.5454 |

## Menu choices (E arms, from the EDIT: line of each refinement response)

- E0: fix_feature_encoding 59, (none named) 36, generate_nesting_toward_cap 35, add_or_upweight_production 16, broaden_exploration 4
- E1: add_or_upweight_production 63, (none named) 38, generate_nesting_toward_cap 31, fix_feature_encoding 16, broaden_exploration 2
