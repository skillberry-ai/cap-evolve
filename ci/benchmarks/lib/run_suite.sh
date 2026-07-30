#!/usr/bin/env bash
# run_suite.sh — optimize ALL of a tier's tasks TOGETHER in ONE optimization run.
#
#   run_suite.sh <bench> [out_dir]
#
# NOT task-by-task. The optimizer sees EVERY failing task each iteration and proposes one
# edit to improve across all of them. Split is a NO-HOLDOUT FIT: train == val == test ==
# all tier tasks — baseline and optimized are both measured on the same tasks, so the
# headline is a TRAIN-FIT number (how well the optimizer fits the tasks), NOT a
# generalization claim. One optimization = ITERATIONS opus passes total (not × #tasks).
#
# Reads ci/benchmarks/<bench>/<TIER>/tasks.json. Writes <out_dir>/{metrics.jsonl, steps.jsonl, report.md,
# optimized/}. Runs on the self-hosted runner (VPC gateway); dogfoods the adapter templates.
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
BENCH="${1:?bench (tau2|swebench|skillsbench|spreadsheetbench)}"
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"; [ -x "$PY" ] || PY="python3"
TIER="${TIER:-smoke}"
ITER="${ITERATIONS:-3}"
AGENT_MODEL="${AGENT_MODEL:-aws/gpt-oss-120b}"
NUM_TRIALS="${NUM_TRIALS:-10}"
OPTIMIZER_MODEL="${OPTIMIZER_MODEL:-claude-opus-4-8}"
GATE_K_SE="${GATE_K_SE:-1.0}"
ALGORITHM_FOCUS="${ALGORITHM_FOCUS:-all}"
BASE="$REPO/ci/benchmarks/$BENCH/$TIER"
OUT="${2:-$REPO/ci/benchmarks/.work/suite_${TIER}_${BENCH}}"
mkdir -p "$OUT/optimized"
: > "$OUT/metrics.jsonl"

[ -f "$BASE/tasks.json" ] || { echo "::warning::no tasks.json for $BENCH/$TIER — nothing to run"; echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no tasks defined for this tier)" >> "$OUT/report.md"; exit 0; }

: "${ANTHROPIC_BASE_URL:?set ANTHROPIC_BASE_URL (IBM gateway)}"
: "${ANTHROPIC_AUTH_TOKEN:?set ANTHROPIC_AUTH_TOKEN}"

export PYTHONPATH="$REPO/core"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"

# All task ids for this tier (this run optimizes them together). Agent is uniform across a
# tier; take the first task's agent and warn if the file mixes agents (this script can't mix).
readarray -t IDS < <("$PY" - "$BASE/tasks.json" <<'PY'
import json,sys
for t in json.load(open(sys.argv[1])):
    print(t["id"])
PY
)
[ "${#IDS[@]}" -gt 0 ] || { echo "::warning::tasks.json empty for $BENCH/$TIER"; echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no tasks)" >> "$OUT/report.md"; exit 0; }
# AGENT_MODEL (env — the workflow's `agent_model` input, or its default) is
# AUTHORITATIVE: it's what this run actually uses. tasks.json's per-task "agent"
# field is only consulted to WARN on a mismatch (e.g. a curated task pinned to a
# different model than requested) — it never silently overrides the caller's choice.
"$PY" - "$BASE/tasks.json" "$AGENT_MODEL" <<'PY'
import json,sys
ts=json.load(open(sys.argv[1]))
agents={t.get("agent") for t in ts if t.get("agent")}
env_model=sys.argv[2]
if agents and agents != {env_model}:
    sys.stderr.write(f"::warning::tasks.json pins agent(s) {sorted(agents)} but this run uses {env_model!r} (override)\n")
PY
IDS_CSV="$(IFS=,; echo "${IDS[*]}")"
echo ">>> $BENCH/$TIER — optimizing ${#IDS[@]} tasks together (agent=$AGENT_MODEL, ${ITER} iters)" >&2

# ---- scaffold ONE project over ALL tasks -----------------------------------
WORK="$REPO/ci/benchmarks/.work/suite_${TIER}_${BENCH}_proj"
rm -rf "$WORK"; mkdir -p "$WORK/.capevolve/project/adapters" "$WORK/.capevolve/project/inputs"
PROJ="$WORK/.capevolve/project"
TPL="$REPO/templates/adapters"
cp "$TPL/model_config.py" "$PROJ/adapters/" 2>/dev/null || true

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
    export TAU2_MAX_CONCURRENCY=10
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
SWEBENCH_INSTANCE_IDS=$IDS_CSV
SWEBENCH_MAX_WORKERS=10
SWEBENCH_NAMESPACE=${SWEBENCH_NAMESPACE:-swebench}
SWEBENCH_ORACLE=${SWEBENCH_ORACLE:-1}
ENV
    export SWEBENCH_MAX_WORKERS=10
    ;;
  skillsbench)
    cp "$TPL/skillsbench/adapter.py" "$PROJ/adapters/"
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
SKILLSBENCH_CONCURRENCY=10
ENV
    export SKILLSBENCH_MODEL="$AGENT_MODEL"
    export SKILLSBENCH_TASKS_DIR="$SB_SRC/tasks"
    export SKILLSBENCH_CONCURRENCY=10
    ;;
  spreadsheetbench)
    cp "$TPL/spreadsheetbench/adapter.py" "$PROJ/adapters/"
    cp -R "$TPL/spreadsheetbench/seed_capability" "$PROJ/seed_capability"
    SB_CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}/spreadsheetbench-data"
    SB_DEFAULT="$SB_CACHE/sample_data_200"
    if [ "$TIER" = "full" ]; then SB_DEFAULT="$SB_CACHE/all_data_912_v0.1"; fi
    # SPREADSHEETBENCH_DATA_DIR is expected to be set (and exported to GITHUB_ENV) by
    # ci_setup.sh, which calls fetch_data.sh and echoes the resolved path. When running
    # locally without ci_setup.sh, the SB_DEFAULT fallback is used instead.
    SB_DATA="${SPREADSHEETBENCH_DATA_DIR:-$SB_DEFAULT}"
    [ -f "$SB_DATA/dataset.json" ] || { echo "::error:: spreadsheetbench dataset not found at $SB_DATA (run ci/benchmarks/spreadsheetbench/fetch_data.sh or set SPREADSHEETBENCH_DATA_DIR)"; exit 1; }
    # full runs 912 tasks in one go — bump container concurrency over smoke's default
    # (still bounded; each container is ~8GB RAM / 2 CPU, see adapter.py's NOTE ON SCORING)
    # unless the caller already pinned SPREADSHEETBENCH_CONCURRENCY explicitly.
    SB_CONCURRENCY_DEFAULT=4
    if [ "$TIER" = "full" ]; then SB_CONCURRENCY_DEFAULT=8; fi
    CAPS="[system-prompt]"
    cat > "$WORK/.env" <<ENV
