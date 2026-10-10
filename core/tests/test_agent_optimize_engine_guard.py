"""#705: the skill's engine requirements are enforced, propose keeps its parent, clusters.json is slim."""

from __future__ import annotations

import json
import re
import types

import pytest
from test_digest_and_act_verbs import (  # noqa: F401  (autouse env fixture must be imported)
    SWITCHES, Sh, _act, _args, _env, _run, act, digest, graph, REPO, SCRIPTS)

ALL_ON = {k.lower(): True for k in SWITCHES[:7]}


def test_digest_first_line_warns_when_a_switch_is_off_and_names_the_full_val_risk(tmp_path, capsys):
    rd, project, _, _ = _run(tmp_path)
    assert digest.main(_args(rd, project)) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("!! CONFIG") and "active_eval" in first and "FULL val" in first
    assert digest.config_warning(ALL_ON) is None


def test_digest_has_no_config_warning_on_the_full_engine(tmp_path, capsys, monkeypatch):
    for k in SWITCHES[:7]:
        monkeypatch.setenv(f"CAPEVOLVE_{k}", "1")
    rd, project, _, _ = _run(tmp_path)
    digest.main(_args(rd, project))
    assert "CONFIG" not in capsys.readouterr().out


def test_probe_auto_with_active_eval_off_warns_loudly(tmp_path):
    rd, _, _, val = _run(tmp_path)
    seen = []
    ctx = types.SimpleNamespace(cfg={"active_eval": False}, run_dir=rd, warn=seen.append)
    ids, how = act.probe_ids(types.SimpleNamespace(tasks=None, auto=True, n=1, budget=None),
                             ctx, "c1", "cur", val)
    assert how.startswith("full val") and ids == val and "FULL val" in seen[0]


def test_second_propose_call_keeps_the_first_calls_parent(tmp_path, capsys, monkeypatch):
    rd, _, _, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    _act(monkeypatch, capsys, ["propose", "cand_p", "--parent", "cur", *_args(rd)])
    sh = Sh(**{"pregate.py": (0, json.dumps({"ok": True, "checks": [], "warnings": []}), "")})
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_p", *_args(rd)], sh)   # no --parent
    assert rc == 0 and out["result"]["parent"] == "cur"
    assert graph.latest_node(rd, "cand_p")["parents"] == ["cur"]


def test_diagnose_v2_writes_a_slim_clusters_json_and_a_full_one(tmp_path):
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(
        "diag_run", REPO / "skills/phases/diagnose/scripts/run.py")
    sys.path.insert(0, str(REPO / "skills/phases/diagnose/scripts"))
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)
    rd, project, _, _ = _run(tmp_path)
    assert diag.main(["--run-dir", str(rd.root), "--tag", "cur", "--split", "val",
                      "--cluster", "v2"]) == 0
    slim = json.loads((rd.root / "clusters.json").read_text())
    full = json.loads((rd.root / "clusters_full.json").read_text())
    assert "reflective_dataset" not in slim and "clusters" in slim
    assert "reflective_dataset" in full and slim["clusters"] == full["clusters"]


def test_every_host_briefing_section_reference_exists_in_the_doc_it_points_at():
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import host
    t = REPO / "tmp_unused"
    legacy_doc = host.LEGACY_DOC.read_text(encoding="utf-8")
    new_doc = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
    for spec, doc in (({}, legacy_doc),
                      ({"optimizer": {"ablation": {"active_eval": True, "dag_parallel": True}}}, new_doc)):
        text = host._briefing(run_dir=t, project=t, spec=spec, skills=t, rounds=3, workdir=t, context={})
        refs = set(re.findall(r'(?:its|SKILL\.md\'s|the) "([A-Z][^"]{2,40})" section', text))
        refs |= set(re.findall(r"(Phase 0|Setup)\b", text))
        assert refs, "briefing names no sections?"
        for r in refs:
            assert r in doc, f"briefing points at section {r!r} missing from the doc it names"
        assert host.optimizer_config.new_engine(spec) == (doc is new_doc)
