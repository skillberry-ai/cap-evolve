"""Failure clustering v2 (issue #716): tool-error signatures, kind/headroom, minimum edit size,
pre-write tool fixtures, and the ``failure_clustering`` ablation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills" / "phases" / "diagnose" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

import build_tool_fixtures as btf  # noqa: E402
import cluster as C  # noqa: E402
import plan_round  # noqa: E402

from cap_evolve import hypotheses  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "diagnose_run", REPO / "skills" / "phases" / "diagnose" / "scripts" / "run.py")
diag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diag)


def _tr(*steps):
    """steps: (tool, args, result, is_error) -> tau2-style trace."""
    trace = []
    for i, (name, args, result, err) in enumerate(steps):
        trace.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{i}", "name": name, "arguments": args}]})
        trace.append({"role": "tool", "id": f"c{i}", "content": result, "error": err})
    return {"trace": trace, "output": "done"}


PAY_ERR = "Error: Payment amount does not add up, total price is 871, but paid 250"
VAL_ERR = "Error: 1 validation error for Payment\npayment_id\n  Field required"


def _pay_rollout(n=2):
    return _tr(*[("book_reservation", {"n": i}, PAY_ERR, True) for i in range(n)])


def test_error_signature_normalises_both_call_shapes():
    a = C.tool_error_sigs(_pay_rollout(2))
    assert a == {"book_reservation|payment amount does not add up": 2}
    openai = {"trace": [
        {"role": "assistant", "tool_calls": [{"id": "x", "function": {
            "name": "book_reservation", "arguments": "{\"a\": 1}"}}]},
        {"role": "tool", "id": "x", "content": VAL_ERR, "error": True}]}
    assert C.tool_error_sigs(openai) == {"book_reservation|validation Payment": 1}


def test_patterns_detect_loop_transfer_first_and_too_many_errors():
    ro = _tr(*[("transfer_to_human_agents", {}, "ok", False)] * 3)
    ro["metadata"] = {"termination_reason": "TerminationReason.TOO_MANY_ERRORS"}
    assert C.patterns(ro) == ["loop:transfer_to_human_agents", "transfer_first", "too_many_errors"]


def _trial(task, rollout, fb="x"):
    return {"task_id": task, "feedback": fb, "lost": 1.0, "rollout": rollout, "trace_id": f"{task}__t"}


def test_shared_tool_error_signature_merges_tasks_with_unrelated_feedback():
    trials = [_trial("8", _pay_rollout(), "alpha beta gamma"),
              _trial("20", _pay_rollout(3), "delta epsilon zeta"),
              _trial("5", _tr(("get_user", {}, "fine", False)), "omega theta kappa")]
    out = C.cluster_v2(trials, n_tasks=30, totals={"8": 3, "20": 3, "5": 3})
    pay = next(c for c in out if c["tasks"] == ["20", "8"])
    assert pay["kind"] == "CAPABILITY"
    assert pay["tool_error_sig"] == "book_reservation|payment amount does not add up"
    assert pay["trial_count"] == 2 and pay["cluster_id"].startswith("C")
    # headroom = (1/3 + 1/3) / 30 tasks, in reward units
    assert pay["headroom"] == round(2 / 3 / 30, 4)
    assert next(c for c in out if c["tasks"] == ["5"])["kind"] == "KNOWLEDGE"


def test_a_single_incidental_error_does_not_chain_failures():
    one = _tr(("book_reservation", {}, PAY_ERR, True))
    out = C.cluster_v2([_trial("1", one, "aaa bbb ccc"), _trial("2", one, "ddd eee fff")], 30)
    assert len(out) == 2


def test_pooled_trials_use_total_trials_as_denominator():
    t = [_trial("7", _pay_rollout()) for _ in range(3)]
    pooled = C.cluster_v2(t, 10, {"7": 30})[0]
    assert pooled["trial_count"] == 3 and pooled["headroom"] == round(3 / 30 / 10, 4)


def test_v2_is_deterministic():
    trials = [_trial(str(i), _pay_rollout(), f"w{i} common") for i in range(4)]
    assert json.dumps(C.cluster_v2(trials, 4)) == json.dumps(C.cluster_v2(list(trials), 4))


def test_legacy_cluster_output_is_unchanged():
    items = [("1", "wrong refund amount stated", 1.0), ("2", "wrong refund amount stated", 1.0),
             ("3", "never called cancel tool", 0.5)]
    out = C.cluster(items)
    assert [(c["tasks"], c["score_lost"]) for c in out] == [(["1", "2"], 2.0), (["3"], 0.5)]
    assert set(out[0]) == {"signature", "tasks", "score_lost", "tag", "blast_radius"}


# --- hypotheses -------------------------------------------------------------------------

CL = [{"cluster_id": "C1", "tasks": ["24"], "headroom": 0.0333},
      {"cluster_id": "C2", "tasks": ["19", "24", "14", "7"], "headroom": 0.0667}]


def test_single_task_hypothesis_is_rejected_with_reason_and_bundle_passes():
    ok, why = hypotheses.validate({"cluster_ids": ["C1"], "predicted_tasks": ["24"]}, CL)
    assert not ok and "covers 1 task" in why and "0.0333" in why
    assert hypotheses.validate({"cluster_ids": ["C2"], "predicted_tasks": ["19", "24"]}, CL)[0]
    # headroom clause alone (one task, many trials)
    big = [{"cluster_id": "C9", "tasks": ["1"], "headroom": 0.07}]
    assert hypotheses.validate({"cluster_ids": ["C9"], "predicted_tasks": ["1"]}, big)[0]


def test_justification_overrides_size_but_not_membership():
    h = {"cluster_ids": ["C1"], "predicted_tasks": ["24"]}
    ok, why = hypotheses.validate(h, CL, "task 24 is the only blocker")
    assert ok and "justification" in why
    ok, why = hypotheses.validate({"cluster_ids": ["C1"], "predicted_tasks": ["99"]}, CL, "x")
    assert not ok and "not in the targeted clusters" in why


def test_repeat_of_is_set_from_a_pruned_hypothesis_with_same_clusters_and_scope(tmp_path):
    hypotheses.append(tmp_path, {"id": "h1", "cluster_ids": ["C3"], "edit_scope": ["policy"],
                                 "status": "pruned"})
    again = hypotheses.append(tmp_path, {"id": "h2", "cluster_ids": ["C3"], "edit_scope": ["policy"]})
    other = hypotheses.append(tmp_path, {"id": "h3", "cluster_ids": ["C3"], "edit_scope": ["tools"]})
    assert again["repeat_of"] == "h1" and "repeat_of" not in other
    assert [h["id"] for h in hypotheses.load(tmp_path)] == ["h1", "h2", "h3"]


# --- diagnose wiring + ablation ---------------------------------------------------------

def _rec(task, reward, rollout):
    return {"score": {"task_id": task, "reward": reward, "feedback": "f"}, "rollout": rollout,
            "input": {}, "__file": f"/x/{task}__seed__t0.json"}


def test_diagnose_v2_pools_trials_and_per_task_is_the_ablation_off_path():
    recs = [_rec("8", 0.0, _pay_rollout()), _rec("20", 0.0, _pay_rollout()),
            _rec("20", 1.0, {"trace": []}), _rec("1", 1.0, {"trace": []})]
    v2 = diag.diagnose(recs, "v2")["clusters"]
    assert len(v2) == 1 and v2[0]["tasks"] == ["20", "8"] and v2[0]["exemplar_trace_ids"]
    # 20 has 2 trials (1 failed), 8 has 1 -> (1/2 + 1/1) / 3 tasks
    assert v2[0]["headroom"] == round(1.5 / 3, 4)
    off = diag.diagnose(recs, "per-task")["clusters"]
    assert sorted(c["tasks"][0] for c in off) == ["20", "8"]
    assert all("headroom" not in c for c in off)


def test_plan_round_reports_size_check_only_when_rule_is_on():
    cl = [dict(c, signature=f"sig{c['cluster_id']}", score_lost=0.1) for c in CL]
    on = plan_round.plan_round(cl, None, None)
    sizes = {tuple(s["cluster_ids"]): s["size_check"]["ok"] for s in on["slots"]}
    assert sizes[("C1",)] is False and sizes[("C2",)] is True
    off = plan_round.plan_round(cl, None, None, size_rule=False)
    assert all("size_check" not in s for s in off["slots"])
    legacy = plan_round.plan_round([{"signature": "a b", "tasks": ["1"], "score_lost": 0.1}], None, None)
    assert "size_check" not in legacy["slots"][0]


# --- fixtures ---------------------------------------------------------------------------

def test_fixtures_keep_only_calls_before_the_first_successful_write_and_dedupe():
    ro = _tr(("get_user_details", {"u": 1}, "user", False),
             ("book_reservation", {"p": 1}, PAY_ERR, True),       # errored write: state unchanged
             ("book_reservation", {"p": 2}, "booked", False),     # real write: window ends
             ("get_reservation_details", {"r": 1}, "mutated state", False))
    recs = [_rec("23", 0.0, ro), _rec("23", 0.0, ro)]
    rows = btf.fixtures_from(recs)
    assert [(r["tool"], r["args"]) for r in rows] == [
        ("book_reservation", {"p": 1}), ("get_user_details", {"u": 1})]
    assert all(r["pre_write"] and r["task_id"] == "23" for r in rows)
    assert rows == btf.fixtures_from(recs)
