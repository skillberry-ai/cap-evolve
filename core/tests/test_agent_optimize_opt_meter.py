"""#610: a hosted agent-optimize decision carries the optimizer spend since the PREVIOUS
decision — metered from claude-code's own session log — not null, and not the whole-run total.

The fixture mirrors the real shapes: the host transcript's stream-json lines name the
session_id (their own ``usage`` is a useless message-start snapshot and is ignored), and the
session log logs each message once per content block with its full usage.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(SCRIPTS))

SID = "11111111-2222-3333-4444-555555555555"


def _msg(mid, inp, out, cread, ccreate):
    u = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cread,
         "cache_creation_input_tokens": ccreate}
    line = json.dumps({"type": "assistant", "timestamp": "2026-09-30T00:00:00.000Z",
                       "message": {"id": mid, "usage": u}})
    return line + "\n" + line + "\n"  # logged once per content block


def _setup(tmp_path):
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="m", budget=Budget(max_iterations=10))
    (rd.root / "host").mkdir(exist_ok=True)
    (rd.root / "host" / "transcript.jsonl").write_text(json.dumps(
        {"type": "assistant", "session_id": SID,
         "message": {"id": "m1", "usage": {"input_tokens": 9, "output_tokens": 0}}}) + "\n")
    cfg = tmp_path / "claude"
    log = cfg / "projects" / "-some-cwd" / f"{SID}.jsonl"
    log.parent.mkdir(parents=True)
    (cfg / "projects" / "-some-cwd" / SID / "subagents").mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    (work / "x.md").write_text("x")
    return rd, cfg, log, work


def _commit(rd, cfg, work, cid, decision, extra=()):
    env = dict(os.environ, PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
               CLAUDE_CONFIG_DIR=str(cfg), CAPEVOLVE_HOST_METER="1")
    p = subprocess.run([sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(rd.root),
                        "--candidate-id", cid, "--from-dir", str(work), "--decision", decision,
                        "--missing-handover-justification", "fixture", *extra],
                       capture_output=True, text=True, env=env, cwd=str(SCRIPTS))
    assert p.returncode == 0, p.stdout + p.stderr
    evs = [json.loads(ln) for ln in rd.events_path.read_text().splitlines() if ln.strip()]
    return [e for e in evs if e.get("kind") == decision and e.get("candidate") == cid][-1]


def test_each_decision_carries_only_the_delta_since_the_previous_one(tmp_path, monkeypatch):
    rd, cfg, log, work = _setup(tmp_path)
    log.write_text(_msg("m1", 10, 100, 1000, 200) + _msg("m2", 5, 50, 500, 0))
    acc = _commit(rd, cfg, work, "cand1", "accept", ["--val", "0.5"])
    assert acc["opt_tokens"] == 1310 + 555  # input+output+cache_read+cache_creation
    assert acc["opt_seconds"] and acc["opt_seconds"] > 0

    # More optimizer activity, including a subagent, then the next decision.
    with log.open("a") as f:
        f.write(_msg("m3", 1, 20, 300, 0))
    (log.parent / SID / "subagents" / "agent-a.jsonl").write_text(_msg("s1", 2, 3, 4, 5))
    rej = _commit(rd, cfg, work, "cand2", "reject", ["--reject-basis", "infra"])
    assert rej["opt_tokens"] == 321 + 14, "delta since cand1, not the cumulative total"
    assert rej["opt_meter"]["tokens"] == 1865 + 335

    # Session ends with spend after the last decision; the real total is split, sum-preserving.
    with log.open("a") as f:
        f.write(_msg("m4", 100, 0, 0, 0))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    import meter
    att = meter.attribute_usd(rd.root, 10.0)
    by = att["by_candidate"]
    assert by["cand1"] > by["cand2"] > 0 and att["residual_usd"] > 0
    assert abs(by["cand1"] + by["cand2"] + att["residual_usd"] - 10.0) < 1e-5

    # The dashboard reads the attributed USD per candidate.
    rd.log_event("opt_cost_attribution", **att)
    from cap_evolve.dashboard import reduce_run
    red = reduce_run(rd)
    nodes = {n["id"]: n for n in red["graph"]["nodes"]}
    assert nodes["cand1"]["opt_cost_usd"] == by["cand1"]
    rows = [r for r in red["summary"]["cost_ledger"]["rows"]
            if r["kind"] == "optimizer_call" and r["candidate"] == "cand1"]
    assert [r["usd"] for r in rows if r["usd"] is not None] == [by["cand1"]], rows


def test_unhosted_commit_is_unchanged(tmp_path):
    rd, cfg, log, work = _setup(tmp_path)
    log.write_text(_msg("m1", 10, 100, 1000, 200))
    env = dict(os.environ, PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
               CLAUDE_CONFIG_DIR=str(cfg))
    env.pop("CAPEVOLVE_HOST_METER", None)
    p = subprocess.run([sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(rd.root),
                        "--candidate-id", "c", "--from-dir", str(work), "--decision", "accept",
                        "--missing-handover-justification", "fixture"],
                       capture_output=True, text=True, env=env, cwd=str(SCRIPTS))
    assert p.returncode == 0, p.stdout + p.stderr
    ev = [json.loads(ln) for ln in rd.events_path.read_text().splitlines()
          if '"accept"' in ln][-1]
    assert ev["opt_tokens"] is None and "opt_meter" not in ev
