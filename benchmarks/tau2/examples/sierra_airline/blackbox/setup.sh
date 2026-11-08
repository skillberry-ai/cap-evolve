#!/usr/bin/env bash
# Onboard VANILLA tau2-bench (sierra-research, pinned at TAU2_REFERENCE_SHA) for the blackbox arm.
#
# HAND-WRITTEN REPLAY, not generated output. The files beside this script (adapters/,
# seed_capability/, optimizer/, capevolve*.yaml, split_ids*.json, PROJECT.md) were produced by
# a coding agent following ../PROMPT.md alone. This script replays the setup steps that agent
# ran, in the prompt's R1 order, and then installs THOSE files instead of regenerating them:
#
#   bash examples/tau2_sierra_airline/blackbox/setup.sh
#   bash examples/tau2_sierra_airline/blackbox/run.sh --smoke     # then:  bash examples/tau2_sierra_airline/blackbox/run.sh
#
# The clone is NEVER edited: everything the blackbox arm needs from tau2 is supplied from
# outside by adapters/tau2_tailoring.py.
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../../.." && pwd)"
TAU2_REPO="https://github.com/sierra-research/tau2-bench"
TAU2_DIR="$REPO/vendor/tau2-bench"
# The tau2 commit this arm's adapters/ (adapter.py and tau2_tailoring.py) were created from,
# when the benchmark was onboarded with ../PROMPT.md. Step 2 clones tau2 at exactly this commit,
# and the snapshot runs on no other: a newer tau2 needs a new onboarding with ../PROMPT.md.
TAU2_REFERENCE_SHA="4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699"
VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
# Its OWN base: the two arms are separate onboardings. Runs land here too.
BASE="${BASE:-$REPO/.capevolve-blackbox}"
PROJECT="$BASE/project"
BB="$REPO/skills/interventions/llm-proxies/blackbox/scripts"
WITH_DASHBOARD="${WITH_DASHBOARD:-1}"
for arg in "$@"; do
  case "$arg" in
    --dashboard)    WITH_DASHBOARD=1 ;;
    --no-dashboard) WITH_DASHBOARD=0 ;;
    -h|--help) echo "usage: setup.sh [--dashboard|--no-dashboard]  (default: --dashboard)"; exit 0 ;;
    *) echo "unknown option: $arg  (use --dashboard | --no-dashboard)" >&2; exit 2 ;;
  esac
done
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

say "1/6  Tools + venv (tau2 needs Python >=3.12,<3.14)"
for t in git uv curl make; do command -v "$t" >/dev/null || die "'$t' not found on PATH"; done
[ -x "$PY" ] || uv venv -q -p 3.12 "$VENV" || die "uv venv -p 3.12 failed"
"$PY" --version

say "2/6  Clone tau2 at TAU2_REFERENCE_SHA"
if [ ! -d "$TAU2_DIR/.git" ]; then
  git clone -q "$TAU2_REPO" "$TAU2_DIR" || die "clone of $TAU2_REPO failed"
fi
# A local edit would change what the pinned commit means: refuse rather than run on it.
[ -z "$(git -C "$TAU2_DIR" status --porcelain)" ] \
  || die "vendor/tau2-bench has local changes; the snapshot runs only on a clean checkout. Commit or discard them, or delete vendor/tau2-bench."
if [ "$(git -C "$TAU2_DIR" rev-parse HEAD)" != "$TAU2_REFERENCE_SHA" ]; then
  git -C "$TAU2_DIR" cat-file -e "$TAU2_REFERENCE_SHA^{commit}" 2>/dev/null \
    || git -C "$TAU2_DIR" fetch -q origin || die "git fetch in vendor/tau2-bench failed"
  git -C "$TAU2_DIR" checkout -q --detach "$TAU2_REFERENCE_SHA" \
    || die "cannot check out TAU2_REFERENCE_SHA $TAU2_REFERENCE_SHA in vendor/tau2-bench"
fi
SHA="$(git -C "$TAU2_DIR" rev-parse HEAD)"
[ "$SHA" = "$TAU2_REFERENCE_SHA" ] || die "vendor/tau2-bench is at $SHA, expected TAU2_REFERENCE_SHA $TAU2_REFERENCE_SHA"
echo "$SHA" > "$REPO/vendor/tau2-bench.COMMIT"
echo "  tau2 @ $SHA (= TAU2_REFERENCE_SHA)"

say "3/6  Install cap-evolve + tau2 into the venv"
# tau2 imports websockets unconditionally (tau2/__init__ -> voice) but declares it only in its
# `voice` extra, so install it explicitly with tau2's own constraint.
VIRTUAL_ENV="$VENV" uv pip install -q -e "$REPO/core" -e "$TAU2_DIR" "websockets>=13.0" \
  || die "uv pip install failed"
# The live dashboard is optional: without it `cap-evolve run` simply skips it.
if [ "$WITH_DASHBOARD" = "1" ]; then
  VIRTUAL_ENV="$VENV" uv pip install -q -e "$REPO/dashboard/backend" \
    && echo "  dashboard installed (cap-evolve run picks a free port per run base and prints the URL)" \
    || echo "  (optional) dashboard not installed — runs still work"
fi
N="$("$PY" -c "from tau2.domains.airline.environment import get_tasks; print(len(get_tasks('base')))")" \
  || die "tau2 import failed"
[ "$N" = "50" ] || die "expected 50 airline tasks, got $N"
echo "  50 airline tasks"

say "4/6  Install the snapshot as the project"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$BASE" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
rm -rf "$PROJECT/seed_capability"
cp -R "$EX_DIR/adapters" "$EX_DIR/seed_capability" "$EX_DIR/optimizer" "$PROJECT/"
cp "$EX_DIR/capevolve.yaml" "$EX_DIR/capevolve.smoke.yaml" "$EX_DIR"/split_ids*.json \
   "$EX_DIR/PROJECT.md" "$PROJECT/"
echo "  project at $PROJECT"

say "5/6  Provision the Skillberry stack (provision only — run.sh starts it)"
"$PY" - <<PYEOF || die "Skillberry stack provisioning failed"
import json, sys
sys.path.insert(0, "$BB")
import blackbox_env
print("  " + json.dumps(blackbox_env.provision()))
PYEOF

say "6/6  Hard gate — implement-and-check (cap-evolve check + instructions render self-test)"
for v in OPENAI_BASE_URL OPENAI_API_KEY; do
  [ -n "${!v:-}" ] || grep -q "^$v=" "$REPO/.env" 2>/dev/null \
    || echo "  WARNING: $v not set and not in $REPO/.env — every rollout needs it."
done
CAPEVOLVE_SKILLS_DIR="$REPO/skills" LITELLM_LOCAL_MODEL_COST_MAP=True \
  "$PY" "$REPO/skills/phases/implement-and-check/scripts/run.py" --project "$PROJECT" \
  || die "the gate did not pass"

printf '\n\033[1;32mREADY.\033[0m  Next:\n  bash %s/run.sh --smoke   # task 9, 1 trial, mock optimizer\n  bash %s/run.sh           # budget run (tasks 8 10 20 23 35 42 44)\n' "$EX_DIR" "$EX_DIR"
