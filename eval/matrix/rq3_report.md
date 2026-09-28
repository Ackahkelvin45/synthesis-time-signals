# RQ3: proxy score vs measured coverage over loop-internal strategies (exploratory)

Each point is one loop iteration's generator: its proxy score as recorded by the loop (stats.json) against the primary outcome measured afterwards on 3 fresh draw seeds at 1 000 inputs (mean). Spearman rho with a 2 000-resample bootstrap CI. Under the coverage arms the loop also recorded branch coverage on the iteration's own 500 inputs, giving a second pairing with no measurement noise.

## json-parser

- pooled, all arms: rho = +0.08 [-0.06, +0.21], n = 208
- within C2: rho = +0.19 [-0.15, +0.50], n = 39
- within A5: rho = -0.15 [-0.44, +0.17], n = 43
- within C3s: rho = +0.06 [-0.30, +0.40], n = 37
- within C3n: rho = +0.09 [-0.19, +0.35], n = 45
- within C2R: rho = +0.24 [-0.07, +0.51], n = 44
- within replicate (does the proxy rank a run's own iterations as coverage does?): median rho over 43 replicates = +0.10; 23 positive, 18 negative
- in-loop pairing (coverage arms): proxy score vs branch coverage on the same 500 inputs: rho = +0.35 [+0.13, +0.54], n = 82

## parson

- pooled, all arms: rho = +0.37 [+0.23, +0.49], n = 192
- within C2: rho = +0.06 [-0.30, +0.38], n = 45
- within A5: rho = +0.55 [+0.34, +0.70], n = 50
- within C3s: rho = +0.09 [-0.23, +0.40], n = 48
- within C3n: rho = +0.09 [-0.23, +0.40], n = 49
- within replicate (does the proxy rank a run's own iterations as coverage does?): median rho over 38 replicates = +0.00; 18 positive, 18 negative
- in-loop pairing (coverage arms): proxy score vs branch coverage on the same 500 inputs: rho = +0.53 [+0.43, +0.61], n = 146

## tomlc99

- pooled, all arms: rho = +0.41 [+0.28, +0.52], n = 204
- within C2: rho = +0.43 [+0.10, +0.69], n = 34
- within A5: rho = +0.59 [+0.30, +0.79], n = 46
- within C3s: rho = +0.21 [-0.21, +0.59], n = 32
- within C3n: rho = +0.44 [+0.17, +0.66], n = 45
- within C2R: rho = +0.13 [-0.17, +0.41], n = 47
- within replicate (does the proxy rank a run's own iterations as coverage does?): median rho over 44 replicates = +0.35; 28 positive, 14 negative
- in-loop pairing (coverage arms): proxy score vs branch coverage on the same 500 inputs: rho = +0.51 [+0.36, +0.65], n = 111

## cjson

- pooled, all arms: rho = +0.23 [+0.08, +0.36], n = 175
- within C2: rho = +0.45 [+0.16, +0.66], n = 40
- within A5: rho = +0.21 [-0.10, +0.48], n = 48
- within C3s: rho = -0.12 [-0.39, +0.17], n = 39
- within C3n: rho = +0.34 [+0.05, +0.58], n = 48
- within replicate (does the proxy rank a run's own iterations as coverage does?): median rho over 37 replicates = +0.10; 20 positive, 17 negative
- in-loop pairing (coverage arms): proxy score vs branch coverage on the same 500 inputs: rho = +0.30 [+0.11, +0.47], n = 87

