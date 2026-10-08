#!/bin/bash
#
# Submit one `bsub` job per task for an h4 eval sweep, each pinned to its OWN
# compute node. Ported from skillberry-skill-maker's
# run_tasks_on_dedicated_machines.sh, which is the script this pattern comes
# from; the host-filtering below is the part worth copying.
#
# One host per job is not a performance choice, it is a correctness one:
# podman's graphroot is per-UID-per-host (/tmp/podman-$UID), so two jobs on one
# node corrupt each other's image store. Given one node per job, every lane
# binds the default ports on 127.0.0.1 and no offsetting is needed — which is
# the only workable scheme anyway, since install_seeds.py hardcodes localhost
# and those ports.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   export LLM_API_KEY=...  LLM_API_BASE=...  HARNESS_LLM_SIMULATION_MODEL=...
#   bash scripts/parsec/h4/fan_out.sh --suite-id base01 [--max-concurrent 10]
#
#   --suite-id ID        the suite scaffold_eval_projects.py created (required)
#   --tasks a,b,c        override the suite's task manifest
#   --max-concurrent N   how many jobs to submit in this wave (default 10)
#   --redo               resubmit tasks that already have a result
#   --queue Q            LSF queue (default: normal)
#   --memory M           -M value (default: 64G)
#   --allow-host-sharing submit even when there are fewer free hosts than jobs
#   --dry-run            print the bsub commands, submit nothing
#
# bsub inherits the submitting shell's environment, so export PARSEC_V4N and
# the three LLM_* variables BEFORE running this.
#
# Deliberately NO -W. A cap-evolve job routinely finishes its work and then
# hangs in a post-run step; a wall-clock limit kills it AFTER the result is
# written, turning a finished run into TERM_RUNLIMIT and losing the outcome.
# Detect completion from the per-task cap-evolve.log (or the
# `lout <jobid> | grep "Exit:     0"` sweep in RUN_H4.md) and bkill that exact
# job id. -n 1 because an eval-only run needs one slot, not four.
set -eo pipefail

# No apostrophes in these messages: inside ${VAR:?word} bash processes quotes in
# `word`, so a lone ' opens a quoted span that runs on until the next one and
# silently scrambles the parse of everything below.
: "${PARSEC_V4N:?PARSEC_V4N must be exported — bsub inherits the submitting shell env}"
: "${LLM_API_KEY:?LLM_API_KEY must be exported — bsub inherits the submitting shell env}"
: "${LLM_API_BASE:?LLM_API_BASE must be exported — bsub inherits the submitting shell env}"
: "${HARNESS_LLM_SIMULATION_MODEL:?HARNESS_LLM_SIMULATION_MODEL must be exported}"

H4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$H4_DIR/../../.." && pwd)"

# The user's established CCC convention; %J is LSF's job-id substitution, so
# the files land as <jobid>.stdout/.stderr with no post-submission rename.
CCC_LOGS="${CCC_LOGS:-/dccstor/knewedge2/boazc/ccc_logs}"

SUITE_ID=""
TASKS_OVERRIDE=""
MAX_CONCURRENT=10
REDO=false
QUEUE="normal"
MEMORY="64G"
ALLOW_SHARING=false
DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)           SUITE_ID="$2"; shift 2 ;;
    --tasks)              TASKS_OVERRIDE="$2"; shift 2 ;;
    --max-concurrent)     MAX_CONCURRENT="$2"; shift 2 ;;
    --redo)               REDO=true; shift ;;
    --queue)              QUEUE="$2"; shift 2 ;;
    --memory)             MEMORY="$2"; shift 2 ;;
    --allow-host-sharing) ALLOW_SHARING=true; shift ;;
    --dry-run)            DRY_RUN=true; shift ;;
    -h|--help)            sed -n '2,37p' "$0"; exit 0 ;;
    *)                    echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$SUITE_ID" ]]; then
  echo "usage: fan_out.sh --suite-id ID [--max-concurrent N] [--dry-run]" >&2
  exit 1
fi

MANIFEST="$PROJECT_ROOT/.capevolve/h4_${SUITE_ID}.tasks"
if [[ -n "$TASKS_OVERRIDE" ]]; then
  IFS=',' read -r -a ALL_TASKS <<< "$TASKS_OVERRIDE"
elif [[ -f "$MANIFEST" ]]; then
  mapfile -t ALL_TASKS < "$MANIFEST"
