"""test_eval.py — the evaluation plumbing (paper branch): reachable-region
call-graph extraction, llvm-cov parsers, and one real coverage curve.
Run:  .venv/bin/python eval/test_eval.py   (needs ./run.sh build for the curve)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "fuzz"))

import reach  # noqa: E402
import cell  # noqa: E402

_p = _f = 0


def check(name, cond, extra=""):
    global _p, _f
    _p += bool(cond); _f += not cond
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"   {extra}"))


IR = """\
define internal i32 @harness_parse(ptr %0) #0 {
  %5 = call ptr @lib_parse(ptr %0)
  call void @lib_free(ptr %5)
  ret i32 0
}
define ptr @lib_parse(ptr %0) #0 {
  %2 = call ptr @lib_new()
  %3 = call i32 (ptr, ...) @printf(ptr @.str)
  %4 = call ptr %fnptr(i64 8)
  call void @llvm.memset.p0.i64(ptr %2, i8 0, i64 8, i1 false)
  ret ptr %2
}
define ptr @lib_new() #0 {
  ret ptr null
}
define void @lib_free(ptr %0) #0 {
  ret void
}
define void @lib_unused() #0 {
  call void @lib_free(ptr null)
  ret void
}
"""


def main() -> int:
    g = reach.callgraph(IR)
    check("callgraph: direct callees per function",
          g["harness_parse"] == {"lib_parse", "lib_free"} and g["lib_parse"] == {"lib_new", "printf"},
          str(g))
    check("callgraph: intrinsics and indirect calls are not edges",
          "llvm.memset.p0.i64" not in g["lib_parse"] and not any("fnptr" in c for c in g["lib_parse"]))
    check("name_regex anchors, escapes, and admits llvm-cov's `file:` prefix for statics",
          reach.name_regex(["a.b", "c"]) == r"^([^:]+:)?(a\.b|c)$")
    rows = cell.parse_function_report(
        "Name Regions Miss Cover Lines Miss Cover Branches Miss Cover\n"
        "x.c:f 10 2 80.00% 8 1 87.50% 4 4 0.00%\nTOTAL 10 2 80.00% 8 1 87.50% 4 4 0.00%\n")
    check("function report: one row, TOTAL excluded, file prefix stripped",
          len(rows) == 1 and rows[0]["name"] == "f" and rows[0]["branch_pct"] == 0.0)

    for t in ("json-parser", "parson"):
        r = reach.reachable(t)
        check(f"committed reachable list exists for {t}", r is not None and len(r) > 0)
    jp = reach.reachable("json-parser") or []
    check("json-parser: allocator hooks (function-pointer calls) are in the region",
          "default_alloc" in jp and "default_free" in jp, str(jp))
    check("json-parser: the unused json_parse wrapper is outside the region", "json_parse" not in jp)

    if cell.cov_binary("json-parser").exists():
        ex = ['[1,2]', '{"a":1}', '[', '"x"', 'null', '[[1]]', 'tru', '1e309'] * 4
        cc = cell.coverage_curve("json-parser", ex, [8, 16, 32], "test_eval")
        ns = sorted(cc["curve"])
        check("coverage curve: checkpoints present incl. the final n", ns == [8, 16, 32], str(ns))
        mono = all(cc["curve"][a]["branch"] <= cc["curve"][b]["branch"] for a, b in zip(ns, ns[1:]))
        check("coverage curve: cumulative branch coverage is monotone", mono)
        last = cc["curve"][32]
        check("coverage curve: reachable-region totals present and >= whole-file",
              "branch_reach" in last and last["branch_reach"] >= last["branch"], str(last))
        check("coverage curve: repeated inputs add no coverage (8 == 16 == 32)",
              cc["curve"][8]["branch"] == cc["curve"][32]["branch"])
        check("coverage curve: no lost segments", cc["lost_segments"] == 0)
        # The restriction must be exact: restricted to ALL functions == whole file.
        prof = Path(last["profdata"])
        allf = [r["name"] for r in cell.function_coverage("json-parser", prof)]
        whole = cell._cov_totals(cell.cov_binary("json-parser"), prof, cell.target_src("json-parser"))
        restricted = cell._cov_totals(cell.cov_binary("json-parser"), prof,
                                      cell.target_src("json-parser"), allf)
        check("restricted totals over ALL functions equal the whole-file totals (statics included)",
              whole == restricted, f"{whole} vs {restricted}")
        # json-parser: only json_parse (1 region, uncovered) is outside the region,
        # so region coverage restricted must be slightly HIGHER than whole-file.
        check("json-parser reachable-region coverage excludes exactly the uncovered wrapper",
              last["region_reach"] > last["region"], str(last))
    else:
        print("  SKIP  coverage curve (no coverage binary; run ./run.sh build + eval/coverage.py)")

    print(f"\n{_p} passed, {_f} failed")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
