#!/usr/bin/env bash
# Issue #131 evidence: end-to-end integrity of a --parallel run on toy_calc.
#
# Runs the SAME spec + SAME seed twice through `cap-evolve run` — once at the default
# (serial) and once at --parallel 4 — and checks the honest artifacts: final.json, the
# per-candidate val scores, the sealed test number, events.jsonl parseability, cost
# exactness, and absence of worktree orphans. Prints a timing for each.
#
# THIS IS NOT AN EQUIVALENCE PROOF. toy_calc's mock optimizer is IDEMPOTENT and the run
# accepts on iteration 1 then plateaus, so every candidate converges to the same content
# no matter which parent it forked — the two arms agreeing here is an artifact of the
# fixture, not a general property. `--parallel N>1` really does change the search
# (breadth from one champion, not depth per accept); the deterministic proof, with a
# NON-idempotent optimizer, is
# core/tests/test_parallel_candidates.py::test_parallel_changes_the_search_and_is_not_score_equivalent
# Usage: PYTHONPATH=<repo>/core bash scripts/verify_issue_131.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python3}"
export CAPEVOLVE_CORE="$REPO/core"
export PYTHONPATH="$REPO/core"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export CAPEVOLVE_TOY_DATA="$REPO/examples/toy_calc"
export CAPEVOLVE_MOCK_SCRIPT="$REPO/examples/toy_calc/mock_script.json"

setup() {  # $1 = dir
  local D="$1"
  mkdir -p "$D/.capevolve/project/adapters"
  cp "$REPO/examples/toy_calc/adapter.py" "$D/.capevolve/project/adapters/"
  cp -R "$REPO/examples/toy_calc/capability" "$D/seed_capability"
  cp "$REPO/templates/project/capevolve.yaml" "$D/.capevolve/project/capevolve.yaml"
}

run_one() {  # $1 = dir, $2.. = extra flags
  local D="$1"; shift
  local t0 t1
  t0=$(date +%s.%N)
  (cd "$D" && "$PY" -m cap_evolve.cli run \
      --spec "$D/.capevolve/project/capevolve.yaml" \
      --project "$D/.capevolve/project" \
      --run-ts demo --dashboard off "$@" >"$D/run.log" 2>&1)
  t1=$(date +%s.%N)
  echo "$t1 - $t0" | bc
}

SER="$(mktemp -d -t ce131ser.XXXXXX)"
PAR="$(mktemp -d -t ce131par.XXXXXX)"
setup "$SER"; setup "$PAR"

echo "== serial (default, --parallel 1) =="
T_SER=$(run_one "$SER" --parallel 1)
echo "wall: ${T_SER}s"

echo "== parallel (--parallel 4) =="
T_PAR=$(run_one "$PAR" --parallel 4)
echo "wall: ${T_PAR}s"

R_SER="$SER/.capevolve/run_demo"
R_PAR="$PAR/.capevolve/run_demo"

echo
echo "== final.json diff (empty == identical headline + sealed test) =="
diff <(jq -S . "$R_SER/final.json") <(jq -S . "$R_PAR/final.json") && echo "IDENTICAL"

echo
echo "== per-candidate val scores diff =="
scores() {  # step events: candidate, accept, val
  jq -c 'select(.kind=="step") | {candidate,accept,val}' "$1/events.jsonl"
}
diff <(scores "$R_SER") <(scores "$R_PAR") && echo "IDENTICAL"

echo
echo "== sealed test number =="
for d in "$R_SER" "$R_PAR"; do
  jq -c '{best_id, test: .test.reward, baseline: .test_baseline.reward, delta: .test_delta}' "$d/final.json"
done

echo
echo "== test seal intact (scored exactly once) =="
for d in "$R_SER" "$R_PAR"; do
  echo "$d: test_used=$(jq -r .test_used "$d/splits.json") finalize_events=$(grep -c '"kind": "finalize"' "$d/events.jsonl" || true)"
done

echo
echo "== events.jsonl strictly parseable =="
for d in "$R_SER" "$R_PAR"; do
  "$PY" - "$d/events.jsonl" <<'EOF'
import json, sys
n = 0
with open(sys.argv[1], encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        assert line.endswith("\n"), f"line {i} has no terminator"
        json.loads(line)
        n += 1
print(f"{sys.argv[1]}: {n} lines, all parse")
EOF
done

echo
echo "== cost accounting: Spent == sum of step costs =="
for d in "$R_SER" "$R_PAR"; do
  "$PY" - "$d" <<'EOF'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
st = json.loads((d / "state.json").read_text())["spent"]
ev = [json.loads(l) for l in (d / "events.jsonl").read_text().splitlines()]
run_usd = sum(e.get("cost_usd", 0.0) for e in ev if e["kind"] == "evaluate")
run_tok = sum(e.get("tokens", 0) for e in ev if e["kind"] == "evaluate")
opt_usd = sum(e.get("opt_cost_usd", 0.0) for e in ev if e["kind"] == "step")
print(f"{d.name}: spent.usd={st['usd']} sum(evaluate.cost_usd)={run_usd} "
      f"spent.runner_tokens={st['runner_tokens']} sum(evaluate.tokens)={run_tok} "
      f"spent.optimizer_usd={st['optimizer_usd']} sum(step.opt_cost_usd)={opt_usd}")
assert abs(st["usd"] - run_usd) < 1e-9, "runner usd mismatch"
assert st["runner_tokens"] == run_tok, "runner tokens mismatch"
assert abs(st["optimizer_usd"] - opt_usd) < 1e-6, "optimizer usd mismatch"
print("EXACT")
EOF
done

echo
echo "== no git worktree orphans =="
for d in "$R_SER" "$R_PAR"; do
  echo "$d:"; (cd "$d" && git worktree list 2>/dev/null || echo "  (no git repo)")
  test ! -d "$d/.git/worktrees" && echo "  no .git/worktrees dir"
done

echo
echo "== speedup =="
echo "serial=${T_SER}s parallel4=${T_PAR}s  speedup=$(echo "scale=2; $T_SER / $T_PAR" | bc)x"
echo
echo "serial dir:   $SER"
echo "parallel dir: $PAR"
