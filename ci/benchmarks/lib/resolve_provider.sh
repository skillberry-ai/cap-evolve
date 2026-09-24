#!/usr/bin/env bash
# resolve_provider.sh — map a CI model id to the provider that actually serves it.
#
# Three providers coexist on this runner, and every agent_model/optimizer_model id must
# carry one of these three CI-only prefixes (there is no bare-id fallback: the dropdowns
# are the only source of these ids in normal use, and every dropdown entry carries one):
#
#   * ibm-ete-int/<model>  — the original ete-litellm gateway
#     (https://ete-litellm.ai-models.vpc-int.res.ibm.com), IBM_ETE_INT_API_BASE /
#     IBM_ETE_INT_API_KEY. Strip the prefix; the remainder is the wire model id verbatim.
#   * ibm-ete/<model>      — a second, separate ete-litellm gateway
#     (https://ete-litellm.ai-models.vpc.res.ibm.com; a DIFFERENT auth domain from
#     ibm-ete-int — a key valid on one is unrecognized on the other), IBM_ETE_API_BASE /
#     IBM_ETE_API_KEY. Strip the prefix; the remainder is the wire model id verbatim.
#   * ibm-rits/<vendor>/<model> — RITS via the lite-rits proxy on skillberry-1:4000
#     (IBM_RITS_API_BASE / IBM_RITS_API_KEY). Strip only the "ibm-" part: lite-rits's own
#     custom_callbacks.py (async_pre_call_hook) only engages when the incoming wire model
#     STILL starts with "rits/" — it strips THAT prefix itself to look up the bare
#     "<vendor>/<model>" key in its scraped rits.json. Send it the bare id instead and the
#     hook never fires, so the request falls through to plain LiteLLM routing and fails
#     with "Invalid model name passed in model=...". Verified against the live proxy
#     (skillberry-1:4000): "rits/Qwen/Qwen3-8B" -> HTTP 200; the stripped bare
#     "Qwen/Qwen3-8B" -> HTTP 400 "Invalid model name". So "ibm-rits/<vendor>/<model>" ->
#     wire model "rits/<vendor>/<model>" — the ibm- part is the ONLY thing this strips.
#
# Usage: source this file, then call `resolve_provider "$SOME_MODEL_ID"` and read the
# four RESOLVED_* variables it sets:
#   RESOLVED_MODEL     — the model id to actually send on the wire (prefix stripped/rewritten)
#   RESOLVED_API_BASE  — the provider's api_base
#   RESOLVED_API_KEY   — the provider's api_key
#   RESOLVED_PROVIDER  — "ibm-ete-int" | "ibm-ete" | "ibm-rits", for callers that need to
#                        branch on provider identity instead of re-deriving it from
#                        RESOLVED_API_BASE string comparisons
resolve_provider() {
  local model="${1:?resolve_provider: model id required}"
  case "$model" in
    ibm-ete-int/*)
      RESOLVED_MODEL="${model#ibm-ete-int/}"
      RESOLVED_PROVIDER="ibm-ete-int"
      : "${IBM_ETE_INT_API_BASE:?set IBM_ETE_INT_API_BASE (ete-litellm vpc-int gateway)}"
      : "${IBM_ETE_INT_API_KEY:?set IBM_ETE_INT_API_KEY}"
      RESOLVED_API_BASE="$IBM_ETE_INT_API_BASE"
      RESOLVED_API_KEY="$IBM_ETE_INT_API_KEY"
      ;;
    ibm-ete/*)
      RESOLVED_MODEL="${model#ibm-ete/}"
      RESOLVED_PROVIDER="ibm-ete"
      : "${IBM_ETE_API_BASE:?set IBM_ETE_API_BASE (ete-litellm vpc gateway)}"
      : "${IBM_ETE_API_KEY:?set IBM_ETE_API_KEY}"
      RESOLVED_API_BASE="$IBM_ETE_API_BASE"
      RESOLVED_API_KEY="$IBM_ETE_API_KEY"
      ;;
    ibm-rits/*)
      RESOLVED_MODEL="rits/${model#ibm-rits/}"
      RESOLVED_PROVIDER="ibm-rits"
      : "${IBM_RITS_API_BASE:?set IBM_RITS_API_BASE (skillberry-1 lite-rits proxy, e.g. http://localhost:4000)}"
      : "${IBM_RITS_API_KEY:?set IBM_RITS_API_KEY}"
      RESOLVED_API_BASE="$IBM_RITS_API_BASE"
      RESOLVED_API_KEY="$IBM_RITS_API_KEY"
      ;;
    *)
      echo "resolve_provider: '$model' has no recognized provider prefix (expected ibm-ete-int/, ibm-ete/, or ibm-rits/)" >&2
      exit 1
      ;;
  esac
}
