"""tables.py — generated paper tables (never hand-edited).

T1  targets: source lines, functions, parse-reachable region size, grammar, ground-truth bugs
T2  per target and arm: final level (mean ± 95% CI, median), collapsed replicates,
    per-replicate delta final − seed (mean ± CI, sign-flip p), last-working level where it differs

    python eval/tables.py --inputs eval/matrix/stage1.jsonl eval/matrix/stage1c.jsonl eval/matrix/day1.jsonl --out eval/matrix/tables.md
"""
import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from targets import TARGETS  # noqa: E402
from cell import measure_for_loop  # noqa: E402
from experiment import ci95, paired_perm_test  # noqa: E402
from full_report import load, level, collapsed  # noqa: E402

ARMS = ("C2", "A5", "C3s", "C3n", "C2R", "M2C2", "M2A5", "M2C3s")
# canonical arm names: used identically in prose, tables, figures and captions
NAME = {"C2": "C2 proxy", "A5": "A5 no steering", "C3s": "C3s coverage", "C3n": "C3n coverage+names",
        "C2R": "C2' re-seed repair",
        "M2C2": "C2 proxy (gpt-5-mini)", "M2A5": "A5 no steering (gpt-5-mini)", "M2C3s": "C3s coverage (gpt-5-mini)"}
TARGET_ORDER = ("json-parser", "parson", "tomlc99", "cjson")


def t1():
    L = ["## T1. Targets", "", "| target | source | lines | functions | parse-reachable functions | grammar (grammars-v4) | ground-truth bug builds | role |",
         "|-------|----------|-----|--------|----------|--------------|--------------|-----------|"]
    role = {"json-parser": "development (in-sample)", "parson": "held out", "tomlc99": "held out", "cjson": "held out (Stage 2)"}
    for t, v in TARGETS.items():
        src = ROOT / v["src"]
        lines = sum(1 for _ in src.open())
        r = json.loads((ROOT / "eval" / "reachable" / f"{t}.json").read_text())
        reach = len(set(r["static"]) | set(r.get("observed_extra", [])))
        total = measure_for_loop(t, ["[1]"], f"t1_{t}")["functions_total"]
        bugs = ", ".join(v.get("bugs", {}).keys()) or "none"
        gram = ", ".join(Path(g).name for g in v.get("grammars", (v["grammar"],)))
        L.append(f"| {t} | {Path(v['src']).name} | {lines} | {total} | {reach} | {gram} | {bugs} | {role[t]} |")
    return L + [""]


def t2(data):
    L = ["## T2. Final-generator level and refinement delta per target and arm", "",
         "Primary outcome auc_branch_reach (10^4 inputs x 20 draw seeds per replicate; failed cells and collapsed finals score 0). "
         "Mean ± 95% CI over ten replicates (median); coll. = collapsed replicates; last working = the last working iteration's level where it differs from the final (n = replicates where it differs). Δ = final − seed per replicate, exact sign-flip test; replicates whose seed "
         "generator failed but whose final works are excluded from Δ and counted under seed failed.", "",
         "| target | arm | final | coll. | Δ final − seed | up / down | sign-flip p | seed failed | last working |",
         "|--------|--------------|-----------------|-----|--------------|-------|--------|-------|-----------|"]
    for t in ("json-parser", "parson", "tomlc99", "cjson"):
        d = data[t]
        for c in ARMS:
            fin, seed = level(d, c, "final"), level(d, c, "seed")
            if not fin:
                continue
            mu, h = ci95(list(fin.values()))
            col = collapsed(d, c)
            reps = [k for k in sorted(fin) if k in seed]
            infl = [k for k in reps if all(x == 0.0 for x in d[c][k]["seed"].values()) and fin[k] > 0]
            ok = [k for k in reps if k not in infl]
            if len(ok) >= 2:
                dd, half, p = paired_perm_test([seed[k] for k in ok], [fin[k] for k in ok])
                ds = [fin[k] - seed[k] for k in ok]
                dcell, ud, pcell = f"{dd:+.2f} ± {half:.2f}", f"{sum(x > 0 for x in ds)} / {sum(x < 0 for x in ds)}", f"{p:.3f}"
            else:
                dcell = ud = pcell = "-"
            last = level(d, c, "last")
            lcell = f"{st.mean(last.values()):.1f} (n {len(last)})" if last else "-"
            L.append(f"| {t} | {NAME[c]} | {mu:.1f} ± {h:.1f} ({st.median(fin.values()):.1f}) | {len(col)} | {dcell} | {ud} | {pcell} | "
                     f"{len(infl)} | {lcell} |")
    return L + [""]


