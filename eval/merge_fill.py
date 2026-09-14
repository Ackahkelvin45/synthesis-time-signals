"""merge_fill.py — merge measurement shards into one JSONL, de-duplicated on
(target, condition, seed, n), and make the registered minimum-score rule
explicit for conditions the matrix SKIPPED: when run:<C>-rep<k>:final rows
exist for a target but no run:<C>-rep<k>:seed rows do (no iteration of that
run passed the drawability probe, so resolve_condition returned None), write
20 explicit error rows for the seed so the report scores it 0 rather than
silently dropping the replicate from the paired delta.

    python merge_fill.py --out eval/matrix/day1.jsonl eval/matrix/day1_*_shard*.jsonl
"""
import argparse
import glob
import json
import re
from collections import defaultdict

_RX = re.compile(r"^run:([A-Za-z0-9]+)-rep(\d+):(seed|final|last)$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("inputs", nargs="+")
    a = ap.parse_args()
    rows, seen = [], set()
    for pat in a.inputs:
        for f in sorted(glob.glob(pat)):
            for l in open(f):
                if not l.strip():
                    continue
                r = json.loads(l)
                key = (r["target"], r["condition"], r["seed"], r["n"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(r)
    have = defaultdict(set)
    for r in rows:
        m = _RX.match(r["condition"])
        if m and r["n"] == a.n:
            have[(r["target"], m.group(1), int(m.group(2)))].add(m.group(3))
    filled = []
    for (t, c, k), whats in sorted(have.items()):
        if "final" in whats and "seed" not in whats:
            for s in range(a.k):
                rows.append({"target": t, "condition": f"run:{c}-rep{k}:seed", "seed": s, "n": a.n,
                             "strategy_ref": None,
                             "error": "no iteration of this run produced a drawable generator (matrix skipped the condition); "
                                      "scored as the registered minimum"})
            filled.append(f"{t} {c}-rep{k}")
    with open(a.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"{len(rows)} rows -> {a.out}; filled seed rows for: {filled or 'none'}")


if __name__ == "__main__":
    main()
