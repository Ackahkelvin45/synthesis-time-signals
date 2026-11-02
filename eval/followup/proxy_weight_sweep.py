"""proxy_weight_sweep.py: sensitivity of the RQ3 validity result to the proxy's weights (review point 8).
For every loop-internal strategy measured for RQ3 (eval/matrix/rq3.jsonl), recompute the proxy score from
the recorded run summary under a grid of weights, and report, per target, the pooled Spearman rho with the
measured primary outcome and the median within-replicate rho. Also each component alone.

    .venv/bin/python eval/followup/proxy_weight_sweep.py > eval/matrix/proxy_weight_sweep.md
"""
import json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "eval"))
from rq3_report import spearman, TARGETS, ARMS, _RX  # noqa: E402
from cell import runs_dir  # noqa: E402

meas = defaultdict(list)
for l in (ROOT / "eval/matrix/rq3.jsonl").read_text().splitlines():
    if not l.strip(): continue
    r = json.loads(l); m = _RX.match(r["condition"])
    if m: meas[(r["target"], m.group(1), int(m.group(2)), int(m.group(3)))].append(0.0 if "error" in r else r["auc_branch_reach"])
rows = defaultdict(list)  # target -> (arm, rep, prod, nov, cap, y)
for t in TARGETS:
    for arm in ARMS:
        for k in range(1, 11):
            for it in range(1, 6):
                s = runs_dir(t) / f"{arm}-rep{k}" / f"iter-{it}" / "stats.json"
                if not s.exists(): continue
                d = json.loads(s.read_text())
                if d.get("gated") or not d.get("summary"): continue
                key = (t, arm, k, it)
                if key not in meas or not meas[key]: continue
                sm = d["summary"]
                rows[t].append((arm, k, len(sm.get("productions_accepted", [])), sm.get("novelty", 0), sm.get("cap_distance_mass", 0.0), st.mean(meas[key])))
GRID = [(5, 1, 20, "paper"), (1, 0, 0, "productions only"), (0, 1, 0, "novelty only"), (0, 0, 1, "cap mass only"),
        (1, 1, 1, "equal"), (5, 1, 0, "no cap"), (0, 1, 20, "no productions"), (5, 0, 20, "no novelty"),
        (10, 1, 20, ""), (2, 1, 20, ""), (5, 1, 50, ""), (5, 1, 5, ""), (5, 5, 20, ""), (20, 1, 20, "")]
print("# Proxy weight sweep (exploratory)\n\nscore = a x productions accepted + b x novelty + c x cap mass, recomputed from each recorded run summary; "
      "rho = Spearman with the measured primary outcome at 1 000 inputs (3 draw seeds); within = median within-replicate rho over replicates with 3 or more points.\n")
print("| a | b | c | note | " + " | ".join(f"{t} pooled / within" for t in TARGETS) + " |\n|---|---|---|---|" + "---|" * len(TARGETS))
for a, b, c, note in GRID:
    cells = []
    for t in TARGETS:
        R = rows[t]; xs = [a * p + b * n + c * m for _, _, p, n, m, _ in R]; ys = [y for *_, y in R]
        by = defaultdict(list)
        for (arm, k, p, n, m, y) in R: by[(arm, k)].append((a * p + b * n + c * m, y))
        w = [spearman([q[0] for q in v], [q[1] for q in v]) for v in by.values() if len(v) >= 3]
        cells.append(f"{spearman(xs, ys):+.2f} / {st.median(w):+.2f}" if xs else "-")
    print(f"| {a} | {b} | {c} | {note} | " + " | ".join(cells) + " |")
