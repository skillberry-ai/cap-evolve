#!/usr/bin/env bash
# Ported from rossoctl/context-guru's .claude/skills/offload-review (Apache-2.0),
# adapted for cap-evolve: default OFFLOAD_MAX_ROUNDS raised from 2 to 3, and the
# prompt files moved under .claude/skills/review-cycles/.
#
# Offload two independent reviews of one PR to an agent tool, in parallel, on this machine.
#
#   scripts/offload-review.sh <pr> [--backend <name>] [--no-fallback] [--live-tests <rules-file>] [--same-head]
#   scripts/offload-review.sh <pr> --cleanup
#
# --backend picks the reviewer tool from scripts/offload-review/backends/<name>.sh.
# The default is $OFFLOAD_BACKEND, else glm (backends/glm.sh lists the environment it needs).
#
# Fallback: when a reviewer's backend is not set up, or it fails before that reviewer posted, the
# next backend in $OFFLOAD_FALLBACK (default "bob claude") runs that reviewer. `claude` is the
# user's own Claude Code, so it is the Anthropic fallback. A reviewer never posts twice: the next
# backend runs only while no review of this reviewer, round and head is on the PR. The marker of
# each review names the backend that wrote it, and in a later round each reviewer starts with the
# backend it used last, so it can resume its session. --no-fallback (or OFFLOAD_FALLBACK="")
# turns this off, for example to compare one backend with another.
#
# Each reviewer gets its own worktree, .claude/worktrees/review-pr<N>-<backend>-r<1|2>. A fixed
# path per reviewer lets round 2 resume that reviewer's own round-1 session, and keeps the two
# reviewers' sessions apart.
#
# --live-tests gives the reviewers permission to run tests on the eval box. Use it only after the
# user approved it. <rules-file> holds the box rules; they are not in this repo, so the caller
# passes them in.
#
# --same-head starts the next round on a head that already has both reviews of its round. Use it
# only when the user asked for it: for example, the reviewers could not run their tests, or the
# author replied to a finding without a code change. The round still counts toward the budget.
#
# Each reviewer has a wall-clock limit, $OFFLOAD_REVIEW_TIMEOUT seconds (default 1800; 0 turns it
# off). A run past it is stopped with its whole process group, and the reviewer then goes to the
# next backend, unless its review is already on the PR. The limit is for a run that never ends: on
# #507 a GLM reviewer repeated one word up to the output limit 4 turns in a row, about 21 minutes
# each. It is not a token limit; the model keeps its full output and thinking budget.
#
# A run that ends without posting a review loses its session: the next round starts fresh, and
# does not resume a session that may be the one that failed.
#
# --cleanup runs after the PR merges or closes. It removes the reviewer worktrees, the backend's
# sessions for them, and the live-test rules file.
#
# Exit codes:
#   0  both reviews are posted (or --cleanup is done)
#   1  a reviewer failed, or the input is wrong
#   2  the round budget is used; only the user can grant more (OFFLOAD_MAX_ROUNDS)
#   3  this head already has both reviews of its round; push the fixes first (or --same-head)
#
# Files for each reviewer, in its worktree:
#   .review-prompt.md  the prompt this script writes for the reviewer
#   .review.md         the review the reviewer writes and posts
#   review.log         the tool's output; this script writes it, the reviewer does not
set -euo pipefail
# A step that fails under `set -e` would otherwise end the script with no message.
trap 'echo "offload-review: line $LINENO failed (exit $?)" >&2' ERR

usage="usage: offload-review.sh <pr> [--backend <name>] [--no-fallback] [--live-tests <rules-file>] [--same-head] | <pr> --cleanup"
pr=${1:?$usage}
shift
backend=${OFFLOAD_BACKEND:-glm}
rules=
cleanup=0
same_head=0
fallback=${OFFLOAD_FALLBACK-bob claude}
while [ $# -gt 0 ]; do
  case $1 in
    --backend) backend=${2:?$usage}; shift 2 ;;
    --live-tests)
      rules=${2:?$usage}; shift 2
      [ -s "$rules" ] || { echo "rules file $rules is empty or missing" >&2; exit 1; } ;;
    --cleanup) cleanup=1; shift ;;
    --same-head) same_head=1; shift ;;
    --no-fallback) fallback=; shift ;;
    *) echo "$usage" >&2; exit 1 ;;
  esac
