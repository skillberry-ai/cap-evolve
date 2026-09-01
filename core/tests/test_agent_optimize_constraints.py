"""Free-text stop_condition → re-checkable predicates (agent-optimize item B)."""

from __future__ import annotations

import json

import pytest

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
    assert p["predicates"] == [] and p["ambiguous"] == [] and p["unenforceable"] == []


def test_behavioral_prose_with_no_number_is_reported_unenforceable_not_dropped():
    """The live-run bug: a stop_condition mixing a real numeric ceiling with a
    behavioral clause that has NO number at all ("use screen.py before paying for
    full val each round") used to silently drop the second clause — neither enforced
    nor visible anywhere, which is exactly the silent-drop this field exists to end."""
    p = parse_constraints(
        "stop after $40; use screen.py before paying for full val each round")
    assert any(pr["kind"] == "max_usd" for pr in p["predicates"])
    assert any("screen.py" in u for u in p["unenforceable"]), p["unenforceable"]


def test_a_fully_numeric_condition_leaves_nothing_unenforceable():
    p = parse_constraints("reach val mean >= 0.75, or stop after $40 / 90 minutes")
    assert p["unenforceable"] == [], p["unenforceable"]


def test_unenforceable_survives_into_the_check_payload():
    from cap_evolve.constraints import check_constraints
    p = parse_constraints("stop after $40; use screen.py before paying for full val")
    r = check_constraints(p, usd=0.0)
    assert any("screen.py" in u for u in r["unenforceable"]), r["unenforceable"]


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


def test_a_train_or_test_qualified_score_goal_is_reported_not_installed_as_val():
    """A score goal naming another split must NEVER become ``target_val_score``.

    ``spend.py`` only ever checks a score goal against the FULL-VAL mean (honesty
    invariant 1), so parsing "train mean >= 0.9" into ``target_val_score`` would
    enforce a val bar while telling the user their train bar was being watched.
    """
    for prose, split in (("reach train mean >= 0.90", "train"),
                         ("reach 90% on the test split", "test"),
                         ("get to 90% on the train set", "train"),
                         ("val mean of 0.9 on the training set", "train")):
        p = parse_constraints(prose)
        assert not any(x["kind"] == "target_val_score" for x in p["predicates"]), \
            f"{prose!r} silently became a VAL goal: {p['predicates']}"
        assert any(isinstance(a, str) and split in a for a in p["ambiguous"]), \
            f"{prose!r} was dropped without being reported: {p['ambiguous']}"


def test_plain_val_score_goals_still_parse_after_the_split_veto():
    """The veto must not eat the ordinary phrasings the parser exists for."""
    for prose, want in (("reach val mean >= 0.95", 0.95),
                        ("stop when val reaches 0.85", 0.85),
                        ("target: 0.7", 0.7),
                        ("reach 90% on val", 0.9),
                        ("reach 0.8", 0.8)):
        assert _kinds(parse_constraints(prose)).get("target_val_score") == want, prose


def test_spec_for_run_reads_the_spec_the_run_was_started_with(tmp_path):
    """A non-default spec filename must not silently yield zero constraints.

    ``cap-evolve run --spec capevolve.agentopt.yaml`` is fully supported, but the readout
    scripts used to hardcode ``project/capevolve.yaml``. On a real run that made
    ``spend.py`` report ``predicates: []`` — the entire re-read-your-constraints
    discipline no-opping without a word.
    """
    from cap_evolve.specfile import spec_for_run

    project = tmp_path / "project"
    project.mkdir()
    (project / "capevolve.yaml").write_text('stop_condition: "reach val mean >= 0.10"\n',
                                            encoding="utf-8")
    (project / "capevolve.agentopt.yaml").write_text(
        'stop_condition: "reach val mean >= 0.95"\nnum_trials: 3\n', encoding="utf-8")

    class _RD:
        events_path = tmp_path / "events.jsonl"

    # No run_config event yet -> falls back to the project default.
    _RD.events_path.write_text('{"kind": "splits", "val": 2}\n', encoding="utf-8")
    assert spec_for_run(_RD, project)["stop_condition"] == "reach val mean >= 0.10"

    # With a run_config event, the RUN's own spec wins.
    with _RD.events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "run_config",
                            "spec": str(project / "capevolve.agentopt.yaml")}) + "\n")
    spec = spec_for_run(_RD, project)
    assert spec["stop_condition"] == "reach val mean >= 0.95"
    assert spec["num_trials"] == 3
    assert parse_constraints(spec["stop_condition"])["predicates"], \
        "the run's real stop_condition must parse into predicates"

    # A missing project and a missing spec are both survivable, not fatal.
    _RD.events_path.write_text("", encoding="utf-8")
    assert spec_for_run(_RD, None) == {}


