"""reach.py — the parse-reachable region of a target (paper plan, step 7).

Absolute coverage of a whole source file is not comparable across targets: a
parse-only harness can never reach a library's serializer / query / mutation
APIs, and how much of the file those occupy varies wildly (random text reaches
~42% of json-parser's json.c but ~5% of parson's parson.c). The paper's
primary outcome is therefore branch coverage of the PARSE-REACHABLE REGION:
the functions of the target source that the harness entry point can reach.

Definition (operational, auditable, per target):
  reachable = STATIC  union  OBSERVED
  STATIC    = functions of the target source reachable from `harness_parse`
              in the direct call graph extracted from clang's LLVM IR of the
              library and the harness (function-pointer calls are invisible
              here; json-parser's allocator hooks are such calls)
  OBSERVED  = functions with at least one covered region in any coverage
              profile handed to `build` (closes the function-pointer gap)
The list is written to eval/reachable/<target>.json with its provenance and
COMMITTED. The evaluation's sanity check (plan E9) fails if any cell ever
covers a function outside the list, which forces regeneration and a note.

    python eval/reach.py --target json-parser [--profdata a.profdata ...]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fuzz"))
sys.path.insert(0, str(ROOT / "eval"))
from targets import TARGETS  # noqa: E402

OUT_DIR = ROOT / "eval" / "reachable"
ENTRY = "harness_parse"

_DEF = re.compile(r"^define [^@]*@([A-Za-z0-9_.]+)\(")
_CALL = re.compile(r"\bcall [^@%]*@([A-Za-z0-9_.]+)\(")


def _ir(src: Path, inc: list[Path]) -> str:
    cmd = [os.environ.get("CC", "clang"), "-S", "-emit-llvm", "-O0",
           *[a for i in inc for a in ("-I", str(i))], str(src), "-o", "-"]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def callgraph(ir_text: str) -> dict[str, set[str]]:
    """{function: {direct callees}} from LLVM IR text."""
    graph: dict[str, set[str]] = {}
    cur: str | None = None
    for ln in ir_text.splitlines():
        m = _DEF.match(ln)
        if m:
            cur = m.group(1)
            graph.setdefault(cur, set())
            continue
        if cur is None:
            continue
        if ln.startswith("}"):
            cur = None
            continue
        for c in _CALL.finditer(ln):
            callee = c.group(1)
            if not callee.startswith("llvm."):
                graph[cur].add(callee)
    return graph


def static_reachable(target: str, entry: str = ENTRY) -> tuple[set[str], set[str]]:
    """(reachable functions defined in the target source, all functions defined
    in the target source)."""
    t = TARGETS[target]
    inc = [ROOT / t["inc"], ROOT / "harness"]
    lib_graph = callgraph(_ir(ROOT / t["src"], inc))
    harness_graph = callgraph(_ir(ROOT / t["harness"], inc))
    lib_funcs = set(lib_graph)
    graph = {**lib_graph, **harness_graph}
    seen: set[str] = set()
    stack = [entry]
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        stack.extend(graph.get(f, ()))
    return seen & lib_funcs, lib_funcs


def observed_functions(target: str, profdata: Path) -> set[str]:
    from cell import function_coverage  # noqa: E402
    return {r["name"] for r in function_coverage(target, profdata)
            if r["regions_missed"] < r["regions"]}


def build(target: str, profdatas: list[Path]) -> dict:
    static, all_funcs = static_reachable(target)
    observed: set[str] = set()
    for p in profdatas:
        observed |= observed_functions(target, p)
    observed &= all_funcs
    reachable = sorted(static | observed)
    doc = {
        "target": target, "entry": ENTRY,
        "source": TARGETS[target]["src"], "harness": TARGETS[target]["harness"],
        "static": sorted(static),
        "observed_extra": sorted(observed - static),
        "reachable": reachable,
        "unreachable": sorted(all_funcs - set(reachable)),
        "functions_total": len(all_funcs),
        "profiles_used": [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
                          for p in profdatas],
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{target}.json").write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def reachable(target: str) -> list[str] | None:
    """The committed list, or None if it has not been generated."""
    p = OUT_DIR / f"{target}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())["reachable"]


def name_regex(names: list[str]) -> str:
    """llvm-cov -name-regex for exactly these functions. Static (internal)
    functions are listed as `file.c:name`, so an optional `<file>:` prefix is
    allowed; without it every static function silently drops out of the
    restricted totals (found by checking the numbers, not by reading docs)."""
    return "^([^:]+:)?(" + "|".join(re.escape(n) for n in names) + ")$"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--target", default="json-parser")
    ap.add_argument("--profdata", nargs="*", default=[],
                    help="merged .profdata files whose covered functions are added")
    args = ap.parse_args()
    doc = build(args.target, [Path(p) for p in args.profdata])
    print(f"[reach] {args.target}: {len(doc['reachable'])}/{doc['functions_total']} functions "
          f"reachable (static {len(doc['static'])}, observed extra {len(doc['observed_extra'])}); "
          f"unreachable: {', '.join(doc['unreachable']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
