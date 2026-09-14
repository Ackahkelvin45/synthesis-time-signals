"""equal_time.py — exploratory equal-time views (plan E3): coverage reached within a wall-clock
budget that INCLUDES generation time, per arm and target, for the final and seed generators.

Each matrix row records draw_s (persisted wall time of drawing the 10^4-input set, first draw)
and run_s (batch execution time) plus the coverage curve at log-spaced input counts. The inputs
affordable in T seconds are n_T = min(10^4, T / ((draw_s + run_s) / 10^4)); coverage at n_T is
interpolated on the log-n curve. Draw times were measured under varying machine load (threats).

    python eval/equal_time.py --inputs eval/matrix/stage1.jsonl eval/matrix/stage1c.jsonl eval/matrix/day1.jsonl eval/matrix/stage1c_grammarinator.jsonl --out eval/matrix/equal_time.md
"""
import argparse
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from report import parse_run_cond  # noqa: E402

CPS = [10, 30, 100, 150, 300, 1000, 3000, 10000]
BUDGETS = (300, 1800)
ARMS = ("C2", "A5", "C3s", "C3n", "C2R")


def cov_at(r, n):
    xs = [math.log(c) for c in CPS]
    ys = [r["curve"][str(c)]["branch_reach"] for c in CPS]
    if n <= CPS[0]:
        return ys[0]
    if n >= CPS[-1]:
        return ys[-1]
    x = math.log(n)
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


def value(r, T):
    if "error" in r:
        return 0.0
    per_input = (r["draw_s"] + r["run_s"]) / r["n"]
    return cov_at(r, min(r["n"], T / per_input))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    loop = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    fixed = defaultdict(lambda: defaultdict(dict))
    for p in a.inputs:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("n") != 10000:
                continue
            pr = parse_run_cond(r["condition"])
            if pr:
                loop[r["target"]][pr[0]][pr[1]][pr[2]][r["seed"]] = r
            elif r["condition"] in ("grammarinator", "grammarinator-deep", "random"):
                fixed[r["target"]][r["condition"]][r["seed"]] = r
    L = ["# Equal-time views (exploratory): branch coverage of the reachable region reached within T seconds, generation time included", "",
         "Per replicate the mean over 20 draw seeds; per arm the mean ± 95% CI over replicates. Fixed generators: mean over 20 draw seeds. "
         "Inputs affordable in T = T / (per-input draw + run time of the 10^4 set); coverage interpolated on the log-n curve. "
         "Draw times were measured under varying load; treat differences below a few points as noise.", ""]
    for t in ("json-parser", "parson", "tomlc99", "cjson"):
        L += [f"## {t}", "", "| generator | 5 min | 30 min | inputs affordable in 5 min (median) |", "|---|---|---|---|"]
        for arm in ARMS:
            for what in ("final", "seed"):
                reps = [v[what] for v in loop[t][arm].values() if v.get(what)]
                if not reps:
                    continue
                cells = []
                for T in BUDGETS:
                    vals = [st.mean(value(r, T) for r in rows.values()) for rows in reps]
                    ci = 1.96 * st.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else 0
                    cells.append(f"{st.mean(vals):.1f} ± {ci:.1f}")
                nin = st.median(min(r["n"], 300 / ((r["draw_s"] + r["run_s"]) / r["n"])) for rows in reps for r in rows.values() if "error" not in r)
                L.append(f"| {arm} {what} | {cells[0]} | {cells[1]} | {nin:.0f} |")
        for cond in ("grammarinator", "grammarinator-deep", "random"):
            if cond in fixed[t]:
                rows = fixed[t][cond]
                cells = [f"{st.mean(value(r, T) for r in rows.values()):.1f}" for T in BUDGETS]
                nin = st.median(min(r["n"], 300 / ((r["draw_s"] + r["run_s"]) / r["n"])) for r in rows.values() if "error" not in r)
                L.append(f"| {cond} | {cells[0]} | {cells[1]} | {nin:.0f} |")
        L.append("")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
