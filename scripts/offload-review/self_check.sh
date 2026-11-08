#!/usr/bin/env bash
# Smoke test for offload-review.sh and its backends — no network, no real PR.
# Run from anywhere inside the repo: scripts/offload-review/self_check.sh
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
fail=0

check() { # <name> <expected-rc> <cmd...>
  local name=$1 want=$2 rc=0
  shift 2
  "$@" >/tmp/offload-review-selfcheck.out 2>&1 || rc=$?
  if [ "$rc" != "$want" ]; then
    echo "FAIL $name: expected exit $want, got $rc" >&2
    cat /tmp/offload-review-selfcheck.out >&2
    fail=1
  else
    echo "ok   $name"
  fi
}

# No PR argument -> usage error, exit 1.
check "no args" 1 scripts/offload-review.sh

# A bad backend name must be rejected before it ever runs anything.
check "bad backend name" 1 scripts/offload-review.sh 1 --backend '../evil'

# Every shipped backend must define the three required functions.
for b in scripts/offload-review/backends/*.sh; do
  name=$(basename "$b" .sh)
  (
    # shellcheck source=/dev/null
    . "$b"
    for fn in backend_label backend_has_session backend_run; do
      declare -F "$fn" >/dev/null || { echo "backend $name missing $fn" >&2; exit 1; }
    done
  ) && echo "ok   backend $name defines the required functions" \
    || { echo "FAIL backend $name" >&2; fail=1; }
done

bash -n scripts/offload-review.sh && echo "ok   offload-review.sh parses" \
  || { echo "FAIL offload-review.sh syntax" >&2; fail=1; }
for b in scripts/offload-review/backends/*.sh; do
  bash -n "$b" && echo "ok   $(basename "$b") parses" \
    || { echo "FAIL $(basename "$b") syntax" >&2; fail=1; }
done

rm -f /tmp/offload-review-selfcheck.out
exit "$fail"
