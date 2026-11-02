"""shared_seed_report.py: the shared-seed, common-policy follow-up (review of October 2026, points 1 and 2).

Arms SF0 (no feedback), SF1 (proxy summary), SF2 (coverage numbers), SF3 (numbers + names) all start from
the same first draft per replicate number (the A5 iteration-1 generator), receive the same edit instruction,
and keep the last working generator; only the feedback text differs. Every contrast is therefore paired on
the seed. Exploratory, outside the confirmatory family.

Inputs: the measured finals (run:SF<a>-rep<k>:final rows) and the A5 seed rows (run:A5-rep<k>:seed), same
20 draw seeds. A collapsed final scores 0, as everywhere else in the paper.

    .venv/bin/python eval/followup/shared_seed_report.py --inputs eval/matrix/stage1.jsonl eval/matrix/day1.jsonl \
        eval/matrix/day2.jsonl eval/matrix/sf.jsonl > eval/matrix/shared_seed.md
"""
import argparse, json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "eval"))
from report import parse_run_cond, a12  # noqa: E402

ARMS = {"SF0": "no feedback", "SF1": "proxy summary", "SF2": "coverage numbers", "SF3": "numbers + names"}
CONTRASTS = [("SF1", "SF0"), ("SF2", "SF0"), ("SF3", "SF0"), ("SF2", "SF1"), ("SF3", "SF1"), ("SF3", "SF2")]


def sign_flip_p(d, iters=20000, seed=0):
    rng = random.Random(seed); obs = abs(st.mean(d)); hits = 0
    for _ in range(iters):
        hits += abs(st.mean(x if rng.random() < 0.5 else -x for x in d)) >= obs - 1e-12
    return (hits + 1) / (iters + 1)


def ci(vals, seed=0):
    rng = random.Random(seed); v = sorted(st.mean(rng.choices(vals, k=len(vals))) for _ in range(5000))
    return v[125], v[4874]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", nargs="+", required=True); a = ap.parse_args()
    lvl = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))  # target -> arm -> rep -> seed -> value
    for src in a.inputs:
        for line in Path(src).read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line); pr = parse_run_cond(r["condition"])
            if not pr: continue
            arm, k, what = pr
            if arm in ARMS and what == "final":
                lvl[r["target"]][arm][k][r["seed"]] = 0.0 if "error" in r else r["auc_branch_reach"]
            elif arm == "A5" and what == "seed":
                lvl[r["target"]]["seed"][k][r["seed"]] = 0.0 if "error" in r else r["auc_branch_reach"]
    print("# Shared-seed, common-policy follow-up (exploratory)\n")
    print("Four arms branched from the same first draft per replicate; same edit instruction; last-working selection; only the feedback shown differs. "
          "Primary outcome, 20 draw seeds, collapsed finals at 0. Paired on the seed; exact sign-flip test on the paired differences; A12 on the paired differences against 0 is not reported, A12 between arms is.\n")
    for t in ("parson", "tomlc99", "cjson"):
        d = lvl[t]
        if not any(d[arm] for arm in ARMS): continue
        reps = sorted(set.intersection(*[set(d[arm]) for arm in ARMS]) & set(d["seed"]))
        if not reps: continue
        mean = lambda arm, k: st.mean(d[arm][k].values())  # noqa: E731
        print(f"## {t} (n = {len(reps)} shared seeds)\n")
        print("| arm | final mean ± 95% CI | collapsed | Δ final − shared seed, mean ± 95% CI | up / down / zero | sign-flip p |\n|---|---|---|---|---|---|")
        for arm in ARMS:
            fin = [mean(arm, k) for k in reps]; dd = [mean(arm, k) - mean("seed", k) for k in reps]
            lo, hi = ci(fin); dlo, dhi = ci(dd)
            print(f"| {arm} {ARMS[arm]} | {st.mean(fin):.1f} [{lo:.1f}, {hi:.1f}] | {sum(x == 0 for x in fin)} | {st.mean(dd):+.2f} [{dlo:+.2f}, {dhi:+.2f}] | "
                  f"{sum(x > 0 for x in dd)} / {sum(x < 0 for x in dd)} / {sum(x == 0 for x in dd)} | {sign_flip_p(dd):.3f} |")
        print("\n| contrast | paired Δ mean [95% CI] | up / down / zero | sign-flip p | A12 (unpaired) |\n|---|---|---|---|---|")
        for x, y in CONTRASTS:
            dd = [mean(x, k) - mean(y, k) for k in reps]; lo, hi = ci(dd)
            print(f"| {x} vs {y} | {st.mean(dd):+.2f} [{lo:+.2f}, {hi:+.2f}] | {sum(v > 0 for v in dd)} / {sum(v < 0 for v in dd)} / {sum(v == 0 for v in dd)} | "
                  f"{sign_flip_p(dd):.3f} | {a12([mean(x, k) for k in reps], [mean(y, k) for k in reps]):.2f} |")
        print()


if __name__ == "__main__":
    main()
