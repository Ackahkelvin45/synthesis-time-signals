"""mechanism.py — log-only analysis of HOW the proxy loop collapses (paper mechanism section).

Reads only recorded run artifacts (no runs, no API calls). For every C2 (and,
for contrast, A5) replicate of stage 1a/1b:

  edits        the edit instruction the model received at each iteration,
               parsed from iter-N/prompt.md ("Make EXACTLY ONE change ...
               **action** — detail"), or SEED / RESEED-after-rejection
  gate events  iterations that were gated (acceptance < 5%), build-rejected,
               or errored mid-run (iter-N/stats.json + evolution.md)
  code change  difflib similarity between consecutive iterations' strategy.py
               (1.0 = identical code): did the model actually change anything?
  collapse     final generator unusable = every iteration gated

Two tests:
  T1 fixation: in collapsed replicates, are consecutive edit instructions
     (and consecutive strategies) near-identical, versus varying in healthy ones?
  T2 do early gate events predict collapse within the C2 arm? Fisher exact
     (hypergeometric, computed here; no scipy) on 2x2 tables.

    python eval/mechanism.py --out eval/mechanism.md
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from cell import runs_dir  # noqa: E402

_EDIT = re.compile(r"Make EXACTLY ONE change to the strategy: \*\*([a-z_]+)\*\* — (.*?)\.\n", re.S)


def iter_dirs(rd: Path) -> list[Path]:
    return sorted((d for d in rd.glob("iter-*") if d.is_dir()),
                  key=lambda d: int(d.name.split("-")[1]))


def edit_of(idir: Path) -> tuple[str, str]:
    p = idir / "prompt.md"
    if not p.exists():
        return ("?", "")
    t = p.read_text()
    m = _EDIT.search(t)
    if m:
        return (m.group(1), m.group(2).strip())
    if "previous attempt was REJECTED" in t:
        return ("RESEED", "after build rejection")
    return ("SEED", "initial seed from grammar")


def gate_of(idir: Path, evolution: str) -> str:
    """'ok' | 'gated' | 'rejected' | 'midrun-error'"""
    it = idir.name.split("-")[1]
    line = next((l for l in evolution.splitlines() if l.startswith(f"- iter {it}:")), "")
    if "build rejected" in line:
        return "rejected"
    if "mid-run error" in line:
        return "midrun-error"
    s = idir / "stats.json"
    if s.exists() and json.loads(s.read_text()).get("gated"):
        return "gated"
    return "ok"


def strategy_text(idir: Path) -> str:
    for name in ("strategy.py", "strategy_fix.py"):
        p = idir / name
        if p.exists():
            return p.read_text()
    return ""


def similarity(a: str, b: str) -> float | None:
    if not a or not b:
        return None
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 3)


def analyse(target: str, cond: str, k: int) -> dict:
    rd = runs_dir(target) / f"{cond}-rep{k}"
    ev = (rd / "evolution.md").read_text() if (rd / "evolution.md").exists() else ""
    its = iter_dirs(rd)
    edits = [edit_of(d) for d in its]
    gates = [gate_of(d, ev) for d in its]
    codes = [strategy_text(d) for d in its]
    sims = [similarity(codes[i - 1], codes[i]) for i in range(1, len(codes))]
    final = json.loads((rd / "final.json").read_text()) if (rd / "final.json").exists() else {}
    collapsed = bool(its) and all(g == "gated" for g in gates)
    # fixation metrics
    actions = [a for a, _ in edits[1:]]           # the refinement edits (iteration 2..)
    details = [f"{a}|{d}" for a, d in edits[1:]]
    consecutive_same = sum(1 for i in range(1, len(details)) if details[i] == details[i - 1])
    return {
        "target": target, "cond": cond, "rep": k, "iterations": len(its),
        "collapsed": collapsed, "gate_events": sum(1 for g in gates if g != "ok"),
        "gates": gates, "iter1_gated": bool(gates) and gates[0] != "ok",
        "edits": [f"{a}: {d[:60]}" for a, d in edits],
        "distinct_edits": len(set(details)), "consecutive_same_edit": consecutive_same,
        "code_similarity": sims,
        "mean_code_similarity": round(sum(s for s in sims if s is not None) / max(1, sum(1 for s in sims if s is not None)), 3) if any(s is not None for s in sims) else None,
        "source_iter": final.get("source_iter"), "selection": final.get("selection"),
    }


# --- Fisher exact (two-sided, hypergeometric) ---------------------------------

def _hyper(a: int, b: int, c: int, d: int) -> float:
    n = a + b + c + d
    return (math.comb(a + b, a) * math.comb(c + d, c)) / math.comb(n, a + c)


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided p for [[a, b], [c, d]] by summing tables at least as extreme."""
    r1, r2, c1 = a + b, c + d, a + c
    p_obs = _hyper(a, b, c, d)
    p = 0.0
    for x in range(max(0, c1 - r2), min(r1, c1) + 1):
        y, z, w = r1 - x, c1 - x, r2 - (c1 - x)
        if w < 0:
            continue
        px = _hyper(x, y, z, w)
        if px <= p_obs + 1e-12:
            p += px
    return min(1.0, p)


