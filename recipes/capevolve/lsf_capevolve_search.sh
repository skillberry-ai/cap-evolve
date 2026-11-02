#!/usr/bin/env bash
# LSF job: ONE CapEvolve search (issue #895 §6) on a dedicated host.
# Usage (env): SEED=<0|1|2> R=<max_metric_calls> NAME=<run name> [TRAIN_IDS=<file>] [OPT_TURNS=80] [CONC=10] [MAX_ITERS=]
#   MAX_ITERS caps optimizer iterations (smoke: 1). Empty = the spec's max_iterations (R binds).
#   TRAIN_IDS replaces train=val with a SUBSET (smoke runs only); the full search uses the 120-id split.
# Layout: runs/capevolve/<NAME>/ = a fresh copy of the arm template + gateway ledgers + logs. The template is never
# modified, so every seed starts from the same bytes.
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
SEED="${SEED:?}"; R="${R:?}"; NAME="${NAME:?}"; OPT_TURNS="${OPT_TURNS:-80}"; CONC="${CONC:-10}"
RUN="$EXP/runs/capevolve/$NAME"
[ -e "$RUN" ] && { echo "run dir exists, refusing to overwrite: $RUN" >&2; exit 3; }
mkdir -p "$RUN"; cp -r "$EXP/arms/capevolve/template/." "$RUN/work/"
P="$RUN/work/.capevolve/project"
# Re-point the spec's absolute paths at this run's copy, and set seed / budget.
python -I - "$P/capevolve.yaml" "$EXP/arms/capevolve/template/.capevolve/project" "$P" "$SEED" "$R" "$OPT_TURNS" <<'EOF'
import sys
f, old, new, seed, r, turns = sys.argv[1:]
s = open(f).read().replace(old, new)
for k, v in (("split_seed", seed), ("max_metric_calls", r), ("optimizer_max_turns", turns)):
    import re
    s, n = re.subn(rf"^{k}:[^\n]*$", f"{k}: {v}", s, flags=re.M)   # whole line, trailing comment included
    assert n == 1, k
open(f, "w").write(s)
EOF
if [ -n "${TRAIN_IDS:-}" ]; then
  python -I -c 'import json,sys; ids=[l.strip() for l in open(sys.argv[1]) if l.strip()]; json.dump({"train":ids,"val":ids,"test":[]}, open(sys.argv[2],"w"))' \
    "$TRAIN_IDS" "$P/split_ids.json"
fi
python -I - "$P/split_ids.json" "$REPO/ci/benchmarks/spreadsheetbench/full_verified/split_ids.json" <<'EOF'
import json, sys
mine, official = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
assert mine["test"] == [], "CapEvolve project must have test: []"
leak = set(map(str, mine["train"] + mine["val"])) & set(map(str, official["test"]))
assert not leak, f"TEST ids in a CapEvolve project: {sorted(leak)[:5]}"
print("split ok:", {k: len(v) for k, v in mine.items()})
EOF
[ $? -eq 0 ] || exit 4

echo '{"gemma": 64, "glm": 8}' > "$RUN/caps.json"
TAG="exp895-capevolve-s${SEED}"
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
# Pre-warm the Gemma route (first burst after start has always stalled; tag exp895-warmup, outside every arm's budget).
python -I "$EXP/tools/warmup.py" "$CONC" http://127.0.0.1:4113 | tee -a "$RUN/run_meta.txt"

# Agent (target): the adapter calls litellm -> gateway, which injects the RITS key and the served model id.
export MODEL="openai/google/gemma-4-31B-it" API_BASE="http://127.0.0.1:4113/t/${TAG}:target/v1" API_KEY="tag-not-a-secret"
export SPREADSHEETBENCH_CONCURRENCY="$CONC"
# Optimizer: `claude` = the sandbox shim (first on PATH); it talks only to the GLM gateway through the bridge.
export PATH="$EXP/tools/sandbox:$PATH" EXP895_OPT_TAG="${TAG}:optimizer" EXP895_OPT_MODEL="rits/zai-org/glm-5-3"
# Common helper gate (all arms), and finalize OFF (the env would override the spec).
export CAPEVOLVE_HELPERS_SPEC="$P/capevolve.yaml"; unset CAPEVOLVE_FINALIZE
# Full turn-by-turn optimizer transcript (stream-json, secrets redacted by run-optimizer), for the §4.1
# post-search isolation scan. Append mode: every iteration's session lands in the one file.
export CAPEVOLVE_OPTIMIZER_TRANSCRIPT="$RUN/optimizer_transcript.jsonl"
command -v claude | grep -q '/tools/sandbox/claude$' || { echo "claude does not resolve to the sandbox shim" >&2; exit 5; }

{ echo "host=$(hostname) job=${LSB_JOBID:-none} seed=$SEED R=$R start=$(date -u +%FT%TZ)"
  echo "code_sha=$(git -C "$REPO" rev-parse HEAD) adapter_sha256=$(sha256sum "$P/adapters/adapter.py" | cut -c1-64)"
  echo "spec_sha256=$(sha256sum "$P/capevolve.yaml" | cut -c1-64)"; } | tee -a "$RUN/run_meta.txt"   # -a: keep the WARMUP line
cd "$RUN/work"
python -c "import sys; from cap_evolve.cli import main; sys.exit(main())" run --spec "$P/capevolve.yaml" --project "$P" \
  --run-ts main --dashboard off ${MAX_ITERS:+--max-iterations "$MAX_ITERS"} > "$RUN/cap-evolve.log" 2>&1
echo "CAPEVOLVE_RC=$?" | tee -a "$RUN/run_meta.txt"
echo "end=$(date -u +%FT%TZ)" >> "$RUN/run_meta.txt"
echo CAPEVOLVE_SEARCH_DONE
