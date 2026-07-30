#!/usr/bin/env bash
# Install smoke test — the one artifact that lets a host row be graded ✅ (issues
# #143, #208).
#
# Everything else in CI sets $CAPEVOLVE_SKILLS_DIR to the repo tree, which takes
# install.sh's FIRST precedence branch and bypasses the --host mapping entirely, so
# "the documented host-agnostic install path works" was never actually executed.
# That is how #193's total optimizer failure hid: skills/optimizers/registry.yaml is a
# plain file, install.sh's copy loop only walked directories, so every stock install
# copied the skills and could not run one iteration.
#
# This script closes it, and the details are load-bearing:
#   * runs `./install.sh --host claude` with a TEMP $HOME, so the --host mapping
#     (hosts.yaml -> ~/.claude/skills) is what actually places the files;
#   * UNSETS $CAPEVOLVE_SKILLS_DIR, so cap-evolve discovers the INSTALLED tree the
#     way a user's install does;
#   * runs from a cwd OUTSIDE the repo. Inside it, run-optimizer's parent-walk finds
#     registry.yaml in the source tree and the job passes while a real install is
#     broken. Outside, only the installed copy can satisfy it.
#   * asserts test_reward == 1.0, not merely exit 0. A failing optimizer is *silent*:
#     the run completes, keeps the seed, and reports 0.0.
#
# SCOPE — what this job does NOT cover: the run below sets PYTHONPATH="$REPO/core" and
# CAPEVOLVE_CORE="$REPO/core", so it exercises the SOURCE core. Step 1 of the documented
# install, `pip install ./core`, is deliberately out of scope here — this job's subject
# is install.sh's skill placement, and the pip step is a plain install already covered by
# every other CI job. Do not read the ✅ on claude-code in hosts.yaml as covering it.
# ($CAPEVOLVE_TOY_DATA / $CAPEVOLVE_MOCK_SCRIPT also point into the repo, but those are
# the fixture — tasks and a mock transcript — not library code.)
#
# Zero API calls (the `mock` optimizer). Usage: bash ci/install_smoke.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d -t capevolve-install-smoke.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

FAKE_HOME="$TMP/home"
WORK="$TMP/work"          # cwd for the run: outside $REPO, so no parent-walk rescue
mkdir -p "$FAKE_HOME" "$WORK"

echo "== install via ./install.sh --host claude (HOME=$FAKE_HOME) =="
# CAPEVOLVE_SKILLS_DIR must be unset or the --host mapping is never consulted.
env -u CAPEVOLVE_SKILLS_DIR HOME="$FAKE_HOME" bash "$REPO/install.sh" --host claude

SKILLS="$FAKE_HOME/.claude/skills"
[[ -d "$SKILLS" ]] || { echo "::error::--host claude did not install to ~/.claude/skills"; exit 1; }
for f in _registry/manifest.json _registry/hosts.yaml optimizers/registry.yaml; do
  [[ -f "$SKILLS/$f" ]] || { echo "::error::installed tree is missing $f"; exit 1; }
done
ndirs="$(find "$SKILLS" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')"
# Assert it, don't just echo it: an echoed number nothing checks is decoration. (Every
# install-shaped failure the review could construct was already caught downstream by
# the installed manifest; this makes the line itself mean something.)
[[ "$ndirs" -ge 20 ]] \
  || { echo "::error::only $ndirs skill dirs installed (expected >= 20)"; exit 1; }
echo "OK: $ndirs skill dirs + registry + hosts.yaml"

echo "== zero-API toy_calc run from OUTSIDE the repo, against the INSTALLED skills =="
P="$WORK/.capevolve/project"
mkdir -p "$P/adapters"
cp "$REPO/examples/toy_calc/adapter.py" "$P/adapters/"
cp "$REPO/templates/project/capevolve.yaml" "$P/capevolve.yaml"
cp -R "$REPO/examples/toy_calc/capability" "$WORK/seed_capability"

cd "$WORK"
out="$(env -u CAPEVOLVE_SKILLS_DIR \
  HOME="$FAKE_HOME" \
  CAPEVOLVE_CORE="$REPO/core" \
  PYTHONPATH="$REPO/core" \
  CAPEVOLVE_TOY_DATA="$REPO/examples/toy_calc" \
  CAPEVOLVE_MOCK_SCRIPT="$REPO/examples/toy_calc/mock_script.json" \
  python3 -m cap_evolve.cli run \
    --spec "$P/capevolve.yaml" --project "$P" --run-ts smoke --dashboard off)"
echo "$out"

# A broken optimizer does not fail the run — it keeps the seed and reports 0.0. Assert
# the real improvement, which is the only thing that proves the install can optimize.
echo "$out" | grep -q '"baseline_val": 0.0' \
  && echo "$out" | grep -q '"test_reward": 1.0' \
  || { echo "::error::installed tree did not reach baseline_val 0.0 -> test_reward 1.0"; exit 1; }

echo "PASS: ./install.sh --host claude produces an install that optimizes from outside the repo"
