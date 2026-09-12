"""campaign.py — ground-truth bug campaigns (paper plan, step 12; RQ4).

For each (target, bug build, generator, replicate seed): keep drawing inputs
from the generator and feeding them to the PRE-FIX sanitizer build until the
bug's own crash signature appears, the time budget runs out, or the input
budget is exhausted. Record inputs-to-trigger and time-to-trigger (or
censoring), plus every OTHER crash signature seen (new findings).

"The bug was triggered" is decided Magma-style by SIGNATURE, not by "any
crash": at start the bug's hand-written PoC is run through the same build and
its normalized crash signature (fuzz/triage/signature.py) is the oracle; a
PoC that does not crash is a failed positive control and the bug is dropped
with a note (plan section 13).

Generators are strategy references exactly as in eval/matrix.py
(`builtin:text`, `grammarinator:<FMT>:<variant>`, or a strategy .py path);
batches are drawn with `eval/_draw.py` under seeds base, base+1, ... so every
batch is reproducible and disjoint in seed. Inputs are fed in batch mode
(fuzz/runner.run_many), which restarts the harness after every crash.

    python eval/campaign.py --target tomlc99 --bug issue50 \\
        --ref runs/tomlc99/C2-rep1/final_strategy.py --seed 0 --minutes 30 \\
        --out eval/campaigns/tomlc99.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fuzz"))
sys.path.insert(0, str(ROOT / "fuzz" / "triage"))
sys.path.insert(0, str(ROOT / "eval"))
from targets import TARGETS, binary_name  # noqa: E402
from runner import run_once, run_many, Outcome, TIMEOUT_S  # noqa: E402
from signature import crash_signature  # noqa: E402
from cell import draw_examples, input_set_id  # noqa: E402

BATCH = 2000


def bug_binary(target: str, bug: str) -> Path:
    mode = TARGETS[target]["bugs"][bug]["mode"]
    return ROOT / "build" / binary_name(target, mode)


def positive_control(target: str, bug: str) -> tuple[bool, str]:
    """Run the bug's PoC through its build; (crashed?, signature). Uses BATCH
    mode (run_many), the same path the campaign classifies inputs with, so the
    oracle signature matches campaign hits exactly — the driver's entry-point
    frame (run_batch_mode vs run_stdin_mode) is part of the app-frame chain."""
    poc = TARGETS[target]["bugs"][bug]["poc"].encode("utf-8", "surrogatepass")
    results, _ = run_many(bug_binary(target, bug), [poc], timeout_s=max(TIMEOUT_S, 30))
    r = results[0]
    if r.outcome is not Outcome.CRASH:
        return False, ""
    return True, crash_signature(r.stderr, r.timed_out)


def run_campaign(target: str, bug: str, ref: str, seed: int, minutes: float,
                 max_inputs: int, batch: int = BATCH) -> dict:
    ok, sig = positive_control(target, bug)
    row = {"target": target, "bug": bug, "ref": ref, "seed": seed,
           "budget_minutes": minutes, "budget_inputs": max_inputs,
           "positive_control": ok, "bug_signature": sig}
    if not ok:
        row.update({"triggered": False, "note": "positive control failed: PoC does not crash"})
        return row
    binary = bug_binary(target, bug)
    t0 = time.monotonic()
    deadline = t0 + minutes * 60
    n_done = 0
    draw_s = run_s = 0.0
    others: dict[str, int] = {}
    triggered = None
    k = 0
    while time.monotonic() < deadline and n_done < max_inputs:
        td = time.monotonic()
        ex = draw_examples(ref, batch, seed * 100_000 + k)   # disjoint seed per batch
        draw_s += time.monotonic() - td
        data = [e.encode("utf-8", "surrogatepass") for e in ex]
        tr = time.monotonic()
        results, _ = run_many(binary, data, timeout_s=TIMEOUT_S)
        run_s += time.monotonic() - tr
        for i, r in enumerate(results):
            if r.outcome is Outcome.CRASH:
                s = crash_signature(r.stderr, r.timed_out)
                if s == sig and triggered is None:
                    triggered = {"inputs": n_done + i + 1,
                                 "seconds": round(time.monotonic() - t0, 2),
                                 "input_set": input_set_id(ref, batch, seed * 100_000 + k),
                                 "index_in_set": i}
                elif s != sig:
                    others[s] = others.get(s, 0) + 1
        n_done += len(results)
        k += 1
        if triggered:
            break
    row.update({"triggered": triggered is not None, "trigger": triggered,
                "inputs_total": n_done, "elapsed_s": round(time.monotonic() - t0, 2),
                "draw_s": round(draw_s, 2), "run_s": round(run_s, 2),
                "other_signatures": others, "batches": k})
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="ground-truth bug campaign (plan step 12)")
    ap.add_argument("--target", required=True)
    ap.add_argument("--bug", required=True, help="bug name from fuzz/targets.py, or 'all'")
    ap.add_argument("--ref", required=True, help="strategy reference (as in eval/matrix.py)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--max-inputs", type=int, default=10**7)
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--out", default=None, help="append one JSON row per campaign")
    args = ap.parse_args()
    bugs = list(TARGETS[args.target]["bugs"]) if args.bug == "all" else [args.bug]
    rows = []
    for b in bugs:
        row = run_campaign(args.target, b, args.ref, args.seed, args.minutes, args.max_inputs, args.batch)
        rows.append(row)
        print(f"[campaign] {args.target}/{b}: control={'ok' if row['positive_control'] else 'FAILED'} "
              f"triggered={row.get('triggered')} after {row.get('inputs_total', 0)} inputs "
              f"({row.get('elapsed_s', 0)}s); other signatures: {len(row.get('other_signatures', {}))}")
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
