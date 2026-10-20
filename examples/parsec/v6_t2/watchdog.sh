#!/bin/bash
#
# Unattended watchdog for a v6_t2 suite, meant to run as its own LSF job on a compute node (not a
# login node). Every minute it:
#   1. kills the newer of any two lane workers LSF has put on the same node (their simulators bind
#      the same fixed ports; the killed worker's trials are requeued by the queue's heartbeat check);
#   2. resubmits, as a resume, any task whose run has not ended and has no driver pending or running
#      (a driver lost to a node failure or a kill), at most MAX_RESUBMITS times per task;
#   3. exits once every scaffolded task's run has ended, or after DEADLINE_H hours.
# Everything it does is logged to $LOG; a status snapshot is written to $STATUS when it exits.
#
# Usage (from the worktree root):
#   bsub -q normal -n 1 -M 4G -J v6t2_watchdog -oo ~/ccc_logs/%J.stdout -eo ~/ccc_logs/%J.stderr \
#        bash examples/parsec/v6_t2/watchdog.sh --suite-id e1
set -uo pipefail

T2_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$T2_DIR/../../.." && pwd)"
SUITE="${2:-}"
[[ "${1:-}" == --suite-id && -n "$SUITE" ]] || { echo "usage: watchdog.sh --suite-id ID" >&2; exit 2; }
MAX_RESUBMITS="${V6_T2_MAX_RESUBMITS:-3}"
DEADLINE_H="${V6_T2_WATCHDOG_HOURS:-14}"
LOG="${CCC_LOGS:-$HOME/ccc_logs}/v6t2_${SUITE}_watchdog.log"
STATUS="${CCC_LOGS:-$HOME/ccc_logs}/v6t2_${SUITE}_status.json"
COUNTS="${CCC_LOGS:-$HOME/ccc_logs}/v6t2_${SUITE}_resubmits.tsv"
touch "$COUNTS"

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# shellcheck disable=SC1090
source "$HOME/.v5_g2e1_env.sh" >/dev/null 2>&1
export PARSEC_V6N="${PARSEC_V6N:-/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v6_2026-10-16}"
cd "$PROJECT_ROOT"

ended() { [[ -f "$1/events.jsonl" ]] && grep -q '"finalize_skipped"' "$1/events.jsonl"; }

log "watchdog start on $(hostname) job=${LSB_JOBID:-none} suite=$SUITE"
start=$(date +%s)
while true; do
  # 1. one lane worker per node: keep the oldest job id, kill the rest
  bjobs -noheader -J "v6w_v6_t2_${SUITE}" -o "jobid stat exec_host" 2>/dev/null \
    | awk '$2=="RUN"{print $3, $1}' | sort -k1,1 -k2,2n | awk '{if($1==h){print $2, $1} else {h=$1}}' \
    | while read -r j h; do bkill "$j" >/dev/null 2>&1 && log "COLLISION on $h: killed newer worker $j"; done

  # 2. resubmit unfinished tasks that have lost their driver
  alive="$(bjobs -u "$USER" -noheader -o "stat job_name" 2>/dev/null | awk '$1=="RUN"||$1=="PEND"{print $2}')"
  open=0
  for proj in .capevolve/v6_t2_"${SUITE}"_*/project; do
    t="$(basename "$(dirname "$proj")")"; t="${t#v6_t2_${SUITE}_}"
    run=".capevolve/v6_t2_${SUITE}_$t/run_$t"
    ended "$run" && continue
    open=$((open + 1))
    grep -qx "v6d_t2_${SUITE}_$t" <<< "$alive" && continue
    n="$(awk -v t="$t" '$1==t{c++} END{print c+0}' "$COUNTS")"
    if (( n >= MAX_RESUBMITS )); then
      log "$t: driver gone, run not ended, resubmit limit ($MAX_RESUBMITS) reached; leaving it"
      continue
    fi
    out="$(V6_T2_SUBMIT_GAP=0 bash "$T2_DIR/run_t2.sh" --suite-id "$SUITE" --max-iterations 5 --resume --only "$t" 2>&1 \
           | grep -o 'Job <[0-9]*>')"
    echo "$t" >> "$COUNTS"
    log "$t: driver gone, run not ended -> resubmitted as resume ($((n + 1))/$MAX_RESUBMITS) $out"
    sleep 20
  done

  if (( open == 0 )); then log "all tasks ended"; break; fi
  if (( $(date +%s) - start > DEADLINE_H * 3600 )); then log "deadline ${DEADLINE_H}h reached with $open task(s) open"; break; fi
  sleep 60
done

python3 - "$SUITE" "$STATUS" <<'PY'
import json, os, sys, time
sys.path.insert(0, "examples/parsec/v6_t2"); import scaffold_projects as S
suite, status = sys.argv[1], sys.argv[2]
rows = []
for t in S.TASK_IDS:
    d = f".capevolve/v6_t2_{suite}_{t}/run_{t}"; seed = None; steps = ""; ended = False; opt = 0.0
    if os.path.exists(d + "/events.jsonl"):
        for l in open(d + "/events.jsonl"):
            try: e = json.loads(l)
            except ValueError: continue
            k = e.get("kind")
            if k == "baseline_reused": seed = e["val"]
            elif k == "step": steps += "A" if e.get("accept") else "r"; opt += e.get("opt_cost_usd") or 0
            elif k == "finalize_skipped": ended = True
    try: best = json.load(open(d + "/state.json"))["spent"]["best_val"]
    except Exception: best = None
    rows.append(dict(task=t, seed=seed, best=best, steps=steps, ended=ended, opt_usd=round(opt, 2)))
json.dump({"written": time.strftime("%Y-%m-%d %H:%M"), "tasks": rows}, open(status, "w"), indent=1)
PY
log "status written to $STATUS; watchdog exit"
