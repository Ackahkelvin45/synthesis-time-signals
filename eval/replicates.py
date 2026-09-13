"""replicates.py — the replicate driver (paper plan, step 8).

Runs the loop many times, unattended, in the background, and never lets an
evaluation job overlap with it. One invocation = one BATCH:

    nohup .venv/bin/python eval/replicates.py --batch stage1 \\
        --targets json-parser,parson --conditions C2,A5,C3s,C3n --reps 10 \\
        > runs/_batches/stage1.log 2>&1 &

    cat runs/_batches/stage1/STATUS        # the ONLY thing to read for progress

Design rules (from the plan and DECISIONS D15):
  - Interleaved order: rep 1 of every (condition x target) before rep 2, and
    conditions alternate within a rep, so provider-side model drift is
    orthogonal to treatment.
  - Resumable: a run whose final.json exists is skipped; a run directory
    WITHOUT final.json is a failed run: deleted and rerun (never reconstructed).
  - Mutual exclusion: holds build/.runs.lock while running; eval/matrix.py
    refuses to start while the lock is held (load-induced timeouts would be
    misread as crashes and change the loop's decisions).
  - Provenance: the manifest records every run's argv, exit code, wall time,
    and the served model(s) read back from final.json.
  - STATUS is a one-line file rewritten after every run; the log holds the
    loop's own output. The session that launched the batch reads STATUS only.

Conditions map to agent.py flags:
    C2   proxy-steered loop            (no flags)
    A5   no-steering control           --ablate signal
    C3s  coverage-scalar oracle        --oracle coverage_scalar
    C3n  coverage-named oracle         --oracle coverage_named
    C2R  C2 with repair-by-re-seed     --repair reseed   (follow-up C2', DECISIONS D27)
A run lands in runs/<target>/<cond>-rep<k>/ (json-parser: runs/<cond>-rep<k>/).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fuzz"))
from targets import TARGETS  # noqa: E402

CONDITIONS: dict[str, list[str]] = {
    "C2": [],
    "A5": ["--ablate", "signal"],
    "C3s": ["--oracle", "coverage_scalar"],
    "C3n": ["--oracle", "coverage_named"],
    "C2R": ["--repair", "reseed"],
}
LOCK = ROOT / "build" / ".runs.lock"
BATCHES = ROOT / "runs" / "_batches"


def run_dir(target: str, name: str) -> Path:
    base = ROOT / "runs" if target == "json-parser" else ROOT / "runs" / target
    return base / name


def plan(targets: list[str], conds: list[str], reps: int, start_rep: int = 1) -> list[dict]:
    out = []
    for k in range(start_rep, start_rep + reps):
        for c in conds:
            for t in targets:
                out.append({"target": t, "cond": c, "rep": k, "name": f"{c}-rep{k}"})
    return out


def acquire_lock(batch: str) -> None:
    LOCK.parent.mkdir(exist_ok=True)
    if LOCK.exists():
        info = LOCK.read_text().strip()
        pid = int(info.split()[0]) if info else 0
        alive = pid and _alive(pid)
        if alive:
            raise SystemExit(f"another batch holds {LOCK}: {info}")
        LOCK.unlink()  # stale lock from a dead process
    LOCK.write_text(f"{os.getpid()} {batch} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def release_lock() -> None:
    try:
        if LOCK.exists() and LOCK.read_text().split()[0] == str(os.getpid()):
            LOCK.unlink()
    except OSError:
        pass


def write_status(bdir: Path, done: int, total: int, current: str, failed: int, note: str = "") -> None:
    line = f"done {done}/{total}, running {current or '-'}, failed {failed}"
    if note:
        line += f", {note}"
    line += f", updated {time.strftime('%H:%M:%SZ', time.gmtime())}\n"
    tmp = bdir / "STATUS.tmp"
    tmp.write_text(line)
    os.replace(tmp, bdir / "STATUS")


def run_one(item: dict, max_examples: int | None, extra: list[str], log) -> dict:
    t, name = item["target"], item["name"]
    rd = run_dir(t, name)
    if (rd / "final.json").exists():
        return {"status": "skipped-done"}
    if rd.exists():
        shutil.rmtree(rd)   # partial run: discard, never reconstruct
    argv = [sys.executable, str(ROOT / "fuzz" / "loop" / "agent.py"),
            "--target", t, "--run-name", name, *CONDITIONS[item["cond"]], *extra]
    if max_examples:
        argv += ["--max-examples", str(max_examples)]
    t0 = time.monotonic()
    log.write(f"\n=== {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {t} {name}: {' '.join(argv[2:])}\n")
    log.flush()
    p = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    wall = round(time.monotonic() - t0, 1)
    ok = p.returncode == 0 and (rd / "final.json").exists()
    served = []
    if ok:
        try:
            served = json.loads((rd / "final.json").read_text()).get("served_models", [])
        except Exception:  # noqa: BLE001
            pass
    return {"status": "ok" if ok else "failed", "exit": p.returncode, "wall_s": wall,
            "served_models": served, "argv": argv[2:]}


def main() -> int:
    ap = argparse.ArgumentParser(description="replicate driver (plan step 8)")
    ap.add_argument("--batch", required=True, help="batch name (runs/_batches/<name>/)")
    ap.add_argument("--targets", default="json-parser,parson")
    ap.add_argument("--conditions", default="C2,A5,C3s,C3n")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--start-rep", type=int, default=1)
    ap.add_argument("--max-examples", type=int, default=None,
                    help="override the loop's per-iteration budget (smoke tests only)")
    ap.add_argument("--retries", type=int, default=1, help="reruns of a failed run")
    ap.add_argument("--dry", action="store_true", help="print the plan and exit")
    args = ap.parse_args()

    targets = [t for t in args.targets.split(",") if t]
    conds = [c for c in args.conditions.split(",") if c]
    for t in targets:
        if t not in TARGETS:
            raise SystemExit(f"unknown target {t}")
    for c in conds:
        if c not in CONDITIONS:
            raise SystemExit(f"unknown condition {c} (known: {', '.join(CONDITIONS)})")
    items = plan(targets, conds, args.reps, args.start_rep)
    if args.dry:
        for it in items:
            print(f"{it['target']:12s} {it['name']:10s} {' '.join(CONDITIONS[it['cond']]) or '(proxy)'}")
        print(f"{len(items)} runs")
        return 0

    bdir = BATCHES / args.batch
    bdir.mkdir(parents=True, exist_ok=True)
    manifest_path = bdir / "manifest.jsonl"
    log = (bdir / "loop.log").open("a")
    acquire_lock(args.batch)
    done = failed = 0
    extra = ["--legacy-prompts"] if os.environ.get("REPLICATES_LEGACY_PROMPTS") == "1" else []
    try:
        write_status(bdir, 0, len(items), "", 0, "starting")
        for i, it in enumerate(items):
            write_status(bdir, done, len(items), f"{it['target']} {it['name']}", failed)
            rec = None
            for attempt in range(1 + args.retries):
                rec = run_one(it, args.max_examples, extra, log)
                if rec["status"] != "failed":
                    break
                log.write(f"--- retry {attempt + 1} for {it['target']} {it['name']}\n")
            rec.update({"target": it["target"], "cond": it["cond"], "rep": it["rep"],
                        "name": it["name"], "seq": i,
                        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            with manifest_path.open("a") as mf:
                mf.write(json.dumps(rec) + "\n")
            if rec["status"] == "failed":
                failed += 1
            else:
                done += 1
        write_status(bdir, done, len(items), "", failed, "finished")
    finally:
        release_lock()
        log.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
