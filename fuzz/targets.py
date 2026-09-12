"""targets.py — the registry of fuzz targets (multi-target support).

One entry per target library. All paths are relative to the repo root. This is
the single source of truth for the Python side (agent.py, the evals, the matrix
runner); harness/build.sh carries the matching bash table because it must run
without Python.

Adding a target = vendoring its pinned source + a harness under
targets/<name>/harness.c + adaptation notes + one entry here (+ build.sh).

Binary naming rule (shared with build.sh): the default-mode binary is
`build/<binary>`; any other mode is `build/<binary>_<mode>`. So json-parser's
control build is `build/harness_control` and parson's is
`build/harness_parson_control`.
"""
from __future__ import annotations

TARGETS: dict[str, dict] = {
    # T1 — the original/default target. Every path here is exactly what the
    # single-target code used, so the default behaviour is unchanged.
    "json-parser": {
        "format": "JSON",
        "src": "vendor/json-parser/json.c",
        "inc": "vendor/json-parser",
        "harness": "harness/harness.c",
        "grammar": "grammar/JSON.g4",
        "notes": "grammar/adaptation-notes.md",
        "binary": "harness",
        "modes": ("default", "control", "hunt", "unmask"),
        "pinned": "8ac4477",
    },
    # T2 — same grammar, different parser: a within-format comparison.
    "parson": {
        "format": "JSON",
        "src": "vendor/parson/parson.c",
        "inc": "vendor/parson",
        "harness": "targets/parson/harness.c",
        "grammar": "grammar/JSON.g4",
        "notes": "targets/parson/adaptation-notes.md",
        "binary": "harness_parson",
        "modes": ("default", "control", "roundtrip"),
        "pinned": "1.5.3 @ ba29f4e",
    },
}


def binary_name(target: str, mode: str = "default") -> str:
    """Build-output basename for (target, mode), per the shared naming rule."""
    base = TARGETS[target]["binary"]
    return base if mode == "default" else f"{base}_{mode}"
