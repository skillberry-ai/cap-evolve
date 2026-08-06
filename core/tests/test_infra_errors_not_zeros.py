"""An unscored trial is missing data, not a reward of 0.0.

From benchmarks run 31040448986 (`full / swebench` on skillberry-1). Docker Hub
rate-limits unauthenticated pulls to 100 manifest requests/hour per source IP,
and the runner had no `docker.io` credential, so `docker compose build` failed
with HTTP 429 before the agent ever started:

    RuntimeError: Docker compose command failed for environment django__django-10554
    #3 ERROR: unexpected status from HEAD request to registry-1.docker.io/...: 429

Harbor recorded that faithfully (`n_errored_trials: 50`, `n_trials: 0`), but
`capevolve_harbor.results` never read `exception_info`, so every crashed trial
arrived as a legitimate "Task not solved (reward 0.0)". Consequences, all of
which these tests pin down:

  * cand_0001 and cand_0002 scored val **0.000** with 50/50 trials never run.
  * The baseline itself was measured with 33/50 tasks unscored (val 0.08 where
    the tasks that ran gave ~0.27), so every delta was against a fiction.
  * The `paired` gate reads per-task, so an unscored candidate task the parent
    had passed contributed a full -1.0: cand_0007 was rejected at
    `paired Δ̄=-0.6400` without a single task being evaluated.
  * cand_0006 scored 0.69 on the tasks that ran — better than the accepted
    cand_0003 — but was rejected as Δ=-0.16 because 9 of its tasks 429'd.
  * The optimizer burned an iteration proving to itself that "iters 1–2 were
    infra flakes, not content regressions".
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


# ---- has_valid_trials: the single predicate everything else keys off --------

def test_valid_trials_zero_means_unscored():
    from cap_evolve.loop import has_valid_trials
    assert has_valid_trials({"raw": {"valid_trials": 0, "n_trials": 1}}) is False
    assert has_valid_trials({"raw": {"valid_trials": 2, "n_trials": 3}}) is True


def test_falls_back_to_errored_trial_counts_for_older_run_dirs():
    from cap_evolve.loop import has_valid_trials
    assert has_valid_trials({"raw": {"errored_trials": 3, "n_trials": 3}}) is False
    assert has_valid_trials({"raw": {"errored_trials": 1, "n_trials": 3}}) is True


def test_absent_metadata_defaults_to_scored():
    """Missing metadata must never silently erase a task from a mean."""
    from cap_evolve.loop import has_valid_trials
    assert has_valid_trials({}) is True
    assert has_valid_trials({"raw": {}}) is True


# ---- aggregate_scores: unscored tasks leave the statistics ------------------

def _score(tid, reward, *, valid=1, n=1):
    from cap_evolve import Score
    return Score(task_id=tid, reward=reward, trial_rewards=[reward] * valid,
                 n=n, raw={"valid_trials": valid, "n_trials": n,
                           "errored_trials": n - valid, "errored": valid < n})


def test_unscored_tasks_are_excluded_from_the_mean():
    from cap_evolve.loop import aggregate_scores
    # 1 pass, 1 real fail, 2 never ran. Honest answer is 1/2, not 1/4.
    res = aggregate_scores("val", [
        _score("pass", 1.0),
        _score("fail", 0.0),
        _score("infra1", 0.0, valid=0),
        _score("infra2", 0.0, valid=0),
    ])
    assert res.reward == 0.5, "unscored tasks must not dilute the mean"
    assert res.n_tasks == 4
    assert res.n_scored == 2
    assert res.coverage == 0.5


def test_unscored_tasks_are_still_reported():
    """Excluded from the statistics, but never hidden from the record."""
    from cap_evolve.loop import aggregate_scores
    res = aggregate_scores("val", [_score("pass", 1.0), _score("infra", 0.0, valid=0)])
    assert {pt["task_id"] for pt in res.per_task} == {"pass", "infra"}


def test_coverage_is_one_when_nothing_errored():
    from cap_evolve.loop import aggregate_scores
    res = aggregate_scores("val", [_score("a", 1.0), _score("b", 0.0)])
    assert res.coverage == 1.0
    assert res.reward == 0.5


def test_coverage_defaults_to_one_for_legacy_split_results():
    """A SplitResult read back from an old run dir must not look decimated."""
    from cap_evolve.loop import SplitResult
    old = SplitResult.from_dict({"split": "val", "reward": 0.5, "stderr": 0.1})
    assert old.coverage == 1.0


def test_split_result_roundtrips_coverage():
    from cap_evolve.loop import SplitResult
    r = SplitResult(split="val", reward=0.5, stderr=0.1, n_tasks=10, n_scored=4)
    assert SplitResult.from_dict(r.to_dict()).coverage == 0.4


# ---- _paired_deltas: the -0.64 that never happened -------------------------

def test_paired_deltas_drop_unscored_candidate_tasks():
    """The cand_0007 failure: infra outage read as the largest possible regression."""
    from cap_evolve.harness import _paired_deltas
    from cap_evolve.loop import aggregate_scores

    parent = aggregate_scores("val", [_score(f"t{i}", 1.0) for i in range(4)])
    # Candidate: one real regression, three tasks that never ran.
    cand = aggregate_scores("val", [
        _score("t0", 0.0),
        _score("t1", 0.0, valid=0),
        _score("t2", 0.0, valid=0),
        _score("t3", 0.0, valid=0),
    ])
    deltas = _paired_deltas(parent, cand)
    assert deltas == [-1.0], "only the one measured task may contribute a delta"


def test_paired_deltas_drop_unscored_parent_tasks():
    from cap_evolve.harness import _paired_deltas
    from cap_evolve.loop import aggregate_scores
    parent = aggregate_scores("val", [_score("t0", 1.0), _score("t1", 0.0, valid=0)])
    cand = aggregate_scores("val", [_score("t0", 1.0), _score("t1", 1.0)])
    assert _paired_deltas(parent, cand) == [0.0]


def test_paired_deltas_none_when_nothing_is_comparable():
    """No shared measured task -> fall back to the unpaired test, not a fake 0."""
    from cap_evolve.harness import _paired_deltas
    from cap_evolve.loop import aggregate_scores
    parent = aggregate_scores("val", [_score("t0", 1.0)])
    cand = aggregate_scores("val", [_score("t0", 0.0, valid=0)])
    assert _paired_deltas(parent, cand) is None


# ---- the gate refuses to judge a decimated split ---------------------------

def test_gate_is_indecisive_below_min_coverage():
    from cap_evolve import gate
    d = gate.decide(0.08, 0.0, coverage=0.02, min_coverage=0.6,
                    paired_deltas=[-1.0] * 50)
    assert d.accept is False
    assert d.indecisive is True
    assert "INDECISIVE" in d.reason


def test_gate_judges_normally_at_acceptable_coverage():
    from cap_evolve import gate
    d = gate.decide(0.0, 1.0, coverage=0.9, min_coverage=0.6, mode="strict")
    assert d.accept is True
    assert d.indecisive is False


def test_min_coverage_zero_disables_the_guard():
    from cap_evolve import gate
    d = gate.decide(0.0, 1.0, coverage=0.01, min_coverage=0.0, mode="strict")
    assert d.indecisive is False
    assert d.accept is True


def test_coverage_none_disables_the_guard():
    """Callers that don't know their coverage keep the old behaviour."""
    from cap_evolve import gate
    d = gate.decide(0.0, 1.0, coverage=None, mode="strict")
    assert d.indecisive is False
    assert d.accept is True