done

root=$(git rev-parse --show-toplevel)
skill=$root/.claude/skills/review-cycles
# The backends to try, in order: the chosen one, then the fallbacks, each once.
chain=("$backend")
for b in $fallback; do [[ " ${chain[*]} " == *" $b "* ]] || chain+=("$b"); done
for b in "${chain[@]}"; do
  # A plain name only: `--backend ../x` must not source a file from outside backends/.
  [[ $b =~ ^[a-z0-9_-]+$ ]] || { echo "bad backend name: $b" >&2; exit 1; }
  [ -f "$root/scripts/offload-review/backends/$b.sh" ] || { echo "no backend $b in scripts/offload-review/backends" >&2; exit 1; }
  # A subshell, so one backend's functions never stand in for another's.
  # shellcheck source=/dev/null
  ( . "$root/scripts/offload-review/backends/$b.sh"
    for fn in backend_label backend_has_session backend_run; do
      declare -F "$fn" >/dev/null || { echo "backend $b does not define $fn" >&2; exit 1; }
    done ) || exit 1
done

max_rounds=${OFFLOAD_MAX_ROUNDS:-3}
# Worktrees hang off the main checkout, even when this runs inside another worktree.
main=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
me=$(gh api user --jq .login)
[[ $pr =~ ^[0-9]+$ ]] || { echo "bad PR number: $pr" >&2; exit 1; }

