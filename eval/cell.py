"""cell.py — target-aware per-cell measurement shared by every eval and the
matrix runner. MEASUREMENT ONLY (never used to steer the loop).

One CELL = (target, strategy, seed, N). One pass over N seeded examples through
the target's coverage build yields, on the SAME inputs:
  - region / line / branch coverage of the target's C source (merged profile)
  - acceptance rate, accepted-structure novelty, cap-mass, productions
    (from the harness exit codes, via the loop's own summarize())
so coverage and the proxy metrics are directly comparable. This is the single
implementation the evals used to duplicate; the matrix runner sweeps it over
targets x conditions x seeds x models.

REPRODUCIBLE INPUT SETS. A seeded Hypothesis draw is deterministic only for an
identical process history (which @given functions existed/ran before, import
order, launch method). Different eval scripts therefore drew different "seeded"
input sets and reported different coverage (42.2 / 42.6 / 43.6 line% on one
binary) — measured, not guessed: identical inputs measured twice on the same
binary are bit-identical; only the inputs varied. So every draw here runs in a
FRESH interpreter with a fixed minimal history (eval/_draw.py), is cached on
disk keyed by a hash of exactly (strategy source, n, seed), and every
measurement can report that input-set id. Strategies are passed by REFERENCE
('builtin:text' or a strategy .py path), never as live objects.

The coverage build is a NON-sanitizer -fcoverage-mapping binary compiled from
the target's pinned source + its harness, so objects parse normally (on
json-parser the sanitizer build would abort on finding #1) and the harness exit
codes still mean 0=valid, 2=reject, 10/11=skip.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fuzz"))
sys.path.insert(0, str(ROOT / "fuzz" / "loop"))

from targets import TARGETS  # noqa: E402

BUILD = ROOT / "build"
INPUTS = BUILD / "_inputs"          # cached, hashed input sets (regenerable)
_DRAW = Path(__file__).resolve().parent / "_draw.py"
BUILTIN_TEXT = "builtin:text"        # the naive st.text() baseline, by reference


# --- toolchain ---------------------------------------------------------------

def _llvm(tool: str) -> list[str]:
    """argv prefix for an LLVM tool, portable across macOS (xcrun) and Linux
    (plain or versioned llvm-cov-N)."""
    if shutil.which(tool):
        return [tool]
    if shutil.which("xcrun"):
        return ["xcrun", tool]
    for cand in (f"{tool}-18", f"{tool}-17", f"{tool}-16", f"{tool}-15", f"{tool}-14"):
        if shutil.which(cand):
            return [cand]
    return ["xcrun", tool]  # last resort; errors clearly if truly absent


# --- target plumbing ---------------------------------------------------------

def target_src(target: str) -> Path:
    return ROOT / TARGETS[target]["src"]


def runs_dir(target: str) -> Path:
    """Where a target's loop runs live: runs/ for the default json-parser (the
    committed run), runs/<target>/ for every other target."""
    return ROOT / "runs" if target == "json-parser" else ROOT / "runs" / target


def cov_binary(target: str) -> Path:
    """json-parser keeps the historical name build/harness_cov; others get a
    suffix so several targets' coverage builds can coexist."""
    return BUILD / ("harness_cov" if target == "json-parser" else f"harness_cov_{target}")


