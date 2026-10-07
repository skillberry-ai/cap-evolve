#!/bin/bash
#
# Build (or verify) one parallel-eval LANE: a parsec-live root of its own, so
# that N concurrent eval jobs do not share the mutable state under
# $PARSEC_V4N/_run/parsec-live.
#
# A lane is a SYMLINK FARM, not a copy — ~1MB instead of ~990MB:
#
#   config/   real copy  — the 8 prompts the adapter snapshots, applies and
#                          then RESTORES in a finally. Two lanes sharing this
#                          directory race on the restore, not just the apply:
#                          lane A puts the original back while lane B is still
#                          mid-trial, and the run scores a bundle nobody asked
#                          for. It reports no error.
#   data/     real copy  — agent_learnings.md, which parsec-live WRITES at
#                          runtime (src/agent/learnings.py) and then appends to
#                          every agent prompt. Shared, one lane's learnings
#                          contaminate another lane's prompts mid-sweep.
#   src/ .venv/ ...      symlinks to the shared clone (read-only at runtime).
#
# Why the symlinks are safe, and why this script verifies rather than assumes:
# parsec-live finds its prompts via src/agent/system_prompt.py's
# `_BASE_DIR = dirname^3(__file__)`, and Python leaves __file__ unresolved
# through a symlinked directory, so _BASE_DIR lands on the LANE. But the shared
# venv also carries an editable-install finder whose MAPPING sends the `src`
# package at the SHARED tree. It only loses because its install() APPENDS to
# sys.meta_path, so the stdlib PathFinder (searching sys.path, which uvicorn
# prepends cwd to) resolves `src` from the lane first. A future `pip install -e`
# that prepends instead would silently route every lane back to the shared tree
# and cross-contaminate the whole sweep with no error at all. The --verify probe
# below turns that silent failure into a loud one, so always let it run.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/parsec/h4/make_lane.sh <lane-id>            # create or verify
#   bash scripts/parsec/h4/make_lane.sh <lane-id> --force     # rebuild config/+data/
#   bash scripts/parsec/h4/make_lane.sh --verify-only <lane-id>
#
# Exit codes:
#   0  lane present and verified
#   1  bad usage / missing precondition
#   3  lane built but VERIFICATION FAILED — do not run a sweep on it
set -eo pipefail

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"

SHARED="$PARSEC_V4N/_run/parsec-live"
LANES_ROOT="${H4_LANES_ROOT:-$PARSEC_V4N/_run/h4-lanes}"

# Copied per lane because they are written at runtime; everything else is
# symlinked. .git and __pycache__ are skipped outright: neither is needed to
# serve a request, and a symlink to either invites a write into the shared tree.
COPY_ENTRIES=(config data)
SKIP_ENTRIES=(.git __pycache__)

FORCE=false
VERIFY_ONLY=false
LANE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)       FORCE=true; shift ;;
    --verify-only) VERIFY_ONLY=true; shift ;;
    -h|--help)     sed -n '2,45p' "$0"; exit 0 ;;
    -*)            echo "unknown flag: $1" >&2; exit 1 ;;
    *)             LANE="$1"; shift ;;
  esac
done

if [[ -z "$LANE" ]]; then
  echo "usage: make_lane.sh <lane-id> [--force|--verify-only]" >&2
  exit 1
