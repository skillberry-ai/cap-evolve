#!/usr/bin/env bash
# select_tasks.sh — sweep candidate task ids for a benchmark and print their scores.
#
#   select_tasks.sh <bench> <mode> <id...>
#
#   mode = baseline  → prints "<id> baseline=<r>"          (cheap filter: keep reward==0)
#   mode = full      → prints "<id> baseline=<r> test=<r>" (baseline 0 + optimize 3 iters:
#                       test==1 ⇒ FLIP, test==0 ⇒ HARD)
#
# Results also appended to ci/benchmarks/.work/select_<bench>_<mode>.log
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="${1:?bench}"; MODE="${2:?mode}"; shift 2
LOG="$LIB_DIR/../.work/select_${BENCH}_${MODE}.log"; mkdir -p "$(dirname "$LOG")"

for id in "$@"; do
  out="$(bash "$LIB_DIR/run_task.sh" "$BENCH" "$id" "$MODE" 2>>"$LOG.err" || true)"
  b="$(printf '%s' "$out" | grep -o '"baseline_val": [0-9.]*' | grep -o '[0-9.]*' | head -1)"
  t="$(printf '%s' "$out" | grep -o '"test_reward": [0-9.]*'  | grep -o '[0-9.]*' | head -1)"
  line="$id baseline=${b:-ERR}${t:+ test=$t}"
  echo "$line" | tee -a "$LOG"
done