else
  echo "ERROR: no task manifest at $MANIFEST and no --tasks given." >&2
  echo "       Scaffold the suite first:" >&2
  echo "       python3 scripts/parsec/h4/scaffold_eval_projects.py --suite-id $SUITE_ID --artifact <dir>" >&2
  exit 1
fi

# A finished eval leaves results/h4_<suite>/<task>/run/baseline.json. Skipping
# those makes a second invocation a resume rather than a duplicate spend.
RESULTS_ROOT="$PROJECT_ROOT/results/h4_$SUITE_ID"

# A task with no baseline.json yet might still have an LSF job already working
# on it -- "pending" from the completed-result check alone would resubmit it,
# and two jobs racing to create the same cap-evolve run dir corrupts both (one
# wins RunDir.create(), the other crashes on FileExistsError, or worse, they
# interleave trial writes into the one that wins). Cross-reference bjobs by
# this suite's own -J naming (set below, identical to what gets submitted) so
# an in-flight task is never resubmitted underneath itself.
mapfile -t INFLIGHT_JOBS < <(bjobs -w -u "$USER" 2>/dev/null | awk -v p="h4_${SUITE_ID}_" \
  'NR>1 && index($7,p)==1 {print substr($7,length(p)+1)}')

PENDING=()
DONE=()
INFLIGHT=()
for t in "${ALL_TASKS[@]}"; do
  [[ -z "$t" ]] && continue
  if [[ "$REDO" != true && -f "$RESULTS_ROOT/$t/run/baseline.json" ]]; then
    DONE+=("$t")
    continue
  fi
  in_flight=false
  for it in "${INFLIGHT_JOBS[@]:-}"; do
    [[ "$it" == "$t" ]] && in_flight=true && break
  done
  if [[ "$in_flight" == true ]]; then
    INFLIGHT+=("$t")
  else
    PENDING+=("$t")
  fi
