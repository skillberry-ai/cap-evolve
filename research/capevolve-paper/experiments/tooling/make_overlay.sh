#!/usr/bin/env bash
# make_overlay.sh <bench> <tier_name> <task_id[,task_id...]> [dataset_variant]
#
# Builds $BENCH/overlay: a tree of SYMLINKS to the campaign repo plus ONE extra, real tier directory
# ci/benchmarks/<bench>/<tier_name>/tasks.json holding only the given task ids. run_suite.sh derives
# REPO from its own location, so running <overlay>/ci/benchmarks/lib/run_suite.sh makes it read this tier and
# write ci/benchmarks/.work/ INSIDE the overlay (not in the repo). The repo itself is never modified.
set -euo pipefail
BENCH_NAME="${1:?bench: spreadsheetbench|tau2}"; TIER="${2:?tier name, e.g. one}"; IDS="${3:?task ids, comma separated}"
SRC="${REPO:-/home/dev/projects2/cap-evolve-campaign}"; OV="${OVERLAY:-/home/dev/projects2/campaign-scratch/bench/overlay}"
rm -rf "$OV"; mkdir -p "$OV/ci/benchmarks"
for e in "$SRC"/* "$SRC"/.[!.]*; do b="$(basename "$e")"; case "$b" in ci|.git|.work|.venv*) continue;; esac; ln -s "$e" "$OV/$b"; done
for e in "$SRC"/ci/*; do b="$(basename "$e")"; [ "$b" = benchmarks ] && continue; ln -s "$e" "$OV/ci/$b"; done
for e in "$SRC"/ci/benchmarks/*; do b="$(basename "$e")"; [ "$b" = "$BENCH_NAME" ] && continue; ln -s "$e" "$OV/ci/benchmarks/$b"; done
mkdir -p "$OV/ci/benchmarks/$BENCH_NAME"
for e in "$SRC/ci/benchmarks/$BENCH_NAME"/*; do ln -s "$e" "$OV/ci/benchmarks/$BENCH_NAME/$(basename "$e")"; done
mkdir -p "$OV/ci/benchmarks/$BENCH_NAME/$TIER"
python3 - "$IDS" > "$OV/ci/benchmarks/$BENCH_NAME/$TIER/tasks.json" <<'PY'
import json, sys
print(json.dumps([{"id": i, "tag": "local-smoke", "agent": "aws/gpt-oss-120b"} for i in sys.argv[1].split(",") if i], indent=1))
PY
echo "overlay ready: $OV  (run: bash $OV/ci/benchmarks/lib/run_suite.sh $BENCH_NAME <out_dir>  with TIER=$TIER)"
