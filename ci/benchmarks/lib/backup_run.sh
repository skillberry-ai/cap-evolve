#!/usr/bin/env bash
# Keep ONE benchmark leg's raw run data on the runner, outside the workspace, as a capture source
# for the full backup procedure (docs/FULL_BACKUP.md, §5.3(b)).
#
#   backup_run.sh <out_dir> <run_id> <slug>
#     out_dir  the leg's output dir (ci/benchmarks/.work/suite_<tier>_<bench>)
#     run_id   GitHub run id
#     slug     <tier>-<bench>, e.g. smoke-tau2
#
# Writes one capture dir per leg and run attempt (never overwritten):
#   $CI_CAPTURE_ROOT/<run_id>__<slug>/            (attempt 1; attempt N>1: <run_id>__<slug>.a<N>/)
#     <run_id>__<slug>.tar.zst   (.tar.gz if zstd is missing) the run's whole work area:
#                                <out_dir>/ (report, metrics, optimized capability, logs) and
#                                <out_dir>_proj/.capevolve/ (project + run dir: candidates, traces,
#                                rollouts, journal), and <out_dir>_proj.sealed/ when the run sealed
#                                data there
#     members.sha256             sha256 of every readable regular file, taken on the source BEFORE packing,
#                                one `<sha256>  <tar member path>` line each (FULL_BACKUP §5.5:
#                                hashes are taken on the source, because the workspace is gone by
#                                the time anyone captures this)
#     symlinks.txt               every symlink in the work area and its target
#     unreadable.txt             every path the job could not read (not in the archive)
#     backup.json                what this is: run, attempt, bench, tier, who triggered it, runner,
#                                archive sha256 and size, member count and bytes
# and a copy of backup.json at <out_dir>/backup.json, which publish_results.sh puts in the run's
# ci_runs/ folder, so the capture dir can be found from the run's page later.
#
# WHY: the published results (ci_runs/, ci_ui/, the record) are a summary; the raw run data is
# lost when the next job's checkout cleans the workspace. This keeps it until an operator runs
# docs/FULL_BACKUP.md, which treats the capture dir as a SOURCE: it unpacks the archive into
# staging, checks it against backup.json and members.sha256, scans it for secrets, organizes it
# and uploads the organized run folder. This tree is NOT laid out like the backup location and is
# never copied into it as is (FULL_BACKUP §2.6), nor deleted by the backup (FULL_BACKUP Rules).
#
# Best-effort by design (the workflow step is continue-on-error): it never fails a run, and it
# skips (with a warning) when the disk would drop below BACKUP_MIN_FREE_GB.
#
# Environment:
#   CI_CAPTURE_ROOT     default $HOME/capevolve-ci-capture
#   BACKUP_USER         who triggered the run (CI: github.triggering_actor); default $GITHUB_ACTOR, $USER.
#                       Recorded as given; FULL_BACKUP §2.2 maps it to a user id, not this script.
#   BACKUP_REPO         the skillberry-runs repo of the bench (default: from the dashboard's sections.json)
#   PROJECT_WORK        default <out_dir>_proj (as run_suite.sh lays it out)
#   BACKUP_MIN_FREE_GB  default 20
#   GITHUB_RUN_ATTEMPT  the run attempt (default 1)
#   PY                  python for the sections.json lookup and backup.json (default python3)
set -uo pipefail

out="${1:?out_dir}"; run_id="${2:?run_id}"; slug="${3:?slug}"
safe() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }
attempt="${GITHUB_RUN_ATTEMPT:-1}"
name="$(safe "${run_id}__${slug}")"
dirname_="$name"; [ "$attempt" != "1" ] && dirname_="$name.a$(safe "$attempt")"
ROOT="${CI_CAPTURE_ROOT:-$HOME/capevolve-ci-capture}"
PROJECT_WORK="${PROJECT_WORK:-${out}_proj}"
MIN_FREE_GB="${BACKUP_MIN_FREE_GB:-20}"
PY="${PY:-python3}"
SECTIONS_URL="${SECTIONS_URL:-https://raw.githubusercontent.com/skillberry-runs/dashboard/main/sections.json}"

log() { echo "backup_run: $*"; }

