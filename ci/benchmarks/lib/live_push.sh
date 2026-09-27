#!/usr/bin/env bash
# Periodically export a still-running CapEvolve run's static dashboard data onto the
# benchmark-history branch's live/<run_id>__<tier>-<bench>/data/ dir, overwritten in
# place every cycle -- no history of intermediate snapshots is kept, only the latest --
# so site/benchmarks.html's "Running now" panel can link to a near-live SPA view.
# See docs/superpowers/specs/2026-07-29-live-benchmark-monitoring-design.md.
#
# Usage:
#   live_push.sh <run_dir> <run_id> <slug>                loop forever (caller backgrounds this)
#   live_push.sh --cleanup <run_id> <slug> [pidfile]      one-shot: stop the poller named by
#                                                         <pidfile>, delete live/<run_id>__<slug>,
#                                                         push. No pidfile on disk => no-op.
#
# <run_dir> is the .capevolve/run_suite dir that gains an events.jsonl once the suite
# starts producing events. <slug> is "<tier>-<bench>" (e.g. "smoke-tau2") -- the same
# format the `aggregate` job uses for runs/<slug>/, so both trees are keyed consistently.
#
# Env:
#   GH_TOKEN          - push access to this repo (required unless LIVE_REMOTE is set)
#   GITHUB_REPOSITORY - "owner/repo" (set by default on Actions runners)
#   GITHUB_WORKSPACE  - repo checkout root (set by default on Actions runners)
#   CAPEVOLVE_PY      - python executable with capevolve_dashboard importable (exported
#                       by ci_setup.sh)
#   RUNNER_TEMP       - scratch dir (set by default on Actions runners; falls back to /tmp)
#   LIVE_REMOTE       - override the git remote URL (used by the manual test in this
#                       task's Step 3; defaults to the token-authenticated github.com URL)
#   LIVE_PUSH_GIT_TIMEOUT      - wall-clock cap, seconds, on EVERY git call (default 60)
#   LIVE_PUSH_ATTEMPTS         - clone/push attempts per poller cycle (default 3)
#   LIVE_PUSH_CLEANUP_ATTEMPTS - clone/push attempts in --cleanup mode (default 1, see below)
set -uo pipefail   # no -e: a failed cycle should log and retry, not kill the loop

INTERVAL=300  # 5 minutes, hardcoded -- see design doc; not worth a workflow input (YAGNI)

# BOUNDS. Nothing in here used to have one, and the `Stop live snapshot poller` step inherits
# the benchmark job's `timeout-minutes: 1440` (sized for a 912-task suite). In run 36304767214
# that step sat `in_progress` for 20+ minutes on a job whose real work had already failed after
# 3, on a self-hosted runner that serves one leg at a time -- and GitHub serves no step log
# until the job ends, so the actual failure was unreachable the whole time and lost for good
# when the run was cancelled to force the flush (#547).
#
# The workflow step now also carries its own `timeout-minutes`, but that is only a BACKSTOP: a
# step killed by `timeout-minutes` is a FAILED step, and a failed best-effort cleanup must not
# fail a job. So the bound that has to fire is this one, and it stays well inside the step's.
GIT_TIMEOUT="${LIVE_PUSH_GIT_TIMEOUT:-60}"
ATTEMPTS="${LIVE_PUSH_ATTEMPTS:-3}"

# A credential prompt on a runner has no tty to answer it, which makes it an indefinite stall
# rather than an error. Exported so it covers every git call, including any git may itself run.
export GIT_TERMINAL_PROMPT=0

remote_url() {
  echo "${LIVE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"
}

# Run one git call under a hard wall-clock cap.
#
# Deliberately NOT coreutils `timeout`: it is absent from a stock macOS (where this file's
# pytest coverage also runs), so depending on it would let the bound silently vanish on some
# hosts -- which is the exact failure mode being fixed. git is started as a DIRECT child so
# the watchdog's signal lands on git itself, and the watchdog polls in 1s steps so it exits on
# its own the moment git finishes, leaving no stray `sleep` behind to outlive the step.
git_bounded() {
  git "$@" &
  local gpid=$!
  (
    _waited=0
    while [ "$_waited" -lt "$GIT_TIMEOUT" ]; do
      kill -0 "$gpid" 2>/dev/null || exit 0
      sleep 1
      _waited=$((_waited + 1))
    done
    echo "live_push: git $1 exceeded ${GIT_TIMEOUT}s -- terminating it"
    kill -TERM "$gpid" 2>/dev/null
    sleep 2
    kill -KILL "$gpid" 2>/dev/null
  ) &
  local wpid=$!
  wait "$gpid"
  local rc=$?
  kill "$wpid" 2>/dev/null
  wait "$wpid" 2>/dev/null
  return "$rc"
}

