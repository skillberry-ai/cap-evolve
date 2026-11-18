#!/usr/bin/env bash
# Publish ONE benchmark leg's results to the skillberry-runs org, from the bench job itself.
#
#   publish_results.sh <out_dir> <run_id> <slug>
#     out_dir  the leg's output dir (ci/benchmarks/.work/suite_<tier>_<bench>): runmeta.json,
#              metrics.jsonl, steps.jsonl, ui/data/
#     run_id   GitHub run id
#     slug     <tier>-<bench>, e.g. canary-tau2
#
# Writes (https://skillberry-runs.github.io/dashboard/):
#   ci_ui/<run_id>__<slug>/          -> skillberry-runs/<bench repo>   the run's "Open UI" data
#   records/<run_id>__<slug>.json    -> skillberry-runs/dashboard      its push deploys the site
# The bench -> repo map is the dashboard's sections.json ("benches"); masking and record validation
# are the dashboard's own scripts, so CI and hand-publishing (its PUBLISHING.md) apply the same rules.
#
# WHY HERE AND NOT IN A SEPARATE JOB: until 2026-11-18 the bench job uploaded an artifact and a
# GitHub-hosted `aggregate` job published it. After IBM's network change the self-hosted runners
# reach github.com (every connection ~8 s slower) but the artifact service's CreateArtifact call
# times out, so nothing was published. Plain git to github.com still works, so each leg now
# publishes itself. The artifact upload is kept, best-effort, as a download convenience only.
#
# Order: Open UI data first, then the record, so the dashboard deploy the record push triggers
# already sees the data; and the record says has_ui only if that data was actually pushed.
# Each push retries on a race (another leg publishing at the same moment) with a fresh clone;
# every leg adds only its own new files, so a retry never conflicts.
#
# Environment:
#   GH_TOKEN             push access to the dashboard and the benchmark repos (in CI:
#                        SKILLBERRY_RUNS_RESULTS_TOKEN); not needed with RESULTS_REMOTE_BASE
#   RESULTS_ORG          default skillberry-runs
#   RESULTS_REMOTE_BASE  tests: <base>/<repo>.git is used for clone AND push (e.g. file:///tmp/r)
#   PY                   python to run the record/mask/check scripts (default python3)
#   ATTEMPTS             push attempts per repo (default 5)
#   GIT_TIMEOUT          seconds per git call (default 240)
#
# Exit: 0 published (or nothing to publish), 1 a publish failed (the job shows it as failed).
set -uo pipefail

out="${1:?out_dir}"; run_id="${2:?run_id}"; slug="${3:?slug}"
RESULTS_ORG="${RESULTS_ORG:-skillberry-runs}"
PY="${PY:-python3}"
ATTEMPTS="${ATTEMPTS:-5}"
GIT_TIMEOUT="${GIT_TIMEOUT:-240}"
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
name="${run_id}__${slug}"
BOT=(-c user.name=skillberry-bot -c user.email=281869455+skillberry-bot@users.noreply.github.com)

log() { echo "publish_results: $*"; }

# Repos are public: clone anonymously; the token is used for the push only, and only on the
# command line, so it is never written into a .git/config on this (persistent) runner.
clone_url() { echo "${RESULTS_REMOTE_BASE:-https://github.com/${RESULTS_ORG}}/$1.git"; }
push_url() {
  if [ -n "${RESULTS_REMOTE_BASE:-}" ]; then echo "${RESULTS_REMOTE_BASE}/$1.git"
  else echo "https://x-access-token:${GH_TOKEN}@github.com/${RESULTS_ORG}/$1.git"; fi
}

# One git call under a hard wall-clock cap (same approach as live_push.sh: no coreutils
# `timeout`, git is a direct child so the signal lands on it).
git_bounded() {
  git "$@" &
  local gpid=$!
  (
    _w=0
    while [ "$_w" -lt "$GIT_TIMEOUT" ]; do kill -0 "$gpid" 2>/dev/null || exit 0; sleep 1; _w=$((_w + 1)); done
    echo "publish_results: git $1 exceeded ${GIT_TIMEOUT}s -- terminating it"
    kill -TERM "$gpid" 2>/dev/null; sleep 2; kill -KILL "$gpid" 2>/dev/null
  ) &
  local wpid=$!
  wait "$gpid"; local rc=$?
  kill "$wpid" 2>/dev/null; wait "$wpid" 2>/dev/null
  return "$rc"
}

# Partial, sparse, shallow clone of $1 into $2 with only the paths $3... checked out. Run from
# $work, never the caller's cwd: in CI that is the cap-evolve checkout, whose config carries
# actions/checkout's auth header for github.com.
sparse_clone() {
  local repo="$1" dir="$2"; shift 2
  rm -rf "$dir"
  (cd "$work" && git_bounded clone -q --depth 1 --filter=blob:none --sparse "$(clone_url "$repo")" "$dir") || return 1
  git -C "$dir" sparse-checkout set "$@"
}

