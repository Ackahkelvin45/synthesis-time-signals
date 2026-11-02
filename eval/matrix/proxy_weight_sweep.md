# Proxy weight sweep (exploratory)

score = a x productions accepted + b x novelty + c x cap mass, recomputed from each recorded run summary; rho = Spearman with the measured primary outcome at 1 000 inputs (3 draw seeds); within = median within-replicate rho over replicates with 3 or more points.

| a | b | c | note | json-parser pooled / within | parson pooled / within | tomlc99 pooled / within | cjson pooled / within |
|---|---|---|---|---|---|---|---|
| 5 | 1 | 20 | paper | +0.08 / +0.15 | +0.37 / +0.00 | +0.41 / +0.35 | +0.23 / +0.13 |
| 1 | 0 | 0 | productions only | +0.13 / +0.18 | +0.28 / +0.35 | +0.35 / +0.33 | +0.05 / +nan |
| 0 | 1 | 0 | novelty only | +0.04 / +0.20 | +0.37 / +0.35 | +0.43 / +0.26 | +0.37 / -0.05 |
| 0 | 0 | 1 | cap mass only | +nan / +nan | +0.03 / -0.21 | +0.15 / +0.70 | +0.11 / +nan |
| 1 | 1 | 1 | equal | +0.07 / +0.14 | +0.38 / +0.30 | +0.43 / +0.21 | +0.33 / +0.02 |
| 5 | 1 | 0 | no cap | +0.08 / +0.15 | +0.36 / +0.30 | +0.40 / +0.35 | +0.22 / +0.05 |
| 0 | 1 | 20 | no productions | +0.04 / +0.20 | +0.34 / +0.30 | +0.44 / +0.32 | +0.38 / -0.03 |
| 5 | 0 | 20 | no novelty | +0.13 / +0.18 | +0.26 / +0.00 | +0.37 / +0.31 | +0.07 / +0.27 |
| 10 | 1 | 20 |  | +0.08 / +0.15 | +0.35 / +0.00 | +0.39 / +0.33 | +0.18 / +0.13 |
| 2 | 1 | 20 |  | +0.08 / +0.14 | +0.36 / +0.30 | +0.43 / +0.33 | +0.30 / +0.13 |
| 5 | 1 | 50 |  | +0.08 / +0.15 | +0.33 / -0.05 | +0.41 / +0.36 | +0.24 / +0.18 |
| 5 | 1 | 5 |  | +0.08 / +0.15 | +0.37 / +0.20 | +0.41 / +0.35 | +0.22 / +0.13 |
| 5 | 5 | 20 |  | +0.07 / +0.14 | +0.38 / +0.30 | +0.43 / +0.21 | +0.33 / +0.02 |
| 20 | 1 | 20 |  | +0.08 / +0.15 | +0.35 / +0.00 | +0.38 / +0.31 | +0.16 / +0.13 |
