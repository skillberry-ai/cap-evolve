#!/usr/bin/env bash
# fetch_data.sh — download a SpreadsheetBench dataset variant at CI/run time.
#
# The harness code is vendored (third_party/spreadsheetbench, a filtered git subtree);
# the DATA (spreadsheet files) is deliberately NOT vendored — it's tens of MB of xlsx
# blobs that don't belong in git history. This script fetches it into a cache dir so
# repeated runs don't re-download.
#
#   fetch_data.sh [dest_dir]
#
# dest_dir defaults to $CAPEVOLVE_CI_CACHE/spreadsheetbench-data (or ~/.cache/capevolve-ci/…).
# SPREADSHEETBENCH_VARIANT selects which dataset to fetch (default sample_200):
#   sample_200 — the 200-task curated sample used by the smoke tier (~19MB).
#   full_912   — the full 912-task set self-reported leaderboards are computed over
#                (used by the full tier, ~91MB).
# On success, prints the path to the extracted dataset root to stdout.
set -euo pipefail
CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}"
DEST="${1:-$CACHE/spreadsheetbench-data}"
VARIANT="${SPREADSHEETBENCH_VARIANT:-sample_200}"

case "$VARIANT" in
  sample_200)
    URL="https://raw.githubusercontent.com/RUCKBReasoning/SpreadsheetBench/main/data/sample_data_200.tar.gz"
    INNER="sample_data_200"
    ;;
  full_912)
    URL="https://raw.githubusercontent.com/RUCKBReasoning/SpreadsheetBench/main/data/spreadsheetbench_912_v0.1.tar.gz"
    INNER="all_data_912_v0.1"
    ;;
  *)
    echo "::error:: unknown SPREADSHEETBENCH_VARIANT: $VARIANT (want sample_200|full_912)" >&2
    exit 1
    ;;
esac
OUT="$DEST/$INNER"

if [ -f "$OUT/dataset.json" ]; then
  echo "$OUT"
  exit 0
fi

mkdir -p "$DEST"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "::group::fetching SpreadsheetBench $VARIANT ($URL)" >&2
curl -sSL -o "$tmp/$INNER.tar.gz" "$URL"
tar -xzf "$tmp/$INNER.tar.gz" -C "$tmp"
[ -f "$tmp/$INNER/dataset.json" ] || { echo "::error:: $INNER.tar.gz did not contain dataset.json" >&2; exit 1; }
rm -rf "$OUT"
mv "$tmp/$INNER" "$OUT"
echo "::endgroup::" >&2

echo "$OUT"