def _pt(tid, reward):
    return {"task_id": str(tid), "reward": float(reward), "raw": {"valid_trials": 1}}


def test_full_val_ceiling_proves_an_accept_impossible_when_the_screen_covers_all_failures():
    """The measured cand_r1_disc / cand_r3_lookup case from the gpt-oss-120b run.

    Parent (seed) is 9/12 on val, failing 24/40/44. The tier-1 subset was
    [0,12,16,24,40,44] — every failing task plus 3 the parent passes. The candidate fixed
    none and broke 12, so even a perfect score on all 6 unscreened tasks caps it at 8/12
    = 0.667 < 0.750. No full-val eval could accept it; paying for one buys nothing.
    """
    from cap_evolve.subsample import full_val_ceiling

    val = [str(i) for i in range(0, 48, 4)]
    parent = [_pt(i, 0.0 if i in (24, 40, 44) else 1.0) for i in range(0, 48, 4)]
    subset = ["0", "12", "16", "24", "40", "44"]
    cand = [_pt(t, r) for t, r in (("0", 1.0), ("12", 0.0), ("16", 1.0),
                                   ("24", 0.0), ("40", 0.0), ("44", 0.0))]
    c = full_val_ceiling(parent, cand, subset, val)
    assert c["accept_possible"] is False
    assert c["candidate_best_case_mean"] == pytest.approx(8 / 12, abs=1e-6)
    assert c["parent_mean"] == pytest.approx(0.75)
    assert c["best_case_mean_delta"] == pytest.approx(-1 / 12, abs=1e-6)
    assert c["n_unscreened_assumed_perfect"] == 6


def test_full_val_ceiling_leaves_accept_possible_when_the_candidate_fixed_something():
    """It must never foreclose a candidate that could still clear the gate."""
    from cap_evolve.subsample import full_val_ceiling

    val = [str(i) for i in range(0, 48, 4)]
    parent = [_pt(i, 0.0 if i in (24, 40, 44) else 1.0) for i in range(0, 48, 4)]
    subset = ["0", "12", "16", "24", "40", "44"]
    cand = [_pt(t, r) for t, r in (("0", 1.0), ("12", 1.0), ("16", 1.0),
                                   ("24", 1.0), ("40", 0.0), ("44", 0.0))]
    c = full_val_ceiling(parent, cand, subset, val)
    assert c["accept_possible"] is True
    assert c["best_case_mean_delta"] == pytest.approx(1 / 12, abs=1e-6)


def test_full_val_ceiling_is_not_computable_without_coverage():
    """Missing data must produce a status, never a confident False."""
    from cap_evolve.subsample import full_val_ceiling

    assert "status" in full_val_ceiling([], [], [], [])
    assert "accept_possible" not in full_val_ceiling([_pt("a", 1.0)], [], ["a"], ["a"])


# --- run 32861747778: a gate at concurrency 100 -------------------------------

def _round_rc(*extra, run_dir="/nonexistent", concurrency="100"):
    """Invoke round.py's guard. Dummy paths: the refusal must precede any run-dir access."""
    import json as _json
    import subprocess as _sp
    import sys as _sys
    from pathlib import Path as _P
    here = _P(__file__).resolve().parents[2] / "skills/algorithms/agent-optimize/scripts"
    p = _sp.run([_sys.executable, str(here / "round.py"), "--run-dir", run_dir,
                 "--project", run_dir, "--candidates", "c1", "--n-trials", "1",
                 "--concurrency", concurrency, *extra],
                capture_output=True, text=True)
    try:
        return p.returncode, _json.loads(p.stdout or "{}")
    except Exception:
        return p.returncode, {"stdout": p.stdout, "stderr": p.stderr}


def test_a_gate_too_coarse_to_resolve_its_own_verdict_is_refused_not_warned():
    """Measured: the agent set --concurrency 100 after SKILL.md told it not to.

    round.py already warned in its own output ("cannot resolve an effect smaller than roughly
    0.08") and the run continued regardless, producing verdicts nobody should believe. This
    skill's own edit-form rule applies to the skill: where the agent has the criterion and
    violates it anyway, the form that works is a guard in the code, not another restatement in
    prose. `--gate-against control --no-control` is already refused this way, so refusal — not
    a silent clamp — is the established idiom here.
    """
    rc, out = _round_rc()
    assert rc == 2, f"concurrency 100 was accepted: rc={rc} {out}"
    blob = json.dumps(out).lower()
    assert "concurrency" in blob, f"the refusal does not name the offending knob: {out}"
    assert "8" in json.dumps(out), f"the refusal should name the value to use instead: {out}"


