#!/usr/bin/env bash
# One-command, re-runnable setup of the AppWorld example (README: Setup, steps 1-4).
#
#   export AW_EVAL=/path/to/aw_eval                                   # default /tmp/aw_eval
#   bash benchmarks/appworld/examples/react_agent/setup.sh            # AppWorld + the direct project
#   bash benchmarks/appworld/examples/react_agent/setup.sh --blackbox # AppWorld + the blackbox project
#
# Every step checks first and skips what is already in place, so a re-run only pays the checks:
# AppWorld is cloned only when missing, the header patch is applied only when not yet in the tree,
# the environment ($AW_EVAL/.venv, or AW_VENV) is created only when missing (never recreated) and packages are installed only when they
# do not import, the data is downloaded and the derived data built only when missing.
# Step 3 of the README (the agent-model key in AW_SECRETS_FILE) is yours: this script only checks it.
set -uo pipefail

EX="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX/../../../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"; export AW_EVAL
AW_REPO_URL="https://github.com/StonyBrookNLP/appworld"
AW_PIN=42b5bcf
APPWORLD="$AW_EVAL/appworld"
VENV="${AW_VENV:-$AW_EVAL/.venv}"
PY="$VENV/bin/python"
PATCH="$EX/patches/appworld-extra-headers.patch"
SECRETS="${AW_SECRETS_FILE:-$REPO/.env}"
KEY="${AW_KEY_ENV:-RITS_API_KEY}"

APPROACH=direct
for arg in "$@"; do
  case "$arg" in
    --blackbox) APPROACH=blackbox ;;
    -h|--help) echo "usage: setup.sh [--blackbox]"; exit 0 ;;
    *) echo "unknown option: $arg  (use --blackbox)" >&2; exit 2 ;;
  esac
done

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

say "1/6  Tools"
for t in git uv; do command -v "$t" >/dev/null || die "'$t' not found on PATH"; done
mkdir -p "$AW_EVAL" || die "cannot create $AW_EVAL"
echo "  AW_EVAL=$AW_EVAL"

