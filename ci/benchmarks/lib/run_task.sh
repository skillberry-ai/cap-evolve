#!/usr/bin/env bash
# run_task.sh — drive ONE benchmark task through cap-evolve (dogfoods the adapter templates).
#
#   run_task.sh <bench> <task_id> <mode> [frozen_baseline_dir]
#
#   bench : tau2 | swebench | skillsbench
#   mode  : baseline — baseline eval only (max-iterations 0); cheap SELECTION probe
#           full     — baseline + optimize (3 iters) + finalize (used for task SELECTION
#                      and to GENERATE the frozen baseline)
#           optimize — reuse a frozen baseline (no baseline agent re-run) + optimize + finalize
#                      (used by CI). Requires <frozen_baseline_dir>.
#           check    — scaffold + cap-evolve check only (no model run)
#
# Models (per project standard): agent = aws/gpt-oss-120b, optimizer = claude-code @ claude-opus-4-8.
# Credentials come from env ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN (GitHub secrets in CI).
#
# Prints the cap-evolve summary JSON and, on the last line, "RUN_DIR=<abs path>".
set -euo pipefail

BENCH="${1:?bench (tau2|swebench|skillsbench)}"
TASK_ID="${2:?task id}"
MODE="${3:-full}"
FROZEN="${4:-}"

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
ITER="${ITERATIONS:-3}"                                   # optimizer iterations (CI-configurable; default 3)
AGENT_MODEL="${AGENT_MODEL:-aws/gpt-oss-120b}"            # bare gateway model for the AGENT under test
#   hard tasks use aws/gpt-oss-120b; flip tasks may use a stronger model (e.g. aws/claude-sonnet-5)
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"          # venv with core+litellm(+swebench/datasets)
[ -x "$PY" ] || PY="python3"
export PYTHONPATH="$REPO/core"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"

: "${ANTHROPIC_BASE_URL:?set ANTHROPIC_BASE_URL (IBM gateway)}"
: "${ANTHROPIC_AUTH_TOKEN:?set ANTHROPIC_AUTH_TOKEN}"

# Per-task isolated work dir (gitignored).
WORK="$REPO/ci/benchmarks/.work/$BENCH/$(echo "$TASK_ID" | tr '/ ' '__')"
rm -rf "$WORK"; mkdir -p "$WORK/.capevolve/project/adapters" "$WORK/.capevolve/project/inputs"
PROJ="$WORK/.capevolve/project"
TPL="$REPO/templates/adapters"

cp "$TPL/model_config.py" "$PROJ/adapters/" 2>/dev/null || true

# ---- per-benchmark wiring --------------------------------------------------
case "$BENCH" in
  tau2)
    cp "$TPL/tau2_bench/adapter.py" "$PROJ/adapters/"
    cp -R "$REPO/examples/tau2_airline/seed_capability" "$PROJ/seed_capability"
    CAPS="[system-prompt, tools]"
    cat > "$WORK/.env" <<ENV
MODEL=litellm_proxy/$AGENT_MODEL
LITELLM_PROXY_API_BASE=$ANTHROPIC_BASE_URL
LITELLM_PROXY_API_KEY=$ANTHROPIC_AUTH_TOKEN
MAX_TOKENS=8000
TEMPERATURE=0.0
ENV
    ;;
  swebench)
    cp "$TPL/swe_bench/adapter.py" "$PROJ/adapters/"
    cp -R "$TPL/swe_bench/seed_capability" "$PROJ/seed_capability"
    CAPS="[system-prompt]"
    cat > "$WORK/.env" <<ENV