if [ "$cleanup" = 1 ]; then
  state=$(gh pr view "$pr" --repo "$repo" --json state --jq .state)
  if [ "$state" = OPEN ] && [ "${OFFLOAD_FORCE:-0}" != 1 ]; then
    echo "PR #$pr is still open. Clean up after it merges or closes (or set OFFLOAD_FORCE=1)." >&2
    exit 1
  fi
  for wt in "$main"/.claude/worktrees/review-pr"$pr"-*-r[12]; do
    [ -d "$wt" ] || continue
    name=${wt##*/}; b=${name#review-pr"$pr"-}; b=${b%-r[12]}
    if [[ $b =~ ^[a-z0-9_-]+$ ]] && [ -f "$root/scripts/offload-review/backends/$b.sh" ]; then
      # A subshell, so one backend's functions do not leak into the next worktree's cleanup.
      # shellcheck source=/dev/null
      ( . "$root/scripts/offload-review/backends/$b.sh"; cd "$wt"
        if declare -F backend_cleanup >/dev/null; then backend_cleanup; fi ) \
        || echo "Backend $b could not clean up its sessions for $wt" >&2
    fi
    # --force: the worktree holds the reviewer's untracked files (.review.md and the rest).
    git -C "$main" worktree remove --force "$wt"
    echo "Removed $wt"
  done
  rm -f "/tmp/offload-review-pr$pr-rules.md"
  exit 0
fi

# Checked once here: a bad value inside a run would fail every backend in turn. It sits after
# --cleanup, which runs no reviewer, and before any reviewer worktree or session is touched.
review_timeout=${OFFLOAD_REVIEW_TIMEOUT:-1800}
[[ $review_timeout =~ ^[0-9]+$ ]] || { echo "OFFLOAD_REVIEW_TIMEOUT must be whole seconds, not '$review_timeout'" >&2; exit 1; }

pr_json=$(gh pr view "$pr" --repo "$repo" --json headRefName,headRefOid,baseRefName)
head_ref=$(jq -r .headRefName <<<"$pr_json")
sha=$(jq -r .headRefOid <<<"$pr_json")
base_ref=$(jq -r .baseRefName <<<"$pr_json")

reviews=$(gh api --paginate "repos/$repo/pulls/$pr/reviews" --jq '.[].body')
# posted <reviewer> <round>: exit 0 when that reviewer posted that round on this head.
posted() { grep -qE "<!-- offload-review reviewer=$1 round=$2 sha=$sha backend=[a-z0-9_-]+ verdict=(approve|blocking)" <<<"$reviews"; }

# The last round is the highest round in any marker, from either reviewer and any backend.
# `|| true`: grep exits 1 on a PR with no reviews yet, and pipefail would end the script.
last=$({ grep -oE '<!-- offload-review reviewer=[12] round=[0-9]+' <<<"$reviews" || true; } \
  | sed -E 's/.*round=//' | sort -n | tail -1)
last=${last:-0}
todo=()
rehead=0 # 1: this round reviews the same head as the round before it
if [ "$last" -gt 0 ] && { posted 1 "$last" || posted 2 "$last"; }; then
  # The last round is on this head. Finish it: run only the reviewer that has not posted.
  round=$last
  for r in 1 2; do posted "$r" "$round" || todo+=("$r"); done
  if [ ${#todo[@]} -eq 0 ]; then
    if [ "$same_head" = 0 ]; then
      echo "Head $sha already has both round-$round reviews. Push the fixes first," \
        "or run with --same-head if the user asked for a round on this head." >&2
      exit 3
    fi
    round=$((last + 1))
    todo=(1 2)
    rehead=1
  fi
else
  round=$((last + 1))
  todo=(1 2)
fi
if [ "$round" -gt "$max_rounds" ]; then
  echo "PR #$pr used its $max_rounds review rounds. Ask the user for more rounds" \
    "(OFFLOAD_MAX_ROUNDS=$((max_rounds + 1))), or let a person decide." >&2
  exit 2
fi

git -C "$main" fetch -q origin "$head_ref" "$base_ref"

wt_of() { echo "$main/.claude/worktrees/review-pr$pr-$1-r$2"; } # <backend> <reviewer>

# ensure_wt <backend> <reviewer>: create that worktree, or reset it to the head. One at a time:
# two `git worktree add` calls at the same time can fail on a git lock file, and with fallback the
# reviewers may need a new worktree at the same moment. The backends' own session folders
# survive the clean, so round 2 can resume.
lockdir="$(git rev-parse --path-format=absolute --git-common-dir)/offload-review-worktree.lock"
ensure_wt() {
  local wt n=0 rc=0
  wt=$(wt_of "$1" "$2")
  until mkdir "$lockdir" 2>/dev/null; do
    n=$((n + 1))
    [ "$n" -lt 600 ] || { echo "The worktree lock $lockdir is held for over 60 s. Remove it if no review is running." >&2; return 1; }
    sleep 0.1
  done
  if [ -d "$wt" ]; then
    git -C "$wt" checkout -q --detach "$sha" && git -C "$wt" clean -qfd -e .glm-cc/ -e .claude-review-session || rc=1
  else
    git -C "$main" worktree add -q --detach "$wt" "$sha" || rc=1
  fi
  rmdir "$lockdir"
  return "$rc"
}

# posted_now <reviewer>: exit 0 when that reviewer's review of this round and head is on the PR,
# from any backend. Read fresh: it decides whether the next backend may run.
# The answer is read whole before grep, not piped: under pipefail, `gh ... | grep -q` fails with
# SIGPIPE when gh writes after grep has matched, and a posted review then reads as missing, so the
# next backend would post a second one. A gh failure counts as posted for the same reason: an
# uncertain answer stops the chain. The final check below still reports a review that is missing.
posted_now() {
  local now
  now=$(gh api --paginate "repos/$repo/pulls/$pr/reviews" --jq '.[].body') \
    || { echo "Reviewer $1: could not read the PR's reviews; not trying another backend." >&2; return 0; }
  grep -qE "<!-- offload-review reviewer=$1 round=$round sha=$sha backend=[a-z0-9_-]+ verdict=(approve|blocking)" <<<"$now"
}

# chain_for <reviewer>: the backends to try for this reviewer. In a later round the backend that
# wrote its last review goes first, so it can resume its own session.
chain_for() {
  local prev b out=()
  prev=$({ grep -oE "<!-- offload-review reviewer=$1 round=[0-9]+ sha=[0-9a-f]+ backend=[a-z0-9_-]+" <<<"$reviews" || true; } \
    | tail -1 | sed -E 's/.*backend=//')
  if [ "$round" -gt 1 ] && [ -n "$prev" ] && [[ " ${chain[*]} " == *" $prev "* ]]; then out=("$prev"); fi
  for b in "${chain[@]}"; do [[ " ${out[*]-} " == *" $b "* ]] || out+=("$b"); done
  echo "${out[@]}"
}

# run_limited <seconds> <marker> <cmd...>: run cmd in its own process group. Past the limit, stop
# the whole group (TERM, then KILL), create <marker> and return 124. The marker, not the exit code,
# says it was stopped: a backend may exit 124 on its own. A plain kill of the backend's pid would
# leave its children (claude -p starts tool processes) running. 0 means no limit.
run_limited() {
  local limit=$1 marker=$2 pid rc=0 t=0
  shift 2
  set -m
  # stdin from /dev/null: a job in its own process group that reads the terminal is stopped
  # (SIGTTIN) and would sit there until the limit.
  "$@" < /dev/null &
  pid=$!
  set +m
  # A stopped review script must not leave the reviewer running in its own group.
  trap 'kill -TERM -- "-$pid" 2>/dev/null || true' INT TERM
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$limit" -gt 0 ] && [ "$t" -ge "$limit" ]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
      sleep 5
      kill -KILL -- "-$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      trap - INT TERM
      : > "$marker"
      return 124
    fi
    sleep 1
    t=$((t + 1))
  done
  wait "$pid" || rc=$?
  trap - INT TERM
  return "$rc"
}

# forget_session <reviewer> <backend>: drop that worktree's saved session after a run that posted
# nothing, so a later round starts fresh instead of resuming it. A backend names its own way with
# backend_forget_session; one without it falls back to backend_cleanup.
forget_session() {
  local wt
  wt=$(wt_of "$2" "$1")
  [ -d "$wt" ] || return 0
  # shellcheck source=/dev/null
  ( . "$root/scripts/offload-review/backends/$2.sh"; cd "$wt"
    if declare -F backend_forget_session >/dev/null; then backend_forget_session
    elif declare -F backend_cleanup >/dev/null; then backend_cleanup; fi ) \
    || echo "Reviewer $1: could not clear the $2 session in $wt" >&2
}

# attempt <reviewer> <backend>: one review by one backend, in that backend's worktree. Exit 4: the
# backend is not set up on this machine, so it was not run; its reason is in $skipdir/<backend>.
# Otherwise the backend's own exit code. The subshell keeps this backend's functions to this attempt.
skipdir=$(mktemp -d)
trap 'rm -rf -- "$skipdir"' EXIT
attempt() {
  local r=$1 b=$2
  (
    # shellcheck source=/dev/null
    . "$root/scripts/offload-review/backends/$b.sh"
    if declare -F backend_ready >/dev/null; then
      why=$(backend_ready 2>/dev/null) || { printf '%s' "${why:-not set up}" > "$skipdir/$b"; exit 4; }
    fi
    ensure_wt "$b" "$r" || exit 1
    wt=$(wt_of "$b" "$r")
    cd "$wt" || exit 1
    mode=fresh resume=0
    live="Live tests are NOT approved. Read the code only."
    if [ "$round" -gt 1 ]; then
      if backend_has_session 2>>review.log; then
        mode=resumed; resume=1
      else
        echo "Reviewer $r: no earlier $b session found; round $round starts fresh." >&2
      fi
    fi

    if [ -n "$rules" ]; then
      live="Live tests ARE approved by the user. Use your own box folder, review-pr$pr-r$r.
Follow every rule below.

$(cat "$rules")"
    fi

    label=$(backend_label)
    base=$(git merge-base "origin/$base_ref" HEAD)
    marker="<!-- offload-review reviewer=$r round=$round sha=$sha backend=$b verdict=<approve|blocking> -->"
    {
      if [ "$mode" = resumed ] && [ "$rehead" = 1 ]; then
        echo "# Re-check, round $round, on the same head"
        echo "Your round-$((round - 1)) review is earlier in this session. The head did not move."
        echo "This round is for what is new on the PR since then: replies to findings, test results,"
        echo "and a working eval box if your earlier tests could not run. Run the tests you could not."
        echo "Follow the same rules and format as before; they are repeated below."
        echo
      elif [ "$mode" = resumed ]; then
        echo "# Re-check, round $round"
        echo "Your round-$((round - 1)) review is earlier in this session. The author pushed fixes."
        echo "Follow the same rules and format as before; they are repeated below."
        echo
      fi
      if [ "$round" -gt 1 ]; then
        # A plain file with placeholders, not echo lines: escaping jq inside echo broke twice.
        sed -e "s|{{PR}}|$pr|g" -e "s|{{REPO}}|$repo|g" -e "s|{{ROUND}}|$round|g" \
          -e "s|{{REVIEWER}}|$r|g" "$skill/review-prompt-later-rounds.md"
        echo
      fi
      cat "$skill/review-prompt.md"
      echo
      echo "## This review"
      echo "- PR: #$pr in $repo, head $sha, base $base."
      echo "- Read the diff with: git diff $base..HEAD"
      echo "- You are reviewer $r of 2, round $round of $max_rounds, context: $mode."
      [ "$rehead" = 0 ] || echo "- The head is the same as in round $((round - 1)). Expect no new commits. That is not a skip."
      echo "- Your folder is $wt. It is a git worktree of the PR head, only for you."
      echo "  Write your review to $wt/.review.md. Do not change any file outside this folder."
      [ "$round" -gt 1 ] || echo "  Do not read the other review-pr* folders in $main/.claude/worktrees."
      echo "- Marker line (line 1 of .review.md): $marker"
      echo "- Identity table (lines 2-4):"
      echo "  | Reviewer | Kind | Started by | Context | Review | Round | Head | Verdict |"
      echo "  |---|---|---|---|---|---|---|---|"
      echo "  | Reviewer $r ($b, user of @$me) | $label | offload-review skill, @$me's session | $mode | $r of 2 | $round of $max_rounds | \`${sha:0:12}\` | **<verdict>** |"
      echo "- Post with: gh pr review $pr --repo $repo --comment --body-file $wt/.review.md"
      echo "- $live"
    } > .review-prompt.md

    # The backend is about to run, so a session it leaves may be the one that failed. Before this
    # point no run happened, and run_reviewer keeps the session.
    : > "$skipdir/ran-$r-$b"
    rc=0
    # >>, not >: backend_has_session above may have written its own error to the log.
    run_limited "$review_timeout" "$skipdir/stopped-$r-$b" backend_run .review-prompt.md "$resume" >> review.log 2>&1 || rc=$?
    if [ -e "$skipdir/stopped-$r-$b" ]; then
      echo "offload-review: stopped after ${review_timeout}s (OFFLOAD_REVIEW_TIMEOUT)" >> review.log
      echo "Reviewer $r: $b ran past ${review_timeout}s and was stopped." >&2
    fi
    exit "$rc"
  )
}

# run_reviewer <reviewer>: try each backend until one has posted this reviewer's review.
run_reviewer() {
  local r=$1 b rc tried=()
  for b in $(chain_for "$r"); do
    rc=0
    attempt "$r" "$b" || rc=$?
    if posted_now "$r"; then
      if [ ${#tried[@]} -gt 0 ]; then
        echo "Reviewer $r: posted with $b. Tried first: ${tried[*]}." >&2
        # A fallback happened in THIS round. A round-2 resume of an earlier fallback backend
        # posts on its first try and leaves no marker, so it is not flagged as a new fallback.
        : > "$skipdir/fellback-$r"
      fi
      return 0
    fi
    if [ "$rc" = 4 ]; then
      tried+=("$b (not set up: $(cat "$skipdir/$b" 2>/dev/null || echo unknown))")
    else
      # Only a run that started can have left a broken session. A failure before it (the worktree,
      # the prompt) keeps the reviewer's earlier session for the next round.
      [ ! -e "$skipdir/ran-$r-$b" ] || forget_session "$r" "$b"
      if [ -e "$skipdir/stopped-$r-$b" ]; then
        tried+=("$b (timed out, no review posted; see $(wt_of "$b" "$r")/review.log)")
      else
        tried+=("$b (exit $rc, no review posted; see $(wt_of "$b" "$r")/review.log)")
      fi
      echo "Reviewer $r: $b did not post a review (exit $rc). Trying the next backend." >&2
    fi
  done
  echo "Reviewer $r: no backend posted a review. Tried: ${tried[*]}." >&2
  return 1
}

# A reviewer may write only in its own worktree. Its worktree is checked below. The checkouts
# where people work are checked here, but only with a warning: the user may edit them during
# the run.
watched=("$main"); [ "$root" = "$main" ] || watched+=("$root")
before=()
for d in "${watched[@]}"; do before+=("$(git -C "$d" status --porcelain)"); done

[ ${#todo[@]} -eq 2 ] || echo "Round $round: reviewer ${todo[*]} has not posted yet; running it only."
pids=()
for r in "${todo[@]}"; do run_reviewer "$r" & pids+=("$!"); done
rc=0
for i in "${!todo[@]}"; do
  wait "${pids[$i]}" || { echo "Reviewer ${todo[$i]} failed; see the messages above" >&2; rc=1; }
done

for i in "${!watched[@]}"; do
  [ "$(git -C "${watched[$i]}" status --porcelain)" = "${before[$i]}" ] \
    || echo "Warning: files changed in ${watched[$i]} during the review. Check that a reviewer did not write there." >&2
done

reviews=$(gh api --paginate "repos/$repo/pulls/$pr/reviews" --jq '.[].body')
used=()
for r in "${todo[@]}"; do
  for b in "${chain[@]}"; do
    wt=$(wt_of "$b" "$r")
    # Only the worktrees this round used: their prompt names this round and head.
    [ -f "$wt/.review-prompt.md" ] && grep -q "reviewer=$r round=$round sha=$sha " "$wt/.review-prompt.md" || continue
    # A reviewer may write only its own files. Anything else is a broken rule. Any .review-in-*.txt
    # is its own: the later-rounds prompt saves the conversation there, and a reviewer that also
    # saves the PR body (.review-in-prbody.txt, #508) breaks no rule. .glm-cc/ and
    # .claude-review-session are the glm and claude backends' own session files.
    extra=$(git -C "$wt" status --porcelain | grep -vE ' (\.review(-prompt)?\.md|\.review-in-[a-z0-9-]+\.txt|review\.log|\.glm-cc/|\.claude-review-session)$' || true)
    [ -z "$extra" ] || { echo "Reviewer $r ($b) changed files:"$'\n'"$extra" >&2; rc=1; }
    [ "$(git -C "$wt" rev-parse HEAD)" = "$sha" ] || { echo "Reviewer $r ($b) moved HEAD" >&2; rc=1; }
  done
  b=$({ grep -oE "<!-- offload-review reviewer=$r round=$round sha=$sha backend=[a-z0-9_-]+ verdict=(approve|blocking)" <<<"$reviews" || true; } \
    | tail -1 | sed -E 's/.*backend=([a-z0-9_-]+).*/\1/')
  if [ -n "$b" ]; then used+=("reviewer $r: $b"); else echo "Reviewer $r did not post its review" >&2; rc=1; fi
done

[ "$rc" -eq 0 ] && echo "Round $round: both reviews are on PR #$pr for ${sha:0:12} (${used[*]})."
# A fallback is quiet by design, so say it last and plainly: a round that went to another backend
# must be a decision the user sees, not a note they miss.
for r in "${todo[@]}"; do
  [ -e "$skipdir/fellback-$r" ] || continue
  echo "Note: a reviewer fell back to another backend in this round. The reason is in the 'Tried first' lines above. Tell the user before you accept this round." >&2
  break
done
exit "$rc"
