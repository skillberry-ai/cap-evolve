"""Subset screening: deterministic selection, and a screen that cannot accept."""

from __future__ import annotations

from cap_evolve.subsample import (
    GROSS_KILL_DELTA, paired_deltas_on, screen_decision, screen_savings,
    select_screen_subset,
)


def _pt(tid, reward, *, stderr=0.0, valid=1):
    return {"task_id": tid, "reward": reward, "stderr": stderr,
            "raw": {"valid_trials": valid, "n_trials": max(1, valid)}}


PARENT = [
    _pt("t0", 1.0), _pt("t1", 1.0), _pt("t2", 1.0), _pt("t3", 1.0),
    _pt("t4", 0.0), _pt("t5", 0.0), _pt("t6", 0.5, stderr=0.5), _pt("t7", 0.0),
]


# ---- selection ------------------------------------------------------------

def test_selection_is_deterministic_for_a_seed():
    a = select_screen_subset(PARENT, k=4, seed=7)
    b = select_screen_subset(PARENT, k=4, seed=7)
    assert a == b
    assert len(a["ids"]) == 4
    assert a["ids"] == sorted(a["ids"])


def test_holdout_comes_from_currently_passing_tasks():
    """The holdout is the only part of a screen that can see a regression."""
    s = select_screen_subset(PARENT, k=6, seed=1, holdout_frac=0.5)
    assert s["holdout"], "no holdout drawn"
    for tid in s["holdout"]:
        assert next(p for p in PARENT if p["task_id"] == tid)["reward"] >= 1.0


def test_informative_half_prefers_failing_and_high_variance():
    s = select_screen_subset(PARENT, k=4, seed=1, holdout_frac=0.0)
    # zero holdout ⇒ every slot is informative ⇒ all four failing/unstable tasks
    assert set(s["ids"]) == {"t4", "t5", "t6", "t7"}
    assert s["holdout"] == []


def test_broken_tasks_are_screened_first():
    s = select_screen_subset(PARENT, k=3, seed=3, holdout_frac=0.34, broken_ids=["t0"])
    assert "t0" in s["ids"] and s["broken"] == ["t0"]


# ---- rationale (issue #437) -----------------------------------------------

def test_rationale_names_broken_informative_and_holdout_tasks():
    s = select_screen_subset(PARENT, k=6, seed=1, holdout_frac=0.5, broken_ids=["t0"])
    assert "t0" in s["rationale"]
    for tid in s["informative"]:
        assert tid in s["rationale"]
    for tid in s["holdout"]:
        assert tid in s["rationale"]


def test_rationale_is_never_empty_for_a_nonempty_subset():
    s = select_screen_subset(PARENT, k=4, seed=1)
    assert s["rationale"]


def test_unmeasured_tasks_are_never_screened():
    """A task with no valid trial is missing data, not a 0.0 to go re-measure."""
    parent = PARENT + [_pt("ghost", 0.0, valid=0)]
    s = select_screen_subset(parent, k=8, seed=0, holdout_frac=0.0)
    assert "ghost" not in s["ids"]
    assert s["pool_n"] == len(PARENT)


def test_different_seeds_move_the_holdout_but_not_the_size():
    a = select_screen_subset(PARENT, k=4, seed=1)
    b = select_screen_subset(PARENT, k=4, seed=99)
    assert len(a["ids"]) == len(b["ids"]) == 4
    assert a["holdout"] != b["holdout"] or a["ids"] == b["ids"]


def test_k_larger_than_the_pool_is_clamped():
    s = select_screen_subset(PARENT, k=99, seed=0)
    assert len(s["ids"]) == len(PARENT) and s["requested_k"] == 99


# ---- the decision (issue #684 item 5: gross-failure kill, not significance) -----

def test_unanimous_negative_subset_is_killed():
    d = screen_decision([-1.0, -1.0, -1.0])
    assert d["decision"] == "kill"


def test_gross_negative_is_killed_regardless_of_se():
    """A clearly-broken candidate kills even though SE is nonzero (the point of #684:

    the old rule required Δ̄ + k_se·SE < 0, which a wide-SE subset like this could
    never clear; the new rule only looks at the mean.
    """
    d = screen_decision([-1.0, -1.0, -1.0, 0.0], k_se=1.0)
    assert d["decision"] == "kill" and d["se"] > 0.0


def test_mild_negative_above_gross_threshold_promotes_not_killed():
    """A real close-call effect size (chased in a real run: 0.02-0.09) must not die here."""
    d = screen_decision([-0.09, 0.0, 0.0, 0.0], k_se=1.0)
    assert d["decision"] == "promote" and d["inconclusive"] is True


def test_noisy_negative_is_promoted_not_killed():
    """Biased against false kills: one bad task out of four is not a gross failure."""
    d = screen_decision([-1.0, 0.0, 0.0, 1.0], k_se=1.0)
    assert d["decision"] == "promote"
    assert d["mean_delta"] == 0.0 and d["inconclusive"] is False