def test_indecisive_decision_is_serialised():
    from cap_evolve import gate
    d = gate.decide(0.5, 0.0, coverage=0.1, min_coverage=0.6, mode="strict")
    assert d.to_dict()["indecisive"] is True


# ---- end to end through evaluate_candidate --------------------------------

class _FlakyAdapter:
    """A/B score for real; C/D always fail to start (the 429 case)."""

    ERRORED = ("C", "D")

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in ("A", "B", "C", "D")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        if task.id in self.ERRORED:
            return Rollout(task_id=task.id,
                           error="RuntimeError: Docker compose command failed ... "
                                 "429 Too Many Requests")
        return Rollout(task_id=task.id, output="pass" if task.id == "A" else "fail")

    def score(self, task, rollout):
        from cap_evolve import Score
        # Deliberately returns 0.0 for the errored rollouts, exactly as the harbor
        # adapter does. The harness must not let that 0.0 into the mean.
        ok = rollout.output == "pass"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0)

    def apply(self, candidate_dir, edits=None):
        return None


def _run_dir(tmp_path, ts, ids=("A", "B", "C", "D")):
    from cap_evolve import RunDir
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / ".capevolve", ts=ts)
    rd.write_splits(Splits(train=[], val=list(ids), test=[], seed=0))
    seed = tmp_path / "seed"
    seed.mkdir(exist_ok=True)
    (seed / "cap.md").write_text("x")
    rd.snapshot("seed", seed)
    rd.set_best("seed")
    return rd


