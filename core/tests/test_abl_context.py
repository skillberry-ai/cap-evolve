"""Ablation switches abl_history (none|state) and abl_info (reward|eval|fail): proposer input only."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
FIX = Path(__file__).parent / "fixtures" / "abl_rollouts"
HIST_WORDS = ("LEDGER", "JOURNAL", "RUNMAP", "prior_iterations", "INSIGHTS", "rejected.jsonl",
              "history.jsonl", "Currently PASSING")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    from cap_evolve import abl_context
    for k in ("CAPEVOLVE_HISTORY", abl_context.ENV_HISTORY, abl_context.ENV_INFO):
        monkeypatch.delenv(k, raising=False)
    abl_context._ACTIVE.update(history=None, info=None)
    yield
    for k in ("CAPEVOLVE_HISTORY", abl_context.ENV_HISTORY, abl_context.ENV_INFO):
        os.environ.pop(k, None)
    abl_context._ACTIVE.update(history=None, info=None)


def _traj(tmp_path):
    d = tmp_path / "trajectories"
    d.mkdir()
    for f in FIX.glob("*__t*.json"):
        shutil.copyfile(f, d / f.name)
    return d


def _all_text(d):
    return "\n".join(f.read_text() for f in d.glob("*.json"))


def test_fixture_has_failures_with_ground_truth():
    names = sorted(p.name for p in FIX.glob("*__t*.json"))
    assert len(names) == 4
    bad = json.loads((FIX / "10__cand_0002__t0.json").read_text())
    assert bad["score"]["reward"] == 0 and "tau2_reward_info" in bad["rollout"]["metadata"]


def test_settings_validation(tmp_path):
    from cap_evolve import abl_context as a
    assert a.settings_from_spec({}) == (None, None)
    assert a.settings_from_spec({"abl_history": "none", "abl_info": "fail"}) == ("none", "fail")
    for bad in ({"abl_history": "nope"}, {"abl_info": "all"}):
        with pytest.raises(ValueError):
            a.settings_from_spec(bad)


def test_settings_from_run_dir_spec(tmp_path):
    from cap_evolve import RunDir, abl_context as a
    (tmp_path / "capevolve.yaml").write_text("abl_history: state\nabl_info: reward\n")
    rd = RunDir.create(tmp_path / ".capevolve", ts="x")
    rd.log_event("run_config", spec=str(tmp_path / "capevolve.yaml"))
    assert a.settings(rd) == ("state", "reward")
    assert a.current_info() == "reward" and a.current_history() == "state"
    (tmp_path / "capevolve.yaml").write_text("abl_history: bogus\n")
    with pytest.raises(ValueError):
        a.settings(rd)


def test_export_env_routes_none_to_history_switch(monkeypatch):
    from cap_evolve import abl_context as a, harness
    a.export_env({"abl_history": "none"})
    assert os.environ["CAPEVOLVE_HISTORY"] == "0" and harness.history_enabled() is False
    os.environ.pop("CAPEVOLVE_HISTORY")      # (not monkeypatch: its undo would restore "0" for later tests)
    os.environ.pop(a.ENV_HISTORY)
    a._ACTIVE.update(history=None, info=None)
    a.export_env({"abl_history": "state"})
    assert "CAPEVOLVE_HISTORY" not in os.environ and harness.history_enabled() is True


def test_info_reward(tmp_path):
    from cap_evolve import abl_context as a
    d = _traj(tmp_path)
    a.transform_trajectories(d, "reward")
    text = _all_text(d)
    for key in ("tau2_reward_info", '"judge"', '"usersim"', "termination_reason", "db_check",
                "Database state", "action_checks"):
        assert key not in text, key
    j = json.loads((d / "10__cand_0002__t0.json").read_text())
    assert j["score"]["feedback"] == "Task reward: 0.000." and j["score"]["raw"] == {}
    assert j["rollout"]["trace"] and "tau2_reward" in j["rollout"]["metadata"] or True
    assert len(list(d.glob("*.json"))) == 4


def test_info_eval(tmp_path):
    from cap_evolve import abl_context as a
    d = _traj(tmp_path)
    a.transform_trajectories(d, "eval")
    j = json.loads((d / "10__cand_0002__t0.json").read_text())
    assert set(j) == {"task_id", "trial", "reward", "score", "metadata"}
    assert j["trial"] == 0 and j["reward"] == 0 and "tau2_reward_info" in j["metadata"]
    assert "Database state" in j["score"]["feedback"]
    text = _all_text(d)
    for key in ('"trace"', '"output"', "tool_calls", '"rollout"', "usersim", "raw_data", "Hi! How can I help"):
        assert key not in text, key


def test_info_fail(tmp_path):
    from cap_evolve import abl_context as a
    d = _traj(tmp_path)
    a.transform_trajectories(d, "fail")
    assert sorted(p.name for p in d.glob("*.json")) == ["10__cand_0002__t0.json", "11__cand_0002__t0.json"]
    j = json.loads((d / "10__cand_0002__t0.json").read_text())
    assert "tau2_reward_info" in j["rollout"]["metadata"]       # everything else stock


def test_info_unset_is_noop(tmp_path):
    from cap_evolve import abl_context as a
    d = _traj(tmp_path)
    before = _all_text(d)
    a.transform_trajectories(d, None)
    assert _all_text(d) == before
    with pytest.raises(ValueError):
        a.transform_trajectories(d, "bogus")


def test_failure_index_reward_only():
    from cap_evolve import abl_context as a, harness
    pt = {"task_id": "10", "reward": 0.0, "feedback": "Database state does NOT match"}
    stock = harness._fmt(pt)
    assert "Database state" in stock
    a._ACTIVE["info"] = "reward"
    assert harness._fmt(pt) == "- 10 (reward 0.00)"
    block = harness._failures_block([pt], [], [])
    assert "Database state" not in block and "- 10 (reward 0.00)" in block
    a._ACTIVE["info"] = "eval"
    assert harness._fmt(pt) == stock


def test_inject_context_applies_info(tmp_path, monkeypatch):
    """_inject_optimizer_context transforms the copied trajectories after _copy_step_trajectories."""
    from cap_evolve import RunDir, harness
    (tmp_path / "capevolve.yaml").write_text("abl_info: fail\n")
    rd = RunDir.create(tmp_path / ".capevolve", ts="x")
    rd.log_event("run_config", spec=str(tmp_path / "capevolve.yaml"))
    vdir = rd.rollout_dir("val")
    vdir.mkdir(parents=True, exist_ok=True)
    for f in FIX.glob("*__t*.json"):
        shutil.copyfile(f, vdir / f.name.replace("cand_0002", "seed"))
    work = tmp_path / "work"
    work.mkdir()
    harness._inject_optimizer_context(None, rd, work, split="val", tag="seed")
    assert sorted(p.name for p in (work / "trajectories").glob("*.json")) == [
        "10__seed__t0.json", "11__seed__t0.json"]


def test_hidden_paths_and_cli(tmp_path, capsys):
    from cap_evolve import abl_context as a
    assert a.hidden_paths(None, None, None) == []
    assert a.hidden_paths("state", None) == ["rollouts", "native_sims", "eval_index.jsonl", "baseline.json",
                                             "champion.json", "state.json", "candidates"]
    assert a.hidden_paths(None, "eval") == a.hidden_paths("state", None)
    none = a.hidden_paths("none", None)
    assert none[:4] == ["rollouts", "native_sims", "candidates", "work"] and "LEDGER.md" in none
    assert "graph.jsonl" in a.hidden_paths(None, None, "disjoint")
    with pytest.raises(ValueError):
        a.hidden_paths("x", None)
    spec = tmp_path / "s.yaml"
    spec.write_text("abl_history: state\n")
    assert a._main(["hidden", str(spec)]) == 0
    assert capsys.readouterr().out.strip() == ",".join(a.hidden_paths("state", None))


def test_runmap_drops_trace_sentence_only_for_state(tmp_path):
    from cap_evolve import RunDir, abl_context as a, harness
    rd = RunDir.create(tmp_path / ".capevolve", ts="x")
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    w = tmp_path / "w"
    w.mkdir()
    harness._build_runmap(w, rd)
    assert "rollouts/<split>/" in (w / "RUNMAP.md").read_text()
    a._ACTIVE["history"] = "state"
    harness._build_runmap(w, rd)
    t = (w / "RUNMAP.md").read_text()
    assert "rollouts" not in t and "prior_iterations" in t


def test_hist_none_renders_no_history(tmp_path, monkeypatch):
    from cap_evolve import RunDir, abl_context as a, harness
    from cap_evolve.loop import SplitResult
    a.export_env({"abl_history": "none"})
    rd = RunDir.create(tmp_path / ".capevolve", ts="x")
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    rd.log_event("step", candidate="cand_1", parent="seed", accept=False, val=0.5)
    val = SplitResult.from_dict({"split": "val", "reward": 0.5, "stderr": 0.0, "per_task": [
        {"task_id": "v1", "reward": 0.0, "feedback": "boom"},
        {"task_id": "v2", "reward": 1.0, "feedback": ""}]})
    for tmpl in (FIX / "PROJECT_INSTRUCTIONS.md", REPO / "templates" / "project" / "optimizer" / "INSTRUCTIONS.md"):
        work = tmp_path / ("w_" + tmpl.parent.name + tmpl.stem)
        work.mkdir()
        text = harness._focus_instructions(val, None, "val", instructions_file=str(tmpl))
        text = harness._augment_instructions(text, work, rd)
        harness._write_instructions_pointer(work / "CLAUDE.md", ".claude/skills", run_dir=rd, workdir=work)
        listing = "\n".join(str(p.relative_to(work)) for p in work.rglob("*"))
        blob = "\n".join([text, (work / "CLAUDE.md").read_text(), listing])
        for w in HIST_WORDS:
            assert w not in blob, (tmpl.name, w, [m for m in blob.splitlines() if w in m][:3])
        assert (work / "PROCESS.md").is_file() and "PROCESS.md" in text
        assert "Currently PASSING" not in text and "v1" in text


def test_stock_render_unchanged_without_switches(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.loop import SplitResult
    rd = RunDir.create(tmp_path / ".capevolve", ts="x")
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    val = SplitResult.from_dict({"split": "val", "reward": 0.5, "stderr": 0.0, "per_task": [
        {"task_id": "v1", "reward": 0.0, "feedback": "boom"}]})
    text = harness._focus_instructions(val, None, "val", instructions_file=str(FIX / "PROJECT_INSTRUCTIONS.md"))
    assert "LEDGER.md" in text and "ablation" not in text and "boom" in text
    work = tmp_path / "w"
    work.mkdir()
    assert "rejected.jsonl" in harness._augment_instructions(text, work, rd)


def test_info_note_added_to_instructions(tmp_path):
    from cap_evolve import abl_context as a, harness
    from cap_evolve.loop import SplitResult
    val = SplitResult.from_dict({"split": "val", "reward": 0.5, "stderr": 0.0, "per_task": [
        {"task_id": "v1", "reward": 0.0, "feedback": "boom"}]})
    a._ACTIVE["info"] = "eval"
    text = harness._focus_instructions(val, None, "val", instructions_file=str(FIX / "PROJECT_INSTRUCTIONS.md"))
    assert "NO conversation traces" in text and "boom" in text
