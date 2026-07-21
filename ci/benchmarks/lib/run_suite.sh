#!/usr/bin/env bash
# run_suite.sh — run the optimize+eval suite for ONE benchmark and emit metrics +
# reviewable optimized-capability artifacts. Reuses the FROZEN baselines (no baseline
# agent re-run). Called by .github/workflows/benchmarks.yml (self-hosted, ibm-vpc) and
# usable locally.
#
#   run_suite.sh <bench> [out_dir]
#
# Reads ci/benchmarks/<bench>/tasks.json = [{"id":..,"tag":"flip|hard"}, ...] and, per task,
# runs `run_task.sh <bench> <id> optimize <frozen>`, extracts metrics, and captures the
# optimizer's edits. Writes <out_dir>/{metrics.jsonl, report.md, optimized/<id>/…}.
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
BENCH="${1:?bench}"; OUT="${2:-$REPO/ci/benchmarks/.work/suite_$BENCH}"
mkdir -p "$OUT/optimized"
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"; [ -x "$PY" ] || PY="python3"
BASE="$REPO/ci/benchmarks/$BENCH"
: > "$OUT/metrics.jsonl"

ids_tags="$("$PY" - "$BASE/tasks.json" <<'PY'
import json,sys
for t in json.load(open(sys.argv[1])):
    print(f"{t['id']}\t{t.get('tag','')}\t{t.get('agent','aws/gpt-oss-120b')}")
PY
)"

while IFS=$'\t' read -r id tag agent; do
  [ -n "$id" ] || continue
  frozen="$BASE/$(echo "$id" | tr '/ ' '__')/baseline"
  echo "::group::$BENCH $id ($tag, agent=$agent)"
  out="$(AGENT_MODEL="$agent" bash "$LIB_DIR/run_task.sh" "$BENCH" "$id" optimize "$frozen" 2>&1)" || true
  echo "$out"
  run_dir="$(printf '%s' "$out" | sed -n 's/^RUN_DIR=//p' | tail -1)"
  echo "::endgroup::"
  [ -n "$run_dir" ] || { echo "::warning::no run dir for $id"; continue; }

  # metrics row (adds the tag)
  row="$("$PY" "$LIB_DIR/metrics.py" extract "$run_dir" --bench "$BENCH" --task "$id")"
  row="$("$PY" - "$row" "$tag" <<'PY'
import json,sys
d=json.loads(sys.argv[1]); d["tag"]=sys.argv[2]; print(json.dumps(d))
PY
)"
  echo "$row" >> "$OUT/metrics.jsonl"

  # reviewable optimized capability: a diff vs seed. For skillsbench the skills are
  # Anthropic-licensed → capture only a stat summary (no content), never the files.
  best="$(sed -n 's/.*"best_id": "\([^"]*\)".*/\1/p' "$run_dir/state.json" 2>/dev/null | head -1)"
  seed_dir="$run_dir/candidates/seed"; opt_dir="$run_dir/candidates/${best:-seed}"
  dst="$OUT/optimized/$(echo "$id" | tr '/ ' '__')"; mkdir -p "$dst"
  if [ "$BENCH" = "skillsbench" ]; then
    git --no-pager diff --no-index --stat "$seed_dir" "$opt_dir" > "$dst/capability.diffstat.txt" 2>/dev/null || true
    echo "(skillsbench skills are Anthropic-licensed — content not published; stat only)" >> "$dst/capability.diffstat.txt"
  else
    git --no-pager diff --no-index "$seed_dir" "$opt_dir" > "$dst/capability.diff" 2>/dev/null || true
    [ -d "$opt_dir" ] && cp -R "$opt_dir"/. "$dst/optimized_capability/" 2>/dev/null || true
  fi
done <<< "$ids_tags"

# render the report
{
  echo "## Benchmark suite — $BENCH"
  echo
  echo "Agent \`aws/gpt-oss-120b\` · optimizer Claude Code \`claude-opus-4-8\` · ${ITERATIONS:-1} iteration(s) · baselines frozen (reused)."
  echo
  "$PY" "$LIB_DIR/metrics.py" table "$OUT/metrics.jsonl"
} > "$OUT/report.md"
cat "$OUT/report.md"