def test_evaluate_candidate_excludes_errored_trials(tmp_path):
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "ee")
    res = harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                                     run_dir=rd, split="val", tag="seed")
    # A=1.0, B=0.0 measured; C,D never ran. 0.5, not 0.25.
    assert res.reward == 0.5
    assert res.n_scored == 2
    assert res.n_tasks == 4
    assert res.coverage == 0.5


def test_errored_tasks_are_marked_in_per_task_records(tmp_path):
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "mark")
    res = harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                                     run_dir=rd, split="val", tag="seed")
    by_id = {pt["task_id"]: pt for pt in res.per_task}
    assert by_id["C"]["raw"]["valid_trials"] == 0
    assert by_id["C"]["raw"]["errored"] is True
    assert by_id["A"]["raw"]["valid_trials"] == 1
    assert by_id["A"]["raw"]["errored"] is False


def test_rollout_files_still_record_the_error(tmp_path):
    """Excluded from the mean, but the forensic trail must survive."""
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "forensics")
    harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                               run_dir=rd, split="val", tag="seed")
    rec = json.loads((rd.rollouts / "val" / "C__seed__t0.json").read_text())
    assert "429" in rec["rollout"]["error"]


def test_resume_reproduces_the_same_score(tmp_path):
    """A resumed val score must equal the score the run computed live.

    The resume path reads persisted rollouts, and it used to look only at
    `score.raw.errored` — which adapters legitimately leave empty, so every infra
    failure came back from disk as a real 0.0 and the bug reappeared on resume.
    """
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "resume")
    live = harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                                      run_dir=rd, split="val", tag="seed")
    back = harness.split_result_from_rollouts(rd, "seed", split="val")
    assert back.reward == live.reward == 0.5
    assert back.coverage == live.coverage == 0.5


class _TotalOutageAdapter(_FlakyAdapter):
    """Every task fails to start — cand_0001/cand_0002's actual situation."""
    ERRORED = ("A", "B", "C", "D")


def test_total_outage_does_not_count_as_a_stall(tmp_path):
    """A candidate that was never evaluated must not push the run toward 'stalled'."""
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "outage")
    base = harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                                      run_dir=rd, split="val", tag="seed")
    stall_before = rd.spent.stall

    noop = harness.optimizer_from_command(["python3", "-c", "pass"])
    step = harness.run_step(_TotalOutageAdapter(), run_dir=rd,
                            parent_dir=rd.candidate_dir("seed"), optimizer=noop,
                            instructions="x", current_val=base)

    assert step["accepted"] is False
    assert step["decision"]["indecisive"] is True
    assert rd.spent.stall == stall_before, (
        "an unevaluated candidate is not evidence the optimizer has run out of ideas"
    )


