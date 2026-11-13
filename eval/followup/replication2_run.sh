#!/bin/bash
# Runs the second pre-registered study end to end (eval/followup/PLAN_replication2.md).
# STATUS line: eval/followup/replication2.STATUS. Rows: eval/matrix/replication2_*.jsonl.
cd "$(dirname "$0")/../.."
( caffeinate -i -m -s -w $$ & )   # no idle sleep while this runs; subshell so the bare `wait`s below do not wait on it
ST=eval/followup/replication2.STATUS; PY=.venv/bin/python; M=eval/matrix
say() { echo "$* $(date -u +%FT%TZ)" > $ST; }
dns() { until python3 -c "import socket;socket.gethostbyname('api.deepseek.com')" 2>/dev/null; do say "waiting for DNS"; sleep 60; done; }
missing() { local n=0 t c k; for t in ${5:-parson tomlc99 cjson}; do for c in $2; do for k in $(seq $3 $4); do [ -f runs/$t/$c-rep$k/final.json ] || n=$((n+1)); done; done; done; echo $n; }
# run a batch until every run has a final (infrastructure failures are rerun from the start), up to 8 passes
batch() { local name=$1 conds=$2 from=$3 to=$4 targets=${5:-parson,tomlc99,cjson} p
  for p in 1 2 3 4 5 6 7 8; do
    [ "$(missing x "${conds//,/ }" $from $to "${targets//,/ }")" -eq 0 ] && return 0
    dns; fund 0.5; say "$name pass $p: $(missing x "${conds//,/ }" $from $to "${targets//,/ }") runs missing"
    $PY eval/replicates.py --batch $name --targets $targets --conditions $conds --start-rep $from --reps $((to-from+1)) --retries 2 >/dev/null 2>&1
    [ "$(missing x "${conds//,/ }" $from $to "${targets//,/ }")" -eq 0 ] && return 0; sleep 600
  done; say "$name: runs still missing after 8 passes, stopped"; exit 1; }
# wait for at least $1 USD of DeepSeek balance before a batch (a 402 mid-batch is an infrastructure failure, rerun)
bal() { set -a; . ./.env; set +a; curl -s https://api.deepseek.com/user/balance -H "Authorization: Bearer $DEEPSEEK_API_KEY" | python3 -c "import sys,json;print(sum(float(b['total_balance']) for b in json.load(sys.stdin)['balance_infos']))" 2>/dev/null || echo 0; }
fund() { until python3 -c "import sys;sys.exit(float('$(bal)')<$1)"; do say "waiting for DeepSeek top-up to $1 USD (now $(bal))"; sleep 600; done; }
conds() { local c="" a k; for k in $(seq $3 $4); do for a in $2; do c="$c,run:$a-rep$k:$1"; done; done; echo "${c#,}"; }
# measure one target's conditions into its own file; then re-measure that file's error cells once, alone
measure1() { local tag=$1 what=$2 arms=$3 from=$4 to=$5 t=$6 f=$M/replication2_${1}_$6.jsonl
  [ -f $f.done ] && return 0   # resume: this file was measured and re-measured once already
  $PY eval/matrix.py --targets $t --conditions "$(conds $what "$arms" $from $to)" --k 20 --n 10000 --out $f >> $M/replication2.log 2>&1
  grep -q '"error"' $f 2>/dev/null || { touch $f.done; return 0; }
  grep '"error"' $f >> $M/replication2_first_errors.jsonl; grep -v '"error"' $f > $f.tmp; mv $f.tmp $f
  $PY eval/matrix.py --targets $t --conditions "$(conds $what "$arms" $from $to)" --k 20 --n 10000 --out $f >> $M/replication2.log 2>&1; touch $f.done; }
measure() { local t; say "measuring $1"; for t in ${6:-parson tomlc99 cjson}; do measure1 $1 $2 "$3" $4 $5 $t & done; wait; }
# phase 1: fresh first drafts (B6 = B5), 24 per target, more for a short target up to 30
fund 1.5; batch replication2_b6 B6 1 24
measure b6seed1 seed B6 1 12 & measure b6seed2 seed B6 13 24 & wait
# the draft mapping is computed once; a resume never rewrites it (DEVIATIONS 4 changed one entry by hand)
if [ ! -f eval/followup/replication2_seeds.json ]; then
for extra in 25 26 27 28 29 30; do
  $PY eval/followup/replication_seeds.py --arm B6 --need 20 --out replication2_seeds.json --inputs $M/replication2_b6seed*_*.jsonl > /dev/null 2>&1 && break
  short=$($PY eval/followup/replication_seeds.py --arm B6 --need 20 --out replication2_seeds.json --inputs $M/replication2_b6seed*_*.jsonl 2>&1 | grep -o "[a-z0-9]*: [0-9]* drawing" | cut -d: -f1 | paste -sd, -)
  batch replication2_b6_extra B6 $extra $extra $short
  measure b6seed_x$extra seed B6 $extra $extra "${short//,/ }"
done
$PY eval/followup/replication_seeds.py --arm B6 --need 20 --out replication2_seeds.json --inputs $M/replication2_b6seed*_*.jsonl > /dev/null 2>&1 || { say "draft rule: fewer than 20 drawing drafts after 30 B6 replicates, stopped for a decision"; exit 1; }
fi
# phase 2: the four arms, 20 pairs per target; measured as two halves in parallel (six processes)
fund 1.0; batch replication2_arms Q0,Q1,Q2,Q3 1 20   # gate lowered from 3.5 on the 2026-11-11 resume: 74 of 240 runs remained (DEVIATIONS 3)
say "measuring arms"
measure arms1 final "Q0 Q1 Q2 Q3" 1 10 & measure arms2 final "Q0 Q1 Q2 Q3" 11 20 & wait
say "measured; running the analysis once"
$PY eval/followup/replication2_report.py --inputs $M/replication2_arms1_*.jsonl $M/replication2_arms2_*.jsonl > $M/replication2.md 2>> $M/replication2.log
say "finished; report eval/matrix/replication2.md"
