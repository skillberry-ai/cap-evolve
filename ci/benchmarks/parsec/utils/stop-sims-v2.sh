#!/usr/bin/env bash
# Tear down the parsec v2 tier's simulators.
#
# Kill every kaegis process recorded in the manifest start-sims-v2.sh wrote, then delete the
# manifest (which is what re-arms start-sims-v2.sh). Leaves the per-task skills-store shadows
# and the sim logs in place for inspection.
#
# Overrides (env vars):
#   PARSEC_V2_WORK — runtime scratch root holding the manifest
#                    (default: <repo>/e2e/parsec/v2 — gitignored; must match the value
#                    start-sims-v2.sh ran with)
#
# Requires: jq.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
REPO=$(cd "$HERE/../../../.." && pwd -P)
V2WORK=${PARSEC_V2_WORK:-$REPO/e2e/parsec/v2}
MANIFEST="$V2WORK/sims-v2.manifest.json"

if [ ! -f "$MANIFEST" ]; then
  echo "no manifest at $MANIFEST — nothing to stop" >&2
  exit 0
fi

killed=0
while read -r pid task_id; do
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    killed=$((killed + 1))
    echo "  killed pid=$pid ($task_id)"
  else
    echo "  pid=$pid ($task_id) already gone"
  fi
done < <(jq -r '.tasks[] | "\(.pid) \(.task_id)"' "$MANIFEST")

# Give kaegis a moment to release ports.
sleep 2

rm -f "$MANIFEST"
echo "stopped $killed processes; manifest removed"
