"""Explicit split_ids: pin a split, and support the no-holdout fit case."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


class _Adapter:
    def tasks(self, split):
        from agent_capo import Task
        return [Task(id=str(i)) for i in range(6)]
    def run_target(self, t, d, s):
        from agent_capo import Rollout
        return Rollout(task_id=t.id)
    def score(self, t, r):
        from agent_capo import Score
        return Score(task_id=t.id, reward=1.0, trial_rewards=[1.0])
    def apply(self, d, edits=None):
        return None


def test_explicit_split_ids(tmp_path):
    from agent_capo import RunDir, harness
    rd = RunDir.create(tmp_path / ".agentcapo", ts="s")
    sp = harness.ensure_splits(_Adapter(), rd, split_ids={"train": [0, 1, 2], "val": [3, 4], "test": [5]})
    assert sp.train == ["0", "1", "2"] and sp.val == ["3", "4"] and sp.test == ["5"]
    # frozen: a second call returns the same (no re-split)
    assert harness.ensure_splits(_Adapter(), rd).to_dict() == sp.to_dict()


def test_no_holdout_fit_case(tmp_path):
    """train==val==test==all is allowed (a deliberate fit), and test still seals."""
    from agent_capo import RunDir, TestSealError, harness
    allids = [str(i) for i in range(6)]
    rd = RunDir.create(tmp_path / ".agentcapo", ts="fit")
    harness.ensure_splits(_Adapter(), rd, split_ids={"train": allids, "val": allids, "test": allids})
    seed = tmp_path / "seed"; seed.mkdir()
    harness.baseline(_Adapter(), seed, run_dir=rd)
    rd.consume_test()
    with __import__("pytest").raises(TestSealError):
        rd.consume_test()
