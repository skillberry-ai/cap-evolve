"""Confirmation-without-execution has to be a NAMED cluster, not a lexical accident.

A well-documented LLM-agent failure: the agent proposes a change, the user approves it, and the
agent's final message reports the change as done — while no state-mutating tool call ever appears
in the trace. It treated its own completion signal (the approval) as the action.

A scorer describes that exactly as it describes a *wrong* write, so the feedback-based cluster key
cannot separate the two: the round then ships an argument fix for a call that never happened. It is
detectable mechanically from the rollout, which is what these tests pin — and pin conservatively,
because the same detector must stay silent when the rollout carries no tool-call record at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "phases" / "diagnose" / "scripts"


def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"_diag_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def _rec(rollout, feedback="the required change was not applied", reward=0.0, task="t1"):
    return {"input": "…", "rollout": rollout,
            "score": {"task_id": task, "reward": reward, "feedback": feedback}}


def test_a_read_only_trace_that_claims_success_is_flagged():
    cl = _load("cluster")
    assert cl.narrated_without_action({
        "tool_calls": [{"name": "get_record"}, {"name": "list_options"}],
        "output": "All set — your record has been successfully updated to the new plan.",
    })


def test_a_trace_that_actually_wrote_is_not_flagged():
    cl = _load("cluster")
    assert not cl.narrated_without_action({
        "tool_calls": [{"name": "get_record"}, {"name": "update_record"}],
        "output": "Your record has been updated.",
    })


def test_an_adapter_may_declare_a_call_mutating_and_win_over_the_name_heuristic():
    cl = _load("cluster")
    assert not cl.narrated_without_action({
        # A read-sounding name that the adapter says mutates: trust the adapter.
        "tool_calls": [{"name": "check_out", "mutates": True}],
        "output": "It has been processed.",
    })


def test_calls_carried_in_the_trace_count_too():
    """A runner that keeps an OpenAI-style message list in Rollout.trace instead of filling
    Rollout.tool_calls must not read as "no tools were called"."""
    cl = _load("cluster")
    roll = {"trace": [{"role": "assistant",
                       "tool_calls": [{"function": {"name": "modify_booking"}}]},
                      {"role": "assistant", "content": "Done — it has been changed."}]}
    assert not cl.narrated_without_action(roll)
    roll["trace"][0]["tool_calls"] = [{"function": {"name": "search_bookings"}}]
    assert cl.narrated_without_action(roll)


def test_no_tool_call_record_at_all_is_never_flagged():
    """With an empty record there is no way to tell "the agent called nothing" from "this adapter
    does not report calls" — guessing would flag every failure on such an adapter."""
    cl = _load("cluster")
    assert not cl.narrated_without_action({"output": "Your booking has been cancelled."})
    assert not cl.narrated_without_action({})


def test_a_read_only_trace_without_a_completion_claim_is_not_flagged():
    cl = _load("cluster")
    assert not cl.narrated_without_action({
        "tool_calls": [{"name": "get_record"}],
        "output": "I could not find a way to do that; please contact support.",
    })


def test_diagnose_surfaces_it_as_its_own_named_cluster():
    run = _load("run")
    cl = _load("cluster")
    # Two failures with the SAME feedback wording: one narrated, one a genuine bad write. A
    # lexical key puts them in one cluster; the mechanical check must not.
    fb = "the expected change was not applied to the record"
    out = run.diagnose([
        _rec({"tool_calls": [{"name": "get_record"}],
              "output": "Your record has been successfully updated."}, fb, task="t1"),
        _rec({"tool_calls": [{"name": "update_record"}],
              "output": "I updated it."}, fb, task="t2"),
    ])
    sigs = {c["signature"]: c for c in out["clusters"]}
    assert cl.NARRATED_WITHOUT_ACTION in sigs, (
        f"the narrated failure was folded into a lexical cluster: {list(sigs)}")
    assert sigs[cl.NARRATED_WITHOUT_ACTION]["tasks"] == ["t1"]
    assert "t2" not in sigs[cl.NARRATED_WITHOUT_ACTION]["tasks"]
    flags = {e["task_id"]: e[cl.NARRATED_WITHOUT_ACTION] for e in out["reflective_dataset"]}
    assert flags == {"t1": True, "t2": False}


def test_the_cluster_says_the_fix_is_structural_not_a_prose_reminder():
    """A prose "always call the tool" edit has been tried on this class and rejected, so the
    cluster the optimizer reads must not leave that as the obvious move."""
    run = _load("run")
    cl = _load("cluster")
    out = run.diagnose([_rec({"tool_calls": [{"name": "get_x"}],
                             "output": "It has been cancelled."})])
    c = next(c for c in out["clusters"] if c["signature"] == cl.NARRATED_WITHOUT_ACTION)
    assert "reading" in c and "detector" in c
    assert "prose" in c["reading"].lower()


def test_the_detector_is_deterministic():
    run = _load("run")
    recs = [_rec({"tool_calls": [{"name": "get_x"}], "output": "It has been updated."}, task="t1"),
            _rec({"tool_calls": [{"name": "set_x"}], "output": "nope"}, task="t2")]
    assert run.diagnose(recs) == run.diagnose(recs)
