"""sensitivity.py — the design's sensitivity for the power statement.

For two arms of n replicates each, simulate the registered test (two-sample
permutation p on the difference of means; A12 with a bootstrap CI) under a
shifted-normal alternative with the observed replicate SD, and report the
smallest true A12 (equivalently, the smallest mean shift in AUC points) at
which the permutation test rejects at 0.05 with 80% probability, and at which
the bootstrap CI of A12 excludes 0.5 with 80% probability. Observed SDs are
taken from the healthy replicates of each target (collapsed replicates are
zeros and would inflate the SD; both SDs are reported).

    python sensitivity.py
"""
from __future__ import annotations

import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from report import a12, parse_run_cond  # noqa: E402


def perm_p(a, b, iters=2000, rng=None):
    obs = abs(st.mean(a) - st.mean(b))
    pool = a + b
    na = len(a)
    hits = 0
    for _ in range(iters):
        rng.shuffle(pool)
        if abs(st.mean(pool[:na]) - st.mean(pool[na:])) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (iters + 1)


def boot_excludes_half(a, b, iters=500, rng=None):
    vals = []
    for _ in range(iters):
        vals.append(a12([rng.choice(a) for _ in a], [rng.choice(b) for _ in b]))
    vals.sort()
    lo, hi = vals[int(0.025 * iters)], vals[int(0.975 * iters) - 1]
    return lo > 0.5 or hi < 0.5


def power(shift, sd, n=10, sims=300, seed=0):
    rng = random.Random(seed)
    rej = ci = 0
    for _ in range(sims):
        a = [rng.gauss(shift, sd) for _ in range(n)]
        b = [rng.gauss(0.0, sd) for _ in range(n)]
        rej += perm_p(a, b, rng=rng) < 0.05
        ci += boot_excludes_half(a, b, rng=rng)
    return rej / sims, ci / sims


def true_a12(shift, sd):
    # P(X > Y) for X ~ N(shift, sd), Y ~ N(0, sd): Phi(shift / (sd*sqrt2))
    return 0.5 * (1 + math.erf(shift / (sd * math.sqrt(2)) / math.sqrt(2)))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="eval/matrix/stage1.jsonl,eval/matrix/day2.jsonl")
    ap.add_argument("--targets", default="json-parser,parson,tomlc99,cjson")
    args = ap.parse_args()
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for src in args.inputs.split(","):
        if not (ROOT / src).exists():
            continue
        for line in (ROOT / src).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            pr = parse_run_cond(r["condition"])
            if pr and pr[2] == "final" and pr[0] in ("C2", "A5"):
                data[r["target"]][pr[0]][pr[1]][r["seed"]] = 0.0 if "error" in r else r["auc_branch_reach"]
    print("| target | arm | SD all replicates | SD healthy | shift for 80% power (perm) | A12 at that shift | shift for 80% CI-excludes-0.5 |")
    print("|---|---|---|---|---|---|---|")
    for t in [t for t in args.targets.split(",") if t in data]:
        for arm in ("C2", "A5"):
            reps = [st.mean(v.values()) for v in data[t][arm].values()]
            healthy = [x for x in reps if x > 0]
            sd_all, sd_h = st.stdev(reps), st.stdev(healthy)
            found_p = found_ci = None
            for shift in [x * 0.5 for x in range(1, 40)]:
                p, c = power(shift, sd_h)
                if found_p is None and p >= 0.8:
                    found_p = shift
                if found_ci is None and c >= 0.8:
                    found_ci = shift
                if found_p and found_ci:
                    break
            print(f"| {t} | {arm} | {sd_all:.1f} | {sd_h:.1f} | {found_p} | {true_a12(found_p, sd_h):.2f} | {found_ci} |")


if __name__ == "__main__":
    main()
