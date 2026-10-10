"""issue #611: a real from-scratch run committed 0/17 candidates with a DIAGNOSIS.json and
every graph.jsonl node carried empty ``cluster_ids``/``subset``, while the dashboard's
PROCESS.md fallback swallowed its parse failures. commit.py now refuses without a real
diagnosis (same escape-hatch shape as #588's JOURNAL.md precondition), feeds the diagnosis'
clusters/tasks into the graph node, and the dashboard surfaces a missing diagnosis instead
of hiding it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

DIAG = {"candidate": "cand_1", "headline": "fix refund arithmetic",
        "clusters": [{"id": "A", "name": "refund math", "tasks": ["t3", "t1"]},
                     {"id": "B", "name": "untargeted", "tasks": ["t9"]}],
        "edits": [{"id": "E1", "title": "compute refunds", "files": [], "clusters": ["A"]}]}


def _run_dir(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=10, stall=10))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    work = run_dir.root / "work" / "cand_1"
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.candidate_dir("seed"), work)
    return run_dir, work


def _commit(run_dir, work, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", "cand_1", "--from-dir", str(work), "--decision", "reject",
         "--val", "0.4", "--val-unverified", "fixture: val not under test", "--note", "test",
         "--missing-handover-justification", "fixture: journal handover not under test",
         "--missing-ranked-issues-justification", "fixture: ranked issues not under test",
         *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})


def _nodes(run_dir):
    from cap_evolve import graph
    return graph.read_nodes(run_dir)


def test_refuses_without_diagnosis(tmp_path):
    run_dir, work = _run_dir(tmp_path)
    p = _commit(run_dir, work)
    assert p.returncode == 2, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert "DIAGNOSIS.json" in out["error"] and "--missing-diagnosis-justification" in out["fix"]
    assert _nodes(run_dir) == [], "a refused commit must book nothing"


def test_refuses_an_empty_template(tmp_path):
    run_dir, work = _run_dir(tmp_path)
    (work / "DIAGNOSIS.json").write_text(json.dumps(
        {"candidate": "cand_1", "clusters": [{"id": "A", "tasks": []}], "edits": []}))
    assert _commit(run_dir, work).returncode == 2


def test_real_diagnosis_populates_graph_cluster_ids_and_subset(tmp_path):
    run_dir, work = _run_dir(tmp_path)
    (work / "DIAGNOSIS.json").write_text(json.dumps(DIAG))
    p = _commit(run_dir, work)
    assert p.returncode == 0, p.stdout + p.stderr
    assert json.loads(p.stdout)["diagnosis_recorded"] is True
    (node,) = _nodes(run_dir)
    assert node["cluster_ids"] == ["A"], "only the cluster the edit targets"
    assert node["subset"]["task_ids"] == ["t1", "t3"]
    # ...and the dashboard reads it through to the node.
    from cap_evolve import dashboard
    n = {x["id"]: x for x in dashboard.reduce_run(run_dir)["graph"]["nodes"]}["cand_1"]
    assert n["cluster_ids"] == ["A"] and n["diagnosis"]["headline"] == DIAG["headline"]


def test_override_flag_commits_with_a_warning(tmp_path):
    run_dir, work = _run_dir(tmp_path)
    p = _commit(run_dir, work, "--missing-diagnosis-justification", "infra failure")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["diagnosis_recorded"] is False
    assert any("missing diagnosis" in w and "infra failure" in w for w in out["warnings"])
    (node,) = _nodes(run_dir)
    assert node["cluster_ids"] == []


def test_dashboard_surfaces_a_diagnosis_parse_failure(tmp_path, monkeypatch):
    from cap_evolve import dashboard, harness

    run_dir, work = _run_dir(tmp_path)
    assert _commit(run_dir, work, "--missing-diagnosis-justification", "x").returncode == 0
    cand = run_dir.candidate_dir("cand_1")
    (cand / "DIAGNOSIS.json").unlink(missing_ok=True)

    def _warned(reduced):
        n = {x["id"]: x for x in reduced["graph"]["nodes"]}["cand_1"]
        ds = [d for d in reduced["summary"]["diagnoses"]
              if d["kind"] == "diagnosis_parse_warning" and d["candidate"] == "cand_1"]
        assert n["diagnosis"]["warnings"] and ds, "a missing diagnosis was silently hidden"
        return ds[0]["text"]

    # 1. PROCESS.md with a header-only "Ranked issue list" (the #611 run's actual shape).
    (cand / "PROCESS.md").write_text(
        "## Ranked issue list\n| rank | cluster | tasks | shared root cause | tag | class |\n"
        "|---|---|---|---|---|---|\n")
    assert "no data rows" in _warned(dashboard.reduce_run(run_dir))

    # 2. the parser itself raising — visible, never fatal.
    def _boom(_text):
        raise ValueError("bad table")
    monkeypatch.setattr(harness, "_parse_process_md_tables", _boom)
    assert "bad table" in _warned(dashboard.reduce_run(run_dir))

    # 3. an unparseable DIAGNOSIS.json.
    (cand / "DIAGNOSIS.json").write_text("{not json")
    assert "DIAGNOSIS.json unreadable" in _warned(dashboard.reduce_run(run_dir))
