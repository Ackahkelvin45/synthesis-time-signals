# Proxy-signal validation against coverage (json-parser; measurement only)

**Question.** Coverage instrumentation is forbidden for *steering* the
loop. Post-hoc, does the blind proxy signal the loop actually steered by
correlate with the code coverage it could not see? This audits the central
design bet.

**Method.** For each committed iteration's *effective* strategy, 300 seeded
examples are drawn once (in a history-fixed subprocess, hashed) and used for
BOTH measurements, so proxy and coverage describe the same inputs: coverage of
`vendor/json-parser/json.c` on the `-fcoverage-mapping` build, and the proxy signal via the
loop's own `summarize()`. Spearman rho is computed across the five iterations.

**Caveat (read first).** n = 5 is small and **line coverage saturates at
iteration 1** (every production appears immediately), so line coverage
cannot move and is not the basis for any correlation. The informative axes
are **region** and **branch** coverage vs. the depth/diversity proxy
components. Treat rho values as exploratory, reported with their n.

## Per-iteration measurements

| iter | strategy | region% | line% | branch% | acc | prods | cap_mass | novelty | score | input set |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | strategy_fix.py | 67.9 | 79.5 | 65.4 | 0.85 | 7 | 0.00 | 18 | 53.0 | `154e0bb3f362379a` |
| 2 | strategy.py | 63.2 | 73.8 | 60.3 | 0.87 | 7 | 0.31 | 16 | 57.2 | `b0ccec9deced9c97` |
| 3 | strategy.py | 67.6 | 78.8 | 65.6 | 0.79 | 7 | 0.24 | 26 | 65.9 | `2d6ec091406c3cc0` |
| 4 | strategy.py | 66.3 | 76.5 | 62.0 | 0.81 | 7 | 0.34 | 25 | 66.8 | `e79ce3b4203aca2a` |
| 5 | strategy.py | 70.6 | 79.3 | 66.2 | 0.71 | 7 | 0.27 | 29 | 69.4 | `a593b88220578d15` |

## Correlation (Spearman rho, n=5)

| proxy component | vs region cov | vs branch cov |
|---|---|---|
| score | +0.300 | +0.500 |
| novelty | +0.700 | +0.900 |
| cap_mass | -0.600 | -0.500 |
| productions | +0.000 | +0.000 |
| acceptance | -0.700 | -0.900 |

## Reading it

A positive rho means the proxy component moved together with real coverage
across iterations — evidence the blind signal was tracking something the
loop could not observe. A near-zero or negative rho for a component means it
was *not* a good coverage proxy at this budget, which is itself an honest,
useful result: it says which parts of the hand-designed signal earned their
place and which did not. With n=5 and saturating line coverage this is an
exploratory audit, not a significance test; the value is in *doing* the
post-hoc validation the assignment's 'why did you expect it to work?' asks
for, rather than asserting the signal was good.
