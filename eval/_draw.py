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

from hypothesis import HealthCheck, Phase, given, seed as hyp_seed, settings, strategies as st

# Draw protocol v2 (paper): an LLM-authored generator may raise on a rare
# branch (a strategy object added to a str, an IndexError on an empty list).
# A fuzzing harness skips such an example and continues; Hypothesis instead
# aborts the whole draw. So the n examples are drawn in CHUNKS under derived
# seeds (seed*1000 + chunk_index); a chunk whose generator raises is dropped
# and the next derived seed is tried, up to MAX_ATTEMPTS chunks. The number of
# failed chunks is reported alongside the set ("draw_failures"): generator
# fragility becomes a measured quantity instead of a lost replicate. The set
# remains a pure function of (strategy source, n, seed). Shrinking is off:
# only the generate phase runs, so a failure costs one chunk, not a minimisation.
CHUNK = 100               # a raise costs 100 examples; tolerates ~1 failure in 300 examples
MAX_ATTEMPTS_FACTOR = 3   # give up after 3x the chunks needed (then the cell scores 0)


def _draw_grammarinator(ref: str, n: int, sd: int) -> list[str]:
    """Grammarinator baseline (C0b): NO Hypothesis involved. The generator class
    is driven directly (not GeneratorTool, which adds unseeded choices and
    mutators); Python's `random` is the only RNG, seeded here in a fresh
    process, so the draw is a pure function of (generator, params, seed)."""
    import json as _json
    import random
    from pathlib import Path
    _, fmt, variant = ref.split(":")
    root = Path(__file__).resolve().parent.parent
    pin = _json.loads((root / "eval" / "grammarinator.json").read_text())[fmt]
    gen = root / pin["generator"]
    sys.path.insert(0, str(gen.parent))
    import importlib
    from grammarinator.runtime import DefaultModel, WeightedModel, RuleSize
    mod = importlib.import_module(pin.get("module", gen.stem))
    cls = getattr(mod, pin.get("class", gen.stem))
    model = DefaultModel()
    if variant == "deep":
        w = float(pin["deep_weight"])
        model = WeightedModel(model, weights={tuple(k): w for k in pin["deep_alternatives"]})
    random.seed(sd)
    g = cls(model=model, limit=RuleSize(depth=400, tokens=float("inf")))
    start = getattr(g, pin["start_rule"])
    return [str(start()) for _ in range(n)]


def main() -> int:
    ref, n, sd = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    if ref.startswith("grammarinator:"):
        sys.stdout.write(json.dumps({"examples": _draw_grammarinator(ref, n, sd),
                                     "draw_failures": 0, "chunks": 1, "complete": True}))
        return 0
    if ref == "builtin:text":
        strat = st.text()
    else:
        spec = importlib.util.spec_from_file_location("target_strategy", ref)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        strat = mod.strategy
    out: list[str] = []
    failures = 0
    need_chunks = (n + CHUNK - 1) // CHUNK
    attempts = 0
    chunk_idx = 0
    while len(out) < n and attempts < need_chunks * MAX_ATTEMPTS_FACTOR:
        want = min(CHUNK, n - len(out))
        got: list[str] = []

        @settings(max_examples=want, database=None, deadline=None, phases=(Phase.generate,),
                  suppress_health_check=list(HealthCheck))
        @given(s=strat)
        def draw(s) -> None:
            got.append(s if isinstance(s, str) else str(s))

        exhausted = False
        try:
            hyp_seed(sd * 1000 + chunk_idx)(draw)()
            out.extend(got)
            # Hypothesis returns FEWER examples, without raising, when the
            # strategy's space is exhausted (e.g. st.just): that is a complete
            # draw of a small generator, not a failure.
            exhausted = len(got) < want
        except Exception:  # noqa: BLE001 - the generator raised on this chunk
            failures += 1
        attempts += 1
        chunk_idx += 1
        if exhausted:
            break
    sys.stdout.write(json.dumps({"examples": out[:n], "draw_failures": failures,
                                 "chunks": attempts, "complete": len(out) >= n or exhausted}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
