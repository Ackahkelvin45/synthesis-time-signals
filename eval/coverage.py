"""coverage.py — EVALUATION ONLY (not part of the blackbox loop).

The assignment forbids coverage instrumentation *for steering* the loop. This
script uses coverage purely to *measure*, after the fact, one claim the design
rests on: that an LLM grammar-seeded generator reaches far more of the parser
than random text. It builds a SEPARATE, non-sanitizer llvm-cov binary for the
target (so json-parser's finding #1 UB is harmless and objects parse normally),
draws a fixed, seeded, REPRODUCIBLE sample of inputs from each strategy
(eval/cell.py: history-fixed subprocess draws, cached and hashed), and reports
line coverage of the target's C source.

    .venv/bin/python eval/coverage.py                     # json-parser -> eval/coverage.md
    .venv/bin/python eval/coverage.py --target parson     # -> eval/coverage_parson.md

Deliberately measures only two points — random baseline vs the evolved
generator. It does NOT plot a per-iteration trajectory: iteration 1 already
covers every JSON production (see runs/iter-*/stats.json), so line coverage
saturates immediately and a trajectory would misrepresent the loop's later,
depth/diversity-oriented work. (The per-iteration view lives in
proxy_validation.py; the multi-seed comparison in experiment.py.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from cell import (BUILTIN_TEXT, build_coverage_binary, cov_binary,  # noqa: E402
                  effective_strategy_path, input_set_id, measure_ref, runs_dir,
                  target_src)

N = 400          # examples drawn per strategy (fixed, seeded)
SEED = 0


def main() -> int:
    ap = argparse.ArgumentParser(description="random vs evolved line coverage")
    ap.add_argument("--target", default="json-parser")
    ap.add_argument("--out", default=None,
                    help="markdown output (default eval/coverage.md, or "
                         "eval/coverage_<target>.md for non-default targets)")
    args = ap.parse_args()
    target = args.target
    out_path = Path(args.out) if args.out else (
        ROOT / "eval" / ("coverage.md" if target == "json-parser" else f"coverage_{target}.md"))

    print(f"[eval] building coverage binary for {target} -> {cov_binary(target)}")
    build_coverage_binary(target)

    src_rel = target_src(target).relative_to(ROOT)
    print(f"[eval] measuring line coverage of {src_rel} over {N} seeded examples each")
    base = measure_ref(target, BUILTIN_TEXT, N, SEED, "baseline")
    base_cov = base["line"]

    evolved_dir = runs_dir(target) / "iter-5"
    if (evolved_dir / "strategy.py").exists():
        ev_ref = str(effective_strategy_path(evolved_dir))
        ev = measure_ref(target, ev_ref, N, SEED, "evolved")
        eng_cov = ev["line"]
        rows = (f"| naive baseline (`st.text()`, Step 3) | {base_cov:.1f}% | `{base['input_set']}` |\n"
                f"| LLM grammar-seeded (evolved, iter-5) | {eng_cov:.1f}% | `{ev['input_set']}` |\n\n")
        ratio = (f"The grammar-seeded generator reaches **{eng_cov/max(base_cov,1e-9):.1f}x** "
                 "the line coverage of random text. ")
    else:
        rows = f"| naive baseline (`st.text()`, Step 3) | {base_cov:.1f}% | `{base['input_set']}` |\n\n"
        ratio = (f"*(No evolved run exists yet for `{target}` under "
                 f"`{runs_dir(target).relative_to(ROOT)}/`; only the random baseline is "
                 f"reported. Run the loop with `--target {target}` to add the evolved row.)* ")

    out = (
        "# Coverage evaluation (measurement only — not used to steer the loop)\n\n"
        f"Line coverage of `{src_rel}` over {N} seeded examples "
        "each, on a separate non-sanitizer `-fcoverage-mapping` build. The input-set id\n"
        "is a hash of (strategy source, n, seed); identical ids mean identical inputs,\n"
        "so the numbers reproduce exactly across machines and script versions:\n\n"
        "| Generator | line coverage | input set |\n|---|---|---|\n"
        + rows + ratio +
        "Random text still exercises the lexer and\n"
        "rejection/error paths (hence the non-trivial baseline), but it rarely forms a\n"
        "parseable value, so it misses the value/number/string/object *construction*\n"
        "paths that only (near-)valid input reaches — exactly what the grammar-seeded\n"
        "generator adds. This *measures* an assertion the design rests on; it is not a\n"
        "steering signal.\n"
    )
    out_path.write_text(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
