#!/bin/bash
# Runs the pre-registered replication end to end (eval/followup/PLAN_replication.md).
# STATUS line: eval/followup/replication.STATUS. Rows: eval/matrix/replication_*.jsonl.
cd "$(dirname "$0")/../.."
ST=eval/followup/replication.STATUS; PY=.venv/bin/python; M=eval/matrix
say() { echo "$* $(date -u +%FT%TZ)" > $ST; }
dns() { until python3 -c "import socket;socket.gethostbyname('api.deepseek.com')" 2>/dev/null; do say "waiting for DNS"; sleep 60; done; }
missing() { local n=0 t c k; for t in parson tomlc99 cjson; do for c in $2; do for k in $(seq $3 $4); do [ -f runs/$t/$c-rep$k/final.json ] || n=$((n+1)); done; done; done; echo $n; }
# run a batch until every run has a final (infrastructure failures are rerun from the start), up to 8 passes
batch() { local name=$1 conds=$2 from=$3 to=$4 targets=${5:-parson,tomlc99,cjson} p
  for p in 1 2 3 4 5 6 7 8; do
    [ "$(missing x "${conds//,/ }" $from $to)" -eq 0 ] && return 0
    dns; say "$name pass $p: $(missing x "${conds//,/ }" $from $to) runs missing"
    $PY eval/replicates.py --batch $name --targets $targets --conditions $conds --start-rep $from --reps $((to-from+1)) --retries 2 >/dev/null 2>&1
    [ "$(missing x "${conds//,/ }" $from $to)" -eq 0 ] && return 0; sleep 600
  done; say "$name: runs still missing after 8 passes, stopped"; exit 1; }
# wait for at least $1 USD of DeepSeek balance before a batch (a 402 mid-batch is an infrastructure failure, rerun)
bal() { set -a; . ./.env; set +a; curl -s https://api.deepseek.com/user/balance -H "Authorization: Bearer $DEEPSEEK_API_KEY" | python3 -c "import sys,json;print(sum(float(b['total_balance']) for b in json.load(sys.stdin)['balance_infos']))" 2>/dev/null || echo 0; }
fund() { until python3 -c "import sys;sys.exit(float('$(bal)')<$1)"; do say "waiting for DeepSeek top-up to $1 USD (now $(bal))"; sleep 600; done; }
conds() { local c="" a k; for k in $(seq $3 $4); do for a in $2; do c="$c,run:$a-rep$k:$1"; done; done; echo "${c#,}"; }
# measure in up to three parallel processes on disjoint conditions; then re-measure error cells once, alone
measure() { local tag=$1 what=$2 arms=$3 from=$4 to=$5 t
  say "measuring $tag"
  for t in parson cjson; do $PY eval/matrix.py --targets $t --conditions "$(conds $what "$arms" $from $to)" --k 20 --n 10000 --out $M/replication_${tag}_$t.jsonl >> $M/replication.log 2>&1 & done
  $PY eval/matrix.py --targets tomlc99 --conditions "$(conds $what "$arms" $from $to)" --k 20 --n 10000 --out $M/replication_${tag}_tomlc99.jsonl >> $M/replication.log 2>&1 &
  wait
  for f in $M/replication_${tag}_*.jsonl; do
    grep -q '"error"' $f || continue
    grep '"error"' $f >> $M/replication_first_errors.jsonl; grep -v '"error"' $f > $f.tmp; mv $f.tmp $f
    t=$(basename $f .jsonl); t=${t##*_}
    $PY eval/matrix.py --targets $t --conditions "$(conds $what "$arms" $from $to)" --k 20 --n 10000 --out $f >> $M/replication.log 2>&1
  done; }
# phase 1: bridge
fund 1.5; batch replication_b5 B5 1 12
measure b5seed seed B5 1 12; measure b5final final B5 1 12
for extra in 13 14 15; do
  $PY eval/followup/replication_seeds.py --inputs $M/replication_b5seed_*.jsonl > /dev/null 2>&1 && break
  short=$($PY eval/followup/replication_seeds.py --inputs $M/replication_b5seed_*.jsonl 2>&1 | grep -o "[a-z0-9]*: [0-9]* drawing" | cut -d: -f1 | paste -sd, -)
  batch replication_b5_extra B5 $extra $extra $short
  measure b5seed_x$extra seed B5 $extra $extra; measure b5final_x$extra final B5 $extra $extra
done
$PY eval/followup/replication_seeds.py --inputs $M/replication_b5seed_*.jsonl > /dev/null 2>&1 || { say "draft rule: fewer than 10 drawing drafts after 15 bridge replicates, stopped for a decision"; exit 1; }
# phase 2: replication arms
fund 4.5; batch replication_arms R0,R1,R2,R3,R4,E0,E1 1 10
measure arms final "R0 R1 R2 R3 R4 E0 E1" 1 10
say "measured; running the analysis once"
$PY eval/followup/replication_report.py --inputs $M/stage1.jsonl $M/day1.jsonl $M/day2.jsonl $M/replication_*.jsonl > $M/replication.md 2>> $M/replication.log
say "finished; report eval/matrix/replication.md"
