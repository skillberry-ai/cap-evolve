#!/usr/bin/env bash
# Launch (or resume) the cap-evolve arm with the optimizer isolated (README: Isolation).
#   bash launch_cape_hc.sh RUN_DIR [extra cap-evolve run args, e.g. --resume]
# Run scripts/check_optimizer_isolation.sh namespace first; it must pass.
set -euo pipefail
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$EX/../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
RUN_DIR="${1:?run dir}"; shift
P="$RUN_DIR/.capevolve/project"
TS="${AW_RUN_TS:-$(basename "$RUN_DIR")}"
mkdir -p "$AW_EVAL/progress"
cd "$P"
export PYTHONPATH="$P/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export AW_SECRETS_FILE="${AW_SECRETS_FILE:-$REPO/.env}" AW_EXPERIMENT="$TS" AW_WORKERS="${AW_WORKERS:-24}"
export AW_PROGRESS_LOG="$AW_EVAL/progress/$TS.log" AW_TRIAL=cape-hc AW_PHASE=eval
unset "${AW_KEY_ENV:-RITS_API_KEY}"
# every optimizer call runs through the namespace wrapper, with the deny rules added
export PATH="$EX/sandbox:$PATH" AW_CLAUDE_SETTINGS="$P/sandbox/optimizer-permissions.json"
export AW_NS_TRANSCRIPTS="$AW_EVAL/runs/optimizer_transcripts/$TS"
exec "$AW_EVAL/venv-aw/bin/cap-evolve" run --spec "$P/capevolve.yaml" --project "$P" --run-ts "$TS" \
  --dashboard off --follow "$@" >> "$AW_EVAL/progress/$TS.out" 2>&1
