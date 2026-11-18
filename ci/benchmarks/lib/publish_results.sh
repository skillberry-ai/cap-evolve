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
#   ci_runs/<run_id>__<slug>/        -> skillberry-runs/<bench repo>   the run's folder (run_folder.py):
#                                       README, report, metrics, optimized capability, recipe
#   ci_ui/<run_id>__<slug>/          -> skillberry-runs/<bench repo>   the run's "Open UI" data
#   records/<run_id>__<slug>.json    -> skillberry-runs/dashboard      its push deploys the site;
#                                       report_url links the run folder's README
# The bench -> repo map is the dashboard's sections.json ("benches"); masking and record validation
# are the dashboard's own scripts, so CI and hand-publishing (its PUBLISHING.md) apply the same rules.
#
# WHY HERE AND NOT IN A SEPARATE JOB: until 2026-11-18 the bench job uploaded an artifact and a
# GitHub-hosted `aggregate` job published it. After IBM's network change the self-hosted runners
# reach github.com (every connection ~8 s slower) but the artifact service's CreateArtifact call
# times out, so nothing was published. Plain git to github.com still works, so each leg now
# publishes itself. The artifact upload is kept, best-effort, as a download convenience only.
#
# Order: the benchmark repo first (run folder + Open UI data, one commit), then the record, so the
# dashboard deploy the record push triggers already sees them; the record says has_ui and carries
# report_url only if that commit was actually pushed.
# Each push retries on a race (another leg publishing at the same moment) with a fresh clone;
# every leg adds only its own new files, so a retry never conflicts.
#
# Environment:
#   GH_TOKEN             push access to the dashboard and the benchmark repos (in CI:
#                        SKILLBERRY_RUNS_RESULTS_TOKEN); not needed with RESULTS_REMOTE_BASE
#   RESULTS_ORG          default skillberry-runs
#   RESULTS_REMOTE_BASE  tests: <base>/<repo>.git is used for clone AND push (e.g. file:///tmp/r)
#   PY                   python to run the record/mask/check scripts (default python3)
#   PROJECT_WORK         the run's project work dir (default <out_dir>_proj, as run_suite.sh lays it
#                        out): .capevolve/project (recipe) and .capevolve/run_suite (final.json)
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

