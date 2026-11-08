#!/usr/bin/env bash
# taubench (tau2 airline) regression test on ONE task (task 9). A real end-to-end
# optimization run used as an on-demand regression check for the pipeline. Cheap:
# 1 task, 1 trial, 1 iteration.
#
#   - agent + user simulator : aws/claude-haiku-4-5 via the ETE gateway
#   - optimizer              : claude-code @ claude-sonnet-4-6
#   - seed                   : the existing airline policy + tools
#   - credentials            : OPENAI_BASE_URL + OPENAI_API_KEY (the runner's gateway);
#                              the claude-code optimizer authenticates separately
#
# Exit code is the test result (0 = pass) — the asserter gates it.
set -euo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
TAU2_DIR="$REPO/vendor/tau2-bench"
# tau2-bench requires python >=3.12,<3.14. Override the interpreter used to CREATE
# the venv (and/or the venv path) when the default `python3` is outside that range:
#   PYTHON=/opt/homebrew/bin/python3.12 VENV=.venv-tau2 bash setup.sh
VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
PYTHON="${PYTHON:-python3}"
PROJECT="$REPO/.capevolve/project"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mITEST FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

# Run the agent + user simulator on claude via the gateway (default for this test). The
# aws/ namespace matters: gateway.py normalizes it to openai/aws/... so litellm takes the
# gateway's OpenAI-compatible route, which is the one the key's model scope is enforced on.
export TAU2_AGENT_MODEL="${TAU2_AGENT_MODEL:-aws/claude-haiku-4-5}"
export TAU2_USER_MODEL="${TAU2_USER_MODEL:-aws/claude-haiku-4-5}"

say "1/4  Install cap-evolve core + tau2-bench"
[ -x "$PY" ] || "$PYTHON" -m venv "$VENV" \
  || die "could not create venv with '$PYTHON' — tau2-bench needs python >=3.12,<3.14; pass PYTHON=/path/to/python3.12"
"$PY" -m pip install -q --upgrade pip || true   # best-effort; a mirror 401 must not abort
"$PY" -m pip install -q -e "$REPO/core" || die "pip install ./core failed"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"
if [ ! -d "$TAU2_DIR/.git" ]; then
  git clone --depth 1 https://github.com/sierra-research/tau2-bench "$TAU2_DIR" || die "git clone tau2-bench failed"
fi
"$PY" -m pip install -q -e "$TAU2_DIR" || die "pip install tau2-bench failed"
"$PY" -c "import tau2" >/dev/null 2>&1 || die "tau2 import failed after install"

say "2/4  Credentials (the runner's gateway)"
# adapters/gateway.py reads these from the environment; we deliberately do NOT write them
# to a .env file (a self-hosted runner's workspace may persist, so this test never leaves
# the token on disk). An existing .env is honored.
# The key must be scoped for the model above: a key provisioned only for gpt-oss answers
# "key can only access models=[...]" on every rollout, which reads as a broken run rather
# than a narrow credential.
if { [ -z "${OPENAI_BASE_URL:-}" ] || [ -z "${OPENAI_API_KEY:-}" ]; } && [ ! -f "$REPO/.env" ]; then
  die "Set OPENAI_BASE_URL + OPENAI_API_KEY in the environment (or provide $REPO/.env)."
fi
# The claude-code optimizer authenticates on its own (a logged-in session or its own env),
# so it is NOT covered by the check above and is not this script's to configure.

say "3/4  Wire the project (adapter + seed + spec) + hard gate"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$REPO/.capevolve" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
mkdir -p "$PROJECT/adapters"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/gateway.py" "$PROJECT/adapters/"
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
