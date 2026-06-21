"""Wave-1 engine invariants: seed threading, seal-on-success, paired gate,
structured infra signal, atomic state, materialize/live split, and the new
selection / lr_schedule / cache modules.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


# ---- per-trial seed threading --------------------------------------------

class _SeedAdapter:
    """Records the seeds it was handed and returns reward depending on the seed
    (so distinct trials are genuinely distinct — proving the seed is threaded)."""

    def __init__(self):
        self.seeds_seen = []

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id="t0")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        self.seeds_seen.append(seed)
        # reward alternates with the seed so trials differ -> nonzero variance
        return Rollout(task_id=task.id, output=str(seed % 2))

    def score(self, task, rollout):
        from cap_evolve import Score
        r = 1.0 if rollout.output == "1" else 0.0
        return Score(task_id=task.id, reward=r, trial_rewards=[r])

    def apply(self, candidate_dir, edits=None):
        return None


def test_per_trial_seed_is_threaded(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    adapter = _SeedAdapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="seed")
    rd.write_splits(Splits(train=[], val=["t0"], test=[], seed=100))
    cand = tmp_path / "c"; cand.mkdir()
    rd.snapshot("seed", cand)
    res = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                     split="val", n_trials=3, tag="seed")
    # base_seed defaults to the splits seed (100); trials are 100,101,102
    assert adapter.seeds_seen == [100, 101, 102]
    # distinct trials -> non-degenerate per-task stderr (the whole point)
    assert res.per_task[0]["stderr"] > 0.0


# ---- seal-on-success ------------------------------------------------------

class _CrashingAdapter:
    """Scores fine on val, but raises on the test split (simulating a finalize
    crash mid-scoring) until ``armed`` is cleared."""

    def __init__(self):
        self.crash_on_test = True

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id="t0")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        return Rollout(task_id=task.id, output="ok")

    def score(self, task, rollout):
        from cap_evolve import Score
        return Score(task_id=task.id, reward=1.0, trial_rewards=[1.0])

    def apply(self, candidate_dir, edits=None):
        if self.crash_on_test and _CrashingAdapter._scoring_test:
            raise RuntimeError("simulated finalize crash mid-scoring")

    _scoring_test = False


def test_finalize_crash_does_not_burn_seal(tmp_path):
    from cap_evolve import RunDir, TestSealError, harness
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / ".capevolve", ts="seal")
    rd.write_splits(Splits(train=[], val=["t0"], test=["t0"], seed=0))
    cand = tmp_path / "c"; cand.mkdir()
    rd.snapshot("best", cand); rd.set_best("best")
    adapter = _CrashingAdapter()

    # First finalize raises mid-scoring (live()/apply crashes on the test split).
    _CrashingAdapter._scoring_test = True
    with pytest.raises(RuntimeError):
        harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("best"))

    # The seal must be UNUSED — the crash happened before commit_test.
    assert rd.read_splits().test_used is False

    # A retry (no crash) can still score test exactly once...
    _CrashingAdapter._scoring_test = False
    payload = harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("best"))
    assert payload["test"]["reward"] == 1.0
    assert rd.read_splits().test_used is True

    # ...and a SECOND successful finalize is now refused (seal burned on success).
    with pytest.raises(TestSealError):
        harness.finalize(adapter, run_dir=rd, best_dir=rd.candidate_dir("best"))


def test_reserve_does_not_burn_commit_does(tmp_path):
    from cap_evolve import RunDir, TestSealError
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / ".capevolve", ts="rc")
    rd.write_splits(Splits(train=[], val=[], test=["a"], seed=0))
    rd.reserve_test()                       # does not flip
    assert rd.read_splits().test_used is False
    rd.reserve_test()                       # still fine (idempotent, unused)
    rd.commit_test()                        # now flips
    assert rd.read_splits().test_used is True
    with pytest.raises(TestSealError):
        rd.reserve_test()                   # burned -> refused


# ---- paired gate + SE=0 warning -------------------------------------------

def test_paired_gate_accepts_consistent_small_gain():
    from cap_evolve.gate import decide
    # Every task improves by +0.1 (zero variance in the delta) -> SE(Δ)=0 -> strict
    # fallback accepts a positive mean delta (and warns).
    d = decide(0.5, 0.6, split="val", mode="paired",
               paired_deltas=[0.1, 0.1, 0.1, 0.1])
    assert d.accept is True


def test_paired_gate_rejects_noisy_wash():
    from cap_evolve.gate import decide
    # Mean delta ~0 but high paired variance -> not significant.
    d = decide(0.5, 0.5, split="val", mode="paired",
               paired_deltas=[0.5, -0.5, 0.5, -0.5], k_se=1.0)
    assert d.accept is False


def test_paired_gate_significant_gain():
    from cap_evolve.gate import decide
    # Consistent +0.2 with tiny variance -> clears the bar.
    d = decide(0.5, 0.7, split="val", mode="paired",
               paired_deltas=[0.2, 0.21, 0.19, 0.2, 0.2], k_se=1.0)
    assert d.accept is True


def test_se_zero_logs_gate_warning(tmp_path):
    from cap_evolve import RunDir
    from cap_evolve.gate import decide
    rd = RunDir.create(tmp_path / ".capevolve", ts="warn")
    # significant mode, both SE=0 -> warn + strict fallback
    d = decide(0.5, 0.6, split="val", mode="significant",
               candidate_stderr=0.0, current_stderr=0.0, run_dir=rd)
    assert d.accept is True  # strict fallback on positive delta
    events = [json.loads(l) for l in rd.events_path.read_text().splitlines()]
    assert any(e["kind"] == "gate_warning" for e in events)


# ---- structured infra signal (Rollout.error) -----------------------------

class _InfraAdapter:
    """Two tasks: 'good' scores 0 with a normal feedback; 'flaky' returns a
    Rollout.error (infra) -> should be classified uncontrollable by the engine."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id="good"), Task(id="flaky")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        if task.id == "flaky":
            return Rollout(task_id=task.id, error="timeout after 300s")
        return Rollout(task_id=task.id, output="wrong")

    def score(self, task, rollout):
        from cap_evolve import Score
        # NOTE: feedback prose deliberately does NOT contain infra keywords, proving
        # classification comes from Rollout.error, not substring matching.
        return Score(task_id=task.id, reward=0.0, feedback="did not match expected",
                     trial_rewards=[0.0])

    def apply(self, candidate_dir, edits=None):
        return None


