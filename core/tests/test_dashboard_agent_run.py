"""Reducer fixes for AGENT-DRIVEN runs (agent-optimize / evograph).

Every case here failed on the one real ``agent-optimize`` run in the repo
(``examples/tau2_airline/run_agentopt``) before these fixes, and each failure looked
like an empty or mislabelled dashboard rather than an error:

* the run was labelled "algorithm not recorded" — its only distinguishing event is
  ``screen``, which the marker table did not know about;
* every gate rationale rendered blank — agent-mode commits put it in ``note``, not
  ``reason``, so the most informative field in the run was dropped;
* the per-task matrix had a lone seed column — the run persists per-candidate per-task
  rewards in ``val_per_task.json`` and nothing read it;
* each candidate's eval cost read "—" beside a cost ledger showing the same dollars —
  the spend is on the ``evaluate`` event, not on the commit;
* the sealed test number had nothing to be read against — ``final.json``'s
  ``test_baseline``/``test_delta`` were never published;
* the tiered cheap screens (``screen`` events + ``screens/*.json``) were invisible.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

#: An agent-driven run exactly as the real one is shaped: no run_config, no
#: algorithm-specific "round" event, commits via accept/reject carrying ``note``.
_EVENTS = [
    {"t": 1.0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"t": 2.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
     "stderr": 0.25, "cost_usd": 0.90, "tokens": 10, "seconds": 12.0, "n_scored": 2},
    {"t": 3.0, "kind": "baseline", "val": 0.5, "stderr": 0.25, "n_scored": 2},
    {"t": 4.0, "kind": "screen", "tag": "cand_a", "tier": 1, "ids": ["t1", "t2"],
     "fired": 2, "decision": "promote", "mean_delta": 0.5, "se": 0.5, "n": 2,
     "inconclusive": True, "net_rollouts": -2,
     "rationale": "1 most-informative failing/high-variance task(s) ['t2']; 1 random "
                  "regression-canary task(s) ['t1'] drawn (seed 1) from tasks the parent "
                  "currently passes"},
    {"t": 5.0, "kind": "evaluate", "split": "val", "tag": "cand_a", "reward": 0.5,
     "stderr": 0.25, "cost_usd": 1.25, "tokens": 20, "seconds": 30.0, "n_scored": 2},
    {"t": 6.0, "kind": "reject", "candidate": "cand_a", "val": 0.5,
     "note": "churn — fixed t2, broke t1, paired delta 0.0000"},
    {"t": 7.0, "kind": "finalize", "test_reward": 0.5, "best_id": "seed"},
]

_BASELINE = {"val": {"reward": 0.5, "stderr": 0.25, "cost_usd": 0.90, "seconds": 12.0,
                     "per_task": [{"task_id": "t1", "reward": 1.0},
                                  {"task_id": "t2", "reward": 0.0}]}}
_FINAL = {"test": {"split": "test", "reward": 0.5, "stderr": 0.25, "pass_k": {"1": 0.5},
                   "per_task": [{"task_id": "s1", "reward": 1.0, "n": 1}]},
          "test_baseline": {"split": "test", "reward": 0.5}, "test_delta": 0.0,
          "best_id": "seed", "baseline_id": "seed"}

_VAL_PER_TASK = {
    "seed": {"per_task": {"t1": 1.0, "t2": 0.0}, "stderr": 0.25, "n_scored": 2},
    # Same mean as the seed, different tasks passing — the churn the matrix exists for.
    "cand_a": {"per_task": {"t1": 0.0, "t2": 1.0}, "stderr": 0.25, "n_scored": 2,
               "fixed": ["t2"], "broke": ["t1"]},
}

_SCREEN_FILE = {
    "tag": "cand_a", "screen_tag": "cand_a__screen1", "tier": 1, "current": "seed",
    "subset": {"ids": ["t1", "t2"], "holdout": ["t1"], "informative": ["t2"],
               "k": 2, "pool_n": 2},
    "paired": {"deltas": [-1.0, 1.0], "ids": ["t1", "t2"],
               "regressed": ["t1"], "fixed": ["t2"], "dropped": []},
    "decision": "promote", "inconclusive": True, "n": 2, "mean_delta": 0.0, "se": 0.5,
    "threshold": -0.5,
}


def _reduce(*, with_per_task=True, with_screens=True):
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text(
        "\n".join(json.dumps(e) for e in _EVENTS) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps(_BASELINE), encoding="utf-8")
    (rd.root / "final.json").write_text(json.dumps(_FINAL), encoding="utf-8")
    if with_per_task:
        (rd.root / "val_per_task.json").write_text(
            json.dumps(_VAL_PER_TASK), encoding="utf-8")
    if with_screens:
        d = rd.root / "screens"
        d.mkdir(exist_ok=True)
        (d / "cand_a__screen1.json").write_text(json.dumps(_SCREEN_FILE), encoding="utf-8")
    return dashboard.reduce_run(rd)


def _node(reduced, nid):
    return next(n for n in reduced["graph"]["nodes"] if n["id"] == nid)


def test_screen_event_identifies_agent_optimize():
    """``screen`` is agent-optimize's and nobody else's — it must name the algorithm.

    A real agent-driven run emits no ``agent_round``/``run_config``, so before this the
    marker table matched nothing and the whole run rendered as "algorithm not recorded"
    with none of the agent panels mounted.
    """
    s = _reduce()["summary"]
    assert s["algorithm"] == "agent-optimize"
    assert s["algorithm_source"] == "events"
    # freeform gates the agent-rounds panel; screens gates the screens panel.
    assert s["capabilities"]["freeform"] is True
    assert s["capabilities"]["screens"] is True


def test_agent_commit_note_becomes_the_gate_reason():
    """Agent-mode commits carry the rationale in ``note``; reading only ``reason`` lost it."""
    reduced = _reduce()
    assert "churn" in _node(reduced, "cand_a")["reason"]
    gate = next(g for g in reduced["summary"]["gate_decisions"] if g["candidate"] == "cand_a")
    assert gate["verdict"] == "reject"
    assert "broke t1" in gate["reason"]


def test_val_per_task_file_fills_the_per_task_matrix():
    """Per-candidate per-task rewards come from ``val_per_task.json`` when rollouts are gone."""
    reduced = _reduce()
    cand = _node(reduced, "cand_a")
    assert cand["per_task"] == {"t1": 0.0, "t2": 1.0}
    assert cand["stderr"] == 0.25
    assert cand["fixed"] == ["t2"] and cand["broke"] == ["t1"]
    # …and the evaluations table stops claiming the candidate scored 0 tasks.
    ev = next(e for e in reduced["summary"]["evaluations"] if e["candidate"] == "cand_a")
    assert ev["n_tasks"] == 2


def test_no_per_task_file_leaves_candidate_per_task_empty():
    """Absent evidence stays absent — the fallback must not invent per-task rewards."""
    cand = _node(_reduce(with_per_task=False), "cand_a")
    assert cand["per_task"] == {}


def test_candidate_eval_spend_comes_from_the_evaluate_event():
    """The commit records no spend; the eval that produced its val recorded all of it."""
    reduced = _reduce()
    cand = _node(reduced, "cand_a")
    assert cand["cost_usd"] == 1.25
    assert cand["runner_seconds"] == 30.0
    assert cand["tokens"] == 20
    ev = next(e for e in reduced["summary"]["evaluations"] if e["candidate"] == "cand_a")
    assert ev["cost_usd"] == 1.25


def test_sealed_test_is_published_with_its_baseline_and_delta():
    """A sealed test number means nothing without the seed's score on the same split."""
    s = _reduce()["summary"]
    assert s["test_reward"] == 0.5
    assert s["test_baseline_reward"] == 0.5
    assert s["test_delta"] == 0.0


