"""matrix.py — the experiment-matrix runner (paper Tier A/B). MEASUREMENT ONLY.

Sweeps cells = (target x condition x seed) and appends ONE JSON row per cell to
a JSONL file. Resumable: cells already present in the file are skipped, so a
sweep can be interrupted, extended (more seeds, more conditions, more targets)
or re-run without redoing work. Every row carries its input-set id (see
eval/cell.py), so a reader can verify identical inputs by hash.

Conditions (a condition names a fixed generator; nothing is re-run through the
LLM here — loop runs are produced separately by fuzz/loop/agent.py):
  random             builtin st.text() baseline (no grammar knowledge)
  grammarinator      Grammarinator on the SAME .g4, defaults (C0b; eval/grammarinator.json)
  grammarinator-deep same, recursive alternatives up-weighted to the LLM seed's depth
  seed               the run's first WORKING iteration (normally iter-1; when the
                     model's first attempts were gated, the first that draws)
  evolved            the loop's OUTPUT (final_strategy.py, or reconstructed from
                     evolution.md after any revert — NOT blindly iter-5)
  run:<sub>:<what>   the same for a differently-configured loop run under
                     runs/<t>/<sub>/ — an ablation (run:ablate-signal:final) or
                     another model (run:model-x:final); <what> = seed | final | N

    .venv/bin/python eval/matrix.py --targets json-parser,parson \
        --conditions random,seed,evolved --k 20 --n 150 --out eval/matrix/main.jsonl
Then aggregate with eval/report.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from cell import (BUILTIN_TEXT, DEFAULT_CHECKPOINTS, build_coverage_binary,  # noqa: E402
                  effective_strategy_path, final_strategy_path, last_strategy_path,
                  input_set_id, measure_curve_cell, draw_examples, grammarinator_ref,
                  runs_dir, seed_strategy_path)

METRICS = ("region", "line", "branch", "acceptance", "novelty", "cap_mass",
           "productions", "crashes")


def _rel(p: Path) -> str:
    """Repo-relative for display, or absolute when outside the repo (scratch dirs)."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def resolve_condition(target: str, cond: str) -> str | None:
    """Map a condition name to a strategy reference for `target`, or None (with
    a printed reason) when the loop run it needs does not exist yet."""
    rd = runs_dir(target)
    if cond in ("grammarinator", "grammarinator-deep"):
        from targets import TARGETS as _T  # noqa: E402
        return grammarinator_ref(_T[target]["format"],
                                 "deep" if cond.endswith("-deep") else "defaults")
    if cond == "random":
        return BUILTIN_TEXT
    # `seed` / `evolved` replay the loop's own bookkeeping (cell.py): the first
    # WORKING iteration, and the loop's OUTPUT after any revert.
    if cond == "seed":
        p = seed_strategy_path(rd)
        return str(p) if p else None
    if cond == "evolved":
        p = final_strategy_path(rd)
        return str(p) if p else None
    if cond.startswith("run:"):
        try:
            _, sub, it = cond.split(":")
        except ValueError:
            raise SystemExit(f"bad condition '{cond}' (want run:<subdir>:<seed|final|N>)")
        sd = rd / sub
        if it == "seed":
            p = seed_strategy_path(sd)
        elif it == "last":
            p = last_strategy_path(sd)
        elif it == "final":
            p = final_strategy_path(sd)
        else:
            d = sd / f"iter-{it}"
            p = effective_strategy_path(d) if (d / "strategy.py").exists() else None
        return str(p) if p else None
    raise SystemExit(f"unknown condition '{cond}'")


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)


def load_done(out: Path) -> set[tuple]:
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["target"], r["condition"], r["seed"], r["n"]))
    return done


def _refuse_during_live_runs() -> None:
    """Never measure while a replicate batch runs (eval/replicates.py holds
    build/.runs.lock): load-induced timeouts would be misread as crashes and
    change the loop's decisions."""
    lock = ROOT / "build" / ".runs.lock"
    if lock.exists():
        raise SystemExit(f"a live-run batch holds {lock} ({lock.read_text().strip()}); "
                         "wait for it to finish before measuring")


def main() -> int:
    _refuse_during_live_runs()
    ap = argparse.ArgumentParser(description="experiment matrix runner")
    ap.add_argument("--targets", default="json-parser")
    ap.add_argument("--conditions", default="random,seed,evolved")
    ap.add_argument("--k", type=int, default=20, help="seeds per cell (0..k-1)")
    ap.add_argument("--n", type=int, default=10000, help="examples per seed (paper: 10^4)")
    ap.add_argument("--checkpoints", default=",".join(str(c) for c in DEFAULT_CHECKPOINTS),
                    help="coverage-curve checkpoints (inputs); the AUC is their mean")
    ap.add_argument("--out", default="eval/matrix/main.jsonl")
    args = ap.parse_args()

    out = (ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    cps = [int(c) for c in args.checkpoints.split(",") if c.strip()]
    done = load_done(out)
    print(f"[matrix] {len(done)} cells already in {_rel(out)}; "
          f"sweeping {len(targets)} target(s) x {len(conds)} condition(s) x K={args.k} at N={args.n}")

    todo = skipped = 0
    with out.open("a") as fh:
        for target in targets:
            build_coverage_binary(target)
            for cond in conds:
                ref = resolve_condition(target, cond)
                if ref is None:
                    print(f"[matrix] {target}/{cond}: no loop run for it yet — skipped "
                          f"(run fuzz/loop/agent.py --target {target} first)")
                    continue
                for seed in range(args.k):
                    key = (target, cond, seed, args.n)
                    if key in done:
                        skipped += 1
                        continue
                    t0 = time.time()
                    ex = draw_examples(ref, args.n, seed)
                    t1 = time.time()
                    r = measure_curve_cell(target, ex, cps,
                                           f"mx_{_slug(target)}_{_slug(cond)}_{seed}")
                    row = {
                        "target": target, "condition": cond, "seed": seed, "n": args.n,
                        "strategy_ref": ref if (ref.startswith("builtin:") or ref.startswith("grammarinator:"))
                        else str(Path(ref).relative_to(ROOT)),
                        "input_set": input_set_id(ref, args.n, seed),
                        **{k: v for k, v in r.items()},
                        "draw_s": round(t1 - t0, 2),
                        "run_s": round(time.time() - t1, 2),
                        "wall_s": round(time.time() - t0, 2),
                    }
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()
                    done.add(key)
                    todo += 1
                    print(f"[matrix] {target:12} {cond:22} seed={seed:2d} "
                          f"region={r['region']:.1f} branch={r['branch']:.1f} "
                          f"nov={r['novelty']:2d} acc={r['acceptance']:.2f} "
                          f"({row['wall_s']}s)")
    print(f"[matrix] done: {todo} new cells, {skipped} skipped (already present) -> "
          f"{_rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
