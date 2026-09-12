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

import random as _random  # noqa: E402
import re  # noqa: E402

CI_METRICS = ("region", "line", "branch", "acceptance", "novelty", "cap_mass")
CMP_METRICS = ("region", "branch", "novelty")
# The pre-registered primary outcome, with fallbacks for rows measured before
# the reachable region / curves existed.
PRIMARY_CANDIDATES = ("auc_branch_reach", "branch_reach", "auc_branch", "branch")
_RUN_COND = re.compile(r"^run:([A-Za-z0-9]+)-rep(\d+):(seed|final|last)$")
LOOP_CONDS = ("C2", "A5", "C3s", "C3n")
H1H2 = (("C2", "A5", "H1: proxy (C2) vs no-steering (A5)"),
        ("C3s", "C2", "H2: coverage-scalar (C3s) vs proxy (C2)"),
        ("C3n", "C2", "H2: coverage-named (C3n) vs proxy (C2)"))


# --- replicate-level statistics (unit of analysis = the loop run) ------------

def parse_run_cond(cond: str) -> tuple[str, int, str] | None:
    """'run:C2-rep3:final' -> ('C2', 3, 'final'); None for anything else."""
    m = _RUN_COND.match(cond)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else None


def primary_metric(rows: dict) -> str:
    """First primary-outcome candidate present (and non-null) in the rows."""
    for m in PRIMARY_CANDIDATES:
        if all(r.get(m) is not None for r in rows.values()):
            return m
    return "branch"


def a12(a: list[float], b: list[float]) -> float:
    """Vargha-Delaney A12: P(a > b) + 0.5 P(a == b). 0.5 = no effect."""
    if not a or not b:
        return float("nan")
    gt = eq = 0
    for x in a:
        for y in b:
            gt += x > y
            eq += x == y
    return (gt + 0.5 * eq) / (len(a) * len(b))


