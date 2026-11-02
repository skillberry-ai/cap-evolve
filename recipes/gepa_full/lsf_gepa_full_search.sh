#!/usr/bin/env bash
# LSF job: ONE GEPA-full search (issue #895 §7.1, GEPA-full variant) on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [TRAIN_IDS=<file>] [CONC=10] [MAX_ITERS=]
#              [FIRST_COMPONENT=]
#   Full search: train = official train 80, val = official val 40 (GEPA's valset), from split_ids.json.
#   TRAIN_IDS (smoke only) replaces BOTH train and val with that subset.
#   MAX_ITERS caps GEPA proposals (smoke: 1). Empty = unbounded (R binds).
#   FIRST_COMPONENT (smoke only) = the component GEPA's round robin visits first.
# Layout: runs/gepa_full/<NAME>/ = gateway ledgers, rollouts.jsonl, budget_state.json, candidates/, gepa/, logs.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/gepa_full"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"
RUN="$EXP/runs/gepa_full/$NAME"
[ -e "$RUN" ] && { echo "run dir exists, refusing to overwrite: $RUN" >&2; exit 3; }
mkdir -p "$RUN"

# --- search data, and the test-id guard -----------------------------------------------------------------------
SPLIT="$REPO/ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"
python -I - "$SPLIT" "$RUN" "${TRAIN_IDS:-}" <<'EOF' || exit 4
import json, sys
split, run, subset = sys.argv[1], sys.argv[2], sys.argv[3]
off = json.load(open(split))
if subset:
    ids = [l.strip() for l in open(subset) if l.strip()]
    train, val = ids, ids
else:
    train, val = [str(x) for x in off["train"]], [str(x) for x in off["val"]]
leak = (set(train) | set(val)) & set(map(str, off["test"]))
assert not leak, f"{len(leak)} TEST ids in the gepa_full search data; refusing"
assert set(train) <= set(map(str, off["train"] + off["val"])) and set(val) <= set(map(str, off["train"] + off["val"]))
open(f"{run}/train_ids.txt", "w").write("\n".join(train) + "\n")
open(f"{run}/val_ids.txt", "w").write("\n".join(val) + "\n")
print("split ok:", {"train": len(train), "val": len(val), "subset": bool(subset)})
EOF

# --- the common helper gate: the SAME surface/helpers config as the CapEvolve spec, copied verbatim -----------
python -I - "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml" <<'EOF' || exit 4
import json, sys, yaml
spec = yaml.safe_load(open(sys.argv[1]))
sub = {"surface": spec["surface"], "helpers": spec["helpers"]}
assert sub["helpers"]["enabled"] and sub["helpers"]["lint"] and sub["helpers"]["smoke"], sub
# JSON is valid YAML; cap_evolve.specfile.read_yaml reads it the same way.
open(sys.argv[2], "w").write(json.dumps(sub, indent=1) + "\n")
print("helper gate config copied from the CapEvolve spec:", json.dumps(sub["helpers"])[:200])
EOF

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
TAG="exp895-gepa_full-s${SEED}"
# GEPA's reflection LM makes NON-streamed chat/completions calls of up to 16k output tokens; the gateway's default
# 180 s non-stream read timeout is a total-latency cap for those (a stream only times out per chunk). See BUILD notes.
export GW_GLM_TIMEOUT="${GW_GLM_TIMEOUT:-900}"
python -I "$EXP/tools/gateway.py" --upstream gemma --run-dir "$RUN" > "$RUN/gw_gemma.log" 2>&1 & GW1=$!
python -I "$EXP/tools/gateway.py" --upstream glm --run-dir "$RUN" > "$RUN/gw_glm.log" 2>&1 & GW2=$!
cleanup() {
  for d in "${TMPDIR:-/tmp}"/capevolve_sb_sandbox_*; do [ -f "$d/server.log" ] && cp "$d/server.log" "$RUN/sandbox_$(basename "$d").log"; done
  kill $GW1 $GW2 2>/dev/null; exp895_stop_podman_daemons
}
trap cleanup EXIT
for port in 4113 4115; do for _ in $(seq 1 30); do curl -fsS -m 2 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 && break; sleep 1; done; done
python -I "$EXP/tools/warmup.py" "$CONC" http://127.0.0.1:4113 | tee -a "$RUN/run_meta.txt"

# Agent (target): the adapter calls litellm -> gateway, which injects the RITS key and the served model id.
export MODEL="openai/google/gemma-4-31B-it" API_BASE="http://127.0.0.1:4113/t/${TAG}:target/v1" API_KEY="tag-not-a-secret"
export SPREADSHEETBENCH_CONCURRENCY="$CONC"
export CAPEVOLVE_HELPERS_SPEC="$RUN/helpers_spec.yaml"; unset CAPEVOLVE_FINALIZE

{ echo "host=$(hostname) job=${LSB_JOBID:-none} arm=gepa_full seed=$SEED R=$R conc=$CONC max_iters=${MAX_ITERS:-} first_component=${FIRST_COMPONENT:-} start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "port_sha256=$(sha256sum "$ARMDIR/gepa_full_port.py" | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "gepa=$(python -c 'import importlib.metadata as m; print(m.version("gepa"))') litellm=$(python -c 'import importlib.metadata as m; print(m.version("litellm"))') GW_GLM_TIMEOUT=$GW_GLM_TIMEOUT"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
python "$ARMDIR/gepa_full_port.py" --run-dir "$RUN" --seed "$SEED" --R "$R" \
  --train-ids "$RUN/train_ids.txt" --val-ids "$RUN/val_ids.txt" \
  ${MAX_ITERS:+--max-iters "$MAX_ITERS"} ${FIRST_COMPONENT:+--first-component "$FIRST_COMPONENT"} > "$RUN/gepa_full.log" 2>&1
echo "GEPA_FULL_RC=$?" | tee -a "$RUN/run_meta.txt"
python -I "$ARMDIR/isolation_scan.py" "$RUN" | tee -a "$RUN/run_meta.txt"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo GEPA_FULL_SEARCH_DONE
