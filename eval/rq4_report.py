"""rq4_report.py — RQ4: ground-truth bug campaigns (exploratory; registered expectations in prereg section 9).

Reads eval/campaigns/rq4.jsonl (one row per (target, bug, generator, seed)).
Per target and bug: per arm, replicates that triggered within the budget,
median inputs- and seconds-to-trigger among those that did, censoring count;
fixed reference rows (random, Grammarinator); positive-control status;
every other crash signature seen (candidate new findings), deduplicated.
Between arms: Fisher exact on triggered counts for H1/H2 pairs (descriptive).

    python rq4_report.py --in eval/campaigns/rq4.jsonl --out eval/matrix/rq4_report.md
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from mechanism import fisher_exact  # noqa: E402

ARMS = ("C2", "A5", "C3s", "C3n")
_ARM = re.compile(r"/(C2|A5|C3s|C3n|C2R)-rep(\d+)/")


def arm_of(row):
    m = _ARM.search(row["ref"])
    if m:
        return m.group(1)
    return row.get("name") or row["ref"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="eval/campaigns/rq4.jsonl")
    ap.add_argument("--out", default="eval/matrix/rq4_report.md")
    a = ap.parse_args()
    rows = [json.loads(l) for l in (ROOT / a.inp).read_text().splitlines() if l.strip()]
    L = ["# RQ4: ground-truth bug campaigns (exploratory)", "",
         f"{len(rows)} campaigns; budget {sorted({r.get('budget_minutes') for r in rows})} minutes each; a campaign "
         "counts as triggered when an input's normalised crash signature matches the bug's proof of concept "
         "(Magma-style). Generators: each registered arm's final per replicate (seed = 1000 x replicate), plus "
         "fixed references at seed 0. A final that cannot draw is censored at zero inputs.", ""]
    by = defaultdict(list)
    for r in rows:
        by[(r["target"], r["bug"])].append(r)
    others = Counter()
    for (t, b), rs in sorted(by.items()):
        pc = {r.get("positive_control") for r in rs}
        L += [f"## {t} / {b}", "", f"positive control: {pc}", "",
              "| generator | campaigns | triggered | median inputs to trigger | median seconds | inputs run (median) |",
              "|---|---|---|---|---|---|"]
        groups = defaultdict(list)
        for r in rs:
            groups[arm_of(r)].append(r)
            for sig, n in (r.get("other_signatures") or {}).items():
                others[(t, sig)] += n
        for g in [*ARMS, *sorted(k for k in groups if k not in ARMS)]:
            if g not in groups:
                continue
            gr = groups[g]
            trig = [r for r in gr if r.get("triggered")]
            mi = st.median(r["trigger"]["inputs"] for r in trig) if trig else "-"
            ms = st.median(r["trigger"]["seconds"] for r in trig) if trig and "seconds" in trig[0]["trigger"] else "-"
            L.append(f"| {g} | {len(gr)} | {len(trig)} | {mi} | {ms} | {st.median(r.get('inputs_total', 0) for r in gr):.0f} |")
        L.append("")
        tc = {g: (sum(1 for r in groups[g] if r.get("triggered")), len(groups[g])) for g in ARMS if g in groups}
        for x, y in (("C2", "A5"), ("C3s", "C2"), ("C3n", "C2")):
            if x in tc and y in tc:
                a1, n1 = tc[x]; a2, n2 = tc[y]
                L.append(f"- {x} {a1}/{n1} vs {y} {a2}/{n2} triggered: Fisher exact p = {fisher_exact(a1, n1 - a1, a2, n2 - a2):.3f}")
        L.append("")
    L += ["## Other crash signatures seen during campaigns (candidate findings, by target)", ""]
    for (t, sig), n in others.most_common():
        L.append(f"- {t}: `{sig}` x{n}")
    (ROOT / a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
