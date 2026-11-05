"""replication_seeds.py: the pre-registered draft rule (PLAN_replication.md, section 3).

For each target, replication replicate k takes the iteration-1 generator of the k-th bridge replicate
(B5-rep1, B5-rep2, ... in order) whose iteration-1 generator draws: all 20 seed cells
(run:B5-rep<j>:seed, seeds 0..19) measured without error. Writes eval/followup/replication_seeds.json.
The second study (PLAN_replication2.md) runs it with --arm B6 --need 20 --out replication2_seeds.json.

    .venv/bin/python eval/followup/replication_seeds.py --inputs eval/matrix/replication.jsonl
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "eval"))
from report import parse_run_cond  # noqa: E402

TARGETS, NEED, SEEDS = ("parson", "tomlc99", "cjson"), 10, 20


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--arm", default="B5"); ap.add_argument("--need", type=int, default=NEED)
    ap.add_argument("--out", default="replication_seeds.json"); a = ap.parse_args()
    ok = defaultdict(lambda: defaultdict(dict))
    for src in a.inputs:
        for line in Path(src).read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line); pr = parse_run_cond(r["condition"])
            if pr and pr[0] == a.arm and pr[2] == "seed":
                ok[r["target"]][pr[1]][r["seed"]] = "error" not in r
    out, short = {}, []
    for t in TARGETS:
        good = [j for j in sorted(ok[t]) if len(ok[t][j]) == SEEDS and all(ok[t][j].values())]
        if len(good) < a.need: short.append(f"{t}: {len(good)} drawing drafts of {len(ok[t])} measured")
        out[t] = {str(k + 1): j for k, j in enumerate(good[:a.need])}
    if short:
        raise SystemExit("too few drawing drafts, run more bridge replicates (plan section 3): " + "; ".join(short))
    (ROOT / "eval" / "followup" / a.out).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
