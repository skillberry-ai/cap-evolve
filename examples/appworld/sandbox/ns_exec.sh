#!/usr/bin/env bash
# Namespace isolation for one optimizer call (README: Isolation), used by sandbox/claude when
# AW_ISOLATION=namespace: the fallback for hosts where Claude Code's built-in sandbox (bubblewrap)
# cannot start, e.g. containers whose /dev/null is bound from the host.
#
# Runs the real claude CLI in a private mount namespace where $AW_EVAL is an empty tmpfs, except for
# an allowlist bound back in: read-only tools and docs, and the optimizer's own working directory
# (read-write). Other places that may hold task answers are covered too: other sessions'
# transcripts (~/.claude/projects, replaced by a per-run transcript dir that the isolation scan
# reads), the machine's claude temp dir, the secrets file, and any $AW_NS_HIDE dirs. The call runs in
# a nested user namespace as a normal user, so it cannot unmount any of this.
#   ns_exec.sh REAL_CLAUDE [claude args...]
set -euo pipefail

REAL_CLAUDE="${1:?real claude path}"; shift
# Both resolved, so a symlinked AW_EVAL compares equal to the working dir's physical path.
AW="$(readlink -f "${AW_EVAL:-/tmp/aw_eval}")"
WORK="$(pwd -P)"
# Read-only allowlist inside $AW (relative paths). Only AppWorld's src/ and experiments/ are needed by
# the venv's editable installs; NOT the whole clone: appworld/generate holds the task generators,
# i.e. the solution and evaluation logic of every train/dev scenario (README: Isolation).
ALLOW_RO="${AW_NS_ALLOW_RO:-venv-aw appworld/src appworld/experiments reference lint_cache.json}"
REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../../.." && pwd)"
HIDE="${AW_NS_HIDE:-}"                                                     # extra dirs to cover (space-separated)
HIDE_FILES="${AW_NS_HIDE_FILES:-${AW_SECRETS_FILE:-$REPO/.env}}"          # covered with an empty file
# Claude Code permission rules (deny Read/Grep on the answer paths), added to every call when set.
SETTINGS="${AW_CLAUDE_SETTINGS:-}"
TRANSCRIPTS="${AW_NS_TRANSCRIPTS:-$AW/runs/optimizer_transcripts}"
LOG="${AW_NS_LOG:-$AW/progress/optimizer_guard.log}"
UID_="$(id -u)"; GID_="$(id -g)"

# The working dir is bound read-write: it must be a proper subdirectory of $AW, never $AW itself
# (that would bind root_opt and every other run back in).
case "$WORK" in
  "$AW") echo "claude shim: working dir is $AW itself; refusing to bind all of it read-write" >&2; exit 97 ;;
  "$AW"/*) ;;
  *) echo "claude shim: working dir $WORK is outside $AW; refusing to run unisolated" >&2; exit 97 ;;
esac
mkdir -p "$TRANSCRIPTS" "$(dirname "$LOG")"
STAGE="$(mktemp -d /tmp/aw_ns_stage.XXXXXX)"
EMPTY="$(mktemp -d /tmp/aw_ns_empty.XXXXXX)"
CTMP="$(mktemp -d /tmp/aw_ns_ctmp.XXXXXX)"; : > "$CTMP/.empty"
INNER="$(mktemp /tmp/aw_ns_inner.XXXXXX.sh)"
trap 'rmdir "$STAGE" "$EMPTY" 2>/dev/null || true; rm -rf "$CTMP" "$INNER"' EXIT

cat > "$INNER" <<'EOF'
set -euo pipefail
# runs as namespace-root in a private mount namespace; args: the claude arguments
mount --bind "$AW" "$STAGE"
mount -t tmpfs -o mode=755 tmpfs "$AW"
for item in $ALLOW_RO; do
  [ -e "$STAGE/$item" ] || continue
  if [ -d "$STAGE/$item" ]; then mkdir -p "$AW/$item"; else mkdir -p "$(dirname "$AW/$item")"; : > "$AW/$item"; fi
  mount --bind "$STAGE/$item" "$AW/$item"
  mount -o remount,bind,ro "$AW/$item"
done
rel="${WORK#"$AW"/}"
case "$rel" in ""|/*) echo "claude shim: bad working dir $WORK under $AW" >&2; exit 97 ;; esac
mkdir -p "$AW/$rel"
mount --bind "$STAGE/$rel" "$AW/$rel"
# the transcript dir may live under $AW, which is covered now: bind it from the staged view
case "$TRANSCRIPTS/" in "$AW"/*) TSRC="$STAGE/${TRANSCRIPTS#"$AW"/}" ;; *) TSRC="$TRANSCRIPTS" ;; esac
[ -d "$HOME/.claude/projects" ] && mount --bind "$TSRC" "$HOME/.claude/projects"
umount -l "$STAGE"
for d in $HIDE; do [ -d "$d" ] && mount --bind "$EMPTY" "$d"; done
for f in $HIDE_FILES; do [ -f "$f" ] && mount --bind "$CTMP/.empty" "$f"; done
[ -d "/tmp/claude-$UID_" ] && mount --bind "$CTMP" "/tmp/claude-$UID_"
cd "$WORK"
exec unshare -U --map-user="$UID_" --map-group="$GID_" "$REAL_CLAUDE" "$@"
EOF

# Pass the settings inline: the file itself may sit in a path the call cannot see.
SETTINGS_JSON=""; [ -n "$SETTINGS" ] && SETTINGS_JSON="$(cat "$SETTINGS")"
echo "$(date -u +%FT%TZ) | guard | namespace call start (pid $$, work $WORK, settings ${SETTINGS:-none})" >> "$LOG"
set +e
AW="$AW" STAGE="$STAGE" EMPTY="$EMPTY" CTMP="$CTMP" WORK="$WORK" ALLOW_RO="$ALLOW_RO" HIDE="$HIDE" HIDE_FILES="$HIDE_FILES" \
  TRANSCRIPTS="$TRANSCRIPTS" REAL_CLAUDE="$REAL_CLAUDE" UID_="$UID_" GID_="$GID_" \
  unshare -rm --propagation private bash "$INNER" ${SETTINGS_JSON:+--settings "$SETTINGS_JSON"} "$@"
rc=$?
set -e
echo "$(date -u +%FT%TZ) | guard | namespace call end (pid $$, exit $rc)" >> "$LOG"
exit $rc
