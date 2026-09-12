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
        sys.stdout.write(json.dumps(_draw_grammarinator(ref, n, sd)))
        return 0
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