MODEL=litellm_proxy/$AGENT_MODEL
LITELLM_PROXY_API_BASE=$ANTHROPIC_BASE_URL
LITELLM_PROXY_API_KEY=$ANTHROPIC_AUTH_TOKEN
MAX_TOKENS=8000
TEMPERATURE=0.0
SWEBENCH_INSTANCE_IDS=$TASK_ID
SWEBENCH_MAX_WORKERS=1
SWEBENCH_NAMESPACE=${SWEBENCH_NAMESPACE:-swebench}
ENV
    ;;
  skillsbench)
    cp "$TPL/skillsbench/adapter.py" "$PROJ/adapters/"
    # seed skills extracted from a skillsbench clone (docx/pptx/xlsx/pdf)
    SB_SRC="${SKILLSBENCH_SRC:-$REPO/e2e/skillsbench-src}"
    [ -d "$SB_SRC/tasks" ] || { echo "::error:: skillsbench clone not found at $SB_SRC (set SKILLSBENCH_SRC)"; exit 1; }
    SEED="$PROJ/seed_capability"; mkdir -p "$SEED"
    cp -R "$SB_SRC/tasks/offer-letter-generator/environment/skills/docx" "$SEED/docx"
    cp -R "$SB_SRC/tasks/exceltable-in-ppt/environment/skills/pptx"      "$SEED/pptx"
    cp -R "$SB_SRC/tasks/exceltable-in-ppt/environment/skills/xlsx"      "$SEED/xlsx"
    cp -R "$SB_SRC/tasks/pdf-excel-diff/environment/skills/pdf"          "$SEED/pdf"
    CAPS="[skill-package]"
    cat > "$WORK/.env" <<ENV
ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL
ANTHROPIC_AUTH_TOKEN=$ANTHROPIC_AUTH_TOKEN
SKILLSBENCH_MODEL=$AGENT_MODEL
SKILLSBENCH_TASKS_DIR=$SB_SRC/tasks
SKILLSBENCH_CONCURRENCY=1
ENV
    export SKILLSBENCH_MODEL="$AGENT_MODEL"        # read at adapter import
    export SKILLSBENCH_TASKS_DIR="$SB_SRC/tasks"   # local tasks (avoid remote SHA resolution)
    ;;
  *) echo "unknown bench: $BENCH" >&2; exit 2;;
esac

# single-task no-holdout split (train == val == test)
printf '{"train":["%s"],"val":["%s"],"test":["%s"]}\n' "$TASK_ID" "$TASK_ID" "$TASK_ID" \
  > "$PROJ/inputs/split_ids.json"

cat > "$PROJ/capevolve.yaml" <<YAML
capabilities:       $CAPS
capability_path:    seed_capability
optimizer_skill:    claude-code
optimizer_model:    claude-opus-4-8
algorithm_skill:    hill-climb
algorithm_focus:    all
dataset_source:     adapter
split_ids_file:     "inputs/split_ids.json"
num_trials:         1
gate_mode:          paired
gate_k_se:          1.0
max_iterations:     $ITER
stall:              $ITER
store:              git
YAML

cd "$WORK"
echo ">>> $BENCH task=$TASK_ID mode=$MODE"  >&2
"$PY" -m cap_evolve.cli check .capevolve/project >&2

if [ "$MODE" = "check" ]; then
  echo "RUN_DIR=$WORK/.capevolve/project"; exit 0
fi

RUN_TS="$MODE"
case "$MODE" in
  baseline)
    "$PY" -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml \
          --project .capevolve/project --run-ts "$RUN_TS" --max-iterations 0 ;;
  full)
    "$PY" -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml \
          --project .capevolve/project --run-ts "$RUN_TS" --max-iterations "$ITER" ;;
  optimize)
    [ -n "$FROZEN" ] || { echo "::error:: optimize mode needs a frozen baseline dir" >&2; exit 3; }
    [ -f "$FROZEN/baseline.json" ] || { echo "::error:: no baseline.json in $FROZEN" >&2; exit 3; }
    # Assemble a runtime prior-run dir from the COMMITTED baseline (splits.json +
    # baseline.json + optional rollouts/val) and reconstruct candidates/seed from the
    # freshly-scaffolded seed capability — so seed capabilities (incl. Anthropic-licensed
    # skillsbench skills) are never committed, yet the optimizer still has a seed to edit.
    PRIOR="$WORK/frozen"; rm -rf "$PRIOR"; mkdir -p "$PRIOR/candidates"
    cp "$FROZEN/splits.json" "$FROZEN/baseline.json" "$PRIOR/"
    [ -d "$FROZEN/rollouts" ] && cp -R "$FROZEN/rollouts" "$PRIOR/rollouts"
    cp -R "$PROJ/seed_capability" "$PRIOR/candidates/seed"
    "$PY" -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml \
          --project .capevolve/project --run-ts "$RUN_TS" \
          --reuse-baseline "$PRIOR" --max-iterations "$ITER" ;;
  *) echo "unknown mode: $MODE" >&2; exit 2;;
esac
echo "RUN_DIR=$WORK/.capevolve/run_$RUN_TS"
