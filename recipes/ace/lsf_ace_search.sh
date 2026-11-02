#!/usr/bin/env bash
# LSF job: ONE ACE search, issue #895 §7.8, on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [CONC=10] [MAX_EPOCHS=] [TEST_WORKERS=]
#   [TRAIN_IDS=<file> VAL_IDS=<file>]   smoke only: subsets of the official train/val (default: official train 80 / val 40)
#   MAX_EPOCHS caps ACE epochs (smoke: 1). Empty = R binds.
#   TEST_WORKERS = parallel val tasks (each runs k=3 trials); default CONC/3, so <= CONC rollouts at once.
#   SKILL_BULLETS=0 runs the text-only ablation (no [skill]/[script] surface). FILTER_PROBE=1 re-checks the GLM
#   content filter on upstream vs patched prompts first (tag exp895-ace-probe, outside the search's optimizer tag).
# Layout: runs/ace/<NAME>/ = ids, helper-gate spec copy, gateway ledgers, rollouts.jsonl, budget_state.json,
#   candidates/, ace/ (ACE's own run dir incl. detailed_llm_logs), generator_calls.jsonl, val_evals.jsonl,
#   prompt_patch.diff, run_summary.json, budget_probe.json, isolation_scan.json.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/ace"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"
TEST_WORKERS="${TEST_WORKERS:-$(( CONC / 3 > 0 ? CONC / 3 : 1 ))}"
SKILL_BULLETS="${SKILL_BULLETS:-1}"
RUN="$EXP/runs/ace/$NAME"
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
assert not (set(train) | set(val)) & test, f"TEST ids in the ACE search data: {len((set(train) | set(val)) & test)}"
assert set(train) <= set(map(str, s["train"] + s["val"])) and set(val) <= set(map(str, s["train"] + s["val"]))
open(f"{run}/train_ids.txt", "w").write("\n".join(train) + "\n")
open(f"{run}/val_ids.txt", "w").write("\n".join(val) + "\n")
print("split ok:", {"train": len(train), "val": len(val), "test_overlap": 0})
EOF

# Common helper gate: the SAME helpers table as the CapEvolve arm (copied, not edited), identical for every arm.
cp "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml"

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
TAG="exp895-ace-s${SEED}"
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
# ACE's Reflector and Curator are plain chat completions to the GLM gateway (no tools, no file access), so no
# sandbox is needed; ACE's own logger keeps every prompt/reply (ace/*/detailed_llm_logs) for the isolation scan.
# ACE's utils.py builds a tiktoken cl100k encoder at import: point it at the bundled copy (no network fetch).
export TIKTOKEN_CACHE_DIR="$ARMDIR/tiktoken_cache"
export PYTHONDONTWRITEBYTECODE=1   # never write .pyc into the upstream clone
export PYTHONUNBUFFERED=1          # ACE prints progress; keep arm.log live

{ echo "host=$(hostname) job=${LSB_JOBID:-none} arm=ace seed=$SEED R=$R conc=$CONC test_workers=$TEST_WORKERS max_epochs=${MAX_EPOCHS:-} skill_bullets=$SKILL_BULLETS start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "ace_pin=$(git -C "$EXP/competitors/ace" rev-parse HEAD) ace_clean=$(git -C "$EXP/competitors/ace" status --porcelain | wc -l)"
  echo "ace_arm_sha256=$(sha256sum "$ARMDIR/ace_arm.py" | cut -c1-64) prompts_patch_sha256=$(sha256sum "$ARMDIR/ace_prompts_patch.py" | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "helpers_spec_sha256=$(sha256sum "$RUN/helpers_spec.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
if [ "${FILTER_PROBE:-0}" = 1 ]; then
  python "$ARMDIR/filter_probe.py" "$RUN/filter_probe.json" 2 > "$RUN/filter_probe.log" 2>&1
  grep FILTER_PROBE "$RUN/filter_probe.log" | tee -a "$RUN/run_meta.txt"
fi
python "$ARMDIR/ace_arm.py" --run-dir "$RUN" --seed "$SEED" --R "$R" --train-ids "$RUN/train_ids.txt" \
  --val-ids "$RUN/val_ids.txt" --test-workers "$TEST_WORKERS" ${MAX_EPOCHS:+--max-epochs "$MAX_EPOCHS"} \
  $([ "$SKILL_BULLETS" = 0 ] && echo --no-skill-bullets) > "$RUN/arm.log" 2>&1
RC=$?
echo "ACE_RC=$RC" | tee -a "$RUN/run_meta.txt"
# R-counter probe: an evaluation one task past the remaining budget must raise BudgetStop and spend nothing.
[ -d "$RUN/champion" ] && python "$ARMDIR/budget_probe.py" "$RUN" "$SEED" "$R" "$(head -1 "$RUN/train_ids.txt")" \
  > "$RUN/budget_probe.json" 2>"$RUN/budget_probe.err"; cat "$RUN/budget_probe.json" 2>/dev/null
# §4.1 isolation scan over everything the optimizer saw/said (counts only).
python -I "$ARMDIR/isolation_scan.py" "$RUN" "$SPLIT" $(head -2 "$RUN/train_ids.txt") > "$RUN/isolation_scan.json" 2>&1
cat "$RUN/isolation_scan.json"
echo "ace_clean_after=$(git -C "$EXP/competitors/ace" status --porcelain | wc -l)" >> "$RUN/run_meta.txt"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo ACE_SEARCH_DONE
