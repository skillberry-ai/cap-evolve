#!/usr/bin/env bash
# Back up ONE benchmark leg's raw run data on the runner, outside the workspace.
#
#   backup_run.sh <out_dir> <run_id> <slug>
#     out_dir  the leg's output dir (ci/benchmarks/.work/suite_<tier>_<bench>)
#     run_id   GitHub run id
#     slug     <tier>-<bench>, e.g. smoke-tau2
#
# Writes
#   $BACKUP_ROOT/user/<user>/<repo>/<run_id>__<slug>.tar.zst      (.tar.gz if zstd is missing)
# holding the run's whole work area: <out_dir>/ (report, metrics, optimized capability, logs) and
# <out_dir>_proj/.capevolve/ (the project and the run dir: candidates, traces, rollouts, journal).
# Also writes <out_dir>/backup.json saying where the archive is, which publish_results.sh puts in
# the run's ci_runs/ folder, so the archive can be found from the run's page later.
#
# WHY: the published results (ci_runs/, ci_ui/, the record) are a summary; the raw run data is
# lost when the next job's checkout cleans the workspace. Until there is an approved way to send
# it to Box from CI, it is kept on the runner in the SAME layout as the Box folder
# "skillberry-runs-backup", so moving it is a plain copy (by someone with access to the runner).
#
# Best-effort by design (the workflow step is continue-on-error): it never fails a run, and it
# skips (with a warning) when the disk would drop below BACKUP_MIN_FREE_GB.
#
# Environment:
#   BACKUP_ROOT         default $HOME/skillberry-runs-backup
#   BACKUP_USER         who triggered the run (CI: github.triggering_actor); default $GITHUB_ACTOR, $USER
#   BACKUP_REPO         the skillberry-runs repo of the bench (default: from the dashboard's sections.json)
#   PROJECT_WORK        default <out_dir>_proj (as run_suite.sh lays it out)
#   BACKUP_MIN_FREE_GB  default 20
#   PY                  python for the sections.json lookup and backup.json (default python3)
set -uo pipefail

out="${1:?out_dir}"; run_id="${2:?run_id}"; slug="${3:?slug}"
name="${run_id}__${slug}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/skillberry-runs-backup}"
PROJECT_WORK="${PROJECT_WORK:-${out}_proj}"
MIN_FREE_GB="${BACKUP_MIN_FREE_GB:-20}"
PY="${PY:-python3}"
SECTIONS_URL="${SECTIONS_URL:-https://raw.githubusercontent.com/skillberry-runs/dashboard/main/sections.json}"

log() { echo "backup_run: $*"; }
safe() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }

# What to archive: the output dir and the project's .capevolve/ (project + run dir).
parts=()
[ -d "$out" ] && parts+=(-C "$(dirname "$out")" "$(basename "$out")")
[ -d "$PROJECT_WORK/.capevolve" ] && parts+=(-C "$(dirname "$PROJECT_WORK")" "$(basename "$PROJECT_WORK")/.capevolve")
[ "${#parts[@]}" -gt 0 ] || { log "no run data at $out or $PROJECT_WORK/.capevolve; nothing to back up"; exit 0; }

bench="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("bench",""))' "$out/runmeta.json" 2>/dev/null)"
bench="${bench:-${slug#*-}}"
repo="${BACKUP_REPO:-}"
if [ -z "$repo" ]; then
  repo="$(curl -fsS -m 60 "$SECTIONS_URL" 2>/dev/null | "$PY" -c '
import json,sys
for s in json.load(sys.stdin):
    if sys.argv[1] in s.get("benches", [s["repo"]]): print(s["repo"]); break
' "$bench" 2>/dev/null)"
  [ -n "$repo" ] || { repo="$bench"; log "bench '$bench' not found in the dashboard's sections.json; filing it under '$repo'"; }
fi
user="$(safe "${BACKUP_USER:-${GITHUB_ACTOR:-${USER:-unknown}}}")"
repo="$(safe "$repo")"

dir="$BACKUP_ROOT/user/$user/$repo"
mkdir -p "$dir" || { echo "::warning::cannot create $dir; raw run data of $name not backed up"; exit 0; }

if command -v zstd >/dev/null 2>&1; then ext="tar.zst"; else
  ext="tar.gz"
  echo "::warning::zstd is not installed on runner ${RUNNER_NAME:-?}; backing up $name as .tar.gz instead of .tar.zst (install zstd to fix)"
fi
dst="$dir/$name.$ext"

# Disk check: the uncompressed size is an upper bound for the archive.
need_kb=$(du -sk "$out" "$PROJECT_WORK/.capevolve" 2>/dev/null | awk '{s+=$1} END{print s+0}')
avail_kb=$(df -Pk "$dir" | awk 'NR==2{print $4}')
if [ $(( avail_kb - need_kb )) -lt $(( MIN_FREE_GB * 1024 * 1024 )) ]; then
  echo "::warning::not backing up $name (~$((need_kb / 1024)) MB): only $((avail_kb / 1024 / 1024)) GB free on the runner's backup disk, below the ${MIN_FREE_GB} GB floor. Move older archives in $BACKUP_ROOT to Box to make room."
  exit 0
fi

tmp="$dst.partial"
if [ "$ext" = "tar.zst" ]; then
  tar -cf - "${parts[@]}" 2>/dev/null | zstd -q -T0 -10 -f -o "$tmp"; rc=$?
else
  tar -czf "$tmp" "${parts[@]}" 2>/dev/null; rc=$?
fi
if [ "$rc" -ne 0 ] || [ ! -s "$tmp" ]; then
  rm -f "$tmp"
  echo "::warning::archiving the raw run data of $name failed (rc=$rc); not backed up"
  exit 0
fi
mv -f "$tmp" "$dst"

bytes=$(wc -c < "$dst" | tr -d ' ')
sha=$( (sha256sum "$dst" 2>/dev/null || shasum -a 256 "$dst") | awk '{print $1}')
"$PY" - "$out/backup.json" "user/$user/$repo/$name.$ext" "${RUNNER_NAME:-$(hostname)}" "$bytes" "$sha" <<'PY'
import datetime, json, sys
path, archive, runner, size, sha = sys.argv[1:]
json.dump({
    "archive": archive,                       # relative to the skillberry-runs-backup folder (Box)
    "location": f"on runner {runner} in ~/skillberry-runs-backup/, to be moved to Box",
    "bytes": int(size), "sha256": sha,
    "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}, open(path, "w"), indent=2)
PY
log "backed up $name -> $dst ($((bytes / 1024 / 1024)) MB)"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "Raw run data archived on runner \`${RUNNER_NAME:-?}\`: \`~/skillberry-runs-backup/user/$user/$repo/$name.$ext\` ($((bytes / 1024 / 1024)) MB, sha256 \`${sha:0:12}…\`)" >> "$GITHUB_STEP_SUMMARY"
exit 0
