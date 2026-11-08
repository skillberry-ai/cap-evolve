# Backend: GLM through Claude Code. Sourced by scripts/offload-review.sh.
#
# A backend defines three functions, and optional ones listed below. Each runs inside the reviewer's worktree.
#   backend_label            one line for the identity table
#   backend_has_session      exit 0 when this worktree has an earlier session to resume
#   backend_run <prompt> <resume:0|1>   run one review; stdout and stderr go to the log
#   backend_cleanup          optional: delete this worktree's sessions (runs after the PR merges)
#   backend_forget_session   optional: drop the session to resume after a run that posted nothing
#
# GLM has no CLI of its own here. The reviewer is plain Claude Code (`claude -p`) pointed at a
# gateway that serves GLM with the Anthropic /v1/messages format, so tools, sessions and resume
# work as they do for Claude.
#
# Required environment (not in this repo, because the gateway and the key are internal):
#   GLM_KEY_FILE   a JSON file {"env": {...}} holding the key, the gateway URL and the model id.
#                  It is read at call time and never copied, so a rotated key works at once.
# Read from that file (field names overridable):
#   GLM_KEY_FIELD  default BENCHMARK_ANTHROPIC_AUTH_TOKEN
#   GLM_URL_FIELD  default BENCHMARK_ANTHROPIC_BASE_URL (the gateway, without /v1)
#   GLM_MODEL_FIELD default BENCHMARK_ANTHROPIC_MODEL
# Optional overrides: GLM_BASE_URL, GLM_MODEL (default rits/zai-org/glm-5-3 if the file has none)
#   OFFLOAD_MAX_TURNS  default 200; GLM has no price in Claude Code's table, so a turn limit is
#                  the spend cap (--max-budget-usd would not count anything)
#
# The key never enters the reviewer's environment. Claude Code reads it through apiKeyHelper at call
# time, so a reviewer that runs `env` in its shell cannot print it into its transcript.
#
# Each reviewer gets its own Claude Code config folder inside its worktree, .glm-cc/. The session
# id is fixed in round 1 and resumed by id in round 2, because two reviewers run at once and
# "latest" could pick the other one's session.

# glm_field <name>: one non-secret field (the URL or the model) from the key file. Never the key.
glm_field() {
  [ -r "${GLM_KEY_FILE:-}" ] || return 0
  python3 -I - "$GLM_KEY_FILE" "$1" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get("env", {}).get(sys.argv[2], ""))
PY
}
glm_model() {
  local m=${GLM_MODEL:-}
  [ -n "$m" ] || m=$(glm_field "${GLM_MODEL_FIELD:-BENCHMARK_ANTHROPIC_MODEL}")
  echo "${m:-rits/zai-org/glm-5-3}"
}
glm_base_url() {
  local u=${GLM_BASE_URL:-}
  [ -n "$u" ] || u=$(glm_field "${GLM_URL_FIELD:-BENCHMARK_ANTHROPIC_BASE_URL}")
  echo "$u"
}
glm_dir() { echo "$(pwd -P)/.glm-cc"; }

backend_label() {
  echo "GLM $(glm_model) via Claude Code $(claude --version 2>/dev/null | cut -d' ' -f1)"
}

backend_has_session() {
  [ -s "$(glm_dir)/session-id" ]
}

# Set up on this machine: Claude Code is installed, and the key file exists with a gateway URL.
# The script skips a backend that is not ready and goes to the next one. The reason goes to
# stdout, and the script prints it: "not set up" alone sent a whole round to Bob unnoticed.
backend_ready() {
  if ! command -v claude >/dev/null; then echo "claude (Claude Code) is not on PATH"; return 1; fi
  if [ -z "${GLM_KEY_FILE:-}" ]; then
    # The common case: the variable is in the shell profile, but this session started before the
    # line was added, so it never saw it.
    # A login and interactive shell reads every profile file (.zprofile and .zshrc, or
    # .bash_profile). A marker, matched anywhere, survives any line the profile prints.
    local login
    login=$(${SHELL:-/bin/sh} -lic 'printf "CGPROBE:%s\n" "${GLM_KEY_FILE:+set}"' 2>/dev/null </dev/null || true)
    if [[ $login == *CGPROBE:set* ]]; then
      echo "GLM_KEY_FILE is set in your shell profile but not in this session, which started before it. Start a new session, or prefix the command with GLM_KEY_FILE=<path>"
    else
      echo "GLM_KEY_FILE is not set (see the GLM setup guide)"
    fi
    return 1
  fi
  if [ ! -r "$GLM_KEY_FILE" ]; then echo "GLM_KEY_FILE names a file that is missing or not readable"; return 1; fi
  if [ -z "$(glm_base_url)" ]; then echo "no gateway URL in the key file (field ${GLM_URL_FIELD:-BENCHMARK_ANTHROPIC_BASE_URL})"; return 1; fi
}

