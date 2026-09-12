#!/usr/bin/env bash
# Compile the JVM feature server (harness/FeatureServer.java) and the Java twins
# of the grammars (grammar/gen/<fmt>-java/) into build/antlr-java/. Needs a JDK
# (javac); the ANTLR 4.13.2 complete jar is what antlr4-tools downloads
# (~/.m2/repository/org/antlr/antlr4/4.13.2/) and is copied next to the classes.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="$ROOT/build/antlr-java"
JAR="$OUT/antlr4-4.13.2-complete.jar"
mkdir -p "$OUT"
if [ ! -f "$JAR" ]; then
  SRC_JAR="$(find "$HOME/.m2" -name 'antlr4-4.13.2-complete.jar' 2>/dev/null | head -1 || true)"
  if [ -z "$SRC_JAR" ]; then
    # antlr4-tools fetches the jar on first use
    "$ROOT/.venv/bin/antlr4" -v 4.13.2 >/dev/null 2>&1 || true
    SRC_JAR="$(find "$HOME/.m2" -name 'antlr4-4.13.2-complete.jar' 2>/dev/null | head -1 || true)"
  fi
  [ -n "$SRC_JAR" ] || { echo "antlr4-4.13.2-complete.jar not found" >&2; exit 1; }
  cp "$SRC_JAR" "$JAR"
fi
for d in "$ROOT"/grammar/gen/*-java; do
  fmt="$(basename "$d" -java)"
  mkdir -p "$OUT/$fmt"
  javac -nowarn -cp "$JAR" -d "$OUT/$fmt" "$d"/*.java "$HERE/FeatureServer.java"
  echo "[build_java.sh] ok: $OUT/$fmt"
done
