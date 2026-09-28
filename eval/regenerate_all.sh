#!/usr/bin/env bash
# Regenerate every report, table and figure from the committed data. Idempotent.
#   bash eval/regenerate_all.sh
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python
M=eval/matrix
echo "[1/9] merge day-2 cells (cJSON, M2) with explicit failed rows for skipped seeds"
$PY eval/merge_fill.py --out $M/day2.jsonl "$M/day2_cjson_*_shard*.jsonl" "$M/m2_tomlc99_*_shard*.jsonl" "$M/m2_parson_*_shard*.jsonl"
if ls $M/rq3_cjson_shard*.jsonl >/dev/null 2>&1; then cat $M/rq3_*_shard*.jsonl > $M/rq3.jsonl; echo "    rq3 cells: $(wc -l < $M/rq3.jsonl)"; fi
INPUTS="$M/stage1.jsonl $M/stage1c.jsonl $M/day1.jsonl $M/day2.jsonl"
echo "[2/9] full report";        $PY eval/full_report.py --inputs $INPUTS --out $M/full_report.md > /dev/null
echo "[3/9] tables T1/T2";       $PY eval/tables.py --inputs $INPUTS --out $M/tables.md > /dev/null
echo "[4/9] RQ1";                cat $M/stage1.jsonl $M/day2.jsonl > $M/_rq1_seeds.jsonl; $PY eval/rq1_report.py --stage1 $M/_rq1_seeds.jsonl --gram $M/fixed.jsonl --out $M/rq1_report.md > /dev/null
echo "[5/9] taxonomy, cost, equal-time"
$PY eval/taxonomy.py --arms C2,A5,C3s,C3n,C2R --out $M/taxonomy.md > /dev/null
$PY eval/cost_table.py --out $M/cost_table.md > /dev/null
$PY eval/equal_time.py --inputs $INPUTS $M/fixed.jsonl --out $M/equal_time.md > /dev/null
echo "[6/9] RQ3";                [ -f $M/rq3.jsonl ] && $PY eval/rq3_report.py --cells $M/rq3.jsonl --out $M/rq3_report.md > /dev/null || true
echo "[7/9] RQ4";                $PY eval/rq4_report.py --in eval/campaigns/rq4.jsonl --out $M/rq4_report.md > /dev/null
echo "[8/9] AFL++ row";          [ -f $M/afl_ref.jsonl ] && $PY eval/afl_ref.py report --in $M/afl_ref.jsonl --out $M/afl_ref.md > /dev/null || echo "    (no afl_ref.jsonl yet)"
echo "[9/9] figures F1-F6";      $PY eval/figures.py --inputs $INPUTS $M/fixed.jsonl --rq3 $M/rq3.jsonl --rq4 eval/campaigns/rq4.jsonl --outdir paper/figures > /dev/null
echo "done: $(ls paper/figures | wc -l | tr -d ' ') figure files; reports in $M"
