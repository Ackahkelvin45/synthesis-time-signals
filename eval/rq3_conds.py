"""rq3_conds.py — matrix conditions for RQ3 (proxy score vs coverage over every
loop-internal strategy): run:<cond>-rep<k>:<N> for each iteration N whose
stats.json carries a proxy_score (i.e. the iteration ran; gated ones have none).
usage: rq3_conds.py <target> <nshards> [conds]   -> shard lists on stdout"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from cell import runs_dir  # noqa: E402

t, nsh = sys.argv[1], int(sys.argv[2])
conds_in = (sys.argv[3] if len(sys.argv) > 3 else "C2,A5,C3s,C3n").split(",")
conds = []
for c in conds_in:
    for k in range(1, 11):
        rd = runs_dir(t) / f"{c}-rep{k}"
        for it in range(1, 6):
            s = rd / f"iter-{it}" / "stats.json"
            if not s.exists():
                continue
            d = json.loads(s.read_text())
            # An iteration that RAN has a summary (gated ones do not). The crash-triage
            # branch rewrites stats.json without proxy_score, so key on the summary and
            # recompute the proxy score from it in the report.
            if d.get("gated") or "summary" not in d:
                continue
            conds.append(f"run:{c}-rep{k}:{it}")
print(f"# {t}: {len(conds)} iteration strategies", file=sys.stderr)
print(" ".join(",".join(conds[i::nsh]) for i in range(nsh)))
