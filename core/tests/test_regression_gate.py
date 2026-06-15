"""The no-regression (dual) gate rejects a mean-improving candidate that breaks a
previously-passing task (SWE-bench FAIL_TO_PASS + PASS_TO_PASS discipline)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


class _Adapter:
    """3 tasks A/B/C; a task passes iff the config file contains its letter."""
    def __init__(self, cfg_name="cfg.txt"):
        self.cfg = cfg_name

    def tasks(self, split):
        from agent_capo import Task
        return [Task(id=t) for t in ("A", "B", "C")]

    def run_target(self, task, candidate_dir, split):
        from agent_capo import Rollout
        cfg = (Path(candidate_dir) / self.cfg).read_text() if (Path(candidate_dir) / self.cfg).exists() else ""
        return Rollout(task_id=task.id, output=("pass" if task.id in cfg else "fail"))

    def score(self, task, rollout):
        from agent_capo import Score
        ok = rollout.output == "pass"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir, edits=None):
        return None


def test_no_regression_gate_rejects_breaking_candidate(tmp_path):
    from agent_capo import RunDir, harness

    adapter = _Adapter()
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.txt").write_text("A")          # A passes, B & C fail -> baseline 1/3

    run_dir = RunDir.create(tmp_path / ".agentcapo", ts="rg")
    # all three tasks in val so the gate sees them
    from agent_capo.splits import Splits
    run_dir.write_splits(Splits(train=[], val=["A", "B", "C"], test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")

    base = harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                                      split="val", tag="seed")
    assert abs(base.reward - 1 / 3) < 1e-9

    # optimizer rewrites cfg to "B C" -> B,C pass, A regresses. mean 2/3 > 1/3.
    opt = harness.optimizer_from_command(
        ["python3", "-c",
         "import sys,pathlib; (pathlib.Path(sys.argv[1])/'cfg.txt').write_text('B C')",
         "{workdir}"])

    # without the dual gate: accepted (mean improved)
    step1 = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                             optimizer=opt, instructions="x", current_val=base,
                             gate_kwargs={"mode": "strict"})
    assert step1["accepted"] is True
    assert abs(harness.SplitResult.from_dict(step1["candidate_val"]).reward - 2 / 3) < 1e-9

    # with the dual gate: rejected because task A regressed
    step2 = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                             optimizer=opt, instructions="x", current_val=base,
                             gate_kwargs={"mode": "strict"}, no_regression=True)
    assert step2["accepted"] is False
    assert "A" in step2["regressions"]
