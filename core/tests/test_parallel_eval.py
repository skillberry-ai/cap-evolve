"""Framework-level rollout parallelism must be free — and invisible in the numbers.

``evaluate_candidate`` can generate a split's rollouts through a thread pool
(``workers > 1``) for plain adapters that implement only ``run_target``. That is a
speed knob and nothing else, so these tests pin the properties that make it safe to
turn on:

  * a parallel run and a serial run of the same deterministic adapter produce an
    IDENTICAL ``SplitResult`` (reward, stderr, per_task) — every published number in
    docs/RESULTS.md was measured serially,
  * ``workers`` defaults to 1, so nothing is parallel unless a user opts in,
  * a ``run_target`` that raises on a worker thread becomes an error rollout for that
    task — missing data (``valid_trials: 0``), never a lost task and never a 0.0,
  * runner/scorer stdout still cannot reach the caller's stdout (the pure-JSON phase
    contract), which is the reason the redirect is wrapped once outside the pool.
"""

import contextlib
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

TASK_IDS = ["t0", "t1", "t2", "t3", "t4"]


class _DeterministicAdapter:
    """Reward is a pure function of (task, seed) — so serial and parallel must agree."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=i, input={"n": n}) for n, i in enumerate(TASK_IDS)]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        return Rollout(task_id=task.id, output=f"{task.id}:{seed}", cost_usd=0.01, tokens=7)

    def score(self, task, rollout):
        from cap_evolve import Score
        if rollout.error:  # unscorable; the harness ignores the reward of an errored trial
            return Score(task_id=task.id, reward=0.0, feedback=rollout.error)
        n = int(task.input["n"])
        seed = int(str(rollout.output).split(":")[1])
        return Score(task_id=task.id, reward=((n + seed) % 3) / 2.0,
                     feedback=f"fb {rollout.output}")

    def apply(self, candidate_dir, edits=None):
        return None


class _RaisingAdapter(_DeterministicAdapter):
    """``run_target`` blows up for one task on every trial (the infra-failure case)."""

    def run_target(self, task, ctx, *, seed=0):
        if task.id == "t2":
            raise RuntimeError("runner exploded")
        return super().run_target(task, ctx, seed=seed)


class _NoisyAdapter(_DeterministicAdapter):
    def run_target(self, task, ctx, *, seed=0):
        print("RUNNER PROGRESS must not leak")
        return super().run_target(task, ctx, seed=seed)

    def score(self, task, rollout):
        print("SCORER CHATTER must not leak")
        return super().score(task, rollout)


def _evaluate(adapter, tmp_path, tag, *, workers, n_trials=3, capture=None):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / f".capevolve-{tag}", ts=tag)
    rd.write_splits(Splits(train=[], val=list(TASK_IDS), test=[], seed=41))
    cand = tmp_path / f"c-{tag}"
    cand.mkdir()
    rd.snapshot(tag, cand)
    with contextlib.redirect_stdout(capture or io.StringIO()):
        res = harness.evaluate_candidate(adapter, rd.candidate_dir(tag), run_dir=rd,
                                         split="val", n_trials=n_trials, tag=tag,
                                         workers=workers)
    return rd, res


def test_default_is_serial():
    """Parallelism is opt-in: the process default must stay 1."""
    from cap_evolve import harness
    assert harness.DEFAULT_WORKERS == 1
    assert harness._resolve_workers(None) == 1
    assert harness._resolve_workers(0) == 1      # never a zero-worker pool
    assert harness._resolve_workers(8) == 8


def test_parallel_result_identical_to_serial(tmp_path):
    """The whole point: same adapter, same numbers, regardless of worker count."""
    _, serial = _evaluate(_DeterministicAdapter(), tmp_path, "ser", workers=1)
    _, par = _evaluate(_DeterministicAdapter(), tmp_path, "par", workers=8)

    assert par.reward == serial.reward
    assert par.stderr == serial.stderr
    assert par.n_tasks == serial.n_tasks and par.n_scored == serial.n_scored
    assert par.pass_k == serial.pass_k
    # per_task must match element-for-element AND in the same (task) order, since the
    # paired gate diffs these lists positionally.
    assert [pt["task_id"] for pt in par.per_task] == TASK_IDS
    assert par.per_task == serial.per_task


def test_raising_run_target_is_missing_data_not_zero(tmp_path):
    """A thread that raises must not become a measured failure of the capability."""
    _, res = _evaluate(_RaisingAdapter(), tmp_path, "err", workers=4)
    by_id = {pt["task_id"]: pt for pt in res.per_task}

    bad = by_id["t2"]
    assert bad["raw"]["valid_trials"] == 0, "an exception is not a measurement"
    assert bad["raw"]["errored"] is True
    assert bad["raw"]["errored_trials"] == 3
    # kept in per_task (forensics) but excluded from the statistics
    assert res.n_tasks == len(TASK_IDS)
    assert res.n_scored == len(TASK_IDS) - 1
    # ...and the surviving tasks are scored exactly as the clean adapter scores them
    # (one exploding task must not perturb its neighbours).
    _, clean = _evaluate(_DeterministicAdapter(), tmp_path, "err_ref", workers=1)
    assert {k: v for k, v in by_id.items() if k != "t2"} == {
        pt["task_id"]: pt for pt in clean.per_task if pt["task_id"] != "t2"}


def test_parallel_run_never_leaks_runner_or_scorer_stdout(tmp_path):
    """The phase skills' stdout is a pure-JSON contract; threads must not corrupt it."""
    buf = io.StringIO()
    _, res = _evaluate(_NoisyAdapter(), tmp_path, "noisy", workers=4, capture=buf)
    assert buf.getvalue() == ""
    assert res.n_scored == len(TASK_IDS)


def test_event_records_the_worker_count(tmp_path):
    """A run record must show whether it was parallel (and stay unchanged when serial)."""
    import json
    rd_par, _ = _evaluate(_DeterministicAdapter(), tmp_path, "evp", workers=4)
    rd_ser, _ = _evaluate(_DeterministicAdapter(), tmp_path, "evs", workers=1)

    def _evals(rd):
        return [json.loads(line) for line in rd.events_path.read_text().splitlines()
                if json.loads(line)["kind"] == "evaluate"]

    assert _evals(rd_par)[-1]["workers"] == 4
    assert "workers" not in _evals(rd_ser)[-1]


def test_an_evaluation_brackets_itself_in_the_event_log(tmp_path):
    """`evaluate_candidate` logs nothing between its start and the closing `evaluate`,
    and that stretch is the longest silence in a run. Without an opening bracket a
    reader cannot tell "scoring in progress" from "process died" — which is how the live
    dashboard came to stamp `failed` on a healthy spreadsheetbench baseline
    (run 33492876620). The bracket must carry the scale of the work, not just its name.
    """
    import json

    rd, res = _evaluate(_DeterministicAdapter(), tmp_path, "brk", workers=2, n_trials=3)
    events = [json.loads(l) for l in rd.events_path.read_text().splitlines() if l.strip()]
    starts = [e for e in events if e["kind"] == "eval_start"]
    assert len(starts) == 1
    s = starts[0]
    assert (s["split"], s["tag"], s["n_tasks"], s["n_trials"], s["workers"]) == (
        "val", "brk", len(TASK_IDS), 3, 2)
    assert s["rollouts"] == len(TASK_IDS) * 3
    # Opening bracket strictly before the closing one, and exactly one pair.
    kinds = [e["kind"] for e in events if e["kind"] in ("eval_start", "evaluate")]
    assert kinds == ["eval_start", "evaluate"]
    assert res.reward is not None
