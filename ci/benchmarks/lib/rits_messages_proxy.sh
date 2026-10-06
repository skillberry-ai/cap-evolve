# shellcheck shell=bash
# ============================================================================
# A per-job Anthropic Messages API front for a RITS optimizer model.
# ============================================================================
#
# The claude-code optimizer only speaks the Anthropic Messages API (POST /v1/messages). RITS
# serves OpenAI-shaped vLLM endpoints, and the shared lite-rits proxy (skillberry-1:4000) cannot
# bridge the two:
#   * lite-rits's own /v1/messages answers HTTP 500 "'metadata'": its RITS hook reads
#     data['metadata']['headers'], and LiteLLM files /v1/messages headers under
#     'litellm_metadata' instead.
#   * Putting a second LiteLLM in front of lite-rits's /chat/completions fails the same way,
#     because LiteLLM's Anthropic->OpenAI bridge forwards a litellm_metadata field.
# Fixing lite-rits means rebuilding and restarting a container that other jobs use while they
# run. So this starts a private LiteLLM proxy for the job instead. It takes /v1/messages, turns
# it into /chat/completions and calls the model's RITS endpoint directly, the same endpoint
# lite-rits itself would call. It uses the `hosted_vllm/` provider, not `openai/`: for
# `openai/`, LiteLLM 1.82 sends some /v1/messages traffic in the Responses API shape, which
# vLLM rejects with HTTP 400.
#
# Verified by hand on skillberry-1 (2026-10-04): `claude -p` (2.1.220) with
# rits/google/gemma-4-31B-it ran a 3-turn tool task (Read, Write) and exited 0.
#
# Usage (sourced): start_rits_messages_proxy <wire model, e.g. rits/google/gemma-4-31B-it> <RITS key>
# On success it exports ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN pointing at the private proxy,
# plus every Claude Code model alias set to the same model, so no side call (the "small fast"
# model, sub-agents) silently asks for a Claude model the proxy does not serve.
#
# The RITS endpoint URL comes from CAPEVOLVE_RITS_ENDPOINT if set, else from the lite-rits
# container's rits.json (read-only `docker exec`). It is never written into the repository.
# ============================================================================

RITS_PROXY_LITELLM_VERSION="${RITS_PROXY_LITELLM_VERSION:-1.82.1}"
RITS_PROXY_VENV="${RITS_PROXY_VENV:-$HOME/.cache/capevolve-ci/rits-messages-proxy-venv}"

# The bare RITS catalog key for a wire model: "rits/google/gemma-4-31B-it" -> "google/gemma-4-31B-it".
rits_catalog_key() { printf '%s' "${1#rits/}"; }

_rits_endpoint() {
  local key="$1"
  if [ -n "${CAPEVOLVE_RITS_ENDPOINT:-}" ]; then printf '%s' "$CAPEVOLVE_RITS_ENDPOINT"; return 0; fi
  docker exec "${LITE_RITS_CONTAINER:-lite-rits}" python -c \
    "import json,sys; print(json.load(open('rits.json'))[sys.argv[1]])" "$key" 2>/dev/null
}

# Writes the proxy's LiteLLM config to $1. The key lands only in this 0600 file in a 0700
# temp dir, never on a command line.
rits_proxy_config() {
  local out="$1" wire="$2" endpoint="$3" key="$4"
  ( umask 077; cat > "$out" <<YAML
model_list:
  - model_name: "$wire"
    litellm_params:
      model: "hosted_vllm/$(rits_catalog_key "$wire")"
      api_base: "${endpoint%/}/v1"
      api_key: "$key"
      extra_headers:
        RITS_API_KEY: "$key"
litellm_settings:
  drop_params: true
YAML
  )
}

