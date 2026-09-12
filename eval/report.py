"""report.py — aggregate an experiment-matrix JSONL (eval/matrix.py) into the
paper's per-RQ tables. MEASUREMENT ONLY.

For every (target, condition): mean +/- 95% CI per metric over seeds.
Comparisons (paired by seed; only seeds present under BOTH conditions count):
  seed    vs random     RQ1 — does grammar-seeding help?
  evolved vs seed       RQ2 — does refinement help beyond seeding?
  run:*   vs evolved    RQ3/RQ5 — each ablation / other-model run against the
                        full loop; this family is Holm-Bonferroni corrected
                        within each target because it is several tests at once.
Each comparison reports the paired mean difference, its 95% CI, the exact
paired sign-flip permutation p, and (for the family) the Holm-adjusted p.
Cross-target summary = the mean of per-target deltas; seeds are never pooled
across targets as if they were one population (absolute coverage is not
comparable across targets).

    .venv/bin/python eval/report.py [--in eval/matrix/main.jsonl] [--out eval/matrix/report.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from experiment import ci95, mean, paired_perm_test  # noqa: E402  (shared stats)

CI_METRICS = ("region", "line", "branch", "acceptance", "novelty", "cap_mass")
CMP_METRICS = ("region", "branch", "novelty")


def _rel(p: Path) -> str:
    """Repo-relative for display, or absolute when outside the repo (scratch dirs)."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def holm(pvals: list[float]) -> list[float]:
    """Holm–Bonferroni step-down adjustment; returns adjusted p in input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def load(path: Path) -> dict:
    """-> data[target][condition][seed] = row"""
    data: dict = defaultdict(lambda: defaultdict(dict))
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            data[r["target"]][r["condition"]][r["seed"]] = r
    return data


def fmt(mu: float, h: float, m: str) -> str:
    return f"{mu:.1f}±{h:.1f}" if m in ("region", "line", "branch", "novelty") else f"{mu:.2f}±{h:.2f}"


def paired(rows_lo: dict, rows_hi: dict, metric: str):
    seeds = sorted(set(rows_lo) & set(rows_hi))
    if len(seeds) < 2:
        return None
    lo = [rows_lo[s][metric] for s in seeds]
    hi = [rows_hi[s][metric] for s in seeds]
    d, half, p = paired_perm_test(lo, hi)
    return {"n": len(seeds), "delta": d, "half": half, "p": p}


def main() -> int:
    ap = argparse.ArgumentParser(description="aggregate matrix results")
    ap.add_argument("--in", dest="inp", default="eval/matrix/main.jsonl")
    ap.add_argument("--out", default="eval/matrix/report.md")
    args = ap.parse_args()
    inp = ROOT / args.inp if not Path(args.inp).is_absolute() else Path(args.inp)
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    if not inp.exists():
        print(f"[report] no matrix file at {inp}; run eval/matrix.py first")
        return 1
    data = load(inp)

    L = ["# Experiment matrix report", "",
         f"Source: `{_rel(inp)}`. Values are mean ± 95% CI over seeds; "
         "comparisons are paired by seed (exact sign-flip permutation test). The "
         "`run:*` family is Holm-corrected within each target. Absolute coverage is not "
         "comparable across targets; compare conditions within a target.", ""]

    core_deltas: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for target in sorted(data):
        conds = data[target]
        L += [f"## {target}", "", "### Results (mean ± 95% CI over seeds)", "",
              "| condition | seeds | " + " | ".join(CI_METRICS) + " |",
              "|---|---|" + "---|" * len(CI_METRICS)]
        for cond in sorted(conds, key=lambda c: (c.startswith("run:"), c)):
            rows = conds[cond]
            cells = []
            for m in CI_METRICS:
                v = [rows[s][m] for s in sorted(rows)]
                mu, h = ci95(v)
                cells.append(fmt(mu, h, m))
            L.append(f"| {cond} | {len(rows)} | " + " | ".join(cells) + " |")

        # core comparisons
        L += ["", "### Core comparisons (paired by seed)", ""]
        for lo, hi, rq in (("random", "seed", "RQ1 seeding"), ("seed", "evolved", "RQ2 refinement")):
            if lo in conds and hi in conds:
                L.append(f"**{rq}: {hi} vs {lo}**")
                for m in CMP_METRICS:
                    r = paired(conds[lo], conds[hi], m)
                    if r is None:
                        L.append(f"- {m}: not enough paired seeds")
                        continue
                    sig = "**significant**" if r["p"] < 0.05 else "not significant"
                    L.append(f"- {m}: Δ={r['delta']:+.1f} (95% CI [{r['delta']-r['half']:+.1f}, "
                             f"{r['delta']+r['half']:+.1f}]), n={r['n']}, paired p={r['p']:.4f}, {sig}")
                    core_deltas[rq][m].append(r["delta"])
                L.append("")

        # the run:* family (ablations / other models) vs the full loop, Holm-corrected
        fam = [c for c in conds if c.startswith("run:")]
        if fam and "evolved" in conds:
            L += ["### Ablation / other-run family vs evolved (Holm-corrected within target)", ""]
            for m in CMP_METRICS:
                results = [(c, paired(conds["evolved"], conds[c], m)) for c in fam]
                valid = [(c, r) for c, r in results if r is not None]
                if not valid:
                    continue
                adj = holm([r["p"] for _, r in valid])
                L.append(f"**{m}** (Δ = run − evolved; negative = removing it hurt)")
                for (c, r), pa in zip(valid, adj):
                    sig = "**significant**" if pa < 0.05 else "n.s."
                    L.append(f"- {c}: Δ={r['delta']:+.1f} (95% CI [{r['delta']-r['half']:+.1f}, "
                             f"{r['delta']+r['half']:+.1f}]), n={r['n']}, p={r['p']:.4f}, "
                             f"Holm p={pa:.4f}, {sig}")
                L.append("")

    if core_deltas:
        L += ["## Cross-target summary (mean of per-target paired deltas)", "",
              "| comparison | " + " | ".join(CMP_METRICS) + " | targets |", "|---|" + "---|" * (len(CMP_METRICS) + 1)]
        for rq, byM in core_deltas.items():
            nt = max(len(v) for v in byM.values())
            L.append(f"| {rq} | " + " | ".join(
                f"{mean(byM[m]):+.1f}" if byM[m] else "—" for m in CMP_METRICS) + f" | {nt} |")
        L.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L))
    print("\n".join(L))
    print(f"[report] wrote {_rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
