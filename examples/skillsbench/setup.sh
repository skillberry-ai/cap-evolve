#!/usr/bin/env bash
# Onboard SkillsBench as a NEW benchmark and prepare it for optimization.
#
# Executable transcript of the cap-evolve INTAKE / implement-and-check phase for
# this example, driven by PROMPT.md: a coding agent following RUN.md does exactly
# these steps. Run it directly to reproduce in one command:
#
#   bash examples/skillsbench/setup.sh   # install cap-evolve + onboard SkillsBench + check
#   bash examples/skillsbench/smoke.sh   # 1-task autonomy smoke (cheap, Docker)
#   bash examples/skillsbench/run.sh     # full run (7 iters) + live dashboard
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
VENV="$REPO/.venv"
PY="$VENV/bin/python"
SB_DIR="$REPO/vendor/skillsbench"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

say "1/4  Install cap-evolve (Python venv + core CLI)"
[ -x "$PY" ] || python3 -m venv "$VENV" || die "could not create venv (need python3.10+)"
"$PY" -m pip install -q -e "$REPO/core" || die "pip install ./core failed (a 401 from an IBM mirror is harmless if install still succeeds)"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"

say "2/4  INTAKE — install the SkillsBench benchmark (clone + benchflow CLI)"
# (a) Clone SkillsBench (structure only is fine; LFS payloads not needed for seed/structure).
if [ ! -d "$SB_DIR/.git" ]; then
  echo "  cloning skillsbench (latest main) -> $SB_DIR"
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/benchflow-ai/skillsbench "$SB_DIR" || die "git clone skillsbench failed"
fi
SB_SHA="$(git -C "$SB_DIR" rev-parse HEAD)"
echo "  skillsbench @ $SB_SHA"
# (b) Install the runner CLI: `bench` (benchflow). Lands in ~/.local/bin.
if ! command -v bench >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/bench" ]; then
  uv tool install benchflow || die "uv tool install benchflow failed"
fi
export PATH="$HOME/.local/bin:$PATH"
bench --version || die "bench CLI not on PATH (add ~/.local/bin)"
# (c) Verify each of the 10 tasks still ships one of docx/pptx/xlsx/pdf.
for t in offer-letter-generator exceltable-in-ppt xlsx-recover-data sales-pivot-analysis \
         invoice-fraud-detection weighted-gdp-calc financial-modeling-qa \
         pdf-excel-diff pptx-reference-formatting reserves-at-risk-calc; do
  ls "$SB_DIR/tasks/$t/environment/skills/" >/dev/null 2>&1 || die "task $t has no environment/skills (drifted)"
done
echo "  all 10 tasks ship office skills"

say "3/4  Credentials — repo-root .env (Anthropic-compatible gateway)"
if [ ! -f "$REPO/.env" ]; then
  if [ -n "${ANTHROPIC_BASE_URL:-}" ] && [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    printf 'ANTHROPIC_BASE_URL=%s\nANTHROPIC_AUTH_TOKEN=%s\n' "$ANTHROPIC_BASE_URL" "$ANTHROPIC_AUTH_TOKEN" > "$REPO/.env"
    echo "  wrote $REPO/.env from the environment (gitignored; token never committed)"
  else
    echo "  WARNING: $REPO/.env missing and ANTHROPIC_* not in env — the sandboxed agent needs them."
  fi
fi

say "4/4  Wire the project + hard gate (cap-evolve check)"
# Scaffold the cap-evolve project (intake script), then wire the authored integration.
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$REPO/.capevolve" --workdir "$REPO" --force >/dev/null \
  || die "intake scaffold failed"
PROJECT="$REPO/.capevolve/project"
mkdir -p "$PROJECT/adapters" "$PROJECT/optimizer"
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/anthropic_env.py" "$PROJECT/adapters/"
rm -rf "$PROJECT/seed_capability"; cp -R "$EX_DIR/seed_capability" "$PROJECT/seed_capability"
cp "$EX_DIR/optimizer/INSTRUCTIONS.md" "$PROJECT/optimizer/"
cp "$EX_DIR/capevolve.yaml" "$EX_DIR/capevolve.smoke.yaml" \
   "$EX_DIR/split_ids.json" "$EX_DIR/smoke_split.json" "$PROJECT/"
echo "  project wired at $PROJECT"

PYTHONPATH="$PROJECT/adapters" "$VENV/bin/cap-evolve" check "$PROJECT" || die "cap-evolve check did not pass"
# The capability's own self-check (multi-skill aware).
CAPEVOLVE_CORE="$REPO/core" "$PY" "$REPO/skills/capabilities/skill-package/scripts/check.py" >/dev/null \
  || die "skill-package check.py did not pass"

printf '\n\033[1;32mREADY.\033[0m  Next:\n  bash %s/smoke.sh   # 1-task autonomy smoke (cheap, Docker)\n  bash %s/run.sh     # full run (7 iters · 7 val tasks · 3 trials) + live dashboard\n' "$EX_DIR" "$EX_DIR"
