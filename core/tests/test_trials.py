"""Tests for the concurrent multi-trial helper (cap_evolve.run_trials_pool)."""
import contextlib
import io

from cap_evolve import run_trials_pool
from cap_evolve.types import Rollout, Task


def _tasks(ids):
    return [Task(id=i) for i in ids]


def test_shape_and_per_trial_seed_order():
    def run_one(task, seed):
        return Rollout(task_id=task.id, output=f"{task.id}:{seed}")

    out = run_trials_pool(run_one, _tasks(["a", "b"]), n_trials=3, base_seed=100, max_workers=1)
    assert set(out) == {"a", "b"}
    # trial-ordered; trial k uses seed = base_seed + k
    assert [r.output for r in out["a"]] == ["a:100", "a:101", "a:102"]
    assert [r.output for r in out["b"]] == ["b:100", "b:101", "b:102"]


def test_concurrent_matches_sequential():
    def run_one(task, seed):
        return Rollout(task_id=task.id, output=str(seed))

    seq = run_trials_pool(run_one, _tasks(["x"]), n_trials=5, base_seed=0, max_workers=1)
    par = run_trials_pool(run_one, _tasks(["x"]), n_trials=5, base_seed=0, max_workers=4)
    assert [r.output for r in seq["x"]] == [r.output for r in par["x"]] == ["0", "1", "2", "3", "4"]


def test_exception_becomes_error_rollout():
    def run_one(task, seed):
        if seed == 1:
            raise RuntimeError("boom")
        return Rollout(task_id=task.id, output="ok")

    out = run_trials_pool(run_one, _tasks(["a"]), n_trials=3, base_seed=0, max_workers=2)
    assert out["a"][1].error and "boom" in out["a"][1].error   # the failing trial
    assert out["a"][0].error is None and out["a"][2].error is None  # neighbours unaffected


def test_zero_trials_is_empty_lists():
    out = run_trials_pool(lambda t, s: Rollout(task_id=t.id), _tasks(["a", "b"]),
                          n_trials=0, base_seed=0, max_workers=4)
    assert out == {"a": [], "b": []}


def test_on_progress_fires_once_per_completed_job():
    """#589: the harness needs a heartbeat as rollouts complete, both serial and
    concurrent — one call per (task, trial) job, regardless of worker count.
    """
    def run_one(task, seed):
        return Rollout(task_id=task.id, output="ok")

    for workers in (1, 4):
        calls = []
        run_trials_pool(run_one, _tasks(["a", "b", "c"]), n_trials=2, base_seed=0,
                        max_workers=workers, on_progress=lambda: calls.append(1))
        assert len(calls) == 6  # 3 tasks * 2 trials


def test_on_progress_not_required():
    """Omitting ``on_progress`` (the default) must not change behavior."""
    out = run_trials_pool(lambda t, s: Rollout(task_id=t.id), _tasks(["a"]),
                          n_trials=1, base_seed=0, max_workers=2)
    assert out["a"][0].task_id == "a"


def test_caller_stdout_protected_from_concurrent_rollout_output():
    # Adapters' runners (e.g. tau2) print progress to stdout; run in parallel that would
    # race the per-call redirect_stdout and leak into the pure-JSON stdout contract. The
    # pool must keep the caller's stdout clean regardless.
    def noisy(task, seed):
        print("RUNNER PROGRESS must not leak to stdout")
        return Rollout(task_id=task.id, output="ok")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = run_trials_pool(noisy, _tasks(["a", "b"]), n_trials=3, base_seed=0, max_workers=4)
    assert buf.getvalue() == ""  # nothing leaked to the caller's stdout
    assert all(r.output == "ok" for r in out["a"] + out["b"])
