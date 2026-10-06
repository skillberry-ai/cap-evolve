#!/usr/bin/env bash
# Plain-assertion bash test for ci_setup.sh's probe_model(), extracted from the live file so
# the test tracks the real function body rather than a hand-copied duplicate. Mirrors
# test_resolve_provider.sh's no-framework style.
#
# probe_model's ibm-ete-int/* and ibm-ete/* case arms each guard against their own
# IBM_<NAME>_API_BASE/KEY being unset before calling resolve_provider (which would otherwise
# hard-`:?`-abort the whole script under `set -uo pipefail`, with nothing to catch it) — see
# the comment above probe_model's case statement in ci_setup.sh. The ibm-rits/* arm must have
# the same guard: a local/laptop run of an ibm-ete-int-only dispatch, with IBM_RITS_API_BASE/
# KEY simply not exported, must warn-and-skip that role's probe, not crash the script.
set -uo pipefail  # not -e: we want to capture probe_model's own exit status, not die with it
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

# Extract the real probe_model() body out of ci_setup.sh (not a hand-copied duplicate) and
# source it, so the test exercises the actual shipped code.
probe_model_src="$(awk '/^  probe_model\(\) \{/,/^  \}$/' "$LIB_DIR/ci_setup.sh")"
eval "$probe_model_src"

export IBM_ETE_INT_API_BASE="https://int.example.com"
export IBM_ETE_INT_API_KEY="int-key"
export IBM_ETE_API_BASE="https://ete.example.com"
export IBM_ETE_API_KEY="ete-key"
unset IBM_RITS_API_BASE IBM_RITS_API_KEY

out="$(probe_model optimizer "ibm-rits/google/gemma-4-31B-it" 2>&1)"
code=$?
check "ibm-rits probe with no IBM_RITS_API_BASE/KEY exits 0 (warn-and-skip, not a crash)" "$code" "0"
case "$out" in
  *"IBM_RITS_API_BASE"*"skipping"*) echo "ok: warns and names the missing var" ;;
  *) echo "FAIL: expected a skip warning naming IBM_RITS_API_BASE, got: $out"; fail=1 ;;
esac

exit "$fail"
