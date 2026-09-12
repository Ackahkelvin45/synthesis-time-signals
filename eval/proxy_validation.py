"""proxy_validation.py — EVALUATION ONLY. Does the blind proxy signal correlate
with actual coverage?

The assignment forbids coverage instrumentation *for steering*. This script uses
coverage purely to AUDIT, after the fact, the central design bet: that the proxy
signal the loop steered by (production coverage, deep-nesting mass, accepted-
structure novelty) actually tracks the code coverage it could not observe.

Method (proxy and coverage computed from the SAME inputs, so they are comparable):
  for each committed iteration's EFFECTIVE strategy (runs/<target>/iter-N),
    1. draw N reproducible example strings (eval/cell.py: history-fixed
       subprocess draw, cached and hashed),
    2. one pass through the target's coverage build -> region/line/branch
       coverage of the target's C source AND the proxy signal,
  then correlate the two series across iterations (Spearman rho, no scipy).

CAVEAT stated up front: n = 5 iterations is a SMALL sample and line coverage
SATURATES at iteration 1 (every production appears immediately), so the
informative signal is region/branch coverage vs. the depth/diversity proxy
components — not line coverage, which cannot move once saturated. This is an
exploratory correlation, reported with its n, not a significance claim. (The
paper's matrix runner gives a per-target n of K seeds instead.)

    .venv/bin/python eval/proxy_validation.py [--target T] [--n 300] [--out F]
    # default: json-parser -> eval/proxy_validation.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from cell import (build_coverage_binary, effective_strategy_path, measure_ref,  # noqa: E402
                  runs_dir, target_src)

SEED = 0
ITERS = [1, 2, 3, 4, 5]


def spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation, no scipy. Returns 0.0 if a series is constant."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return round(num / (dx * dy), 3) if dx and dy else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="proxy signal vs coverage audit")
    ap.add_argument("--target", default="json-parser")
    ap.add_argument("--n", type=int, default=300, help="examples per iteration")
    ap.add_argument("--out", default=None, help="markdown output path")
    args = ap.parse_args()
    target, N = args.target, args.n
    out_path = Path(args.out) if args.out else (
        ROOT / "eval" / ("proxy_validation.md" if target == "json-parser"
                         else f"proxy_validation_{target}.md"))

    rd = runs_dir(target)
    missing = [i for i in ITERS if not (rd / f"iter-{i}" / "strategy.py").exists()]
    if missing:
        print(f"[eval] {target}: missing iterations {missing} under {rd.relative_to(ROOT)}/ — "
              f"run the loop with --target {target} first.")
        return 1

    print(f"[eval] {target}: building coverage binary")
    build_coverage_binary(target)

    rows = []
    for it in ITERS:
        spath = effective_strategy_path(rd / f"iter-{it}")
        r = measure_ref(target, str(spath), N, SEED, f"pv_{it}")
        r["score"] = r["productions"] * 5 + r["novelty"] + r["cap_mass"] * 20
        rows.append({"iter": it, "strategy": spath.name, **r})
        print(f"[eval] iter-{it} ({spath.name}): region={r['region']:.1f}% "
              f"branch={r['branch']:.1f}% | novelty={r['novelty']} "
              f"cap_mass={r['cap_mass']:.2f} score={r['score']:.1f} inputs={r['input_set']}")

    proxy_keys = ["score", "novelty", "cap_mass", "productions", "acceptance"]
    corr = {pk: {"region": spearman([r[pk] for r in rows], [r["region"] for r in rows]),
                 "branch": spearman([r[pk] for r in rows], [r["branch"] for r in rows])}
            for pk in proxy_keys}

    src_rel = target_src(target).relative_to(ROOT)
    lines = [
        f"# Proxy-signal validation against coverage ({target}; measurement only)",
        "",
        "**Question.** Coverage instrumentation is forbidden for *steering* the",
        "loop. Post-hoc, does the blind proxy signal the loop actually steered by",
        "correlate with the code coverage it could not see? This audits the central",
        "design bet.",
        "",
        f"**Method.** For each committed iteration's *effective* strategy, {N} seeded",
        "examples are drawn once (in a history-fixed subprocess, hashed) and used for",
        f"BOTH measurements, so proxy and coverage describe the same inputs: coverage of",
        f"`{src_rel}` on the `-fcoverage-mapping` build, and the proxy signal via the",
        "loop's own `summarize()`. Spearman rho is computed across the five iterations.",
        "",
        "**Caveat (read first).** n = 5 is small and **line coverage saturates at",
        "iteration 1** (every production appears immediately), so line coverage",
        "cannot move and is not the basis for any correlation. The informative axes",
        "are **region** and **branch** coverage vs. the depth/diversity proxy",
        "components. Treat rho values as exploratory, reported with their n.",
        "",
        "## Per-iteration measurements",
        "",
        "| iter | strategy | region% | line% | branch% | acc | prods | cap_mass | novelty | score | input set |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['iter']} | {r['strategy']} | {r['region']:.1f} | {r['line']:.1f} "
            f"| {r['branch']:.1f} | {r['acceptance']:.2f} | {r['productions']} "
            f"| {r['cap_mass']:.2f} | {r['novelty']} | {r['score']:.1f} | `{r['input_set']}` |")
    lines += ["", "## Correlation (Spearman rho, n=5)", "",
              "| proxy component | vs region cov | vs branch cov |", "|---|---|---|"]
    for pk in proxy_keys:
        lines.append(f"| {pk} | {corr[pk]['region']:+.3f} | {corr[pk]['branch']:+.3f} |")
    lines += [
        "",
        "## Reading it",
        "",
        "A positive rho means the proxy component moved together with real coverage",
        "across iterations — evidence the blind signal was tracking something the",
        "loop could not observe. A near-zero or negative rho for a component means it",
        "was *not* a good coverage proxy at this budget, which is itself an honest,",
        "useful result: it says which parts of the hand-designed signal earned their",
        "place and which did not. With n=5 and saturating line coverage this is an",
        "exploratory audit, not a significance test; the value is in *doing* the",
        "post-hoc validation the assignment's 'why did you expect it to work?' asks",
        "for, rather than asserting the signal was good.",
        "",
    ]
    out_path.write_text("\n".join(lines))
    print("\n".join(lines[:4]))
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:  # --out outside the repo (e.g. a scratch dir)
        shown = out_path
    print(f"[eval] wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