# What to archive: the output dir, the project's .capevolve/ (project + run dir) and, when the run
# sealed data, core's default sealed dir <project work>.sealed/ (rundir.py seal()), each as
# (base dir, member path relative to it).
bases=(); rels=()
[ -d "$out" ] && { bases+=("$(dirname "$out")"); rels+=("$(basename "$out")"); }
[ -d "$PROJECT_WORK/.capevolve" ] && { bases+=("$(dirname "$PROJECT_WORK")"); rels+=("$(basename "$PROJECT_WORK")/.capevolve"); }
[ -d "$PROJECT_WORK.sealed" ] && { bases+=("$(dirname "$PROJECT_WORK")"); rels+=("$(basename "$PROJECT_WORK").sealed"); }
[ "${#rels[@]}" -gt 0 ] || { log "no run data at $out or $PROJECT_WORK/.capevolve; nothing to keep"; exit 0; }
parts=(); for i in "${!rels[@]}"; do parts+=(-C "${bases[$i]}" "${rels[$i]}"); done

bench="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("bench",""))' "$out/runmeta.json" 2>/dev/null)"
bench="${bench:-${slug#*-}}"
repo="${BACKUP_REPO:-}"
if [ -z "$repo" ]; then
  repo="$(curl -fsS -m 60 "$SECTIONS_URL" 2>/dev/null | "$PY" -c '
import json,sys
for s in json.load(sys.stdin):
    if sys.argv[1] in s.get("benches", [s["repo"]]): print(s["repo"]); break
' "$bench" 2>/dev/null)"
  [ -n "$repo" ] || { repo="$bench"; log "bench '$bench' not found in the dashboard's sections.json; recording results repo '$repo'"; }
fi
user="${BACKUP_USER:-${GITHUB_ACTOR:-${USER:-unknown}}}"

dst="$ROOT/$dirname_"
if [ -e "$dst" ]; then
  echo "::warning::$dst already exists; it is a capture source and is never overwritten, so the raw run data of this attempt is not kept"
  exit 0
fi
mkdir -p "$ROOT" || { echo "::warning::cannot create $ROOT; raw run data of $name not kept"; exit 0; }

if command -v zstd >/dev/null 2>&1; then ext="tar.zst"; else
  ext="tar.gz"
  echo "::warning::zstd is not installed on runner ${RUNNER_NAME:-?}; keeping $name as .tar.gz instead of .tar.zst (install zstd to fix)"
fi

# Disk check: the uncompressed size is an upper bound for the archive.
need_kb=0
for i in "${!rels[@]}"; do
  need_kb=$(( need_kb + $(du -sk "${bases[$i]}/${rels[$i]}" 2>/dev/null | awk '{print $1+0}') ))
done
avail_kb=$(df -Pk "$ROOT" | awk 'NR==2{print $4}')
if [ $(( avail_kb - need_kb )) -lt $(( MIN_FREE_GB * 1024 * 1024 )) ]; then
  echo "::warning::not keeping $name (~$((need_kb / 1024)) MB): only $((avail_kb / 1024 / 1024)) GB free on the runner's capture disk, below the ${MIN_FREE_GB} GB floor. Capture dirs in $ROOT whose runs a full backup (docs/FULL_BACKUP.md) recorded as uploaded and checked may be removed by the runner's admin to make room."
  exit 0
fi

tmp="$dst.partial"
rm -rf "$tmp"; mkdir -p "$tmp" || { echo "::warning::cannot create $tmp; raw run data of $name not kept"; exit 0; }
fail() { rm -rf "$tmp"; echo "::warning::keeping the raw run data of $name failed ($1); not kept"; exit 0; }

# Source hashes and symlinks first, on the files as they are (FULL_BACKUP §5.5). A file the job
# cannot read (for example one a container wrote as root) does not stop the capture: it is listed
# in unreadable.txt and backup.json, and FULL_BACKUP records it as an `unreadable` gap.
sha256_cmd() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
export -f sha256_cmd
# -readable, -executable and -printf are GNU find primaries (bfs has them too); without them the
# capture may not be kept at all, so say so up front.
find . -maxdepth 0 -readable -executable -printf '' >/dev/null 2>&1 \
  || echo "::warning::find on runner ${RUNNER_NAME:-?} lacks -readable/-executable/-printf (not GNU find); the raw run data of $name may not be kept"
