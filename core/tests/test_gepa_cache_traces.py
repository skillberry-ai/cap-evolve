"""A GEPA eval-cache HIT must yield the same reflective signal as a fresh eval (#111).

The cache used to store only ``{reward, feedback}``, so ``_eval_minibatch`` rebuilt a
``Score`` with ``raw={"cached": True}`` and no ``output``/``trace``. ``_write_reflection``
then emitted ``- Agent output:`` (empty) for cached failing tasks — GEPA's whole learning
signal, blank, on exactly the parents it re-samples most.

These tests pin the fix at both levels: the cache entry carries a pointer to the rollout
json that produced the score, and a hit re-reads it (and re-materializes it under the new
eval tag so the tag-pinned ``trajectories/`` dir still exists).
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _adapter():
    """A deterministic adapter whose rollouts carry a distinctive output AND trace."""
    from cap_evolve import CapabilityAdapter, Rollout, Score, Task

    class _A(CapabilityAdapter):
        def tasks(self, split):  # noqa: ARG002
            return [Task(id=f"t{i}", input=f"in-{i}", target="ok") for i in range(4)]

        def run_target(self, task, ctx, *, seed=0):  # noqa: ARG002
            return Rollout(task_id=task.id,
                           output=f"WRONG-ANSWER-for-{task.id}",
                           trace=f"STEP1 read {task.input}; STEP2 guessed")

        def score(self, task, rollout):  # noqa: ARG002
            return Score(task_id=task.id, reward=0.0,
                         feedback=f"expected ok, got {rollout.output}",
                         trial_rewards=[0.0])

        def materialize(self, candidate_dir, edits=None):  # noqa: ARG002
            return None

    return _A()


@pytest.fixture
def setup(tmp_path):
    from cap_evolve import Budget, RunDir
    from cap_evolve.cache import EvalCache
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "cap.md").write_text("seed capability\n", encoding="utf-8")
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="c1", budget=Budget(max_iterations=4))
    return _adapter(), run_dir, cand, EvalCache(run_dir.root / "eval_cache.json")


def test_cache_hit_reflective_dataset_has_output_and_trace(setup):
    """Fail-before / pass-after: a fully-cached minibatch must still produce a
    REFLECTION.md with the agent's real output AND trajectory."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    ids = ["t0", "t1", "t2"]

    first = gepa._eval_minibatch(adapter, cand, ids, run_dir=run_dir, cache=cache,
                                 tag="mb_p_0000", seed=0)
    # Second eval of the same candidate + tasks: every task is a cache hit (0 rollouts).
    before = run_dir.spent.metric_calls
    second = gepa._eval_minibatch(adapter, cand, ids, run_dir=run_dir, cache=cache,
                                  tag="mb_p_0001", seed=0)
    assert run_dir.spent.metric_calls == before, "expected a full cache hit"
    assert second.reward == first.reward

    for pt in second.per_task:
        raw = pt.get("raw") or {}
        assert raw.get("cached") is True
        assert f"WRONG-ANSWER-for-{pt['task_id']}" in str(raw.get("output"))
        assert "STEP1 read" in str(raw.get("trace"))

    wd = run_dir.root / "work" / "x"
    wd.mkdir(parents=True)
    gepa._write_reflection(wd, second)
    refl = (wd / "REFLECTION.md").read_text(encoding="utf-8")
    assert "- Agent output: \n" not in refl, "hollow reflective dataset"
    assert "WRONG-ANSWER-for-t0" in refl
    assert "- Trajectory: STEP1 read in-0" in refl


def test_cache_hit_rematerializes_rollouts_under_new_tag(setup):
    """The cached hit must leave ``rollouts/train/*__<tag>__t0.json`` for the NEW tag, so
    ``harness._copy_step_trajectories(tag=...)`` still finds this minibatch verbatim."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0", "t1"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    gepa._eval_minibatch(adapter, cand, ["t0", "t1"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0001", seed=0)
    got = sorted(p.name for p in (run_dir.rollouts / "train").glob("*__mb_p_0001__t0.json"))
    assert got == ["t0__mb_p_0001__t0.json", "t1__mb_p_0001__t0.json"]
    rec = json.loads((run_dir.rollouts / "train" / "t0__mb_p_0001__t0.json")
                     .read_text(encoding="utf-8"))
    assert rec["rollout"]["output"] == "WRONG-ANSWER-for-t0"
    assert "STEP1" in rec["rollout"]["trace"]


def test_cache_entry_stores_rollout_pointer_not_payload(setup):
    """Cache format: reward + feedback + a POINTER. The trace is NOT copied into the
    cache, so the cache stays tiny however large the traces get."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    raw = json.loads((run_dir.root / "eval_cache.json").read_text(encoding="utf-8"))
    (entry,) = raw.values()
    assert set(entry) == {"reward", "feedback", "rollout_file"}
    assert entry["rollout_file"] == "t0__mb_p_0000__t0.json"
    assert "STEP1" not in json.dumps(entry), "trace must not be duplicated into the cache"


def test_pointerless_or_missing_rollout_is_treated_as_a_miss(setup):
    """A pre-#111 (score-only) entry, or one whose rollout json was pruned, must be
    RE-RUN rather than served as an empty reflective row."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup

    # (a) legacy score-only entry
    from cap_evolve.cache import hash_candidate_dir
    chash = hash_candidate_dir(cand)
    cache._data[f"{chash}::t0"] = {"reward": 0.0, "feedback": "legacy"}
    cache._flush()
    before = run_dir.spent.metric_calls
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0000", seed=0)
    assert run_dir.spent.metric_calls == before + 1, "legacy entry must miss"
    assert "WRONG-ANSWER-for-t0" in str((res.per_task[0]["raw"] or {}).get("output"))

    # (b) pointer present but the rollout json is gone
    (run_dir.rollouts / "train" / "t0__mb_p_0000__t0.json").unlink()
    before = run_dir.spent.metric_calls
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0002", seed=0)
    assert run_dir.spent.metric_calls == before + 1, "dangling pointer must miss"
    assert "WRONG-ANSWER-for-t0" in str((res.per_task[0]["raw"] or {}).get("output"))


def test_trace_is_bounded_in_the_reflective_signal(setup):
    """Cache size + prompt size stay bounded: the replayed output/trace go through the
    same ``_short`` truncation a fresh eval uses."""
    from cap_evolve import gepa
    adapter, run_dir, cand, cache = setup
    huge = "X" * 50_000
    orig = adapter.run_target

    def _big(task, ctx, *, seed=0):
        r = orig(task, ctx, seed=seed)
        r.trace = huge
        return r
    adapter.run_target = _big
    gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                         tag="mb_p_0000", seed=0)
    res = gepa._eval_minibatch(adapter, cand, ["t0"], run_dir=run_dir, cache=cache,
                               tag="mb_p_0001", seed=0)
    trace = str((res.per_task[0]["raw"] or {}).get("trace"))
    assert len(trace) < 2000 and trace.endswith("…[truncated]")
    # and the cache itself never grew by the trace
    assert (run_dir.root / "eval_cache.json").stat().st_size < 1000
