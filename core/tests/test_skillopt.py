"""SkillOpt loop — offline, deterministic, zero-API unit + e2e tests.

Drives ``skillopt_loop`` with the shared synthetic adapter + in-process mock
optimizer (``cap_evolve.skillcheck``) and asserts the SkillOpt mechanics:
epochs×mini-batches, the decaying textual learning rate, the bounded per-epoch
rejected-edit buffer, the GATED epoch-boundary slow update, and a sealed test.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _fresh(tmp_path, ts, *, n=8, level=0, max_iterations=50):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir
    adapter = SyntheticAdapter(n=n)
    seed = seed_capability_dir(tmp_path, level=level)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts=ts, budget=Budget(max_iterations=max_iterations))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    return adapter, run_dir, base


def test_schedule_decays():
    from cap_evolve.lr_schedule import build_schedule
    sched = build_schedule("cosine", max_lr=4, min_lr=2, total_steps=8)
    assert len(sched) == 8
    assert sched[0] == 4 and sched[-1] == 2
    assert sched[0] >= sched[-1]
    assert all(2 <= x <= 4 for x in sched)


def test_loop_runs_epochs_and_improves(tmp_path):
    from cap_evolve import skillopt
    from cap_evolve.skillcheck import make_mock_optimizer
    adapter, run_dir, base = _fresh(tmp_path, "e2e")
    assert base.reward == 0.0  # level 0 solves nothing

    # bump=8 solves every task in one edit so the paired gate's small-val SE
    # collapses to 0 (both val tasks move +1) → strict fallback accepts. (bump=2
    # would legitimately be rejected by the paired gate on a 2-task val set — the
    # documented small-val pitfall, exercised in test_small_val_gate_rejects.)
    result = skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=8),
        current_val=base, epochs=2, batch_size=2, accumulation=1,
        edit_budget=4, min_edit_budget=2, lr_schedule="cosine",
        gate_kwargs={"mode": "significant", "k_se": 1.0},
        slow_update=True, slow_update_sample=4, store=None,
    )
    assert result["algorithm"] == "skillopt"
    assert result["epochs"] == 2
    assert len(result["steps"]) >= 2
    assert result["accepts"] >= 1
    # monotone-improving optimizer should climb above the (zero) baseline
    assert result["best_val"] > base.reward
    # result mirrors hill_climb_loop's shape + skillopt extras
    for key in ("best_id", "best_val", "iterations", "accepts", "stop_reason", "steps",
                "edit_budget_schedule", "epoch_stats", "slow_updates"):
        assert key in result


def test_edit_budget_schedule_in_result_decays(tmp_path):
    from cap_evolve import skillopt
    from cap_evolve.skillcheck import make_mock_optimizer
    adapter, run_dir, base = _fresh(tmp_path, "sched")
    result = skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=1),
        current_val=base, epochs=3, batch_size=2, lr_schedule="cosine",
        edit_budget=4, min_edit_budget=2, slow_update=False, store=None,
    )
    sched = result["edit_budget_schedule"]
    assert sched[0] >= sched[-1]
    # each training step logged its budget L
    budgets = [s["edit_budget"] for s in result["steps"] if s.get("step_in_epoch") != "slow"]
    assert budgets and budgets[0] >= budgets[-1]


def test_rejected_buffer_populated_and_bounded(tmp_path):
    """A non-improving optimizer rejects every step → buffer is populated. The
    module's buffer cap bounds it."""
    from cap_evolve import skillopt
    from cap_evolve.skillcheck import make_mock_optimizer
    adapter, run_dir, base = _fresh(tmp_path, "buf")
    result = skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=0),  # never improves
        current_val=base, epochs=1, batch_size=1, accumulation=1,
        edit_budget=4, min_edit_budget=2, slow_update=False, store=None,
    )
    rejects = sum(1 for s in result["steps"] if not s["accepted"])
    assert rejects >= 1
    assert 0 < skillopt._MAX_BUFFER_STEPS <= 50

    # the buffer block builder caps task ids per pattern and patterns per block
    block = skillopt._buffer_block(
        3,
        step_buffer=[{"failure_patterns": [
            {"pattern": "p", "task_ids": ["a", "b", "c", "d", "e"], "n": 5}]}],
        rejected_this_epoch=[{"candidate_id": f"c{i}", "val_delta": -0.1} for i in range(40)],
    )
    # only up to 3 task ids shown per pattern
    assert "a, b, c" in block and "d, e" not in block


