#!/usr/bin/env bash
# Plain-assertion bash test for ci_setup.sh's provider choice: select_provider() walking the
# catalog order (ibm-rits, ibm-ete-int, ibm-ete) with check_listed() and probe_model(). The three
# functions are extracted from the live ci_setup.sh, as test_ci_setup_probe_model.sh does, so the
# test runs the shipped code. `curl` is replaced by a shell function that plays each gateway's
# answer, so no network is used. Mirrors test_resolve_provider.sh's no-framework style.
set -uo pipefail  # not -e here; each case runs select_provider under `set -e`, as ci_setup.sh does
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail=0
check() {
  local desc="$1" got="$2" want="$3"
  if [ "$got" != "$want" ]; then
    echo "FAIL: $desc — got '$got', want '$want'"
    fail=1
  else
    echo "ok: $desc"
  fi
}

# shellcheck source=ci/benchmarks/lib/resolve_provider.sh
. "$LIB_DIR/resolve_provider.sh"
for fn in check_listed probe_model select_provider; do
  src="$(awk "/^  $fn\\(\\) \\{/,/^  \\}\$/" "$LIB_DIR/ci_setup.sh")"
  [ -n "$src" ] || { echo "FAIL: could not extract $fn() from ci_setup.sh"; exit 1; }
  eval "$src"
done

CAPEVOLVE_PY="${CAPEVOLVE_PY:-python3}"
export CAPEVOLVE_PROBE_BACKOFFS="0 0" CAPEVOLVE_PROBE_TIMEOUT=1
sleep() { :; }

WORK="$(mktemp -d)"
CALLS="$WORK/calls"
trap 'rm -rf "$WORK"' EXIT

set_all_secrets() {
  export IBM_RITS_API_BASE="http://rits.test" IBM_RITS_API_KEY="rits-key"
  export IBM_ETE_INT_API_BASE="https://int.test" IBM_ETE_INT_API_KEY="int-key"
  export IBM_ETE_API_BASE="https://ext.test" IBM_ETE_API_KEY="ext-key"
}

# Fake gateways. SCN_<TAG> is the completion answer (ok | budget | deny | down | bad) and
# LIST_<TAG> the wire ids its /models lists. Every call is logged to $CALLS as "<TAG> <path>".
curl() {
  local out="" url="" a
  while [ $# -gt 0 ]; do
    a="$1"
    case "$a" in
      -o) out="$2"; shift 2 ;;
      -m|-w|-H|-d) shift 2 ;;
      -*) shift ;;
      *) url="$a"; shift ;;
    esac
  done
  local host="${url#*://}" tag
  host="${host%%/*}"
  case "$host" in int.test) tag=INT ;; ext.test) tag=EXT ;; rits.test) tag=RITS ;; *) tag=UNKNOWN ;; esac
  echo "$tag ${url##*/}" >> "$CALLS"
  if [ "${url##*/}" = "models" ]; then
    local list_var="LIST_$tag" m body=""
    for m in ${!list_var:-}; do body="$body{\"id\":\"$m\"},"; done
    printf '{"data":[%s]}' "${body%,}" > "$out"
    printf 200; return 0
  fi
  local scn_var="SCN_$tag"
  case "${!scn_var:-ok}" in
    ok)     echo '{"choices":[]}' > "$out"; printf 200 ;;
    budget) echo '{"error":"litellm.RateLimitError: Budget has been exceeded!"}' > "$out"; printf 429 ;;
    deny)   echo '{"error":"team not allowed to access model"}' > "$out"; printf 401 ;;
    bad)    echo '{"error":"unsupported parameter"}' > "$out"; printf 400 ;;
    unauth) echo '{"error":"invalid api key"}' > "$out"; printf 401 ;;
    forbid) echo '{"error":"forbidden"}' > "$out"; printf 403 ;;
    gone)   echo '{"error":"model deployment not found"}' > "$out"; printf 404 ;;
    rate)   echo '{"error":"rate limit reached, slow down"}' > "$out"; printf 429 ;;
    down)   : > "$out"; printf 000; return 28 ;;
  esac
}

