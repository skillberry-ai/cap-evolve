#!/usr/bin/env bash
# fetch_data.sh — clone the two upstream repos this benchmark drives, and merge this
# repo's reward_overlay.yaml onto the upstream eval config, at CI/run time.
#
# Neither upstream repo is vendored: both are public but UNLICENSED
# (github.com/opendatahub-io/rfe-creator, github.com/opendatahub-io/agent-eval-harness),
# so there is no grant to copy their code or their 25 eval cases into this repo. Same
# convention as spreadsheetbench/fetch_data.sh (data fetched, not committed) and the
# parsec local-shadow pattern (ci/benchmarks/parsec/utils/).
#
#   fetch_data.sh [dest_dir]
#
# dest_dir defaults to $CAPEVOLVE_CI_CACHE/rfe-creator-src (or ~/.cache/capevolve-ci/…).
# On success, prints three lines to stdout:
#   RFE_CREATOR_DIR=<path>
#   AGENT_EVAL_HARNESS_DIR=<path>
#   RFE_EVAL_CONFIG=<path to the merged eval config>
set -euo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}"
DEST="${1:-$CACHE/rfe-creator-src}"
mkdir -p "$DEST"

RFE_CREATOR_DIR="$DEST/rfe-creator"
AGENT_EVAL_HARNESS_DIR="$DEST/agent-eval-harness"
EVAL_MERGED="$DEST/eval.merged.yaml"

if [ -d "$RFE_CREATOR_DIR/.git" ]; then
  git -C "$RFE_CREATOR_DIR" fetch --depth 1 origin main -q
  git -C "$RFE_CREATOR_DIR" reset --hard origin/main -q
else
  git clone --depth 1 https://github.com/opendatahub-io/rfe-creator "$RFE_CREATOR_DIR" -q
fi

if [ -d "$AGENT_EVAL_HARNESS_DIR/.git" ]; then
  git -C "$AGENT_EVAL_HARNESS_DIR" fetch --depth 1 origin main -q
  git -C "$AGENT_EVAL_HARNESS_DIR" reset --hard origin/main -q
else
  git clone --depth 1 https://github.com/opendatahub-io/agent-eval-harness "$AGENT_EVAL_HARNESS_DIR" -q
fi

[ -f "$RFE_CREATOR_DIR/eval.yaml" ] || { echo "::error:: $RFE_CREATOR_DIR/eval.yaml not found — upstream layout changed?" >&2; exit 1; }

python3 - "$RFE_CREATOR_DIR/eval.yaml" "$LIB_DIR/../reward_overlay.yaml" "$EVAL_MERGED" <<'PY'
import sys
import yaml

base_path, overlay_path, out_path = sys.argv[1:4]
base = yaml.safe_load(open(base_path)) or {}
overlay = yaml.safe_load(open(overlay_path)) or {}

def deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst

merged = deep_merge(base, overlay)
with open(out_path, "w") as f:
    yaml.safe_dump(merged, f, sort_keys=False)
PY

echo "RFE_CREATOR_DIR=$RFE_CREATOR_DIR"
echo "AGENT_EVAL_HARNESS_DIR=$AGENT_EVAL_HARNESS_DIR"
echo "RFE_EVAL_CONFIG=$EVAL_MERGED"
