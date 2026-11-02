# Equal budget: best of k first drafts against one refined generator (exploratory)

Per target and arm: mean primary outcome of one refined final (ten replicates), of one first draft, and of the best of k first drafts (k drafts of the arm's ten, without replacement, 2 000 resamples); P(best of k > a random final). Cost of k drafts in runs of five iterations: about k/5 of one refined run's API spend.

| target | arm | one final | one seed | best of 2 | best of 3 | best of 5 | P(best of 3 > final) | P(best of 5 > final) |
|---|---|---|---|---|---|---|---|---|
| parson | C2 | 60.9 | 60.0 | 67.5 | 68.1 | 68.7 | 0.56 | 0.65 |
| parson | A5 | 66.3 | 65.8 | 67.0 | 67.5 | 67.8 | 0.70 | 0.77 |
| parson | C3s | 69.1 | 67.5 | 68.6 | 69.0 | 69.6 | 0.49 | 0.63 |
| parson | C3n | 66.0 | 66.1 | 67.2 | 67.7 | 68.2 | 0.84 | 0.88 |
| tomlc99 | C2 | 52.9 | 46.5 | 59.3 | 62.6 | 64.8 | 0.73 | 0.86 |
| tomlc99 | A5 | 60.2 | 52.6 | 60.6 | 62.0 | 64.0 | 0.61 | 0.77 |
| tomlc99 | C3s | 55.1 | 54.9 | 62.8 | 64.0 | 65.4 | 0.72 | 0.79 |
| tomlc99 | C3n | 57.4 | 51.8 | 59.9 | 61.6 | 63.3 | 0.73 | 0.87 |
| cjson | C2 | 61.8 | 62.3 | 70.1 | 71.0 | 72.0 | 0.85 | 0.95 |
| cjson | A5 | 70.3 | 68.9 | 70.2 | 70.9 | 71.5 | 0.59 | 0.69 |
| cjson | C3s | 64.2 | 55.9 | 69.1 | 70.5 | 70.7 | 0.30 | 0.30 |
| cjson | C3n | 66.6 | 55.0 | 68.1 | 70.2 | 70.9 | 0.73 | 0.84 |
| json-parser | C2 | 51.0 | 52.0 | 64.2 | 66.1 | 66.5 | 0.91 | 0.97 |
| json-parser | A5 | 63.7 | 63.5 | 65.5 | 66.1 | 66.5 | 0.68 | 0.70 |
| json-parser | C3s | 48.8 | 50.4 | 62.8 | 65.1 | 66.1 | 0.84 | 0.89 |
| json-parser | C3n | 54.9 | 64.1 | 65.5 | 66.0 | 66.4 | 0.98 | 1.00 |
