# Backend: the user's own Claude Code (Anthropic models). Sourced by scripts/offload-review.sh.
#
# A backend defines three functions, and optional ones listed below. Each runs inside the reviewer's worktree.
#   backend_label            one line for the identity table
#   backend_has_session      exit 0 when this worktree has an earlier session to resume
#   backend_run <prompt> <resume:0|1>   run one review; stdout and stderr go to the log
#   backend_ready            optional: exit 0 when the backend is set up on this machine
#   backend_cleanup          optional: delete this worktree's sessions (runs after the PR merges)
#   backend_forget_session   optional: drop the session to resume after a run that posted nothing
#
# This is the last fallback. It runs `claude -p` with the user's own login and settings, so it
# uses whatever endpoint the user's Claude Code uses. Optional environment:
#   OFFLOAD_CLAUDE_MODEL   the model to review with (default: the user's own default model)
#   OFFLOAD_MAX_TURNS      default 200
#
# Sessions live in the user's Claude Code folder, under the worktree's path. The session id is kept
# in .claude-review-session in the worktree, so round 2 resumes this reviewer's own session.

claude_sid_file() { echo "$(pwd -P)/.claude-review-session"; }

backend_label() {
  echo "Claude Code $(claude --version 2>/dev/null | cut -d' ' -f1)${OFFLOAD_CLAUDE_MODEL:+, $OFFLOAD_CLAUDE_MODEL}"
}

backend_ready() {
  command -v claude >/dev/null
}

backend_has_session() {
  [ -s "$(claude_sid_file)" ]
}

backend_cleanup() {
  local f sid dir
  f=$(claude_sid_file)
  [ -s "$f" ] || return 0
  sid=$(cat "$f")
  # Only a session id, never a path: guard the rm.
  [[ $sid =~ ^[0-9a-f-]{36}$ ]] || { echo "claude cleanup: bad session id in $f" >&2; return 1; }
  dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
  [ -d "$dir" ] && find "$dir" -maxdepth 2 -name "$sid.jsonl" -type f -delete
  rm -f -- "$f"
}

# backend_forget_session: drop the saved session, so the next run starts a new one. The session
# lives under ~/.claude/projects, outside the worktree, so --cleanup could not find it once the id
# file names a newer session: remove it here, as backend_cleanup does.
backend_forget_session() {
  backend_cleanup
}

backend_run() {
  local prompt=$1 resume=$2 f sess=() model=()
  f=$(claude_sid_file)
  if [ "$resume" = 1 ]; then
    sess=(--resume "$(cat "$f")")
  else
    python3 -I -c 'import uuid; print(uuid.uuid4())' > "$f"
    [ -s "$f" ] || { echo "claude backend: could not make a session id" >&2; return 1; }
    sess=(--session-id "$(cat "$f")")
  fi
  [ -z "${OFFLOAD_CLAUDE_MODEL:-}" ] || model=(--model "$OFFLOAD_CLAUDE_MODEL")
  claude -p "$(cat "$prompt")" --permission-mode bypassPermissions \
    --max-turns "${OFFLOAD_MAX_TURNS:-200}" "${model[@]}" "${sess[@]}" < /dev/null
}
