"""tables.py — generated paper tables (never hand-edited).

T1  targets: source lines, functions, parse-reachable region size, grammar, ground-truth bugs
T2  per target and arm: final level (mean ± 95% CI, median), collapsed replicates,
    per-replicate delta final − seed (mean ± CI, sign-flip p), last-working level where it differs

    python eval/tables.py --inputs eval/matrix/stage1.jsonl eval/matrix/stage1c.jsonl eval/matrix/day1.jsonl --out eval/matrix/tables.md
"""
import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from targets import TARGETS  # noqa: E402
from cell import measure_for_loop  # noqa: E402
from experiment import ci95, paired_perm_test  # noqa: E402
from full_report import load, level, collapsed  # noqa: E402

ARMS = ("C2", "A5", "C3s", "C3n", "C2R")
LABEL = {"C2": "proxy", "A5": "no steering", "C3s": "coverage", "C3n": "coverage + names", "C2R": "C2' re-seed repair"}


def t1():
    L = ["## T1. Targets", "", "| target | source | lines | functions | parse-reachable functions | grammar (grammars-v4) | ground-truth bug builds | role |",
         "|---|---|---|---|---|---|---|---|"]
    role = {"json-parser": "development (in-sample)", "parson": "held out", "tomlc99": "held out", "cjson": "held out (Stage 2)"}
    for t, v in TARGETS.items():
        src = ROOT / v["src"]
        lines = sum(1 for _ in src.open())
        r = json.loads((ROOT / "eval" / "reachable" / f"{t}.json").read_text())
        reach = len(set(r["static"]) | set(r.get("observed_extra", [])))
        total = measure_for_loop(t, ["[1]"], f"t1_{t}")["functions_total"]
        bugs = ", ".join(v.get("bugs", {}).keys()) or "none"
        gram = ", ".join(Path(g).name for g in v.get("grammars", (v["grammar"],)))
        L.append(f"| {t} | {Path(v['src']).name} | {lines} | {total} | {reach} | {gram} | {bugs} | {role[t]} |")
    return L + [""]


def t2(data):
    L = ["## T2. Final-generator level and refinement delta per target and arm", "",
         "Primary outcome auc_branch_reach (10^4 inputs x 20 draw seeds per replicate; failed cells and collapsed finals score 0). "
         "Mean ± 95% CI over ten replicates (median). Δ = final − seed per replicate, exact sign-flip test; replicates whose seed "
         "generator failed but whose final works are excluded from Δ and counted in the last column.", "",
         "| target | arm | final | collapsed | Δ final − seed | up / down | sign-flip p | seed failed, final works | last working where it differs |",
         "|---|---|---|---|---|---|---|---|---|"]
    for t in ("json-parser", "parson", "tomlc99", "cjson"):
        d = data[t]
        for c in ARMS:
            fin, seed = level(d, c, "final"), level(d, c, "seed")
            if not fin:
                continue
            mu, h = ci95(list(fin.values()))
            col = collapsed(d, c)
            reps = [k for k in sorted(fin) if k in seed]
            infl = [k for k in reps if all(x == 0.0 for x in d[c][k]["seed"].values()) and fin[k] > 0]
            ok = [k for k in reps if k not in infl]
            if len(ok) >= 2:
                dd, half, p = paired_perm_test([seed[k] for k in ok], [fin[k] for k in ok])
                ds = [fin[k] - seed[k] for k in ok]
                dcell, ud, pcell = f"{dd:+.2f} ± {half:.2f}", f"{sum(x > 0 for x in ds)} / {sum(x < 0 for x in ds)}", f"{p:.3f}"
            else:
                dcell = ud = pcell = "-"
            last = level(d, c, "last")
            lcell = f"{st.mean(last.values()):.1f} (n {len(last)})" if last else "-"
            L.append(f"| {t} | {c} {LABEL[c]} | {mu:.1f} ± {h:.1f} ({st.median(fin.values()):.1f}) | {len(col)} | {dcell} | {ud} | {pcell} | "
                     f"{len(infl)} | {lcell} |")
    return L + [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data, _ = load(a.inputs)
    L = ["# Generated tables", ""] + t1() + t2(data)
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
