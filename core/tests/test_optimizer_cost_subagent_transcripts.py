"""Smoke-run B3: a SUBAGENT optimizer is metered from its own transcript, found under the LAUNCH
cwd's project dir, never billing sibling agents; a missing transcript warns instead of silent $0."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

from cap_evolve import Budget, RunDir, optimizer_cost  # noqa: E402

SID = "4e54482c-0000-0000-0000-000000000000"


def _line(mid, out):
    return json.dumps({"type": "assistant", "timestamp": "2030-01-01T00:00:00Z", "message": {
        "id": mid, "model": "claude-opus-4-8", "usage": {"output_tokens": out}}}) + "\n"


def _setup(tmp_path, monkeypatch):
    launch = tmp_path / "launch"                       # where Claude Code was started
    rd = RunDir.create(launch / "repo" / ".capevolve", ts="s", budget=Budget(max_iterations=5))
    cfg = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("CAPEVOLVE_OPTIMIZER_TRANSCRIPTS", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    sub = cfg / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(launch)) / SID / "subagents"
    sub.mkdir(parents=True)
    return rd, launch, sub


def test_registered_subagent_transcript_is_billed_alone(tmp_path, monkeypatch):
    rd, launch, sub = _setup(tmp_path, monkeypatch)
    mine, sibling = sub / "agent-mine.jsonl", sub / "agent-sibling.jsonl"
    mine.write_text(_line("a", 1000))
    sibling.write_text(_line("b", 10**6))
    (sub.parent.parent / f"{SID}.jsonl").write_text(_line("lead", 10**6))
    r = subprocess.run([sys.executable, "-m", "cap_evolve.optimizer_cost", "register", "--run-dir",
                        str(rd.root), "--transcript", str(mine)], capture_output=True, text=True,
                       env={"PYTHONPATH": str(REPO / "core"), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)   # the lead's id must NOT widen the scope
    h = optimizer_cost.harvest(rd, [rd.root.parent.parent], since=0)
    assert h["tokens"] == 1000 and h["transcripts"] == 1 and h["scoped"]
    assert optimizer_cost.harvest(rd, [rd.root.parent.parent], since=0)["tokens"] == 0  # idempotent


def test_env_var_accepts_globs_and_lists(tmp_path, monkeypatch):
    rd, launch, sub = _setup(tmp_path, monkeypatch)
    (sub / "agent-a1.jsonl").write_text(_line("a", 10))
    (sub / "agent-a2.jsonl").write_text(_line("b", 20))
    (sub / "agent-zz.jsonl").write_text(_line("c", 10**6))
    monkeypatch.setenv("CAPEVOLVE_OPTIMIZER_TRANSCRIPTS", f"{sub}/agent-a*.jsonl, /nonexistent.jsonl")
    assert optimizer_cost.harvest(rd, [launch], since=0)["tokens"] == 30


def test_session_id_finds_log_under_launch_dir_above_the_run_dir(tmp_path, monkeypatch):
    rd, launch, sub = _setup(tmp_path, monkeypatch)
    (sub.parent.parent / f"{SID}.jsonl").write_text(_line("lead", 500))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    # dirs deliberately omit the launch dir: it is an ancestor of the run dir's parent chain
    h = optimizer_cost.harvest(rd, [rd.root.parent.parent], since=0)
    assert h is not None and h["tokens"] == 500


def test_unrelated_sessions_are_never_billed_and_missing_log_is_none(tmp_path, monkeypatch):
    rd, launch, sub = _setup(tmp_path, monkeypatch)
    (sub.parent.parent / "other-session.jsonl").write_text(_line("x", 10**6))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    assert optimizer_cost.harvest(rd, [rd.root.parent.parent], since=0) is None


def test_digest_meter_warns_loudly_when_no_transcript(tmp_path, monkeypatch, capsys):
    import digest
    rd, _, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "no-such-session")
    assert digest.meter(rd) is None
    assert "no optimizer transcript found" in capsys.readouterr().err
    assert any("no optimizer transcript" in m for m in digest.recent_infra(rd))
    assert "INFRA" in digest.render({**_stub(rd), "infra_warnings": digest.recent_infra(rd)})


def _stub(rd):
    b = {"remaining_usd": None, "eval_usd": 0, "opt_usd": 0, "usersim_usd": 0, "rollouts": 0, "wall_min": 0}
    return {"budget": b, "context_digest": False, "best_id": "seed", "note": "n"}


def test_act_jload_tolerates_stray_log_lines():
    import act
    assert act.jload('WARNING: noise\n{"a": 1}\n') == {"a": 1}
    assert act.jload('{"a": 2}') == {"a": 2}
    assert act.jload("garbage") is None


def test_digest_labels_posterior_mean():
    import digest
    d = {**_stub(None), "context_digest": True, "noise": {"sd_est": None, "why": "x"},
         "champion": {"id": "seed", "mean": 0.7222, "raw": 0.8333, "cov": 6, "T": 6},
         "clusters": [], "tips": [], "merge_opps": [], "pregate": [], "suggested": []}
    assert "posterior mean 0.7222 (raw 0.8333)" in digest.render(d)


def test_stale_noise_does_not_trigger_finalize():
    import digest
    d = {"tips": [], "merge_opps": [], "budget": {}, "champion": {"id": "seed"},
         "noise": {"min_detectable": 0.5, "stale": True, "why": "few repeats"},
         "clusters": [{"id": "C1", "status": "open", "headroom": 0.03, "tasks": ["1"], "attempts": 0}]}
    verbs = [s["verb"] for s in digest.suggest(d, [], {})]
    assert "finalize" not in verbs and "propose" in verbs
