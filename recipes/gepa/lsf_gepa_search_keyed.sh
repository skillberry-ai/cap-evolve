#!/usr/bin/env bash
# LSF job: ONE GEPA (text-only) search, issue #895 §7.1, on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [CONC=10] [MAX_ITERS=]
#   [TRAIN_IDS=<file> VAL_IDS=<file>]   smoke only: subsets of the official train/val (default: official train 80 / val 40)
#   MAX_ITERS caps GEPA proposals (smoke: 1). Empty = R binds.
# Layout: runs/gepa/<NAME>/ = ids, helper-gate spec copy, gateway ledgers, rollouts.jsonl, budget_state.json,
#   candidates/, gepa/ (GEPA's own run_dir), reflection_log.jsonl, run_summary.json, isolation_scan.json.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/gepa"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"
RUN="$EXP/runs/gepa/$NAME"
# RESUME=1: continue an existing run dir after an infra stop (state is reloaded; ids/spec are kept as they were).
if [ -e "$RUN" ] && [ "${RESUME:-}" != "1" ]; then echo "run dir exists, refusing to overwrite: $RUN" >&2; exit 3; fi
[ "${RESUME:-}" = "1" ] && [ ! -d "$RUN" ] && { echo "RESUME=1 but no run dir: $RUN" >&2; exit 3; }
mkdir -p "$RUN"
SPLIT="$REPO/ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"
# ids: official train 80 / val 40 unless a smoke subset is given; then the test-id guard (counts only, never ids).
if [ "${RESUME:-}" = "1" ]; then echo "resume: keeping ids"; else python -I - "$SPLIT" "$RUN" "${TRAIN_IDS:-}" "${VAL_IDS:-}" <<'EOF' || exit 4
import json, sys
split, run, tr, va = sys.argv[1:]
s = json.load(open(split))
read = lambda f: [l.strip() for l in open(f) if l.strip()]
train = read(tr) if tr else [str(x) for x in s["train"]]
val = read(va) if va else [str(x) for x in s["val"]]
test = set(map(str, s["test"]))
assert not (set(train) | set(val)) & test, f"TEST ids in the GEPA search data: {len((set(train) | set(val)) & test)}"
assert set(train) <= set(map(str, s["train"] + s["val"])) and set(val) <= set(map(str, s["train"] + s["val"]))
open(f"{run}/train_ids.txt", "w").write("\n".join(train) + "\n")
open(f"{run}/val_ids.txt", "w").write("\n".join(val) + "\n")
print("split ok:", {"train": len(train), "val": len(val), "test_overlap": 0})
EOF
fi

# Common helper gate: the SAME helpers table as the CapEvolve arm (copied, not edited), identical for every arm.
[ "${RESUME:-}" = "1" ] || cp "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml"

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
# KEY_SLOT=<n>: this job's own RITS key (RITS_API_KEY_<n> in ~/secrets/rits_keys.env); unset = rits.env key.
export GW_RITS_KEY_SLOT="${KEY_SLOT:-}"
TAG="exp895-gepa-s${SEED}"
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
# GEPA's reflection LM goes straight to the GLM gateway (no tools, no file access: a plain chat completion),
# so no sandbox is needed; its every prompt/reply is kept in reflection_log.jsonl for the isolation scan.
export LITELLM_LOCAL_MODEL_COST_MAP=True

{ echo "resume=${RESUME:-0} key_slot=${KEY_SLOT:-rits.env}"; echo "host=$(hostname) job=${LSB_JOBID:-none} arm=gepa seed=$SEED R=$R conc=$CONC max_iters=${MAX_ITERS:-} start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "gepa_arm_sha256=$(sha256sum "$ARMDIR/gepa_arm.py" | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "gepa=$(python -c 'import importlib.metadata as m; print(m.version("gepa"))') helpers_spec_sha256=$(sha256sum "$RUN/helpers_spec.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
python "$ARMDIR/gepa_arm.py" --run-dir "$RUN" --seed "$SEED" --R "$R" --train-ids "$RUN/train_ids.txt" \
  --val-ids "$RUN/val_ids.txt" ${MAX_ITERS:+--max-iters "$MAX_ITERS"} >> "$RUN/arm.log" 2>&1
RC=$?
echo "GEPA_RC=$RC" | tee -a "$RUN/run_meta.txt"
# R-counter probe: an evaluation one task past the remaining budget must raise BudgetStop and spend nothing.
[ -d "$RUN/champion" ] && python "$ARMDIR/budget_probe.py" "$RUN" "$SEED" "$R" "$(head -1 "$RUN/train_ids.txt")" \
  > "$RUN/budget_probe.json" 2>"$RUN/budget_probe.err"; cat "$RUN/budget_probe.json" 2>/dev/null
# §4.1 isolation scan over everything the optimizer saw/said (counts only).
python -I "$ARMDIR/isolation_scan.py" "$RUN" "$SPLIT" $(head -2 "$RUN/train_ids.txt") > "$RUN/isolation_scan.json" 2>&1
cat "$RUN/isolation_scan.json"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo GEPA_SEARCH_DONE
