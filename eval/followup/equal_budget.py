"""equal_budget.py: best-of-k independent first drafts against one refined generator (exploratory,
after the review of October 2026). Uses the existing measurement rows: every replicate's seed and
final generator on the same 20 draw seeds. For each target and arm, draws k of the arm's ten seed
generators without replacement (2 000 resamples), takes the best seed-level mean, and compares it
with a random replicate's final-level mean. Collapsed finals and failed seeds score 0, as pre-specified.

    .venv/bin/python eval/followup/equal_budget.py > eval/matrix/equal_budget.md
"""
import json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "eval"))
from report import parse_run_cond  # noqa: E402
ARMS = ("C2", "A5", "C3s", "C3n")
data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))  # t arm rep what seed
for src in ("stage1", "stage1c", "day1", "day2"):
    for line in (ROOT / "eval/matrix" / f"{src}.jsonl").read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line); pr = parse_run_cond(r["condition"])
        if pr and pr[0] in ARMS and pr[2] in ("seed", "final"):
            data[r["target"]][pr[0]][pr[1]][pr[2]][r["seed"]] = 0.0 if "error" in r else r["auc_branch_reach"]
rng = random.Random(0)
print("# Equal budget: best of k first drafts against one refined generator (exploratory)\n")
print("Per target and arm: mean primary outcome of one refined final (ten replicates), of one first draft, and of the best of k first drafts "
      "(k drafts of the arm's ten, without replacement, 2 000 resamples); P(best of k > a random final). Cost of k drafts in runs of five iterations: about k/5 of one refined run's API spend.\n")
print("| target | arm | one final | one seed | best of 2 | best of 3 | best of 5 | P(best of 3 > final) | P(best of 5 > final) |\n|---|---|---|---|---|---|---|---|---|")
for t in ("parson", "tomlc99", "cjson", "json-parser"):
    for a in ARMS:
        reps = sorted(data[t][a]); seeds = [st.mean(data[t][a][k]["seed"].values()) for k in reps]
        finals = [st.mean(data[t][a][k]["final"].values()) for k in reps]
        best = {}
        for k in (2, 3, 5):
            best[k] = [max(rng.sample(seeds, k)) for _ in range(2000)]
        p3 = st.mean(b > f for b in best[3] for f in finals); p5 = st.mean(b > f for b in best[5] for f in finals)
        print(f"| {t} | {a} | {st.mean(finals):.1f} | {st.mean(seeds):.1f} | {st.mean(best[2]):.1f} | {st.mean(best[3]):.1f} | {st.mean(best[5]):.1f} | {p3:.2f} | {p5:.2f} |")
