"""replication2_report.py: the second pre-registered analysis (PLAN_replication2.md, sections 4 and 5).
Run once, after every cell is measured.

Arms Q0..Q3 run under --policy strict (a gated generator falls back to the last working one).
A final is collapsed when any of its 20 measured cells errors (after the one re-measurement); it scores 0.
Confirmatory family, Holm at 0.05 over two hypotheses, all 20 pairs per target:
  K1  Q3 - Q2 < 0   (names below numbers)              stratified sign-flip, one-sided
  K2  Q1 - Q0 < 0   (proxy summary below no feedback)  stratified sign-flip, one-sided
Secondary (outside the family): K1 and K2 over pairs with neither final collapsed.
Descriptive: Q2 - Q0; collapsed finals, gated iterations and gate fallbacks per arm; each collapse's draw record.

    .venv/bin/python eval/followup/replication2_report.py --inputs eval/matrix/replication2_*.jsonl \
        > eval/matrix/replication2.md
"""
import argparse, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT.parent))
from report import parse_run_cond  # noqa: E402
from replication_report import TARGETS, ALPHA, stat, flip_p, boot, fmt, holm  # noqa: E402

REPS, SEEDS = 20, 20
PAIRS = [("K1", "Q3", "Q2", "names minus numbers"), ("K2", "Q1", "Q0", "proxy summary minus no feedback")]
TEXT, BARE = ("Q1", "Q3"), ("Q0", "Q2")


def load(paths):
    v, errors = defaultdict(dict), {}  # (target, arm, rep) -> seed -> (value, error); first error text
    for src in paths:
        for line in Path(src).read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line); pr = parse_run_cond(r["condition"])
            if pr and pr[2] == "final":
                v[(r["target"], pr[0], pr[1])][r["seed"]] = (0.0 if "error" in r else r["auc_branch_reach"], "error" in r)
                if "error" in r: errors.setdefault((r["target"], pr[0], pr[1]), r["error"][:160])
    return v, errors


def final(v, t, arm, k):
    """(mean with errors at 0, collapsed) or None when the final is not fully measured."""
    d = v.get((t, arm, k))
    if not d or len(d) != SEEDS: return None
    return st.mean(x for x, _ in d.values()), any(e for _, e in d.values())


def diffs(v, x, y, survivors):
    out = {}
    for t in TARGETS:
        out[t] = []
        for k in range(1, REPS + 1):
            a, b = final(v, t, x, k), final(v, t, y, k)
            if a is None or b is None or (survivors and (a[1] or b[1])): continue
            out[t].append(a[0] - b[0])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", nargs="+", required=True); a = ap.parse_args()
    v, errors = load(a.inputs)
    missing = [(t, arm, k) for t in TARGETS for arm in TEXT + BARE for k in range(1, REPS + 1) if final(v, t, arm, k) is None]
    print("# Second pre-registered study: results\n")
    if missing:
        print(f"incomplete data: {len(missing)} finals not fully measured, e.g. {missing[:3]}; not tested"); return
    coll = {(t, arm): sum(final(v, t, arm, k)[1] for k in range(1, REPS + 1)) for t in TARGETS for arm in TEXT + BARE}
    print("Unit: replicate pair on a shared draft; a collapsed final scores 0. Statistic: mean over parson, tomlc99, "
          "cjson of the per-target mean paired difference, coverage points; stratified sign flips, 100000 flips, seed 0. "
          "Per-target cells: mean (up/down/zero).\n")
    print("## Confirmatory family (Holm, alpha 0.05)\n")
    print("| hypothesis | contrast | pairs | estimate [95% CI] | " + " | ".join(TARGETS) + " | p | Holm p | decision |\n|---|---|---|---|" + "---|" * len(TARGETS) + "---|---|---|")
    rows = [(h, label, d, flip_p(d, "less")) for h, x, y, label in PAIRS for d in [diffs(v, x, y, survivors=False)]]
    for (h, label, d, p), q in zip(rows, holm([r[3] for r in rows])):
        lo, hi = boot(d)
        print(f"| {h} | {label} | {sum(map(len, d.values()))} | {stat(d):+.2f} [{lo:+.2f}, {hi:+.2f}] | {fmt(d)} | "
              f"{p:.4f} | {q:.4f} | {'supported' if q < ALPHA else 'not supported'} |")
    print("\n## Secondary: pairs with neither final collapsed (outside the family)\n")
    print("| contrast | pairs | estimate [95% CI] | " + " | ".join(TARGETS) + " | one-sided p |\n|---|---|---|" + "---|" * len(TARGETS) + "---|")
    for h, x, y, label in PAIRS:
        d = diffs(v, x, y, survivors=True)
        if not all(d.values()): print(f"| {label} | {sum(map(len, d.values()))} | a target has no pair | | | | |"); continue
        lo, hi = boot(d)
        print(f"| {label} | {sum(map(len, d.values()))} | {stat(d):+.2f} [{lo:+.2f}, {hi:+.2f}] | {fmt(d)} | {flip_p(d, 'less'):.4f} |")
    print("\n## Descriptive\n")
    d = diffs(v, "Q2", "Q0", survivors=False); lo, hi = boot(d)
    print(f"- numbers minus no feedback, all pairs: {stat(d):+.2f} [{lo:+.2f}, {hi:+.2f}]; {fmt(d)}")
    print("- collapsed finals: " + "; ".join(f"{arm} " + ", ".join(f"{t} {coll[(t, arm)]}" for t in TARGETS) for arm in BARE + TEXT))
    for arm in BARE + TEXT:
        g = fb = 0
        for t in TARGETS:
            for k in range(1, REPS + 1):
                rd = ROOT.parents[1] / "runs" / t / f"{arm}-rep{k}"
                g += sum(bool(json.loads(f.read_text()).get("gated")) for f in rd.glob("iter-*/stats.json"))
                fb += "discarded, back to iter" in ((rd / "evolution.md").read_text(errors="replace") if (rd / "evolution.md").exists() else "")
        print(f"- {arm}: {g} gated iterations, {fb} runs with a gate fallback")
    # pairs whose shared iteration-1 draft was rejected at build or gated (identical in all four arms;
    # read from the Q0 run): DEVIATIONS_replication2.md, 4
    bad = {t: sum(any(l.startswith("- iter 1: build rejected") or "iter 1: gated" in l for l in
                      (ROOT.parents[1] / "runs" / t / f"Q0-rep{k}" / "evolution.md").read_text(errors="replace").splitlines())
                  for k in range(1, REPS + 1)) for t in TARGETS}
    print("- pairs whose shared first draft failed at iteration 1: " + ", ".join(f"{t} {bad[t]}" for t in TARGETS))
    for t in TARGETS:
        for arm in BARE + TEXT:
            for k in range(1, REPS + 1):
                if final(v, t, arm, k)[1]:
                    print(f"- collapse {t} {arm}-rep{k}: {errors.get((t, arm, k), '')}")


if __name__ == "__main__":
    main()
