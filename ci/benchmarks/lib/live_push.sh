#!/usr/bin/env bash
# Periodically export a still-running CapEvolve run's static dashboard data to its own branch,
# <run_id>__<tier>-<bench>, of the skillberry-runs/live repo (data/ at the branch root). Each cycle
# force-pushes ONE fresh commit, so a branch never holds more than the latest snapshot and nothing
# accumulates; cleanup deletes the branch. The skillberry-runs dashboard's "Running now" panel links
# to it (raw.githubusercontent.com/skillberry-runs/live/<branch>/data). Until 2026-11 this wrote
# live/<slug>/ on cap-evolve's benchmark-history branch instead, cloning it every cycle.
# See docs/superpowers/specs/2026-07-29-live-benchmark-monitoring-design.md.
#
# Usage:
#   live_push.sh <run_dir> <run_id> <slug>                loop forever (caller backgrounds this)
#   live_push.sh --cleanup <run_id> <slug> [pidfile]      one-shot: stop the poller named by
#                                                         <pidfile>, delete branch <run_id>__<slug>.
#                                                         No pidfile on disk => no-op.
#
# <run_dir> is the .capevolve/run_suite dir that gains an events.jsonl once the suite
# starts producing events. <slug> is "<tier>-<bench>" (e.g. "smoke-tau2") -- the same
# format the `aggregate` job uses for runs/<slug>/, so both trees are keyed consistently.
#
# Env:
#   GH_TOKEN          - push access to LIVE_REPO (required unless LIVE_REMOTE is set); in CI this is
#                       SKILLBERRY_RUNS_LIVE_TOKEN, a token that can reach the live repo ONLY
#   LIVE_REPO         - "owner/repo" receiving the branches (default skillberry-runs/live)
#   GITHUB_WORKSPACE  - repo checkout root (set by default on Actions runners)
#   CAPEVOLVE_PY      - python executable with capevolve_dashboard importable (exported
#                       by ci_setup.sh)
#   RUNNER_TEMP       - scratch dir (set by default on Actions runners; falls back to /tmp)
#   LIVE_REMOTE       - override the git remote URL (tests use a local bare repo; defaults to the
#                       token-authenticated github.com URL of LIVE_REPO)
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

LIVE_REPO="${LIVE_REPO:-skillberry-runs/live}"

remote_url() {
  echo "${LIVE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${LIVE_REPO}.git}"
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

# Publish $1's contents as data/ on branch $2 of the live repo: build ONE fresh commit locally and
# force-push it, so the branch only ever holds the latest snapshot. No clone: nothing on the remote
# is read, so the cost is one push no matter how many runs are live. Retries on push failure.
#   $1 = dir whose contents become data/, or "" to delete the branch instead
#   $2 = branch, e.g. "12345__smoke-tau2"
push_live() {
  local src="$1" branch="$2" work="${RUNNER_TEMP:-/tmp}/_live_snap_$$"
  for attempt in $(seq 1 "$ATTEMPTS"); do
    if [ -z "$src" ]; then
      # Delete. A branch that is already gone (never pushed, or swept) is success, not an error.
      # Run from a fresh empty repo, NEVER the caller's cwd: in CI that is the cap-evolve checkout,
      # whose actions/checkout config sends `http.https://github.com/.extraheader: AUTHORIZATION
      # basic <cap-evolve GITHUB_TOKEN>` on every github.com request -- overriding the live token in
      # the URL, so the push is refused (the 2026-11-18 smoke run left its branch behind that way).
      rm -rf "$work"
      git_bounded init -q "$work"
      git_bounded -C "$work" ls-remote --exit-code --heads "$(remote_url)" "$branch" >/dev/null 2>&1
      local lrc=$?
      if [ "$lrc" -eq 2 ]; then rm -rf "$work"; return 0; fi
      if [ "$lrc" -eq 0 ] && git_bounded -C "$work" push -q "$(remote_url)" --delete "$branch"; then
        rm -rf "$work"
        return 0
      fi
      rm -rf "$work"
      echo "live_push: delete attempt $attempt failed (ls-remote rc=$lrc)"
    else
      rm -rf "$work"
      mkdir -p "$work/data"
      cp -R "$src/." "$work/data/"
      if git_bounded -C "$work" init -q \
         && git_bounded -C "$work" add -A \
         && git_bounded -C "$work" -c user.name="skillberry-bot" -c user.email="actions@github.com" \
              commit -q -m "live: $branch" \
         && git_bounded -C "$work" push -q --force "$(remote_url)" "HEAD:refs/heads/$branch" 2>/dev/null; then
        rm -rf "$work"
        return 0
      fi
      rm -rf "$work"
      echo "live_push: push attempt $attempt failed"
    fi
    [ "$attempt" -lt "$ATTEMPTS" ] && sleep 3
  done
  echo "live_push: giving up after $ATTEMPTS attempt(s) (best-effort)"
  return 1
}

# One-shot cleanup: stop the poller, then delete its branch from the live repo.
#
# The pidfile is the only proof the poller ever ran. `Start live snapshot poller` is skipped
# whenever an earlier step failed -- only the stop step carries `if: always()` -- so a missing
# pidfile means there is nothing to kill AND no branch to delete. Cleaning up anyway is what hung
# run 36304767214 (then a clone of benchmark-history, ~1.4 GB, to delete a path never created).
# There is no clone any more, but the rule stands: no poller, no network.
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
  # Kill BEFORE the delete, so the poller cannot recreate the branch behind us. And no wait on it
  # afterwards: a wait here is the other way this step learns to hang, and the worst case it would
  # buy us is one leftover branch, which skillberry-runs/live's hourly stale-branch sweep removes.
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
  # One attempt, not three. Worst case must fit inside the step's `timeout-minutes` (see BOUNDS
  # above): 3 attempts x 2 network git calls (ls-remote, push --delete) x 60s is ~6min, which the
  # step would kill -- and a killed step is a failed job. Retrying is for the poller's 5-minute
  # cycle, which has another cycle coming; cleanup does not, and a missed delete only leaves a
  # stale branch for the sweep (and a stale "Running now" row until then).
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