# A directory the job cannot list or enter is pruned, never opened: find would exit 1 on it and,
# with pipefail, drop the whole capture. Pruned dirs and unreadable files go to unreadable.txt.
blocked=( \( -type d \( ! -readable -o ! -executable \) \) )
: > "$tmp/members.sha256"; : > "$tmp/symlinks.txt"; : > "$tmp/unreadable.txt"
for i in "${!rels[@]}"; do
  ( cd "${bases[$i]}" && { find "${rels[$i]}" "${blocked[@]}" -prune -o -type f -readable -print0 2>/dev/null || true; } \
      | LC_ALL=C sort -z | xargs -0 -r bash -c 'sha256_cmd "$@"' _ ) \
    >> "$tmp/members.sha256" || fail "hashing ${rels[$i]}"
  ( cd "${bases[$i]}" && find "${rels[$i]}" "${blocked[@]}" -print -prune -o -type f ! -readable -print ) >> "$tmp/unreadable.txt" 2>/dev/null || true
  ( cd "${bases[$i]}" && find "${rels[$i]}" "${blocked[@]}" -prune -o -type l -printf '%p -> %l\n' ) >> "$tmp/symlinks.txt" 2>/dev/null || true
done
[ -s "$tmp/unreadable.txt" ] && echo "::warning::$(wc -l < "$tmp/unreadable.txt" | tr -d ' ') paths of $name are not readable by the job; kept the rest, listed them in unreadable.txt"
# GNU tar skips what it cannot read (already listed in unreadable.txt) instead of failing; another
# tar has no such option, so there an unreadable path still makes the archive step fail.
tar_opts=(); tar --version 2>/dev/null | grep -q GNU && tar_opts=(--ignore-failed-read)

archive="$tmp/$name.$ext"
if [ "$ext" = "tar.zst" ]; then
  tar "${tar_opts[@]}" -cf - "${parts[@]}" 2>/dev/null | zstd -q -T0 -10 -f -o "$archive"; rc=$?
else
  tar "${tar_opts[@]}" -czf "$archive" "${parts[@]}" 2>/dev/null; rc=$?
fi
{ [ "$rc" -eq 0 ] && [ -s "$archive" ]; } || fail "rc=$rc"

bytes=$(wc -c < "$archive" | tr -d ' ')
sha=$(sha256_cmd "$archive" | awk '{print $1}')
"$PY" - "$tmp/backup.json" "$dst" "$name.$ext" "${RUNNER_NAME:-$(hostname)}" "$bytes" "$sha" \
     "$run_id" "$attempt" "$slug" "$bench" "$repo" "$user" "$tmp/members.sha256" "$tmp/unreadable.txt" <<'PY' || fail "writing backup.json"
import datetime, json, os, sys
(path, capture_dir, archive, runner, size, sha, run_id, attempt, slug, bench, repo, user,
 members, unreadable) = sys.argv[1:]
unreadable = [l for l in open(unreadable, encoding="utf-8", errors="replace").read().splitlines() if l]
lines = [l for l in open(members, encoding="utf-8", errors="replace").read().splitlines() if l.strip()]
tier = slug.split("-", 1)[0]
json.dump({
    "schema": "ci-capture v1",
    "what": "raw run data of one CI benchmark leg, kept on the runner as a capture source for "
            "docs/FULL_BACKUP.md (§5.3(b)); never copy it into the backup location as is",
    "run_id": run_id, "run_attempt": int(attempt) if attempt.isdigit() else attempt,
    "slug": slug, "tier": tier, "bench": bench, "results_repo": repo,
    "triggering_actor": user,
    "runner": runner, "capture_dir": capture_dir,
    "archive": archive, "bytes": int(size), "sha256": sha,
    "members": "members.sha256", "member_count": len(lines),
    "symlinks": "symlinks.txt",
    "unreadable": unreadable,
    "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}, open(path, "w"), indent=2)
PY
mv "$tmp" "$dst" || fail "moving $tmp into place"
cp "$dst/backup.json" "$out/backup.json" 2>/dev/null || log "could not copy backup.json into $out"
log "kept $name -> $dst/$name.$ext ($((bytes / 1024 / 1024)) MB)"
[ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "Raw run data kept on runner \`${RUNNER_NAME:-?}\` for the full backup: \`$dst/$name.$ext\` ($((bytes / 1024 / 1024)) MB, sha256 \`${sha:0:12}…\`)" >> "$GITHUB_STEP_SUMMARY"
exit 0
