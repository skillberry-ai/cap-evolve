#!/usr/bin/env bash
# ci_setup.sh — idempotently prepare the self-hosted runner for ONE benchmark.
# Creates a cached py3.12 venv + benchmark deps/clones OUTSIDE the checkout (so they
# survive between jobs), and exports CAPEVOLVE_PY / SKILLSBENCH_SRC / PATH to $GITHUB_ENV.
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

# Export for later workflow steps (no-op locally).
if [ -n "${GITHUB_ENV:-}" ]; then
  {
    echo "CAPEVOLVE_PY=$CAPEVOLVE_PY"
    echo "SKILLSBENCH_SRC=$CACHE/skillsbench-src"
    echo "PATH=$HOME/.local/bin:$PATH"
  } >> "$GITHUB_ENV"
fi
echo "ci_setup done for $BENCH (venv: $VENV)"
