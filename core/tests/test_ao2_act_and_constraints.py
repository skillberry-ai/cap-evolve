"""AO-2 supporting changes (#811): duplicate refusal in `act propose`, finalize that completes from
existing test rollouts and is idempotent, and prose stop_conditions that never become caps."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_digest_and_act_verbs import Sh, _act, _args, _run  # noqa: E402

from cap_evolve import RunDir, graph  # noqa: E402
from cap_evolve.constraints import check_constraints, parse_constraints  # noqa: E402


# 10 (real propose verb) -------------------------------------------------------------------------
def test_act_propose_refuses_byte_identical_candidates(tmp_path, capsys, monkeypatch):
    import shutil
    rd, _, work, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    sh = Sh(**{"pregate.py": (0, json.dumps({"ok": True}), "")})
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd)], sh)
    assert rc == 0, out
    shutil.copytree(work / "cand_1", work / "cand_2")                    # byte-identical to cand_1
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_2", "--parent", "cur", *_args(rd)], sh)
    assert rc == 2 and "duplicate candidate" in out["error"] and out["duplicate_of"] == "cand_1"
    assert (graph.latest_node(rd, "cand_2") or {}).get("stage") != "checked"
    (work / "cand_2" / "edit.txt").write_text("a real change")
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_2", "--parent", "cur", *_args(rd)], sh)
    assert rc == 0, out


# 8 ----------------------------------------------------------------------------------------------
def _test_rollout(rd, task, tag, reward):
    d = rd.rollouts / "test"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{task}__{tag}__t0.json").write_text(json.dumps({
        "input": None, "rollout": {"task_id": task, "output": "", "error": None},
        "score": {"task_id": task, "reward": reward, "feedback": "", "n": 1, "stderr": 0.0,
                  "trial_rewards": [reward], "raw": {}}}))


def test_finalize_completes_from_existing_test_rollouts_without_a_second_look(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TEST_RESCORE", raising=False)
    rd, project, _, _ = _run(tmp_path)
    for i, t in enumerate(rd.read_splits().ids("test")):
        _test_rollout(rd, t, "FINAL", float(i % 2))
        _test_rollout(rd, t, "FINAL_seed", 0.0)
    (rd.root / "finalize.intent").write_text(json.dumps({"champion": "cur", "n_trials": 1}))
    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], sh)
    assert rc == 0, out
    assert not sh.calls, "no evaluation of any split: nothing is scored again"
    assert out["result"]["completed_from_existing"] is True
    fin = json.loads((rd.root / "final.json").read_text())
    assert fin["final"]["completed_from_existing_rollouts"] is True and fin["final"]["test_delta"] > 0
    assert RunDir.open(rd.root).read_splits().test_used, "the seal is burned exactly once, by the completion"
    # and a relaunch after DONE is a no-op that reports the sealed result
    rc, out = _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], sh)
    assert rc == 0 and out["result"]["already_finalized"] is True and not sh.calls


def test_finalize_with_missing_seed_test_rollouts_refuses_rather_than_rescoring(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_ALLOW_TEST_RESCORE", raising=False)
    rd, project, _, _ = _run(tmp_path)
    for t in rd.read_splits().ids("test"):
        _test_rollout(rd, t, "FINAL", 1.0)
    (rd.root / "finalize.intent").write_text(json.dumps({"champion": "cur"}))
    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], sh)
    assert rc == 2 and "FINAL_seed" in out["error"] and not sh.calls
    assert not RunDir.open(rd.root).read_splits().test_used


def test_finalize_writes_the_intent_before_the_test_attempt(tmp_path, capsys, monkeypatch):
    rd, project, _, _ = _run(tmp_path)
    seen = {}

    def phase(cmd):
        seen["intent"] = (rd.root / "finalize.intent").exists()
        return 0, json.dumps({"test_reward": 0.5}), ""
    rc, out = _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], Sh(**{"run.py": phase}))
    assert rc == 0 and seen["intent"] is True


# 11 ---------------------------------------------------------------------------------------------
SUITE_A = "stop when the rollout budget (max_metric_calls) is exhausted or after 10 candidates"
SUITE_B = ("Total budget: 600 target rollouts (max_metric_calls=600), ALL evaluations included; one full-val "
           "evaluation is 40 rollouts. Promotion goes through rule P (screen, then fresh-trial confirmation of "
           "candidate and parent; a confirmation costs about 240 rollouts), so keep that in mind. Stop proposing "
           "when spend.py's recommendation is 'stop' or the remaining rollouts would not cover another gate.")
SUITE_C = ("Total budget: 600 target rollouts (max_metric_calls=600); one full-val evaluation is 40 rollouts. "
           "Reserve 120 rollouts for the champion confirmation that act.py finalize runs (n_confirm=3 fresh "
           "trials per val task). Stop proposing when the remaining rollouts would not cover another gate plus the reserve.")


@pytest.mark.parametrize("text", [SUITE_A, SUITE_B, SUITE_C])
def test_constraints_definitional_sentence(text):
    p = parse_constraints(text)
    assert not [x for x in p["predicates"] if x["kind"] in ("max_metric_calls", "max_iterations")], p["predicates"]
    c = check_constraints(p, best_val=0.5, usd=0, wallclock_seconds=0, iterations=4, stall=0, metric_calls=300,
                          regressed_tasks=[], warn_frac=0.8, per_task_ceiling=None)
    assert c["recommendation"] != "stop"


def test_a_real_ceiling_is_still_parsed():
    assert {x["kind"]: x["target"] for x in parse_constraints("stop after 200 rollouts")["predicates"]} == {"max_metric_calls": 200.0}
    assert parse_constraints("one evaluation is 40 rollouts, stop after 300 rollouts")["predicates"][0]["target"] == 300.0


def test_spend_for_the_conductor_engine_never_reads_the_prose(tmp_path, capsys, monkeypatch):
    import spend
    rd, project, _, _ = _run(tmp_path, extra="ao_engine: conductor\nstop_condition: \"stop after 3 rollouts and $0.01\"\n")
    rc = spend.main(["--run-dir", str(rd.root), "--project", str(project)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["constraints"]["predicates"] == [] and out["recommendation"] != "stop"


# ---- the helper gate (cap_evolve.helper_gate), shared with the pregate --------------------------

_ON = {"helpers": {"enabled": True, "task_ids": ["105-24"], "smoke_timeout": 30}}


def _helper_tree(root, script):
    d = root / "skills" / "s" / "scripts"
    d.mkdir(parents=True)
    (root / "skills" / "s" / "SKILL.md").write_text("s\n")
    (d / "h.py").write_text(script)
    return root


def test_helper_checks_are_a_noop_when_the_helper_modules_are_absent(monkeypatch, tmp_path):
    import conductor_backend as cb
    monkeypatch.setitem(sys.modules, "cap_evolve.helpers", None)       # ImportError on import
    assert cb.helper_refusal({}, tmp_path, None) is None


def test_the_conductor_refuses_a_cheating_or_broken_helper_before_any_rollout(monkeypatch, tmp_path):
    import conductor_backend as cb
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    monkeypatch.delenv("CAPEVOLVE_HELPER_GATE", raising=False)
    leaky = _helper_tree(tmp_path / "leaky", 'ID = "105-24"\n')
    assert cb.helper_refusal(_ON, leaky, None)[0] == "helper_lint"
    broken = _helper_tree(tmp_path / "broken", "import nonexistent_module_xyz\n")
    assert cb.helper_refusal(_ON, broken, None)[0] == "helper_smoke"
    clean = _helper_tree(tmp_path / "clean", "def f(x):\n    return x\n")
    assert cb.helper_refusal(_ON, clean, None) is None
    assert cb.helper_refusal({}, leaky, None) is None                                  # helpers off
    assert cb.helper_refusal({"helpers": {**_ON["helpers"], "gate": False}}, leaky, None) is None   # gate off