backend_cleanup() {
  local d
  d=$(glm_dir)
  # Guard the rm: the folder must be the one inside this worktree, never an empty or root path.
  [[ $d == */.glm-cc ]] && [ "$d" != "/.glm-cc" ] || { echo "glm cleanup: bad dir $d" >&2; return 1; }
  if [ -d "$d" ]; then rm -rf -- "$d"; fi
}

# backend_forget_session: drop the saved session id, so the next run starts a new session. The
# transcript stays in .glm-cc/ for diagnosis; --cleanup removes it after the PR merges.
backend_forget_session() {
  rm -f -- "$(glm_dir)/session-id"
}

backend_run() {
  local prompt=$1 resume=$2 d m base sess=()
  command -v claude >/dev/null || { echo "glm backend: claude (Claude Code) is not on PATH" >&2; return 1; }
  [ -r "${GLM_KEY_FILE:-}" ] || { echo "glm backend: GLM_KEY_FILE is not set or not readable" >&2; return 1; }
  base=$(glm_base_url)
  [ -n "$base" ] || { echo "glm backend: no gateway URL (GLM_BASE_URL or the key file's URL field)" >&2; return 1; }
  d=$(glm_dir)
  m=$(glm_model)
  mkdir -p "$d"
  chmod 700 "$d"
  # The helper reads the key at call time. It takes the file and the field from argv, so the key
  # file's path is the only secret-adjacent value in the settings file.
  cat > "$d/key_helper.py" <<'PY'
import json, sys
sys.stdout.write(json.load(open(sys.argv[1]))["env"][sys.argv[2]].strip())
PY
  python3 -I - "$d/settings.json" "$d/key_helper.py" "$GLM_KEY_FILE" "${GLM_KEY_FIELD:-BENCHMARK_ANTHROPIC_AUTH_TOKEN}" "$base" "$m" <<'PY'
import json, shlex, sys
out, helper, keyfile, field, base, model = sys.argv[1:7]
cmd = " ".join(shlex.quote(a) for a in ["python3", "-I", helper, keyfile, field])
json.dump({"apiKeyHelper": cmd, "env": {"ANTHROPIC_BASE_URL": base}, "model": model},
          open(out, "w"), indent=1)
PY
  if [ "$resume" = 1 ]; then
    sess=(--resume "$(cat "$d/session-id")")
  else
    # python3 is already required above; uuidgen is not on every Linux box.
    python3 -I -c 'import uuid; print(uuid.uuid4())' > "$d/session-id"
    [ -s "$d/session-id" ] || { echo "glm backend: could not make a session id" >&2; return 1; }
    sess=(--session-id "$(cat "$d/session-id")")
  fi
  # Every model variable names GLM, or Claude Code asks the gateway for a Claude model it does
  # not serve (a background classifier or a subagent).
  local envset=() v
  for v in ANTHROPIC_MODEL ANTHROPIC_DEFAULT_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL \
    ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL ANTHROPIC_DEFAULT_FABLE_MODEL \
    ANTHROPIC_SMALL_FAST_MODEL ANTHROPIC_CUSTOM_MODEL_OPTION CLAUDE_CODE_SUBAGENT_MODEL \
    CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL CLAUDE_CODE_AUTO_MODE_MODEL CLAUDE_CODE_BG_CLASSIFIER_MODEL; do
    envset+=("$v=$m")
  done
  # No inherited key, token or header: the helper is the only credential. A private
  # CLAUDE_CONFIG_DIR keeps the user's own settings (base URL, plugins, hooks) out of the run.
  env -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_CUSTOM_HEADERS \
    CLAUDE_CONFIG_DIR="$d" ANTHROPIC_BASE_URL="$base" "${envset[@]}" \
    claude -p "$(cat "$prompt")" --settings "$d/settings.json" \
      --permission-mode bypassPermissions --max-turns "${OFFLOAD_MAX_TURNS:-200}" "${sess[@]}" < /dev/null
}
