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
        "modes": ("default", "control", "hunt", "unmask", "o2"),
        # deep-nesting steer band (json-parser has no cap; 2048 is a target)
        "cap_band": (1500, 2048),
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
        "modes": ("default", "control", "roundtrip", "o2"),
        "cap_band": (1500, 2048),   # parson rejects deeper than ~2048
        "pinned": "1.5.3 @ ba29f4e",
    },
    # T4 — TOML: the first non-JSON format. Grammar = two files (lexer +
    # parser); the seed prompt concatenates every file in `grammars`.
    "tomlc99": {
        "format": "TOML",
        "src": "vendor/tomlc99/toml.c",
        "inc": "vendor/tomlc99",
        "harness": "targets/tomlc99/harness.c",
        "grammar": "grammar/TomlParser.g4",
        "grammars": ("grammar/TomlLexer.g4", "grammar/TomlParser.g4"),
        "notes": "targets/tomlc99/adaptation-notes.md",
        "binary": "harness_tomlc99",
        "modes": ("default", "control", "o2", "bug-issue50"),
        "pinned": "29076df",
        # depth steer band: tomlc99 recurses per nesting level (arrays / inline
        # tables); the band stays well below its stack-overflow depth
        "cap_band": (1500, 2048),
        # Ground-truth bugs (paper RQ4). `mode` names the build; `poc` is the
        # hand-written positive control that MUST trigger through the harness.
        "bugs": {
            "issue50": {"mode": "bug-issue50", "class": "null-deref",
                        "fix": "fd82018", "poc": "[0]\n0.0=[]\n+.\n"},
            "recursion": {"mode": "default", "class": "stack-overflow",
                          "fix": None, "poc": "a = " + "[" * 100000 + "1" + "]" * 100000},
        },
    },
}


def binary_name(target: str, mode: str = "default") -> str:
    """Build-output basename for (target, mode), per the shared naming rule."""
    base = TARGETS[target]["binary"]
    return base if mode == "default" else f"{base}_{mode}"
