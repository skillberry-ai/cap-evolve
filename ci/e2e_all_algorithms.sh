#!/usr/bin/env bash
# Drive EVERY algorithm end to end on the zero-API toy_calc example and assert each one
# produced the run-dir artifacts the CLI and the dashboard read.
#
#   bash ci/e2e_all_algorithms.sh [outdir]
#
# Two classes of algorithm, and the difference is the whole reason this script exists:
#
#   deterministic (hill-climb, gepa, skillopt) - `cap-evolve run` sequences the entire
#       loop, so a full baseline -> algorithm -> finalize -> report run is verifiable here.
#
#   agent mode (evograph, agent-optimize) - `cap-evolve run` deliberately stops after
#       baseline and hands the loop to a coding agent (cli.py `orchestration_mode: agent`).
#       There is no subprocess to wait on, so the most this script can assert is that the
#       handoff contract holds: check + baseline ran, and the handoff names a real run_dir.
#       Driving those loops to a gate decision requires an agent and is done separately.
#
# Exits non-zero on the first failure. Prints one JSON summary line per algorithm.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$(mktemp -d -t capevolve-e2e.XXXXXX)}"
mkdir -p "$OUT"

PY="${PYTHON:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY="python3"

export CAPEVOLVE_CORE="$REPO/core"
export PYTHONPATH="$REPO/core"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export CAPEVOLVE_TOY_DATA="$REPO/examples/toy_calc"
export CAPEVOLVE_MOCK_SCRIPT="$REPO/examples/toy_calc/mock_script.json"

DETERMINISTIC="hill-climb gepa skillopt"
AGENT_MODE="evograph agent-optimize"

fail=0

# Lay out a throwaway project for one algorithm and echo its dir.
scaffold() {
  local alg="$1" mode="$2" d="$OUT/$alg"
  rm -rf "$d"; mkdir -p "$d/.capevolve/project/adapters"
  cp    "$REPO/examples/toy_calc/adapter.py"    "$d/.capevolve/project/adapters/"
  cp -R "$REPO/examples/toy_calc/capability"    "$d/seed_capability"
  cp    "$REPO/templates/project/capevolve.yaml" "$d/.capevolve/project/capevolve.yaml"
  # Flat key rewrite only - the zero-dependency spec reader does not parse inline maps.
  "$PY" - "$d/.capevolve/project/capevolve.yaml" "$alg" "$mode" <<'PYEOF'
import re, sys
path, alg, mode = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path).read()
def setkey(text, key, val):
    pat = re.compile(rf"^({re.escape(key)}:)([^\n]*)$", re.M)
    return pat.sub(lambda m: f"{key}: {val}", text) if pat.search(text) else text + f"\n{key}: {val}\n"
src = setkey(src, "algorithm_skill", alg)
src = setkey(src, "orchestration_mode", mode)
open(path, "w").write(src)
PYEOF
  echo "$d"
}

for alg in $DETERMINISTIC; do
  d="$(scaffold "$alg" deterministic)"
  log="$OUT/$alg.log"
  if ! "$PY" -m cap_evolve.cli run \
        --spec "$d/.capevolve/project/capevolve.yaml" \
        --project "$d/.capevolve/project" --run-ts e2e >"$log" 2>&1; then
    echo "FAIL $alg: cap-evolve run exited non-zero; see $log" >&2
    tail -20 "$log" >&2; fail=1; continue
  fi
  # The run dir is under the project, not the cwd.
  rd="$(find "$d" -type d -name 'run_e2e' -print -quit)"
  if [ -z "$rd" ]; then
    echo "FAIL $alg: no run_e2e dir under $d" >&2; fail=1; continue
  fi
  if ! "$PY" - "$rd" "$alg" <<'PYEOF'
import json, pathlib, sys
rd, alg = pathlib.Path(sys.argv[1]), sys.argv[2]
missing = [n for n in ("events.jsonl", "baseline.json", "final.json") if not (rd / n).exists()]
assert not missing, f"{alg}: run dir missing {missing}"
final = json.loads((rd / "final.json").read_text())
for k in ("best_id", "baseline_id", "test", "test_baseline", "test_delta"):
    assert k in final, f"{alg}: final.json has no {k} (keys={sorted(final)})"
