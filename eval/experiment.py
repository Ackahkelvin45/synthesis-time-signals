"""experiment.py — EVALUATION ONLY. A controlled, multi-seed experiment:
does grammar-seeding, and then feedback refinement, MEASURABLY beat the baseline?

Motivation. A single unseeded run is max-of-noise (DECISIONS.md D9): its
trajectory does not reproduce. Rather than claim per-iteration improvement from
one lucky draw, this runs a proper experiment — three fixed generators, each
measured over K independent PRNG seeds — and reports mean +/- 95% CI with a
paired, exact permutation test. The claim then rests on a distribution.

Conditions (all fixed strategies; nothing is re-run through the LLM here):
  A. baseline   random `st.text()`                              (no grammar knowledge)
  B. seed       iteration-1's effective grammar-seeded strategy (NO refinement)
  C. evolved    iteration-5's strategy                          (AFTER refinement)

Per (seed, condition) ONE pass over N reproducible examples (eval/cell.py:
history-fixed subprocess draws, cached and hashed) through the target's
coverage build yields region/line/branch coverage AND the proxy metrics on the
same inputs. Then across the K seeds: mean +/- std, a 95% CI, and a PAIRED
sign-flip permutation test — the correct analysis for this randomized block
design (every seed runs under every condition) — for the two comparisons that
matter:
  grammar-seed vs random baseline   (does grammar-seeding help?)
  evolved vs grammar-seed           (does REFINEMENT help, beyond seeding?)

    .venv/bin/python eval/experiment.py [--target T] [--k 12] [--n 150] [--out F]
    # default: json-parser, K=12, N=150 -> eval/experiment.md
    # other targets -> eval/experiment_<target>.md (needs a loop run under runs/<target>/)
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from cell import (BUILTIN_TEXT, build_coverage_binary, final_strategy_path,  # noqa: E402
                  measure_ref, runs_dir, seed_strategy_path, target_src)

PERM_ITERS = 20000
PERM_SEED = 12345


# --- statistics (no scipy) -------------------------------------------------

def mean(v): return sum(v) / len(v)


def std(v):
    m = mean(v)
    return (sum((x - m) ** 2 for x in v) / (len(v) - 1)) ** 0.5 if len(v) > 1 else 0.0


# two-sided 95% t-multipliers by dof (n-1), small-sample table; ~1.96 asymptote.
_T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36,
        8: 2.31, 9: 2.26, 10: 2.23, 11: 2.20, 12: 2.18, 14: 2.14, 16: 2.12,
        19: 2.09, 24: 2.06, 29: 2.05}


def ci95(v):
    n = len(v)
    if n < 2:
        return (mean(v), 0.0)
    dof = n - 1
    t = _T95.get(dof) or next((_T95[k] for k in sorted(_T95) if k >= dof), 1.96)
    return (mean(v), t * std(v) / (n ** 0.5))


def paired_perm_test(lo: list[float], hi: list[float],
                     iters: int = PERM_ITERS) -> tuple[float, float, float]:
    """Paired sign-flip permutation test for a randomized BLOCK design: the same
    K seeds are run under every condition, so measurements are paired by seed and
    the correct analysis conditions on that block. Tests whether the per-seed
    difference (hi - lo) has zero mean; each seed's difference-sign is independent
    under H0. Exact enumeration (2^K) when K is small. Returns
    (mean_diff, ci95_halfwidth_of_diff, p_value)."""
    diffs = [h - l for h, l in zip(hi, lo)]
    obs = abs(mean(diffs))
    n = len(diffs)
    _, half = ci95(diffs)                      # CI of the paired differences
    if n <= 20:                                # exact: enumerate all sign flips
        hits = total = 0
        for mask in range(1 << n):
            signed = [diffs[i] if (mask >> i) & 1 else -diffs[i] for i in range(n)]
            total += 1
            if abs(mean(signed)) >= obs - 1e-12:
                hits += 1
        return mean(diffs), half, hits / total
    rng = random.Random(PERM_SEED)             # sampled for large K
    hits = 0
    for _ in range(iters):
        signed = [d if rng.random() < 0.5 else -d for d in diffs]
        if abs(mean(signed)) >= obs - 1e-12:
            hits += 1
    return mean(diffs), half, (hits + 1) / (iters + 1)


# --- the experiment ---------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="multi-seed A/B/C coverage experiment")
    ap.add_argument("--target", default="json-parser")
    ap.add_argument("--k", type=int, default=12, help="seeds per cell")
    ap.add_argument("--n", type=int, default=150, help="examples per seed")
    ap.add_argument("--out", default=None, help="markdown output path")
    args = ap.parse_args()
    target, K, N = args.target, args.k, args.n
    out_path = Path(args.out) if args.out else (
        ROOT / "eval" / ("experiment.md" if target == "json-parser" else f"experiment_{target}.md"))

    rd = runs_dir(target)
    seed_p, final_p = seed_strategy_path(rd), final_strategy_path(rd)
    if seed_p is None or final_p is None:
        print(f"[exp] {target}: no usable loop run under {rd.relative_to(ROOT)}/ "
              f"(seed={seed_p}, final={final_p}). Run the loop with --target {target} first.")
        return 1

    print(f"[exp] {target}: building coverage binary; K={K} seeds x N={N} examples x 3 conditions")
    build_coverage_binary(target)

    # Strategies by REFERENCE so every cell's inputs are reproducible and hashed.
    # `seed` = the run's first WORKING iteration; `evolved` = the loop's OUTPUT
    # after any revert (cell.seed_strategy_path / final_strategy_path). On the
    # json-parser run these resolve to iter-1 (repaired) and iter-5, as before.
    final_label = "loop output" if final_p.name == "final_strategy.py" else final_p.parent.name
    conditions = {
        "A. baseline (random)": BUILTIN_TEXT,
        f"B. seed ({seed_p.parent.name}, no refine)": str(seed_p),
        f"C. evolved ({final_label})": str(final_p),
    }
    metrics = ["region", "line", "branch", "acceptance", "novelty", "cap_mass"]
    data = {c: {m: [] for m in metrics} for c in conditions}
    input_sets = {c: [] for c in conditions}

    for si, seed in enumerate(range(K)):
        for ci, (cname, ref) in enumerate(conditions.items()):
            r = measure_ref(target, ref, N, seed, f"exp_{ci}_{si}")
            for m in metrics:
                data[cname][m].append(r[m])
            input_sets[cname].append(r["input_set"])
        print(f"[exp] seed {seed}: "
              + " | ".join(f"{c.split('.')[0]} reg={mean(data[c]['region']):.1f}"
                           for c in conditions))

    agg = {c: {m: ci95(data[c][m]) for m in metrics} for c in conditions}
    names = list(conditions)

    def fmt(c, m):
        mu, h = agg[c][m]
        return f"{mu:.1f}±{h:.1f}" if m in ("region", "line", "branch", "novelty") \
            else f"{mu:.2f}±{h:.2f}"

    src_rel = target_src(target).relative_to(ROOT)
    lines = [
        f"# Controlled experiment ({target}): does grammar-seeding, then refinement, help?",
        "",
        f"**Design.** Three fixed generators, each measured over **K={K} independent",
        f"PRNG seeds** at **N={N} examples/seed**, against `{src_rel}`. Per (seed, condition)",
        "one pass over the coverage build yields both coverage AND the acceptance /",
        "novelty / cap-mass proxy metrics on the *same* inputs. Every input set is drawn",
        "in a history-fixed subprocess and identified by a hash of (strategy source, n,",
        "seed), so the cells reproduce exactly. Values are **mean ± 95% CI** (t-interval)",
        "over the K seeds; comparisons use a two-sided **paired sign-flip permutation",
        "test** (exact enumeration at this K). This replaces a single run's",
        "non-reproducible trajectory (max-of-noise; DECISIONS.md D9) with a claim that",
        "rests on a distribution.",
        "",
        "## Results (mean ± 95% CI over seeds)",
        "",
        "| Condition | region% | line% | branch% | acceptance | novelty | cap_mass |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in names:
        lines.append("| " + c + " | " + " | ".join(
            fmt(c, m) for m in ["region", "line", "branch", "acceptance", "novelty", "cap_mass"]) + " |")

    def comp(lo, hi, label):
        out = [f"### {label}"]
        for m in ("region", "branch", "novelty"):
            d, half, p = paired_perm_test(data[lo][m], data[hi][m])
            sig = "**significant**" if p < 0.05 else "not significant"
            out.append(f"- {m}: Δ={d:+.1f} (95% CI [{d-half:+.1f}, {d+half:+.1f}])  "
                       f"paired p={p:.4f}, {sig}")
        return out

    lines += ["", "## Significance (paired sign-flip permutation test, exact)"]
    lines += comp(names[0], names[1], "Grammar-seed (B) vs random baseline (A) — does seeding help?")
    lines += comp(names[1], names[2], "Evolved (C) vs grammar-seed (B) — does REFINEMENT help beyond seeding?")
    lines += [
        "",
        "## Input sets (hash of strategy source + n + seed; seed index 0..K-1)",
        "",
    ]
    for c in names:
        lines.append(f"- {c}: " + ", ".join(f"`{s}`" for s in input_sets[c]))
    lines += [
        "",
        "## Reading it",
        "",
        "A comparison is meaningful only if its CIs separate AND the permutation p is",
        "small. **B vs A** tests the project's core premise (grammar-seeding reaches the",
        "value-construction code random bytes miss). **C vs B** is the honest, harder",
        "test the single run could not make: does the feedback loop's refinement add",
        "anything *beyond* the initial grammar-seed, once seed-noise is averaged out? The",
        "numbers above answer both from a distribution rather than one lucky draw —",
        "including the case where refinement's effect is within noise, which is stated",
        "plainly rather than hidden.",
        "",
    ]
    out_path.write_text("\n".join(lines))
    print("\n".join(lines[lines.index("## Results (mean ± 95% CI over seeds)"):]))
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:  # --out outside the repo (e.g. a scratch dir)
        shown = out_path
    print(f"[exp] wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