start_rits_messages_proxy() {
  local wire="$1" key="$2" py="${CAPEVOLVE_PY:-python3}"
  local endpoint
  endpoint="$(_rits_endpoint "$(rits_catalog_key "$wire")")"
  if [ -z "$endpoint" ]; then
    echo "::error:: no RITS endpoint for '$wire' (set CAPEVOLVE_RITS_ENDPOINT, or run where the lite-rits container is up)" >&2
    return 1
  fi
  # Own venv, so the proxy's dependencies never touch the agent's venv.
  if ! "$RITS_PROXY_VENV/bin/python" -c "import litellm.proxy.proxy_server" >/dev/null 2>&1 \
     || [ "$("$RITS_PROXY_VENV/bin/pip" show litellm 2>/dev/null | sed -n 's/^Version: //p')" != "$RITS_PROXY_LITELLM_VERSION" ]; then
    echo ">>> rits-messages-proxy: installing litellm[proxy]==$RITS_PROXY_LITELLM_VERSION into $RITS_PROXY_VENV"
    "$py" -m venv "$RITS_PROXY_VENV" && \
      "$RITS_PROXY_VENV/bin/pip" install -q "litellm[proxy]==$RITS_PROXY_LITELLM_VERSION" || {
        echo "::error:: could not install the RITS messages proxy" >&2; return 1; }
  fi
  RITS_PROXY_DIR="$(mktemp -d)"
  rits_proxy_config "$RITS_PROXY_DIR/config.yaml" "$wire" "$endpoint" "$key"
  local port
  port="$("$py" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
  "$RITS_PROXY_VENV/bin/litellm" --config "$RITS_PROXY_DIR/config.yaml" --host 127.0.0.1 --port "$port" \
    > "$RITS_PROXY_DIR/proxy.log" 2>&1 &
  RITS_PROXY_PID=$!
  local _
  for _ in $(seq 1 90); do
    curl -s -o /dev/null "http://127.0.0.1:$port/health/liveliness" && break
    kill -0 "$RITS_PROXY_PID" 2>/dev/null || break
    sleep 1
  done
  # One real /v1/messages round trip, with a long timeout: a cold RITS endpoint has taken ~80 s.
  local code
  code="$(curl -sS -m 240 -o "$RITS_PROXY_DIR/probe.json" -w '%{http_code}' \
    "http://127.0.0.1:$port/v1/messages" -H "x-api-key: capevolve-local" \
    -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d "{\"model\":\"$wire\",\"max_tokens\":16,\"messages\":[{\"role\":\"user\",\"content\":\"Reply OK.\"}]}" \
    2>/dev/null || true)"
  if [ "$code" != "200" ]; then
    echo "::error:: RITS messages proxy probe returned HTTP ${code:-000} for '$wire'" >&2
    head -c 600 "$RITS_PROXY_DIR/probe.json" >&2 2>/dev/null; echo >&2
    grep -iE "error|exception" "$RITS_PROXY_DIR/proxy.log" | grep -v guardrail | tail -5 >&2
    kill "$RITS_PROXY_PID" 2>/dev/null
    return 1
  fi
  echo ">>> rits-messages-proxy: '$wire' served at http://127.0.0.1:$port (/v1/messages probe HTTP 200)"
  export ANTHROPIC_BASE_URL="http://127.0.0.1:$port"
  # The private proxy has no master key, so any token is accepted. The real RITS key stays in
  # its config file.
  export ANTHROPIC_AUTH_TOKEN="capevolve-local"
  export ANTHROPIC_MODEL="$wire" ANTHROPIC_SMALL_FAST_MODEL="$wire"
  export ANTHROPIC_DEFAULT_OPUS_MODEL="$wire" ANTHROPIC_DEFAULT_SONNET_MODEL="$wire" ANTHROPIC_DEFAULT_HAIKU_MODEL="$wire"
  export CLAUDE_CODE_SUBAGENT_MODEL="$wire"
  export RITS_PROXY_PID RITS_PROXY_DIR
}

stop_rits_messages_proxy() {
  [ -n "${RITS_PROXY_PID:-}" ] && kill "$RITS_PROXY_PID" 2>/dev/null
  [ -n "${RITS_PROXY_DIR:-}" ] && rm -rf "$RITS_PROXY_DIR"
  return 0
}