def test_the_high_concurrency_refusal_has_a_deliberate_escape_hatch():
    """A hard wall would break any tier that legitimately needs throughput; the point is that
    raising it must be an explicit, recorded choice rather than a default someone drifts into.
    """
    rc, out = _round_rc("--allow-high-concurrency")
    assert rc != 2 or "concurrency" not in json.dumps(out).lower(), (
        f"the escape hatch does not bypass the concurrency guard: rc={rc} {out}")


def test_the_default_concurrency_is_not_refused():
    """The guard must be silent on the value the skill actually documents."""
    rc, out = _round_rc(concurrency="8")
    blob = json.dumps(out).lower()
    assert not (rc == 2 and "concurrency" in blob), (
        f"the documented default was refused by its own guard: rc={rc} {out}")


def test_the_round_table_does_not_report_the_controls_reward_under_the_parents_tag():
    """Measured on run 32871360361: `parent: {tag: 'seed', reward: 0.34}` while
    `baseline.json` said the seed scored 0.38 — because line 214 loads `parent` from
    `gate_ref` (the CONTROL under --gate-against control) and line 266 emits it with
    `"tag": best`. Two different objects in one block, irreconcilable for anyone reading it.

    This is not cosmetic. The true parent vs the concurrently-measured control IS the round's
    temporal drift — the quantity that decides whether any delta means anything, measured at
    0.24/0.44/0.38 on identical seed bytes across three runs — and conflating them erases it.
    So the table must carry both, and the delta key must name what it is really measured
    against.
    """
    import pathlib  # noqa: PLC0415
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "skills/algorithms/agent-optimize/scripts/round.py").read_text(encoding="utf-8")

    assert '"delta_vs_parent"' not in src, (
        "delta_vs_parent is computed against gate_ref, which under --gate-against control is "
        "the control, not the parent — the key name lies")
    assert '"delta_vs_gate_ref"' in src, "the delta key must name its actual reference"
    assert '"gate_reference"' in src, (
        "the table must report the object deltas were computed against, separately from the "
        "parent it is climbing from")
    assert '"parent_vs_gate_ref_drift"' in src, (
        "the parent-vs-control gap is the round's own drift measurement and must be reported, "
        "not left for a reader to reconstruct from baseline.json")
    # The true parent must be read from `best`, never from gate_ref.
    assert "split_result_from_rollouts(run_dir, best," in src, (
        "the parent block still sources its reward from gate_ref rather than from `best`")


def test_the_round_states_ONE_evidence_bar_matched_to_how_it_gated():
    """Measured on run 32871360361 round 2: the table handed the driver two incompatible bars
    and it took the wrong one.

    `cand2` was gated against a CONCURRENT control (0.24, replicate 0.25 — agreeing to 0.01) and
    beat it by +0.19, three times the k_se threshold. But the table also reported
    `noise_floor_from_control = 0.14`, which is the control-vs-STORED-parent gap, i.e. temporal
    drift — and its `reading` said "treat any candidate whose |delta| is at or below that as no
    evidence". Comparing a control-relative delta against a drift-derived floor is apples to
    oranges, and the driver resolved the ambiguity conservatively: it re-derived +0.05 against
    the stored best and booked a REJECT on a candidate that had cleared its concurrent control
    nineteen times over.

    Drift is exactly what control-mode gating removes, so under that mode the bar is the
    replicate null delta. Under parent-mode gating the delta IS against a stored reward, so
    drift belongs in the bar. One number, named, matched to the mode.
    """
    import pathlib  # noqa: PLC0415
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "skills/algorithms/agent-optimize/scripts/round.py").read_text(encoding="utf-8")

    assert '"evidence_bar"' in src, (
        "the round must state ONE bar the candidate delta is judged against, or the driver "
        "picks between the several numbers reported and may pick the wrong one")
    # It must be mode-aware: the replicate gap under control gating, drift-inclusive otherwise.
    bar = src[src.index('"evidence_bar"'):]
    bar = bar[:bar.index("\n\n")] if "\n\n" in bar[:1500] else bar[:1500]
    assert "gate_against" in bar or "control" in bar, (
        f"evidence_bar is not matched to the gate mode: {bar[:400]}")
    # And the drift must be described as affecting the absolute number, not as a bar to clear.
    assert "absolute" in src.lower(), (
        "nothing tells the reader that drift bounds the trustworthiness of the ABSOLUTE reward "
        "rather than the candidate-vs-control comparison")


