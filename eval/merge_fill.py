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
    # A run whose every iteration was build-rejected has no strategy file at
    # all, so the matrix skipped BOTH its conditions ("no loop run for it
    # yet"). Under the registered rule it is a collapsed replicate: 20
    # explicit error rows for seed and final each, scored 0.
    from pathlib import Path
    for (t, c, k) in sorted({(t, c, k) for (t, c, k) in have}):
        for j in range(1, 11):
            if (t, c, j) in have:
                continue
            fj = Path(__file__).resolve().parent.parent / "runs" / t / f"{c}-rep{j}" / "final.json"
            if fj.exists() and json.load(open(fj)).get("has_strategy") is False:
                have[(t, c, j)] = set()
    for (t, c, k), whats in sorted(have.items()):
        if not whats:
            for what in ("seed", "final"):
                for s in range(a.k):
                    rows.append({"target": t, "condition": f"run:{c}-rep{k}:{what}", "seed": s, "n": a.n,
                                 "strategy_ref": None,
                                 "error": "every iteration of this run was build-rejected (no strategy file; matrix skipped both conditions); "
                                          "scored as the registered minimum"})
            filled.append(f"{t} {c}-rep{k} (seed+final)")
            continue
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