base_val = (json.loads((rd / "baseline.json").read_text()).get("val") or {})
kinds = {json.loads(l)["kind"] for l in (rd / "events.jsonl").read_text().splitlines() if l.strip()}
# Every algorithm must emit a per-candidate step event or the dashboard/TUI render nothing.
assert kinds & {"step", "skillopt_step", "gepa_val_gate"}, f"{alg}: no step events, kinds={sorted(kinds)}"
# toy_calc is deterministic: the seed lacks the [CALC] marker and scores 0.0; the mock
# optimizer adds it, so a working loop MUST accept a candidate and seal test at 1.0.
assert base_val.get("reward") == 0.0, f"{alg}: baseline val {base_val.get('reward')!r}, expected 0.0"
assert final["test"]["reward"] == 1.0, f"{alg}: sealed test {final['test']['reward']!r}, expected 1.0"
assert final["best_id"] != final["baseline_id"], f"{alg}: nothing was accepted (best == baseline)"
print(json.dumps({"algorithm": alg, "mode": "deterministic", "ok": True,
                  "run_dir": str(rd), "best_id": final["best_id"],
                  "baseline_val": base_val.get("reward"),
                  "test_reward": final["test"]["reward"], "test_delta": final["test_delta"],
                  "event_kinds": sorted(kinds)}))
PYEOF
  then
    echo "FAIL $alg: artifact assertions failed" >&2; fail=1
  fi
done

for alg in $AGENT_MODE; do
  d="$(scaffold "$alg" agent)"
  log="$OUT/$alg.log"
  if ! "$PY" -m cap_evolve.cli run \
        --spec "$d/.capevolve/project/capevolve.yaml" \
        --project "$d/.capevolve/project" --run-ts e2e >"$log" 2>&1; then
    echo "FAIL $alg: agent-mode setup+baseline exited non-zero; see $log" >&2
    tail -20 "$log" >&2; fail=1; continue
  fi
  if ! "$PY" - "$log" "$alg" "$d" <<'PYEOF'
import json, pathlib, sys
log, alg, proj = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
# The handoff is the LAST json object printed; earlier lines are phase output.
hand = None
for line in log.read_text().splitlines():
    line = line.strip()
    if line.startswith("{") and '"mode"' in line and '"run_dir"' in line:
        try: hand = json.loads(line)
        except ValueError: pass
assert hand, f"{alg}: no agent-mode handoff JSON in {log}"
assert hand["mode"] == "agent", f"{alg}: handoff mode is {hand['mode']!r}, not 'agent'"
assert hand["algorithm"] == alg, f"{alg}: handoff names {hand['algorithm']!r}"
# The handoff prints run_dir relative to the workdir, so resolve it against the project.
rd = pathlib.Path(hand["run_dir"])
if not rd.is_absolute():
    rd = proj / rd
assert rd.is_dir(), f"{alg}: handoff run_dir does not exist: {rd}"
assert (rd / "baseline.json").exists(), f"{alg}: baseline.json missing - baseline did not run"
base = json.loads((rd / "baseline.json").read_text())
# Agent mode must NOT have run the loop or sealed the test - that is the agent's job.
assert not (rd / "final.json").exists(), f"{alg}: agent mode sealed test itself (final.json exists)"
print(json.dumps({"algorithm": alg, "mode": "agent", "ok": True, "run_dir": str(rd),
                  "baseline_val": (base.get("val") or {}).get("reward"),
                  "note": "handoff verified; the loop itself requires an agent to drive"}))
PYEOF
  then
    echo "FAIL $alg: handoff assertions failed" >&2; fail=1
  fi
done

echo "artifacts: $OUT"
[ "$fail" -eq 0 ] || { echo "E2E FAILED" >&2; exit 1; }
echo "E2E OK: all 5 algorithms verified (3 full loops, 2 agent-mode handoffs)"