def test_a_verdict_that_flips_with_the_choice_of_control_replicate_is_marked_unstable():
    """Measured on run 32871360361 round 3: the verdict was decided by a coin flip.

    Two byte-identical control replicates, measured two minutes apart, read 0.32 and 0.20 — a
    0.12 gap. The gate reference was whichever one carried the round-scoped tag (0.20), so
    `cand3` at 0.37 scored +0.17 and ACCEPTED. Against the other replicate it is +0.05 and
    rejects. Nothing in the table said the verdict rested on that choice.

    Re-gating against each replicate costs no new rollouts — they are already stored — so the
    round can simply report whether its verdict survives every reference it could have used. One
    that does not is not evidence, however large the delta looks against the replicate that
    happened to be picked.
    """
    import pathlib  # noqa: PLC0415
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "skills/algorithms/agent-optimize/scripts/round.py").read_text(encoding="utf-8")

    assert '"verdict_stable"' in src, (
        "the table does not say whether the verdict survives the choice of control replicate, "
        "so a coin-flip accept is indistinguishable from a real one")
    assert '"verdict_by_reference"' in src, (
        "the per-replicate verdicts must be shown, not just a boolean, or nobody can see how "
        "close the call was")
    assert "unstable" in src.lower(), (
        "the reading must tell the driver an unstable verdict is not evidence")


def test_rejecting_a_candidate_the_gate_ACCEPTED_cannot_claim_the_gate_as_its_basis():
    """Run 32871360361's audit log says cand2 was rejected on basis `gate`. The gate accepted it.

    `--reject-basis gate` is documented as "full-val paired gate ran", so anyone reading
    events.jsonl concludes the gate rejected the candidate. In fact round_i1.json recorded
    `verdict: accept` at +0.19 against a concurrent control, and the driver overrode it on its own
    reading of the drift. Overriding is legitimate — round.py explicitly leaves the decision to
    the driver — but recording it as the gate's own verdict makes the run's history wrong about
    the one thing it exists to preserve.

    commit.py already refuses an incoherent basis ("--reject-basis is meaningless on an accept"),
    so the idiom exists; it just could not see the gate's verdict until round.py started
    persisting its table.
    """
    import pathlib  # noqa: PLC0415
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "skills/algorithms/agent-optimize/scripts/commit.py").read_text(encoding="utf-8")

    assert "driver_judgement" in src, (
        "there is no truthful basis for an override, so a driver that disagrees with the gate has "
        "no honest option but to misattribute the reject to the gate")
    assert "gate_verdict" in src, (
        "the booked event must carry the gate's own verdict, so a divergence between what the "
        "gate said and what was booked is visible in events.jsonl rather than lost")
    assert "overrode_gate" in src, (
        "an override must be marked as one in the audit record")


def test_a_parent_gated_round_still_reports_the_drift_free_comparison_it_measured():
    """Run 32871360361 round 4 held both answers in one table and printed only the weaker one.

    It gated in `parent` mode: `cand4` 0.53 against the seed's STORED 0.38 = +0.15, bar 0.11
    (drift), so 1.4x — marginal. But the round also measured two concurrent controls that read
    **exactly 0.27 both times**, so the drift-free comparison from the very same rollouts is +0.26
    against a bar of 0.00. The 0.11 is a property of *when* the seed was measured, not of `cand4`;
    parent-mode gating both understated the effect and inflated the bar.

    Rather than change the default gate mode on one benchmark's evidence, report both: the
    control-relative comparison costs no rollouts (the controls are already evaluated and
    `gate_check.py` reads stored data), and on a benchmark without drift the two simply agree.
    """
    import pathlib  # noqa: PLC0415
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "skills/algorithms/agent-optimize/scripts/round.py").read_text(encoding="utf-8")

    assert '"control_relative"' in src, (
        "a parent-gated round throws away the drift-free comparison it already paid to measure, "
        "so a real improvement can read as marginal with no way to see why")
    assert "drift" in src.lower(), "the report must name what separates the two comparisons"
