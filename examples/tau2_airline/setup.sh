#!/usr/bin/env bash
# Onboard tau2-bench airline as a NEW benchmark and prepare it for optimization.
#
# This is the executable transcript of the cap-evolve INTAKE / implement-and-check
# phase for this example, driven by PROMPT.md: a coding agent following RUN.md does
# exactly these steps. Run it directly to reproduce in one command:
#
#   bash examples/tau2_airline/setup.sh   # install cap-evolve + onboard tau2 + check
#   bash examples/tau2_airline/run.sh     # full run + live dashboard
#
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
TAU2_DIR="$(cd "$REPO/.." && pwd)/tau2-bench"
VENV="$REPO/.venv"
PY="$VENV/bin/python"
PIP_INDEX="${PIP_INDEX:-https://pypi.org/simple}"   # public PyPI (override if you have a mirror)
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

# --- options: install the live dashboard server or not ---------------------
WITH_DASHBOARD="${WITH_DASHBOARD:-1}"   # default ON; env or flag can override
for arg in "$@"; do
  case "$arg" in
    --dashboard)    WITH_DASHBOARD=1 ;;
    --no-dashboard) WITH_DASHBOARD=0 ;;
    -h|--help) echo "usage: setup.sh [--dashboard|--no-dashboard]  (default: --dashboard)"; exit 0 ;;
    *) echo "unknown option: $arg  (use --dashboard | --no-dashboard)" >&2; exit 2 ;;
  esac
done

say "1/3  Install cap-evolve (Python venv + core CLI)"
[ -x "$PY" ] || python3 -m venv "$VENV" || die "could not create venv (need python3.10+)"
"$PY" -m pip install -q --index-url "$PIP_INDEX" --upgrade pip
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$REPO/core" || die "pip install ./core failed"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"
# Live dashboard (recommended; toggle with --dashboard / --no-dashboard). The built
# frontend (dashboard/frontend/dist — the capybara UI) is committed, so no node is
# needed at runtime; this just installs the server that serves it. Non-fatal.
if [ "$WITH_DASHBOARD" = "1" ]; then
  "$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$REPO/dashboard/backend" 2>/dev/null \
    && echo "  dashboard server installed (live capybara UI: cap-evolve run --dashboard auto)" \
    || echo "  (optional) dashboard server not installed — run still works with --dashboard off"
else
  echo "  dashboard install SKIPPED (--no-dashboard) — run with: CAPEVOLVE_DASHBOARD=off bash run.sh"
fi

say "2/3  INTAKE — onboard the tau2-bench benchmark (per PROMPT.md)"
# (a) Install the benchmark: clone tau2-bench (latest main) + pip install -e. Record the SHA.
if [ ! -d "$TAU2_DIR/.git" ]; then
  echo "  cloning tau2-bench (latest main) -> $TAU2_DIR"
  git clone --depth 1 https://github.com/sierra-research/tau2-bench "$TAU2_DIR" || die "git clone tau2-bench failed"
fi
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$TAU2_DIR" || die "pip install tau2-bench failed"
TAU2_SHA="$(git -C "$TAU2_DIR" rev-parse HEAD)"
mkdir -p "$EX_DIR/run_full"; echo "$TAU2_SHA" > "$EX_DIR/run_full/TAU2_COMMIT.txt"
"$PY" -c "import tau2" >/dev/null 2>&1 || die "tau2 import failed after install"
echo "  tau2-bench installed @ $TAU2_SHA"
# (b) Scaffold the cap-evolve project (the intake script).
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$REPO/.capevolve" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
PROJECT="$REPO/.capevolve/project"
# (c) Wire the integration the agent authored: adapter + RITS shim + seed capability + spec.
mkdir -p "$PROJECT/adapters"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/rits.py" "$PROJECT/adapters/"
rm -rf "$PROJECT/seed_capability"; cp -R "$EX_DIR/seed_capability" "$PROJECT/seed_capability"
cp "$EX_DIR/capevolve.yaml" "$EX_DIR/capevolve.smoke.yaml" \
   "$EX_DIR/split_ids.json" "$EX_DIR/smoke_split.json" "$PROJECT/"
echo "  project scaffolded + integration wired at $PROJECT"

say "3/3  Hard gate — cap-evolve check (credentials + adapter contract)"
if [ -z "${RITS_API_KEY:-}" ] && ! grep -q '^RITS_API_KEY=' "$REPO/.env" 2>/dev/null; then
  echo "  WARNING: RITS_API_KEY not set and not in $REPO/.env — the run needs it (agent + user simulator)."
fi
PYTHONPATH="$PROJECT/adapters" "$VENV/bin/cap-evolve" check "$PROJECT" || die "cap-evolve check did not pass"

printf '\n\033[1;32mREADY.\033[0m  Next:\n  bash %s/run.sh     # full run (10 iters · 50 tasks · 10 trials) + live dashboard\n  bash %s/smoke.sh   # 2-task autonomy smoke (cheap)\n' "$EX_DIR" "$EX_DIR"
