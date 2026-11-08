"""Tests for the ``stop_at_reward`` budget field: stop the optimizer loop as
soon as the best val reward reaches a ceiling, including before iteration 1
when the seed is already saturated."""

from cap_evolve import RunDir
from cap_evolve.rundir import Budget, Spent
from cap_evolve.splits import Splits
from cap_evolve.loop import SplitResult
from cap_evolve.harness import hill_climb_loop


# ---- Budget / Spent round-trip + legacy tolerance --------------------------

def test_budget_roundtrip_stop_at_reward():
    b = Budget.from_dict({"max_iterations": 5, "stop_at_reward": 0.95})
    assert Budget.from_dict(b.to_dict()).stop_at_reward == 0.95


def test_budget_legacy_dict_tolerated():
    # An old spec/state.json without the new key still loads (defaults to off).
    b = Budget.from_dict({"max_iterations": 5})
    assert b.stop_at_reward == 0.0


def test_spent_roundtrip_best_val():
    s = Spent(best_val=0.8)
    assert Spent.from_dict(s.to_dict()).best_val == 0.8


def test_spent_legacy_dict_tolerated():
    # An old state.json without best_val still loads (defaults to 0).
    s = Spent.from_dict({"usd": 2.0})
    assert s.best_val == 0.0


# ---- update_spent(best_val=...) is monotonic -------------------------------

def test_best_val_is_monotonic(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget())
    rd.update_spent(best_val=0.9)
    rd.update_spent(best_val=0.4)  # a later, worse candidate must not regress it
    assert rd.spent.best_val == 0.9


def test_best_val_unaffected_by_calls_without_it(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget())
    rd.update_spent(best_val=0.7)
    rd.update_spent(iterations=1, accepted=False)  # no best_val kwarg
    assert rd.spent.best_val == 0.7


# ---- budget_exhausted() ceiling check --------------------------------------

def test_stop_at_reward_fires_at_or_above_threshold(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(stop_at_reward=0.9))
    rd.update_spent(best_val=0.9)
    exhausted, why = rd.budget_exhausted()
    assert exhausted and "reward ceiling" in why


def test_stop_at_reward_does_not_fire_below_threshold(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(stop_at_reward=0.9))
    rd.update_spent(best_val=0.5)
    exhausted, _ = rd.budget_exhausted()
    assert not exhausted


def test_stop_at_reward_off_by_default_even_at_1_0(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget())  # stop_at_reward=0.0 = off
    rd.update_spent(best_val=1.0)
    exhausted, _ = rd.budget_exhausted()
    assert not exhausted


def test_stop_at_reward_reason_wins_over_max_iterations(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(max_iterations=1, stop_at_reward=0.9))
    rd.update_spent(iterations=1, best_val=0.95)  # satisfies both limits at once
    exhausted, why = rd.budget_exhausted()
    assert exhausted and "reward ceiling" in why and "max_iterations" not in why


# ---- update_budget can toggle it on a resumed run --------------------------

def test_update_budget_can_set_stop_at_reward(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget())
    rd.update_budget(stop_at_reward=0.99)
    assert rd.budget.stop_at_reward == 0.99


# ---- integration: seed already at ceiling stops before iteration 1 --------

def test_hill_climb_loop_stops_immediately_on_saturated_seed(tmp_path):
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(stop_at_reward=1.0, max_iterations=10))
    rd.write_splits(Splits(train=["a"], val=["b"], test=["c"]))
    rd.set_best("seed")
    rd.update_spent(best_val=1.0)  # what harness.baseline() would record for a seed at 1.0
    current_val = SplitResult(split="val", reward=1.0, stderr=0.0)

    # adapter/optimizer are never touched: budget_exhausted() is true at loop entry,
    # so the loop body (which would call run_step -> adapter/optimizer) never runs.
    result = hill_climb_loop(
        adapter=None, run_dir=rd, optimizer=None, current_val=current_val,
        max_iterations=10,
    )
    assert result["iterations"] == 0
    assert result["accepts"] == 0
    assert "reward ceiling" in result["stop_reason"]


