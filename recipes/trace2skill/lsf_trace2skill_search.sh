#!/usr/bin/env bash
# LSF job: ONE Trace2Skill search (one pass of the official method), issue #895 §7.5, on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [CONC=10] [WORKERS=8]
#   [TRAIN_IDS=<file> VAL_IDS=<file>]   smoke only: subsets of the official train/val (default: official train 80 / val 40)
#   [PARALLEL_CANDIDATES=1]              evaluate error-skill and combined concurrently (doubles the arm's containers)
# Uses k*|train| + k*|val|*(1 + #non-seed candidates) rollouts = 240 + 360(+360) at the full split; R only caps it.
# Layout: runs/trace2skill/<NAME>/ = ids, helper-gate spec copy, gateway ledgers, rollouts.jsonl, budget_state.json,
#   pool_logs/, analysis/, evolve_{error,combined}/, candidates/, champion/, selection.json, run_summary.json,
#   cost_summary.json, isolation_scan.json.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/trace2skill"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"; WORKERS="${WORKERS:-8}"
RUN="$EXP/runs/trace2skill/$NAME"
[ -e "$RUN" ] && { echo "run dir exists, refusing to overwrite: $RUN" >&2; exit 3; }
mkdir -p "$RUN"
SPLIT="$REPO/ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"
# ids: official train 80 / val 40 unless a smoke subset is given; then the test-id guard (counts only, never ids).
python -I - "$SPLIT" "$RUN" "${TRAIN_IDS:-}" "${VAL_IDS:-}" <<'EOF' || exit 4
import json, sys
split, run, tr, va = sys.argv[1:]
s = json.load(open(split))
read = lambda f: [l.strip() for l in open(f) if l.strip()]
train = read(tr) if tr else [str(x) for x in s["train"]]
val = read(va) if va else [str(x) for x in s["val"]]
test = set(map(str, s["test"]))
assert not (set(train) | set(val)) & test, f"TEST ids in the Trace2Skill search data: {len((set(train) | set(val)) & test)}"
assert set(train) <= set(map(str, s["train"] + s["val"])) and set(val) <= set(map(str, s["train"] + s["val"]))
open(f"{run}/train_ids.txt", "w").write("\n".join(train) + "\n")
open(f"{run}/val_ids.txt", "w").write("\n".join(val) + "\n")
print("split ok:", {"train": len(train), "val": len(val), "test_overlap": 0})
EOF

# Common helper gate: the SAME helpers table as the CapEvolve arm (copied, not edited), identical for every arm.
cp "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml"

echo "{\"gemma\": 64, \"glm\": $WORKERS}" > "$RUN/caps.json"
TAG="exp895-trace2skill-s${SEED}"
python -I "$EXP/tools/gateway.py" --upstream gemma --run-dir "$RUN" > "$RUN/gw_gemma.log" 2>&1 & GW1=$!
python -I "$EXP/tools/gateway.py" --upstream glm --run-dir "$RUN" > "$RUN/gw_glm.log" 2>&1 & GW2=$!
cleanup() { kill $GW1 $GW2 2>/dev/null; exp895_stop_podman_daemons; }
trap cleanup EXIT
for port in 4113 4115; do for _ in $(seq 1 30); do curl -fsS -m 2 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 && break; sleep 1; done; done
# Pre-warm the Gemma route (cold-start stall; tag exp895-warmup, outside every arm's budget).
python -I "$EXP/tools/warmup.py" "$CONC" http://127.0.0.1:4113 | tee -a "$RUN/run_meta.txt"

# Agent (target): litellm -> gateway, which injects the RITS key and the served model id.
export MODEL="openai/google/gemma-4-31B-it" API_BASE="http://127.0.0.1:4113/t/${TAG}:target/v1" API_KEY="tag-not-a-secret"
export SPREADSHEETBENCH_CONCURRENCY="$CONC"
export CAPEVOLVE_HELPERS_SPEC="$RUN/helpers_spec.yaml"; unset CAPEVOLVE_FINALIZE
# Trace2Skill's roles (analysts, MAP/MERGE editors) are plain OpenAI chat completions with no tools and no file access
# (gold-free LLM-only analyst), straight to the GLM gateway; no sandbox is needed. Every prompt/reply they see is
# written by upstream (*_prompt.md, --save-intermediates) for the isolation scan. Make sure no real key leaks in:
unset OPENAI_API_KEY OPENAI_BASE_URL
GLM_BASE="http://127.0.0.1:4115/t/${TAG}:optimizer/v1"

{ echo "host=$(hostname) job=${LSB_JOBID:-none} arm=trace2skill seed=$SEED R=$R conc=$CONC workers=$WORKERS parallel_candidates=${PARALLEL_CANDIDATES:-0} start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "trace2skill_pin=$(git -C "$EXP/competitors/trace2skill" rev-parse HEAD) upstream_dirty=$(git -C "$EXP/competitors/trace2skill" status --porcelain --untracked-files=no | wc -l)"
  echo "arm_sha256=$(cat "$ARMDIR"/trace2skill_arm.py "$ARMDIR"/t2s_evolve.py "$ARMDIR"/t2s_analyse.py "$ARMDIR"/skill-creator/scripts/quick_validate.py | sha256sum | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "helpers_spec_sha256=$(sha256sum "$RUN/helpers_spec.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
python "$ARMDIR/trace2skill_arm.py" --run-dir "$RUN" --seed "$SEED" --R "$R" --train-ids "$RUN/train_ids.txt" \
  --val-ids "$RUN/val_ids.txt" --glm-base "$GLM_BASE" --workers "$WORKERS" \
  ${PARALLEL_CANDIDATES:+--parallel-candidates} > "$RUN/arm.log" 2>&1
RC=$?
echo "TRACE2SKILL_RC=$RC" | tee -a "$RUN/run_meta.txt"
# §4.1 isolation scan over everything the optimizer roles saw/said (counts only).
python -I "$ARMDIR/isolation_scan.py" "$RUN" "$SPLIT" $(head -2 "$RUN/train_ids.txt") > "$RUN/isolation_scan.json" 2>&1
cat "$RUN/isolation_scan.json"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo TRACE2SKILL_SEARCH_DONE