def test_indecisive_step_is_not_filed_as_a_rejected_edit(tmp_path):
    """The rejected list is optimizer guidance — an outage must not enter it.

    Otherwise the next iteration is told "this edit did not work" about a change
    whose content was never evaluated, which is how cand_0003 ended up spending an
    iteration proving iters 1-2 were infra flakes rather than real regressions.
    """
    from cap_evolve import harness

    class _Rejected:
        def __init__(self):
            self.entries = []

        def add(self, *a, **kw):
            self.entries.append((a, kw))

    rd = _run_dir(tmp_path, "noguide")
    base = harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                                      run_dir=rd, split="val", tag="seed")
    rejected = _Rejected()
    noop = harness.optimizer_from_command(["python3", "-c", "pass"])
    harness.run_step(_TotalOutageAdapter(), run_dir=rd,
                     parent_dir=rd.candidate_dir("seed"), optimizer=noop,
                     instructions="x", current_val=base, rejected=rejected)
    assert rejected.entries == []


def test_total_outage_reward_is_not_reported_as_a_measurement(tmp_path):
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "outage2")
    res = harness.evaluate_candidate(_TotalOutageAdapter(), rd.candidate_dir("seed"),
                                     run_dir=rd, split="val", tag="seed")
    assert res.n_scored == 0
    assert res.coverage == 0.0


# ---- the baseline poisons every later delta, so it warns loudly -------------

def _events(rd):
    p = rd.root / "events.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()] \
        if p.exists() else []


def test_partial_baseline_is_flagged(tmp_path):
    """The real run established val 0.08 with 34/50 tasks never scored.

    baseline.json looks like an ordinary number, so nothing downstream can notice.
    """
    from cap_evolve import harness
    rd = _run_dir(tmp_path, "basewarn")
    seed = tmp_path / "seed"
    res = harness.baseline(_FlakyAdapter(), seed, run_dir=rd)
    assert res.coverage == 0.5
    kinds = [e.get("kind") for e in _events(rd)]
    assert "baseline_incomplete" in kinds


def test_complete_baseline_is_not_flagged(tmp_path):
    from cap_evolve import harness

    class _Clean(_FlakyAdapter):
        ERRORED = ()

    rd = _run_dir(tmp_path, "baseok")
    seed = tmp_path / "seed"
    res = harness.baseline(_Clean(), seed, run_dir=rd)
    assert res.coverage == 1.0
    kinds = [e.get("kind") for e in _events(rd)]
    assert "baseline_incomplete" not in kinds


# ---- the CI safety net was correct; it was starved of the signal ------------

def _assert_run_module():
    import importlib.util
    path = REPO / "ci" / "benchmarks" / "lib" / "assert_run.py"
    spec = importlib.util.spec_from_file_location("_assert_run_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_infra_tasks_now_trip_the_ci_assertion(tmp_path):
    """`assert_run.py --max-infra-frac` keys off `raw.errored`.

    That guard has existed since run 30682720920 and would have failed this run at
    the assert step — but `raw.errored` was never set for harbor, so it saw a clean
    baseline and passed. Setting the flag is what re-arms it.
    """
    from cap_evolve import harness
    ar = _assert_run_module()

    rd = _run_dir(tmp_path, "assertwire")
    res = harness.evaluate_candidate(_FlakyAdapter(), rd.candidate_dir("seed"),
                                     run_dir=rd, split="val", tag="seed")
    infra = [pt for pt in res.per_task if ar._infra_task(pt)]
    assert {pt["task_id"] for pt in infra} == {"C", "D"}
    # 2/4 tasks infra-errored, i.e. exactly at the default 0.5 ceiling.
    assert len(infra) / len(res.per_task) == 0.5


def test_healthy_tasks_do_not_trip_the_ci_assertion(tmp_path):
    from cap_evolve import harness
    ar = _assert_run_module()

    class _Clean(_FlakyAdapter):
        ERRORED = ()

    rd = _run_dir(tmp_path, "assertclean")
    res = harness.evaluate_candidate(_Clean(), rd.candidate_dir("seed"),
                                     run_dir=rd, split="val", tag="seed")
    assert [pt for pt in res.per_task if ar._infra_task(pt)] == []