def test_screens_expose_the_subset_and_its_movement():
    """The screen event's decision plus the screen file's subset/paired lists."""
    s = _reduce()["summary"]
    (sc,) = s["algo_extra"]["screens"]
    assert sc["candidate"] == "cand_a"
    assert sc["decision"] == "promote" and sc["inconclusive"] is True
    assert sc["holdout"] == ["t1"] and sc["informative"] == ["t2"]
    assert sc["fixed"] == ["t2"] and sc["regressed"] == ["t1"]
    assert sc["pool_n"] == 2
    assert "t2" in sc["rationale"] and "t1" in sc["rationale"]


def test_no_screens_means_no_screens_capability():
    s = _reduce(with_screens=False)["summary"]
    # The event alone still names the algorithm and yields a row; only the subset
    # detail is missing, and it must render as absent rather than as an empty subset.
    assert s["algorithm"] == "agent-optimize"
    (sc,) = s["algo_extra"]["screens"]
    assert sc["holdout"] == [] and sc["fixed"] == [] and sc["threshold"] is None


if __name__ == "__main__":  # self-check without pytest
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)


def test_gepa_minibatch_reads_the_ids_the_event_actually_wrote():
    """gepa writes ``ids``/``fired``, not ``tasks``/``n_tasks``.

    Reading only the latter left every minibatch row showing "n tasks —" and an empty
    subset, so the panel that exists to show WHICH cheap tasks screened a candidate
    showed none of them.
    """
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = [
        {"t": 1.0, "kind": "gepa_start"},
        {"t": 2.0, "kind": "minibatch", "tag": "mb_c_0000", "ids": ["a1", "a2", "a3"],
         "reward": 1.0, "fired": 3, "cached": 0},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (mb,) = dashboard.reduce_run(rd)["summary"]["algo_extra"]["minibatch"]
    assert mb["n_tasks"] == 3
    assert mb["tasks"] == ["a1", "a2", "a3"]


#: The other real agent-optimize shape (``run_agentopt_v2``): every candidate is KILLED
#: on the tier-1 cheap screen, so no commit carries a val, and the per-task rewards live
#: under the SCREEN tag as ``{tid: {reward, feedback}}``.
_SCREEN_ONLY_EVENTS = [
    {"t": 1.0, "kind": "splits", "train": 4, "val": 4, "test": 2, "seed": 0},
    {"t": 2.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5,
     "stderr": 0.25, "cost_usd": 0.0, "tokens": 0, "seconds": 10.0},
    {"t": 3.0, "kind": "baseline", "val": 0.5, "stderr": 0.25},
    {"t": 4.0, "kind": "screen", "tag": "cand_x", "tier": 1, "ids": ["t1", "t2"],
     "decision": "kill", "mean_delta": -0.5, "se": 0.2, "n": 2, "inconclusive": False},
    {"t": 5.0, "kind": "evaluate", "split": "val", "tag": "cand_x__screen1",
     "reward": 0.0, "stderr": 0.0, "subset": True, "subset_ids": ["t1", "t2"]},
    {"t": 6.0, "kind": "reject", "candidate": "cand_x", "val": None,
     "note": "KILLED by tier-1 screen; not promoted to full val"},
]


def _reduce_screen_only():
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text(
        "\n".join(json.dumps(e) for e in _SCREEN_ONLY_EVENTS) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps(
        {"val": {"reward": 0.5, "per_task": [{"task_id": "t1", "reward": 1.0},
                                             {"task_id": "t2", "reward": 0.0}]}}),
        encoding="utf-8")
    (rd.root / "val_per_task.json").write_text(json.dumps({
        "cand_x__screen1": {"t1": {"reward": 0.0, "feedback": "regressed"},
                            "t2": {"reward": 0.0, "feedback": "still failing"}},
    }), encoding="utf-8")
    return dashboard.reduce_run(rd)


def test_screen_killed_candidate_is_rejected_not_failed():
    """An explicit reject IS a verdict, even with no val — never a red "no measurement".

    A candidate agent-optimize kills on a cheap screen never reaches full val, so its
    commit carries ``val: null``. Treating "no val" as ``failed`` painted a failure badge
    on the screening mechanism working exactly as intended, and made a deliberate,
    cheap, correct kill indistinguishable from an infrastructure fault.
    """
    reduced = _reduce_screen_only()
    n = _node(reduced, "cand_x")
    assert n["status"] == "rejected"
    assert n["val"] is None  # and it still must NOT claim a val score
    assert reduced["summary"]["counts"]["failed"] == 0
    (gate,) = reduced["summary"]["gate_decisions"]
    assert gate["verdict"] == "reject"


def test_screen_tag_per_task_and_feedback_attach_to_the_candidate():
    """Per-task rewards recorded under ``<cid>__screenN`` belong to ``<cid>``.

    Also covers the ``{tid: {reward, feedback}}`` record shape — a run that wrote it got
    an empty matrix because only the bare-number shape was parsed.
    """
    n = _node(_reduce_screen_only(), "cand_x")
    assert n["per_task"] == {"t1": 0.0, "t2": 0.0}
    assert n["feedback"]["t1"] == "regressed"


# --- unmetered spend: $0 after real calls is missing data, not a free run -----

def test_spend_metered_flags_a_zero_that_nobody_measured():
    """The whole inference, in one table.

    A $0 total after real calls means no per-call cost was REPORTED. That covers a
    zero-API adapter (genuinely free) AND a real model behind a proxy that returns no
    usage (real spend, unpriced) -- the run dir cannot tell those apart, which is why
    the UI wording is "not reported" rather than any claim about money. Printing
    "$0.000" would assert a fact nobody measured, the same class of lie as `pass^k NaN%`.
    """
    from cap_evolve.dashboard import _spend_metered
    assert _spend_metered(0.0, 0) is True, "nothing ran: $0.00 is a real, correct zero"
    assert _spend_metered(0.0, 68) is False, "68 rollouts for exactly $0: no cost was reported"
    assert _spend_metered(12.98, 68) is True
    assert _spend_metered(0.0001, 5) is True, "a tiny real cost is still metered"


def test_the_unmetered_tau2_run_is_not_reported_as_free(tmp_path):
    """Regression on the real committed artifact, not a synthetic fixture.

    run_agentopt_v2 ran 68 real rollouts through a proxy that reports no cost;
    run_agentopt recorded $12.98. The reducer must tell them apart.
    """
    from pathlib import Path
    from cap_evolve import RunDir, dashboard
    base = Path(__file__).resolve().parents[2] / "examples" / "tau2_airline"
    if not (base / "run_agentopt_v2" / "events.jsonl").exists():
        import pytest
        pytest.skip("curated tau2 artifacts not present")

    unmetered = dashboard.reduce_run(RunDir.open(base / "run_agentopt_v2"))["summary"]
    metered = dashboard.reduce_run(RunDir.open(base / "run_agentopt"))["summary"]

    assert unmetered["cost"]["total_usd"] == 0.0
    assert unmetered["cost"]["metered"] is False
    assert unmetered["cost_ledger"]["metered"] is False

    assert metered["cost"]["total_usd"] > 0
    assert metered["cost"]["metered"] is True


# --- the cumulative-best stair must only count what the gate ACCEPTED ---------

def test_a_rejected_candidate_does_not_raise_the_running_best():
    """`best_so_far` feeds the TUI chart AND the self-contained dashboard.html chart.

    It used to advance on any non-indecisive candidate, so a REJECTED one raised the
    stair. On the real v4 tau2 run two candidates scored a raw 0.5833, were vetoed on
    no-regression, and every cumulative-best chart read 58.3% while the KPI tile beside
    it read 56.7% -- the chart contradicted the tile, and the chart was wrong.
    """
    from pathlib import Path
    from cap_evolve import RunDir, dashboard
    base = Path(__file__).resolve().parents[2] / "examples" / "tau2_airline" / "run_agentopt_v4"
    if not (base / "events.jsonl").exists():
        import pytest
        pytest.skip("curated v4 artifacts not present")

    red = dashboard.reduce_run(RunDir.open(base))
    nodes = red["graph"]["nodes"]
    best_val = red["summary"]["best_val"]

    # every candidate here was rejected, and two scored ABOVE the seed
    assert red["summary"]["best_id"] == "seed"
    raw = [n["val"] for n in nodes if n["status"] == "rejected" and n.get("val")]
    assert max(raw) > best_val, "fixture no longer exercises the bug"

    # the stair never exceeds the accepted best
    assert max(n.get("best_so_far") or 0 for n in nodes) == best_val
    # but the rejected measurements are still PLOTTED -- hiding them would be its own lie
    assert all(n.get("val") is not None for n in nodes if n["status"] == "rejected")


def test_an_accepted_candidate_still_raises_the_running_best():
    """The other direction: the fix must not freeze the stair on real progress."""
    from pathlib import Path
    from cap_evolve import RunDir, dashboard
    for run in ("run_hillclimb", "run_gepa", "run_skillopt"):
        base = Path("/tmp/dash-all") / run
        if not (base / "events.jsonl").exists():
            import pytest
            pytest.skip("deterministic e2e run dirs not present")
        red = dashboard.reduce_run(RunDir.open(base))
        nodes = red["graph"]["nodes"]
        assert any(n["status"] == "accepted" for n in nodes), run
        assert max(n.get("best_so_far") or 0 for n in nodes) == red["summary"]["best_val"]
        assert red["summary"]["best_val"] == 1.0, run


# ---- second round: gate structured fields / null-control replicates / screened badge ----

def test_gate_fields_read_directly_from_the_event_when_present():
    """A commit event that RECORDS the gate numbers (``gate_delta``/``gate_stderr``/
    ``gate_n``/``gate_k_se``/``gate_threshold``/``gate_resolvable_effect_size``) is
    preferred over parsing them back out of the prose ``reason``; a prose-only event
    (every deterministic loop) still takes the regex path unchanged."""
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = [
        {"t": 1.0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
        {"t": 2.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"t": 3.0, "kind": "baseline", "val": 0.5},
        # No structured fields at all — the fallback path (prose-only, as every existing
        # agent-optimize run writes today) must still populate delta/stderr/n from ``note``.
        {"t": 4.0, "kind": "reject", "candidate": "cand_prose", "val": 0.53,
         "note": "Δ̄=+0.0300 <= 1.0·SE=0.0500 (SE=0.0500, n=8)"},
        # Structured fields present — must win over the (deliberately contradictory) prose.
        {"t": 5.0, "kind": "reject", "candidate": "cand_struct", "val": 0.55,
         "note": "Δ̄=+0.0300 <= 1.0·SE=0.0500 (SE=0.0500, n=8)",
         "gate_delta": 0.099, "gate_stderr": 0.011, "gate_n": 40, "gate_k_se": 1.0,
         "gate_threshold": 0.011, "gate_resolvable_effect_size": 0.022},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps({"val": {"reward": 0.5}}), encoding="utf-8")
    reduced = dashboard.reduce_run(rd)
    gd = {d["candidate"]: d for d in reduced["summary"]["gate_decisions"]}

    prose = gd["cand_prose"]
    assert prose["delta"] == 0.03 and prose["stderr"] == 0.05 and prose["n"] == 8
    assert prose["resolvable_effect_size"] is None  # not in the prose, no fallback pattern

    struct = gd["cand_struct"]
    assert struct["delta"] == 0.099 and struct["stderr"] == 0.011 and struct["n"] == 40
    assert struct["k_se"] == 1.0 and struct["threshold"] == 0.011
    assert struct["resolvable_effect_size"] == 0.022


def test_controls_are_read_generically_and_absent_by_default():
    """Null-control replicates surface as their own summary list, detected by EITHER the
    documented ``ctl_null`` tag-prefix convention or a generic ``role``/``is_control``
    marker.

    The prefix half is not optional: nothing in round.py/commit.py sets ``role`` or
    ``is_control``, so keying on the marker alone produced an empty list and a silently
    dropped noise-floor section on every real run that measured one — while four real
    control evaluations with real rewards sat in the same event log. The marker half stays
    for forward-compatibility with an algorithm that names its controls differently.
    """
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = [
        {"t": 1.0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
        {"t": 2.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"t": 3.0, "kind": "baseline", "val": 0.5},
        # The ``ctl_null`` prefix IS the signal agent-optimize actually emits.
        {"t": 4.0, "kind": "evaluate", "split": "val", "tag": "ctl_null_i0", "reward": 0.52},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps({"val": {"reward": 0.5}}), encoding="utf-8")
    reduced = dashboard.reduce_run(rd)
    (by_tag,) = reduced["summary"]["controls"]
    assert by_tag["tag"] == "ctl_null_i0" and by_tag["reward"] == 0.52
    assert reduced["summary"]["capabilities"]["controls"] is True
    # A control is never in NEITHER place: it has no graph node, so it must at least appear
    # in the evaluations table, labelled as a control rather than as an anonymous row.
    assert [e["candidate"] for e in reduced["summary"]["evaluations"]
            if e["kind"] == "control"] == ["ctl_null_i0"]

    # And with the generic marker present — picked up regardless of tag shape.
    events.append({"t": 5.0, "kind": "evaluate", "split": "val", "tag": "anything_at_all",
                   "reward": 0.48, "stderr": 0.02, "n_scored": 4, "role": "control"})
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    reduced2 = dashboard.reduce_run(rd)
    ctl = next(c for c in reduced2["summary"]["controls"] if c["tag"] == "anything_at_all")
    assert ctl["reward"] == 0.48 and ctl["n"] == 4
    assert reduced2["summary"]["capabilities"]["controls"] is True


def test_screened_badge_read_generically_by_candidate_tag():
    """``screened_before_fullval`` is looked up by whatever event carries it, keyed by
    tag — not tied to the ``agent_optimize_compliance`` kind name agent-optimize happens
    to emit it under today."""
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = [
        {"t": 1.0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
        {"t": 2.0, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"t": 3.0, "kind": "baseline", "val": 0.5},
        {"t": 4.0, "kind": "some_future_algorithms_event", "tag": "cand_1",
         "screened_before_fullval": True},
        {"t": 5.0, "kind": "reject", "candidate": "cand_1", "val": 0.5, "note": "x"},
        # cand_2 has no compliance signal at all -> stays None, not False.
        {"t": 6.0, "kind": "reject", "candidate": "cand_2", "val": 0.51, "note": "y"},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(json.dumps({"val": {"reward": 0.5}}), encoding="utf-8")
    reduced = dashboard.reduce_run(rd)
    nodes = {n["id"]: n for n in reduced["graph"]["nodes"]}
    assert nodes["cand_1"]["screened"] is True
    assert nodes["cand_2"]["screened"] is None
    assert reduced["summary"]["capabilities"]["screened"] is True