fi
# Lane ids become directory names and are interpolated into paths below.
if [[ ! "$LANE" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "lane id must match [A-Za-z0-9_.-]+ (got: $LANE)" >&2
  exit 1
fi

LANE_DIR="$LANES_ROOT/$LANE"

if [[ ! -d "$SHARED" ]]; then
  echo "FATAL: shared parsec-live clone not found at $SHARED" >&2
  exit 1
fi

in_list() {
  local needle="$1"; shift
  local x
  for x in "$@"; do [[ "$x" == "$needle" ]] && return 0; done
  return 1
}

build_lane() {
  mkdir -p "$LANE_DIR"

  local path entry
  # dotglob so .coderabbit.yaml, .pre-commit-config.yaml etc. come along;
  # nullglob so an empty match doesn't yield a literal '*'.
  shopt -s dotglob nullglob
  for path in "$SHARED"/*; do
    entry="$(basename "$path")"
    in_list "$entry" "${SKIP_ENTRIES[@]}" && continue

    if in_list "$entry" "${COPY_ENTRIES[@]}"; then
      if [[ -e "$LANE_DIR/$entry" && "$FORCE" != true ]]; then
        echo "  keep    $entry/ (already present; --force to refresh)"
        continue
      fi
      rm -rf "$LANE_DIR/$entry"
      cp -r "$path" "$LANE_DIR/$entry"
      echo "  copy    $entry/"
    else
      # Replace a stale symlink, but never clobber a real file someone put here.
      if [[ -L "$LANE_DIR/$entry" ]]; then
        ln -sfn "$path" "$LANE_DIR/$entry"
      elif [[ -e "$LANE_DIR/$entry" ]]; then
        echo "  SKIP    $entry (exists and is not a symlink — leaving alone)" >&2
        continue
      else
        ln -s "$path" "$LANE_DIR/$entry"
      fi
    fi
  done
  shopt -u dotglob nullglob

  mkdir -p "$LANE_DIR/_h4/logs"

  # The skills store is bind-mounted into all five simulators. It lives outside
  # parsec-live (at $PARSEC_V4N/_run/skills), so the loop above never sees it.
  # Copy rather than symlink: the five services each write their own
  # parsec-<service>/ subdirectory, which keeps them apart from each other but
  # NOT from another lane's five doing the same. 20 files, so the copy is free.
  # parsec_stack.sh refuses to come up if this is empty, which is the loud
  # failure we want if the shared store was never populated.
  if [[ -e "$LANE_DIR/_h4/skills" && "$FORCE" != true ]]; then
    echo "  keep    _h4/skills/ (already present; --force to refresh)"
  else
    rm -rf "$LANE_DIR/_h4/skills"
    cp -r "$PARSEC_V4N/_run/skills" "$LANE_DIR/_h4/skills"
    echo "  copy    _h4/skills/"
  fi
}

# Import exactly the way parsec-live does (uvicorn prepends cwd to sys.path),
# then assert the prompt dir the server would serve is this lane's own.
verify_lane() {
  local py="$LANE_DIR/.venv/bin/python"
  if [[ ! -x "$py" ]]; then
    echo "FATAL: no interpreter at $py (is .venv symlinked?)" >&2
    return 3
  fi
  ( cd "$LANE_DIR" && PYTHONDONTWRITEBYTECODE=1 "$py" - "$LANE_DIR" <<'PY'
import os, sys
lane = os.path.realpath(sys.argv[1])
sys.path.insert(0, ".")          # what uvicorn's --app-dir default does
from src.agent import system_prompt as sp
got = os.path.realpath(sp._PROMPTS_DIR)
if got != os.path.join(lane, "config", "prompts"):
    print(f"VERIFY FAIL: parsec-live would serve prompts from {got}, not this lane "
          f"({lane}/config/prompts). The editable-install finder has most likely "
          f"taken precedence over sys.path — a sweep on this lane would silently "
          f"score the SHARED bundle.", file=sys.stderr)
    raise SystemExit(3)
missing = [n for n in (
    "orchestrator.md", "shared_context.md", "aap2_agent.md", "babylon_agent.md",
    "cost_agent.md", "icinga_agent.md", "ocpv_agent.md", "security_agent.md",
) if not os.path.isfile(os.path.join(got, n))]
if missing:
    print(f"VERIFY FAIL: lane prompt dir is missing {missing}", file=sys.stderr)
    raise SystemExit(3)
print(f"verified: prompts served from {got}")
PY
  )
}

if [[ "$VERIFY_ONLY" != true ]]; then
  echo "lane $LANE -> $LANE_DIR"
  build_lane
fi

if [[ ! -d "$LANE_DIR" ]]; then
  echo "FATAL: lane not found: $LANE_DIR" >&2
  exit 1
fi

if ! verify_lane; then
  echo "lane $LANE FAILED verification — do not run a sweep on it" >&2
  exit 3
fi
echo "lane $LANE ready"
