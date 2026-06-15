#!/usr/bin/env bash
# Full tau2-airline COMPOSITE run (policy + tools), reusing a cached baseline to
# save the ~40-min baseline pass. Optimizer: claude-code @ claude-opus-4-6;
# agent+user: gpt-oss-120b (watsonx/RITS); all 50 tasks in train/val/test;
# 10 iterations; num_trials 4; tau concurrency 7; git iteration store.
#
# Usage:  REPO=/path/to/agent-capo BASELINE=/tmp/tau2_baseline_cache ./reuse_baseline.sh
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
BASELINE="${BASELINE:-/tmp/tau2_baseline_cache}"     # dir with baseline.json + rollouts/ (val=0.46)
R="${R:-/tmp/tau2_comp}"

export AGENT_CAPO_CORE="$REPO/core" PYTHONPATH="$REPO/core" ACAPO_SKILLS_DIR="$REPO/skills"
export ACAPO_TAU2_DATA="$REPO/examples/tau2_airline/data" TAU2_MAX_CONCURRENCY=7
unset ACAPO_TAU2_TASK_IDS   # => all 50 tasks

rm -rf "$R"; mkdir -p "$R/.agentcapo/project/adapters"
cp "$REPO/examples/tau2_airline/adapter.py"            "$R/.agentcapo/project/adapters/"
cp "$REPO/examples/tau2_airline/tau2_runtime.py"       "$R/.agentcapo/project/adapters/"
cp -R "$REPO/examples/tau2_airline/seed_caps"     "$R/seed_composite"
cp    "$REPO/examples/tau2_airline/run_full/split_ids_all50.json" "$R/split_ids.json"
cp    "$REPO/examples/tau2_airline/run_full/acapo.yaml"  "$R/.agentcapo/project/acapo.yaml"

# Seed the run dir with the cached baseline (val 0.46) so we skip re-scoring it.
python3 - "$R" "$BASELINE" "$R/seed_composite" "$R/split_ids.json" <<'PY'
import json, shutil, sys, time
from pathlib import Path
sys.path.insert(0, __import__("os").environ["AGENT_CAPO_CORE"])
from agent_capo import RunDir, Budget
from agent_capo.splits import Splits
R, BASELINE, SEED, SPLIT = map(Path, sys.argv[1:5])
rd = RunDir.create(R / ".agentcapo", ts="comp", budget=Budget(max_iterations=10, stall=0))
ids = json.loads(SPLIT.read_text())
rd.write_splits(Splits(train=ids["train"], val=ids["val"], test=ids["test"], seed=0))
rd.snapshot("seed", SEED); rd.set_best("seed")
shutil.copy(BASELINE / "baseline.json", rd.root / "baseline.json")
# reuse the cached seed val rollouts (same behavior as the composite seed) for diagnosis
dst = rd.rollouts / "val"; dst.mkdir(parents=True, exist_ok=True)
for f in (BASELINE / "rollouts" / "val").glob("*__seed__*.json"):
    shutil.copy(f, dst / f.name)
print("RUN_DIR", rd.root, "baseline_val", json.load(open(rd.root/"baseline.json"))["val"]["reward"])
PY

# Run algorithm -> finalize -> report directly against the seeded run dir.
RD="$R/.agentcapo/run_comp"
OPT="python3 $REPO/skills/optimizers/claude-code/scripts/run.py --workdir {workdir} --prompt {prompt} --model claude-opus-4-6"
python3 "$REPO/skills/algorithms/all-at-once/scripts/run.py" --run-dir "$RD" --project "$R/.agentcapo/project" \
    --optimizer "$OPT" --max-iterations 10 --n-trials 4 --gate-mode significant --k-se 1.0 --store git \
    > "$R/algo.out" 2> "$R/algo.err"
python3 "$REPO/skills/phases/finalize/scripts/run.py" --run-dir "$RD" --project "$R/.agentcapo/project" --n-trials 4 \
    > "$R/finalize.out" 2>> "$R/algo.err"
python3 "$REPO/skills/phases/report/scripts/run.py" --run-dir "$RD" > "$R/report.out" 2>> "$R/algo.err"
echo "DONE -> $RD/report.md , $RD/dashboard.html"