def t3(fixed_path):
    """RQ1: the twenty LLM seed generators per target against random text and Grammarinator (fixed.jsonl)."""
    from rq1_report import load as rq1_load
    from report import a12, bootstrap_a12
    loop, _ = rq1_load(ROOT / "eval/matrix/stage1.jsonl", "auc_branch_reach")
    loop2, _ = rq1_load(ROOT / "eval/matrix/day2.jsonl", "auc_branch_reach")   # cJSON seeds
    for t, v in loop2.items():
        loop[t].update(v)
    _, fixed = rq1_load(ROOT / fixed_path, "auc_branch_reach")
    L = ["## T3. RQ1: the LLM seed generators against random text and Grammarinator on the identical grammar", "",
         "Primary outcome at 10^4 inputs, draw seeds 0..19. Fixed generators: mean over the 20 draw seeds. "
         "LLM seed: mean over the 20 seed generators of C2 and A5 (identical seed prompt), a generator whose every cell "
         "failed scoring 0; healthy = generators that drew on at least one seed. A12 = P(a healthy LLM seed generator's "
         "mean exceeds a Grammarinator input set's value) against the stronger Grammarinator variant, bootstrap 95% CI.", "",
         "| target | random text | Grammarinator defaults | Grammarinator depth-matched | LLM seed (20) | healthy | A12 healthy seeds vs stronger Grammarinator |",
         "|-----------|--------|----------|-----------|----------|------|----------------------|"]
    for t in TARGET_ORDER:
        gens = {(c, k): v for (c, k, w), v in loop[t].items() if w == "seed"}
        gens = {(c, k): v for (c, k), v in gens.items() if c in ("C2", "A5")}
        if not gens or not fixed.get(t):
            L.append(f"| {t} | not measured | not measured | - | {st.mean(st.mean(v.values()) for v in gens.values()):.1f} | "
                     f"{sum(1 for v in gens.values() if any(x > 0 for x in v.values()))} of {len(gens)} | not measured |" if gens else f"| {t} | - | - | - | - | - | - |")
            continue
        f = fixed[t]
        rnd = st.mean(f["random"].values()) if "random" in f else None
        gd = st.mean(f["grammarinator"].values())
        gdeep = st.mean(f["grammarinator-deep"].values()) if "grammarinator-deep" in f else None
        strong = "grammarinator-deep" if gdeep is not None and gdeep > gd else "grammarinator"
        means = [st.mean(v.values()) for v in gens.values()]
        healthy = [st.mean(v.values()) for v in gens.values() if any(x > 0 for x in v.values())]
        eff = a12(healthy, list(f[strong].values())); lo, hi = bootstrap_a12(healthy, list(f[strong].values()))
        L.append(f"| {t} | {rnd:.1f} | {gd:.1f} | {'-' if gdeep is None else f'{gdeep:.1f}'} | {st.mean(means):.1f} | "
                 f"{len(healthy)} of {len(means)} | {eff:.2f} [{lo:.2f}, {hi:.2f}] |")
    return L + [""]


def t4():
    """RQ5: cause class by arm, copied from the generated taxonomy report (eval/matrix/taxonomy.md)."""
    tx = (ROOT / "eval/matrix/taxonomy.md").read_text()
    head = re.search(r"Guard events over (\d+) completed replicates.*?(\d+) events", tx, re.S)
    i = tx.index("## Cause class by arm"); j = tx.index("\n## ", i + 5)
    block = [l for l in tx[i:j].splitlines() if l.startswith("|")]
    block[0] = block[0].replace("| C2R |", "| C2' |")
    block[1] = "|------------------------------|-----|-----|-----|-----|-----|------|"
    return ["## T4. RQ5: guard events by cause class and arm", "",
            f"{head.group(2)} events over {head.group(1)} completed replicates (four targets), coded from the recorded "
            "exception and rejection text by ordered regular expressions, first match wins; iterations without an event are not listed. "
            "Arm codes as in Table 1.", ""] + block + [""]


