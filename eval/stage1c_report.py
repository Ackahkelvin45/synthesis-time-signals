"""stage1c_report.py — the two follow-up cells that close Stage 1, in the registered structure.

  C3s on tomlc99   (coverage-scalar oracle; H2s = C3s vs C2, plus C3s vs A5 for context)
  C2R on json-parser (C2 with repair-by-re-seed, the mechanism note's follow-up condition C2')

Primary outcome `auc_branch_reach` (10^4 inputs x 20 fresh draw seeds per replicate; failed
cells scored 0, collapsed replicates therefore 0, as registered). Unit = loop replicate.
Per arm: final level, per-replicate delta (final - seed) with exact sign-flip test; between
arms: difference of replicate means, Vargha-Delaney A12 with 5 000-resample percentile
bootstrap CI against the registered bands, two-sample permutation p (20 000 shuffles).
Holm within target over the confirmatory hypotheses actually run on that target.

Mechanism statistics (log-only, exploratory; eval/mechanism.py's parsers): per replicate the
gate events, the path taken after each gate event (in-place refine of the failed code vs
grammar re-seed), whether the next iteration recovered, and the code similarity between the
failed iteration and the next (the fixation signature), plus the similarity between a gated
iteration's code and its in-iteration repair.

    python eval/stage1c_report.py --out eval/matrix/stage1c_report.md
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
from report import a12, bootstrap_a12, perm_two_sample, parse_run_cond, holm  # noqa: E402
from mechanism import analyse, iter_dirs, similarity, fisher_exact  # noqa: E402
from cell import runs_dir  # noqa: E402

METRIC = "auc_branch_reach"
BANDS = "A12 >= 0.64 (or <= 0.36) practical; 0.56-0.64 (0.36-0.44) small; otherwise negligible"


def band(v: float, a: str, b: str) -> str:
    d = abs(v - 0.5)
    size = "practical" if d >= 0.14 else ("small" if d >= 0.06 else "negligible")
    return size if size == "negligible" else f"{size}, favouring {a if v > 0.5 else b}"


def load(paths: list[Path]) -> tuple[dict, dict]:
    """data[target][cond][rep][what][seed] = value; meta[target] integrity counters."""
    data: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    meta: dict = defaultdict(lambda: {"rows": defaultdict(int), "failed": defaultdict(int),
                                      "shas": set(), "backends": set()})
    for p in paths:
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            pr = parse_run_cond(r["condition"])
            if not pr:
                continue
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


def level(d: dict, cond: str, what: str) -> dict[int, float]:
    return {k: st.mean(v[what].values()) for k, v in sorted(d[cond].items()) if v.get(what)}


def collapsed(d: dict, cond: str) -> list[int]:
    return sorted(k for k, v in d[cond].items() if v.get("final") and all(x == 0.0 for x in v["final"].values()))


def fmt(vals: list[float]) -> str:
    mu, h = ci95(vals)
    return f"{mu:.1f} ± {h:.1f} (median {st.median(vals):.1f})"


def arm_lines(d: dict, cond: str, label: str) -> list[str]:
    fin, seed = level(d, cond, "final"), level(d, cond, "seed")
    out = [f"- {label} final: {fmt(list(fin.values()))}; replicate means "
           + ", ".join(f"{fin[k]:.1f}" for k in sorted(fin))]
    reps = [k for k in sorted(fin) if k in seed]
    dd, half, p = paired_perm_test([seed[k] for k in reps], [fin[k] for k in reps])
    ds = [fin[k] - seed[k] for k in reps]
    pos, neg = sum(x > 0 for x in ds), sum(x < 0 for x in ds)
    out.append(f"- {label}: per-replicate Δ(final − seed) = " + ", ".join(f"r{k}:{fin[k] - seed[k]:+.1f}" for k in reps)
               + f"; mean {dd:+.2f} ± {half:.2f}; {pos} positive / {neg} negative / {len(ds) - pos - neg} zero "
               f"of {len(ds)}; sign-flip p = {p:.4f}")
    seed_failed = [k for k in reps if all(x == 0.0 for x in d[cond][k]["seed"].values())]
    infl = [k for k in seed_failed if fin[k] > 0]
    if infl:
        ok = [k for k in reps if k not in infl]
        dd2, half2, p2 = paired_perm_test([seed[k] for k in ok], [fin[k] for k in ok])
        out.append(f"- {label}: seed generator failed but final works for "
                   + ", ".join(f"rep{k}" for k in infl)
                   + f" (delta inflated by the whole final level); without them: mean {dd2:+.2f} ± {half2:.2f}, "
                   f"sign-flip p = {p2:.4f}, n = {len(ok)}")
    last = level(d, cond, "last")
    if last:
        out.append(f"- {label} last working iteration (reported next to final, plan E1): {fmt(list(last.values()))}")
    col = collapsed(d, cond)
    out.append(f"- {label} unusable final generators (collapsed, scored 0): {len(col)} of {len(fin)}"
               + (f" ({', '.join(f'rep{k}' for k in col)})" if col else ""))
    return out


def compare(d: dict, a: str, b: str) -> tuple[str, float]:
    fa, fb = level(d, a, "final"), level(d, b, "final")
    x, y = [fa[k] for k in sorted(fa)], [fb[k] for k in sorted(fb)]
    eff = a12(x, y)
    lo, hi = bootstrap_a12(x, y)
    p = perm_two_sample(x, y)
    return (f"difference of means ({a} − {b}) = {st.mean(x) - st.mean(y):+.2f}; A12 = {eff:.2f} "
            f"(bootstrap 95% CI [{lo:.2f}, {hi:.2f}]) → {band(eff, a, b)}; permutation p = {p:.4f}; "
            f"n = {len(x)} vs {len(y)}", p)


def healthy_compare(d: dict, a: str, b: str) -> str:
    ca, cb = set(collapsed(d, a)), set(collapsed(d, b))
    fa = {k: v for k, v in level(d, a, "final").items() if k not in ca}
    fb = {k: v for k, v in level(d, b, "final").items() if k not in cb}
    x, y = list(fa.values()), list(fb.values())
    if len(x) < 2 or len(y) < 2:
        return "too few healthy replicates"
    eff = a12(x, y)
    lo, hi = bootstrap_a12(x, y)
    return (f"healthy only (exploratory): {a} {st.mean(x):.1f} (n {len(x)}) vs {b} {st.mean(y):.1f} (n {len(y)}); "
            f"A12 = {eff:.2f} [{lo:.2f}, {hi:.2f}] → {band(eff, a, b)}; permutation p = {perm_two_sample(x, y):.4f}")


# --- mechanism: gate paths and fixation ----------------------------------------

def gate_paths(target: str, cond: str, k: int) -> dict:
    r = analyse(target, cond, k)
    rd = runs_dir(target) / f"{cond}-rep{k}"
    events = []
    for i, g in enumerate(r["gates"][:-1]):
        if g == "ok":
            continue
        nxt = r["edits"][i + 1].split(":")[0]
        path = ("re-seed" if nxt in ("RESEED", "SEED") else
                "in-place" if nxt in ("fix_generator_error", "raise_acceptance") else f"other ({nxt})")
        events.append({"iter": i + 1, "gate": g, "path": path, "recovered": r["gates"][i + 1] == "ok",
                       "sim_next": r["code_similarity"][i]})
    # in-iteration repair similarity (gated iterations that attempted a repair)
    rep_sims = []
    for idir in iter_dirs(rd):
        # After an ADOPTED repair the loop rewrites strategy.py to the repaired code and
        # keeps the model's original as strategy_orig.py; compare against the original.
        a = idir / "strategy_orig.py" if (idir / "strategy_orig.py").exists() else idir / "strategy.py"
        b = idir / "strategy_fix.py"
        if a.exists() and b.exists():
            s = similarity(a.read_text(), b.read_text())
            if s is not None:
                rep_sims.append(s)
    return {**r, "events": events, "repair_sims": rep_sims}


def path_table(rows: list[dict], label: str) -> list[str]:
    ev = [e for r in rows for e in r["events"]]
    out = []
    for path in sorted({e["path"] for e in ev}):
        es = [e for e in ev if e["path"] == path]
        sims = [e["sim_next"] for e in es if e["sim_next"] is not None]
        out.append(f"| {label} | {path} | {len(es)} | {sum(e['recovered'] for e in es)} of {len(es)} | "
                   + (f"{st.mean(sims):.2f} (min {min(sims):.2f}, max {max(sims):.2f})" if sims else "n/a") + " |")
    if not ev:
        out.append(f"| {label} | no gate event followed by another iteration | 0 | - | - |")
    return out


def mechanism_section(target: str, new: str, base: list[str]) -> list[str]:
    L = [f"### Mechanism on {target} (log-only, exploratory)", "",
         "Path after each gate event (gated, build-rejected or mid-run error, followed by another iteration), "
         "whether the next iteration recovered, and the code similarity between the failed iteration and the "
         "next (1.0 = resubmitted unchanged; the fixation signature).", "",
         "| arm | path after a gate event | cases | next iteration recovered | code similarity to the failed iteration |",
         "|---|---|---|---|---|"]
    groups = {}
    for cond in [new, *base]:
        rows = [gate_paths(target, cond, k) for k in range(1, 11)
                if (runs_dir(target) / f"{cond}-rep{k}" / "evolution.md").exists()]
        groups[cond] = rows
        L += path_table(rows, cond)
    L.append("")
    for cond, rows in groups.items():
        ms = [r["mean_code_similarity"] for r in rows if r["mean_code_similarity"] is not None]
        rs = [s for r in rows for s in r["repair_sims"]]
        col = [r for r in rows if r["collapsed"]]
        g1 = [r for r in rows if r["iter1_gated"]]
        L.append(f"- {cond}: collapsed {len(col)} of {len(rows)}; iteration-1 gate events {len(g1)} "
                 f"(collapsed after one: {sum(r['collapsed'] for r in g1)}); mean consecutive code similarity "
                 f"{st.mean(ms):.3f} over replicates; in-iteration repair similarity to the gated code "
                 + (f"{st.mean(rs):.2f} over {len(rs)} repairs (min {min(rs):.2f})" if rs else "n/a (no repairs)"))
    if new in groups and base and base[0] in groups:
        a = sum(r["collapsed"] for r in groups[new]); b = len(groups[new]) - a
        c = sum(r["collapsed"] for r in groups[base[0]]); dd = len(groups[base[0]]) - c
        L.append(f"- collapse {new} {a}/{a + b} vs {base[0]} {c}/{c + dd}: Fisher exact two-sided p = "
                 f"{fisher_exact(a, b, c, dd):.4f}")
    L.append("")
    return L


def integrity(meta: dict, target: str, conds: list[str], batch: str) -> list[str]:
    m = meta[target]
    L = ["### Data integrity", ""]
    for c in conds:
        L.append(f"- {c}: matrix rows {m['rows'][c]}, failed cells {m['failed'][c]}")
    L.append(f"- reachable_region_sha {sorted(x for x in m['shas'] if x)}; features_backend "
             f"{sorted(x for x in m['backends'] if x)}")
    mf = ROOT / "runs" / "_batches" / batch / "manifest.jsonl"
    if mf.exists():
        rows = [json.loads(l) for l in mf.read_text().splitlines() if l.strip()]
        ok = [r for r in rows if r.get("status") == "ok"]
        bad = [r for r in rows if r.get("status") == "failed"]
        L.append(f"- batch {batch}: {len(ok)} ok, {len(bad)} failed after rerun"
                 + (f" ({', '.join(r['name'] for r in bad)})" if bad else "")
                 + f"; served {sorted({s for r in ok for s in r.get('served_models', [])})}; "
                 f"mean wall {st.mean(r['wall_s'] for r in ok) / 60:.1f} min")
    L.append("")
    return L


def spend(target: str, cond: str) -> float:
    return round(sum(json.loads(f.read_text()).get("est_usd", 0.0)
                     for f in (runs_dir(target).glob(f"{cond}-rep*/final.json"))), 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", default="eval/matrix/stage1.jsonl")
    ap.add_argument("--new", default="eval/matrix/stage1c.jsonl")
    ap.add_argument("--out", default="eval/matrix/stage1c_report.md")
    args = ap.parse_args()
    data, meta = load([ROOT / args.stage1, ROOT / args.new])
    L = ["# Stage 1 closing cells: C3s on tomlc99, C2R (repair by re-seed) on json-parser", "",
         f"Primary outcome `{METRIC}` (10^4 inputs x 20 fresh draw seeds per replicate; failed cells scored 0, "
         f"so a collapsed replicate scores 0). Unit = loop replicate. Bands: {BANDS}. Sources `{args.stage1}` "
         f"(C2, A5), `{args.new}` (C3s, C2R).", ""]

    t = "tomlc99"
    if "C3s" in data[t]:
        d = data[t]
        L += [f"## {t}: C3s (coverage-scalar oracle) vs C2 and A5", "",
              "### Per arm", "", *arm_lines(d, "C3s", "C3s"), *arm_lines(d, "C2", "C2"), *arm_lines(d, "A5", "A5"), ""]
        h2, p_h2 = compare(d, "C3s", "C2")
        h1, p_h1 = compare(d, "C2", "A5")
        cx, _ = compare(d, "C3s", "A5")
        adj = holm([p_h1, p_h2])
        L += ["### Between arms", "",
              f"- H2s (C3s vs C2, confirmatory): {h2}; Holm-adjusted p over the family run on this target "
              f"{{H1, H2s}} = {adj[1]:.4f}",
              f"- H1 (C2 vs A5, from the Stage 1 report, restated for the Holm family): {h1}; Holm-adjusted p = {adj[0]:.4f}",
              f"- C3s vs A5 (context, outside the registered family): {cx}",
              f"- {healthy_compare(d, 'C3s', 'C2')}",
              f"- {healthy_compare(d, 'C3s', 'A5')}", ""]
        L += integrity(meta, t, ["C3s", "C2", "A5"], "stage1c-tomlc99-c3s")
        L += mechanism_section(t, "C3s", ["C2", "A5"])

    t = "json-parser"
    if "C2R" in data[t]:
        d = data[t]
        L += [f"## {t}: C2R (C2 with repair by re-seed) vs C2", "",
              "### Per arm", "", *arm_lines(d, "C2R", "C2R"), *arm_lines(d, "C2", "C2"), ""]
        cr, _ = compare(d, "C2R", "C2")
        cra, _ = compare(d, "C2R", "A5")
        L += ["### Between arms (follow-up condition, outside the registered confirmatory family)", "",
              f"- C2R vs C2: {cr}", f"- C2R vs A5 (context): {cra}",
              f"- {healthy_compare(d, 'C2R', 'C2')}", ""]
        L += integrity(meta, t, ["C2R", "C2"], "stage1c-json-c2r")
        L += mechanism_section(t, "C2R", ["C2", "A5"])

    L += ["## Spend of the closing cells", "",
          f"- C3s tomlc99: {spend('tomlc99', 'C3s'):.3f} USD; C2R json-parser: {spend('json-parser', 'C2R'):.3f} USD "
          "(est. from per-run token counts at .env prices)", ""]
    out = ROOT / args.out
    out.write_text("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
