#!/usr/bin/env bash
# freeze_baseline.sh — capture a task's FROZEN baseline (metrics + seed trajectories)
# into ci/benchmarks/<bench>/<task>/baseline/ for `--reuse-baseline`. Seed capabilities
# are intentionally NOT captured (reconstructed at runtime; keeps Anthropic-licensed
# skillsbench skills out of git). Also appends the recorded metrics to baselines.json.
#
#   freeze_baseline.sh <bench> <task_id> [run_dir] [--no-rollouts]
#
# run_dir defaults to the task's run_full (else run_baseline) under .work.
set -euo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"; [ -x "$PY" ] || PY="python3"
BENCH="${1:?bench}"; TASK="${2:?task}"; shift 2
NO_ROLLOUTS=0; RUN_DIR=""
for a in "$@"; do case "$a" in --no-rollouts) NO_ROLLOUTS=1;; *) RUN_DIR="$a";; esac; done

SAFE="$(echo "$TASK" | tr '/ ' '__')"
WORK="$REPO/ci/benchmarks/.work/$BENCH/$SAFE/.capevolve"
[ -n "$RUN_DIR" ] || { for ts in run_full run_baseline; do [ -d "$WORK/$ts" ] && RUN_DIR="$WORK/$ts" && break; done; }
[ -d "$RUN_DIR" ] || { echo "no run dir for $BENCH/$TASK (looked under $WORK)"; exit 1; }

DST="$REPO/ci/benchmarks/$BENCH/$SAFE/baseline"
rm -rf "$DST"; mkdir -p "$DST"
cp "$RUN_DIR/splits.json" "$RUN_DIR/baseline.json" "$DST/"
if [ "$NO_ROLLOUTS" = 0 ] && [ -d "$RUN_DIR/rollouts/val" ]; then
  mkdir -p "$DST/rollouts/val"
  # only the SEED baseline trajectories (not candidate iterations)
  cp "$RUN_DIR"/rollouts/val/*__seed__*.json "$DST/rollouts/val/" 2>/dev/null || true
fi

# append the recorded baseline metrics to baselines.json
"$PY" - "$BENCH" "$TASK" "$RUN_DIR" "$REPO/ci/benchmarks/baselines.json" <<'PY'
import json,sys,pathlib
bench,task,run_dir,store=sys.argv[1:5]
import os
b=json.loads((pathlib.Path(run_dir)/"baseline.json").read_text())["val"]
rec={"bench":bench,"task":task,"agent":os.environ.get("AGENT_MODEL","aws/gpt-oss-120b"),
     "reward":b.get("reward"),
     "latency_s":b.get("seconds"),"cost_usd":b.get("cost_usd"),"tokens":b.get("tokens")}
p=pathlib.Path(store); data=json.loads(p.read_text()) if p.exists() else {}
data.setdefault(bench,{})[task]=rec
p.write_text(json.dumps(data,indent=2))
print("froze",bench,task,"->",rec)
PY
echo "frozen baseline at $DST"
