#!/usr/bin/env python3
"""Post-search check that the shared R counter refuses an over-budget evaluation BEFORE any rollout.

Opens the run's CommonRollout (same run dir, same R), asks for one evaluation that needs remaining+1..+3
rollouts, and checks that BudgetStop is raised and budget_state.json / rollouts.jsonl are unchanged.
Usage: budget_probe.py RUN_DIR SEED R TASK_ID
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895/arms/common")
from rollout import BudgetStop, CommonRollout  # noqa: E402

run, seed, R, tid = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
before_state = (run / "budget_state.json").read_text()
before_rows = (run / "rollouts.jsonl").read_text().count("\n")
ro = CommonRollout(run, arm="evoskill", search_seed=seed, R=R)
need = ro.remaining() // 3 + 1          # tasks; x3 trials > remaining
try:
    ro.evaluate(run / "champion", [tid] * need, k=3, candidate_id="budget_probe")
    verdict = "NOT_RAISED"
except BudgetStop as e:
    verdict = f"BudgetStop raised: {e}"
after_state = (run / "budget_state.json").read_text()
after_rows = (run / "rollouts.jsonl").read_text().count("\n")
print("BUDGET_PROBE", json.dumps({"verdict": verdict, "requested_rollouts": need * 3,
                                  "state_unchanged": before_state == after_state,
                                  "rollout_rows_unchanged": before_rows == after_rows,
                                  "budget_state": json.loads(after_state)}))