# Copy paths $4... (files or dirs, relative to stage dir $3 and to the repo root) into a fresh
# clone of repo $1, commit them with message $2, push; retry on races. Only those paths are
# checked out (for Open UI data: the run's own new ci_ui/<name> folder, never all of ci_ui/,
# which runs to GBs).
publish_to() {
  local repo="$1" msg="$2" stage="$3" d="$work/r_$1" branch p; shift 3
  local sparse=()
  for p in "$@"; do if [ -d "$stage/$p" ]; then sparse+=("$p"); else sparse+=("$(dirname "$p")"); fi; done
  for attempt in $(seq 1 "$ATTEMPTS"); do
    if ! sparse_clone "$repo" "$d" "${sparse[@]}"; then
      log "clone of $repo failed (attempt $attempt)"; sleep 5; continue
    fi
    for p in "$@"; do
      mkdir -p "$d/$(dirname "$p")"
      rm -rf "${d:?}/$p"
      cp -R "$stage/$p" "$d/$p"
      git -C "$d" add "$p"
    done
    if git -C "$d" diff --cached --quiet; then log "$repo already has $*"; return 0; fi
    git -C "$d" "${BOT[@]}" commit -q -m "$msg" || return 1
    branch="$(git -C "$d" rev-parse --abbrev-ref HEAD)"   # the repo's default branch
    if git_bounded -C "$d" push -q "$(push_url "$repo")" "HEAD:refs/heads/$branch"; then
      log "pushed $* to $RESULTS_ORG/$repo"; return 0
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
meta() { "$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")' "$rm_json" "$1"; }
bench="$(meta bench)"; tier="$(meta tier)"
# "<repo>|<site>" of the section holding this bench (site: does the repo have section pages?)
section="$("$PY" -c '
import json,sys
for s in json.load(open(sys.argv[1])):
    if sys.argv[2] in s.get("benches", [s["repo"]]): print(s["repo"] + "|" + str(s.get("site", True)).lower()); break
' "$work/dash/sections.json" "$bench")"
repo="${section%%|*}"; site="${section#*|}"

# 1. The run's folder and its Open UI data -> the benchmark's repo, in one commit:
#      ci_runs/<name>/   README, report, metrics, the optimized capability, the recipe (run_folder.py)
#      ci_ui/<name>/     the Open UI data (export_static output)
has_ui=""; report_url=""
if [ -z "$repo" ]; then
  echo "::warning::bench '$bench' has no repo in $RESULTS_ORG/dashboard's sections.json, so its run folder and Open UI data are not published (only its row); add it there (dashboard PUBLISHING.md, section E) to keep future runs' data"
else
  stage="$work/stage"; paths=()
  ui_flag=()
  if [ -d "$out/ui/data" ] && [ -n "$(ls -A "$out/ui/data" 2>/dev/null)" ]; then
    mkdir -p "$stage/ci_ui"
    cp -R "$out/ui/data" "$stage/ci_ui/$name"
    paths+=("ci_ui/$name"); ui_flag=(--has-ui)
  fi
  proj_work="${PROJECT_WORK:-${out}_proj}"
  "$PY" "$LIB/run_folder.py" "$out" "$stage/ci_runs/$name" --name "$name" --repo "$repo" ${ui_flag[@]+"${ui_flag[@]}"} \
      --project "$proj_work/.capevolve/project" --run-dir "$proj_work/.capevolve/run_suite" \
      --tier-dir "$LIB/../$bench/$tier" \
    && paths+=("ci_runs/$name") \
    || echo "::warning::run_folder.py failed for $name; publishing without its run folder"
  # Mask what IBM Vault Radar flags in run data (all false positives so far); exits 1 if a
  # .json no longer parses afterwards.
  if [ "${#paths[@]}" -gt 0 ]; then
    "$PY" "$work/dash/scripts/mask_secrets.py" "$stage" \
      || { echo "::error::masking the run data of $name failed"; exit 1; }
    if publish_to "$repo" "run $run_id ($slug): ci_runs/ folder and Open UI data" "$stage" "${paths[@]}"; then
      [ "${#ui_flag[@]}" -gt 0 ] && has_ui="--has-ui"
      if [ -d "$stage/ci_runs/$name" ]; then
        if [ "$site" = "true" ]; then report_url="https://skillberry-runs.github.io/dashboard/$repo/ci_runs/$name/README.html"
        else report_url="https://github.com/$RESULTS_ORG/$repo/tree/main/ci_runs/$name"; fi
      fi
    else
      echo "::error::failed to push the run folder and Open UI data of $name to $RESULTS_ORG/$repo; publishing the record without them"
      ui_failed=1
    fi
  fi
fi

# 2. The record -> the dashboard
mkdir -p "$work/rec/records"
rec="$work/rec/records/$name.json"
"$PY" "$LIB/record.py" build "$out/metrics.jsonl" --runmeta "$rm_json" --steps "$out/steps.jsonl" $has_ui \
    ${report_url:+--report-url "$report_url"} > "$rec" \
  || { echo "::error::record.py build failed for $name"; exit 1; }
"$PY" "$work/dash/scripts/check_records.py" "$rec" \
  || { echo "::error::the record of $name fails the dashboard's check_records.py; not published"; exit 1; }
publish_to dashboard "records: run $run_id ($slug)" "$work/rec" "records/$name.json" \
  || { echo "::error::failed to push the record of $name to $RESULTS_ORG/dashboard"; exit 1; }

log "done: https://skillberry-runs.github.io/dashboard/ (the site redeploys in a few minutes)"
exit "${ui_failed:-0}"