def test_zero_mean_promotes_because_a_subset_cannot_prove_no_effect():
    d = screen_decision([0.0, 0.0, 0.0, 0.0])
    assert d["decision"] == "promote"


def test_custom_gross_kill_threshold_is_honored():
    d = screen_decision([-0.2, -0.2, -0.2], gross_kill_threshold=-0.3)
    assert d["decision"] == "promote"
    d2 = screen_decision([-0.2, -0.2, -0.2], gross_kill_threshold=-0.1)
    assert d2["decision"] == "kill"


def test_empty_deltas_promote_rather_than_kill_on_an_infra_fault():
    d = screen_decision([])
    assert d["decision"] == "promote" and d["n"] == 0


def test_screen_never_returns_accept():
    for ds in ([-1.0] * 4, [1.0] * 4, [0.0, 1.0, -1.0], []):
        assert screen_decision(ds)["decision"] in ("kill", "promote")


def test_churn_candidate_promotes_but_reports_its_regressions():
    """The motivating failure: fixes 2, breaks 2, identical mean.

    A screen must not kill it (the mean says nothing) and must not hide the breakage —
    the full-val no-regression veto is what rejects it.
    """
    parent = [_pt("a", 1.0), _pt("b", 1.0), _pt("c", 0.0), _pt("d", 0.0)]
    cand = [_pt("a", 0.0), _pt("b", 0.0), _pt("c", 1.0), _pt("d", 1.0)]
    pair = paired_deltas_on(parent, cand, ["a", "b", "c", "d"])
    assert pair["regressed"] == ["a", "b"] and pair["fixed"] == ["c", "d"]
    d = screen_decision(pair["deltas"], regressed=pair["regressed"])
    assert d["decision"] == "promote"
    assert d["mean_delta"] == 0.0
    assert d["regressed"] == ["a", "b"]


# ---- pairing --------------------------------------------------------------

def test_pairing_drops_unmeasured_tasks_instead_of_scoring_them_minus_one():
    parent = [_pt("a", 1.0), _pt("b", 1.0)]
    cand = [_pt("a", 1.0), _pt("b", 0.0, valid=0)]
    pair = paired_deltas_on(parent, cand, ["a", "b"])
    assert pair["deltas"] == [0.0] and pair["dropped"] == ["b"]
    assert pair["regressed"] == []


def test_pairing_ignores_ids_outside_the_subset():
    parent = [_pt("a", 0.0), _pt("b", 0.0)]
    cand = [_pt("a", 1.0), _pt("b", 1.0)]
    assert paired_deltas_on(parent, cand, ["a"])["ids"] == ["a"]


# ---- economics ------------------------------------------------------------

def test_savings_are_measured_and_a_promote_costs_rather_than_saves():
    kill = screen_savings(fired=4, val_n=15, n_trials=2, decision="kill")
    assert kill["full_val_rollouts"] == 30 and kill["avoided"] == 26
    assert kill["net_rollouts"] == 26
    promote = screen_savings(fired=4, val_n=15, n_trials=2, decision="promote")
    assert promote["avoided"] == 0 and promote["net_rollouts"] == -4


# ---- issue #684 item 5: screening_economics audit, real-run fixture -------

def test_gross_kill_default_sits_between_drift_and_real_failure():
    """-0.15 default: above the ~0.10 drift measured between byte-identical control
    replicates (so ordinary re-measurement noise never trips it), below the ~0.2 of the
    one confirmed gross failure in a real run (so it still catches what it exists for).
    """
    assert -0.20 < GROSS_KILL_DELTA < -0.10


def test_cand7_old_significance_rule_would_have_missed_this_gross_failure():
    """Reproduces the confirmed bug: cand_7's tier-1 screen delta was -0.2 — a real
    gross negative (an infra-broken edit) — but 0 of 7 candidates screen-killed in that
    run because tier-1 SEs (0.11-0.17) were wide enough to swallow it. This fixture
    constructs an n=6 subset with mean Δ̄=-0.2 and a wide enough SE that the OLD rule
    (``mean(Δ) + k_se·SE < 0``) promotes it instead of killing it.
    """
    deltas = [-1.0, -1.0, 0.0, 0.0, 0.0, 0.8]
    n = len(deltas)
    mean = sum(deltas) / n
    assert round(mean, 4) == -0.2
    var = sum((d - mean) ** 2 for d in deltas) / (n - 1)
    se = (var / n) ** 0.5
    assert mean + 1.0 * se > 0, "sanity check: the OLD significance rule promoted this"

    d = screen_decision(deltas)
    assert d["decision"] == "kill", "the NEW gross-threshold rule kills it instead"


def test_genuinely_close_calls_still_promote_under_the_new_rule():
    """The real round deltas that mattered in that run were 0.02-0.09 in magnitude —
    the new gross-kill rule must not be trigger-happy on noise of that size, whichever
    sign it falls on.
    """
    for mean in (0.02, 0.05, 0.09, -0.02, -0.05, -0.09):
        deltas = [mean] * 6
        d = screen_decision(deltas)
        assert d["decision"] == "promote", f"wrongly killed a close call at Δ̄={mean}"
