#!/usr/bin/env bash
# The altk arm end to end (README: ALTK-Evolve arm): wait for the cape-hc baseline's seed
# rollouts, mine the 90 official train trajectories, render both doses, select the dose on dev.
# Idempotent: mining skips task ids already in runs/altk/mined.json.
set -euo pipefail
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAPE="${AW_CAPE_RUN:-cape_hc_s0}"
RUN="$AW_EVAL/runs/$CAPE/.capevolve/run_$CAPE"
ALTK="$AW_EVAL/runs/altk"
REPO="$(cd "$EX/../.." && pwd)"
VALTK="${AW_ALTK_PYTHON:-$REPO/.venv/bin/python}"
SECRETS="${AW_SECRETS_FILE:-$REPO/.env}"
VAW="$AW_EVAL/venv-aw/bin/python"
log(){ echo "$(date -u +%FT%TZ) | altk | $1 | $2" >> "$AW_EVAL/progress/altk.log"; }
mkdir -p "$ALTK"; cd "$ALTK"
until [ -f "$RUN/baseline.json" ]; do sleep 60; done
log wait "cape-hc baseline.json present; seed train rollouts reused from $RUN/rollouts/val"
LITELLM_LOG=ERROR "$VALTK" "$EX/altk/altk_mine.py" "$RUN/rollouts/val" --workers 8 > "$ALTK/mine.out" 2>&1
LITELLM_LOG=ERROR "$VALTK" "$EX/altk/altk_render.py" full "$ALTK/cand_full" > "$ALTK/render_full.out" 2>&1
LITELLM_LOG=ERROR "$VALTK" "$EX/altk/altk_render.py" ret "$ALTK/cand_ret_dev" "$AW_EVAL/root_opt/data/datasets/dev.txt" \
  > "$ALTK/render_ret.out" 2>&1
env -u "${AW_KEY_ENV:-RITS_API_KEY}" AW_SECRETS_FILE="$SECRETS" AW_EXPERIMENT=altk_dev AW_WORKERS=24 \
  AW_PROGRESS_LOG="$AW_EVAL/progress/altk.log" AW_TRIAL=altk \
  "$VAW" "$EX/altk/select_dose.py" "$ALTK/cand_full" "$ALTK/cand_ret_dev" "$ALTK/dose_selection.json" > "$ALTK/select.out" 2>&1
log done "dose selection written: $(python3 -c "import json;print(json.load(open('$ALTK/dose_selection.json'))['chosen'])")"
