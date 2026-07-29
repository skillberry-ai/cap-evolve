#!/usr/bin/env bash
# Periodically export a still-running CapEvolve run's static dashboard data onto the
# benchmark-history branch's live/<run_id>__<tier>-<bench>/data/ dir, overwritten in
# place every cycle -- no history of intermediate snapshots is kept, only the latest --
# so site/benchmarks.html's "Running now" panel can link to a near-live SPA view.
# See docs/superpowers/specs/2026-07-29-live-benchmark-monitoring-design.md.
#
# Usage:
#   live_push.sh <run_dir> <run_id> <slug>     loop forever (caller backgrounds this)
#   live_push.sh --cleanup <run_id> <slug>     one-shot: delete live/<run_id>__<slug>, push
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
set -uo pipefail   # no -e: a failed cycle should log and retry, not kill the loop

INTERVAL=300  # 5 minutes, hardcoded -- see design doc; not worth a workflow input (YAGNI)

remote_url() {
  echo "${LIVE_REMOTE:-https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git}"
}

# Clone benchmark-history, replace live/<slug_dir> in one commit, push. Retries on
# clone/push failure (races with other concurrent bench-job pollers are expected).
#   $1 = dir whose contents become live/<slug_dir>/data/, or "" to only delete
#   $2 = slug_dir, e.g. "12345__smoke-tau2"
push_live() {
  local src="$1" slug_dir="$2" clone_dir="${RUNNER_TEMP:-/tmp}/_live_hist_$$"
  for attempt in 1 2 3; do
    rm -rf "$clone_dir"
    if ! git clone --depth 1 --branch benchmark-history "$(remote_url)" "$clone_dir" 2>/dev/null; then
      echo "live_push: clone failed (attempt $attempt)"
      sleep 3
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
      git add -A live
      git config user.name "skillberry-bot"
      git config user.email "actions@github.com"
      git commit -m "live: update $slug_dir" -q || exit 0
      git push origin benchmark-history
    )
    local rc=$?
    rm -rf "$clone_dir"
    [ "$rc" -eq 0 ] && return 0
    echo "live_push: push attempt $attempt failed, retrying"
    sleep 3
  done
  echo "live_push: giving up after 3 attempts (best-effort, will retry next cycle)"
  return 1
}

main() {
  if [ "${1:-}" = "--cleanup" ]; then
    local run_id="$2" slug="$3"
    push_live "" "${run_id}__${slug}" || true
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
