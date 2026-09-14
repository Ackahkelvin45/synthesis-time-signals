"""full_report.py — the complete per-target report in the registered structure, every arm.

Per target: per-arm level (mean, CI, median, replicate means), per-replicate delta
(final minus seed, exact sign-flip; replicates whose seed generator failed but whose
final works are flagged and the delta restated without them), last-working-iteration
level, collapsed count; the confirmatory family {H1: C2 vs A5, H2s: C3s vs C2, H2n:
C3n vs C2} with A12, bootstrap CI, permutation p and Holm within target over the
members actually run; C2R vs C2 and vs A5 as the follow-up; healthy-only contrasts
(exploratory); integrity lines; per-target mechanism table (gate-event paths) for all
arms; spend. Failed cells score 0 as registered.

    python full_report.py --inputs eval/matrix/stage1.jsonl eval/matrix/stage1c.jsonl eval/matrix/day1.jsonl --out eval/matrix/full_report.md
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from experiment import ci95, paired_perm_test  # noqa: E402
from report import a12, bootstrap_a12, perm_two_sample, parse_run_cond, holm  # noqa: E402
from cell import runs_dir  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage1c_report import gate_paths, path_table  # noqa: E402

METRIC = "auc_branch_reach"
TARGETS = ("json-parser", "parson", "tomlc99", "cjson")
ARMS = ("C2", "A5", "C3s", "C3n", "C2R", "M2C2", "M2A5", "M2C3s")
FAMILY = (("C2", "A5", "H1: C2 vs A5"), ("C3s", "C2", "H2s: C3s vs C2"), ("C3n", "C2", "H2n: C3n vs C2"))
BANDS = "A12 >= 0.64 (or <= 0.36) practical; 0.56-0.64 (0.36-0.44) small; otherwise negligible"


def band(v, a, b):
    d = abs(v - 0.5)
    size = "practical" if d >= 0.14 else ("small" if d >= 0.06 else "negligible")
    return size if size == "negligible" else f"{size}, favouring {a if v > 0.5 else b}"


def load(paths):
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    meta = defaultdict(lambda: {"rows": defaultdict(int), "failed": defaultdict(int), "shas": set(), "backends": set()})
    seen = set()
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            pr = parse_run_cond(r["condition"])
            if not pr or r.get("n") != 10000:
                continue
            key = (r["target"], r["condition"], r["seed"])
            if key in seen:
                continue
            seen.add(key)
            cond, rep, what = pr
            m = meta[r["target"]]
            m["rows"][cond] += 1
            if "error" in r:
                m["failed"][cond] += 1
                v = 0.0
            else:
                v = r[METRIC]
                m["shas"].add(r.get("reachable_region_sha"))
                m["backends"].add(r.get("features_backend"))
            data[r["target"]][cond][rep][what][r["seed"]] = v
    return data, meta


def level(d, cond, what):
    return {k: st.mean(v[what].values()) for k, v in sorted(d[cond].items()) if v.get(what)}


def collapsed(d, cond):
    return sorted(k for k, v in d[cond].items() if v.get("final") and all(x == 0.0 for x in v["final"].values()))


def fmt(vals):
    mu, h = ci95(vals)
    return f"{mu:.1f} ± {h:.1f} (median {st.median(vals):.1f})"


def arm_lines(d, cond):
    fin, seed = level(d, cond, "final"), level(d, cond, "seed")
    out = [f"- {cond} final: {fmt(list(fin.values()))}; replicate means " + ", ".join(f"{fin[k]:.1f}" for k in sorted(fin))]
    reps = [k for k in sorted(fin) if k in seed]
    if len(reps) >= 2:
        dd, half, p = paired_perm_test([seed[k] for k in reps], [fin[k] for k in reps])
        ds = [fin[k] - seed[k] for k in reps]
        pos, neg = sum(x > 0 for x in ds), sum(x < 0 for x in ds)
        out.append(f"- {cond}: Δ(final − seed) = " + ", ".join(f"r{k}:{fin[k] - seed[k]:+.1f}" for k in reps)
                   + f"; mean {dd:+.2f} ± {half:.2f}; {pos} up / {neg} down / {len(ds) - pos - neg} zero of {len(ds)}; sign-flip p = {p:.4f}")
        infl = [k for k in reps if all(x == 0.0 for x in d[cond][k]["seed"].values()) and fin[k] > 0]
        if infl:
            ok = [k for k in reps if k not in infl]
            if len(ok) >= 2:
                dd2, half2, p2 = paired_perm_test([seed[k] for k in ok], [fin[k] for k in ok])
                out.append(f"- {cond}: seed failed but final works for " + ", ".join(f"rep{k}" for k in infl)
                           + f" (delta inflated by the whole final level); without them mean {dd2:+.2f} ± {half2:.2f}, p = {p2:.4f}, n = {len(ok)}")
    last = level(d, cond, "last")
    if last:
        out.append(f"- {cond} last working iteration where it differs from final ({len(last)} replicates): {fmt(list(last.values()))}")
    col = collapsed(d, cond)
    out.append(f"- {cond} collapsed (final unusable, scored 0): {len(col)} of {len(fin)}" + (f" ({', '.join(f'rep{k}' for k in col)})" if col else ""))
    return out


def compare(d, a, b):
    fa, fb = level(d, a, "final"), level(d, b, "final")
    x, y = [fa[k] for k in sorted(fa)], [fb[k] for k in sorted(fb)]
    eff = a12(x, y)
    lo, hi = bootstrap_a12(x, y)
    p = perm_two_sample(x, y)
    return (f"Δmean ({a} − {b}) = {st.mean(x) - st.mean(y):+.2f}; A12 = {eff:.2f} [{lo:.2f}, {hi:.2f}] → {band(eff, a, b)}; "
            f"permutation p = {p:.4f}; n = {len(x)} vs {len(y)}"), p


def healthy(d, a, b):
    ca, cb = set(collapsed(d, a)), set(collapsed(d, b))
    x = [v for k, v in level(d, a, "final").items() if k not in ca]
    y = [v for k, v in level(d, b, "final").items() if k not in cb]
    if len(x) < 2 or len(y) < 2:
        return f"{a} vs {b} healthy only: too few"
    eff = a12(x, y)
    lo, hi = bootstrap_a12(x, y)
    return (f"{a} vs {b}, healthy only (exploratory): {st.mean(x):.1f} (n {len(x)}) vs {st.mean(y):.1f} (n {len(y)}); "
            f"A12 = {eff:.2f} [{lo:.2f}, {hi:.2f}] → {band(eff, a, b)}; p = {perm_two_sample(x, y):.4f}")


def spend(t, c):
    return sum(json.loads(f.read_text()).get("est_usd", 0.0) for f in runs_dir(t).glob(f"{c}-rep*/final.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data, meta = load(a.inputs)
    L = ["# Stage 1 full report (registered structure, every arm)", "",
         f"Primary outcome `{METRIC}` (10^4 inputs x 20 fresh draw seeds per replicate; failed cells scored 0, so a "
         f"collapsed replicate scores 0 and a seed generator that cannot draw scores 0). Unit = loop replicate. "
         f"Bands: {BANDS}. Confirmatory family per target: H1, H2s, H2n (Holm over the members run). C2R is a follow-up "
         f"outside the family. Sources: {', '.join(a.inputs)}.", ""]
    for t in TARGETS:
        d = data[t]
        arms = [c for c in ARMS if c in d and level(d, c, "final")]
        if not arms:
            continue
        L += [f"## {t}", "", "### Per arm", ""]
        for c in arms:
            L += arm_lines(d, c)
        L += ["", "### Confirmatory family", ""]
        fam = [(x, y, name) for x, y, name in FAMILY if x in arms and y in arms]
        res = [(name, *compare(d, x, y)) for x, y, name in fam]
        adj = holm([p for _, _, p in res]) if res else []
        for (name, text, p), ap_ in zip(res, adj):
            L.append(f"- {name}: {text}; Holm-adjusted p = {ap_:.4f}")
        if "C2R" in arms:
            L += ["", "### Follow-up: C2R (repair by re-seed)", "",
                  f"- C2R vs C2: {compare(d, 'C2R', 'C2')[0]}",
                  f"- C2R vs A5: {compare(d, 'C2R', 'A5')[0]}"]
        if "M2C2" in arms:
            L += ["", "### RQ5: the three-way under the second model (gpt-5-mini; exploratory, outside the family)", "",
                  f"- M2 H1, M2C2 vs M2A5: {compare(d, 'M2C2', 'M2A5')[0]}",
                  f"- M2 H2s, M2C3s vs M2C2: {compare(d, 'M2C3s', 'M2C2')[0]}",
                  f"- M2C3s vs M2A5 (context): {compare(d, 'M2C3s', 'M2A5')[0]}",
                  f"- cross-model, same arm: C2 vs M2C2: {compare(d, 'C2', 'M2C2')[0]}",
                  f"- cross-model, same arm: A5 vs M2A5: {compare(d, 'A5', 'M2A5')[0]}",
                  f"- cross-model, same arm: C3s vs M2C3s: {compare(d, 'C3s', 'M2C3s')[0]}"]
        L += ["", "### Exploratory contrasts", ""]
        for x, y, _ in fam:
            L.append(f"- {healthy(d, x, y)}")
        if "C3s" in arms and "A5" in arms:
            L.append(f"- C3s vs A5 (context): {compare(d, 'C3s', 'A5')[0]}")
        if "C3n" in arms and "A5" in arms:
            L.append(f"- C3n vs A5 (context): {compare(d, 'C3n', 'A5')[0]}")
        if "C3n" in arms and "C3s" in arms:
            L.append(f"- C3n vs C3s (context): {compare(d, 'C3n', 'C3s')[0]}")
        m = meta[t]
        L += ["", "### Data integrity", ""]
        for c in arms:
            L.append(f"- {c}: rows {m['rows'][c]}, failed cells {m['failed'][c]}, runs {len(level(d, c, 'final'))}")
        L.append(f"- reachable_region_sha {sorted(x for x in m['shas'] if x)}; features_backend {sorted(x for x in m['backends'] if x)}")
        L += ["", "### Mechanism: path after a gate event (log-only, exploratory)", "",
              "| arm | path | cases | next iteration recovered | code similarity to the failed iteration |", "|---|---|---|---|---|"]
        for c in arms:
            rows = [gate_paths(t, c, k) for k in range(1, 11) if (runs_dir(t) / f"{c}-rep{k}" / "evolution.md").exists()]
            L += path_table(rows, c)
            col = sum(r["collapsed"] for r in rows)
            rs = [s for r in rows for s in r["repair_sims"]]
            L.append(f"| {c} | (summary) | collapsed {col}/{len(rows)} | iteration-1 gate events {sum(r['iter1_gated'] for r in rows)} | "
                     f"in-iteration repair similarity {st.mean(rs):.2f} over {len(rs)} |" if rs else
                     f"| {c} | (summary) | collapsed {col}/{len(rows)} | iteration-1 gate events {sum(r['iter1_gated'] for r in rows)} | no repairs |")
        L.append("")
    L += ["## Spend (per-run final.json at .env prices)", ""]
    tot = 0.0
    for t in TARGETS:
        parts = {c: round(spend(t, c), 3) for c in ARMS if any(runs_dir(t).glob(f"{c}-rep*/final.json"))}
        tot += sum(parts.values())
        L.append(f"- {t}: {parts}")
    L.append(f"- total {tot:.3f} USD")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
