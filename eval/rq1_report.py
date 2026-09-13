"""rq1_report.py — RQ1 (secondary, descriptive): the LLM seed (C1) against
Grammarinator on the identical grammar (C0b), per target, on the primary outcome.

Inputs: the seed cells of every Stage 1 loop replicate (run:<C2|A5>-rep<k>:seed
in eval/matrix/stage1.jsonl; C2 and A5 share the identical seed prompt, so the
20 seeds per target are 20 independent draws of the same authoring process)
and the Grammarinator cells (eval/matrix/stage1c_grammarinator.jsonl), all at
10^4 inputs on draw seeds 0..19. Failed cells score 0, as registered.

Views, per target and Grammarinator variant:
  registered form (plan E7)  paired by draw seed: C1(s) = mean over the 20 seed
                             generators at draw seed s, against C0b(s); exact
                             sign-flip test over the 20 paired differences
  generator level            each seed generator's mean over its 20 draws, set
                             against Grammarinator's 20 draw values: counts
                             above and below, and A12 = P(a random LLM seed beats
                             a random Grammarinator input set) with a bootstrap CI
  failed seeds excluded      the same, without seed generators whose cells all
                             failed (flagged; tomlc99 has two)
Region AUC is reported as an exploratory line. Loop finals (C2, A5) are shown
for context.

    python eval/rq1_report.py --out eval/matrix/rq1_report.md
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
from report import a12, bootstrap_a12, parse_run_cond  # noqa: E402

TARGETS = ("json-parser", "parson", "tomlc99")
GRAM = (("grammarinator", "Grammarinator defaults"),
        ("grammarinator-deep", "Grammarinator depth-matched"))


def band(v: float, a: str, b: str) -> str:
    d = abs(v - 0.5)
    size = "practical" if d >= 0.14 else ("small" if d >= 0.06 else "negligible")
    return size if size == "negligible" else f"{size}, favouring {a if v > 0.5 else b}"


def load(path: Path, metric: str):
    """(loop[target][(cond, rep, what)][seed], fixed[target][cond][seed]); failed cells -> 0."""
    loop: dict = defaultdict(lambda: defaultdict(dict))
    fixed: dict = defaultdict(lambda: defaultdict(dict))
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        v = 0.0 if "error" in r else r[metric]
        pr = parse_run_cond(r["condition"])
        if pr:
            loop[r["target"]][pr][r["seed"]] = v
        else:
            fixed[r["target"]][r["condition"]][r["seed"]] = v
    return loop, fixed


def fmt(vals: list[float]) -> str:
    mu, h = ci95(vals)
    return f"{mu:.1f} ± {h:.1f} (median {st.median(vals):.1f}, range {min(vals):.1f}-{max(vals):.1f})"


def compare(gens: dict, gram: dict[int, float], label: str) -> list[str]:
    """gens: {(cond, rep): {seed: v}}; gram: {seed: v}."""
    seeds = sorted(gram)
    c1_by_seed = [st.mean(g[s] for g in gens.values()) for s in seeds]
    d, half, p = paired_perm_test([gram[s] for s in seeds], c1_by_seed)
    gmeans = [st.mean(g.values()) for g in gens.values()]
    gram_mu = st.mean(gram.values())
    above = sum(1 for x in gmeans if x > gram_mu)
    eff = a12(gmeans, list(gram.values()))
    lo, hi = bootstrap_a12(gmeans, list(gram.values()))
    return [f"  - {label}: A12(C1 generators, C0b draws) = {eff:.2f} [{lo:.2f}, {hi:.2f}] → "
            f"{band(eff, 'C1', 'C0b')}; {above} of {len(gmeans)} seed generators above the Grammarinator "
            f"mean ({gram_mu:.1f}); plan-E7 form (paired by draw seed): C1 − C0b = {d:+.2f} ± {half:.2f}, "
            f"sign-flip p = {p:.4f}"]


def finals_vs(loop_t: dict, cond: str, gram: dict[int, float]) -> str:
    fin = [st.mean(v.values()) for (c, k, w), v in loop_t.items() if c == cond and w == "final"]
    eff = a12(fin, list(gram.values()))
    lo, hi = bootstrap_a12(fin, list(gram.values()))
    return f"A12({cond} finals, C0b) = {eff:.2f} [{lo:.2f}, {hi:.2f}] → {band(eff, cond, 'C0b')}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1", default="eval/matrix/stage1.jsonl")
    ap.add_argument("--gram", default="eval/matrix/stage1c_grammarinator.jsonl")
    ap.add_argument("--out", default="eval/matrix/rq1_report.md")
    args = ap.parse_args()
    L = ["# RQ1: LLM seed (C1) vs Grammarinator on the identical grammar (C0b)", "",
         "Secondary, descriptive (pre-registration section 2). Primary outcome `auc_branch_reach`, "
         "10^4 inputs, draw seeds 0..19; failed cells score 0. C1 = the 20 seed generators per target "
         "(the seeds of C2 rep1-10 and A5 rep1-10; identical seed prompt). C0b = Grammarinator 26.1 "
         f"(pinned, eval/grammarinator.json). Sources `{args.stage1}`, `{args.gram}`.", "",
         "Reading guide. The generator is the unit for an authorship claim: the leading statistic is "
         "A12 of the 20 seed generators' means against Grammarinator's 20 draw values (P(a random LLM "
         "seed beats a random Grammarinator input set)), with a percentile-bootstrap CI and the "
         "registered bands. The plan-E7 form pairs by draw seed and averages the 20 generators within "
         "each seed; its CI carries draw noise only, not authoring variance, so its p-values overstate "
         "certainty and are shown for completeness. json-parser and parson share the JSON grammar and "
         "therefore receive byte-identical Grammarinator input sets; the depth-matched weight was "
         "calibrated on the json-parser pilot's seed (D21).", ""]
    data = {}
    for m in ("auc_branch_reach", "auc_region_reach"):
        l1, _ = load(ROOT / args.stage1, m)
        _, f2 = load(ROOT / args.gram, m)
        data[m] = (l1, f2)
    for t in TARGETS:
        loop, fixed = data["auc_branch_reach"]
        gens = {(c, k): v for (c, k, w), v in loop[t].items() if w == "seed"}
        if not gens or not fixed.get(t):
            continue
        failed = sorted(f"{c}-rep{k}" for (c, k), v in gens.items() if all(x == 0.0 for x in v.values()))
        healthy = {key: v for key, v in gens.items() if f"{key[0]}-rep{key[1]}" not in failed}
        L += [f"## {t}", ""]
        for cond, name in GRAM:
            if cond in fixed[t]:
                L.append(f"- {name} (C0b): {fmt(list(fixed[t][cond].values()))} over 20 draw seeds")
            elif cond == "grammarinator-deep":
                L.append(f"- {name}: not measured; the pinned TOML variant is identical to defaults "
                         "(deep_weight 1.0, no single recursive value rule; eval/grammarinator.json)")
        fin_ok = {f"{c}-rep{k}" for (c, k, w), v in loop[t].items()
                  if w == "final" and not all(x == 0.0 for x in v.values())}
        inflating = [f for f in failed if f in fin_ok]
        L.append(f"- LLM seed (C1): {fmt([st.mean(v.values()) for v in gens.values()])} over 20 generators"
                 + (f"; {len(failed)} seed generator(s) whose every cell failed, scored 0: {', '.join(failed)}"
                    + (f" (of these, {', '.join(inflating)} ended with a working final, so their "
                       "final-minus-seed delta is inflated by the whole final level; the rest also "
                       "collapsed at the final, delta 0)" if inflating else " (all also collapsed at the final)")
                    if failed else "; no failed seed generators"))
        best = max((c for c, _ in GRAM if c in fixed[t]), key=lambda c: st.mean(fixed[t][c].values()))
        for key in ("C2", "A5"):
            fin = [st.mean(v.values()) for (c, k, w), v in loop[t].items() if c == key and w == "final"]
            if fin:
                L.append(f"- context, {key} loop finals: {fmt(fin)} over {len(fin)} replicates; "
                         f"vs the stronger Grammarinator variant ({best}): {finals_vs(loop[t], key, fixed[t][best])}")
        L.append("- comparisons:")
        for cond, name in GRAM:
            if cond not in fixed[t]:
                continue
            L += compare(gens, fixed[t][cond], f"C1 vs {name}")
            if failed:
                L += compare(healthy, fixed[t][cond], f"C1 vs {name}, failed seeds excluded (n = {len(healthy)})")
        rl, rf = data["auc_region_reach"]
        rgens = [st.mean(v.values()) for (c, k, w), v in rl[t].items() if w == "seed"]
        rg = {cond: st.mean(rf[t][cond].values()) for cond, _ in GRAM if cond in rf[t]}
        L += [f"- exploratory, region AUC (`auc_region_reach`): C1 mean {st.mean(rgens):.1f} (median "
              f"{st.median(rgens):.1f}); " + "; ".join(f"{c} {v:.1f}" for c, v in rg.items()), ""]
    out = ROOT / args.out
    out.write_text("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