def test_infra_classified_by_rollout_error(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / ".capevolve", ts="infra")
    rd.write_splits(Splits(train=[], val=["good", "flaky"], test=[], seed=0))
    cand = tmp_path / "c"; cand.mkdir()
    rd.snapshot("seed", cand)
    res = harness.evaluate_candidate(adapter=_InfraAdapter(), candidate_dir=rd.candidate_dir("seed"),
                                     run_dir=rd, split="val", tag="seed")
    by = {pt["task_id"]: pt for pt in res.per_task}
    assert by["flaky"]["raw"]["errored"] is True
    assert by["good"]["raw"].get("errored") in (False, None)
    # the focus builder must route 'flaky' to "ignore" and 'good' to "actionable"
    instr = harness._focus_instructions(res, None, "all")
    assert "flaky" in instr and "infrastructure errors" in instr
    # 'good' appears in the actionable section
    assert "good" in instr


# ---- atomic state write ---------------------------------------------------

def test_state_write_is_atomic_no_partial(tmp_path, monkeypatch):
    """If the write is interrupted, os.replace guarantees no partial state.json."""
    from cap_evolve import rundir
    rd = rundir.RunDir.create(tmp_path / ".capevolve", ts="atom")
    good = rd.state_path.read_text()

    # Make the tmp write blow up AFTER the original is already in place; the
    # original must be untouched (atomic replace never ran on a bad temp).
    real_replace = rundir.os.replace

    def boom(src, dst):
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(rundir.os, "replace", boom)
    with pytest.raises(OSError):
        rd.set_best("x")
    monkeypatch.setattr(rundir.os, "replace", real_replace)
    # state.json is still the valid original (never half-written)
    assert rd.state_path.read_text() == good
    assert json.loads(rd.state_path.read_text())  # parses
    # no leftover tmp files masquerading as state
    assert not list(rd.root.glob(".state.json.tmp*"))


# ---- materialize / live ---------------------------------------------------

def test_materialize_is_pure_write(tmp_path):
    from cap_evolve import CapabilityAdapter

    class A(CapabilityAdapter):
        def tasks(self, split): return []
        def run_target(self, task, ctx, *, seed=0): ...
        def score(self, task, rollout): ...

    a = A()
    d = tmp_path / "cand"; d.mkdir()
    a.materialize(d, {"prompt.txt": "hello", "sub/x.md": "# x"})
    assert (d / "prompt.txt").read_text() == "hello"
    assert (d / "sub" / "x.md").read_text() == "# x"


def test_default_live_calls_apply_and_yields_dir(tmp_path):
    from cap_evolve import CapabilityAdapter

    applied = {}

    class A(CapabilityAdapter):
        def tasks(self, split): return []
        def run_target(self, task, ctx, *, seed=0): ...
        def score(self, task, rollout): ...
        def apply(self, candidate_dir, edits=None):
            applied["dir"] = Path(candidate_dir)

    a = A()
    d = tmp_path / "cand"; d.mkdir()
    with a.live(d) as ctx:
        assert ctx == d
    assert applied["dir"] == d  # back-compat: default live() calls apply()


