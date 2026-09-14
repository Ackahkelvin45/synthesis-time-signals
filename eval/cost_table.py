"""cost_table.py — T6: synthesis cost per arm and target from every completed run's final.json.

    python cost_table.py --out eval/matrix/cost_table.md
"""
import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from cell import runs_dir  # noqa: E402

TARGETS = ("json-parser", "parson", "tomlc99", "cjson")
ARMS = ("C2", "A5", "C3s", "C3n", "C2R")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="eval/matrix/cost_table.md")
    a = ap.parse_args()
    L = ["# T6: synthesis cost per run (mean over replicates; every completed run)", "",
         "| target | arm | runs | LLM calls | tokens in | tokens out | USD | wall min | CPU s | served |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    grand = []
    for t in TARGETS:
        for c in ARMS:
            fs = [json.loads((runs_dir(t) / f"{c}-rep{k}" / "final.json").read_text())
                  for k in range(1, 11) if (runs_dir(t) / f"{c}-rep{k}" / "final.json").exists()]
            if not fs:
                continue
            grand += fs
            served = sorted({s for f in fs for s in f.get("served_models", [])})
            L.append(f"| {t} | {c} | {len(fs)} | {st.mean(f['llm_calls'] for f in fs):.1f} | "
                     f"{st.mean(f['tokens_in'] for f in fs):.0f} | {st.mean(f['tokens_out'] for f in fs):.0f} | "
                     f"{st.mean(f['est_usd'] for f in fs):.3f} | {st.mean(f['wall_s'] for f in fs) / 60:.1f} | "
                     f"{st.mean(f.get('cpu_s', 0) for f in fs):.0f} | {','.join(served)} |")
    L += ["", f"All runs: {len(grand)}; total {sum(f['est_usd'] for f in grand):.3f} USD; "
              f"mean {st.mean(f['est_usd'] for f in grand):.3f} USD, {st.mean(f['wall_s'] for f in grand) / 60:.1f} min per run; "
              f"backstop hits {sum(len(f.get('backstop_hits', [])) for f in grand)}; "
              f"served {sorted({s for f in grand for s in f.get('served_models', [])})}.",
          "Prices: .env estimates (0.27 USD/M input, 1.10 USD/M output); provider list prices for the served model bracket these (D26 addendum)."]
    (ROOT / a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
