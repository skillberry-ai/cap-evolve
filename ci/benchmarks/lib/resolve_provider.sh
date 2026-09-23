#!/usr/bin/env bash
# resolve_provider.sh — map a CI model id to the provider that actually serves it.
#
# Two providers coexist on this runner:
#   * the ETE gateway   (ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN) — the existing
#     default for every non-"rits/" model id in benchmarks.yml's dropdowns.
#   * RITS via the lite-rits proxy on skillberry-1:4000 (RITS_API_BASE / RITS_API_KEY) —
#     reached only through a "rits/<vendor>/<model>" id. lite-rits is a SEPARATE LiteLLM
#     deployment that talks directly to IBM RITS's own API; it is unrelated to the
#     ete-litellm gateway's own (also "rits/"-prefixed) vendor-catalog namespace, which
#     this repo used to route the single legacy "rits/google/gemma-4-31B" entry through.
#
# lite-rits's own custom_callbacks.py (async_pre_call_hook) is what actually recognizes
# RITS models: it only engages when the incoming wire model STILL starts with "rits/" —
# it strips that prefix itself to look up the bare "<vendor>/<model>" key in its scraped
# rits.json (e.g. "rits/google/gemma-4-31B-it" -> looks up "google/gemma-4-31B-it"). Send
# it the bare id instead and lite-rits's hook never fires, so the request falls through to
# plain LiteLLM routing and fails with "Invalid model name passed in model=...". So the
# CI-only "rits/" dropdown prefix and lite-rits's own required prefix are the SAME string —
# do not strip it before the id is sent as the wire model. Verified against the live proxy
# (skillberry-1:4000) 2026-09-23: "rits/Qwen/Qwen3-8B" -> HTTP 200; the stripped bare
# "Qwen/Qwen3-8B" -> HTTP 400 "Invalid model name".
#
# Usage: source this file, then call `resolve_provider "$SOME_MODEL_ID"` and read the
# three RESOLVED_* variables it sets:
#   RESOLVED_MODEL     — the model id to actually send on the wire
#   RESOLVED_API_BASE  — the provider's api_base
#   RESOLVED_API_KEY   — the provider's api_key
resolve_provider() {
  local model="${1:?resolve_provider: model id required}"
  case "$model" in
    rits/*)
      RESOLVED_MODEL="$model"
      : "${RITS_API_BASE:?set RITS_API_BASE (skillberry-1 lite-rits proxy, e.g. http://localhost:4000)}"
      : "${RITS_API_KEY:?set RITS_API_KEY (RITS API key)}"
      RESOLVED_API_BASE="$RITS_API_BASE"
      RESOLVED_API_KEY="$RITS_API_KEY"
      ;;
    *)
      RESOLVED_MODEL="$model"
      : "${ANTHROPIC_BASE_URL:?set ANTHROPIC_BASE_URL (IBM ETE gateway)}"
      : "${ANTHROPIC_AUTH_TOKEN:?set ANTHROPIC_AUTH_TOKEN}"
      RESOLVED_API_BASE="$ANTHROPIC_BASE_URL"
      RESOLVED_API_KEY="$ANTHROPIC_AUTH_TOKEN"
      ;;
  esac
}