def build_coverage_binary(target: str = "json-parser") -> Path:
    """Compile the target's coverage-instrumented, NON-sanitizer harness."""
    t = TARGETS[target]
    BUILD.mkdir(exist_ok=True)
    out = cov_binary(target)
    cmd = [
        os.environ.get("CC", "clang"),
        "-fprofile-instr-generate", "-fcoverage-mapping", "-g", "-O0",
        "-I", str(ROOT / t["inc"]),
        str(ROOT / t["src"]), str(ROOT / t["harness"]), "-o", str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


# --- strategies (by reference) ------------------------------------------------

def load_strategy_file(path: Path):
    """Load a strategy module in-process (for probing only; drawing for
    measurement goes through draw_examples so the history stays fixed)."""
    spec = importlib.util.spec_from_file_location(
        f"strat_{path.parent.name}_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.strategy


def _draws_ok(path: Path) -> bool:
    """Does this strategy file load and produce one example? (in-process probe;
    it may perturb THIS process's Hypothesis history, which is harmless because
    measurement draws are isolated in a subprocess)."""
    try:
        strat = load_strategy_file(path)
        from hypothesis import given, settings, HealthCheck

        @settings(max_examples=1, deadline=None, database=None,
                  suppress_health_check=[HealthCheck.function_scoped_fixture])
        @given(s=strat)
        def _probe(s):
            pass

        _probe()
        return True
    except Exception:  # noqa: BLE001
        return False


def effective_strategy_path(iter_dir: Path) -> Path:
    """The strategy file that actually ran that iteration: strategy.py, unless it
    is a pre-repair artifact that no longer draws, in which case strategy_fix.py
    (mirrors agent.py's replay fallback)."""
    canonical = iter_dir / "strategy.py"
    fix = iter_dir / "strategy_fix.py"
    if fix.exists() and not _draws_ok(canonical):
        return fix
    return canonical


def effective_strategy(iter_dir: Path):
    """Live strategy object for the effective file (probing/compat only)."""
    return load_strategy_file(effective_strategy_path(iter_dir))


# --- reproducible input sets -------------------------------------------------------

def _ref_bytes(ref: str) -> bytes:
    """The content that defines the strategy: the literal builtin name, or the
    strategy file's bytes (so editing the file invalidates cached draws)."""
    return ref.encode() if ref.startswith("builtin:") else Path(ref).read_bytes()


def input_set_id(ref: str, n: int, seed: int) -> str:
    """Stable id of an input set = hash of exactly (strategy source, n, seed)."""
    h = hashlib.sha256()
    h.update(_ref_bytes(ref))
    h.update(f"|n={n}|seed={seed}".encode())
    return h.hexdigest()[:16]


def draw_examples(ref: str, n: int, seed: int) -> list[str]:
    """Reproducible input set for (strategy ref, n, seed): drawn in a fresh,
    history-fixed interpreter (eval/_draw.py) and cached under build/_inputs/.
    `ref` is BUILTIN_TEXT or a strategy .py path — never a live object."""
    if not isinstance(ref, str):
        raise TypeError("draw_examples takes a strategy REFERENCE ('builtin:text' or a "
                        ".py path), not a live strategy object — live-object draws are "
                        "not reproducible across processes (see module docstring)")
    INPUTS.mkdir(parents=True, exist_ok=True)
    cache = INPUTS / f"{input_set_id(ref, n, seed)}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    proc = subprocess.run([sys.executable, str(_DRAW), ref, str(n), str(seed)],
                          capture_output=True, text=True, check=True)
    xs = json.loads(proc.stdout)
    # Atomic publish: parallel matrix cells may race on the same key, and a
    # reader must see either no file or a complete one — never a torn write.
    tmp = cache.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(xs))
    os.replace(tmp, cache)
    return xs


# --- the measurement -------------------------------------------------------------

_OUTCOME = {0: "valid", 2: "reject", 10: "skip", 11: "skip"}


def measure_cell(target: str, examples: list[str], label: str) -> dict:
    """Run `examples` through the target's coverage build once; return coverage
    (region/line/branch %) and the proxy metrics computed on the same inputs."""
    from agent import summarize  # noqa: E402  (loop's own summarizer)
    binary = cov_binary(target)
    profdir = BUILD / f"_cov_{target}_{label}"
    profdir.mkdir(exist_ok=True)
    for old in profdir.glob("*.profraw"):
        old.unlink()
    samples = []
    for i, ex in enumerate(examples):
        data = ex.encode("utf-8", "surrogatepass")
        env = {"LLVM_PROFILE_FILE": str(profdir / f"{i}.profraw")}
        p = subprocess.run([str(binary)], input=data, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        samples.append((ex, _OUTCOME.get(p.returncode, "crash")))
    raws = [str(p) for p in profdir.glob("*.profraw")]
    merged = profdir / "merged.profdata"
    subprocess.run([*_llvm("llvm-profdata"), "merge", "-sparse", *raws,
                    "-o", str(merged)], check=True)
    rep = subprocess.run(
        [*_llvm("llvm-cov"), "report", str(binary),
         f"-instr-profile={merged}", str(target_src(target))],
        capture_output=True, text=True, check=True).stdout
    total = [ln for ln in rep.splitlines() if ln.strip().startswith("TOTAL")][0]
    pcts = [float(t.rstrip("%")) for t in total.split() if t.endswith("%")]
    # llvm-cov report columns: region%, function%, line%, branch%
    s = summarize(samples)
    return {
        "region": pcts[0], "line": pcts[2], "branch": pcts[3],
        "acceptance": s["acceptance_rate"],
        "novelty": s["novelty"],
        "cap_mass": s["cap_distance_mass"],
        "productions": len(s["productions_accepted"]),
        "crashes": sum(1 for _, o in samples if o == "crash"),
    }


def measure_ref(target: str, ref: str, n: int, seed: int, label: str) -> dict:
    """Convenience: draw the reproducible input set for `ref` and measure it,
    recording the input-set id so a reader can verify identical inputs."""
    r = measure_cell(target, draw_examples(ref, n, seed), label)
    r["input_set"] = input_set_id(ref, n, seed)
    return r
