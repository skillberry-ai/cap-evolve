#!/usr/bin/env bash
# LSF job: ONE SkillOpt search, issue #895 §7.3, on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [CONC=10] [TRAIN_IDS=<file>]
#   TRAIN_IDS (smoke only): train = val = those ids (subset of official train/val). Default: official train 80 / val 40.
# Layout: runs/skillopt/<NAME>/ = split/ (SkillOpt split_dir, test = 1-item TRAIN-id stub), seed_packed.md,
#   helper-gate spec copy, gateway ledgers, rollouts.jsonl, budget_state.json, skillopt_out/ (SkillOpt's own out_root),
#   skillopt_evals.jsonl, optimizer_transcript.jsonl, champion/, run_summary.json, isolation_scan.json.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/skillopt"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"
RUN="$EXP/runs/skillopt/$NAME"
[ -e "$RUN" ] && { echo "run dir exists, refusing to overwrite: $RUN" >&2; exit 3; }
mkdir -p "$RUN"
SPLIT="$REPO/ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"
export EXP895_SEED_DIR="$REPO/templates/adapters/spreadsheetbench/seed_capability_v2"

# SkillOpt split_dir with the test-id guard (counts only, never ids).
python -I "$ARMDIR/make_split.py" "$RUN/split" "$SPLIT" "$EXP/competitors/skillopt" ${TRAIN_IDS:+--ids "$TRAIN_IDS"} \
  | tee -a "$RUN/run_meta.txt" || exit 4   # pipefail: a failed guard fails the pipeline
# The skill document SkillOpt starts from = the v2 seed, packed; it must round-trip byte-identically.
python -I "$ARMDIR/skillopt_pack.py" "$EXP895_SEED_DIR" "$RUN" || exit 4
python -I -c 'import sys; sys.path.insert(0, sys.argv[1]); import skillopt_pack as p; open(sys.argv[3], "w").write(p.pack(sys.argv[2]))' \
  "$ARMDIR" "$EXP895_SEED_DIR" "$RUN/seed_packed.md" || exit 4

# Common helper gate: the SAME helpers table as the CapEvolve arm (copied, not edited), identical for every arm.
cp "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml"

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
TAG="exp895-skillopt-s${SEED}"
python -I "$EXP/tools/gateway.py" --upstream gemma --run-dir "$RUN" > "$RUN/gw_gemma.log" 2>&1 & GW1=$!
python -I "$EXP/tools/gateway.py" --upstream glm --run-dir "$RUN" > "$RUN/gw_glm.log" 2>&1 & GW2=$!
cleanup() { kill $GW1 $GW2 2>/dev/null; exp895_stop_podman_daemons; }
trap cleanup EXIT
for port in 4113 4115; do for _ in $(seq 1 30); do curl -fsS -m 2 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 && break; sleep 1; done; done
# Pre-warm the Gemma route (cold-start stall; tag exp895-warmup, outside every arm's budget).
python -I "$EXP/tools/warmup.py" "$CONC" http://127.0.0.1:4113 | tee -a "$RUN/run_meta.txt"

# Agent (target): the common rollout -> adapter -> litellm -> gateway, which injects the RITS key and the served id.
export MODEL="openai/google/gemma-4-31B-it" API_BASE="http://127.0.0.1:4113/t/${TAG}:target/v1" API_KEY="tag-not-a-secret"
export SPREADSHEETBENCH_CONCURRENCY="$CONC"
export CAPEVOLVE_HELPERS_SPEC="$RUN/helpers_spec.yaml"; unset CAPEVOLVE_FINALIZE
# Optimizer: SkillOpt's own openai_compatible backend, pointed at the GLM gateway (a plain chat model, no tools,
# no file access: it sees only the prompts SkillOpt builds, all kept in optimizer_transcript.jsonl). §7.3 settings.
export OPTIMIZER_OPENAI_COMPATIBLE_BASE_URL="http://127.0.0.1:4115/t/${TAG}:optimizer/v1"
export OPTIMIZER_OPENAI_COMPATIBLE_API_KEY="tag-not-a-secret"
export OPTIMIZER_OPENAI_COMPATIBLE_MODEL="rits/zai-org/glm-5-3"
export OPTIMIZER_OPENAI_COMPATIBLE_TEMPERATURE=0.7
export OPTIMIZER_OPENAI_COMPATIBLE_MAX_TOKENS=16000
# Client timeout above the gateway's own retry window (GLM read timeout 180 s x up to 8 attempts), so a call the
# gateway is still retrying is not abandoned and re-sent by the client.
export OPTIMIZER_OPENAI_COMPATIBLE_TIMEOUT_SECONDS=1800
# SkillOpt's target role is never called (rollout() is replaced). Point it at a closed local port so an accidental
# call fails loudly instead of reaching any real endpoint.
export TARGET_OPENAI_COMPATIBLE_BASE_URL="http://127.0.0.1:9/v1" TARGET_OPENAI_COMPATIBLE_API_KEY="none"
unset OPENAI_API_KEY OPENAI_BASE_URL OPENAI_COMPATIBLE_BASE_URL OPENAI_COMPATIBLE_API_KEY

{ echo "host=$(hostname) job=${LSB_JOBID:-none} arm=skillopt seed=$SEED R=$R conc=$CONC start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "skillopt_sha=$(git -C "$EXP/competitors/skillopt" rev-parse HEAD) skillopt_dirty=$(git -C "$EXP/competitors/skillopt" status --porcelain --untracked-files=no | wc -l)"
  echo "port_sha256=$(cat "$ARMDIR"/skillopt_exp895.py "$ARMDIR"/skillopt_pack.py | sha256sum | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "seed_packed_sha256=$(sha256sum "$RUN/seed_packed.md" | cut -c1-64) helpers_spec_sha256=$(sha256sum "$RUN/helpers_spec.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
python "$ARMDIR/skillopt_exp895.py" --run-dir "$RUN" --seed "$SEED" --R "$R" --split "$RUN/split" > "$RUN/arm.log" 2>&1
RC=$?
echo "SKILLOPT_RC=$RC" | tee -a "$RUN/run_meta.txt"
grep '^SKILLOPT_SUMMARY' "$RUN/arm.log" | tee -a "$RUN/run_meta.txt"
# §4.1 isolation scan over everything the optimizer saw/said (counts only, never a test id).
python -I "$ARMDIR/scan_isolation.py" "$RUN" "$SPLIT" > "$RUN/isolation_scan.log" 2>&1; cat "$RUN/isolation_scan.log"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo SKILLOPT_SEARCH_DONE
