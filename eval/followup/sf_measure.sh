#!/bin/bash
# Incremental measurement of the shared-seed finals (run:SF<a>-rep<k>:final, 20 draw seeds x 10^4 inputs)
# into eval/matrix/sf.jsonl while the batch runs; eval/matrix.py skips cells already present and runs that
# do not exist yet. Repeats every 10 minutes until all 2 320 cells are in. STATUS: eval/matrix/sf.STATUS.
cd "$(dirname "$0")/../.."
OUT=eval/matrix/sf.jsonl; ST=eval/matrix/sf.STATUS; LOG=eval/matrix/sf.log
conds() { local maxk=$1; local c=""; for k in $(seq 1 $maxk); do for a in SF0 SF1 SF2 SF3; do c="$c,run:$a-rep$k:final"; done; done; echo "${c#,}"; }
TARGET_CELLS=2320
while true; do
  for t in parson cjson tomlc99; do
    mk=10; [ "$t" = tomlc99 ] && mk=9
    .venv/bin/python eval/matrix.py --targets $t --conditions "$(conds $mk)" --k 20 --n 10000 --out $OUT >> $LOG 2>&1
  done
  n=$(grep -c "" $OUT 2>/dev/null || echo 0)
  echo "cells $n/$TARGET_CELLS, updated $(date -u +%FT%TZ)" > $ST
  [ "$n" -ge "$TARGET_CELLS" ] && { echo "cells $n/$TARGET_CELLS, finished $(date -u +%FT%TZ)" > $ST; break; }
  sleep 600
done
