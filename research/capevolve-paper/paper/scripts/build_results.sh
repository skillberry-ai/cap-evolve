#!/bin/sh
# Rebuild every results artifact. Usage: PY=/path/to/venv/bin/python sh build_results.sh [mock|real]
set -e
cd "$(dirname "$0")"
PY=${PY:-/home/dev/projects2/campaign-scratch/venv-paper/bin/python}
if [ "${1:-mock}" = real ]; then $PY -I real_numbers.py; else $PY -I mock_numbers.py; fi
$PY -I make_tables.py
$PY -I plots/make_plots.py
$PY -I real_results.py