MODEL=litellm_proxy/$AGENT_MODEL
LITELLM_PROXY_API_BASE=$ANTHROPIC_BASE_URL
LITELLM_PROXY_API_KEY=$ANTHROPIC_AUTH_TOKEN
MAX_TOKENS=8000
TEMPERATURE=0.0
SPREADSHEETBENCH_HARNESS_DIR=$REPO/third_party/spreadsheetbench
SPREADSHEETBENCH_DATA_DIR=$SB_DATA
SPREADSHEETBENCH_TASK_IDS=$IDS_CSV
SPREADSHEETBENCH_CONCURRENCY=${SPREADSHEETBENCH_CONCURRENCY:-$SB_CONCURRENCY_DEFAULT}
ENV
    export SPREADSHEETBENCH_HARNESS_DIR="$REPO/third_party/spreadsheetbench"
    export SPREADSHEETBENCH_DATA_DIR="$SB_DATA"
    export SPREADSHEETBENCH_CONCURRENCY="${SPREADSHEETBENCH_CONCURRENCY:-$SB_CONCURRENCY_DEFAULT}"
    ;;
  *) echo "unknown bench: $BENCH" >&2; exit 2;;
esac

# NO-HOLDOUT FIT split: train == val == test == ALL tier tasks.
"$PY" - "$IDS_CSV" > "$PROJ/inputs/split_ids.json" <<'PY'
import json,sys
ids=[s for s in sys.argv[1].split(",") if s]
print(json.dumps({"train":ids,"val":ids,"test":ids}))
PY

cat > "$PROJ/capevolve.yaml" <<YAML
capabilities:       $CAPS
capability_path:    seed_capability
optimizer_skill:    claude-code
optimizer_model:    $OPTIMIZER_MODEL
target_model:       $AGENT_MODEL
optimizer_max_turns:    ${OPTIMIZER_MAX_TURNS:-80}
optimizer_usd_per_iter: ${OPTIMIZER_USD_PER_ITER:-0}
algorithm_skill:    hill-climb
algorithm_focus:    $ALGORITHM_FOCUS
dataset_source:     adapter
split_ids_file:     "inputs/split_ids.json"
num_trials:         $NUM_TRIALS
gate_mode:          paired
gate_k_se:          $GATE_K_SE
max_iterations:     $ITER
stall:              $ITER
store:              git
YAML

cd "$WORK"
"$PY" -m cap_evolve.cli check .capevolve/project >&2

# ONE optimization: baseline (all tasks) + ITER optimize iterations + finalize (all tasks).
"$PY" -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml \
      --project .capevolve/project --run-ts suite --max-iterations "$ITER" </dev/null || \
  echo "::warning::suite run exited non-zero for $BENCH"
RUN_DIR="$WORK/.capevolve/run_suite"

# ---- metrics + report (per-task base→opt from the ONE run) -----------------
"$PY" "$LIB_DIR/metrics.py" suite "$RUN_DIR" --bench "$BENCH" --tier "$TIER" \
      --agent "$AGENT_MODEL" --optimizer-model "$OPTIMIZER_MODEL" --iters "$ITER" \
      --jsonl "$OUT/metrics.jsonl" \
      --steps-jsonl "$OUT/steps.jsonl" > "$OUT/report.md" 2>/dev/null || {
  echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no metrics — run failed; check logs)" >> "$OUT/report.md"; }

# reviewable optimized capability (diff vs seed). skillsbench skills are Anthropic-licensed
# → stat only, never content.
best="$(sed -n 's/.*"best_id": "\([^"]*\)".*/\1/p' "$RUN_DIR/state.json" 2>/dev/null | head -1)"
seed_dir="$RUN_DIR/candidates/seed"; opt_dir="$RUN_DIR/candidates/${best:-seed}"
dst="$OUT/optimized"; mkdir -p "$dst"
if [ "$BENCH" = "skillsbench" ]; then
  git --no-pager diff --no-index --stat "$seed_dir" "$opt_dir" > "$dst/capability.diffstat.txt" 2>/dev/null || true
  echo "(skillsbench skills are Anthropic-licensed — content not published; stat only)" >> "$dst/capability.diffstat.txt"
else
  git --no-pager diff --no-index "$seed_dir" "$opt_dir" > "$dst/capability.diff" 2>/dev/null || true
  [ -d "$opt_dir" ] && cp -R "$opt_dir"/. "$dst/optimized_capability/" 2>/dev/null || true
fi

cat "$OUT/report.md"
echo "RUN_DIR=$RUN_DIR"
