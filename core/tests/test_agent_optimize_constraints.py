"""Free-text stop_condition → re-checkable predicates (agent-optimize item B)."""

from __future__ import annotations

from cap_evolve.constraints import check_constraints, parse_constraints


def _kinds(parsed):
    return {p["kind"]: p["target"] for p in parsed["predicates"]}


# ---- parsing --------------------------------------------------------------

def test_parses_the_canonical_prose_condition():
    p = parse_constraints("reach val mean >= 0.75, or stop after $40 / 90 minutes")
    k = _kinds(p)
    assert k["target_val_score"] == 0.75
    assert k["max_usd"] == 40.0
    assert k["max_wallclock_seconds"] == 5400.0
    assert p["text"].startswith("reach val mean")


def test_percentages_and_bare_percents_normalize_to_a_fraction():
    assert _kinds(parse_constraints("score of 75%"))["target_val_score"] == 0.75
    assert _kinds(parse_constraints("val mean >= 90%"))["target_val_score"] == 0.90


def test_counters_and_stall():
    k = _kinds(parse_constraints("stop after 5 iterations or 3 rejects in a row "
                                "or 200 rollouts"))
    assert k["max_iterations"] == 5.0
    assert k["max_stall"] == 3.0
    assert k["max_metric_calls"] == 200.0


def test_hours_and_glued_units():
    assert _kinds(parse_constraints("finish within 2 hours"))["max_wallclock_seconds"] == 7200.0
    assert _kinds(parse_constraints("finish within 90m"))["max_wallclock_seconds"] == 5400.0


def test_protected_tasks_are_extracted():
    p = parse_constraints("don't regress task 12")
    prot = [x["target"] for x in p["predicates"] if x["kind"] == "protect_task"]
    assert prot == ["12"]


def test_tightest_ceiling_wins_and_highest_goal_wins():
    k = _kinds(parse_constraints("budget $50, hard cap $20; reach 0.6, ideally hit 0.8"))
    assert k["max_usd"] == 20.0
    assert k["target_val_score"] == 0.8


def test_vague_prose_is_reported_as_ambiguous_not_guessed():
    p = parse_constraints("stop when it's good enough and don't spend too much")
    assert p["predicates"] == []
    whys = " ".join(a["why"] for a in p["ambiguous"])
    assert "vague" in whys or "no checkable predicate" in whys


def test_a_number_with_no_unit_is_flagged():
    p = parse_constraints("stop after 7")
    assert any("no recognized unit" in a["why"] for a in p["ambiguous"])


def test_empty_condition_parses_to_nothing_without_complaining():
    p = parse_constraints("")
    assert p["predicates"] == [] and p["ambiguous"] == []


# ---- checking -------------------------------------------------------------

CONS = parse_constraints("reach val mean >= 0.75 or stop after $40 / 90 minutes; "
                         "don't regress task 12")


def test_continue_while_there_is_room_and_the_goal_is_unmet():
    r = check_constraints(CONS, best_val=0.4, usd=1.0, wallclock_seconds=60,
                          iterations=1)
    assert r["recommendation"] == "continue"


def test_score_goal_met_stops():
    r = check_constraints(CONS, best_val=0.80, usd=1.0, wallclock_seconds=60)
    assert r["recommendation"] == "stop"
    assert any("score goal met" in x for x in r["reasons"])


def test_usd_ceiling_breach_stops():
    r = check_constraints(CONS, best_val=0.1, usd=40.0, wallclock_seconds=10)
    assert r["recommendation"] == "stop"
    assert any("max_usd" in x for x in r["reasons"])


def test_wallclock_ceiling_breach_stops():
    r = check_constraints(CONS, best_val=0.1, usd=1.0, wallclock_seconds=5400)
    assert r["recommendation"] == "stop"


def test_eighty_percent_consumed_recommends_narrowing_scope():
    r = check_constraints(CONS, best_val=0.1, usd=34.0, wallclock_seconds=60)
    assert r["recommendation"] == "narrow_scope"
    assert any("max_usd" in x for x in r["reasons"])


def test_protected_task_regression_stops():
    r = check_constraints(CONS, best_val=0.1, usd=1.0, regressed_tasks=["12"])
    assert r["recommendation"] == "stop"
    assert any("protected task" in x for x in r["reasons"])
    row = next(x for x in r["predicates"] if x["kind"] == "protect_task")
    assert row["violated"] is True


def test_score_goal_is_documented_as_full_val_only():
    r = check_constraints(CONS, best_val=None, usd=0.0)
    row = next(x for x in r["predicates"] if x["kind"] == "target_val_score")
    assert row["satisfied"] is False and "FULL-val" in row["note"]


def test_remaining_budget_is_reported_per_ceiling():
    r = check_constraints(CONS, best_val=0.1, usd=10.0, wallclock_seconds=600)
    assert r["remaining"]["max_usd"] == 30.0
    assert r["remaining"]["max_wallclock_seconds"] == 4800.0


def test_ambiguity_survives_into_the_check_payload():
    r = check_constraints(parse_constraints("stop when it feels reasonable"))
    assert r["ambiguous"], "an unparseable condition must not look like 'no constraint'"


