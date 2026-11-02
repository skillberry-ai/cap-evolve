#!/usr/bin/env bash
# LSF job: ONE EvoSkill search (issue #895 §7.4) on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<counted rollouts> NAME=<run name> [CONC=10] [MAX_ITERS=12]
#   [TRAIN_IDS=<file> VAL_IDS=<file>]   smoke only: subsets of the official train/val (default: official train 80 / val 40)
# Layout: runs/evoskill/<NAME>/ = ids, helper-gate spec copy, gateway ledgers, rollouts.jsonl, budget_state.json,
#   project/ (EvoSkill's git project: .claude/skills, .evoskill/feedback_history.md), candidates/, champion/,
#   optimizer_transcript.jsonl (every proposer/generator session), optimizer_permissions.jsonl, base_agent_runs.jsonl,
#   arm.log, run_summary.json, budget_probe.json, isolation_scan.json.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
ARMDIR="$EXP/arms/evoskill"
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; CONC="${CONC:-10}"; MAX_ITERS="${MAX_ITERS:-12}"
RUN="$EXP/runs/evoskill/$NAME"
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
assert not (set(train) | set(val)) & test, f"TEST ids in the EvoSkill search data: {len((set(train) | set(val)) & test)}"
assert set(train) <= set(map(str, s["train"] + s["val"])) and set(val) <= set(map(str, s["train"] + s["val"]))
open(f"{run}/train_ids.txt", "w").write("\n".join(train) + "\n")
open(f"{run}/val_ids.txt", "w").write("\n".join(val) + "\n")
print("split ok:", {"train": len(train), "val": len(val), "test_overlap": 0})
EOF

# Common helper gate: the SAME helpers table as the CapEvolve arm (copied, not edited), identical for every arm.
cp "$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml" "$RUN/helpers_spec.yaml"

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
TAG="exp895-evoskill-s${SEED}"
python -I "$EXP/tools/gateway.py" --upstream gemma --run-dir "$RUN" > "$RUN/gw_gemma.log" 2>&1 & GW1=$!
python -I "$EXP/tools/gateway.py" --upstream glm --run-dir "$RUN" > "$RUN/gw_glm.log" 2>&1 & GW2=$!
export EXP895_GW_SOCK="$(mktemp -d /tmp/exp895-gw-XXXXXX)/gw.sock"
python -I "$EXP/tools/sandbox/sandbox_bridge.py" --serve-unix "$EXP895_GW_SOCK" --to-port 4115 & BR=$!
cleanup() {
  for d in "${TMPDIR:-/tmp}"/capevolve_sb_sandbox_*; do [ -f "$d/server.log" ] && cp "$d/server.log" "$RUN/sandbox_$(basename "$d").log"; done
  kill $GW1 $GW2 $BR 2>/dev/null; exp895_stop_podman_daemons
}
trap cleanup EXIT
for port in 4113 4115; do for _ in $(seq 1 30); do curl -fsS -m 2 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 && break; sleep 1; done; done
for _ in $(seq 1 30); do [ -S "$EXP895_GW_SOCK" ] && break; sleep 1; done
# Pre-warm the Gemma route (cold-start stall; tag exp895-warmup, outside every arm's budget).
python -I "$EXP/tools/warmup.py" "$CONC" http://127.0.0.1:4113 | tee -a "$RUN/run_meta.txt"

# Agent (target): litellm -> gateway, which injects the RITS key and the served model id.
export MODEL="openai/google/gemma-4-31B-it" API_BASE="http://127.0.0.1:4113/t/${TAG}:target/v1" API_KEY="tag-not-a-secret"
export SPREADSHEETBENCH_CONCURRENCY="$CONC"
export CAPEVOLVE_HELPERS_SPEC="$RUN/helpers_spec.yaml"; unset CAPEVOLVE_FINALIZE
# Optimizer (proposer + generator): EvoSkill's claude_agent_sdk agents with cli_path = the sandbox shim, which talks
# only to the GLM gateway through the bridge. The SDK refuses to start without ANTHROPIC_API_KEY in OUR env; the
# shim --clearenv's it away, so a non-secret placeholder is enough.
export EXP895_OPT_TAG="${TAG}:optimizer" EXP895_OPT_MODEL="rits/zai-org/glm-5-3"
export ANTHROPIC_API_KEY="tag-not-a-secret" CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK=1
[ -x "$EXP/tools/sandbox/claude" ] || { echo "sandbox shim missing" >&2; exit 5; }
command -v git >/dev/null || { echo "git missing (EvoSkill's ProgramManager needs it)" >&2; exit 5; }

{ echo "host=$(hostname) job=${LSB_JOBID:-none} arm=evoskill seed=$SEED R=$R conc=$CONC max_iters=$MAX_ITERS start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$REPO/templates/adapters/spreadsheetbench/adapter.py" | cut -c1-64)"
  echo "evoskill_pin=$(git -C "$EXP/competitors/evoskill" rev-parse HEAD) evoskill_dirty=$(git -C "$EXP/competitors/evoskill" status --porcelain | wc -l)"
  echo "port_sha256=$(sha256sum "$ARMDIR/evoskill_port.py" | cut -c1-64) rollout_sha256=$(sha256sum "$EXP/arms/common/rollout.py" | cut -c1-64)"
  echo "claude_agent_sdk=$(python -c 'import importlib.metadata as m; print(m.version("claude-agent-sdk"))') helpers_spec_sha256=$(sha256sum "$RUN/helpers_spec.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"
cd "$RUN"
PYTHONUNBUFFERED=1 python "$ARMDIR/evoskill_port.py" --run-dir "$RUN" --seed "$SEED" --R "$R" --train-ids "$RUN/train_ids.txt" \
  --val-ids "$RUN/val_ids.txt" --max-iters "$MAX_ITERS" --conc "$CONC" > "$RUN/arm.log" 2>&1
RC=$?
echo "EVOSKILL_RC=$RC" | tee -a "$RUN/run_meta.txt"
# R-counter probe: an evaluation one task past the remaining budget must raise BudgetStop and spend nothing.
[ -d "$RUN/champion" ] && python "$ARMDIR/budget_probe.py" "$RUN" "$SEED" "$R" "$(head -1 "$RUN/train_ids.txt")" \
  > "$RUN/budget_probe.json" 2>"$RUN/budget_probe.err"; cat "$RUN/budget_probe.json" 2>/dev/null
# §4.1 isolation scan over everything the optimizer saw/said (counts only).
python -I "$ARMDIR/isolation_scan.py" "$RUN" "$SPLIT" $(head -2 "$RUN/train_ids.txt") > "$RUN/isolation_scan.json" 2>&1
cat "$RUN/isolation_scan.json"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo EVOSKILL_SEARCH_DONE
