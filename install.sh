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
    # Per-host skill dirs come from skills/_registry/hosts.yaml — the SINGLE source
    # of truth (issue #143). This list used to be duplicated here, in
    # cap_evolve.doctor, and in two docs/HOST_SUPPORT.md tables, and it drifted.
    # core/tests/test_host_parity.py fails the build if any of them disagree, so a
    # new host is one row in hosts.yaml and nothing else.
    #
    # Resolved with the repo's own core on PYTHONPATH because install.sh runs BEFORE
    # anything is pip-installed; hosts.py is stdlib-only for exactly this reason.
    # Each row's verified / docs-checked / best-guess grade is in hosts.yaml and
    # rendered in docs/HOST_SUPPORT.md. Unknown host => ~/.config/<host>/skills.
    hostpp="PYTHONPATH=$REPO_DIR/core${PYTHONPATH:+:$PYTHONPATH}"
    if command -v python3 >/dev/null 2>&1 \
       && mapped="$(env "$hostpp" python3 -m cap_evolve.hosts --dest "$HOST" 2>/dev/null)" \
       && [[ -n "$mapped" ]]; then
      echo "$mapped"; return
    fi
    # Fell through. Warn on stderr instead of silently guessing — for a host that DOES
    # have a row, a quiet fallback puts the skills somewhere that host never looks.
    # Two very different causes, and they need different messages: telling someone with
    # no interpreter that `claude` has no hosts.yaml row sends them to edit a file that
    # is correct. Probe once to tell them apart.
    if ! command -v python3 >/dev/null 2>&1; then
      echo "cap-evolve: python3 not found on PATH — --host resolution needs it to read" \
           "skills/_registry/hosts.yaml. hosts.yaml is fine; the interpreter is missing." \
           "Install python3 or pass --dest DIR. Falling back to the dotdir convention." >&2
    elif table="$(env "$hostpp" python3 -m cap_evolve.hosts --json 2>/dev/null)"; \
         [[ "$table" != *'"dest"'* ]]; then
      # The resolver ran but produced no table at all — hosts.yaml missing/unreadable,
      # or $REPO_DIR/core is broken. Not a problem with the host the user named.
      echo "cap-evolve: could not run cap_evolve.hosts (missing or unreadable" \
           "skills/_registry/hosts.yaml, or a broken $REPO_DIR/core) — this is NOT a" \
           "problem with your --host '$HOST'. Pass --dest DIR. Falling back to the" \
           "dotdir convention." >&2
    else
      echo "cap-evolve: no hosts.yaml row for --host '$HOST' — falling back to the" \
           "dotdir convention. Add a row to skills/_registry/hosts.yaml, or pass" \
           "--dest to be sure." >&2
    fi
    echo "$HOME/.config/$HOST/skills"; return
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

# optimizers/registry.yaml is a FILE directly under skills/optimizers/, not a skill
# dir, so the loop above skipped it — and `run-optimizer/scripts/run.py` hard-raises
# FileNotFoundError without it, i.e. every install could copy the skills and still not
# run. Copy it to $DEST/optimizers/ which is exactly where run.py's parent-walk looks.
mkdir -p "$DEST/optimizers"
cp "$SRC/optimizers/registry.yaml" "$DEST/optimizers/registry.yaml"
echo "  + optimizers/registry.yaml"

# hosts.yaml is the same class of file (a plain file under _registry/, not a skill
# dir) and would be skipped for the same reason. build_manifest.py writes
# manifest.json into $DEST/_registry/, so that dir exists either way; copy the
# per-host metadata beside it so an INSTALLED tree can answer "what is this host's
# display name / grade" without the repo.
mkdir -p "$DEST/_registry"
cp "$SRC/_registry/hosts.yaml" "$DEST/_registry/hosts.yaml"
echo "  + _registry/hosts.yaml"

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
