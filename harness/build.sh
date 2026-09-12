#!/usr/bin/env bash
#
# build.sh — compile a target library + its harness with AddressSanitizer + UBSan.
#
# Design notes (why these exact flags):
#   -fsanitize=address,undefined  ASan catches memory-safety bugs (overflow,
#                                 use-after-free); UBSan catches undefined
#                                 behavior (signed overflow, bad shifts, ...).
#   -fno-sanitize-recover=all     REQUIRED. Without it UBSan only prints
#                                 "runtime error:" and CONTINUES, so a real UB
#                                 input would exit 0 and be misread as a valid
#                                 parse. This makes the first error abort.
#   -fno-omit-frame-pointer -g    readable stack traces for crash dedup.
#   -O0                           no optimization, so the compiler can't fold
#                                 away the very UB we want to observe, and
#                                 stack frames aren't inlined together.
#
# Targets (set TARGET env var; default json-parser — its outputs are unchanged):
#   json-parser  vendor/json-parser + harness/harness.c        -> build/harness*
#   parson       vendor/parson      + targets/parson/harness.c -> build/harness_parson*
# The table below must match fuzz/targets.py (binary naming rule: default mode
# is build/<binary>, any other mode is build/<binary>_<mode>).
#
# Modes (set MODE env var); which are valid depends on the target:
#   default    parse -> free              (the faithful "parse entry point")
#   control    injects a synthetic crash  (positive control for the pipeline)
#   roundtrip  parse -> serialize -> free (parson only: it has a serializer,
#              where its historical overflow bugs lived)
#   hunt       (json-parser only) default minus -fno-sanitize=pointer-overflow,
#              suppressing ONLY json-parser's known first-pass NULL-offset idiom
#              (json.c:437/447, finding #1) so the loop can parse objects and
#              reach DEEPER bugs. Documented trade-off: hides any *other*
#              pointer-overflow, so real findings are re-confirmed on `default`.
#   unmask     (json-parser only) STRICTLY BETTER hunt: a line-precise,
#              value-preserving patch (harness/apply_unmask.py) rewrites ONLY
#              finding #1's two NULL+n sites to integer arithmetic, then compiles
#              with the FULL sanitizer set so pointer-overflow stays LIVE
#              everywhere else. Pinned vendor/ source is never touched (patched
#              copy lives in build/_patched/).
#
# macOS note: LeakSanitizer is NOT supported on macOS/arm64, so memory *leaks*
# are not detected on this platform. The assignment targets crashes/UB, not
# leaks, so this is documented rather than worked around. See README.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="$ROOT/build"
mkdir -p "$OUT"

TARGET="${TARGET:-json-parser}"
MODE="${MODE:-default}"
CC="${CC:-clang}"

# --- target table (keep in sync with fuzz/targets.py) -----------------------
case "$TARGET" in
  json-parser)
    SRC="$ROOT/vendor/json-parser/json.c"; INC="$ROOT/vendor/json-parser"
    HSRC="$HERE/harness.c";                BASE="harness"
    VALID_MODES="default control hunt unmask" ;;
  parson)
    SRC="$ROOT/vendor/parson/parson.c";    INC="$ROOT/vendor/parson"
    HSRC="$ROOT/targets/parson/harness.c"; BASE="harness_parson"
    VALID_MODES="default control roundtrip" ;;
  *) echo "unknown TARGET '$TARGET' (use: json-parser|parson)" >&2; exit 1 ;;
esac

case " $VALID_MODES " in
  *" $MODE "*) ;;
  *) echo "MODE '$MODE' is not valid for TARGET '$TARGET' (use: $VALID_MODES)" >&2; exit 1 ;;
esac

if [ "$MODE" = "default" ]; then BIN="$OUT/$BASE"; else BIN="$OUT/${BASE}_$MODE"; fi

# --- mode-specific flags -----------------------------------------------------
case "$MODE" in
  default)   EXTRA=(-DHARNESS_MODE='"default"') ;;
  control)   EXTRA=(-DPOSITIVE_CONTROL -DHARNESS_MODE='"control"') ;;
  roundtrip) EXTRA=(-DROUNDTRIP -DHARNESS_MODE='"roundtrip"') ;;
  hunt)      EXTRA=(-fno-sanitize=pointer-overflow -DHARNESS_MODE='"hunt"') ;;
  unmask)    "${PYTHON:-python3}" "$HERE/apply_unmask.py"
             EXTRA=(-DHARNESS_MODE='"unmask"')
             SRC="$OUT/_patched/json.c"; INC="$OUT/_patched" ;;
esac

COMMON_FLAGS=(
  -fsanitize=address,undefined
  -fno-sanitize-recover=all
  -fno-omit-frame-pointer
  -g -O0
  -I "$INC"
)

echo "[build.sh] TARGET=$TARGET MODE=$MODE  ->  $BIN"
# ${EXTRA[@]+...} guard: expands to nothing when EXTRA is empty, which is
# required under `set -u` on macOS's bash 3.2 (empty-array expansion errors).
"$CC" "${COMMON_FLAGS[@]}" ${EXTRA[@]+"${EXTRA[@]}"} \
  "$SRC" \
  "$HSRC" \
  -o "$BIN"
echo "[build.sh] ok: $BIN"
