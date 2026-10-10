"""#715: conversational runs meter the optimizer from Claude Code's session log (idempotently),
and the user simulator's tokens are priced instead of reading as $0."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(CORE))

from cap_evolve import Budget, RunDir, optimizer_cost  # noqa: E402
from cap_evolve.pricing import token_cost  # noqa: E402
from cap_evolve.harness import _usersim_unpriced, _usersim_usd  # noqa: E402


def _line(mid, model, ts, inp=0, out=0, cr=0, cw=0):
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {
        "id": mid, "model": model,
        "usage": {"input_tokens": inp, "output_tokens": out,
                  "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}}}) + "\n"


def _setup(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    rd = RunDir.create(proj / ".capevolve", ts="m", budget=Budget(max_iterations=10))
    cfg = tmp_path / "claude"
    import re
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(proj.resolve()))
    log = cfg / "projects" / slug / "sess.jsonl"
    log.parent.mkdir(parents=True)
    return proj, rd, cfg, log


def test_token_cost_prices_cache_tiers_and_refuses_unknown_models():
    # sonnet $3/$15: 1M in + 1M out + 1M cache-read (0.1x) + 1M cache-write (1.25x)
    assert abs(token_cost("claude-sonnet-5", 10**6, 10**6, 10**6, 10**6) - (3 + 15 + .3 + 3.75)) < 1e-9
    assert token_cost("mystery-model", 10**6) is None


def test_harvest_is_idempotent_windowed_and_flags_unpriced(tmp_path, monkeypatch):
    proj, rd, cfg, log = _setup(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess")
    log.write_text(
        _line("old", "claude-opus-4-8", "2020-01-01T00:00:00Z", out=10**6)      # before window
        + _line("a", "claude-opus-4-8", "2030-01-01T00:00:00Z", out=1000, cr=10**6)
        + _line("a", "claude-opus-4-8", "2030-01-01T00:00:00Z", out=1000, cr=10**6)  # per block dup
        + _line("b", "weird-model", "2030-01-01T00:00:01Z", inp=500))
    r = optimizer_cost.harvest(rd, [proj], since=time.time())
    assert r["tokens"] == 1000 + 10**6 + 500 and r["unpriced_tokens"] == 500
    assert abs(r["usd"] - token_cost("claude-opus-4-8", 0, 1000, 10**6)) < 1e-6
    again = optimizer_cost.harvest(rd, [proj], since=time.time())
    assert again["tokens"] == 0 and again["usd"] == 0, "same messages are never charged twice"
    assert optimizer_cost.harvest(rd, [tmp_path / "elsewhere"], since=0) is None


def test_only_this_runs_session_is_billed_when_two_sessions_share_a_dir(tmp_path, monkeypatch):
    proj, rd, cfg, log = _setup(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess")
    log.write_text(_line("mine", "claude-opus-4-8", "2030-01-01T00:00:00Z", out=1000))
    (log.parent / "other.jsonl").write_text(
        _line("theirs", "claude-opus-4-8", "2030-01-01T00:00:00Z", out=10**6))
    r = optimizer_cost.harvest(rd, [proj], since=0)
    assert r["tokens"] == 1000 and r["scoped"], "another session in the same cwd is not billed"
    # without a session id the heuristic reads everything and says so
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    rd2 = RunDir.create(proj / ".capevolve2", ts="n", budget=Budget(max_iterations=10))
    r2 = optimizer_cost.harvest(rd2, [proj], since=0)
    assert r2["tokens"] == 1000 + 10**6 and not r2["scoped"]


def test_commit_charges_optimizer_once_and_off_is_legacy(tmp_path):
    proj, rd, cfg, log = _setup(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "x.md").write_text("x")
    log.write_text(_line("a", "claude-opus-4-8", "2030-01-01T00:00:00Z", out=1_000_000))

    def commit(cid, mode):
        env = dict(os.environ, PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
                   CLAUDE_CONFIG_DIR=str(cfg), CAPEVOLVE_OPTIMIZER_COST=mode,
                   CLAUDE_CODE_SESSION_ID="sess")
        env.pop("CAPEVOLVE_HOST_METER", None)
        p = subprocess.run([sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(rd.root),
                            "--candidate-id", cid, "--from-dir", str(work), "--decision", "reject",
                            "--reject-basis", "infra", "--missing-handover-justification", "f",
                            "--missing-ranked-issues-justification", "f",
                            "--missing-diagnosis-justification", "f"],
                           capture_output=True, text=True, env=env, cwd=str(proj))
        assert p.returncode == 0, p.stdout + p.stderr
        return RunDir.open(rd.root).spent

    assert commit("c0", "off").optimizer_usd == 0, "off = legacy, nothing metered"
    sp = commit("c1", "session")
    assert abs(sp.optimizer_usd - 25.0) < 1e-6 and sp.optimizer_tokens == 1_000_000
    assert commit("c2", "session").optimizer_usd == sp.optimizer_usd, "re-commit is idempotent"


def test_usersim_tokens_are_priced_only_when_the_provider_reported_zero():
    ro = lambda **u: SimpleNamespace(metadata={"usersim": u})  # noqa: E731
    z = ro(model="claude-sonnet-5", prompt_tokens=10**6, completion_tokens=10**6, cost_usd=0.0)
    assert abs(_usersim_usd(z) - 18.0) < 1e-9
    unk = ro(model="mystery", prompt_tokens=5, completion_tokens=1, cost_usd=0.0)
    assert _usersim_usd(unk) is None and _usersim_unpriced(unk)
    assert _usersim_usd(SimpleNamespace(metadata={})) is None


def test_adapters_report_user_model_and_only_unpriced_user_tokens(monkeypatch):
    """The user sim is priced at TAU2_USER_MODEL (not the agent's), and a user message the
    provider already costed is not re-priced (no double count)."""
    sys.path.insert(0, str(CORE / "tests"))
    import test_tau2_eval_cost as t  # reuses the template-adapter loader and fakes
    mod = t._load_adapter_module()
    monkeypatch.setenv("TAU2_USER_MODEL", "aws/claude-sonnet-5")
    u = {"prompt_tokens": 100, "completion_tokens": 10}
    msgs = [SimpleNamespace(role="user", cost=0.0, usage=u),
            SimpleNamespace(role="user", cost=0.5, usage=u),
            SimpleNamespace(role="assistant", cost=None, usage=u)]
    m = mod._usersim_meta(msgs, mod._user_model())
    assert m == {"model": "aws/claude-sonnet-5", "prompt_tokens": 100, "completion_tokens": 10}
