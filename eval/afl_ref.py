"""afl_ref.py — the AFL++ reference row (plan step 12, table T7).

Builds each target's harness with afl-clang-fast inside the official AFL++
container (no sanitizers: crash-finding is not the point of this row; coverage
is measured afterwards on the study's coverage build), runs afl-fuzz for a
fixed wall-clock budget from one valid seed per format with default settings,
then replays the final queue, in AFL's creation order, through the coverage
build and reports branch coverage of the parse-reachable region at the same
checkpoints the loop arms use, plus the queue size and executions per second.

    python eval/afl_ref.py build                       # compile AFL binaries in Docker
    python eval/afl_ref.py fuzz --targets json-parser --runs 5 --seconds 3600 [--parallel 4]
    python eval/afl_ref.py replay --out eval/matrix/afl_ref.jsonl
    python eval/afl_ref.py report --in eval/matrix/afl_ref.jsonl --out eval/matrix/afl_ref.md
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from targets import TARGETS  # noqa: E402
from cell import coverage_curve, build_coverage_binary, DEFAULT_CHECKPOINTS  # noqa: E402

IMAGE = "aflplusplus/aflplusplus:latest"
AFL = ROOT / "build" / "afl"
SEEDS = {"JSON": b'{"a":[1,"b",null,true],"c":{"d":1.5e2}}', "TOML": b'a = 1\nb = "x"\n[t]\nc = [1, 2]\n'}


def docker(cmd: str, **kw):
    return subprocess.run(["docker", "run", "--rm", "-v", f"{ROOT}:/src", "-w", "/src", IMAGE, "sh", "-c", cmd], **kw)


def build(targets):
    AFL.mkdir(parents=True, exist_ok=True)
    for t in targets:
        v = TARGETS[t]
        out = f"build/afl/afl_{v['binary']}"
        cmd = (f"afl-clang-fast -O2 -DHARNESS_MODE='\"afl\"' -I {v['inc']} -I harness {v['src']} {v['harness']} -o {out}")
        r = docker(cmd, capture_output=True, text=True)
        print(f"[afl] build {t}: exit {r.returncode} {r.stderr.strip()[-200:]}")
        if r.returncode:
            raise SystemExit(1)


def fuzz(targets, runs, seconds, parallel):
    jobs = [(t, k) for k in range(1, runs + 1) for t in targets]
    procs = []
    for t, k in jobs:
        v = TARGETS[t]
        outdir = AFL / t / f"run{k}"
        if (outdir / "default" / "fuzzer_stats").exists() and (outdir / "DONE").exists():
            print(f"[afl] {t} run{k}: done, skipped")
            continue
        seeddir = AFL / t / "seeds"
        seeddir.mkdir(parents=True, exist_ok=True)
        (seeddir / "seed").write_bytes(SEEDS[v["format"]])
        outdir.mkdir(parents=True, exist_ok=True)
        rel = lambda p: str(Path(p).relative_to(ROOT))
        cmd = (f"AFL_NO_UI=1 AFL_SKIP_CPUFREQ=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 "
               f"afl-fuzz -i {rel(seeddir)} -o {rel(outdir)} -s {k} -V {seconds} -- build/afl/afl_{v['binary']} "
               f"> {rel(outdir)}/afl.log 2>&1; touch {rel(outdir)}/DONE")
        while len([p for p in procs if p.poll() is None]) >= parallel:
            time.sleep(10)
        print(f"[afl] {t} run{k}: starting ({seconds}s)", flush=True)
        procs.append(subprocess.Popen(["docker", "run", "--rm", "-v", f"{ROOT}:/src", "-w", "/src", IMAGE, "sh", "-c", cmd]))
    for p in procs:
        p.wait()
    print("[afl] all runs finished")


def queue_files(outdir: Path):
    q = outdir / "default" / "queue"
    return sorted((f for f in q.iterdir() if f.name.startswith("id:")), key=lambda f: f.name)


def replay(targets, out: Path):
    done = set()
    if out.exists():
        done = {(json.loads(l)["target"], json.loads(l)["run"]) for l in out.read_text().splitlines() if l.strip()}
    with out.open("a") as fh:
        for t in targets:
            build_coverage_binary(t)
            for rd in sorted((AFL / t).glob("run*")):
                k = int(rd.name[3:])
                if (t, k) in done or not (rd / "DONE").exists():
                    continue
                files = queue_files(rd)
                raw = [f.read_bytes() for f in files]
                stats = dict(l.split(":", 1) for l in (rd / "default" / "fuzzer_stats").read_text().splitlines() if ":" in l)
                cps = [c for c in DEFAULT_CHECKPOINTS if c <= len(raw)]
                cc = coverage_curve(t, [""] * len(raw), cps, f"afl_{t}_{k}", raw=raw)
                curve = {n: {kk: vv for kk, vv in d.items() if kk != "profdata"} for n, d in cc["curve"].items()}
                last = curve[len(raw)]
                row = {"target": t, "run": k, "queue": len(raw), "run_time_s": int(float(stats.get("run_time", "0").strip())),
                       "execs_per_sec": float(stats.get("execs_per_sec", "0").strip()), "execs_done": int(float(stats.get("execs_done", "0").strip())),
                       "saved_crashes": int(float(stats.get("saved_crashes", "0").strip())),
                       "branch_reach_final": last.get("branch_reach", last["branch"]), "region_reach_final": last.get("region_reach", last["region"]),
                       "curve": {str(n): {kk: vv for kk, vv in d.items() if kk in ("branch_reach", "region_reach", "branch", "region")} for n, d in curve.items()},
                       "auc_branch_reach_over_queue": st.mean(d.get("branch_reach", d["branch"]) for d in curve.values())}
                fh.write(json.dumps(row) + "\n"); fh.flush()
                print(f"[afl] replay {t} run{k}: queue {len(raw)}, branch_reach {row['branch_reach_final']:.1f}, "
                      f"{row['execs_per_sec']:.0f} exec/s", flush=True)


def report(inp: Path, out: Path):
    rows = [json.loads(l) for l in inp.read_text().splitlines() if l.strip()]
    L = ["# T7. AFL++ reference row", "",
         "afl-clang-fast (-O2, no sanitizers), afl-fuzz defaults, one valid seed per format, fixed wall-clock budget, "
         "no dictionary; the final queue replayed in creation order through the study's coverage build. Branch coverage "
         "of the parse-reachable region at the end of the queue (mean ± 95% CI over runs); the loop arms' numbers at "
         "10^4 inputs are in Table 2 for comparison (not equal-n: AFL's queue is the set of coverage-increasing inputs, "
         "so its size is not comparable to a generator's input count).", "",
         "| target | runs | budget (s) | queue size | execs/s | crashes saved | branch coverage of reachable region (final queue) |",
         "|---|---|---|---|---|---|---|"]
    for t in TARGETS:
        rs = [r for r in rows if r["target"] == t]
        if not rs:
            continue
        v = [r["branch_reach_final"] for r in rs]
        ci = 1.96 * st.stdev(v) / len(v) ** 0.5 if len(v) > 1 else 0
        L.append(f"| {t} | {len(rs)} | {rs[0]['run_time_s']} | {st.mean(r['queue'] for r in rs):.0f} | "
                 f"{st.mean(r['execs_per_sec'] for r in rs):.0f} | {sum(r['saved_crashes'] for r in rs)} | {st.mean(v):.1f} ± {ci:.1f} |")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "fuzz", "replay", "report"])
    ap.add_argument("--targets", default="json-parser,parson,tomlc99,cjson")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--seconds", type=int, default=3600)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--out", default="eval/matrix/afl_ref.jsonl")
    ap.add_argument("--in", dest="inp", default="eval/matrix/afl_ref.jsonl")
    a = ap.parse_args()
    targets = [t for t in a.targets.split(",") if t]
    if a.cmd == "build":
        build(targets)
    elif a.cmd == "fuzz":
        fuzz(targets, a.runs, a.seconds, a.parallel)
    elif a.cmd == "replay":
        replay(targets, ROOT / a.out)
    else:
        report(ROOT / a.inp, ROOT / (a.out if a.out.endswith(".md") else "eval/matrix/afl_ref.md"))


if __name__ == "__main__":
    main()
