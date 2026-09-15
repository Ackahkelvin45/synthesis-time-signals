# Generated tables

## T1. Targets

| target | source | lines | functions | parse-reachable functions | grammar (grammars-v4) | ground-truth bug builds | role |
|-------|----------|-----|--------|----------|--------------|--------------|-----------|
| json-parser | json.c | 1057 | 10 | 9 | JSON.g4 | issue68, issue78 | development (in-sample) |
| parson | parson.c | 2486 | 144 | 40 | JSON.g4 | none | held out |
| cjson | cJSON.c | 3143 | 112 | 13 | JSON.g4 | cve-2023-53154 | held out (Stage 2) |
| tomlc99 | toml.c | 2392 | 82 | 53 | TomlLexer.g4, TomlParser.g4 | issue50, recursion | held out |

## T2. Final-generator level and refinement delta per target and arm

Primary outcome auc_branch_reach (10^4 inputs x 20 draw seeds per replicate; failed cells and collapsed finals score 0). Mean ± 95% CI over ten replicates (median); coll. = collapsed replicates; last working = the last working iteration's level where it differs from the final (n = replicates where it differs). Δ = final − seed per replicate, exact sign-flip test; replicates whose seed generator failed but whose final works are excluded from Δ and counted under seed failed.

| target | arm | final | coll. | Δ final − seed | up / down | sign-flip p | seed failed | last working |
|--------|--------------|-----------------|-----|--------------|-------|--------|-------|-----------|
| json-parser | C2 proxy | 51.0 ± 19.3 (63.9) | 2 | -1.02 ± 0.81 | 2 / 6 | 0.031 | 0 | - |
| json-parser | A5 no steering | 63.7 ± 2.8 (64.6) | 0 | +0.15 ± 1.16 | 6 / 4 | 0.768 | 0 | - |
| json-parser | C3s coverage | 48.8 ± 18.7 (59.4) | 2 | -1.60 ± 1.70 | 2 / 6 | 0.062 | 0 | - |
| json-parser | C3n coverage + names | 54.9 ± 14.0 (61.5) | 1 | -9.20 ± 13.62 | 0 / 10 | 0.002 | 0 | - |
| json-parser | C2R C2' re-seed repair | 63.9 ± 1.3 (64.4) | 0 | -1.32 ± 1.40 | 2 / 7 | 0.074 | 0 | - |
| parson | C2 proxy | 60.9 ± 15.4 (67.1) | 1 | +0.89 ± 0.50 | 7 / 1 | 0.016 | 0 | - |
| parson | A5 no steering | 66.3 ± 1.6 (66.7) | 0 | +0.54 ± 0.75 | 7 / 2 | 0.160 | 0 | - |
| parson | C3s coverage | 69.1 ± 1.1 (69.4) | 0 | +1.59 ± 0.86 | 8 / 2 | 0.008 | 0 | 68.6 (n 1) |
| parson | C3n coverage + names | 66.0 ± 1.3 (65.8) | 0 | -0.16 ± 1.48 | 5 / 5 | 0.797 | 0 | - |
| tomlc99 | C2 proxy | 52.9 ± 13.9 (57.4) | 1 | -0.01 ± 1.10 | 2 / 4 | 1.000 | 1 | - |
| tomlc99 | A5 no steering | 60.2 ± 3.4 (59.8) | 0 | +1.80 ± 2.33 | 6 / 3 | 0.121 | 1 | - |
| tomlc99 | C3s coverage | 55.1 ± 14.1 (60.6) | 1 | +0.22 ± 0.61 | 5 / 1 | 0.438 | 0 | 50.7 (n 6) |
| tomlc99 | C3n coverage + names | 57.4 ± 3.7 (58.5) | 0 | -0.70 ± 0.96 | 0 / 3 | 0.250 | 1 | 51.2 (n 4) |
| tomlc99 | C2R C2' re-seed repair | 59.3 ± 2.4 (60.3) | 0 | -1.41 ± 1.64 | 1 / 7 | 0.086 | 0 | 60.2 (n 3) |
| cjson | C2 proxy | 61.8 ± 15.6 (68.3) | 1 | -0.51 ± 0.46 | 2 / 7 | 0.039 | 0 | 67.1 (n 1) |
| cjson | A5 no steering | 70.3 ± 1.6 (70.1) | 0 | +1.35 ± 1.69 | 6 / 3 | 0.113 | 0 | - |
| cjson | C3s coverage | 64.2 ± 16.2 (72.2) | 1 | +1.15 ± 2.10 | 6 / 2 | 0.234 | 1 | 71.7 (n 2) |
| cjson | C3n coverage + names | 66.6 ± 5.1 (68.8) | 0 | -3.28 ± 6.23 | 2 / 5 | 0.156 | 2 | 60.9 (n 1) |

