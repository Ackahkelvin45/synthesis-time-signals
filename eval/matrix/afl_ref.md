# T7. AFL++ reference row

afl-clang-fast (-O2, no sanitizers), afl-fuzz defaults, one valid seed per format, fixed wall-clock budget, no dictionary; the final queue replayed in creation order through the study's coverage build. Branch coverage of the parse-reachable region at the end of the queue (mean ± 95% CI over runs); the loop arms' numbers at 10^4 inputs are in Table 2 for comparison (not equal-n: AFL's queue is the set of coverage-increasing inputs, so its size is not comparable to a generator's input count).

| target | runs | budget (s) | queue size | execs/s | crashes saved | branch coverage of reachable region (final queue) |
|---|---|---|---|---|---|---|
| json-parser | 5 | 3600 | 760 | 1709 | 0 | 81.2 ± 0.4 |
| parson | 5 | 3600 | 430 | 1713 | 0 | 81.5 ± 0.8 |
| cjson | 5 | 3600 | 484 | 1652 | 0 | 82.8 ± 0.1 |
| tomlc99 | 5 | 3600 | 1004 | 1673 | 0 | 89.5 ± 0.3 |
