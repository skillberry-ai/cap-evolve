"""pass^k / pass@k are OMITTED (⇒ N/A) when k > num_trials, never emitted as 0.0.

Honesty guard for issue #112: a single-trial run used to report pass^2 = 0.0, which
reads as "0% reliable" when the statistic is simply undefined at n_trials=1.
"""
from cap_evolve.loop import aggregate_scores
from cap_evolve.types import Score


def test_single_trial_omits_k2():
    # trial_rewards empty ⇒ falls back to [reward], i.e. n_trials == 1.
    scores = [Score(task_id="t1", reward=1.0), Score(task_id="t2", reward=1.0)]
    r = aggregate_scores("val", scores, ks=(1, 2))
    assert r.pass_k == {"1": 1.0}, r.pass_k          # NOT {"1": 1.0, "2": 0.0}
    assert r.pass_at_k == {"1": 1.0}, r.pass_at_k
    # and it survives (de)serialization as an absent key, not a 0.0
    assert "2" not in r.to_dict()["pass_k"]


def test_multi_trial_still_reports_k2():
    scores = [
        Score(task_id="t1", reward=1.0, trial_rewards=[1.0, 1.0, 1.0]),
        Score(task_id="t2", reward=2 / 3, trial_rewards=[1.0, 1.0, 0.0]),
    ]
    r = aggregate_scores("val", scores, ks=(1, 2))
    assert set(r.pass_k) == {"1", "2"}
    # t1: C(3,2)/C(3,2)=1 ; t2: C(2,2)/C(3,2)=1/3 → mean 2/3
    assert abs(r.pass_k["2"] - 2 / 3) < 1e-9


def test_ragged_trials_use_the_min():
    # One task with a single trial makes k=2 undefined for the split as a whole.
    scores = [
        Score(task_id="t1", reward=1.0, trial_rewards=[1.0, 1.0]),
        Score(task_id="t2", reward=1.0, trial_rewards=[1.0]),
    ]
    r = aggregate_scores("val", scores, ks=(1, 2))
    assert set(r.pass_k) == {"1"}
