"""#589: a long eval (``eval_start`` ... ``evaluate``) must leave a heartbeat in
events.jsonl instead of going completely dark until it returns.

``harness.evaluate_candidate`` logs a throttled ``eval_progress`` event as rollouts
are generated, for the two paths that see individual rollouts complete in real time
(the workers>1 pool and the plain serial loop). ``CAPEVOLVE_EVAL_PROGRESS_INTERVAL``
is set to 0 here so every rollout gets its own event — the default (30s) would never
fire during a test-sized eval.
"""

import contextlib
import io
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

TASK_IDS = ["t0", "t1", "t2", "t3"]


class _Adapter:
    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=i, input={"n": n}) for n, i in enumerate(TASK_IDS)]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        return Rollout(task_id=task.id, output=f"{task.id}:{seed}")

    def score(self, task, rollout):
        from cap_evolve import Score
        n = int(task.input["n"])
        return Score(task_id=task.id, reward=n / 10.0, feedback="ok")

    def apply(self, candidate_dir, edits=None):
        return None


def _events(rd, kind=None):
    evs = [json.loads(l) for l in rd.events_path.read_text().splitlines() if l.strip()]
    return [e for e in evs if kind is None or e["kind"] == kind]


def _evaluate(tmp_path, tag, *, workers, n_trials=1, interval="0"):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    old = os.environ.get("CAPEVOLVE_EVAL_PROGRESS_INTERVAL")
    os.environ["CAPEVOLVE_EVAL_PROGRESS_INTERVAL"] = interval
    try:
        rd = RunDir.create(tmp_path / f".capevolve-{tag}", ts=tag)
        rd.write_splits(Splits(train=[], val=list(TASK_IDS), test=[], seed=7))
        cand = tmp_path / f"c-{tag}"
        cand.mkdir()
        rd.snapshot(tag, cand)
        with contextlib.redirect_stdout(io.StringIO()):
            res = harness.evaluate_candidate(_Adapter(), rd.candidate_dir(tag), run_dir=rd,
                                             split="val", n_trials=n_trials, tag=tag,
                                             workers=workers)
        return rd, res
    finally:
        if old is None:
            os.environ.pop("CAPEVOLVE_EVAL_PROGRESS_INTERVAL", None)
        else:
            os.environ["CAPEVOLVE_EVAL_PROGRESS_INTERVAL"] = old


def test_eval_progress_events_logged_for_parallel_pool(tmp_path):
    rd, res = _evaluate(tmp_path, "par", workers=4)
    progress = _events(rd, "eval_progress")
    assert len(progress) == len(TASK_IDS)  # one heartbeat per completed rollout (interval=0)
    last = progress[-1]
    assert last["split"] == "val" and last["tag"] == "par"
    assert last["completed"] == last["total"] == len(TASK_IDS)
    assert res.reward is not None


def test_eval_progress_events_logged_for_serial_loop(tmp_path):
    rd, res = _evaluate(tmp_path, "ser", workers=1)
    progress = _events(rd, "eval_progress")
    assert len(progress) == len(TASK_IDS)
    assert [p["completed"] for p in progress] == [1, 2, 3, 4]


def test_eval_progress_sits_between_eval_start_and_evaluate(tmp_path):
    rd, _ = _evaluate(tmp_path, "brk", workers=2)
    kinds = [e["kind"] for e in _events(rd)
            if e["kind"] in ("eval_start", "eval_progress", "evaluate")]
    assert kinds[0] == "eval_start"
    assert kinds[-1] == "evaluate"
    assert "eval_progress" in kinds


def test_progress_emitter_throttles_between_the_first_and_last_rollout(monkeypatch):
    """The emitter always fires on the very first call (so a long eval shows
    SOMETHING quickly) and always on the last one (so the final tally is exact) —
    but in between it is throttled to one event per interval, not one per rollout.
    Exercised directly against ``_progress_emitter`` so the clock is controllable,
    unlike a real (fast, tiny) eval where 30s never actually elapses either way.
    """
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        rd = RunDir.create(Path(d) / ".capevolve", ts="emit")
        rd.write_splits(Splits(train=[], val=[], test=[], seed=0))
        clock = {"t": 1_000_000.0}
        monkeypatch.setattr(harness.time, "time", lambda: clock["t"])
        bump = harness._progress_emitter(rd, split="val", tag="x", total=100,
                                         per_task_trials={})
        bump()  # rollout 1: fires immediately
        clock["t"] += 5  # 5s later, well under the 30s default interval
        bump()  # rollout 2: throttled, no event
        clock["t"] += 40  # now 45s since the first event: past the interval
        bump()  # rollout 3: fires

        events = _events(rd, "eval_progress")
        assert [e["completed"] for e in events] == [1, 3]
