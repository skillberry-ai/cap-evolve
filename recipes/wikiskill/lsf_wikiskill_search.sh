#!/usr/bin/env bash
# LSF job: ONE WikiSkill search (community port Stahl-G/wikiskill @ da6984ca), issue #895 §7.7, on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [CONC=10] [MAX_ITERS=] [SUBSET=30]
#   [TRAIN_IDS=<file> VAL_IDS=<file>]   smoke only: subsets of the official train/val (default: official train 80 / val 40)
#   The arm draws a fixed seeded SUBSET-of-train (30 of 80) per search seed from the train pool (train_subset.txt).
#   MAX_ITERS caps engine iterations (smoke: 1). Empty = R binds (pre-iteration guard + BudgetStop).
# Layout: runs/wikiskill/<NAME>/ = ids, helper-gate spec copy, gateway ledgers, rollouts.jsonl, budget_state.json,
#   engine/ (the upstream engine workspace: manifest, events.jsonl, wiki/, iterations/), candidates/, champion/,
#   optimizer_transcript.jsonl, run_summary.json, budget_probe.json, isolation_scan.json.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/wikiskill"
UP="$EXP/competitors/wikiskill"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"; SUBSET="${SUBSET:-30}"
RUN="$EXP/runs/wikiskill/$NAME"
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
assert not (set(train) | set(val)) & test, f"TEST ids in the WikiSkill search data: {len((set(train) | set(val)) & test)}"
assert set(train) <= set(map(str, s["train"])), "train pool must come from the official train split"
assert set(val) <= set(map(str, s["val"])), "val must come from the official val split"
assert not set(train) & set(val), "train/val overlap (the engine refuses it too)"
open(f"{run}/train_ids.txt", "w").write("\n".join(train) + "\n")
open(f"{run}/val_ids.txt", "w").write("\n".join(val) + "\n")
print("split ok:", {"train_pool": len(train), "val": len(val), "test_overlap": 0})
EOF
fi

# Common helper gate: the SAME helpers table as the CapEvolve arm (copied, not edited), identical for every arm.
[ "${RESUME:-}" = "1" ] || cp "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml"

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
TAG="exp895-wikiskill-s${SEED}"
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
# The WikiSkill roles (Maintainer, Proposer) are a GLM chat/completions tool loop (wikiskill_arm.GLMRoleTransport)
# straight to the GLM gateway, tag ${TAG}:optimizer. Their ONLY tools are upstream RoleTools read_file (confined to
# a freshly staged per-session workspace by tools_server.safe) and finish: no shell, no network, no host files.
# So no bwrap sandbox is needed (same reasoning as GEPA); every message is kept in optimizer_transcript.jsonl.
export PYTHONPATH="$UP/src:$PYTHONPATH"

{ echo "resume=${RESUME:-0}"; echo "host=$(hostname) job=${LSB_JOBID:-none} arm=wikiskill seed=$SEED R=$R conc=$CONC subset=$SUBSET max_iters=${MAX_ITERS:-} start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "wikiskill_pin=$(git -C "$UP" rev-parse HEAD) upstream_dirty=$(git -C "$UP" status --porcelain | wc -l)"
  echo "arm_sha256=$(sha256sum "$ARMDIR/wikiskill_arm.py" | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "contract_sha256=$(sha256sum "$EXP/arms/common/SURFACE_CONTRACT.md" | cut -c1-64) helpers_spec_sha256=$(sha256sum "$RUN/helpers_spec.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
python "$ARMDIR/wikiskill_arm.py" --run-dir "$RUN" --seed "$SEED" --R "$R" --train-ids "$RUN/train_ids.txt" \
  --val-ids "$RUN/val_ids.txt" --subset "$SUBSET" ${MAX_ITERS:+--max-iters "$MAX_ITERS"} >> "$RUN/arm.log" 2>&1
RC=$?
echo "WIKISKILL_RC=$RC" | tee -a "$RUN/run_meta.txt"
# R-counter probe: an evaluation one rollout past the remaining budget must raise BudgetStop and spend nothing.
[ -d "$RUN/champion" ] && python "$ARMDIR/budget_probe.py" "$RUN" "$SEED" "$R" "$(head -1 "$RUN/train_subset.txt")" \
  > "$RUN/budget_probe.json" 2>"$RUN/budget_probe.err"; cat "$RUN/budget_probe.json" 2>/dev/null
# §4.1 isolation scan over everything the roles saw/said (counts only).
python -I "$ARMDIR/isolation_scan.py" "$RUN" "$SPLIT" $(cat "$RUN/train_subset.txt") > "$RUN/isolation_scan.json" 2>&1
cat "$RUN/isolation_scan.json"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo WIKISKILL_SEARCH_DONE
