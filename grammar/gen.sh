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
# gen toml "$HERE/TomlLexer.g4" "$HERE/TomlParser.g4"   # added with tomlc99 (plan step 11)
# gen xml  "$HERE/XMLLexer.g4"  "$HERE/XMLParser.g4"    # added with libexpat
echo "[gen.sh] ok"
