#!/bin/bash
#
# One-time repair for a parsec v4 tree copied from Mac to CCC: re-point the
# 8 .claude/skills/* symlinks at their sibling directory (they currently
# point at an absolute /Users/... path that doesn't exist on this machine),
# and rebuild the parsec-live .venv (its 3 python*/python3.12 symlinks point
# at a macOS-arm64 uv-managed interpreter).
#
# Usage:
#   bash scripts/ccc/parsec_bootstrap.sh --tree /path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/parsec_bootstrap.sh --tree /path/to/rhdp-parsec/v4_2026-09-16 --check
#
# --check reports what's broken without changing anything (exit 1 if
# anything needs repair, 0 if the tree is already healthy).

set -eo pipefail

TREE=""
CHECK_ONLY=false

usage() {
  sed -n '2,14p' "$0"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tree)   TREE="$2"; shift 2 ;;
    --check)  CHECK_ONLY=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$TREE" || ! -d "$TREE" ]]; then
  echo "ERROR: --tree must be an existing directory (got: '$TREE')" >&2
  usage
fi
TREE="$(cd "$TREE" && pwd)"

LIVE_DIR="$TREE/_run/parsec-live"
SKILLS_LINK_DIR="$LIVE_DIR/.claude/skills"
SKILLS_REAL_DIR="$LIVE_DIR/skills"
VENV_DIR="$LIVE_DIR/.venv"

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

broken=0

banner "Checking $SKILLS_LINK_DIR"
if [[ -d "$SKILLS_LINK_DIR" ]]; then
  for link in "$SKILLS_LINK_DIR"/*; do
    [[ -L "$link" ]] || continue
    name="$(basename "$link")"
    if [[ ! -e "$link" ]]; then
      echo "BROKEN: $link -> $(readlink "$link")"
      broken=1
      if [[ "$CHECK_ONLY" == false ]]; then
        target="$SKILLS_REAL_DIR/$name"
        if [[ ! -d "$target" ]]; then
          echo "  SKIP: real skill dir missing too: $target" >&2
          continue
        fi
        rel="$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
                 "$target" "$SKILLS_LINK_DIR")"
        rm -f "$link"
        ln -s "$rel" "$link"
        echo "  FIXED: $link -> $rel"
      fi
    fi
  done
else
  echo "(no $SKILLS_LINK_DIR — nothing to check)"
fi

banner "Checking $VENV_DIR"
if [[ -d "$VENV_DIR" ]]; then
  venv_broken=false
  for py in "$VENV_DIR"/bin/python*; do
    [[ -L "$py" ]] || continue
    if [[ ! -e "$py" ]]; then
      echo "BROKEN: $py -> $(readlink "$py")"
      venv_broken=true
      broken=1
    fi
  done
  if [[ "$venv_broken" == true && "$CHECK_ONLY" == false ]]; then
    echo "Rebuilding venv with uv (needs uv + python3.12 on PATH)..."
    rm -rf "$VENV_DIR"
    ( cd "$LIVE_DIR" && uv venv --python 3.12 && uv pip install -e . )
    echo "  FIXED: rebuilt $VENV_DIR"
  fi
else
  echo "(no $VENV_DIR — nothing to check)"
fi

banner "Result"
if [[ "$broken" -eq 0 ]]; then
  echo "OK: $TREE is healthy."
  exit 0
elif [[ "$CHECK_ONLY" == true ]]; then
  echo "NEEDS REPAIR: re-run without --check to fix."
  exit 1
else
  echo "Repaired what could be repaired — re-run with --check to confirm."
  exit 0
fi