# run_case <requested> — select_provider for the agent role, under `set -e` as in ci_setup.sh.
# Sets RC, GOT (chosen id or empty), SKIPPED and LOG.
run_case() {
  PF_DIR="$(mktemp -d "$WORK/pf.XXXXXX")"
  : > "$CALLS"
  ( set -e; select_provider agent "$1" ) > "$WORK/log" 2>&1
  RC=$?
  GOT="$(cat "$PF_DIR/agent.model" 2>/dev/null || true)"
  SKIPPED="$(cat "$PF_DIR/agent.skipped" 2>/dev/null || true)"
  LOG="$(cat "$WORK/log")"
}
both_listed() { LIST_INT="aws/claude-opus-5"; LIST_EXT="aws/claude-opus-5"; }

# 1. RITS first, when it serves the model.
set_all_secrets; SCN_RITS=ok
run_case gemma-4-31B-it
check "RITS-only plain name runs on RITS" "$RC:$GOT" "0:ibm-rits/google/gemma-4-31B-it"

# 2. No RITS entry -> ibm-ete-int, and ibm-ete is never called.
set_all_secrets; both_listed; SCN_INT=ok; SCN_EXT=ok
run_case claude-opus-5
check "claude-opus-5 runs on ibm-ete-int when it is healthy" "$RC:$GOT" "0:ibm-ete-int/aws/claude-opus-5"
check "ibm-ete is not contacted when ibm-ete-int works" "$(grep -c '^EXT' "$CALLS")" "0"

# 3. ibm-ete-int over budget -> ibm-ete (the 2026-09-30 case).
set_all_secrets; both_listed; SCN_INT=budget; SCN_EXT=ok
run_case claude-opus-5
check "over budget on ibm-ete-int falls back to ibm-ete" "$RC:$GOT" "0:ibm-ete/aws/claude-opus-5"
check "the skip reason is recorded" "$SKIPPED" "ibm-ete-int:over-budget"

# 4. Not listed on ibm-ete-int -> no completion is even attempted there.
set_all_secrets; LIST_INT="aws/something-else"; LIST_EXT="aws/claude-opus-5"; SCN_INT=ok; SCN_EXT=ok
run_case claude-opus-5
check "a model ibm-ete-int does not list falls back to ibm-ete" "$RC:$GOT:$SKIPPED" "0:ibm-ete/aws/claude-opus-5:ibm-ete-int:not-listed"
check "no completion probe is sent to a provider that does not list the model" "$(grep -c '^INT completions' "$CALLS")" "0"

# 5. Unreachable after retries -> next provider.
set_all_secrets; both_listed; SCN_INT=down; SCN_EXT=ok
run_case claude-opus-5
check "an unreachable ibm-ete-int falls back to ibm-ete" "$RC:$GOT:$SKIPPED" "0:ibm-ete/aws/claude-opus-5:ibm-ete-int:unreachable"

# 6. Not entitled at call time -> next provider.
set_all_secrets; both_listed; SCN_INT=deny; SCN_EXT=ok
run_case claude-opus-5
check "a call-time entitlement refusal falls back" "$RC:$GOT:$SKIPPED" "0:ibm-ete/aws/claude-opus-5:ibm-ete-int:not-entitled"

# 7. A 400 is about our probe, not the provider: stay, do not fall back (same as before).
set_all_secrets; both_listed; SCN_INT=bad; SCN_EXT=ok
run_case claude-opus-5
check "a 400 on ibm-ete-int keeps ibm-ete-int" "$RC:$GOT" "0:ibm-ete-int/aws/claude-opus-5"

# 7b. Any other non-200 answer means this provider cannot serve the model: fall back, and name
# the HTTP code. (A 429 WITHOUT "budget" is a rate limit, not the budget case above.)
for pair in "unauth 401" "forbid 403" "gone 404" "rate 429"; do
  set -- $pair
  set_all_secrets; both_listed; SCN_INT="$1"; SCN_EXT=ok
  run_case claude-opus-5
  check "HTTP $2 on ibm-ete-int falls back to ibm-ete" "$RC:$GOT:$SKIPPED" "0:ibm-ete/aws/claude-opus-5:ibm-ete-int:http-$2"
done

# 7c. A pinned id that gets such an answer continues with a warning, as before this change.
set_all_secrets; both_listed; SCN_INT=gone
run_case ibm-ete-int/aws/claude-opus-5
check "a pinned id with HTTP 404 continues (no fallback for pinned ids)" "$RC:$GOT" "0:ibm-ete-int/aws/claude-opus-5"
check "a pinned id with HTTP 404 never contacts another provider" "$(grep -c '^EXT' "$CALLS")" "0"