# Clone benchmark-history, replace live/<slug_dir> in one commit, push. Retries on
# clone/push failure (races with other concurrent bench-job pollers are expected).
#   $1 = dir whose contents become live/<slug_dir>/data/, or "" to only delete
#   $2 = slug_dir, e.g. "12345__smoke-tau2"
push_live() {
  local src="$1" slug_dir="$2" clone_dir="${RUNNER_TEMP:-/tmp}/_live_hist_$$"
  for attempt in $(seq 1 "$ATTEMPTS"); do
    rm -rf "$clone_dir"
    if ! git_bounded clone --depth 1 --branch benchmark-history "$(remote_url)" "$clone_dir" 2>/dev/null; then
      echo "live_push: clone failed (attempt $attempt)"
      [ "$attempt" -lt "$ATTEMPTS" ] && sleep 3
      continue
    fi
    (
      cd "$clone_dir" || exit 1
      mkdir -p live   # ensures the pathspec below always matches, even on a first-ever push
      rm -rf "live/$slug_dir"
      if [ -n "$src" ]; then
        mkdir -p "live/$slug_dir/data"
        cp -R "$src/." "live/$slug_dir/data/"
      fi
      git_bounded add -A live
      git_bounded config user.name "skillberry-bot"
      git_bounded config user.email "actions@github.com"
      git_bounded commit -m "live: update $slug_dir" -q || exit 0
      git_bounded push origin benchmark-history
    )
    local rc=$?
    rm -rf "$clone_dir"
    [ "$rc" -eq 0 ] && return 0
    echo "live_push: push attempt $attempt failed"
    [ "$attempt" -lt "$ATTEMPTS" ] && sleep 3
  done
  echo "live_push: giving up after $ATTEMPTS attempt(s) (best-effort)"
  return 1
}

# One-shot cleanup: stop the poller, then drop its live/<slug_dir> from benchmark-history.
#
# The pidfile is the only proof the poller ever ran. `Start live snapshot poller` is skipped
# whenever an earlier step failed -- only the stop step carries `if: always()` -- so a missing
# pidfile means there is nothing to kill AND no live/ dir to delete. Cleaning up anyway is what
# hung run 36304767214: a clone of benchmark-history (~1.4 GB across 24k files at the tip, and
# growing with every recorded run) to delete a path that had never been created.
cleanup() {
  local run_id="$1" slug="$2"
  local pidfile="${3:-${RUNNER_TEMP:-/tmp}/live_push_${slug//-/_}.pid}"
  if [ ! -f "$pidfile" ]; then
    echo "live_push: no pidfile at $pidfile -- the poller never started, nothing to clean up"
    return 0
  fi
  local pid
  pid="$(cat "$pidfile" 2>/dev/null)"
  rm -f "$pidfile"   # so a re-run of the step is the no-op above rather than a second push
  # Kill BEFORE the delete, so the poller cannot recreate live/<slug_dir> behind us. And no
  # wait on it afterwards: a wait here is the other way this step learns to hang, and the
  # worst case it would buy us is one extra live/ dir, which the next cleanup removes.
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
  # One attempt, not three. Worst case must fit inside the step's `timeout-minutes` (see BOUNDS
  # above): 3 attempts x 2 network git calls x 60s is ~6min, which the step would kill -- and a
  # killed step is a failed job. Retrying is for the poller's 5-minute cycle, which has another
  # cycle coming; cleanup does not, and a missed delete only leaves a stale "Running now" row.
  ATTEMPTS="${LIVE_PUSH_CLEANUP_ATTEMPTS:-1}"
  push_live "" "${run_id}__${slug}" || true
  return 0
}

main() {
  if [ "${1:-}" = "--cleanup" ]; then
    cleanup "$2" "$3" "${4:-}"
    return 0
  fi

  local run_dir="$1" run_id="$2" slug="$3" slug_dir="${2}__${3}"
  while true; do
    sleep "$INTERVAL"
    if [ ! -f "$run_dir/events.jsonl" ]; then
      echo "live_push: no events.jsonl yet at $run_dir, skipping this cycle"
      continue
    fi
    local out="${RUNNER_TEMP:-/tmp}/live_export_${slug_dir}"
    rm -rf "$out"
    if PYTHONPATH="$GITHUB_WORKSPACE/dashboard/backend" "$CAPEVOLVE_PY" -m capevolve_dashboard.export_static \
        --base "$(dirname "$run_dir")" --run-id run_suite --out "$out"; then
      push_live "$out" "$slug_dir" || true
    else
      echo "live_push: export_static failed this cycle (best-effort, will retry)"
    fi
    rm -rf "$out"
  done
}

# Guard the auto-run so this file can also be `source`d (functions only) for testing.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
