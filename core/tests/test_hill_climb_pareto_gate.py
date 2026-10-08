"""hill-climb's per-iteration gate dispatches to multi-objective pareto mode when
``gate_kwargs["mode"] == "pareto"`` (issue #684 item 8), and falls back to today's
single-metric behaviour exactly as before when it isn't set (regression test).

``harness.run_step`` is the one place hill-climb calls the gate from (via
``hill_climb_loop``), so these drive it directly rather than the full CLI/loop.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


class _ParetoAdapter:
    """2 tasks A/B. ``cfg.txt`` lists which pass; ``cost.txt`` is a flat per-task $."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in ("A", "B")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        d = Path(ctx)
        cfg = (d / "cfg.txt").read_text() if (d / "cfg.txt").exists() else ""
        cost = float((d / "cost.txt").read_text()) if (d / "cost.txt").exists() else 1.0
        return Rollout(task_id=task.id, output=("pass" if task.id in cfg else "fail"),
                       cost_usd=cost)

    def score(self, task, rollout):
        from cap_evolve import Score
        ok = rollout.output == "pass"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                    trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir, edits=None):
        return None


def _setup(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits

    adapter = _ParetoAdapter()
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.txt").write_text("A")      # A passes, B fails -> reward 0.5
    (seed / "cost.txt").write_text("2.0")   # $2/task

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="pg")
    run_dir.write_splits(Splits(train=[], val=["A", "B"], test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")

    base = harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                                      split="val", tag="seed")
    assert abs(base.reward - 0.5) < 1e-9
    return adapter, run_dir, base


def test_pareto_mode_accepts_a_candidate_that_dominates_on_both_objectives(tmp_path):
    from cap_evolve import harness

    adapter, run_dir, base = _setup(tmp_path)

    # Both tasks pass (reward 0.5 -> 1.0) AND cost drops ($2 -> $1): dominates on both.
    opt = harness.optimizer_from_command(
        ["python3", "-c",
         "import sys, pathlib\n"
         "d = pathlib.Path(sys.argv[1])\n"
         "(d / 'cfg.txt').write_text('A B')\n"
         "(d / 'cost.txt').write_text('1.0')\n",
         "{workdir}"])

    step = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                            optimizer=opt, instructions="x", current_val=base,
                            gate_kwargs={"mode": "pareto"})
    assert step["accepted"] is True, step["decision"]["reason"]
    assert "pareto" in step["decision"]["reason"]
    assert abs(harness.SplitResult.from_dict(step["candidate_val"]).reward - 1.0) < 1e-9


def test_pareto_mode_rejects_a_candidate_dominated_by_current(tmp_path):
    from cap_evolve import harness

    adapter, run_dir, base = _setup(tmp_path)

    # Both tasks still fail except A (reward unchanged) but cost DOUBLES: dominated.
    opt = harness.optimizer_from_command(
        ["python3", "-c",
         "import sys, pathlib\n"
         "d = pathlib.Path(sys.argv[1])\n"
         "(d / 'cost.txt').write_text('4.0')\n",
         "{workdir}"])

    step = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                            optimizer=opt, instructions="x", current_val=base,
                            gate_kwargs={"mode": "pareto"})
    assert step["accepted"] is False, step["decision"]["reason"]
    assert "pareto" in step["decision"]["reason"]


def test_no_objectives_declared_falls_back_to_existing_single_metric_behaviour(tmp_path):
    """Regression test: a project with no ``objectives``/pareto gate_mode gets EXACTLY
    the pre-#684 gate call — no metrics_candidate/current are even computed."""
    from cap_evolve import harness

    adapter, run_dir, base = _setup(tmp_path)

    opt = harness.optimizer_from_command(
        ["python3", "-c",
         "import sys, pathlib\n"
         "d = pathlib.Path(sys.argv[1])\n"
         "(d / 'cfg.txt').write_text('A B')\n"
         "(d / 'cost.txt').write_text('999.0')\n",   # cost would dominate-reject in pareto mode
         "{workdir}"])

    # strict mode: any improvement accepts, cost is irrelevant -- exactly today's behaviour.
    step = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                            optimizer=opt, instructions="x", current_val=base,
                            gate_kwargs={"mode": "strict"})
    assert step["accepted"] is True
    assert not step["decision"]["reason"].startswith("pareto")


def test_pareto_metrics_kwargs_empty_without_cost_data(tmp_path):
    """No ``cost_usd`` on either side -> ``{}``, so gate.py's own ParetoObjectiveError
    (not a fabricated 0.0) is what refuses an unresolvable secondary objective."""
    from cap_evolve.harness import _pareto_metrics_kwargs
    from cap_evolve.loop import SplitResult

    empty = SplitResult(split="val", reward=0.5, stderr=0.0,
                        per_task=[{"task_id": "A", "reward": 1.0, "raw": {"valid_trials": 1}}])
    assert _pareto_metrics_kwargs(empty, empty) == {}