# Copy $3 (a dir or file) to <clone>/$4 in repo $1, commit with message $2, push; retry on races.
# Only $5 is checked out: for Open UI data that is the run's own (new) ci_ui/<name> folder, never
# all of ci_ui/, which runs to GBs.
publish_to() {
  local repo="$1" msg="$2" src="$3" dst="$4" sparse="$5" d="$work/r_$1" branch
  for attempt in $(seq 1 "$ATTEMPTS"); do
    if ! sparse_clone "$repo" "$d" "$sparse"; then
      log "clone of $repo failed (attempt $attempt)"; sleep 5; continue
    fi
    mkdir -p "$d/$(dirname "$dst")"
    rm -rf "${d:?}/$dst"
    cp -R "$src" "$d/$dst"
    git -C "$d" add "$dst"
    if git -C "$d" diff --cached --quiet; then log "$repo already has $dst"; return 0; fi
    git -C "$d" "${BOT[@]}" commit -q -m "$msg" || return 1
    branch="$(git -C "$d" rev-parse --abbrev-ref HEAD)"   # the repo's default branch
    if git_bounded -C "$d" push -q "$(push_url "$repo")" "HEAD:refs/heads/$branch"; then
      log "pushed $dst to $RESULTS_ORG/$repo"; return 0
    fi
    log "push to $repo failed (attempt $attempt; likely another run publishing at the same time), retrying"
    sleep $((attempt * 3))
  done
  return 1
}

rm_json="$out/runmeta.json"
[ -f "$rm_json" ] || { log "no runmeta.json in $out (the job stopped before writing it); nothing to publish"; exit 0; }
[ -n "${RESULTS_REMOTE_BASE:-}" ] || [ -n "${GH_TOKEN:-}" ] || {
  echo "::error::SKILLBERRY_RUNS_RESULTS_TOKEN is not set; results of $name are not published"; exit 1; }

work="$(mktemp -d "${RUNNER_TEMP:-/tmp}/_publish_${name}.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# The dashboard: sections.json (bench -> repo), scripts/ (mask, validate), records/ (where ours goes).
sparse_clone dashboard "$work/dash" scripts records \
  || { echo "::error::cannot clone $RESULTS_ORG/dashboard; results of $name are not published"; exit 1; }
bench="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["bench"])' "$rm_json")"
repo="$("$PY" -c '
import json,sys
for s in json.load(open(sys.argv[1])):
    if sys.argv[2] in s.get("benches", [s["repo"]]): print(s["repo"]); break
' "$work/dash/sections.json" "$bench")"

# 1. Open UI data -> the benchmark's repo
has_ui=""
if [ -d "$out/ui/data" ] && [ -n "$(ls -A "$out/ui/data" 2>/dev/null)" ]; then
  if [ -z "$repo" ]; then
    echo "::warning::bench '$bench' has no repo in $RESULTS_ORG/dashboard's sections.json, so its Open UI data is not published; add it there (dashboard PUBLISHING.md, section E) to keep future runs' data"
  else
    mkdir -p "$work/ui"
    cp -R "$out/ui/data" "$work/ui/$name"
    # Mask what IBM Vault Radar flags in run data (all false positives so far); exits 1 if a
    # .json no longer parses afterwards.
    "$PY" "$work/dash/scripts/mask_secrets.py" "$work/ui" \
      || { echo "::error::masking the Open UI data of $name failed"; exit 1; }
    if publish_to "$repo" "ci_ui: Open UI data of run $run_id ($slug)" "$work/ui/$name" "ci_ui/$name" "ci_ui/$name"; then
      has_ui="--has-ui"
    else
      echo "::error::failed to push the Open UI data of $name to $RESULTS_ORG/$repo; publishing the record without it"
      ui_failed=1
    fi
  fi
fi

# 2. The record -> the dashboard
rec="$work/$name.json"
"$PY" "$LIB/record.py" build "$out/metrics.jsonl" --runmeta "$rm_json" --steps "$out/steps.jsonl" $has_ui > "$rec" \
  || { echo "::error::record.py build failed for $name"; exit 1; }
"$PY" "$work/dash/scripts/check_records.py" "$rec" \
  || { echo "::error::the record of $name fails the dashboard's check_records.py; not published"; exit 1; }
publish_to dashboard "records: run $run_id ($slug)" "$rec" "records/$name.json" records \
  || { echo "::error::failed to push the record of $name to $RESULTS_ORG/dashboard"; exit 1; }

log "done: https://skillberry-runs.github.io/dashboard/ (the site redeploys in a few minutes)"
exit "${ui_failed:-0}"
