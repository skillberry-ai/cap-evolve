#!/usr/bin/env bash
# ci_setup.sh — idempotently prepare the self-hosted runner for ONE benchmark.
# Creates a cached py3.12 venv + benchmark deps/clones OUTSIDE the checkout (so they
# survive between jobs), ensures the claude-code optimizer CLI is installed (hard-fails
# if not — a missing proposer otherwise degrades silently to best=seed/0.000), and
# exports CAPEVOLVE_PY / SKILLSBENCH_SRC / PATH to $GITHUB_ENV.
#
#   ci_setup.sh <bench>
set -euo pipefail
BENCH="${1:?bench}"
CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}"
VENV="$CACHE/venv"
CAPEVOLVE_PY="$VENV/bin/python"
IDX="--index-url https://pypi.org/simple"
mkdir -p "$CACHE"

command -v uv >/dev/null || { echo "::error:: uv is required on the runner"; exit 1; }
[ -x "$CAPEVOLVE_PY" ] || uv venv --python 3.12 "$VENV"

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
uv pip install -p "$CAPEVOLVE_PY" -q $IDX "$REPO/core" litellm

case "$BENCH" in
  swebench)
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX swebench datasets ;;
  tau2)
    [ -d "$CACHE/tau2-bench/.git" ] || git clone --depth 1 https://github.com/sierra-research/tau2-bench "$CACHE/tau2-bench"
    uv pip install -p "$CAPEVOLVE_PY" -q $IDX -e "$CACHE/tau2-bench" ;;
  skillsbench)
    uv tool install $IDX benchflow >/dev/null 2>&1 || true
    [ -d "$CACHE/skillsbench-src/.git" ] || GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/benchflow-ai/skillsbench "$CACHE/skillsbench-src" ;;
esac

"$CAPEVOLVE_PY" -c "import cap_evolve; print('cap_evolve OK')"

# Ensure the claude-code optimizer CLI (the EDIT PROPOSER) is present. If a runner is
# reprovisioned/rebooted the global npm install can vanish; without `claude` the benchmark
# SILENTLY degrades — the optimizer fails every iteration with `cli_present:false`, no edit
# is proposed, and every task reports best=seed / reward 0.000 as if it had "optimized".
# Install idempotently into a user-writable prefix ($HOME/.local/bin is already on PATH and
# exported below), then HARD-FAIL if it is still unavailable so a broken runner is loud, not silent.
if ! command -v claude >/dev/null 2>&1; then
  command -v npm >/dev/null || { echo "::error:: npm required to install the claude-code optimizer"; exit 1; }
  echo "claude CLI missing — installing @anthropic-ai/claude-code into $HOME/.local"
  npm install -g --prefix "$HOME/.local" @anthropic-ai/claude-code
fi
export PATH="$HOME/.local/bin:$PATH"
command -v claude >/dev/null || {
  echo "::error:: claude-code optimizer CLI still unavailable after install — aborting."
  echo "::error:: (running anyway would silently yield best=seed / reward 0.000 on every task.)"
  exit 1
}
echo "claude-code optimizer: $(command -v claude) ($(claude --version 2>/dev/null | head -1))"

# Export for later workflow steps (no-op locally).
if [ -n "${GITHUB_ENV:-}" ]; then
  {
    echo "CAPEVOLVE_PY=$CAPEVOLVE_PY"
    echo "SKILLSBENCH_SRC=$CACHE/skillsbench-src"
    echo "PATH=$HOME/.local/bin:$PATH"
  } >> "$GITHUB_ENV"
fi
echo "ci_setup done for $BENCH (venv: $VENV)"
