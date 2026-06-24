#!/usr/bin/env bash
# Universal installer: place the cap-evolve skills into ANY host's skills dir and
# (re)build the registry manifest. Host-agnostic by design — Claude Code, Codex,
# Gemini CLI, opencode, openclaw, IBM Bob, or a bare clone all work.
#
# Usage:
#   ./install.sh                  # auto-detect destination
#   ./install.sh --dest DIR       # explicit destination
#   ./install.sh --host claude    # pick a known host's conventional dir
#   ./install.sh --link           # symlink instead of copy (dev mode)
#
# Detection precedence: $CAPEVOLVE_SKILLS_DIR > ./.claude/skills > ~/.claude/skills
#                       > ~/.config/<host>/skills > ~/.capevolve/skills
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO_DIR/skills"
DEST=""
HOST=""
LINK=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --link) LINK=1; shift;;
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

detect_dest() {
  if [[ -n "${CAPEVOLVE_SKILLS_DIR:-}" ]]; then echo "$CAPEVOLVE_SKILLS_DIR"; return; fi
  if [[ -n "$HOST" ]]; then
    # Per-host skill dirs verified against current docs (2026). Codex uses
    # .agents/skills (NOT ~/.codex); opencode reads .claude/skills natively;
    # Gemini bundles skills inside extensions; IBM Bob has no SKILL.md concept.
    # cursor/droid/copilot/kimi/pi/antigravity dirs follow each tool's dotdir
    # convention (best-guess) — override with --dest or $CAPEVOLVE_SKILLS_DIR if
    # your build differs. See skills/optimizers/run-optimizer/references/<host>.md.
    case "$HOST" in
      claude|claude-code)          echo "$HOME/.claude/skills"; return;;
      codex)                       echo "$HOME/.agents/skills"; return;;
      gemini|gemini-cli)           echo "$HOME/.gemini/extensions/cap-evolve/skills"; return;;
      opencode)                    echo "$HOME/.config/opencode/skills"; return;;
      openclaw)                    echo "$HOME/.openclaw/workspace/skills"; return;;
      cursor)                      echo "$PWD/.cursor/skills"; return;;
      droid|factory|factory-droid) echo "$HOME/.factory/skills"; return;;
      copilot|github-copilot)      echo "$HOME/.copilot/skills"; return;;
      kimi|kimi-code)              echo "$HOME/.kimi/skills"; return;;
      pi)                          echo "$HOME/.pi/skills"; return;;
      antigravity|agy)             echo "$HOME/.antigravity/skills"; return;;
      bob|ibm-bob)                 echo "$HOME/.bob/skills"; return;;
      *)                           echo "$HOME/.config/$HOST/skills"; return;;
    esac
  fi
  if [[ -d "./.claude/skills" ]]; then echo "./.claude/skills"; return; fi
  if [[ -d "$HOME/.claude/skills" ]]; then echo "$HOME/.claude/skills"; return; fi
  echo "$HOME/.capevolve/skills"
}

[[ -n "$DEST" ]] || DEST="$(detect_dest)"
mkdir -p "$DEST"

echo "cap-evolve: installing skills"
echo "  from: $SRC"
echo "  to:   $DEST"

shopt -s nullglob
for comp in orchestrate phases capabilities algorithms optimizers; do
  for skill in "$SRC/$comp"/*/; do
    [[ -d "$skill" ]] || continue
    name="$(basename "$skill")"
    target="$DEST/$name"
    rm -rf "$target"
    if [[ "$LINK" -eq 1 ]]; then
      ln -s "$(cd "$skill" && pwd)" "$target"
    else
      cp -R "$skill" "$target"
    fi
    echo "  + $comp/$name"
  done
done

# (Re)build the manifest for both the repo (component layout) and the installed
# tree (flat layout). build_manifest handles either, so `cap-evolve run` works whether
# it points at the repo skills or the installed dir.
python3 "$SRC/_registry/build_manifest.py" "$SRC" || true
python3 "$SRC/_registry/build_manifest.py" "$DEST" || true

cat <<EOF

Done. Skills installed to: $DEST
Next:
  1) pip install $REPO_DIR/core        # the honest-eval substrate (or set CAPEVOLVE_CORE=$REPO_DIR/core)
  2) point your agent at $REPO_DIR/RUN.md   — or run: cap-evolve run --spec .capevolve/project/capevolve.yaml
EOF
