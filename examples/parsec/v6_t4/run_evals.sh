#!/bin/bash
#
# Score v6_t4's merged bundles on F + the sealed test split: one LSF job per task, each on its own
# node (examples/parsec/v5/fan_out.sh with PARSEC_BENCH=v6), never more than MAX_CONCURRENT of this
# user's eval jobs at once across every suite listed. Meant to run as its own LSF job on a compute
# node; it only submits and waits, so it needs one slot and little memory.
#
# Every few minutes it tops each suite up (fan_out.sh skips tasks that already have a result or a
# live job), and when a suite has no task left it records the suite's time, cost and tokens.
#
# Usage (from the worktree root):
#   bsub -q normal -n 1 -M 4G -J v6t4_evals -oo ~/ccc_logs/%J.stdout -eo ~/ccc_logs/%J.stderr \
#        bash examples/parsec/v6_t4/run_evals.sh v6t4_m1 v6t4_m2 [v6t4_m3]
set -uo pipefail

T4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$T4_DIR/../../.." && pwd)"
MAX_CONCURRENT="${V6_T4_MAX_CONCURRENT:-30}"
OUT="$PROJECT_ROOT/results/v6_t4_e1/eval"
LOG="$OUT/run_evals.log"
mkdir -p "$OUT"
log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# shellcheck disable=SC1090
source "$HOME/.v5_g2e1_env.sh" >/dev/null 2>&1
export PARSEC_BENCH=v6
export PARSEC_V6N="${PARSEC_V6N:-/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v6_2026-10-16}"
cd "$PROJECT_ROOT"

SUITES=("$@")
[[ ${#SUITES[@]} -gt 0 ]] || { echo "usage: run_evals.sh SUITE [SUITE ...]" >&2; exit 2; }
declare -A started
log "start on $(hostname) job=${LSB_JOBID:-none} suites=${SUITES[*]} max=$MAX_CONCURRENT"

pending_in() {   # tasks of suite $1 with no baseline.json yet
  local s="$1" n=0 t
  while read -r t; do
    [[ -z "$t" ]] && continue
    ls results/v5_"$s"/"$t"/run/baseline.json >/dev/null 2>&1 || n=$((n + 1))
  done < ".capevolve/v5_${s}.tasks"
  echo "$n"
}

# Hosts whose local podman store is broken: a job there fails stack setup and never exits.
export V5_BAD_HOSTS_FILE="$OUT/bad_hosts.txt"
touch "$V5_BAD_HOSTS_FILE"
JOB_LOGS="${CCC_LOGS:-/dccstor/knewedge2/boazc/ccc_logs}"   # where fan_out.sh points bsub -oo/-eo

reap_finished() {
  # A parsec eval job stays in RUN after it is done (RUN_H4.md), so free its node:
  #   - result written            -> kill it, keep the result
  #   - stack setup failed (FATAL) -> kill it, block its host; fan_out resubmits the task elsewhere
  local j name host suite task
  bjobs -u "$USER" -noheader -o "jobid stat exec_host job_name" 2>/dev/null |
    awk '$2=="RUN" && $4 ~ /^v5_v6t4_m[0-9]_/ {print $1, $3, $4}' |
  while read -r j host name; do
    suite="$(sed -E 's/^v5_(v6t4_m[0-9])_.*/\1/' <<< "$name")"; task="${name#v5_${suite}_}"
    if [[ -f "results/v5_${suite}/${task}/run/baseline.json" ]]; then
      bkill "$j" >/dev/null 2>&1 && log "reaped finished job $j ($suite $task)"
    elif grep -qs "FATAL: parsec_stack.sh up failed" "$JOB_LOGS/$j.stdout" "$JOB_LOGS/$j.stderr"; then
      bkill "$j" >/dev/null 2>&1 && log "killed failed-setup job $j on $host ($suite $task); host blocked"
      grep -qx -- "$host" "$V5_BAD_HOSTS_FILE" || echo "$host" >> "$V5_BAD_HOSTS_FILE"
    fi
  done
}

while true; do
  reap_finished
  open=0
  for s in "${SUITES[@]}"; do
    [[ -f ".capevolve/v5_${s}.tasks" ]] || continue
    p="$(pending_in "$s")"
    live="$(bjobs -u "$USER" -noheader -o "stat job_name" 2>/dev/null | awk -v p="v5_${s}_" '($1=="RUN"||$1=="PEND") && index($2,p)==1' | wc -l)"
    if (( p == 0 && live == 0 )); then
      if [[ -z "${started[$s]:-}" || "${started[$s]}" != done ]]; then
        python3 "$T4_DIR/collect_evals.py" --suite "$s" >> "$LOG" 2>&1
        log "$s: all tasks scored; cost/time recorded"
        started[$s]=done
      fi
      continue
    fi
    open=$((open + 1))
    [[ -z "${started[$s]:-}" ]] && { started[$s]="$(date +%s)"; log "$s: started"; }
    total="$(bjobs -u "$USER" -noheader -o "stat job_name" 2>/dev/null | awk '($1=="RUN"||$1=="PEND") && $2 ~ /^v5_v6t4_/' | wc -l)"
    room=$((MAX_CONCURRENT - total))
    if (( room > 0 && p > live )); then
      out="$(bash examples/parsec/v5/fan_out.sh --suite-id "$s" --max-concurrent "$room" 2>&1 | grep -c ' job [0-9]')"
      (( out > 0 )) && log "$s: submitted $out (pending $p, live $live, all-suite live $total)"
    fi
  done
  (( open == 0 )) && { log "all suites scored"; break; }
  sleep 90
done