done
if (( ${#INFLIGHT[@]} > 0 )); then
  echo "skipping ${#INFLIGHT[@]} task(s) with a job already in flight: ${INFLIGHT[*]}"
fi

echo "suite $SUITE_ID: ${#ALL_TASKS[@]} task(s) total, ${#DONE[@]} already done, ${#PENDING[@]} pending"
if (( ${#PENDING[@]} == 0 )); then
  echo "nothing to submit. Collect with:"
  echo "  python3 scripts/parsec/h4/collect.py --suite-id $SUITE_ID"
  exit 0
fi

# ---------------------------------------------------------------------------
# Host selection.
# ---------------------------------------------------------------------------
# Hosts in the cccxc600-630 range are held by the `infusion` advance
# reservation on a window running to 2038, and `bhosts` does not show
# reservations — only `brsvs` does. Pinning there means a job that never
# starts. These extras were reserved as of 2026-09.
EXTRA_RESERVED=(cccxc701 cccxc702 cccxc704 cccxc707 cccxc710 cccxc711 cccxc535 cccxc575)

# One brsvs call, cached, rather than one per candidate host.
RESERVED_BLOB="$(brsvs -w 2>/dev/null || true)"

is_reserved() {
  local h="$1" r n
  if [[ "$h" =~ ^cccxc([0-9]{3})$ ]]; then
    n=$((10#${BASH_REMATCH[1]}))
    (( n >= 600 && n <= 630 )) && return 0
  fi
  for r in "${EXTRA_RESERVED[@]}"; do [[ "$h" == "$r" ]] && return 0; done
  [[ -n "$RESERVED_BLOB" ]] && grep -qw -- "$h" <<< "$RESERVED_BLOB" && return 0
  return 1
}

mapfile -t ALL_OK_HOSTS < <(bhosts 2>/dev/null | awk 'NR>1 && $2=="ok" {print $1}')
# Hosts already running jobs of YOURS — the podman-per-host rule applies across
# your own sweeps too, not just within this one.
mapfile -t USED_HOSTS < <(bjobs -u "$USER" -r 2>/dev/null | awk 'NR>1 && $6!="" {print $6}' | sort -u)

AVAILABLE_HOSTS=()
for h in "${ALL_OK_HOSTS[@]}"; do
  skip=false
  for u in "${USED_HOSTS[@]}"; do [[ "$h" == "$u" ]] && skip=true && break; done
  [[ "$skip" == true ]] && continue
  is_reserved "$h" && continue
  AVAILABLE_HOSTS+=("$h")
done

echo "hosts: ${#ALL_OK_HOSTS[@]} ok, ${#USED_HOSTS[@]} already running your jobs, ${#AVAILABLE_HOSTS[@]} usable after reservations"

WAVE=${#PENDING[@]}
(( WAVE > MAX_CONCURRENT )) && WAVE=$MAX_CONCURRENT
if (( WAVE > ${#AVAILABLE_HOSTS[@]} )); then
  if [[ "$ALLOW_SHARING" == true ]]; then
    echo "WARNING: only ${#AVAILABLE_HOSTS[@]} usable host(s) for $WAVE job(s)." >&2
    echo "         --allow-host-sharing given: jobs will share nodes, and sharing a" >&2
    echo "         node corrupts podman state for BOTH. Expect losses." >&2
  else
    echo "capping this wave at ${#AVAILABLE_HOSTS[@]} job(s): one host per job." >&2
    WAVE=${#AVAILABLE_HOSTS[@]}
  fi
fi
if (( WAVE == 0 )); then
  echo "no usable hosts right now — try again later, or check 'bhosts' / 'brsvs -w'." >&2
  exit 1
fi

[[ "$DRY_RUN" != true ]] && mkdir -p "$CCC_LOGS"
SWEEP_DIR="$RESULTS_ROOT/_sweep"
SWEEP_LOG="$SWEEP_DIR/$(date +%Y%m%d_%H%M%S).tsv"
if [[ "$DRY_RUN" != true ]]; then
  mkdir -p "$SWEEP_DIR"
  printf 'jobid\ttask\thost\tsubmitted_at\n' > "$SWEEP_LOG"
fi

echo
echo "submitting $WAVE of ${#PENDING[@]} pending task(s), queue=$QUEUE mem=$MEMORY"
echo

SUBMITTED=0
for (( i = 0; i < WAVE; i++ )); do
  task="${PENDING[$i]}"
  host="${AVAILABLE_HOSTS[$(( i % ${#AVAILABLE_HOSTS[@]} ))]}"

  BSUB_CMD=(
    bsub -q "$QUEUE" -M "$MEMORY" -n 1 -m "$host"
    -J "h4_${SUITE_ID}_${task}"
    -oo "$CCC_LOGS/%J.stdout"
    -eo "$CCC_LOGS/%J.stderr"
    bash "$H4_DIR/run_one_eval.sh" --suite-id "$SUITE_ID" --task-id "$task"
  )

  if [[ "$DRY_RUN" == true ]]; then
    printf '[dry-run] %-34s -> %s\n' "$task" "$host"
    printf '          %s\n' "${BSUB_CMD[*]}"
    continue
  fi

  # bsub prints: Job <123456> is submitted to queue <normal>.
  if out="$("${BSUB_CMD[@]}" 2>&1)"; then
    jobid="$(sed -n 's/^Job <\([0-9]\+\)>.*/\1/p' <<< "$out")"
    printf '%-34s -> %-12s job %s\n' "$task" "$host" "${jobid:-?}"
    printf '%s\t%s\t%s\t%s\n' "${jobid:-unknown}" "$task" "$host" "$(date -Iseconds)" >> "$SWEEP_LOG"
    SUBMITTED=$((SUBMITTED + 1))
  else
    echo "FAILED to submit $task on $host:" >&2
    sed 's/^/    /' <<< "$out" >&2
  fi
  sleep 1   # don't hammer the scheduler
done

REMAINING=$(( ${#PENDING[@]} - SUBMITTED ))
echo
if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] nothing submitted."
  exit 0
fi
echo "submitted $SUBMITTED job(s); sweep log: $SWEEP_LOG"
if (( REMAINING > 0 )); then
  echo "$REMAINING task(s) still pending — rerun this script when hosts free up"
  echo "(already-finished tasks are skipped automatically)."
fi
cat <<EOF

monitor:   bjobs -w
zombies:   for j in \$(bjobs -o 'jobid' -noheader 2>/dev/null); do lout \$j | grep -q "Exit:     0" && echo "\$j finished — bkill \$j"; done
per-task:  tail -f $RESULTS_ROOT/<task>/cap-evolve.log
collect:   python3 scripts/parsec/h4/collect.py --suite-id $SUITE_ID
EOF
