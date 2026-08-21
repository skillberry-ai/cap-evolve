"""The held-out split must not be scored twice, even when a finalize attempt dies mid-way.

Seal-on-success (``reserve_test`` + ``commit_test``) exists so a finalize that crashes before
scoring can be retried without destroying the run's headline number. It cannot, by itself, tell that
case apart from a crash AFTER test was scored -- and there the held-out set has already been
observed, so a retry makes the reported number a second look at test.

Observed in a real run: a finalize killed by a foreground timeout had already scored test, the retry
scored it again, and the headline came from the second look. These tests pin the fix and, just as
importantly, pin the behaviour it must NOT break -- one honest finalize scores test twice by design
(the best as ``FINAL`` and the baseline as ``FINAL_seed``).
"""

import pytest

from cap_evolve.rundir import RunDir
from cap_evolve.splits import TestSealError, make_splits


def _run(tmp_path):
    rd = RunDir.create(tmp_path)
    rd.write_splits(make_splits([f"t{i}" for i in range(8)], seed=0))
    return rd


def _write_test_rollout(rd, name="t1__FINAL__t0.json"):
    (rd.rollouts / "test").mkdir(parents=True, exist_ok=True)
    (rd.rollouts / "test" / name).write_text("{}", encoding="utf-8")


def test_first_attempt_is_allowed(tmp_path):
    _run(tmp_path).begin_test_attempt()          # must not raise


def test_crash_before_scoring_can_still_be_retried(tmp_path):
    """The whole point of seal-on-success: no test rollouts yet, so a retry is honest."""
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    rd.begin_test_attempt()


def test_retry_after_test_was_scored_is_refused(tmp_path):
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    _write_test_rollout(rd)
    with pytest.raises(TestSealError) as exc:
        rd.begin_test_attempt()
    msg = str(exc.value)
    assert "already SCORED" in msg
    assert "second look" in msg.lower()
    assert "CAPEVOLVE_ALLOW_TEST_RESCORE" in msg, "the refusal must name its own override"


def test_override_is_explicit_and_opt_in(tmp_path, monkeypatch):
    rd = _run(tmp_path)
    _write_test_rollout(rd)
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "1")
    rd.begin_test_attempt()                      # deliberate, disclosed
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "0")
    with pytest.raises(TestSealError):
        rd.begin_test_attempt()                  # and it is genuinely opt-in


def test_reserve_test_still_allows_two_evals_in_one_finalize(tmp_path):
    """Regression guard: the check belongs at ATTEMPT granularity, not per evaluation.

    Putting it in ``reserve_test`` broke seven core tests, because one finalize reserves twice --
    once for the best candidate and once for the baseline, to report a held-out delta.
    """
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    rd.reserve_test()
    _write_test_rollout(rd, "t1__FINAL__t0.json")
    rd.reserve_test()                            # FINAL_seed, same attempt: must not raise
    _write_test_rollout(rd, "t1__FINAL_seed__t0.json")
    rd.commit_test()


def test_committed_seal_still_refuses(tmp_path):
    rd = _run(tmp_path)
    rd.begin_test_attempt()
    rd.commit_test()
    with pytest.raises(TestSealError):
        rd.begin_test_attempt()
    with pytest.raises(TestSealError):
        rd.reserve_test()
