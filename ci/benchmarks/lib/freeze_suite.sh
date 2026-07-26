#!/usr/bin/env bash
# freeze_suite.sh — baseline a LIST of tasks and FREEZE each, emitting a pass@k summary.
#
#   freeze_suite.sh <bench> <ids_source> [out_dir]
#
# For every task id it runs `run_task.sh <bench> <id> baseline` (baseline eval only, at
# the spec's num_trials → pass@k) then `freeze_baseline.sh <bench> <id>` to capture the
# frozen baseline under ci/benchmarks/<bench>/<TIER>/<id>/baseline/ for later reuse by
# run_suite.sh. Writes <out_dir>/baseline_summary.{tsv,md} so a human can pick the SMOKE
# sweet spot (keep tasks whose baseline reward is > 0 and < 1 — visible headroom).
#
# ids_source: a JSON file (array of objects with an "id" field, e.g. smoke_candidates.json),
#             a plain newline/space-separated id file, OR a literal space-separated id list.
# Env: TIER (smoke|full, default smoke), AGENT_MODEL (default aws/gpt-oss-120b),
#      SWEBENCH_ORACLE (swebench; default on via run_task.sh).
#
# Runs on the self-hosted runner (needs the VPC model gateway). Mirrors run_suite.sh.
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"; [ -x "$PY" ] || PY="python3"
BENCH="${1:?bench (tau2|swebench|skillsbench)}"
SRC="${2:?ids source (json file, id file, or literal id list)}"
TIER="${TIER:-smoke}"
AGENT_MODEL="${AGENT_MODEL:-aws/gpt-oss-120b}"
OUT="${3:-$REPO/ci/benchmarks/.work/freeze_${TIER}_${BENCH}}"
mkdir -p "$OUT"

# Resolve the id list. JSON array of {id:…} → ids; otherwise treat SRC as a file of ids
# (one per line / whitespace) or, if it isn't a readable file, as a literal id list.
ids="$("$PY" - "$SRC" <<'PY'
import json, os, sys
src = sys.argv[1]
if os.path.isfile(src):
    data = open(src, encoding="utf-8").read()
    try:
        obj = json.loads(data)
        ids = [ (x["id"] if isinstance(x, dict) else str(x)) for x in obj ]
    except Exception:
        ids = data.split()
else:
    ids = src.split()
print("\n".join(i for i in ids if i))
PY
)"
[ -n "$ids" ] || { echo "::error:: no task ids resolved from '$SRC'"; exit 2; }

: > "$OUT/baseline_summary.tsv"
printf 'id\treward\tpass_metric\ttrials\n' >> "$OUT/baseline_summary.tsv"

# Iterate on FD 3 (not stdin) + feed children </dev/null: a subprocess that reads stdin
# (e.g. the optimizer in non-baseline modes) would otherwise DRAIN this here-string and
# the loop would exit after the first task. See run_suite.sh for the bug this prevents.
while IFS= read -r id <&3; do
  [ -n "$id" ] || continue
  echo "::group::freeze $BENCH $id (tier=$TIER agent=$AGENT_MODEL)"
  AGENT_MODEL="$AGENT_MODEL" bash "$LIB_DIR/run_task.sh" "$BENCH" "$id" baseline </dev/null 2>&1 || \
    echo "::warning::baseline run failed for $id"
  TIER="$TIER" AGENT_MODEL="$AGENT_MODEL" bash "$LIB_DIR/freeze_baseline.sh" "$BENCH" "$id" </dev/null 2>&1 || \
    echo "::warning::freeze failed for $id"
  echo "::endgroup::"

  # Read the frozen baseline reward + any pass^k metric.
  safe="$(echo "$id" | tr '/ ' '__')"
  bj="$REPO/ci/benchmarks/$BENCH/$TIER/$safe/baseline/baseline.json"
  row="$("$PY" - "$id" "$bj" <<'PY'
import json, os, sys
id, bj = sys.argv[1], sys.argv[2]
r = pm = tr = ""
if os.path.isfile(bj):
    v = json.load(open(bj, encoding="utf-8")).get("val", {})
    r = v.get("reward", "")
    tr = v.get("trials", v.get("n_trials", ""))
    for k in ("pass_hat_k", "pass^k", "pass_k", "passk"):
        if k in v:
            pm = v[k]; break
print(f"{id}\t{r}\t{pm}\t{tr}")
PY
)"
  echo "$row" >> "$OUT/baseline_summary.tsv"
done 3<<< "$ids"

# Render a sorted markdown summary flagging the smoke sweet spot (0 < reward < 1).
"$PY" - "$OUT/baseline_summary.tsv" "$BENCH" "$TIER" "$AGENT_MODEL" > "$OUT/baseline_summary.md" <<'PY'
import sys
tsv, bench, tier, agent = sys.argv[1:5]
rows = []
for i, line in enumerate(open(tsv, encoding="utf-8")):
    if i == 0:
        continue
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 4 or not parts[0]:
        continue
    id, r, pm, tr = parts[:4]
    try:
        rv = float(r)
    except ValueError:
        rv = None
    rows.append((id, rv, r, pm, tr))
def sortkey(x):
    return (x[1] is None, x[1] if x[1] is not None else 0.0)
rows.sort(key=sortkey)
print(f"## Baseline freeze — {tier} {bench}\n")
print(f"Agent `{agent}` · reward = mean over trials (pass@k). "
      f"**Sweet spot for smoke: 0 < reward < 1** (visible headroom).\n")
print("| task | reward | pass metric | trials | zone |")
print("|---|---:|---|---:|:--:|")
for id, rv, r, pm, tr in rows:
    if rv is None:
        zone = "⚠️ err"
    elif rv <= 0:
        zone = "floor (0)"
    elif rv >= 1:
        zone = "solved (1)"
    else:
        zone = "✅ sweet"
    print(f"| `{id}` | {r or '—'} | {pm or '—'} | {tr or '—'} | {zone} |")
sweet = [x for x in rows if x[1] is not None and 0 < x[1] < 1]
print(f"\n**{len(sweet)}** task(s) in the sweet spot (0 < reward < 1).")
PY

echo "=== baseline freeze summary ($OUT/baseline_summary.md) ==="
cat "$OUT/baseline_summary.md"
