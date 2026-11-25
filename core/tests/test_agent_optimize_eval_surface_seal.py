"""#762: agent-optimize's act.py seals the project's eval surface (adapters/, scorer, tasks) at the
run's first act call and refuses promote / finalize when it changed since. Fake run, no model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_digest_and_act_verbs import Sh, _act, _args, _covered, _gate, _run  # noqa: E402

from cap_evolve import RunDir, integrity  # noqa: E402


def _events(rd, kind):
    lines = rd.events_path.read_text(encoding="utf-8").splitlines() if rd.events_path.exists() else []
    return [e for e in map(json.loads, lines) if e.get("kind") == kind]


def _first_call(monkeypatch, capsys, rd, project):
    """Any act call naming --project records the manifest (here a cheap probe --plan)."""
    _act(monkeypatch, capsys, ["probe", "cand_1", "--plan", "--tasks", "x", *_args(rd, project)], Sh())
    assert (Path(rd.private_dir) / integrity.EVAL_SURFACE_MANIFEST).exists()


def test_promote_works_when_the_eval_surface_is_unchanged(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _first_call(monkeypatch, capsys, rd, project)
    _covered(rd, val)
    (project / "adapters" / "__pycache__").mkdir()
    (project / "adapters" / "__pycache__" / "adapter.cpython-311.pyc").write_bytes(b"x")  # noise, not tamper
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 0 and out["result"]["champion_changed"], out
    assert not _events(rd, "tamper")


def test_promote_refuses_with_tamper_after_the_adapter_is_edited(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _first_call(monkeypatch, capsys, rd, project)
    _covered(rd, val)
    adapter = project / "adapters" / "adapter.py"
    adapter.write_text(adapter.read_text() + "\n# always score 1.0\n")
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc != 0 and out["verdict"] == "tamper" and out["changed"] == ["adapters/adapter.py"], out
    assert not any(c[1].endswith("commit.py") for c in sh.calls), "nothing committed"
    assert RunDir.open(rd.root).best_id == "cur", "best_id untouched"
    ev = _events(rd, "tamper")
    assert ev and ev[-1]["changed"] == ["adapters/adapter.py"] and ev[-1]["verb"] == "promote"
    # promote without --project still checks against the recorded project
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd)], sh)
    assert rc != 0 and out["verdict"] == "tamper"


def test_an_added_scorer_or_a_different_project_is_tamper(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _first_call(monkeypatch, capsys, rd, project)
    _covered(rd, val)
    (project / "scorer.py").write_text("def score(*a): return 1.0\n")
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc != 0 and out["changed"] == ["scorer.py"]
    (project / "scorer.py").unlink()
    other = tmp_path / "other"
    (other / "adapters").mkdir(parents=True)
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, other)], sh)
    assert rc != 0 and out["verdict"] == "tamper" and "recorded for" in out["error"]


def test_finalize_refuses_with_tamper_and_does_not_score_test(tmp_path, capsys, monkeypatch):
    rd, project, _, _ = _run(tmp_path)
    _first_call(monkeypatch, capsys, rd, project)
    (project / "adapters" / "tasks.jsonl").write_text('{"id": "new"}\n')
    sh = Sh(**{"run.py": (0, json.dumps({"test_reward": 0.5}), "")})
    rc, out = _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], sh)
    assert rc != 0 and out["verdict"] == "tamper" and out["changed"] == ["adapters/tasks.jsonl"], out
    assert not sh.calls and not (rd.root / "finalize.intent").exists()
    assert not RunDir.open(rd.root).read_splits().test_used
    assert _events(rd, "tamper")[-1]["verb"] == "finalize"


def test_finalize_pooled_confirm_gate_is_advisory(tmp_path, capsys, monkeypatch):
    from test_paper_mode_switches import _fin_env, _write_trial
    import test_digest_and_act_verbs as T
    _fin_env(monkeypatch)
    rd, project, _, val = _run(tmp_path)
    rd.snapshot("seed", rd.candidate_dir("cur"))
    T._ledger(rd, T._h(rd, "cur"), {v: [1, 0] for v in val})
    for v in val[:2]:
        for k in (0, 1):
            _write_trial(rd, v, "cur", k, 1.0)
    sh = Sh(**{"gate_check.py": _gate("accept"), "run.py": (0, json.dumps({"test_reward": 0.7}), "")})
    rc, out = _act(monkeypatch, capsys, ["finalize", *_args(rd, project)], sh)
    assert rc == 0, out
    gates = [c for c in sh.calls if any(x.endswith("gate_check.py") for x in c)]
    assert len(gates) == 2
    assert "--advisory" not in gates[0], "the fresh-trial confirmation is the real gate record"
    assert gates[1][gates[1].index("--advisory") + 1] == "pooled_confirm"


def _promote_after_edit(tmp_path, capsys, monkeypatch, rd, project, real_adapter):
    _first_call(monkeypatch, capsys, rd, project)
    man = integrity.read_manifest(Path(rd.private_dir) / integrity.EVAL_SURFACE_MANIFEST)
    assert "adapters/adapter.py" in man["files"], man
    assert man["targets"]["adapters/adapter.py"] == str(real_adapter.resolve()), "resolved path recorded"
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", "")})
    real_adapter.write_text(real_adapter.read_text() + "\n# always score 1.0\n")
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 2 and out["verdict"] == "tamper" and "adapters/adapter.py" in out["changed"], out
    assert RunDir.open(rd.root).best_id == "cur"
    assert not any(c[1].endswith("commit.py") for c in sh.calls)


def test_a_symlinked_adapters_folder_is_sealed_by_content(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    shared = tmp_path / "shared_adapters"  # outside the project, as the parsec scaffolds do
    (project / "adapters").rename(shared)
    (project / "adapters").symlink_to(shared, target_is_directory=True)
    _promote_after_edit(tmp_path, capsys, monkeypatch, rd, project, shared / "adapter.py")


def test_a_symlinked_adapter_file_outside_the_project_is_sealed_by_content(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    outside = tmp_path / "elsewhere" / "adapter.py"
    outside.parent.mkdir()
    (project / "adapters" / "adapter.py").rename(outside)
    (project / "adapters" / "adapter.py").symlink_to(outside)
    _promote_after_edit(tmp_path, capsys, monkeypatch, rd, project, outside)


def test_retargeting_a_symlinked_adapter_is_tamper(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_text("X = 1\n")
    b.write_text("X = 1\n")  # same content, different file
    link = project / "adapters" / "adapter.py"
    link.unlink()
    link.symlink_to(a)
    _first_call(monkeypatch, capsys, rd, project)
    link.unlink()
    link.symlink_to(b)
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 2 and out["verdict"] == "tamper" and out["changed"] == ["adapters/adapter.py"], out


def test_a_project_with_no_eval_surface_files_refuses_promote_and_finalize(tmp_path, capsys, monkeypatch):
    import shutil
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    shutil.rmtree(project / "adapters")
    for p in project.iterdir():
        assert not any(__import__("fnmatch").fnmatch(p.name, g) for g in integrity.EVAL_SURFACE_FILES)
    _first_call(monkeypatch, capsys, rd, project)
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", ""),
               "run.py": (0, json.dumps({"test_reward": 0.5}), "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 2 and out["verdict"] == "tamper" and "TAMPER-UNKNOWN" in out["error"], out
    assert RunDir.open(rd.root).best_id == "cur"
    rc, out = _act(monkeypatch, capsys, ["finalize", "--n-confirm", "0", *_args(rd, project)], sh)
    assert rc == 2 and out["verdict"] == "tamper" and "TAMPER-UNKNOWN" in out["error"], out
    assert not RunDir.open(rd.root).read_splits().test_used


def test_conductor_commit_accept_turns_a_tamper_refusal_into_a_clean_conductor_refusal(tmp_path, monkeypatch):
    """On the conductor path the tamper guard in act.commit raises act.Refused; RealBackend.commit_accept must
    re-raise it as conductor.Refused so the conductor exits 2 (refused) and the supervisor does not relaunch."""
    import argparse
    import types

    import act
    import conductor
    import conductor_backend
    import pytest
    from cap_evolve import harness

    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    ctx = act.Ctx(argparse.Namespace(run_dir=str(rd.root), project=str(project), strict=False))
    adapter = project / "adapters" / "adapter.py"
    adapter.write_text(adapter.read_text() + "\n# always score 1.0\n")
    sh = Sh(**{"commit.py": (0, "{}", "")})
    monkeypatch.setattr(act, "sh", sh)
    monkeypatch.setattr(harness, "split_result_from_rollouts",
                        lambda *a, **k: types.SimpleNamespace(per_task={"t": 1.0}, reward=1.0))
    be = types.SimpleNamespace(run_dir=RunDir.open(rd.root), ctx=ctx, cfg=types.SimpleNamespace(p2=False),
                               _rediagnose=lambda tag: None)
    with pytest.raises(conductor.Refused, match="tamper|changed"):
        conductor_backend.RealBackend.commit_accept(be, "cand_1", {"confirmation": "accept"})
    assert not any(c[1].endswith("commit.py") for c in sh.calls), "nothing committed"
    assert RunDir.open(rd.root).best_id == "cur"
    spawns = []
    assert conductor.supervise([], max_restarts=3, sleep_s=0, sleep=lambda s: None,
                               spawn=lambda a: spawns.append(1) or conductor.EXIT_REFUSED) == conductor.EXIT_REFUSED
    assert len(spawns) == 1, "a refusal is not relaunched"
