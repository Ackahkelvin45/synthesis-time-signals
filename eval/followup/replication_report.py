"""replication_report.py: the pre-registered analysis (PLAN_replication.md, sections 4 to 6). Run once,
after every cell is measured.

Confirmatory family, Holm at 0.05 over three hypotheses, unit = replicate pair (shared draft),
statistic = mean over the three targets of the per-target mean paired difference:
  H1  R3 - R2 < 0           (names worse than numbers)             one-sided stratified sign-flip
  H2  R1 - R0 < 0           (proxy summary worse than no feedback)  one-sided stratified sign-flip
  H3  |R2 - R0| < 2 points  (coverage numbers equivalent to none)   TOST, p = max of two one-sided tests
Secondary (outside the family): bridge B5 vs September A5, finals and first drafts.
Exploratory (uncorrected): R4-R3, R4-R2, E1-E0, E0-R0, and the menu choices.
A final or draft that does not draw scores 0. --alias maps arm names (code check on other data only).

    .venv/bin/python eval/followup/replication_report.py --inputs eval/matrix/stage1.jsonl \
        eval/matrix/day1.jsonl eval/matrix/day2.jsonl eval/matrix/replication.jsonl > eval/matrix/replication.md
"""
import argparse, json, random, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "eval"))
from report import parse_run_cond, a12  # noqa: E402

TARGETS, MARGIN, ALPHA, ITERS = ("parson", "tomlc99", "cjson"), 2.0, 0.05, 100_000
FAMILY = [("H1", "R3", "R2", "less", "numbers and names minus numbers"),
          ("H2", "R1", "R0", "less", "proxy summary minus no feedback"),
          ("H3", "R2", "R0", "equiv", "coverage numbers minus no feedback")]
EXPLORATORY = [("R4", "R3", "numbers, names and source minus numbers and names"),
               ("R4", "R2", "numbers, names and source minus numbers"),
               ("E1", "E0", "menu: proxy summary minus no feedback"),
               ("E0", "R0", "no feedback: menu minus plain instruction"),
               ("E1", "R1", "proxy summary: menu minus plain instruction")]


def load(paths, alias):
    v = defaultdict(lambda: defaultdict(dict))  # (target, arm, rep, what) -> seed -> value
    for src in paths:
        for line in Path(src).read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line); pr = parse_run_cond(r["condition"])
            if not pr: continue
            arm, k, what = pr; arm = alias.get(arm, arm)
            v[(r["target"], arm, k, what)][r["seed"]] = 0.0 if "error" in r else r["auc_branch_reach"]
    return v


def rep_value(v, t, arm, k, what="final"):
    d = v.get((t, arm, k, what)); return st.mean(d.values()) if d and len(d) == 20 else None


def diffs(v, x, y):
    out = {}
    for t in TARGETS:
        ks = [k for k in range(1, 11) if rep_value(v, t, x, k) is not None and rep_value(v, t, y, k) is not None]
        out[t] = [rep_value(v, t, x, k) - rep_value(v, t, y, k) for k in ks]
    return out


def stat(d): return st.mean(st.mean(z) for z in d.values() if z)


def flip_p(d, side, shift=0.0, seed=0):
    rng = random.Random(seed); dd = {t: [x - shift for x in z] for t, z in d.items()}; obs = stat(dd); hit = 0
    for _ in range(ITERS):
        s = stat({t: [x if rng.random() < 0.5 else -x for x in z] for t, z in dd.items()})
        hit += (s <= obs + 1e-12) if side == "less" else (s >= obs - 1e-12)
    return (hit + 1) / (ITERS + 1)


def boot(d, level=0.95, seed=0):
    rng = random.Random(seed); b = sorted(stat({t: rng.choices(z, k=len(z)) for t, z in d.items() if z}) for _ in range(10_000))
    lo = (1 - level) / 2; return b[int(lo * 10_000)], b[int((1 - lo) * 10_000) - 1]


