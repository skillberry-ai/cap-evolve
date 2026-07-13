#!/usr/bin/env bash
# taubench (tau2 airline) regression test on ONE task (task 9). A real end-to-end
# optimization run used as an on-demand regression check for the pipeline. Cheap:
# 1 task, 1 trial, 1 iteration.
#
#   - agent + user simulator : claude-haiku-4-5 via the IBM Anthropic-compatible gateway
#   - optimizer              : claude-code @ claude-sonnet-4-6
#   - seed                   : the existing airline policy + tools
#   - credentials            : ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN
#
# Exit code is the test result (0 = pass) — the asserter gates it.
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
TAU2_DIR="$(cd "$REPO/.." && pwd)/tau2-bench"
VENV="$REPO/.venv"
PY="$VENV/bin/python"
PROJECT="$REPO/.capevolve/project"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mITEST FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

# Run the agent + user simulator on claude via the gateway (default for this test).
export TAU2_AGENT_MODEL="${TAU2_AGENT_MODEL:-anthropic/claude-haiku-4-5}"
export TAU2_USER_MODEL="${TAU2_USER_MODEL:-anthropic/claude-haiku-4-5}"

say "1/4  Install cap-evolve core + tau2-bench"
[ -x "$PY" ] || python3 -m venv "$VENV" || die "could not create venv (need python3.10+)"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -e "$REPO/core" || die "pip install ./core failed"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"
if [ ! -d "$TAU2_DIR/.git" ]; then
  git clone --depth 1 https://github.com/sierra-research/tau2-bench "$TAU2_DIR" || die "git clone tau2-bench failed"
fi
"$PY" -m pip install -q -e "$TAU2_DIR" || die "pip install tau2-bench failed"
"$PY" -c "import tau2" >/dev/null 2>&1 || die "tau2 import failed after install"

say "2/4  Credentials (IBM Anthropic-compatible gateway)"
if [ ! -f "$REPO/.env" ]; then
  if [ -n "${ANTHROPIC_BASE_URL:-}" ] && [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    printf 'ANTHROPIC_BASE_URL=%s\nANTHROPIC_AUTH_TOKEN=%s\n' "$ANTHROPIC_BASE_URL" "$ANTHROPIC_AUTH_TOKEN" > "$REPO/.env"
  else
    die "ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN not set and no $REPO/.env — the claude agent/user/optimizer need them."
  fi
fi

say "3/4  Wire the project (adapter + seed + spec) + hard gate"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$REPO/.capevolve" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
mkdir -p "$PROJECT/adapters"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/rits.py" "$PROJECT/adapters/"
rm -rf "$PROJECT/seed_capability"; cp -R "$EX_DIR/seed_capability" "$PROJECT/seed_capability"
cp "$EX_DIR/capevolve.itest.yaml" "$EX_DIR/itest_split.json" "$PROJECT/"
PYTHONPATH="$PROJECT/adapters" "$VENV/bin/cap-evolve" check "$PROJECT" || die "cap-evolve check did not pass"

say "4/4  Run the optimization (task 9 · 1 trial · 1 iter) + assert regression"
export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export TAU2_MAX_CONCURRENCY="${TAU2_MAX_CONCURRENCY:-1}"
export TAU2_LLM_TIMEOUT="${TAU2_LLM_TIMEOUT:-240}"
rm -rf "$REPO/.capevolve/run_itest"
"$VENV/bin/cap-evolve" run \
  --spec "$PROJECT/capevolve.itest.yaml" --project "$PROJECT" \
  --run-ts itest --dashboard off || die "cap-evolve run failed"

"$PY" "$EX_DIR/assert_itest.py" "$REPO/.capevolve/run_itest" || die "regression assertions failed"
printf '\n\033[1;32mITEST PASSED.\033[0m\n'
