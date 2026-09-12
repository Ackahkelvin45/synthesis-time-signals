#!/usr/bin/env bash
# Regenerate the committed ANTLR Python3 parsers under grammar/gen/<fmt>/.
# Pinned to ANTLR 4.13.2 (matches antlr4-python3-runtime in requirements.txt).
# Needs Java (the antlr4-tools wrapper downloads the jar on first use).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-$HERE/../.venv/bin}"
gen() { # gen <fmt-dir> <grammar files...>
  local out="$HERE/gen/$1"; shift
  mkdir -p "$out"
  "$PY/antlr4" -v 4.13.2 -Dlanguage=Python3 -o "$out" -Xexact-output-dir "$@"
  rm -f "$out"/*.interp "$out"/*.tokens
}
gen json "$HERE/JSON.g4"
gen toml "$HERE/TomlLexer.g4" "$HERE/TomlParser.g4"

# Java twins of the same grammars for the feature server (harness/FeatureServer.java):
# the Python ANTLR runtime costs ~1.3 ms per nesting level on the TOML grammar,
# the JVM runtime is ~50x faster. Same ANTLR version => identical rule/token numbering.
genj() { # genj <fmt-dir> <grammar files...>
  local out="$HERE/gen/$1-java"; shift
  mkdir -p "$out"
  "$PY/antlr4" -v 4.13.2 -Dlanguage=Java -package gen -o "$out" -Xexact-output-dir "$@"
  rm -f "$out"/*.interp "$out"/*.tokens
}
genj json "$HERE/JSON.g4"
genj toml "$HERE/TomlLexer.g4" "$HERE/TomlParser.g4"
# gen xml  "$HERE/XMLLexer.g4"  "$HERE/XMLParser.g4"    # added with libexpat
echo "[gen.sh] ok"
