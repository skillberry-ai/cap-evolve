#!/usr/bin/env bash
# Plain-assertion bash tests for resolve_provider.sh — no test framework, just exit-code
# checks, since that's the pattern the rest of ci/benchmarks/lib uses for its .sh files.
set -euo pipefail
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

export IBM_ETE_INT_API_BASE="https://int.example.com"
export IBM_ETE_INT_API_KEY="int-key"
export IBM_ETE_API_BASE="https://ete.example.com"
export IBM_ETE_API_KEY="ete-key"
export IBM_RITS_API_BASE="http://localhost:4000"
export IBM_RITS_API_KEY="rits-key"

# shellcheck source=ci/benchmarks/lib/resolve_provider.sh
. "$LIB_DIR/resolve_provider.sh"

resolve_provider "ibm-ete-int/aws/gpt-oss-120b"
check "ete-int strips whole prefix" "$RESOLVED_MODEL" "aws/gpt-oss-120b"
check "ete-int api_base"            "$RESOLVED_API_BASE" "https://int.example.com"
check "ete-int api_key"             "$RESOLVED_API_KEY" "int-key"
check "ete-int provider tag"        "$RESOLVED_PROVIDER" "ibm-ete-int"

resolve_provider "ibm-ete/glm-4.6"
check "ete strips whole prefix" "$RESOLVED_MODEL" "glm-4.6"
check "ete api_base"            "$RESOLVED_API_BASE" "https://ete.example.com"
check "ete provider tag"        "$RESOLVED_PROVIDER" "ibm-ete"

resolve_provider "ibm-rits/google/gemma-4-31B-it"
check "rits strips only ibm- part" "$RESOLVED_MODEL" "rits/google/gemma-4-31B-it"
check "rits api_base"              "$RESOLVED_API_BASE" "http://localhost:4000"
check "rits provider tag"          "$RESOLVED_PROVIDER" "ibm-rits"

# Unrecognized/bare id must hard-error, not silently pick a default provider.
if err=$(bash -c '. "'"$LIB_DIR"'/resolve_provider.sh"; resolve_provider "aws/gpt-oss-120b"' 2>&1); then
  echo "FAIL: bare id should have exited non-zero"
  fail=1
else
  case "$err" in
    *ibm-ete-int/*ibm-ete/*ibm-rits/*) echo "ok: bare id hard-errors naming all three prefixes" ;;
    *) echo "FAIL: error message doesn't name all three prefixes: $err"; fail=1 ;;
  esac
fi

# Malformed rits id (missing vendor segment) must not silently produce a bad wire id.
resolve_provider "ibm-rits/onlymodel"
check "malformed rits id still gets the rits/ prefix (caller's job to validate vendor/model shape)" \
  "$RESOLVED_MODEL" "rits/onlymodel"
# This is intentionally documented, not "fixed": resolve_provider only strips the CI
# prefix, it does not validate the vendor/model shape of what's left. A malformed
# "ibm-rits/onlymodel" produces "rits/onlymodel" on the wire, which lite-rits itself will
# 400 on with its own diagnostic — see Task 2 Step 5 for why validating shape here would
# just duplicate that check with a worse error message.

# ---- plain model names (model_catalog.txt) --------------------------------------------------
# The real catalog: candidates come back in the catalog's provider order, whatever order the
# ids are written in on the model line.
check "catalog: claude-opus-5 candidates in order ibm-ete-int, ibm-ete" \
  "$(catalog_candidates claude-opus-5 | tr '\n' ' ')" \
  "ibm-ete-int/aws/claude-opus-5 ibm-ete/aws/claude-opus-5 "
check "catalog: gemma-4-31B-it is RITS only (ete-int's gemma-4-31B is the base model)" \
  "$(catalog_candidates gemma-4-31B-it | tr '\n' ' ')" "ibm-rits/google/gemma-4-31B-it "
check "catalog: the default agent keeps its ete-int-only provider" \
  "$(catalog_candidates gpt-oss-120b | tr '\n' ' ')" "ibm-ete-int/aws/gpt-oss-120b "

# A small fake catalog, to test the order rule itself with a model on all three providers.
fake_catalog="$(mktemp)"
cat > "$fake_catalog" <<'CAT'
# comment line
order ibm-rits ibm-ete-int ibm-ete
model triple  ibm-ete/x/triple  ibm-ete-int/x/triple  ibm-rits/v/triple
model eteonly ibm-ete/x/eteonly
CAT
CAPEVOLVE_MODEL_CATALOG="$fake_catalog"
check "order line wins over the order ids are written in" \
  "$(catalog_candidates triple | tr '\n' ' ')" "ibm-rits/v/triple ibm-ete-int/x/triple ibm-ete/x/triple "

check "pin_model: a prefixed id comes back unchanged" "$(pin_model ibm-ete/x/triple)" "ibm-ete/x/triple"
check "pin_model: plain name -> first provider in order with secrets" "$(pin_model triple)" "ibm-rits/v/triple"
check "pin_model: skips a provider whose secrets are unset" \
  "$(IBM_RITS_API_KEY='' pin_model triple)" "ibm-ete-int/x/triple"
check "pin_model: no provider has secrets -> first candidate, so resolve_provider names the secret" \
  "$(IBM_ETE_API_BASE='' pin_model eteonly)" "ibm-ete/x/eteonly"

resolve_provider "triple"
check "resolve_provider accepts a plain name" "$RESOLVED_PROVIDER/$RESOLVED_MODEL" "ibm-rits/rits/v/triple"

if err=$(bash -c 'CAPEVOLVE_MODEL_CATALOG="'"$fake_catalog"'"; . "'"$LIB_DIR"'/resolve_provider.sh"; resolve_provider "nosuchmodel"' 2>&1); then
  echo "FAIL: an unknown plain name should have exited non-zero"; fail=1
else
  case "$err" in
    *"not a plain model name"*) echo "ok: an unknown plain name hard-errors and names the catalog" ;;
    *) echo "FAIL: unexpected error for an unknown plain name: $err"; fail=1 ;;
  esac
fi
rm -f "$fake_catalog"

exit $fail
