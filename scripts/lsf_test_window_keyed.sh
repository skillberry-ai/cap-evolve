#!/usr/bin/env bash
# LSF job: held-out test window for ONE frozen champion (tools/test_window.py). Env: ARM SEED CHAMP [CONC=10]
set -uo pipefail
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
# shellcheck disable=SC1091
source "$EXP/tools/node_env.sh" || exit 2
ARM="${ARM:?}"; SEED="${SEED:?}"; CHAMP="${CHAMP:?}"; CONC="${CONC:-10}"
OUT="$EXP/runs/test/${ARM}_s${SEED}"
[ -e "$OUT" ] && { echo "test window exists, refusing: $OUT" >&2; exit 3; }
GWD="$EXP/runs/test/.gw_${ARM}_s${SEED}"; mkdir -p "$GWD"; echo '{"gemma": 64}' > "$GWD/caps.json"
export GW_RITS_KEY_SLOT="${KEY_SLOT:-}"   # optional extra RITS key (2026-10-25); unset = rits.env key, as before
python -I "$EXP/tools/gateway.py" --upstream gemma --run-dir "$GWD" > "$GWD/gw_gemma.log" 2>&1 & GW=$!
cleanup() { for d in "${TMPDIR:-/tmp}"/capevolve_sb_sandbox_*; do [ -f "$d/server.log" ] && cp "$d/server.log" "$GWD/sandbox_$(basename "$d").log"; done
            kill $GW 2>/dev/null; exp895_stop_podman_daemons; }
trap cleanup EXIT
for _ in $(seq 1 30); do curl -fsS -m 2 http://127.0.0.1:4113/healthz >/dev/null 2>&1 && break; sleep 1; done
kill -0 $GW 2>/dev/null || { echo "gemma gateway did not start" >&2; exit 4; }
python -I "$EXP/tools/warmup.py" "$CONC" http://127.0.0.1:4113
export MODEL="openai/google/gemma-4-31B-it" API_BASE="http://127.0.0.1:4113/t/exp895-test-${ARM}-s${SEED}:target/v1" API_KEY="tag-not-a-secret"
export SPREADSHEETBENCH_CONCURRENCY="$CONC"
export CAPEVOLVE_HELPERS_SPEC="$EXP/arms/capevolve/template/.capevolve/project/capevolve.yaml"   # the same gate as search
echo "host=$(hostname) job=${LSB_JOBID:-none} arm=$ARM seed=$SEED champ=$CHAMP start=$(date -u +%FT%TZ)"
python "$EXP/tools/test_window.py" "$OUT" "$ARM" "$SEED" "$CHAMP"
echo "TEST_JOB_RC=$?"
