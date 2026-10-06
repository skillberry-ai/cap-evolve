#!/usr/bin/env bash
# resolve_provider.sh — map a CI model id to the provider that actually serves it.
#
# Three providers coexist on this runner. An agent_model/optimizer_model id is either a PLAIN
# name from ci/benchmarks/model_catalog.txt (the provider is chosen by the order there — see
# "Plain model names" below), or carries one of these three CI-only prefixes, which pins it:
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
# wire_model <ci-model-id> -> prints the id the PROVIDER actually answers to.
#
# The rewrite ALONE: no credentials, no side effects, so a caller that only needs to know what
# goes on the wire can ask without having the provider's secrets exported. That is exactly the
# entitlement check's situation -- it compares against the gateway's own `GET /models` listing,
# which uses wire ids, and passing it the CI alias made every ibm-ete* model look unserved
# (run 36300445911: "optimizer model 'ibm-ete-int/aws/claude-opus-5' is NOT served by this
# gateway (prefix mismatch)").
#
# resolve_provider DELEGATES here rather than repeating the cases, so the probe and the
# entitlement check can never disagree about what the wire id is.
wire_model() {
  local model="${1:?wire_model: model id required}"
  case "$model" in
    ibm-ete-int/*) printf '%s' "${model#ibm-ete-int/}" ;;
    ibm-ete/*)     printf '%s' "${model#ibm-ete/}" ;;
    # RITS keeps a `rits/` wire prefix: lite-rits's async_pre_call_hook only engages while it is
    # present, and strips it itself to look up the bare vendor/model in its scraped rits.json.
    ibm-rits/*)    printf '%s' "rits/${model#ibm-rits/}" ;;
    *)
      echo "wire_model: '$model' has no recognized provider prefix (expected ibm-ete-int/, ibm-ete/, or ibm-rits/)" >&2
      return 1
      ;;
  esac
}

# ---- Plain model names and the provider order (ci/benchmarks/model_catalog.txt) ----------
#
# A dispatch may also name a model WITHOUT a provider prefix ("claude-opus-5"). Such a plain
# name is looked up in model_catalog.txt, which lists the CI ids that serve it and the order
# providers are tried in (RITS, then ibm-ete-int, then ibm-ete). ci_setup.sh's preflight walks
# that order with live probes and exports the winner as AGENT_MODEL_RESOLVED /
# OPTIMIZER_MODEL_RESOLVED, so every later step sees an ordinary prefixed id.
#
# pin_model below is the probe-free fallback for a caller that runs WITHOUT that preflight (a
# laptop run, or a runner without curl): it takes the first provider in order whose secrets are
# set. It cannot see budgets, so CI never relies on it.
CAPEVOLVE_MODEL_CATALOG="${CAPEVOLVE_MODEL_CATALOG:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/model_catalog.txt}"

# provider_of <ci-model-id> -> "ibm-ete-int" | "ibm-ete" | "ibm-rits"; non-zero for a plain name.
provider_of() {
  case "$1" in
    ibm-ete-int/*) printf '%s\n' ibm-ete-int ;;
    ibm-ete/*)     printf '%s\n' ibm-ete ;;
    ibm-rits/*)    printf '%s\n' ibm-rits ;;
    *) return 1 ;;
  esac
}

# is_pinned <id> — true for a prefixed id, which pins its provider and never falls back.
is_pinned() { provider_of "$1" >/dev/null; }

# provider_has_creds <provider> — true when that provider's IBM_<NAME>_API_BASE/KEY are both set.
provider_has_creds() {
  case "$1" in
    ibm-ete-int) [ -n "${IBM_ETE_INT_API_BASE:-}" ] && [ -n "${IBM_ETE_INT_API_KEY:-}" ] ;;
    ibm-ete)     [ -n "${IBM_ETE_API_BASE:-}" ]     && [ -n "${IBM_ETE_API_KEY:-}" ] ;;
    ibm-rits)    [ -n "${IBM_RITS_API_BASE:-}" ]    && [ -n "${IBM_RITS_API_KEY:-}" ] ;;
    *) return 1 ;;
  esac
}

# catalog_candidates <plain-name> -> the CI ids that serve it, one per line, in provider order.
# Non-zero, with a message on stderr, when the name is not in the catalog.
catalog_candidates() {
  local name="$1" kind rest order="" ids="" p id
  if [ ! -r "$CAPEVOLVE_MODEL_CATALOG" ]; then
    echo "catalog_candidates: model catalog not found at $CAPEVOLVE_MODEL_CATALOG" >&2
    return 1
  fi
  while read -r kind rest; do
    case "$kind" in
      order) order="$rest" ;;
      model)
        # shellcheck disable=SC2086  # deliberate split of "<name> <id> <id> ..."
        set -- $rest
        if [ "${1:-}" = "$name" ]; then shift; ids="$*"; fi
        ;;
    esac
  done < "$CAPEVOLVE_MODEL_CATALOG"
  if [ -z "$ids" ]; then
    echo "'$name' has no recognized provider prefix (expected ibm-ete-int/, ibm-ete/, or ibm-rits/) and is not a plain model name in $CAPEVOLVE_MODEL_CATALOG" >&2
    return 1
  fi
  for p in $order; do
    for id in $ids; do
      [ "$(provider_of "$id" || true)" = "$p" ] && printf '%s\n' "$id"
    done
  done
  return 0
}

# pin_model <id> -> a prefixed CI id. A prefixed id comes back unchanged; a plain name becomes
# its first candidate whose provider has secrets set (or simply its first candidate, so that
# resolve_provider then fails naming the missing secret instead of a vague "no provider").
pin_model() {
  local model="$1" cands c
  if is_pinned "$model"; then printf '%s\n' "$model"; return 0; fi
  cands="$(catalog_candidates "$model")" || return 1
  for c in $cands; do
    if provider_has_creds "$(provider_of "$c")"; then printf '%s\n' "$c"; return 0; fi
  done
  printf '%s\n' "${cands%%$'\n'*}"
}

resolve_provider() {
  local model="${1:?resolve_provider: model id required}"
  if ! is_pinned "$model"; then
    model="$(pin_model "$model")" || { echo "resolve_provider: see the error above" >&2; exit 1; }
  fi
  case "$model" in
    ibm-ete-int/*)
      RESOLVED_MODEL="$(wire_model "$model")"
      RESOLVED_PROVIDER="ibm-ete-int"
      : "${IBM_ETE_INT_API_BASE:?set IBM_ETE_INT_API_BASE (ete-litellm vpc-int gateway)}"
      : "${IBM_ETE_INT_API_KEY:?set IBM_ETE_INT_API_KEY}"
      RESOLVED_API_BASE="$IBM_ETE_INT_API_BASE"
      RESOLVED_API_KEY="$IBM_ETE_INT_API_KEY"
      ;;
    ibm-ete/*)
      RESOLVED_MODEL="$(wire_model "$model")"
      RESOLVED_PROVIDER="ibm-ete"
      : "${IBM_ETE_API_BASE:?set IBM_ETE_API_BASE (ete-litellm vpc gateway)}"
      : "${IBM_ETE_API_KEY:?set IBM_ETE_API_KEY}"
      RESOLVED_API_BASE="$IBM_ETE_API_BASE"
      RESOLVED_API_KEY="$IBM_ETE_API_KEY"
      ;;
    ibm-rits/*)
      RESOLVED_MODEL="$(wire_model "$model")"
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
