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


def test_commit_charges_optimizer_once_and_off_is_legacy(tmp_path):
    proj, rd, cfg, log = _setup(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "x.md").write_text("x")
    log.write_text(_line("a", "claude-opus-4-8", "2030-01-01T00:00:00Z", out=1_000_000))

    def commit(cid, mode):
        env = dict(os.environ, PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
                   CLAUDE_CONFIG_DIR=str(cfg), CAPEVOLVE_OPTIMIZER_COST=mode)
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
    assert _usersim_usd(ro(model="claude-sonnet-5", prompt_tokens=5, cost_usd=0.4)) is None
    unk = ro(model="mystery", prompt_tokens=5, completion_tokens=1, cost_usd=0.0)
    assert _usersim_usd(unk) is None and _usersim_unpriced(unk)
    assert _usersim_usd(SimpleNamespace(metadata={})) is None