EDIT_CLASS = {"intensify_near_crash": "crash", "increase_branch_coverage": "signal", "cover_function": "signal",
              "add_or_upweight_production": "signal", "generate_nesting_toward_cap": "signal", "broaden_exploration": "signal",
              "fix_feature_encoding": "signal", "improve_strategy": "improve", "revert_last_edit": "revert"}


def t5():
    """The refinement instruction issued for iterations 2 to 5, per target and arm, from evolution.md."""
    from cell import runs_dir
    L = ["## T5. Which refinement instruction the loop issued, iterations 2 to 5, per target and arm", "",
         "Counts over ten replicates x four refinements = 40 per cell, read from each run's evolution log. "
         "crash = \"mutate structurally around the crashing input\" (issued whenever the previous iteration saw a new crash signature, in every arm); "
         "signal = the arm's own edit (C2: add or up-weight a production, generate deeper, broaden, fix a feature; C3s: increase branch coverage; "
         "C3n: cover function F); improve = \"make it a better fuzzer\" (A5's only edit); revert = roll back the last edit; "
         "repair = the previous iteration was gated or its build was rejected, so the next prompt is a repair or a re-seed, not a refinement.", "",
         "| target | arm | crash | signal | improve | revert | repair |",
         "|-----------|--------------------|-----|------|-------|------|------|"]
    for t in TARGET_ORDER:
        for c in ("C2", "A5", "C3s", "C3n", "C2R"):
            cnt = {"crash": 0, "signal": 0, "improve": 0, "revert": 0, "repair": 0}; n = 0
            for k in range(1, 11):
                ev = runs_dir(t) / f"{c}-rep{k}" / "evolution.md"
                if not ev.exists():
                    continue
                n += 1
                for line in ev.read_text().splitlines():
                    m = re.match(r"- iter (\d+): (.*)", line)
                    if not m or int(m.group(1)) > 4:
                        continue
                    nx = re.search(r"next: ([a-z_]+)", m.group(2))
                    cnt[EDIT_CLASS[nx.group(1)] if nx else "repair"] += 1
            if n:
                assert sum(cnt.values()) == 4 * n, (t, c, cnt, n)
                L.append(f"| {t} | {NAME[c]} | {cnt['crash']} | {cnt['signal']} | {cnt['improve']} | {cnt['revert']} | {cnt['repair']} |")
    return L + [""]


def t6():
    """Cost per target, condensed from the generated per-arm cost table (eval/matrix/cost_table.md)."""
    rows = [l for l in (ROOT / "eval/matrix/cost_table.md").read_text().splitlines() if l.startswith("| ") and not l.startswith("| target")]
    per = {}
    for l in rows:
        c = [x.strip() for x in l.strip("|").split("|")]
        per.setdefault(c[0], []).append((int(c[2]), float(c[3]), float(c[4]), float(c[5]), float(c[6]), float(c[7])))
    L = ["## T6. Synthesis cost per run, by target", "",
         "Mean over every completed run of the five DeepSeek arms (C2, A5, C3s, C3n, C2'); every call served by deepseek-flash; "
         "the per-arm table is in the artifact (eval/matrix/cost_table.md).", "",
         "| target | runs | LLM calls | tokens in | tokens out | USD per run | wall minutes |",
         "|-----------|------|------|--------|--------|--------|--------|"]
    tot_runs = tot_usd = 0.0
    for t in TARGET_ORDER:
        if t not in per:
            continue
        v = per[t]; n = sum(x[0] for x in v); w = [x[0] / n for x in v]
        m = lambda i: sum(wi * x[i] for wi, x in zip(w, v))  # noqa: E731
        tot_runs += n; tot_usd += sum(x[0] * x[4] for x in v)
        L.append(f"| {t} | {n} | {m(1):.1f} | {m(2):.0f} | {m(3):.0f} | {m(4):.3f} | {m(5):.1f} |")
    import re as _re
    tot = _re.search(r"All runs: (\d+); total ([0-9.]+) USD; mean ([0-9.]+) USD, ([0-9.]+) min", (ROOT / "eval/matrix/cost_table.md").read_text())
    L.append(f"| all | {tot.group(1)} | | | | {tot.group(3)} (total {tot.group(2)}) | {tot.group(4)} |")
    return L + [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--fixed", default="eval/matrix/fixed.jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data, _ = load(a.inputs)
    L = ["# Generated tables", ""] + t1() + t2(data) + t3(a.fixed) + t4() + t5() + t6()
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
