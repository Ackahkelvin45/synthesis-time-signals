# Controlled experiment (json-parser): does grammar-seeding, then refinement, help?

**Design.** Three fixed generators, each measured over **K=12 independent
PRNG seeds** at **N=150 examples/seed**, against `vendor/json-parser/json.c`. Per (seed, condition)
one pass over the coverage build yields both coverage AND the acceptance /
novelty / cap-mass proxy metrics on the *same* inputs. Every input set is drawn
in a history-fixed subprocess and identified by a hash of (strategy source, n,
seed), so the cells reproduce exactly. Values are **mean ± 95% CI** (t-interval)
over the K seeds; comparisons use a two-sided **paired sign-flip permutation
test** (exact enumeration at this K). This replaces a single run's
non-reproducible trajectory (max-of-noise; DECISIONS.md D9) with a claim that
rests on a distribution.

## Results (mean ± 95% CI over seeds)

| Condition | region% | line% | branch% | acceptance | novelty | cap_mass |
|---|---|---|---|---|---|---|
| A. baseline (random) | 29.9±2.0 | 33.6±2.7 | 23.2±1.6 | 0.01±0.00 | 0.9±0.5 | 0.00±0.00 |
| B. seed (iter-1, no refine) | 64.2±0.9 | 74.8±1.0 | 61.2±0.9 | 0.75±0.02 | 15.0±1.4 | 0.00±0.00 |
| C. evolved (iter-5) | 66.7±1.6 | 77.0±1.8 | 63.5±1.5 | 0.61±0.03 | 18.2±1.7 | 0.22±0.07 |

## Significance (paired sign-flip permutation test, exact)
### Grammar-seed (B) vs random baseline (A) — does seeding help?
- region: Δ=+34.4 (95% CI [+32.1, +36.7])  paired p=0.0005, **significant**
- branch: Δ=+37.9 (95% CI [+36.1, +39.7])  paired p=0.0005, **significant**
- novelty: Δ=+14.1 (95% CI [+12.8, +15.3])  paired p=0.0005, **significant**
### Evolved (C) vs grammar-seed (B) — does REFINEMENT help beyond seeding?
- region: Δ=+2.5 (95% CI [+0.9, +4.1])  paired p=0.0068, **significant**
- branch: Δ=+2.3 (95% CI [+0.7, +4.0])  paired p=0.0122, **significant**
- novelty: Δ=+3.2 (95% CI [+1.2, +5.3])  paired p=0.0107, **significant**

## Input sets (hash of strategy source + n + seed; seed index 0..K-1)

- A. baseline (random): `8e8a7bce486076d0`, `53a5e9f2dad316a9`, `b01e3debe957ba61`, `e5407eaefe67efc7`, `54cfa8e4a10afc03`, `c54b0ea4b9d92cd4`, `fe42fb1c544b478c`, `5ef1d9b335534de0`, `2a1f9d8f8c4ce699`, `294dcf75275fa95c`, `9d3a356238d1585e`, `2d241d1ad46c82ec`
- B. seed (iter-1, no refine): `bb4699b3adb82875`, `4f01605ca478dad0`, `a54fba9744a7da85`, `596a673640d80833`, `e4494dafb2167e9b`, `f575524cfd86dd78`, `0922d1933ecdfc1e`, `923f448d6c6610f9`, `67a4ae5d359c7911`, `f771092c4b717c28`, `c02b72964022f9da`, `3aa537038dfcf8ca`
- C. evolved (iter-5): `b9617f5939ccbf97`, `deaa784287865485`, `4f5c38a9fb426b4d`, `a0f9d25b285003de`, `1456a0228bce3824`, `9182f37c4c9731a3`, `68e041fc871fb34d`, `3399865b64e6e085`, `417a21dd6f007fa4`, `c7c3dd7b18b43314`, `214b0c712119d6eb`, `77e2790c9f00bc45`

## Reading it

A comparison is meaningful only if its CIs separate AND the permutation p is
small. **B vs A** tests the project's core premise (grammar-seeding reaches the
value-construction code random bytes miss). **C vs B** is the honest, harder
test the single run could not make: does the feedback loop's refinement add
anything *beyond* the initial grammar-seed, once seed-noise is averaged out? The
numbers above answer both from a distribution rather than one lucky draw —
including the case where refinement's effect is within noise, which is stated
plainly rather than hidden.
