"""Issue #113: tiny/empty val splits are refused, and the paired gate gets a
Student-t small-sample correction (never looser than the old z bar).

Regression targets:
  * an empty or 1-task val split must fail LOUDLY at split/baseline time rather
    than silently producing a meaningless gate decision;
  * the paired gate's ``k_se`` is a *z* multiplier, but SE(Δ) is estimated from
    the same n deltas, so the correct bar uses t with df=n-1. At small n the old
    z bar was too LOW (accepted noise); the t bar is strictly wider and converges
    back to z as n grows.
"""

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import stats  # noqa: E402
from cap_evolve.gate import decide  # noqa: E402
from cap_evolve.splits import (  # noqa: E402
    LOW_CONFIDENCE_VAL_TASKS,
    MIN_VAL_TASKS,
    Splits,
    TinyValSplitError,
    check_val_size,
    make_splits,
)


# ---- (a) tiny / empty val split guard -------------------------------------

def test_empty_val_split_refused_with_actionable_message():
    # 2 tasks with the default ratios -> train=1 val=0 test=1 (the silent case).
    sp = make_splits(["t0", "t1"], seed=0)
    assert sp.val == []
    with pytest.raises(TinyValSplitError) as ei:
        check_val_size(sp)
    msg = str(ei.value)
    assert "is EMPTY" in msg
    assert "split_ids_file" in msg and "split_val" in msg   # actionable fixes
    assert "CAPEVOLVE_ALLOW_TINY_VAL" in msg                # documented escape hatch


def test_single_task_val_split_refused():
    sp = make_splits([f"t{i}" for i in range(4)], seed=0)
    assert len(sp.val) == 1
    with pytest.raises(TinyValSplitError) as ei:
        check_val_size(sp)
    assert "0 degrees of freedom" in str(ei.value)


def test_min_val_size_is_two_and_passes():
    sp = make_splits([f"t{i}" for i in range(6)], seed=0)
    assert len(sp.val) == MIN_VAL_TASKS == 2
    assert check_val_size(sp) is not None      # usable, but warned (2 < 5)


def test_small_val_split_warns_but_is_allowed(tmp_path):
    from cap_evolve import RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="w")
    sp = Splits(train=[], val=["a", "b", "c"], test=[], seed=0)
    warn = check_val_size(sp, run_dir=rd)
    assert warn and "LOW CONFIDENCE" in warn
    events = (rd.root / "events.jsonl").read_text(encoding="utf-8")
    assert "split_warning" in events


def test_healthy_val_split_is_silent():
    sp = make_splits([f"t{i}" for i in range(40)], seed=0)
    assert len(sp.val) >= LOW_CONFIDENCE_VAL_TASKS
    assert check_val_size(sp) is None


def test_escape_hatch_allows_tiny_val(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_ALLOW_TINY_VAL", "1")
    check_val_size(Splits(train=[], val=[], test=[], seed=0))   # no raise


def test_ensure_splits_refuses_tiny_val(tmp_path):
    """The guard fires at split-freeze time, before any budget is spent."""
    from cap_evolve import RunDir, harness
    from cap_evolve.types import Rollout, Score, Task

    class _Tiny:
        def tasks(self, split):
            return [Task(id=f"t{i}") for i in range(4)]   # -> val=1
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output="x")
        def score(self, task, rollout):
            return Score(task_id=task.id, reward=0.0)
        def apply(self, candidate_dir, edits=None):
            return None

    rd = RunDir.create(tmp_path / ".capevolve", ts="tiny")
    with pytest.raises(TinyValSplitError):
        harness.ensure_splits(_Tiny(), rd, seed=0)
    assert not rd.splits_path.exists()     # nothing frozen on refusal


def test_baseline_refuses_handwritten_tiny_val(tmp_path):
    """A splits.json that bypassed ensure_splits is still caught at baseline."""
    from cap_evolve import RunDir, harness
    from cap_evolve.types import Rollout, Score, Task

    class _A:
        def tasks(self, split):
            return [Task(id="t0")]
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output="x")
        def score(self, task, rollout):
            return Score(task_id=task.id, reward=1.0)
        def apply(self, candidate_dir, edits=None):
            return None

    rd = RunDir.create(tmp_path / ".capevolve", ts="hand")
    rd.write_splits(Splits(train=[], val=["t0"], test=[], seed=0))   # hand-written n=1
    seed = tmp_path / "seed"; seed.mkdir()
    with pytest.raises(TinyValSplitError):
        harness.baseline(_A(), seed, run_dir=rd)


# ---- (b) Student-t small-sample correction ---------------------------------

