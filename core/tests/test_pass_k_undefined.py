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


# --- the exact boundary: k == n is DEFINED and must survive; k == n+1 must not. ---
# A guard whose boundary is untested is one refactor away from silently
# over-suppressing a real measurement (reviewer proved a `k == max_k` mutant went
# undetected by the tests above, which only use n=3, k=2).

def test_k_equals_n_exactly_is_reported():
    scores = [
        Score(task_id="t1", reward=1.0, trial_rewards=[1.0, 1.0]),
        Score(task_id="t2", reward=0.5, trial_rewards=[1.0, 0.0]),
    ]
    r = aggregate_scores("val", scores, ks=(1, 2))
    assert "2" in r.pass_k, r.pass_k       # k == n == 2 is DEFINED
    assert "2" in r.pass_at_k, r.pass_at_k
    # t1: C(2,2)/C(2,2)=1 ; t2: c=1 < k=2 → 0 → mean 0.5
    assert abs(r.pass_k["2"] - 0.5) < 1e-9


def test_k_equals_n_plus_one_is_suppressed():
    scores = [Score(task_id="t1", reward=1.0, trial_rewards=[1.0, 1.0])]
    r = aggregate_scores("val", scores, ks=(1, 2, 3))
    assert set(r.pass_k) == {"1", "2"}, r.pass_k       # 3 == n+1 → undefined
    assert set(r.pass_at_k) == {"1", "2"}, r.pass_at_k


def test_k1_with_n1_is_reported():
    r = aggregate_scores("val", [Score(task_id="t1", reward=1.0, trial_rewards=[1.0])], ks=(1,))
    assert r.pass_k == {"1": 1.0}, r.pass_k


def test_nonpositive_k_is_suppressed():
    # k <= 0 is undefined too; it must not leak a plausible 0.0.
    r = aggregate_scores("val", [Score(task_id="t1", reward=1.0)], ks=(0, 1))
    assert set(r.pass_k) == {"1"}, r.pass_k
    assert set(r.pass_at_k) == {"1"}, r.pass_at_k


def test_nondefault_ks_reports_only_what_was_asked():
    # ks=(1,3): pass^3 is measured and must appear; pass^2 was never requested and
    # must NOT be fabricated (gepa.py already passes a non-default ks).
    scores = [Score(task_id="t1", reward=1.0, trial_rewards=[1.0, 1.0, 1.0])]
    r = aggregate_scores("val", scores, ks=(1, 3))
    assert set(r.pass_k) == {"1", "3"}, r.pass_k


def test_from_dict_tolerates_legacy_scalar_pass_k():
    # report/scripts/check.py still writes {"pass_k": 0.7}; dict(0.7) is a TypeError.
    from cap_evolve.loop import SplitResult
    r = SplitResult.from_dict({"split": "test", "reward": 0.8, "pass_k": 0.7})
    assert r.pass_k == {"1": 0.7}
    assert SplitResult.from_dict({"pass_k": None}).pass_k == {}