def bootstrap_a12(a: list[float], b: list[float], iters: int = 5000, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap 95% CI of A12 (resampling replicates within groups)."""
    rng = _random.Random(seed)
    vals = []
    for _ in range(iters):
        ra = [rng.choice(a) for _ in a]
        rb = [rng.choice(b) for _ in b]
        vals.append(a12(ra, rb))
    vals.sort()
    return vals[int(0.025 * iters)], vals[min(iters - 1, int(0.975 * iters))]


def perm_two_sample(a: list[float], b: list[float], iters: int = 20000, seed: int = 0) -> float:
    """Two-sided permutation test on the difference of means (label shuffling)."""
    if not a or not b:
        return float("nan")
    obs = abs(mean(a) - mean(b))
    pool = list(a) + list(b)
    na = len(a)
    rng = _random.Random(seed)
    hits = 0
    for _ in range(iters):
        rng.shuffle(pool)
        if abs(mean(pool[:na]) - mean(pool[na:])) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (iters + 1)


def replicate_levels(conds: dict, cond_name: str, what: str, metric: str) -> dict[int, float]:
    """{rep: mean over draw seeds of metric} for run:<cond>-rep<k>:<what>."""
    out: dict[int, float] = {}
    for c, rows in conds.items():
        pr = parse_run_cond(c)
        if pr and pr[0] == cond_name and pr[2] == what and rows:
            vals = [r.get(metric) for r in rows.values()]
            if all(v is not None for v in vals):
                out[pr[1]] = mean(vals)
    return out


def replicate_section(target: str, conds: dict) -> list[str]:
    """RQ2 at the replicate level: per-condition levels, per-replicate deltas,
    H1/H2 effect sizes. Draw seeds are averaged WITHIN a replicate first."""
    any_rows = next((rows for c, rows in conds.items() if parse_run_cond(c) and rows), None)
    if any_rows is None:
        return []
    metric = primary_metric(any_rows)
    def _failed_cells(cname: str) -> int:
        return sum(1 for c, rows in conds.items()
                   if (pr := parse_run_cond(c)) and pr[0] == cname and pr[2] == "final"
                   for r in rows.values() if r.get("failed"))
    L = [f"### Replicate level (unit = loop run; primary outcome `{metric}`)", "",
         "| condition | replicates | failed cells (scored 0) | final: mean ± 95% CI | last-iteration mean | "
         "Δ final−seed per replicate: mean ± 95% CI | sign-flip p |",
         "|---|---|---|---|---|---|---|"]
    levels: dict[str, dict[int, float]] = {}
    for cname in LOOP_CONDS:
        fin = replicate_levels(conds, cname, "final", metric)
        if not fin:
            continue
        levels[cname] = fin
        seedl = replicate_levels(conds, cname, "seed", metric)
        lastl = replicate_levels(conds, cname, "last", metric)
        reps = sorted(fin)
        mu, h = ci95([fin[r] for r in reps])
        last_txt = f"{mean([lastl[r] for r in reps if r in lastl]):.1f}" if lastl else "—"
        paired_reps = [r for r in reps if r in seedl]
        if len(paired_reps) >= 2:
            d, dh, pv = paired_perm_test([seedl[r] for r in paired_reps], [fin[r] for r in paired_reps])
            delta_txt = f"{d:+.1f} ± {dh:.1f} (n={len(paired_reps)})"
            p_txt = f"{pv:.4f}"
        else:
            delta_txt, p_txt = "—", "—"
        L.append(f"| {cname} | {len(reps)} | {_failed_cells(cname)} | {mu:.1f} ± {h:.1f} | {last_txt} | {delta_txt} | {p_txt} |")
    L.append("")
    for hi, lo, label in H1H2:
        if hi in levels and lo in levels:
            a = [levels[hi][r] for r in sorted(levels[hi])]
            b = [levels[lo][r] for r in sorted(levels[lo])]
            eff = a12(a, b)
            lo_ci, hi_ci = bootstrap_a12(a, b)
            pv = perm_two_sample(a, b)
            L.append(f"- **{label}**: Δmean={mean(a) - mean(b):+.2f}, A12={eff:.2f} "
                     f"(95% bootstrap CI [{lo_ci:.2f}, {hi_ci:.2f}]), permutation p={pv:.4f}, "
                     f"n={len(a)} vs {len(b)}")
    L.append("")
    return L



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
            if "error" in r:
                # A cell whose generator could not produce its input set scores the
                # MINIMUM on every metric (the loop handed back an unusable
                # generator; pre-registered: gated iterations count as they
                # happened). Flagged so the report counts failed cells per condition.
                r = {**r, "failed": True, **{m: 0.0 for m in
                     ("region", "line", "branch", "branch_reach", "region_reach", "line_reach",
                      "auc_branch", "auc_region", "auc_branch_reach", "auc_region_reach",
                      "acceptance", "novelty", "cap_mass", "productions", "crashes")}}
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
    text = render(data, inp)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)
    print(f"[report] wrote {_rel(out)}")
    return 0


def render(data: dict, inp: Path) -> str:
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
                v = [rows[s].get(m) for s in sorted(rows)]
                v = [x for x in v if x is not None]
                if not v:
                    cells.append("—")
                    continue
                mu, h = ci95(v)
                cells.append(fmt(mu, h, m))
            L.append(f"| {cond} | {len(rows)} | " + " | ".join(cells) + " |")

        # core comparisons
        L += ["", "### Core comparisons (paired by seed)", ""]
        for lo, hi, rq in (("random", "seed", "RQ1 seeding"),
                           ("grammarinator", "seed", "RQ1 authorship: seed vs Grammarinator (defaults)"),
                           ("grammarinator-deep", "seed", "RQ1 authorship: seed vs Grammarinator (depth-matched)"),
                           ("random", "grammarinator", "RQ1 grammar alone: Grammarinator vs random"),
                           ("seed", "evolved", "RQ2 refinement (pilot run)")):
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
        fam = [c for c in conds if c.startswith("run:") and not parse_run_cond(c)]
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

        L += replicate_section(target, conds)

    if core_deltas:
        L += ["## Cross-target summary (mean of per-target paired deltas)", "",
              "| comparison | " + " | ".join(CMP_METRICS) + " | targets |", "|---|" + "---|" * (len(CMP_METRICS) + 1)]
        for rq, byM in core_deltas.items():
            nt = max(len(v) for v in byM.values())
            L.append(f"| {rq} | " + " | ".join(
                f"{mean(byM[m]):+.1f}" if byM[m] else "—" for m in CMP_METRICS) + f" | {nt} |")
        L.append("")

    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
