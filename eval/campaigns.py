"""campaigns.py — RQ4 scheduler: ground-truth bug campaigns for every registered
arm's FINAL generator, in parallel, resumable, one-line STATUS.

Jobs: (target, bug, ref, seed) for the finals of C2, A5, C3s, C3n (reps 1-10;
seed = rep*1000 so batch seeds never overlap across replicates) plus the fixed
references random / grammarinator(-deep) at seed 0. Each job runs
eval/campaign.py (registered 30-minute budget) as a subprocess; a generator
that cannot draw (collapsed final) is recorded as a row with "error" and
inputs_total 0 (censored at zero, the RQ4 analogue of the scored-minimum rule).
Rows append to --out; jobs already present there are skipped.

    python campaigns.py --workers 9 --out eval/campaigns/rq4.jsonl
    cat eval/campaigns/STATUS
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from cell import runs_dir, final_strategy_path, grammarinator_ref, BUILTIN_TEXT  # noqa: E402
from targets import TARGETS  # noqa: E402

ARMS = ("C2", "A5", "C3s", "C3n")
CAMPAIGN_TARGETS = ("json-parser", "tomlc99", "cjson")


def jobs(conds: tuple[str, ...], baselines: bool) -> list[dict]:
    out = []
    for t in CAMPAIGN_TARGETS:
        bugs = list(TARGETS[t]["bugs"])
        refs: list[tuple[str, str, int]] = []
        for c in conds:
            for k in range(1, 11):
                p = final_strategy_path(runs_dir(t) / f"{c}-rep{k}")
                if p:
                    refs.append((f"{c}-rep{k}", str(p.relative_to(ROOT)), k * 1000))
        if baselines:
            fmt = TARGETS[t]["format"]
            refs.append(("random", BUILTIN_TEXT, 0))
            refs.append(("grammarinator", grammarinator_ref(fmt, "defaults"), 0))
            if fmt == "JSON":
                refs.append(("grammarinator-deep", grammarinator_ref(fmt, "deep"), 0))
        for name, ref, seed in refs:
            for b in bugs:
                out.append({"target": t, "bug": b, "name": name, "ref": ref, "seed": seed})
    return out


def key(j: dict) -> tuple:
    return (j["target"], j["bug"], j["ref"], j["seed"])


def done_keys(out: Path) -> set[tuple]:
    if not out.exists():
        return set()
    return {key(json.loads(l)) for l in out.read_text().splitlines() if l.strip()}


def run_job(j: dict, minutes: float, out: Path, log: Path) -> str:
    argv = [str(ROOT / ".venv/bin/python"), str(ROOT / "eval/campaign.py"), "--target", j["target"],
            "--bug", j["bug"], "--ref", j["ref"], "--seed", str(j["seed"]), "--minutes", str(minutes),
            "--out", str(out)]
    with log.open("a") as lf:
        p = subprocess.run(argv, stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
    if p.returncode != 0:
        # generator could not draw (or the runner died): censor at zero, keep the row
        with out.open("a") as fh:
            fh.write(json.dumps({"target": j["target"], "bug": j["bug"], "ref": j["ref"], "seed": j["seed"],
                                 "name": j["name"], "budget_minutes": minutes, "triggered": False,
                                 "trigger": None, "inputs_total": 0, "elapsed_s": 0.0,
                                 "error": f"campaign exit {p.returncode}"}) + "\n")
        return "error"
    return "ok"


def write_status(path: Path, done: int, total: int, running: int, errors: int) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(f"campaigns done {done}/{total}, running {running}, errors {errors}, "
                   f"updated {time.strftime('%H:%M:%SZ', time.gmtime())}\n")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default=",".join(ARMS))
    ap.add_argument("--no-baselines", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--out", default="eval/campaigns/rq4.jsonl")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    status = out.parent / "STATUS"
    log = out.parent / "campaigns.log"
    js = jobs(tuple(c for c in args.conds.split(",") if c), not args.no_baselines)
    dk = done_keys(out)
    todo = [j for j in js if key(j) not in dk]
    if args.dry:
        for j in todo:
            print(f"{j['target']:12} {j['bug']:10} {j['name']:20} seed={j['seed']}")
        print(f"{len(todo)} to run of {len(js)} jobs ({len(js) - len(todo)} done); "
              f"{len(todo) * args.minutes / 60 / args.workers:.1f} h on {args.workers} workers")
        return 0
    lock = ROOT / "build" / ".runs.lock"
    if lock.exists():
        raise SystemExit(f"live-run lock held: {lock.read_text().strip()}")
    done = len(js) - len(todo)
    errors = 0
    write_status(status, done, len(js), 0, errors)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_job, j, args.minutes, out, log): j for j in todo}
        running = len(futs)
        write_status(status, done, len(js), running, errors)
        for f in as_completed(futs):
            done += 1
            running -= 1
            if f.result() == "error":
                errors += 1
            write_status(status, done, len(js), running, errors)
    status.write_text(status.read_text().rstrip("\n") + ", finished\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
