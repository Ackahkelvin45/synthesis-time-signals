"""rq3_report.py — RQ3: does the blind proxy rank generators the way coverage does?

Joins, per target, every loop-internal strategy's recorded proxy score
(iter-N/stats.json: proxy_score; also coverage_in_loop under C3 arms) with its
measured primary outcome from the RQ3 matrix cells (run:<cond>-rep<k>:<N>,
k=3 draw seeds at n=1000, averaged). Spearman rho with a bootstrap CI over
strategies, per target: pooled, within arm, and within replicate (median of
per-replicate rho over replicates with >= 3 strategies). Also the in-loop
pairing for C3 arms: proxy score vs in-loop branch coverage on the same 500
inputs (no measurement needed).

    python rq3_report.py --cells eval/matrix/rq3.jsonl --out eval/matrix/rq3_report.md
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz"), str(ROOT / "fuzz" / "loop")]
from cell import runs_dir  # noqa: E402
from agent import _score  # noqa: E402  (recompute the proxy score from the recorded summary)


def proxy_and_cov(d: dict, arm: str):
    """(proxy score, in-loop branch coverage or None). When an iteration saw a crash the
    loop's triage branch rewrote stats.json without proxy_score / coverage_in_loop; the
    summary survives (proxy recomputed) and `score` survives (== coverage under C3 arms,
    == proxy otherwise)."""
    ps = d.get("proxy_score")
    if ps is None and d.get("summary"):
        ps = _score(d["summary"])
    cov = (d.get("coverage_in_loop") or {}).get("branch_pct")
    if cov is None and arm in ("C3s", "C3n") and d.get("score") is not None:
        cov = d["score"]
    return ps, cov

TARGETS = ("json-parser", "parson", "tomlc99", "cjson")
ARMS = ("C2", "A5", "C3s", "C3n", "C2R", "M2C2", "M2A5", "M2C3s")
_RX = re.compile(r"^run:([A-Za-z0-9]+)-rep(\d+):(\d+)$")


def rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3:
        return float("nan")
    rx, ry = rank(x), rank(y)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def boot(x, y, iters=2000, seed=0):
    rng = random.Random(seed)
    vals = []
    n = len(x)
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(spearman([x[i] for i in idx], [y[i] for i in idx]))
    vals = sorted(v for v in vals if v == v)
    return (vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]) if vals else (float("nan"),) * 2


def line(name, pairs):
    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]
    if len(pairs) < 3:
        return f"- {name}: n = {len(pairs)} (too few)"
    lo, hi = boot(x, y)
    return f"- {name}: rho = {spearman(x, y):+.2f} [{lo:+.2f}, {hi:+.2f}], n = {len(pairs)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="eval/matrix/rq3.jsonl")
    ap.add_argument("--out", default="eval/matrix/rq3_report.md")
    a = ap.parse_args()
    meas = defaultdict(lambda: defaultdict(list))  # (t, arm, rep, it) -> values over seeds
    for l in (ROOT / a.cells).read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        m = _RX.match(r["condition"])
        if not m:
            continue
        key = (r["target"], m.group(1), int(m.group(2)), int(m.group(3)))
        meas[key]["auc"].append(0.0 if "error" in r else r["auc_branch_reach"])
    L = ["# RQ3: proxy score vs measured coverage over loop-internal strategies (exploratory)", "",
         "Each point is one loop iteration's generator: its proxy score as recorded by the loop (stats.json) "
         "against the primary outcome measured afterwards on 3 fresh draw seeds at 1 000 inputs (mean). "
         "Spearman rho with a 2 000-resample bootstrap CI. Under the coverage arms the loop also recorded "
         "branch coverage on the iteration's own 500 inputs, giving a second pairing with no measurement noise.", ""]
    for t in TARGETS:
        pairs_all, by_arm, by_rep, inloop = [], defaultdict(list), defaultdict(list), []
        for arm in ARMS:
            for k in range(1, 11):
                rd = runs_dir(t) / f"{arm}-rep{k}"
                for it in range(1, 6):
                    s = rd / f"iter-{it}" / "stats.json"
                    if not s.exists():
                        continue
                    d = json.loads(s.read_text())
                    if d.get("gated"):
                        continue
                    ps, cov = proxy_and_cov(d, arm)
                    if ps is None:
                        continue
                    if cov is not None:
                        inloop.append((ps, cov))
                    key = (t, arm, k, it)
                    if key in meas and meas[key]["auc"]:
                        y = st.mean(meas[key]["auc"])
                        pairs_all.append((ps, y))
                        by_arm[arm].append((ps, y))
                        by_rep[(arm, k)].append((ps, y))
        if not pairs_all and not inloop:
            continue
        L += [f"## {t}", "", line("pooled, all arms", pairs_all)]
        for arm in ARMS:
            if by_arm[arm]:
                L.append(line(f"within {arm}", by_arm[arm]))
        rhos = [spearman([p[0] for p in v], [p[1] for p in v]) for v in by_rep.values() if len(v) >= 3]
        rhos = [r for r in rhos if r == r]
        if rhos:
            L.append(f"- within replicate (does the proxy rank a run's own iterations as coverage does?): "
                     f"median rho over {len(rhos)} replicates = {st.median(rhos):+.2f}; "
                     f"{sum(r > 0 for r in rhos)} positive, {sum(r < 0 for r in rhos)} negative")
        if inloop:
            L.append(line("in-loop pairing (coverage arms): proxy score vs branch coverage on the same 500 inputs", inloop))
        L.append("")
    (ROOT / a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
