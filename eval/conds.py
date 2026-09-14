"""Print matrix condition shards for one loop arm: final + seed per replicate,
plus :last where the last working iteration differs from the loop's final.
usage: conds.py <target> <cond> <nshards>"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from cell import runs_dir, last_strategy_path, final_strategy_path  # noqa: E402

t, cond, nsh = sys.argv[1], sys.argv[2], int(sys.argv[3])
conds, lasts = [], []
for k in range(1, 11):
    rd = runs_dir(t) / f"{cond}-rep{k}"
    conds += [f"run:{cond}-rep{k}:final", f"run:{cond}-rep{k}:seed"]
    if len(sys.argv) > 4 and sys.argv[4] == "last":
        f, last = final_strategy_path(rd), last_strategy_path(rd)
        if last and f and last.read_text().strip() != f.read_text().strip():
            conds.append(f"run:{cond}-rep{k}:last")
            lasts.append(k)
print("# last differs from final for reps:", lasts, file=sys.stderr)
shards = [conds[i::nsh] for i in range(nsh)]
print(" ".join(",".join(s) for s in shards))