@pytest.mark.parametrize("df,expected", [
    # One-sided upper-tail t critical values, alpha=0.05.
    # Source: Abramowitz & Stegun, Handbook of Mathematical Functions (1964),
    # Table 26.10 (percentage points of the t-distribution).
    (1, 6.314), (2, 2.920), (4, 2.132), (9, 1.833), (29, 1.699), (100, 1.660),
])
def test_t_critical_matches_published_table_alpha_05(df, expected):
    assert stats.t_critical(0.05, df) == pytest.approx(expected, abs=5e-4)


@pytest.mark.parametrize("df,expected", [
    (1, 12.706), (2, 4.303), (10, 2.228), (30, 2.042),   # A&S Table 26.10, alpha=0.025
])
def test_t_critical_matches_published_table_alpha_025(df, expected):
    assert stats.t_critical(0.025, df) == pytest.approx(expected, abs=5e-4)


def test_t_cdf_is_symmetric_and_bounded():
    for df in (1, 3, 12):
        assert stats.t_cdf(0.0, df) == pytest.approx(0.5)
        for t in (0.3, 1.0, 4.0):
            assert stats.t_cdf(t, df) + stats.t_cdf(-t, df) == pytest.approx(1.0, abs=1e-9)


def test_t_converges_to_normal_at_large_df():
    # df -> inf: t_{1-a,df} -> z_{1-a}. k_se=1 corresponds to alpha=P(Z>1).
    z = 1.0
    alpha = stats.normal_sf(z)
    assert stats.t_critical(alpha, 100000) == pytest.approx(z, abs=1e-3)


def test_t_multiplier_never_looser_than_z():
    """The whole honesty point: the correction can only WIDEN the bar."""
    for k in (0.5, 1.0, 1.5, 2.0):
        for n in range(2, 200):
            assert stats.t_multiplier_for_z(k, n) >= k - 1e-12


def test_t_multiplier_monotonically_relaxes_toward_z():
    ks = [stats.t_multiplier_for_z(1.0, n) for n in range(3, 60)]
    assert ks == sorted(ks, reverse=True)              # shrinks as n grows
    assert ks[-1] == pytest.approx(1.0, abs=0.02)      # ...toward the z multiplier


# --- the regression test: small n is STRICTER than the old z bar -------------

def _old_z_bar(deltas, k_se=1.0):
    """The pre-fix bar: k_se * SE(Δ) with a fixed z-style multiplier."""
    n = len(deltas)
    m = sum(deltas) / n
    var = sum((d - m) ** 2 for d in deltas) / (n - 1)
    return k_se * math.sqrt(var / n)


def test_small_n_gate_is_strictly_stricter_than_old_z_bar():
    """REGRESSION (fails before the fix): at n=3 the t bar must exceed the z bar,
    and a candidate that used to squeak through must now be rejected."""
    # 3 val tasks: mean Δ=+0.10, SE(Δ)=0.0577 -> old bar 0.0577 (ACCEPT, 0.10>0.0577).
    deltas = [0.0, 0.1, 0.2]
    old = _old_z_bar(deltas)
    d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=deltas, k_se=1.0)
    assert d.threshold > old                            # strictly wider bar
    # t_{0.1587, df=2} = 1.3213 -> bar 0.0763; Δ̄=0.10 still clears it here.
    assert d.threshold == pytest.approx(0.0763, abs=5e-4)
    assert old == pytest.approx(0.0577, abs=5e-4)

    # And a genuinely marginal case flips from accept to reject.
    marginal = [-0.05, 0.10, 0.25]                       # Δ̄=0.10, SE=0.0866
    old_m = _old_z_bar(marginal)
    assert 0.10 > old_m                                  # old gate: ACCEPTED
    dm = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=marginal, k_se=1.0)
    assert dm.threshold > old_m
    assert dm.accept is False                            # new gate: REJECTED
    assert "df=2" in dm.reason and "t-corrected" in dm.reason


def test_large_n_converges_to_old_behaviour():
    """Normal-sized runs are not broken: the bar matches the old z bar to <1%."""
    deltas = [0.1 + (i % 7 - 3) * 0.02 for i in range(200)]
    old = _old_z_bar(deltas)
    d = decide(0.5, 0.6, split="val", mode="paired", paired_deltas=deltas, k_se=1.0)
    assert d.threshold == pytest.approx(old, rel=0.01)
    assert d.accept is True


def test_paired_gate_logs_low_confidence_warning(tmp_path):
    from cap_evolve import RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="lc")
    d = decide(0.5, 0.6, split="val", mode="paired",
               paired_deltas=[0.0, 0.1, 0.25], k_se=1.0, run_dir=rd)
    assert "LOW CONFIDENCE" in d.reason
    events = (rd.root / "events.jsonl").read_text(encoding="utf-8")
    assert "gate_warning" in events and "Student-t" in events


def test_large_n_has_no_low_confidence_flag():
    d = decide(0.5, 0.6, split="val", mode="paired",
               paired_deltas=[0.1] * 9 + [0.05], k_se=1.0)
    assert "LOW CONFIDENCE" not in d.reason