# ---- the dashboard mirror must not drift from the canonical check ----------

_MIRROR_CASES = (
    # (label, budget kwargs, spent kwargs)
    ("ceiling reached", {"stop_at_reward": 1.0}, {"best_val": 1.0}),
    ("ceiling reached with float slop", {"stop_at_reward": 0.7},
     {"best_val": 0.6999999999999998}),
    ("ceiling not reached", {"stop_at_reward": 1.0}, {"best_val": 0.99}),
    ("ceiling off, val at 1.0", {}, {"best_val": 1.0}),
    ("ceiling wins over max_iterations", {"stop_at_reward": 1.0, "max_iterations": 10},
     {"best_val": 1.0, "iterations": 1}),
    ("ceiling wins over stall", {"stop_at_reward": 1.0, "stall": 2},
     {"best_val": 1.0, "stall": 0}),
    ("max_iterations only", {"max_iterations": 3}, {"iterations": 3}),
    ("stall only", {"stall": 2}, {"stall": 2}),
    ("nothing spent", {"max_iterations": 5, "stop_at_reward": 1.0}, {}),
)


def test_dashboard_budget_mirror_agrees_with_rundir():
    """`dashboard._budget_exhausted` is a hand-maintained copy of
    `RunDir.budget_exhausted`. It has silently drifted from the canonical check three
    times (most recently by missing `stop_at_reward` entirely, so a run that stopped at
    the ceiling was rendered as still running). Pin the two together so the next drift
    fails here instead of on the dashboard.
    """
    from cap_evolve import dashboard

    for label, bkw, skw in _MIRROR_CASES:
        budget, spent = Budget(**bkw), Spent(**skw)
        canonical, reason = RunDir.budget_exhausted(
            type("_RD", (), {"budget": budget, "spent": spent})())
        mirrored = dashboard._budget_exhausted(budget, spent)
        assert canonical == (mirrored is not None), (
            f"{label}: canonical says {canonical}, dashboard says {mirrored!r}")
        if canonical:
            # Same limit blamed, not just the same verdict.
            limit = reason.split(" reached")[0].split(" (")[0]
            assert limit.split()[0] in mirrored, (
                f"{label}: canonical blames {reason!r}, dashboard blames {mirrored!r}")


def test_dashboard_mirror_tolerates_missing_budget_or_spent():
    from cap_evolve import dashboard
    assert dashboard._budget_exhausted(None, Spent(best_val=1.0)) is None
    assert dashboard._budget_exhausted(Budget(stop_at_reward=1.0), None) is None


# ---- shipped templates must not pair a ceiling with a single trial ---------

def test_no_shipped_template_pairs_stop_at_reward_with_num_trials_1():
    """A ceiling is only meaningful if `best_val` could have been wrong.

    With `num_trials: 1` a lucky all-pass val draw has `stderr` exactly 0.0, so no gate
    or SE bar downstream can catch it and the run can end at iteration 0 while real
    headroom remains (reproduced by review of #415: val drew 1.0, sealed test 0.667).
    Ship the ceiling on only where trials give `best_val` a real standard error.
    """
    from pathlib import Path
    from cap_evolve.specfile import read_yaml

    repo = Path(__file__).resolve().parents[2]
    templates = sorted((repo / "benchmarks").rglob("capevolve.yaml"))
    assert templates, "no shipped templates found — path drifted?"

    offenders = []
    for path in templates:
        spec = read_yaml(path.read_text(encoding="utf-8"))
        ceiling = float(spec.get("stop_at_reward") or 0.0)
        trials = int(spec.get("num_trials") or 1)
        if ceiling > 0.0 and trials < 2:
            offenders.append(f"{path.relative_to(repo)} "
                             f"(stop_at_reward={ceiling}, num_trials={trials})")
    assert not offenders, (
        "these templates ship a reward ceiling that trusts a single val measurement:\n  "
        + "\n  ".join(offenders))
