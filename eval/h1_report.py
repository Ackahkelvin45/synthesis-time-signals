"""h1_report.py — the per-target H1 report in the registered structure.

For each target with C2/A5 replicate runs measured (run:<C>-rep<k>:final and
:seed cells): final level per replicate (mean over draw seeds of the primary
outcome, failed cells scored 0), per-replicate paired delta (final − seed),
difference of replicate means, Vargha-Delaney A12 with percentile-bootstrap
95% CI, two-sample permutation p, each against the registered bands; the
same delta statistics on healthy replicates only (collapsed = the loop's
final generator could not draw, i.e. every seed cell failed); data-integrity
lines; and Stage 1 spend.

    python eval/h1_report.py --in eval/matrix/stage1.jsonl --out eval/matrix/h1_report.md
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from experiment import ci95, paired_perm_test  # noqa: E402
from report import a12, bootstrap_a12, perm_two_sample, parse_run_cond, PRIMARY_CANDIDATES  # noqa: E402
from cell import runs_dir  # noqa: E402

BANDS = "A12 >= 0.64 (or <= 0.36) practical; 0.56-0.64 (0.36-0.44) small; otherwise negligible"


def band(v: float) -> str:
    d = abs(v - 0.5)
    size = "practical" if d >= 0.14 else ("small" if d >= 0.06 else "negligible")
    if size == "negligible":
        return size
    return f"{size}, favouring {'C2' if v > 0.5 else 'A5'}"


def load(path: Path) -> dict:
    """data[target][cond][rep][what][seed] = value (failed cells -> 0.0)"""
    data: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    meta: dict = defaultdict(lambda: {"rows": 0, "backends": set(), "shas": set(), "failed": 0})
    metric = None
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        pr = parse_run_cond(r["condition"])
        if not pr:
            continue
        cond, rep, what = pr
        t = r["target"]
        m = meta[t]
        m["rows"] += 1
        if "error" in r:
            m["failed"] += 1
            v = 0.0
        else:
            if metric is None:
                metric = next(k for k in PRIMARY_CANDIDATES if r.get(k) is not None)
            v = r[metric]
            m["backends"].add(r.get("features_backend"))
            m["shas"].add(r.get("reachable_region_sha"))
        data[t][cond][rep][what][r["seed"]] = v
    return data, meta, metric or "auc_branch_reach"


def rep_level(d: dict, cond: str, what: str) -> dict[int, float]:
    return {k: st.mean(v[what].values()) for k, v in sorted(d[cond].items()) if v.get(what)}


def collapsed_reps(d: dict, cond: str) -> set[int]:
    """Replicates whose final generator produced no measurable input set."""
    return {k for k, v in d[cond].items() if v.get("final") and all(x == 0.0 for x in v["final"].values())}


def fmt_ci(vals: list[float]) -> str:
    mu, h = ci95(vals)
    return f"{mu:.1f} ± {h:.1f} (median {st.median(vals):.1f})"


def compare(c2: dict[int, float], a5: dict[int, float]) -> str:
    a = [c2[k] for k in sorted(c2)]
    b = [a5[k] for k in sorted(a5)]
    eff = a12(a, b)
    lo, hi = bootstrap_a12(a, b)
    p = perm_two_sample(a, b)
    return (f"difference of means (C2 − A5) = {st.mean(a) - st.mean(b):+.2f}; A12 = {eff:.2f} "
            f"(bootstrap 95% CI [{lo:.2f}, {hi:.2f}]) → {band(eff)}; permutation p = {p:.4f}; "
            f"n = {len(a)} vs {len(b)}")


def deltas_line(name: str, seed: dict[int, float], fin: dict[int, float]) -> list[str]:
    reps = [k for k in sorted(fin) if k in seed]
    ds = [fin[k] - seed[k] for k in reps]
    if len(reps) < 2:
        return [f"- {name}: fewer than 2 paired replicates"]
    d, half, p = paired_perm_test([seed[k] for k in reps], [fin[k] for k in reps])
    pos = sum(1 for x in ds if x > 0)
    neg = sum(1 for x in ds if x < 0)
    return [f"- {name}: per-replicate Δ(final − seed) = "
            + ", ".join(f"r{k}:{fin[k] - seed[k]:+.1f}" for k in reps)
            + f"; mean {d:+.2f} ± {half:.2f}; {pos} positive / {neg} negative / {len(ds) - pos - neg} zero of {len(ds)}; "
              f"sign-flip p = {p:.4f}"]


def reruns(target: str) -> str:
    """Failed/rerun rows from the batch manifests that include this target."""
    out = []
    for mf in sorted((ROOT / "runs" / "_batches").glob("*/manifest.jsonl")):
        rows = [json.loads(l) for l in mf.read_text().splitlines() if l.strip()]
        mine = [r for r in rows if r.get("target") == target]
        if not mine:
            continue
        failed = [r for r in mine if r.get("status") == "failed"]
        ok = [r for r in mine if r.get("status") == "ok"]
        served = sorted({m for r in ok for m in r.get("served_models", [])})
        out.append(f"{mf.parent.name}: {len(ok)} ok, {len(failed)} failed rows"
                   + (f" ({', '.join(sorted({r['name'] for r in failed}))}; each rerun after a network outage, "
                      f"no tokens spent)" if failed else "")
                   + f", served {served}")
    return "; ".join(out) or "no manifest"


def spend() -> tuple[float, dict[str, float]]:
    per: dict[str, float] = {}
    for t in ("json-parser", "parson", "tomlc99"):
        tot = 0.0
        for c in ("C2", "A5"):
            for k in range(1, 11):
                f = runs_dir(t) / f"{c}-rep{k}" / "final.json"
                if f.exists():
                    tot += json.loads(f.read_text()).get("est_usd", 0.0)
        per[t] = round(tot, 3)
    return round(sum(per.values()), 3), per


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="eval/matrix/stage1.jsonl")
    ap.add_argument("--out", default="eval/matrix/h1_report.md")
    args = ap.parse_args()
    data, meta, metric = load(ROOT / args.inp)
    L = ["# Stage 1 H1 report (registered structure)", "",
         f"Primary outcome `{metric}` (10^4 inputs x 20 fresh draw seeds per replicate; failed cells "
         f"scored 0). Unit = loop replicate. Bands: {BANDS}. Source `{args.inp}`.", ""]
    for t in ("json-parser", "parson", "tomlc99"):
        if t not in data or "C2" not in data[t] or "A5" not in data[t]:
            continue
        d = data[t]
        c2f, a5f = rep_level(d, "C2", "final"), rep_level(d, "A5", "final")
        c2s, a5s = rep_level(d, "C2", "seed"), rep_level(d, "A5", "seed")
        col = collapsed_reps(d, "C2")
        col5 = collapsed_reps(d, "A5")
        L += [f"## {t}", "",
              "### C2 vs A5 (registered analysis, all replicates)", "",
              f"- C2 final: {fmt_ci(list(c2f.values()))}; replicate means "
              + ", ".join(f"{c2f[k]:.1f}" for k in sorted(c2f)),
              f"- A5 final: {fmt_ci(list(a5f.values()))}; replicate means "
              + ", ".join(f"{a5f[k]:.1f}" for k in sorted(a5f)),
              *deltas_line("C2", c2s, c2f), *deltas_line("A5", a5s, a5f),
              f"- {compare(c2f, a5f)}",
              f"- unusable final generators (collapsed): C2 {len(col)} of {len(c2f)} "
              f"({', '.join(f'rep{k}' for k in sorted(col)) or 'none'}); A5 {len(col5)} of {len(a5f)}", ""]
        h2f = {k: v for k, v in c2f.items() if k not in col}
        h2s = {k: v for k, v in c2s.items() if k not in col}
        L += ["### Healthy-replicate contrast (exploratory: collapsed C2 replicates excluded)", "",
              f"- C2 healthy final: {fmt_ci(list(h2f.values()))}" if h2f else "- C2 healthy: none",
              *deltas_line("C2 healthy", h2s, h2f),
              f"- {compare(h2f, a5f)}" if len(h2f) >= 2 else "- too few healthy replicates", ""]
        m = meta[t]
        L += ["### Data integrity", "",
              f"- matrix rows: {m['rows']} (expect 800 = 20 conditions x 20 seeds; final + seed), "
              f"failed cells {m['failed']}",
              f"- runs: C2 {len(c2f)}, A5 {len(a5f)} (expect 10 each); reruns: {reruns(t)}",
              f"- features_backend: {sorted(x for x in m['backends'] if x)}; reachable_region_sha: "
              f"{sorted(x for x in m['shas'] if x)}", ""]
    total, per = spend()
    L += ["## Stage 1 spend", "",
          f"- per target (est. from per-run token counts at .env prices): {per}",
          f"- total {total:.3f} USD of the registered 4.00 USD Stage 1 ceiling (10.00 USD hard cap)", ""]
    out = ROOT / args.out
    out.write_text("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
