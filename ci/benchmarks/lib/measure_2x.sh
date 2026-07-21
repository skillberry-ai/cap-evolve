#!/usr/bin/env bash
# measure_2x.sh — run each benchmark's suite twice (reuse frozen baselines) and assemble
# ci/benchmarks/RESULTS.md with run-to-run reward/latency/cost. Docker benchmarks run
# sequentially to avoid contention. Local + CI usable.
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"; [ -x "$PY" ] || PY="python3"
OUT="$REPO/ci/benchmarks/.work/measure"
BENCHES="${1:-tau2 swebench skillsbench}"
rm -rf "$OUT"; mkdir -p "$OUT"

for run in 1 2; do
  for b in $BENCHES; do
    echo ">>> measure run $run / $b"
    bash "$LIB_DIR/run_suite.sh" "$b" "$OUT/run$run/$b" >/dev/null 2>&1 || true
  done
done

"$PY" "$LIB_DIR/results_md.py" "$OUT" "$REPO/ci/benchmarks/RESULTS.md"
echo "wrote $REPO/ci/benchmarks/RESULTS.md"
cat "$REPO/ci/benchmarks/RESULTS.md"
