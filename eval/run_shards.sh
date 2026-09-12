#!/usr/bin/env bash
# Supervised, resumable matrix shards for one batch. Each shard is restarted
# until its matrix run exits 0 with every cell present (the matrix skips cells
# already in its JSONL), so an external kill costs at most one cell.
#   bash eval/run_shards.sh <batch-name> <target> <k> <n> <conds-shard1> <conds-shard2> ...
set -u
BATCH="$1"; TARGET="$2"; K="$3"; N="$4"; shift 4
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/eval/matrix"; mkdir -p "$OUT"
STATUS="$OUT/$BATCH.STATUS"
i=0; pids=()
for CONDS in "$@"; do
  i=$((i+1))
  (
    n=0
    until "$ROOT/.venv/bin/python" "$ROOT/eval/matrix.py" --targets "$TARGET" --conditions "$CONDS" \
          --k "$K" --n "$N" --out "$OUT/${BATCH}_shard$i.jsonl" >> "$OUT/${BATCH}_shard$i.log" 2>&1; do
      n=$((n+1)); echo "[supervisor] shard $i exited non-zero; restart $n" >> "$OUT/${BATCH}_shard$i.log"; sleep 5
    done
    echo "[supervisor] shard $i complete" >> "$OUT/${BATCH}_shard$i.log"
  ) &
  pids+=($!)
done
while true; do
  done_cells=$(cat "$OUT/${BATCH}"_shard*.jsonl 2>/dev/null | wc -l | tr -d ' ')
  alive=0; for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
  echo "cells $done_cells, shards alive $alive, updated $(date -u +%H:%M:%SZ)" > "$STATUS.tmp"; mv "$STATUS.tmp" "$STATUS"
  [ "$alive" -eq 0 ] && break
  sleep 20
done
echo "cells $done_cells, shards alive 0, finished $(date -u +%H:%M:%SZ)" > "$STATUS"
