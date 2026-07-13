#!/usr/bin/env bash
# EMPTY-SEED integration test on ONE SkillsBench task (regression check for the
# optimization pipeline + PR #33's empty-seed feature). Cheap: 1 task, 1 trial, 1 iter.
#
#   - agent under test : claude-haiku-4-5 (Claude Code via ACP) in Docker
#   - optimizer        : claude-code @ claude-sonnet-4-6
#   - seed             : EMPTY (no SKILL.md) — the optimizer authors the office skill
#   - credentials      : IBM Anthropic-compatible gateway (ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN)
#
# Prereqs: Docker; network reachability to the gateway; `uv` on PATH (for `bench`).
# Exit code is the test result (0 = pass) — the asserter gates it.
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
VENV="$REPO/.venv"
PY="$VENV/bin/python"
SB_DIR="$REPO/vendor/skillsbench"
PROJECT="$REPO/.capevolve/project"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mITEST FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

export SKILLSBENCH_AGENT_MODEL="${SKILLSBENCH_AGENT_MODEL:-claude-haiku-4-5}"

say "1/5  Install cap-evolve core"
[ -x "$PY" ] || python3 -m venv "$VENV" || die "could not create venv (need python3.10+)"
"$PY" -m pip install -q -e "$REPO/core" || die "pip install ./core failed"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"

say "2/5  Install the SkillsBench benchmark (clone + benchflow CLI)"
if [ ! -d "$SB_DIR/.git" ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/benchflow-ai/skillsbench "$SB_DIR" \
    || die "git clone skillsbench failed"
fi
if ! command -v bench >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/bench" ]; then
  uv tool install benchflow || die "uv tool install benchflow failed (is uv installed?)"
fi
export PATH="$HOME/.local/bin:$PATH"
bench --version || die "bench CLI not on PATH (add ~/.local/bin)"

say "3/5  Credentials (IBM Anthropic-compatible gateway)"
if [ ! -f "$REPO/.env" ]; then
  if [ -n "${ANTHROPIC_BASE_URL:-}" ] && [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    printf 'ANTHROPIC_BASE_URL=%s\nANTHROPIC_AUTH_TOKEN=%s\n' "$ANTHROPIC_BASE_URL" "$ANTHROPIC_AUTH_TOKEN" > "$REPO/.env"
  else
    die "ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN not set and no $REPO/.env — the agent + optimizer need them."
  fi
fi

say "4/5  Wire the project with an EMPTY seed + hard gate"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$REPO/.capevolve" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
mkdir -p "$PROJECT/adapters" "$PROJECT/optimizer"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/anthropic_env.py" "$PROJECT/adapters/"
cp "$EX_DIR/optimizer/INSTRUCTIONS.md" "$PROJECT/optimizer/"
cp "$EX_DIR/capevolve.itest.yaml" "$EX_DIR/itest_split.json" "$PROJECT/"
# EMPTY seed — do NOT extract the office skills. The optimizer authors them from scratch.
rm -rf "$PROJECT/seed_capability"; mkdir -p "$PROJECT/seed_capability"
echo "  seed_capability is EMPTY (no SKILL.md) — the optimizer must author the skill"
PYTHONPATH="$PROJECT/adapters" "$VENV/bin/cap-evolve" check "$PROJECT" || die "cap-evolve check did not pass"

say "5/5  Run the optimization (1 task · 1 trial · 1 iter) + assert regression"
export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export SKILLSBENCH_BENCH_CWD="$REPO/.bench_cwd"
export SKILLSBENCH_TASK_TIMEOUT="${SKILLSBENCH_TASK_TIMEOUT:-2400}"
rm -rf "$REPO/.capevolve/run_itest"
"$VENV/bin/cap-evolve" run \
  --spec "$PROJECT/capevolve.itest.yaml" --project "$PROJECT" \
  --run-ts itest --dashboard off || die "cap-evolve run failed"

"$PY" "$EX_DIR/assert_itest.py" "$REPO/.capevolve/run_itest" || die "regression assertions failed"
printf '\n\033[1;32mITEST PASSED.\033[0m\n'
