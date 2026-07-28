#!/usr/bin/env bash
# fetch_data.sh — download SpreadsheetBench's sample_data_200 dataset at CI/run time.
#
# The harness code is vendored (third_party/spreadsheetbench, a filtered git subtree);
# the DATA (spreadsheet files) is deliberately NOT vendored — it's ~19MB of xlsx blobs
# that don't belong in git history. This script fetches it into a cache dir so repeated
# runs don't re-download.
#
#   fetch_data.sh [dest_dir]
#
# dest_dir defaults to $CAPEVOLVE_CI_CACHE/spreadsheetbench-data (or ~/.cache/capevolve-ci/…).
# On success, prints the path to the extracted dataset root (…/sample_data_200) to stdout.
set -euo pipefail
CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}"
DEST="${1:-$CACHE/spreadsheetbench-data}"
DATASET_URL="https://raw.githubusercontent.com/RUCKBReasoning/SpreadsheetBench/main/data/sample_data_200.tar.gz"
OUT="$DEST/sample_data_200"

if [ -f "$OUT/dataset.json" ]; then
  echo "$OUT"
  exit 0
fi

mkdir -p "$DEST"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "::group::fetching SpreadsheetBench sample_data_200 ($DATASET_URL)" >&2
curl -sSL -o "$tmp/sample_data_200.tar.gz" "$DATASET_URL"
tar -xzf "$tmp/sample_data_200.tar.gz" -C "$tmp"
[ -f "$tmp/sample_data_200/dataset.json" ] || { echo "::error:: sample_data_200.tar.gz did not contain dataset.json" >&2; exit 1; }
rm -rf "$OUT"
mv "$tmp/sample_data_200" "$OUT"
echo "::endgroup::" >&2

echo "$OUT"
