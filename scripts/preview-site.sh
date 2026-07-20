#!/usr/bin/env bash
# Preview the cap-evolve site locally, exactly as GitHub Pages will serve it.
#
# Usage:
#   scripts/preview-site.sh             # serves on http://localhost:8080
#   PORT=9090 scripts/preview-site.sh   # override port
#
# What it does: copies site/ into a fresh temp dir and serves it with a plain
# Python HTTP server. No build step, no framework — just static files.

set -euo pipefail

# ---- discover repo root ----
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd)"
SITE_DIR="$REPO_ROOT/site"

if [[ ! -d "$SITE_DIR" ]]; then
  echo "error: no site/ directory at $SITE_DIR" >&2
  exit 1
fi

PORT="${PORT:-8080}"

# ---- stage the site into a temp dir ----
PREVIEW_DIR="$(mktemp -d -t capevolve-site-preview.XXXXXX)"
trap 'rm -rf "$PREVIEW_DIR"' EXIT

cp -R "$SITE_DIR"/. "$PREVIEW_DIR/"

echo "cap-evolve site preview"
echo "  source:  $SITE_DIR"
echo "  serving: http://localhost:$PORT"
echo "  temp:    $PREVIEW_DIR"
echo
echo "  (Ctrl-C to stop)"
echo

# ---- serve ----
cd "$PREVIEW_DIR"
exec python3 -m http.server "$PORT"
