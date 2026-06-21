"""Behavioral contract for skillopt.

Drives the real ``skillopt_loop`` end-to-end with the offline MOCK optimizer on a
tiny synthetic adapter (zero API) and asserts the SkillOpt mechanics actually
hold — not merely that ``run.py`` imports:

  * the epoch/step loop runs end-to-end (epochs × mini-batches produce steps);
  * the edit-budget (textual learning rate) schedule DECAYS (cosine: start>end);
  * the within-epoch rejected-edit buffer is populated AND bounded;
  * the epoch-boundary slow update is GATED on val (it appears as a normal,
    gate-decided step — never force-accepted);
  * the test split is NEVER consumed (seal stays unused).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import (
    Checker, import_run, make_mock_optimizer, SyntheticAdapter, seed_capability_dir,
)


def main() -> int:
    c = Checker("skillopt")
    run = import_run()
    c.require_main(run)

    from cap_evolve import skillopt
    from cap_evolve import RunDir, Budget, harness
    from cap_evolve.lr_schedule import build_schedule

    c.check(hasattr(skillopt, "skillopt_loop"), "core missing skillopt.skillopt_loop")
    c.check(set(run.SCHEDULES) == {"constant", "linear", "cosine"},
            f"unexpected schedules: {run.SCHEDULES}", note=f"schedules: {run.SCHEDULES}")

    # The textual learning rate (edit budget) decays under cosine.
    sched = build_schedule("cosine", max_lr=4, min_lr=2, total_steps=8)
    c.check(sched and sched[0] > sched[-1],
            f"edit-budget schedule did not decay: {sched}",
            note=f"edit-budget anneal (cosine 4->2 over 8): {sched}")

    tmp = Path(tempfile.mkdtemp(prefix="skillopt_chk_"))
    try:
        adapter = SyntheticAdapter(n=8)
        seed = seed_capability_dir(tmp, level=0)
        run_dir = RunDir.create(tmp / ".capevolve", ts="chk",
                                budget=Budget(max_iterations=50))
        harness.ensure_splits(adapter, run_dir, seed=0)
        base = harness.baseline(adapter, seed, run_dir=run_dir)

        # 2 epochs so the epoch-2 boundary triggers a slow update; small batch so we
        # get multiple steps per epoch (exercising the buffer).
        result = skillopt.skillopt_loop(
            adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=1),
            current_val=base, epochs=2, batch_size=2, accumulation=1,
            edit_budget=4, min_edit_budget=2, lr_schedule="cosine",
            gate_kwargs={"mode": "significant", "k_se": 1.0},
            slow_update=True, slow_update_sample=4, store=None,
        )

        # 1) the epoch/step loop ran end to end
        c.check(len(result["steps"]) >= 2 and result["epochs"] == 2,
                f"loop did not run epochs×steps: {result.get('epochs')}, "
                f"{len(result.get('steps', []))} steps",
                note=f"ran {result['epochs']} epochs, {len(result['steps'])} steps, "
                     f"{result['accepts']} accepts")
        c.check(result["best_val"] >= base.reward,
                f"best_val regressed below baseline: {result['best_val']} < {base.reward}")

        # 2) the schedule in the result decays (cosine over the run)
        rs = result["edit_budget_schedule"]
        c.check(rs and rs[0] >= rs[-1] and min(rs) >= 2,
                f"result edit-budget schedule wrong: {rs}")

        # 3) the rejected-edit buffer was populated AND bounded. We assert this from
        # the events: skillopt_step events carry accept; once the synthetic adapter
        # plateaus (all 8 tasks solved at level 8), further steps reject — those feed
        # the per-epoch buffer. We re-run a longer single-epoch loop that plateaus.
        run_dir2 = RunDir.create(tmp / ".capevolve", ts="chk2", budget=Budget(max_iterations=50))
        harness.ensure_splits(adapter, run_dir2, seed=0)
        base2 = harness.baseline(adapter, seed, run_dir=run_dir2)
        result2 = skillopt.skillopt_loop(
            adapter, run_dir=run_dir2, optimizer=make_mock_optimizer(bump=0),  # never improves
            current_val=base2, epochs=1, batch_size=2, accumulation=1,
            edit_budget=4, min_edit_budget=2, lr_schedule="cosine",
            gate_kwargs={"mode": "significant", "k_se": 1.0}, slow_update=False, store=None,
        )
        rejects = sum(1 for s in result2["steps"] if not s["accepted"])
        c.check(rejects >= 1, "a non-improving optimizer produced no rejects to buffer",
                note=f"non-improving optimizer → {rejects} rejected edits buffered")
        # bounded: the module caps the buffer; assert the cap constant is finite+small
        c.check(0 < skillopt._MAX_BUFFER_STEPS <= 50,
                f"buffer cap unreasonable: {skillopt._MAX_BUFFER_STEPS}",
                note=f"per-epoch buffer bounded to {skillopt._MAX_BUFFER_STEPS} steps")

        # 4) the slow update is GATED on val (appeared as a gate-decided step with a
        # decision, not a force-accept). Find it in the first run's slow_updates.
        su = result["slow_updates"]
        c.check(len(su) >= 1, "no slow update ran at the epoch-2 boundary",
                note=f"slow updates: {su}")
        if su:
            slow_step = next((s for s in result["steps"]
                              if s.get("step_in_epoch") == "slow"), None)
            c.check(slow_step is not None and "decision" in slow_step,
                    "slow-update step missing a gate decision (force-accepted?)",
                    note="slow update is gated on val (carries a gate decision)")

        # 5) test was NEVER consumed
        splits = run_dir.read_splits()
        c.check(not splits.test_used, "skillopt consumed the sealed test split",
                note="test split sealed throughout (never consumed)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