def mean(v):
    return sum(v) / len(v) if v else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="eval/mechanism.md")
    ap.add_argument("--json", default="eval/mechanism.jsonl")
    args = ap.parse_args()
    targets = ["json-parser", "parson", "tomlc99"]
    rows = [analyse(t, c, k) for t in targets for c in ("C2", "A5") for k in range(1, 11)
            if (runs_dir(t) / f"{c}-rep{k}" / "evolution.md").exists()]
    (ROOT / args.json).write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    c2 = [r for r in rows if r["cond"] == "C2"]
    a5 = [r for r in rows if r["cond"] == "A5"]
    col = [r for r in c2 if r["collapsed"]]
    ok = [r for r in c2 if not r["collapsed"]]

    L = ["# Mechanism: how the proxy loop collapses (log-only analysis)", "",
         f"Replicates: C2 {len(c2)} ({len(col)} collapsed), A5 {len(a5)} "
         f"({sum(r['collapsed'] for r in a5)} collapsed). Sources: iter-N/prompt.md (the edit "
         "instruction the model received), iter-N/stats.json (gate), strategy.py (code), "
         "evolution.md. No runs, no API calls.", ""]

    # T1 fixation
    L += ["## T1. Fixation: do collapsed replicates repeat the same edit and the same code?", "",
          "| group | n | distinct edit instructions (of 4 refinements) | consecutive identical edits | mean code similarity between consecutive iterations |",
          "|---|---|---|---|---|"]
    for name, g in (("C2 collapsed", col), ("C2 healthy", ok), ("A5 (contrast)", a5)):
        if not g:
            continue
        L.append(f"| {name} | {len(g)} | {mean([r['distinct_edits'] for r in g]):.2f} | "
                 f"{mean([r['consecutive_same_edit'] for r in g]):.2f} | "
                 f"{mean([r['mean_code_similarity'] for r in g if r['mean_code_similarity'] is not None]):.3f} |")
    L += ["", "Per collapsed replicate (edit instruction per iteration; code similarity to the previous iteration):", ""]
    for r in col:
        L.append(f"- **{r['target']} C2-rep{r['rep']}**: gates {r['gates']}")
        for i, e in enumerate(r["edits"], 1):
            sim = r["code_similarity"][i - 2] if i >= 2 else None
            L.append(f"  - iter {i}: {e}" + (f"  (code sim {sim})" if sim is not None else ""))
    L.append("")
    # what edits do healthy C2 replicates receive?
    act = Counter(e.split(":")[0] for r in ok for e in r["edits"][1:])
    L += ["Edit instructions across healthy C2 replicates (iterations 2-5): "
          + ", ".join(f"{k} {v}" for k, v in act.most_common()), ""]

    # T2 gates predict collapse
    L += ["## T2. Do gate events predict collapse within the C2 arm?", ""]
    a = sum(1 for r in col if r["iter1_gated"]); b = len(col) - a
    c = sum(1 for r in ok if r["iter1_gated"]); d = len(ok) - c
    L += [f"Iteration-1 gated: collapsed {a}/{len(col)}, healthy {c}/{len(ok)}; "
          f"Fisher exact two-sided p = {fisher_exact(a, b, c, d):.4f}."]
    ge_col = [r["gate_events"] for r in col]; ge_ok = [r["gate_events"] for r in ok]
    L += [f"Gate events per replicate: collapsed {ge_col} (by definition 5); healthy {ge_ok} "
          f"(mean {mean(ge_ok):.2f}). Note: 'collapsed' is defined as five gated iterations, so total gate "
          f"count is tautological; the informative test is the iteration-1 gate above, and the "
          f"recovery question below.", ""]
    rec = [r for r in ok if r["iter1_gated"]]
    L += [f"Healthy C2 replicates whose iteration 1 was gated but that recovered: {len(rec)} "
          f"({', '.join(f'{r['target']} rep{r['rep']}' for r in rec) or 'none'}).",
          f"A5 replicates with any gate event: {sum(1 for r in a5 if r['gate_events'])}/{len(a5)}; "
          f"iteration-1 gated: {sum(1 for r in a5 if r['iter1_gated'])}/{len(a5)}; collapsed: "
          f"{sum(r['collapsed'] for r in a5)}.", ""]
    # cross-arm: collapse rate C2 vs A5
    a2 = len(col); b2 = len(c2) - a2; c2n = sum(r["collapsed"] for r in a5); d2 = len(a5) - c2n
    L += ["## Cross-arm collapse rate", "",
          f"C2 {a2}/{len(c2)} vs A5 {c2n}/{len(a5)}; Fisher exact two-sided p = {fisher_exact(a2, b2, c2n, d2):.4f}.", ""]

    out = ROOT / args.out
    out.write_text("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
