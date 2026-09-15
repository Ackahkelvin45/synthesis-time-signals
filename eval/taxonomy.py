"""taxonomy.py — RQ5 author-failure taxonomy, log-only (no runs, no API).

For every replicate of every arm on every target, every guard event is coded
by cause from the recorded artefacts: build rejections (evolution.md line +
the next prompt's REJECTED text), gate failures (iter-N/stats.json:
generator_error or validate_acceptance), mid-run errors. Cause classes are
matched on the recorded exception/rejection text with ordered regexes; the
first match wins; unmatched text is listed verbatim so the coding is
auditable.

    python taxonomy.py --out eval/matrix/taxonomy.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT / "fuzz")]
from cell import runs_dir  # noqa: E402

TARGETS = ("json-parser", "parson", "tomlc99", "cjson")
ARMS = ("C2", "A5", "C3s", "C3n", "C2R", "M2C2", "M2A5", "M2C3s")

# (class, regex) in priority order. Classes follow the take-home's Appendix C
# where they existed; new ones were added when the text matched nothing.
CLASSES = [
    ("hallucinated Hypothesis API", r"has no attribute '(st\.)?[a-z_]+'|module 'hypothesis.*has no attribute|cannot import name|AttributeError: module"),
    ("strategy/value confusion (two-level semantics)", r"OneOfStrategy|LazyStrategy|SearchStrategy|can only concatenate str \(not \"[A-Za-z]*Strategy\"|'function' object has no attribute|object has no attribute 'validate|unsupported operand.*Strategy|Strategy' object is not"),
    ("disallowed import or name (screen)", r"disallowed (import|name|attribute|submodule|imported)|dunder attribute"),
    ("syntax / unparseable response", r"does not parse|SyntaxError|no python code block|no ```python|invalid syntax"),
    ("wrong alphabet / characters argument", r"alphabet|characters\(|InvalidArgument.*(categories|whitelist|blacklist|codec|min_codepoint)"),
    ("invalid strategy arguments", r"InvalidArgument|min_size|max_size|max_leaves|must be|out of range"),
    ("recursion / Hypothesis health check", r"RecursionError|HealthCheck|FailedHealthCheck|too_slow|data_too_large|Unsatisfiable"),
    ("ExceptionGroup wrapper (sub-exceptions hidden)", r"ExceptionGroup|distinct failures"),
    ("generic Python error (TypeError/ValueError/KeyError/NameError)", r"TypeError|ValueError|KeyError|NameError|IndexError|ZeroDivision"),
    ("low acceptance (valid code, invalid outputs)", r"acceptance|accepted"),
]


def classify(text: str) -> str:
    for name, rx in CLASSES:
        if re.search(rx, text):
            return name
    return "unclassified"


def events(rd: Path) -> list[dict]:
    ev = (rd / "evolution.md").read_text() if (rd / "evolution.md").exists() else ""
    out = []
    for line in ev.splitlines():
        m = re.match(r"- iter (\d+): (.*)", line)
        if not m:
            continue
        it, rest = int(m.group(1)), m.group(2)
        idir = rd / f"iter-{it}"
        if "build rejected" in rest:
            out.append({"iter": it, "kind": "build rejection", "text": rest})
        elif "mid-run error" in rest:
            out.append({"iter": it, "kind": "mid-run error", "text": rest})
        elif "gated at" in rest:
            s = idir / "stats.json"
            d = json.loads(s.read_text()) if s.exists() else {}
            txt = d.get("generator_error") or f"acceptance {d.get('validate_acceptance')}"
            out.append({"iter": it, "kind": "gate failure", "text": str(txt)})
    return out


def main() -> int:
    global ARMS
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(ARMS), help="arms to include (default: all known)")
    ap.add_argument("--out", default="eval/matrix/taxonomy.md")
    args = ap.parse_args()
    ARMS = tuple(c for c in args.arms.split(',') if c)
    rows = []
    for t in TARGETS:
        for c in ARMS:
            for k in range(1, 11):
                rd = runs_dir(t) / f"{c}-rep{k}"
                if not (rd / "final.json").exists():
                    continue
                for e in events(rd):
                    rows.append({"target": t, "arm": c, "rep": k, **e, "class": classify(e["text"])})
    n_runs = sum(1 for t in TARGETS for c in ARMS for k in range(1, 11)
                 if (runs_dir(t) / f"{c}-rep{k}" / "final.json").exists())
    L = ["# RQ5: author-failure taxonomy (log-only, exploratory)", "",
         f"Guard events over {n_runs} completed replicates (arms {', '.join(ARMS)}; targets {', '.join(TARGETS)}), "
         f"coded from recorded exception and rejection text by ordered regexes (first match wins). "
         f"{len(rows)} events. Iterations with no event are not listed.", ""]
    # class x arm
    arms_present = [c for c in ARMS if any(r["arm"] == c for r in rows)]
    L += ["## Cause class by arm (events)", "", "| cause | " + " | ".join(arms_present) + " | total |",
          "|---|" + "---|" * (len(arms_present) + 1)]
    cls_tot = Counter(r["class"] for r in rows)
    for cls, _ in sorted(cls_tot.items(), key=lambda x: -x[1]):
        L.append(f"| {cls} | " + " | ".join(str(sum(1 for r in rows if r['class'] == cls and r['arm'] == a)) for a in arms_present) + f" | {cls_tot[cls]} |")
    L.append("")
    # kind x target
    L += ["## Event kind by target", "", "| kind | " + " | ".join(TARGETS) + " |", "|---|---|---|---|"]
    for kind in ("build rejection", "gate failure", "mid-run error"):
        L.append(f"| {kind} | " + " | ".join(str(sum(1 for r in rows if r['kind'] == kind and r['target'] == t)) for t in TARGETS) + " |")
    L.append("")
    # per-arm rates
    L += ["## Replicates with at least one event, by arm and target", "",
          "| arm | " + " | ".join(TARGETS) + " |", "|---|---|---|---|"]
    for c in arms_present:
        cells = []
        for t in TARGETS:
            n = sum(1 for k in range(1, 11) if (runs_dir(t) / f"{c}-rep{k}" / "final.json").exists())
            with_ev = len({r["rep"] for r in rows if r["arm"] == c and r["target"] == t})
            cells.append(f"{with_ev}/{n}" if n else "-")
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    L.append("")
    # iteration-1 seeds
    it1 = [r for r in rows if r["iter"] == 1]
    L += [f"Iteration-1 (seed) failures: {len(it1)} events in {len({(r['target'], r['arm'], r['rep']) for r in it1})} replicates; "
          "by class: " + ", ".join(f"{k} {v}" for k, v in Counter(r['class'] for r in it1).most_common()), ""]
    # unclassified, verbatim
    unc = [r for r in rows if r["class"] == "unclassified"]
    L += [f"## Unclassified ({len(unc)}), verbatim for audit", ""]
    for r in unc[:40]:
        L.append(f"- {r['target']} {r['arm']}-rep{r['rep']} iter {r['iter']} ({r['kind']}): {r['text'][:160]}")
    L.append("")
    # examples per class
    L += ["## One example per class", ""]
    seen = set()
    for r in rows:
        if r["class"] in seen or r["class"] == "unclassified":
            continue
        seen.add(r["class"])
        L.append(f"- **{r['class']}**: {r['target']} {r['arm']}-rep{r['rep']} iter {r['iter']}: `{r['text'][:140]}`")
    (ROOT / args.out).write_text("\n".join(L) + "\n")
    (ROOT / args.out).with_suffix(".jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