def test_slow_update_is_gated_not_forced(tmp_path):
    """The epoch-boundary slow update appears as a normal gate-decided step (it
    carries a decision and is accept/rejected by the val gate), never force-accepted."""
    from cap_evolve import skillopt
    from cap_evolve.skillcheck import make_mock_optimizer
    # bump=0 → the slow update cannot improve val, so the gate MUST reject it.
    adapter, run_dir, base = _fresh(tmp_path, "slow")
    result = skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=0),
        current_val=base, epochs=2, batch_size=2, slow_update=True,
        slow_update_sample=4, store=None,
    )
    assert len(result["slow_updates"]) >= 1
    slow_steps = [s for s in result["steps"] if s.get("step_in_epoch") == "slow"]
    assert slow_steps, "slow update did not produce a step"
    for s in slow_steps:
        assert "decision" in s          # went through the gate
        assert s["accepted"] is False   # a non-improving slow edit is rejected, not forced


def test_categorize_regressed_vs_stable():
    from cap_evolve.skillopt import _categorize
    prev = [{"task_id": "a", "reward": 1.0}, {"task_id": "b", "reward": 0.0},
            {"task_id": "c", "reward": 1.0}, {"task_id": "d", "reward": 0.0}]
    cur = [{"task_id": "a", "reward": 0.0, "feedback": "broke"},   # regressed
           {"task_id": "b", "reward": 0.0},                        # persistent_fail
           {"task_id": "c", "reward": 1.0},                        # stable_success
           {"task_id": "d", "reward": 1.0}]                        # improved
    cats = _categorize(prev, cur)
    assert [pt["task_id"] for pt in cats["regressed"]] == ["a"]
    assert [pt["task_id"] for pt in cats["persistent_fail"]] == ["b"]
    assert [pt["task_id"] for pt in cats["stable_success"]] == ["c"]
    assert "d" in [pt["task_id"] for pt in cats["improved"]]


def test_test_split_never_consumed(tmp_path):
    from cap_evolve import skillopt
    from cap_evolve.skillcheck import make_mock_optimizer
    adapter, run_dir, base = _fresh(tmp_path, "seal")
    skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=8),
        current_val=base, epochs=2, batch_size=2, slow_update=True,
        slow_update_sample=4, store=None,
    )
    assert run_dir.read_splits().test_used is False


def test_small_val_gate_rejects_on_paired_se(tmp_path):
    """PITFALL coverage: on a tiny (2-task) val set, a partial improvement
    (bump=2 → only one val task moves) is correctly REJECTED by the default
    paired significance gate (Δ̄ <= 1·SE), not naively accepted on Δ>0."""
    from cap_evolve import skillopt
    from cap_evolve.skillcheck import make_mock_optimizer
    adapter, run_dir, base = _fresh(tmp_path, "smallval")
    result = skillopt.skillopt_loop(
        adapter, run_dir=run_dir, optimizer=make_mock_optimizer(bump=2),
        current_val=base, epochs=1, batch_size=2,
        gate_kwargs={"mode": "significant", "k_se": 1.0},
        slow_update=False, store=None,
    )
    # every step improves t0 (Δ=+0.5) but the 2-task paired SE equals the mean,
    # so the gate holds the line — no accept on noise.
    assert result["accepts"] == 0
    assert result["best_val"] == base.reward