say "2/6  AppWorld at $AW_PIN, with the example's header patch"
# git-lfs is needed only to fetch AppWorld's bundles: when cloning, or for a checkout with history.
need_lfs(){
  command -v git-lfs >/dev/null && return 0
  die "'git-lfs' not found on PATH: AppWorld ships its apps and data as Git LFS bundles. Install it, then re-run:
    sudo apt-get install -y git-lfs && git lfs install
  (no sudo: put the git-lfs binary from https://github.com/git-lfs/git-lfs/releases on PATH, then git lfs install)"
}
if [ -d "$APPWORLD/.git" ]; then
  if [ "$(git -C "$APPWORLD" rev-parse --short=7 HEAD)" != "$AW_PIN" ]; then
    git -C "$APPWORLD" checkout -q "$AW_PIN" || die "cannot check out $AW_PIN in $APPWORLD"
  fi
  need_lfs; (cd "$APPWORLD" && git lfs pull) || die "git lfs pull failed in $APPWORLD"
  echo "  $APPWORLD @ $(git -C "$APPWORLD" rev-parse --short=7 HEAD)"
elif [ -d "$APPWORLD/src/appworld" ]; then
  # An existing source tree without git history (e.g. copied): its commit cannot be checked.
  echo "  WARNING: $APPWORLD has no .git, so its commit cannot be verified as $AW_PIN; using it as is"
else
  [ -e "$APPWORLD" ] && die "$APPWORLD exists but is not an AppWorld checkout: move it away and re-run"
  git clone -q "$AW_REPO_URL" "$APPWORLD" || die "could not clone $AW_REPO_URL"
  git -C "$APPWORLD" checkout -q "$AW_PIN" || die "cannot check out $AW_PIN"
  need_lfs; (cd "$APPWORLD" && git lfs pull) || die "git lfs pull failed in $APPWORLD"
  echo "  cloned $APPWORLD @ $AW_PIN"
fi
# git apply works on a plain directory too, with or without .git.
if (cd "$APPWORLD" && git apply --reverse --check "$PATCH" 2>/dev/null); then
  echo "  header patch already applied"
else
  (cd "$APPWORLD" && git apply "$PATCH") || die "could not apply $PATCH"
  echo "  header patch applied"
fi

say "3/6  Python 3.11 environment $VENV (AppWorld + its agents + cap-evolve)"
if [ -x "$PY" ]; then
  echo "  $VENV exists (never recreated here)"
else
  uv venv -q --python 3.11 "$VENV" || die "uv venv --python 3.11 failed"
  echo "  created $VENV"
fi
if "$PY" -c "import appworld, appworld_agents, cap_evolve" 2>/dev/null && [ -x "$VENV/bin/cap-evolve" ]; then
  echo "  packages already installed"
else
  # The pins: README Setup step 1 (fastapi < 0.155 and starlette >= 0.48 for AppWorld at 42b5bcf).
  (cd "$APPWORLD" && uv pip install -q --python "$PY" -e . -e "experiments[simplified]" \
      "pydantic>=2.12,<2.13" "fastapi==0.135.0" "starlette>=0.48" -e "$REPO/core") \
    || die "installing AppWorld + cap-evolve into $VENV failed"
  "$PY" -c "import appworld, appworld_agents, cap_evolve" || die "$VENV still cannot import appworld / appworld_agents / cap_evolve"
  echo "  installed AppWorld, its agents and cap-evolve"
fi
# The unpacked apps mark a finished install; it resolves the bundles relative to the checkout.
if [ -d "$APPWORLD/src/appworld/apps/admin" ]; then
  echo "  AppWorld apps already unpacked"
else
  (cd "$APPWORLD" && "$VENV/bin/appworld" install --repo >/dev/null) || die "appworld install --repo failed"
  echo "  AppWorld apps unpacked"
fi

say "4/6  Data: AppWorld's tasks, the search-only copy, the lint cache and the reference docs"
if [ -f "$AW_EVAL/root_full/data/datasets/test_normal.txt" ]; then
  echo "  $AW_EVAL/root_full already downloaded"
else
  "$VENV/bin/appworld" download data --root "$AW_EVAL/root_full" >/dev/null || die "appworld download data failed"
  echo "  downloaded $AW_EVAL/root_full"
fi
if [ -f "$AW_EVAL/lint_cache.json" ] && [ -d "$AW_EVAL/root_opt/data" ]; then
  echo "  root_opt and the lint cache already built"
else
  "$PY" "$EX/scripts/make_roots.py" || die "make_roots.py failed"
fi
if [ -f "$AW_EVAL/reference/api_index.md" ] && [ -f "$AW_EVAL/reference/react_agent_notes_blackbox.md" ]; then
  echo "  reference docs already written"
else
  "$PY" "$EX/scripts/make_reference.py" "$AW_EVAL/reference" || die "make_reference.py failed"
fi

say "5/6  Checks: the agent's first request matches stock AppWorld's, and the model key is set"
APPWORLD_ROOT="$AW_EVAL/root_opt" "$PY" "$EX/scripts/check_injection.py" "$EX/seed_capability" \
  | tail -1 | grep -q "A4 PASS" || die "the injection check (scripts/check_injection.py, A4) failed"
echo "  A4 PASS (no model was called)"
grep -q "^$KEY=" "$SECRETS" 2>/dev/null \
  || echo "  WARNING: no $KEY= line in $SECRETS: put the agent model's key there (README Setup step 3)"

say "6/6  The $APPROACH project"
if [ "$APPROACH" = blackbox ]; then
  bash "$EX/blackbox/scripts/setup_project.sh" || die "blackbox/scripts/setup_project.sh failed"
else
  bash "$EX/scripts/setup_project.sh" || die "scripts/setup_project.sh failed"
fi

# What to run next, for the approach just set up (run.sh's own modes).
FLAG=""
[ "$APPROACH" = blackbox ] && FLAG="--blackbox "
printf '\n\033[1;32mSETUP DONE (%s).\033[0m  Run it with:\n' "$APPROACH"
printf '  bash %s/run.sh %s--smoke   # 1 task, 1 trial, 1 iteration\n' "$EX" "$FLAG"
printf '  bash %s/run.sh %s--fix10   # the 10 fixed tasks + 5 held-out test tasks (same in both approaches)\n' "$EX" "$FLAG"
printf '  bash %s/run.sh %s          # the full search\n' "$EX" "$FLAG"
printf '  (the optimizer isolation must PASS first: bash %s/scripts/check_optimizer_isolation.sh $AW_ISOLATION)\n' "$EX"
