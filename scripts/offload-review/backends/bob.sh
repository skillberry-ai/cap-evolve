# Backend: IBM Bob Shell. Sourced by scripts/offload-review.sh.
#
# A backend defines three functions, and optional ones listed below. Each runs inside the reviewer's worktree.
#   backend_label            one line for the identity table
#   backend_has_session      exit 0 when this worktree has an earlier session to resume
#   backend_run <prompt> <resume:0|1>   run one review; stdout and stderr go to the log
#   backend_cleanup          optional: delete this worktree's sessions (runs after the PR merges)
#
# Bob keys its sessions by project path (sha256 of the real path under ~/.bob/tmp), so each
# reviewer's fixed worktree path keeps its own session list.

backend_label() {
  echo "IBM Bob Shell $(bob --version)"
}

# Set up on this machine: the bob command exists. A login problem shows as a failed run.
backend_ready() {
  command -v bob >/dev/null
}

backend_has_session() {
  local out
  # A Bob error is not "no session": say so, so a lost round-1 context is visible.
  out=$(bob --list-sessions 2>&1) || { echo "bob --list-sessions failed: $out" >&2; return 1; }
  grep -q '^ *1\.' <<<"$out"
}

backend_cleanup() {
  local wt hash dir
  wt=$(pwd -P)
  if command -v sha256sum >/dev/null; then
    hash=$(printf '%s' "$wt" | sha256sum | cut -d' ' -f1)
  else
    hash=$(printf '%s' "$wt" | shasum -a 256 | cut -d' ' -f1)
  fi
  # Guard the rm: an empty HOME or hash must never turn this into rm -rf ~/.bob/tmp/.
  [ -n "$HOME" ] && [[ $hash =~ ^[0-9a-f]{64}$ ]] || { echo "bob cleanup: no hash for $wt" >&2; return 1; }
  dir=$HOME/.bob/tmp/$hash
  if [ -d "$dir" ]; then rm -rf -- "$dir"; fi
}

backend_run() {
  local prompt=$1 resume=()
  [ "$2" = 1 ] && resume=(--resume latest)
  # -p, not a positional prompt: Bob 1.0.3 exits 1 on --resume plus a positional prompt.
  bob --accept-license --trust --yolo --max-coins "${OFFLOAD_MAX_COINS:-10}" \
    "${resume[@]}" -p "$(cat "$prompt")"
}