# 8. Secrets missing for ibm-ete-int -> skipped without a call.
set_all_secrets; both_listed; SCN_EXT=ok; unset IBM_ETE_INT_API_KEY
run_case claude-opus-5
check "a provider without secrets is skipped" "$RC:$GOT:$SKIPPED" "0:ibm-ete/aws/claude-opus-5:ibm-ete-int:no-secrets"
check "nothing is sent to a provider without secrets" "$(grep -c '^INT' "$CALLS")" "0"

# 9. Every provider fails -> abort, naming each reason.
set_all_secrets; both_listed; SCN_INT=budget; SCN_EXT=budget
run_case claude-opus-5
check "no usable provider aborts" "$RC:$GOT" "1:"
case "$LOG" in
  *"no provider can serve agent model 'claude-opus-5'"*"ibm-ete-int:over-budget ibm-ete:over-budget"*)
    echo "ok: the abort names every provider and reason" ;;
  *) echo "FAIL: abort message does not list the reasons: $LOG"; fail=1 ;;
esac

# 10. A pinned id never falls back.
set_all_secrets; both_listed; SCN_INT=budget; SCN_EXT=ok
run_case ibm-ete-int/aws/claude-opus-5
check "a pinned id over budget aborts" "$RC:$GOT" "1:"
check "a pinned id never contacts another provider" "$(grep -c '^EXT' "$CALLS")" "0"
case "$LOG" in *"pinned to ibm-ete-int, which is OVER BUDGET"*) echo "ok: the pinned abort says why" ;;
  *) echo "FAIL: pinned abort message: $LOG"; fail=1 ;; esac

# 11. A pinned gateway id that does not answer still goes ahead, with a warning (as before).
set_all_secrets; both_listed; SCN_INT=down
run_case ibm-ete-int/aws/claude-opus-5
check "a pinned unreachable gateway id continues" "$RC:$GOT" "0:ibm-ete-int/aws/claude-opus-5"

# 12. A pinned id the gateway does not list aborts with check_models.py's diagnosis.
set_all_secrets; LIST_INT="aws/something-else"; SCN_INT=ok
run_case ibm-ete-int/aws/claude-opus-5
check "a pinned unlisted id aborts" "$RC" "1"

# 13. An unknown plain name aborts before any call.
set_all_secrets
run_case no-such-model
check "an unknown plain name aborts" "$RC:$(wc -l < "$CALLS" | tr -d ' ')" "1:0"

# 14. The whole preflight block, as ci_setup.sh runs it: both roles in parallel, then the
# chosen ids exported and a job-summary table written.
preflight_src="$(awk '/^if command -v curl >\/dev\/null; then$/,/^fi$/' "$LIB_DIR/ci_setup.sh")"
set_all_secrets; LIST_INT="aws/gpt-oss-120b claude-opus-4-8"; LIST_EXT="claude-opus-4-8"
SCN_INT=budget; SCN_EXT=ok
export AGENT_MODEL="gemma-4-31B-it" OPTIMIZER_MODEL="claude-opus-4-8"
export GITHUB_STEP_SUMMARY="$WORK/summary.md"
SCN_RITS=ok
( set -e; eval "$preflight_src"
  echo "$AGENT_MODEL_RESOLVED|$AGENT_PROVIDER|$OPTIMIZER_MODEL_RESOLVED|$OPTIMIZER_PROVIDER|$OPTIMIZER_PROVIDER_SKIPPED" > "$WORK/exported"
) > "$WORK/log" 2>&1
check "preflight block exits 0" "$?" "0"
check "preflight exports both roles' choices" "$(cat "$WORK/exported" 2>/dev/null)" \
  "ibm-rits/google/gemma-4-31B-it|ibm-rits|ibm-ete/claude-opus-4-8|ibm-ete|ibm-ete-int:over-budget"
case "$(cat "$GITHUB_STEP_SUMMARY" 2>/dev/null)" in
  *"| optimizer | \`claude-opus-4-8\` | \`ibm-ete/claude-opus-4-8\` | ibm-ete | ibm-ete-int:over-budget |"*)
    echo "ok: the job summary shows the fallback" ;;
  *) echo "FAIL: job summary: $(cat "$GITHUB_STEP_SUMMARY" 2>/dev/null)"; fail=1 ;;
esac

exit "$fail"
