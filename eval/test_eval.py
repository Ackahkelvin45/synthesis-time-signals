"""test_eval.py — the evaluation plumbing (paper branch): reachable-region
call-graph extraction, llvm-cov parsers, and one real coverage curve.
Run:  .venv/bin/python eval/test_eval.py   (needs ./run.sh build for the curve)
"""
from __future__ import annotations

import json
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

    # --- replicate-level statistics on synthetic data with KNOWN effects -----
    import random
    import report
    check("A12 = 1 when every a beats every b", report.a12([1, 2, 3], [0, 0, 0]) == 1.0)
    check("A12 = 0.5 for identical groups", report.a12([1, 2, 3], [1, 2, 3]) == 0.5)
    check("permutation p ~ 1 for identical groups",
          report.perm_two_sample([1, 2, 3, 4], [1, 2, 3, 4], iters=2000) > 0.5)
    check("permutation p small for separated groups",
          report.perm_two_sample([10, 11, 12, 13, 14], [0, 1, 2, 3, 4], iters=2000) < 0.01)
    check("parse_run_cond", report.parse_run_cond("run:C3n-rep7:last") == ("C3n", 7, "last")
          and report.parse_run_cond("run:ablate-x:final") is None)
    rng = random.Random(1)
    data: dict = {"synth": {}}
    base = {"region": 50.0, "line": 60.0, "branch": 40.0, "acceptance": 0.5, "novelty": 5, "cap_mass": 0.0}

    def rows(level):
        return {sd: {**base, "auc_branch_reach": level + rng.gauss(0, 0.5)} for sd in range(20)}
    data["synth"]["random"] = rows(20.0)
    data["synth"]["seed"] = rows(40.0)
    data["synth"]["evolved"] = rows(43.0)
    for k in range(1, 11):
        seed_lvl = 40.0 + rng.gauss(0, 1.0)
        data["synth"][f"run:C2-rep{k}:seed"] = rows(seed_lvl)
        data["synth"][f"run:C2-rep{k}:final"] = rows(seed_lvl + 3.0)
        data["synth"][f"run:C2-rep{k}:last"] = rows(seed_lvl + 2.5)
        data["synth"][f"run:A5-rep{k}:seed"] = rows(seed_lvl)
        data["synth"][f"run:A5-rep{k}:final"] = rows(seed_lvl + 0.2)
        data["synth"][f"run:C3s-rep{k}:seed"] = rows(seed_lvl)
        data["synth"][f"run:C3s-rep{k}:final"] = rows(seed_lvl + 5.0)
    text = report.render(data, Path("synthetic"))
    check("report: replicate section uses the pre-registered primary outcome",
          "primary outcome `auc_branch_reach`" in text)
    h1 = next((ln for ln in text.splitlines() if "H1: proxy (C2) vs no-steering (A5)" in ln), "")
    import re as _re

    def _a12_of(line):
        m = _re.search(r"A12=([0-9.]+)", line)
        return float(m.group(1)) if m else -1.0

    def _p_of(line):
        m = _re.search(r"permutation p=([0-9.]+)", line)
        return float(m.group(1)) if m else 1.0
    check("report: H1 detects C2 > A5 (A12 >= 0.9, p < 0.01)",
          _a12_of(h1) >= 0.9 and _p_of(h1) < 0.01, h1)
    h2 = next((ln for ln in text.splitlines() if "H2: coverage-scalar (C3s) vs proxy (C2)" in ln), "")
    check("report: H2 detects C3s > C2 (A12 >= 0.9, p < 0.01)",
          _a12_of(h2) >= 0.9 and _p_of(h2) < 0.01, h2)
    c2row = next((ln for ln in text.splitlines() if ln.startswith("| C2 | 10 |")), "")
    check("report: C2 has 10 replicates, a last-iteration column, and Δ≈+3 with sign-flip p",
          c2row.count("|") == 7 and "+3." in c2row, c2row)
    check("report: replicate runs are NOT in the Holm ablation family",
          "run:C2-rep1:final: Δ=" not in text)

    # --- Grammarinator baseline (C0b): pinned generator, seeded, no Hypothesis ---
    import subprocess as _sp
    ref_d = cell.grammarinator_ref("JSON", "defaults")
    ref_deep = cell.grammarinator_ref("JSON", "deep")
    a = cell.draw_examples(ref_d, 200, 0)
    b = json.loads(_sp.run([sys.executable, str(ROOT / "eval" / "_draw.py"), ref_d, "200", "0"],
                           capture_output=True, text=True, check=True).stdout)
    check("grammarinator: draws are identical across two fresh processes", a == b)
    check("grammarinator: every draw is a str", all(isinstance(x, str) for x in a))
    check("grammarinator: a different seed gives a different set",
          cell.draw_examples(ref_d, 200, 1) != a)
    check("grammarinator: input-set id differs between defaults and deep",
          cell.input_set_id(ref_d, 200, 0) != cell.input_set_id(ref_deep, 200, 0))
    import formats as _fm
    F = _fm.get("JSON")
    check("grammarinator: every draw is grammar-valid (strict ANTLR parse)",
          all(F.parse(x) is not None for x in a))
    md = sum(F.depth(x) for x in cell.draw_examples(ref_deep, 500, 0)) / 500
    mdef = sum(F.depth(x) for x in cell.draw_examples(ref_d, 500, 0)) / 500
    check("grammarinator: deep variant is deeper than defaults (calibrated to the seed)",
          md > mdef and 0.4 < md < 1.2, f"{mdef:.2f} -> {md:.2f}")
    pin = cell.grammarinator_pin("JSON")
    import hashlib as _hh
    check("grammarinator: generator sha256 matches the pin",
          _hh.sha256((ROOT / pin["generator"]).read_bytes()).hexdigest() == pin["sha256"])

    print(f"\n{_p} passed, {_f} failed")
    return 1 if _f else 0


if __name__ == "__main__":
    raise SystemExit(main())
