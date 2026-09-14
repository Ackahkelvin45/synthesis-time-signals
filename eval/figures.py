"""figures.py — paper figures from the matrix JSONL files (never hand-edited).

F1  coverage-vs-inputs curves per target: per arm the mean over replicates of
    the replicate-mean curve (draw seeds averaged first), band = min..max over
    replicates; fixed generators (seed mean, Grammarinator) as dashed lines.
F2  forest plot of A12 with bootstrap CI per target for every between-arm
    contrast run (H1, H2s, H2n, C2R vs C2), registered bands shaded.
F3  per-replicate delta (final minus seed) strip plot per target and arm.
F4  RQ1: seed generators vs Grammarinator per target (strip + Grammarinator band).

    python figures.py --stage1 eval/matrix/stage1.jsonl --extra eval/matrix/stage1c.jsonl ... --gram ... --outdir paper/figures
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from report import a12, bootstrap_a12, parse_run_cond  # noqa: E402

ARMS = ["C2", "A5", "C3s", "C3n", "C2R"]
COLOR = {"C2": "#2a78d6", "A5": "#eb6834", "C3s": "#1baf7a", "C3n": "#eda100", "C2R": "#e87ba4",
         "seed": "#555555", "grammarinator": "#111111", "grammarinator-deep": "#111111", "random": "#999999"}
LABEL = {"C2": "C2 proxy", "A5": "A5 no steering", "C3s": "C3s coverage", "C3n": "C3n coverage+names",
         "C2R": "C2' re-seed repair", "seed": "seed (mean)", "grammarinator": "Grammarinator",
         "grammarinator-deep": "Grammarinator depth-matched", "random": "random text"}
TARGETS = ["json-parser", "parson", "tomlc99", "cjson"]
CPS = [10, 30, 100, 150, 300, 1000, 3000, 10000]
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#888", "axes.linewidth": 0.6, "xtick.color": "#444",
                     "ytick.color": "#444", "grid.color": "#e5e5e5", "grid.linewidth": 0.5})


def load(paths):
    loop = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))  # t/arm/rep/what/seed -> row
    fixed = defaultdict(lambda: defaultdict(dict))  # t/cond/seed -> row
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            pr = parse_run_cond(r["condition"])
            if pr:
                loop[r["target"]][pr[0]][pr[1]][pr[2]][r["seed"]] = r
            elif r["condition"] in ("grammarinator", "grammarinator-deep", "random"):
                fixed[r["target"]][r["condition"]][r["seed"]] = r
    return loop, fixed


def auc(r):
    return 0.0 if "error" in r else r["auc_branch_reach"]


def curve(r):
    if "error" in r:
        return [0.0] * len(CPS)
    return [r["curve"][str(c)]["branch_reach"] for c in CPS]


def rep_mean_curve(rows):
    cs = [curve(r) for r in rows.values()]
    return [st.mean(x) for x in zip(*cs)]


def present(loop):
    return [t for t in TARGETS if loop.get(t)]


def f1(loop, fixed, outdir):
    ts = present(loop)
    fig, axes = plt.subplots(1, len(ts), figsize=(2.4 * len(ts), 2.4), sharey=False, squeeze=False)
    axes = axes[0]
    for ax, t in zip(axes, ts):
        for arm in ARMS:
            if arm not in loop[t]:
                continue
            curves = [rep_mean_curve(v["final"]) for v in loop[t][arm].values() if v.get("final")]
            if not curves:
                continue
            # median and interquartile band over replicates (collapsed replicates are
            # zeros; the mean curve would be dragged down by them and the min band to 0)
            med = [st.median(x) for x in zip(*curves)]
            qs = [st.quantiles(x, n=4) if len(x) >= 4 else (min(x), st.median(x), max(x)) for x in zip(*curves)]
            ax.fill_between(CPS, [q[0] for q in qs], [q[2] for q in qs], color=COLOR[arm], alpha=0.10, linewidth=0)
            ax.plot(CPS, med, color=COLOR[arm], linewidth=1.6, label=LABEL[arm])
        seeds = [rep_mean_curve(v["seed"]) for arm in ("C2", "A5") for v in loop[t][arm].values() if v.get("seed")]
        if seeds:
            ax.plot(CPS, [st.mean(x) for x in zip(*seeds)], color=COLOR["seed"], linewidth=1.2, linestyle="--", label=LABEL["seed"])
        gk = "grammarinator-deep" if "grammarinator-deep" in fixed[t] else "grammarinator"
        if gk in fixed[t]:
            ax.plot(CPS, rep_mean_curve(fixed[t][gk]), color=COLOR[gk], linewidth=1.2, linestyle=":", label=LABEL[gk])
        ax.set_xscale("log")
        ax.set_title(t, fontsize=9, loc="left")
        ax.set_xlabel("inputs (log)")
        ax.grid(True, axis="y")
    axes[0].set_ylabel("branch coverage of reachable region (%)\nmedian over replicates, IQR band")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(outdir / "f1_curves.pdf", bbox_inches="tight")
    fig.savefig(outdir / "f1_curves.png", dpi=200, bbox_inches="tight")


def contrasts(loop, t):
    out = []
    lv = lambda arm: [st.mean(auc(r) for r in v["final"].values()) for v in loop[t][arm].values() if v.get("final")]
    for a, b, name in (("C2", "A5", "H1: C2 vs A5"), ("C3s", "C2", "H2s: C3s vs C2"), ("C3n", "C2", "H2n: C3n vs C2"),
                       ("C2R", "C2", "C2' vs C2 (follow-up)")):
        if a in loop[t] and b in loop[t]:
            x, y = lv(a), lv(b)
            if len(x) >= 2 and len(y) >= 2:
                out.append((name, a12(x, y), *bootstrap_a12(x, y)))
    return out


def f2(loop, outdir):
    ts = present(loop)
    fig, axes = plt.subplots(1, len(ts), figsize=(2.4 * len(ts), 2.0), sharex=True, squeeze=False)
    axes = axes[0]
    for ax, t in zip(axes, ts):
        cs = contrasts(loop, t)
        ax.axvspan(0.36, 0.64, color="#f2f2f2", zorder=0)
        ax.axvspan(0.44, 0.56, color="#e6e6e6", zorder=0)
        ax.axvline(0.5, color="#888", linewidth=0.6)
        for i, (name, e, lo, hi) in enumerate(cs):
            ax.plot([lo, hi], [i, i], color="#333", linewidth=1.2)
            ax.plot([e], [i], marker="o", color="#333", markersize=4)
            ax.text(1.02, i, f"{e:.2f} [{lo:.2f}, {hi:.2f}]", va="center", fontsize=6.5, color="#333")
        ax.set_yticks(range(len(cs)))
        ax.set_yticklabels([c[0] for c in cs], fontsize=7)
        ax.set_ylim(-0.6, max(len(cs) - 0.4, 0.6))
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.set_title(t, fontsize=9, loc="left")
        ax.set_xlabel("A12 (bootstrap 95% CI)")
    fig.tight_layout()
    fig.savefig(outdir / "f2_forest.pdf", bbox_inches="tight")
    fig.savefig(outdir / "f2_forest.png", dpi=200, bbox_inches="tight")


def f3(loop, outdir):
    ts = present(loop)
    fig, axes = plt.subplots(1, len(ts), figsize=(2.4 * len(ts), 2.2), sharey=False, squeeze=False)
    axes = axes[0]
    for ax, t in zip(axes, ts):
        arms = [a for a in ARMS if a in loop[t]]
        for i, arm in enumerate(arms):
            ds = []
            for v in loop[t][arm].values():
                if v.get("final") and v.get("seed"):
                    ds.append(st.mean(auc(r) for r in v["final"].values()) - st.mean(auc(r) for r in v["seed"].values()))
            xs = [i + (j - len(ds) / 2) * 0.04 for j in range(len(ds))]
            YMAX = 8.0   # deltas inflated by a failed seed generator sit far above; mark them at the edge
            inl = [(x, d) for x, d in zip(xs, ds) if -8.0 <= d <= YMAX]
            out = [(x, d) for x, d in zip(xs, ds) if d > YMAX]
            ax.scatter([x for x, _ in inl], [d for _, d in inl], s=12, color=COLOR[arm], edgecolor="white", linewidth=0.5, zorder=3)
            YMIN = -8.0
            for x, d in out:
                ax.scatter([x], [YMAX], s=18, marker="^", color=COLOR[arm], edgecolor="white", linewidth=0.5, zorder=4)
                ax.text(x, YMAX - 0.55, f"+{d:.0f}", fontsize=5.5, ha="center", va="top", color="#333")
            below = [(x, d) for x, d in zip(xs, ds) if d < YMIN]   # collapsed finals: off the scale below
            for j, (x, d) in enumerate(below):
                ax.scatter([x], [YMIN], s=18, marker="v", color=COLOR[arm], edgecolor="white", linewidth=0.5, zorder=4)
                ax.text(i - 0.3, YMIN + 0.55 + 0.75 * j, f"{d:.0f}", fontsize=5.5, ha="left", va="bottom", color="#333")
            if ds:
                ax.plot([i - 0.25, i + 0.25], [st.mean(ds)] * 2, color=COLOR[arm], linewidth=1.5)
                if any(d > YMAX for d in ds):
                    ok = [d for d in ds if d <= YMAX]
                    ax.plot([i - 0.25, i + 0.25], [st.mean(ok)] * 2, color=COLOR[arm], linewidth=1.0, linestyle=":")
        ax.axhline(0, color="#888", linewidth=0.6)
        ax.set_ylim(YMIN - 0.5, YMAX + 0.5)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arms)
        ax.set_title(t, fontsize=9, loc="left")
        ax.grid(True, axis="y")
    axes[0].set_ylabel("final minus seed (AUC points)")
    fig.text(0.5, -0.04, "triangles: off-scale replicates (up: the seed generator failed, so the delta is the whole final level; "
             "down: the final generator collapsed). Bar = arm mean; dotted = mean without off-scale replicates.", ha="center", fontsize=6, color="#333")
    fig.tight_layout()
    fig.savefig(outdir / "f3_deltas.pdf", bbox_inches="tight")
    fig.savefig(outdir / "f3_deltas.png", dpi=200, bbox_inches="tight")


def f4(loop, fixed, outdir):
    ts = present(loop)
    fig, axes = plt.subplots(1, len(ts), figsize=(2.4 * len(ts), 2.2), squeeze=False)
    axes = axes[0]
    for ax, t in zip(axes, ts):
        seeds = [st.mean(auc(r) for r in v["seed"].values()) for arm in ("C2", "A5") for v in loop[t][arm].values() if v.get("seed")]
        xs = [0 + (j - len(seeds) / 2) * 0.03 for j in range(len(seeds))]
        ax.scatter(xs, seeds, s=12, color=COLOR["seed"], edgecolor="white", linewidth=0.5, zorder=3, label="LLM seed generators (20)")
        i = 1
        for gk in ("random", "grammarinator", "grammarinator-deep"):
            if gk in fixed[t]:
                vals = [auc(r) for r in fixed[t][gk].values()]
                ax.scatter([i + (j - len(vals) / 2) * 0.03 for j in range(len(vals))], vals, s=12, color=COLOR[gk],
                           marker="s", edgecolor="white", linewidth=0.5, zorder=3)
                i += 1
        labels = ["LLM\nseeds"] + [{"random": "random\ntext", "grammarinator": "Gram.\ndefault", "grammarinator-deep": "Gram.\ndeep"}[g] for g in ("random", "grammarinator", "grammarinator-deep") if g in fixed[t]]
        ax.set_xlim(-0.6, len(labels) - 0.4)
        ax.tick_params(axis="x", labelsize=6.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_title(t, fontsize=9, loc="left")
        ax.grid(True, axis="y")
    axes[0].set_ylabel("AUC branch coverage, reachable region")
    fig.tight_layout()
    fig.savefig(outdir / "f4_rq1.pdf", bbox_inches="tight")
    fig.savefig(outdir / "f4_rq1.png", dpi=200, bbox_inches="tight")


def f5(rq3_path, outdir):
    """RQ3: proxy score (recorded by the loop, recomputed from the summary when the crash
    branch dropped it) vs measured primary outcome of the same iteration's generator."""
    import re
    sys.path[:0] = [str(ROOT / "fuzz"), str(ROOT / "fuzz" / "loop")]
    from cell import runs_dir  # noqa: E402
    from agent import _score  # noqa: E402
    rx = re.compile(r"^run:([A-Za-z0-9]+)-rep(\d+):(\d+)$")
    meas = defaultdict(list)
    for line in Path(rq3_path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        m = rx.match(r["condition"])
        if m:
            meas[(r["target"], m.group(1), int(m.group(2)), int(m.group(3)))].append(0.0 if "error" in r else r["auc_branch_reach"])
    ts = [t for t in TARGETS if any(k[0] == t for k in meas)]
    fig, axes = plt.subplots(1, len(ts), figsize=(2.4 * len(ts), 2.3), squeeze=False)
    axes = axes[0]
    for ax, t in zip(axes, ts):
        for arm in ARMS:
            xs, ys = [], []
            for k in range(1, 11):
                for it in range(1, 6):
                    key = (t, arm, k, it)
                    if key not in meas:
                        continue
                    sp = runs_dir(t) / f"{arm}-rep{k}" / f"iter-{it}" / "stats.json"
                    if not sp.exists():
                        continue
                    d = json.loads(sp.read_text())
                    if d.get("gated"):
                        continue
                    ps = d.get("proxy_score")
                    if ps is None and d.get("summary"):
                        ps = _score(d["summary"])
                    if ps is None:
                        continue
                    xs.append(ps)
                    ys.append(st.mean(meas[key]))
            if xs:
                ax.scatter(xs, ys, s=9, color=COLOR[arm], edgecolor="white", linewidth=0.3, alpha=0.85, label=LABEL[arm], zorder=3)
        ax.set_title(t, fontsize=9, loc="left")
        ax.set_xlabel("proxy score (loop-internal)")
        ax.grid(True, axis="both")
    axes[0].set_ylabel("AUC branch coverage, reachable region\n(3 fresh draw seeds, 1 000 inputs)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout()
    fig.savefig(outdir / "f5_rq3.pdf", bbox_inches="tight")
    fig.savefig(outdir / "f5_rq3.png", dpi=200, bbox_inches="tight")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--rq3", default=None, help="eval/matrix/rq3.jsonl (adds F5)")
    a = ap.parse_args()
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    loop, fixed = load(a.inputs)
    f1(loop, fixed, outdir)
    f2(loop, outdir)
    f3(loop, outdir)
    f4(loop, fixed, outdir)
    if a.rq3:
        f5(a.rq3, outdir)
    print("wrote", sorted(p.name for p in outdir.iterdir()))


if __name__ == "__main__":
    main()