def test_check_does_not_mutate_host(tmp_path):
    """run_check must not call the global-effect apply() on the project dir."""
    from cap_evolve import check

    adir = tmp_path / "adapters"; adir.mkdir(parents=True)
    (adir / "adapter.py").write_text(
        "from cap_evolve import CapabilityAdapter, Rollout, Score, Task\n"
        "TOUCHED = []\n"
        "class Adapter(CapabilityAdapter):\n"
        "    def tasks(self, split):\n"
        "        return [Task(id='t0')]\n"
        "    def run_target(self, task, ctx, *, seed=0):\n"
        "        return Rollout(task_id=task.id, output='x')\n"
        "    def score(self, task, rollout):\n"
        "        return Score(task_id=task.id, reward=1.0, trial_rewards=[1.0])\n"
        "    def apply(self, candidate_dir, edits=None):\n"
        "        # GLOBAL side effect that check must NOT trigger\n"
        "        (candidate_dir / 'HOST_MUTATED').write_text('boom')\n",
        encoding="utf-8",
    )
    rep = check.run_check(tmp_path)
    assert rep.ok, rep.problems
    # apply() (the host-mutating half) was never called on the project dir
    assert not (tmp_path / "HOST_MUTATED").exists()


# ---- selection registry ---------------------------------------------------

def test_selection_strategies_and_pickers_aligned():
    from cap_evolve import selection
    assert set(selection.STRATEGIES) == set(selection.PICKERS)
    assert {"best", "top_k", "epsilon_greedy", "softmax", "pareto",
            "pareto_per_instance"} <= set(selection.STRATEGIES)


def test_selection_best_and_validation():
    from cap_evolve import selection
    cands = [{"id": "a", "val": 0.3}, {"id": "b", "val": 0.9}, {"id": "c", "val": 0.5}]
    ranked, seed = selection.pick(cands, "best", seed=7)
    assert ranked[0]["id"] == "b" and seed == 7
    # validation casts + clamps
    spec = selection.validate_strategy({"kind": "top_k", "k": "999"})
    assert spec["params"]["k"] == 100  # clamped to max
    with pytest.raises(ValueError):
        selection.validate_strategy("nope")


def test_selection_seed_reproducible():
    from cap_evolve import selection
    cands = [{"id": str(i), "val": 0.5} for i in range(10)]
    a, _ = selection.pick(cands, {"kind": "softmax", "temperature": 1.0}, seed=3)
    b, _ = selection.pick(cands, {"kind": "softmax", "temperature": 1.0}, seed=3)
    assert a[0]["id"] == b[0]["id"]


def test_pareto_per_instance_keeps_specialist():
    from cap_evolve import selection
    # 'spec' uniquely tops task t2; 'gen' tops t0,t1. Per-instance must give 'spec'
    # nonzero weight (a specialist the mean would hide).
    cands = [
        {"id": "gen", "val": 0.66, "per_task": [
            {"task_id": "t0", "reward": 1.0}, {"task_id": "t1", "reward": 1.0},
            {"task_id": "t2", "reward": 0.0}]},
        {"id": "spec", "val": 0.33, "per_task": [
            {"task_id": "t0", "reward": 0.0}, {"task_id": "t1", "reward": 0.0},
            {"task_id": "t2", "reward": 1.0}]},
    ]
    counts = selection._instance_win_counts(cands)
    assert counts["gen"] == 2 and counts["spec"] == 1


def test_loop_select_parent_delegates():
    from cap_evolve.loop import select_parent
    cands = [{"id": "a", "val": 0.3}, {"id": "b", "val": 0.9}]
    assert select_parent(cands, "best")["id"] == "b"


# ---- lr schedule ----------------------------------------------------------

def test_lr_constant():
    from cap_evolve import build_schedule
    assert build_schedule("constant", max_lr=4, min_lr=1, total_steps=5) == [4, 4, 4, 4, 4]


def test_lr_linear_decays():
    from cap_evolve import build_schedule
    s = build_schedule("linear", max_lr=4, min_lr=1, total_steps=4)
    assert s[0] == 4 and s[-1] == 1
    assert all(s[i] >= s[i + 1] for i in range(len(s) - 1))  # non-increasing


def test_lr_cosine_endpoints():
    from cap_evolve import build_schedule
    s = build_schedule("cosine", max_lr=6, min_lr=2, total_steps=7)
    assert s[0] == 6 and s[-1] == 2
    assert all(2 <= x <= 6 for x in s)
    assert build_schedule("cosine", 4, 1, 0) == []


# ---- eval cache -----------------------------------------------------------

def test_cache_hash_ignores_scratch_and_busts_on_edit(tmp_path):
    from cap_evolve import hash_candidate_dir
    d = tmp_path / "c"; d.mkdir()
    (d / "prompt.txt").write_text("v1")
    h1 = hash_candidate_dir(d)
    # scratch files don't change the hash
    (d / "MEMORY.md").write_text("notes")
    (d / "STATE.md").write_text("plan")
    assert hash_candidate_dir(d) == h1
    # an editable-file change busts the hash
    (d / "prompt.txt").write_text("v2")
    assert hash_candidate_dir(d) != h1


def test_cache_get_put_roundtrip(tmp_path):
    from cap_evolve import EvalCache
    c = EvalCache(tmp_path / "cache.json")
    assert c.get("h", "t0") is None
    c.put("h", "t0", reward=0.7, feedback="ok")
    assert c.get("h", "t0") == {"reward": 0.7, "feedback": "ok"}
    # persisted: a fresh instance reads it back
    c2 = EvalCache(tmp_path / "cache.json")
    assert c2.get("h", "t0")["reward"] == 0.7
