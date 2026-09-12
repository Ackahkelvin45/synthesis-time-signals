"""_draw.py — isolated, history-fixed input drawer (used by eval/cell.py).

    python _draw.py <ref> <n> <seed>      -> JSON list of strings on stdout

`ref` is 'builtin:text' (Hypothesis st.text(), the naive baseline) or the path
to a strategy module defining a top-level `strategy`.

WHY THIS EXISTS. A seeded Hypothesis draw is deterministic only for an
identical PROCESS HISTORY: which @given-decorated functions were created or run
before, import order, even how the interpreter was launched all change the
sequence that @seed(n) produces. Two eval scripts drawing "the same" seeded
examples therefore got different input sets — and different coverage — on the
same binary. Running every draw here, in a fresh interpreter whose only prior
Hypothesis activity is this file, fixes the history, so the input set becomes a
pure function of (strategy source, n, seed). Keep this file minimal and never
add Hypothesis work before the draw.
"""
import importlib.util
import json
import sys

from hypothesis import HealthCheck, given, seed as hyp_seed, settings, strategies as st


def main() -> int:
    ref, n, sd = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    if ref == "builtin:text":
        strat = st.text()
    else:
        spec = importlib.util.spec_from_file_location("target_strategy", ref)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        strat = mod.strategy
    out: list[str] = []

    @settings(max_examples=n, database=None, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(s=strat)
    def draw(s) -> None:
        out.append(s if isinstance(s, str) else str(s))

    hyp_seed(sd)(draw)()
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
