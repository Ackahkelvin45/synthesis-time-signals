# Equal-time views (exploratory): branch coverage of the reachable region reached within T seconds, generation time included

Per replicate the mean over 20 draw seeds; per arm the mean ± 95% CI over replicates. Fixed generators: mean over 20 draw seeds. Inputs affordable in T = T / (per-input draw + run time of the 10^4 set); coverage interpolated on the log-n curve. Draw times were measured under varying load; treat differences below a few points as noise.

## json-parser

| generator | 5 min | 30 min | inputs affordable in 5 min (median) |
|---|---|---|---|
| C2 final | 60.6 ± 19.8 | 60.6 ± 19.8 | 10000 |
| C2 seed | 60.3 ± 19.7 | 60.3 ± 19.7 | 10000 |
| A5 final | 76.5 ± 0.6 | 76.5 ± 0.6 | 10000 |
| A5 seed | 75.4 ± 0.8 | 75.4 ± 0.8 | 10000 |
| C3s final | 60.4 ± 19.8 | 60.4 ± 19.8 | 10000 |
| C3s seed | 60.0 ± 19.6 | 60.0 ± 19.6 | 10000 |
| C3n final | 68.3 ± 14.9 | 68.3 ± 14.9 | 10000 |
| C3n seed | 76.0 ± 1.1 | 76.0 ± 1.1 | 10000 |
| C2R final | 76.2 ± 0.7 | 76.2 ± 0.7 | 10000 |
| C2R seed | 75.8 ± 0.8 | 75.8 ± 0.8 | 10000 |
| grammarinator | 68.9 | 68.9 | 10000 |
| grammarinator-deep | 69.3 | 69.3 | 10000 |
| random | 43.1 | 43.1 | 10000 |

## parson

| generator | 5 min | 30 min | inputs affordable in 5 min (median) |
|---|---|---|---|
| C2 final | 70.7 ± 15.4 | 70.7 ± 15.4 | 10000 |
| C2 seed | 70.2 ± 15.3 | 70.2 ± 15.3 | 10000 |
| A5 final | 78.7 ± 1.3 | 78.7 ± 1.3 | 10000 |
| A5 seed | 78.0 ± 1.2 | 78.0 ± 1.2 | 10000 |
| C3s final | 81.6 ± 1.2 | 81.6 ± 1.2 | 10000 |
| C3s seed | 78.4 ± 0.9 | 78.4 ± 0.9 | 10000 |
| C3n final | 78.3 ± 1.1 | 78.3 ± 1.1 | 10000 |
| C3n seed | 78.4 ± 1.0 | 78.4 ± 1.0 | 10000 |
| grammarinator | 71.0 | 71.0 | 10000 |
| grammarinator-deep | 71.2 | 71.2 | 10000 |
| random | 36.1 | 36.1 | 10000 |

## tomlc99

| generator | 5 min | 30 min | inputs affordable in 5 min (median) |
|---|---|---|---|
| C2 final | 71.7 ± 15.8 | 71.7 ± 15.8 | 10000 |
| C2 seed | 63.0 ± 20.8 | 63.1 ± 20.8 | 10000 |
| A5 final | 80.4 ± 2.5 | 80.4 ± 2.5 | 10000 |
| A5 seed | 70.4 ± 15.6 | 70.4 ± 15.6 | 10000 |
| C3s final | 72.0 ± 15.8 | 72.0 ± 15.8 | 10000 |
| C3s seed | 71.9 ± 15.8 | 71.9 ± 15.8 | 10000 |
| C3n final | 77.0 ± 3.1 | 77.0 ± 3.1 | 10000 |
| C3n seed | 69.2 ± 15.3 | 69.2 ± 15.3 | 10000 |
| C2R final | 79.9 ± 1.2 | 79.9 ± 1.2 | 10000 |
| C2R seed | 80.7 ± 1.0 | 80.7 ± 1.0 | 10000 |
| grammarinator | 80.3 | 80.3 | 10000 |
| random | 26.0 | 26.0 | 10000 |

## cjson

| generator | 5 min | 30 min | inputs affordable in 5 min (median) |
|---|---|---|---|
| C2 final | 70.9 ± 15.5 | 70.9 ± 15.5 | 10000 |
| C2 seed | 71.4 ± 15.6 | 71.4 ± 15.6 | 10000 |
| A5 final | 81.8 ± 1.4 | 81.8 ± 1.4 | 10000 |
| A5 seed | 79.4 ± 1.4 | 79.4 ± 1.4 | 10000 |
| C3s final | 73.6 ± 16.1 | 73.6 ± 16.1 | 10000 |
| C3s seed | 63.4 ± 20.7 | 63.4 ± 20.7 | 10000 |
| C3n final | 76.1 ± 4.7 | 76.2 ± 4.7 | 10000 |
| C3n seed | 62.6 ± 20.4 | 62.6 ± 20.4 | 10000 |