# ---- regressions: the parser was WRONG where it was CONFIDENT ---------------
#
# The pattern in every bug below: the ambiguity mechanism was fine, and these cases
# bypassed it entirely to report a confident wrong number. A $0 ceiling is the worst
# of them — budget_exhausted() is true before the first rollout, so the run dies with
# a message blaming spend instead of parsing.

import re

from cap_evolve.constraints import _NUM


def test_grouped_digit_money_parses_to_the_full_value():
    assert _kinds(parse_constraints("don't spend over $1,500.50"))["max_usd"] == 1500.50
    assert _kinds(parse_constraints("budget $1,200"))["max_usd"] == 1200.0
    assert _kinds(parse_constraints("max spend 2,000 USD"))["max_usd"] == 2000.0
    assert _kinds(parse_constraints("budget $1200"))["max_usd"] == 1200.0


def test_no_money_predicate_ever_understates_a_grouped_digit_amount():
    """The invariant, stated directly: if a $ amount is parsed at all, it is parsed WHOLE.

    A regression here is invisible until someone loses a run, so assert it over a grid
    rather than the four strings that happened to be reported.
    """
    for text, want in [("$1,200", 1200.0), ("$12,000", 12000.0),
                       ("$1,234,567", 1234567.0), ("$1,000.25", 1000.25),
                       ("2,000 USD", 2000.0), ("10,500 dollars", 10500.0),
                       ("$999", 999.0), ("$0.50", 0.50)]:
        got = _kinds(parse_constraints(f"stop after {text}"))
        assert got.get("max_usd") == want, f"{text!r} -> {got.get('max_usd')} != {want}"


def test_a_grouped_number_is_never_split_by_the_numeric_pattern():
    """Root cause: alternation order. A bare \\d+ matched "1" of "1,200" and stopped."""
    assert re.findall(_NUM, "1,200 and 2,000.50 and 7") == ["1,200", "2,000.50", "7"]


def test_a_zero_dollar_budget_is_never_invented_from_a_grouped_amount():
    """`2,000 USD` used to yield max_usd=0.0 (the bare pattern matched the trailing 000)."""
    r = check_constraints(parse_constraints("max spend 2,000 USD"), best_val=0.1, usd=1.0)
    assert r["recommendation"] == "continue"
    row = next(p for p in r["predicates"] if p["kind"] == "max_usd")
    assert row["target"] == 2000.0 and row["violated"] is False


def test_per_iteration_and_total_money_are_kept_apart():
    p = parse_constraints("spend at most $5 per iteration but no more than $60 total")
    k = _kinds(p)
    assert k["max_usd"] == 60.0, "the TOTAL cap must not be replaced by the per-iter figure"
    assert k["max_usd_per_iteration"] == 5.0


def test_a_per_iteration_cap_alone_is_flagged_not_treated_as_a_total():
    p = parse_constraints("spend at most $5 per iteration")
    assert "max_usd" not in _kinds(p)
    assert any("PER-ITERATION" in a["why"] for a in p["ambiguous"])


def test_a_per_iteration_cap_is_reported_but_not_enforced_as_a_ceiling():
    p = parse_constraints("$5 per iteration, $60 total")
    r = check_constraints(p, best_val=0.1, usd=10.0)
    row = next(x for x in r["predicates"] if x["kind"] == "max_usd_per_iteration")
    assert row["satisfied"] is None and "not a total" in row["note"]
    assert r["recommendation"] == "continue"


def test_bare_decimal_score_targets_are_recognized():
    assert _kinds(parse_constraints(
        "Stop when val reaches 0.85 or after spending $50"))["target_val_score"] == 0.85
    assert _kinds(parse_constraints(
        "Budget: 100 USD. Target: 0.7. Max 20 iterations."))["target_val_score"] == 0.7
    assert _kinds(parse_constraints("goal = 0.9"))["target_val_score"] == 0.9
    assert _kinds(parse_constraints("get to 0.8 on val"))["target_val_score"] == 0.8


def test_a_recognized_score_target_is_no_longer_flagged_unitless():
    p = parse_constraints("Stop when val reaches 0.85 or after spending $50")
    assert not any("no recognized unit" in a["why"] for a in p["ambiguous"]), p["ambiguous"]


def test_genuinely_unitless_numbers_are_still_flagged():
    """The good half of the parser must survive the fix."""
    p = parse_constraints("stop after 7")
    assert p["predicates"] == []
    assert any("no recognized unit" in a["why"] for a in p["ambiguous"])


def test_the_projects_real_stop_condition_parses_completely():
    p = parse_constraints("reach val mean >= 0.95, or stop after $40 or 120 minutes "
                          "or 3 rejects in a row; don't regress task 0")
    k = _kinds(p)
    assert k["target_val_score"] == 0.95 and k["max_usd"] == 40.0
    assert k["max_wallclock_seconds"] == 7200.0 and k["max_stall"] == 3.0
    assert p["ambiguous"] == [], p["ambiguous"]