def fmt(d):
    return " | ".join(f"{st.mean(z):+.2f} ({sum(x > 0 for x in z)}/{sum(x < 0 for x in z)}/{sum(x == 0 for x in z)})" if z else "n/a" for z in (d[t] for t in TARGETS))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); adj = [0.0] * len(ps); run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i])); adj[i] = run
    return adj


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--alias", default="", help="code check only, e.g. SF0=R0,SF1=R1")
    a = ap.parse_args(); alias = dict(x.split("=") for x in a.alias.split(",") if x)
    v = load(a.inputs, alias)
    print("# Pre-registered replication: results\n")
    if alias: print(f"**CODE CHECK ON ALIASED DATA ({a.alias}); not the replication.**\n")
    print(f"Unit: replicate pair on a shared draft. Statistic: mean over {', '.join(TARGETS)} of the per-target mean paired difference, coverage points. "
          f"Sign-flip tests with {ITERS} random flips, seed 0. Per-target cells: mean (up/down/zero).\n")
    print("## Confirmatory family (Holm, alpha 0.05)\n")
    print("| hypothesis | contrast | pairs | pooled mean [95% CI] | 90% CI | " + " | ".join(TARGETS) + " | p | Holm p | decision |")
    print("|---|---|---|---|---|" + "---|" * len(TARGETS) + "---|---|---|")
    rows, ps = [], []
    for h, x, y, side, label in FAMILY:
        d = diffs(v, x, y)
        if not all(d[t] for t in TARGETS):
            print(f"| {h} | {label} | {sum(map(len, d.values()))} | incomplete data: not tested | | " + " | " * len(TARGETS) + " | | not tested |"); continue
        if side == "equiv":
            p = max(flip_p(d, "greater", shift=-MARGIN), flip_p(d, "less", shift=MARGIN))
        else:
            p = flip_p(d, side)
        rows.append((h, label, d, p)); ps.append(p)
    for (h, label, d, p), q in zip(rows, holm(ps)):
        lo, hi = boot(d); l9, h9 = boot(d, 0.90)
        dec = ("supported" if q < ALPHA else "not supported") + (f" (equivalence within ±{MARGIN})" if h == "H3" else "")
        print(f"| {h} | {label} | {sum(map(len, d.values()))} | {stat(d):+.2f} [{lo:+.2f}, {hi:+.2f}] | [{l9:+.2f}, {h9:+.2f}] | {fmt(d)} | {p:.4f} | {q:.4f} | {dec} |")
    print("\n## Bridge (secondary): current backend B5 against September A5, unpaired\n")
    print("| target | what | September A5 mean (n) | B5 mean (n) | B5 minus A5 [95% CI] | A12 (B5 vs A5) |\n|---|---|---|---|---|---|")
    for t in TARGETS:
        for what in ("seed", "final"):
            a5 = [x for x in (rep_value(v, t, "A5", k, what) for k in range(1, 11)) if x is not None]
            b5 = [x for x in (rep_value(v, t, "B5", k, what) for k in range(1, 11)) if x is not None]
            if not a5 or not b5: continue
            rng = random.Random(0); bs = sorted(st.mean(rng.choices(b5, k=len(b5))) - st.mean(rng.choices(a5, k=len(a5))) for _ in range(10_000))
            print(f"| {t} | {what} | {st.mean(a5):.1f} ({len(a5)}) | {st.mean(b5):.1f} ({len(b5)}) | {st.mean(b5) - st.mean(a5):+.2f} [{bs[250]:+.2f}, {bs[9749]:+.2f}] | {a12(b5, a5):.2f} |")
    print("\n## Exploratory (uncorrected)\n")
    print("| contrast | pairs | pooled mean [95% CI] | " + " | ".join(TARGETS) + " | two-sided p |\n|---|---|---|" + "---|" * len(TARGETS) + "---|")
    for x, y, label in EXPLORATORY:
        d = diffs(v, x, y)
        if not all(d[t] for t in TARGETS): continue
        lo, hi = boot(d); p = min(1.0, 2 * min(flip_p(d, "less"), flip_p(d, "greater")))
        print(f"| {label} | {sum(map(len, d.values()))} | {stat(d):+.2f} [{lo:+.2f}, {hi:+.2f}] | {fmt(d)} | {p:.4f} |")
    print("\n## Menu choices (E arms, from the EDIT: line of each refinement response)\n")
    for arm in ("E0", "E1"):
        c = defaultdict(int)
        for t in TARGETS:
            for f in (ROOT / "runs" / t).glob(f"{arm}-rep*/iter-*/response.md"):
                m = re.search(r"EDIT:\s*([a-z_]+)", f.read_text(errors="replace")); c[m.group(1) if m else "(none named)"] += 1
        if c: print(f"- {arm}: " + ", ".join(f"{k} {n}" for k, n in sorted(c.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
