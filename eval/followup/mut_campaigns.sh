#!/bin/bash
# Follow-up bug campaigns: Grammarinator + mutation stage (review point 7). Same protocol as
# eval/campaigns.py: eval/campaign.py, 30 minutes, 10^7 inputs cap. 3 workers. Rows append to
# eval/campaigns/rq4_mut.jsonl; one-line progress in eval/campaigns/rq4_mut.STATUS.
cd "$(dirname "$0")/../.."
OUT=eval/campaigns/rq4_mut.jsonl; LOG=eval/campaigns/rq4_mut.log; ST=eval/campaigns/rq4_mut.STATUS
jobs() {
  for s in 0 1 2; do
    for v in defaults+mut deep+mut; do
      echo "json-parser issue78 grammarinator:JSON:$v $s"; echo "json-parser issue68 grammarinator:JSON:$v $s"
      echo "cjson cve-2023-53154 grammarinator:JSON:$v $s"
    done
    echo "tomlc99 issue50 grammarinator:TOML:defaults+mut $s"; echo "tomlc99 recursion grammarinator:TOML:defaults+mut $s"
  done
}
TOTAL=$(jobs | wc -l | tr -d " "); export OUTF=$OUT LOGF=$LOG STF=$ST TOTALN=$TOTAL
echo "running 0/$TOTAL started $(date -u +%FT%TZ)" > $ST
jobs | xargs -P 3 -L 1 bash -c 'cd "$0"; .venv/bin/python eval/campaign.py --target "$1" --bug "$2" --ref "$3" --seed "$4" --minutes 30 --out "$OUTF" >> "$LOGF" 2>&1; n=$(grep -c "" "$OUTF" 2>/dev/null || echo 0); echo "running $n/$TOTALN last $1 $2 $3 seed $4 $(date -u +%FT%TZ)" > "$STF"' "$PWD"
echo "done $(grep -c '' $OUT)/$TOTAL finished $(date -u +%FT%TZ)" > $ST
