"""#632: a registered pre-gate check (e.g. replay_gold.py) is a HARD precondition in round.py.

run_full's cand_13 had 4/30 gold-replay diffs and still paid a 300-rollout gate; the bundle
cand_15 carried the same guard and paid a second one. round.py now runs the check on every
tag's bytes before any screen/eval and refuses the round on a failure — so a bundle carrying
the invalid edit is caught too, and the earlier invalid tag is named.
"""

from __future__ import annotations

import json
import shutil
import sys

from test_round_requires_screen_ladder import SCRIPTS, _JUSTIFY, _run, _staged_run_dir

# Mimics replay_gold.py's real output AND its real exit code (always 0): a candidate carrying a
# GUARD file is "invalid" — 4 of 30 tasks differ.
_CHECK = """import sys, pathlib
bad = (pathlib.Path(sys.argv[1]) / "GUARD").exists()
print(f"{4 if bad else 0} of 30 val tasks differ from pristine under gold replay")
"""


def _round(run_dir, project, tags, *extra):
    return _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                 "--project", str(project), "--candidates", tags, "--n-trials", "1",
                 "--skip-screen-justification", "pregate test", *_JUSTIFY, *extra])


def _events(run_dir, kind):
    return [json.loads(ln) for ln in run_dir.events_path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and json.loads(ln).get("kind") == kind]


def _check_cmd(tmp_path):
    script = tmp_path / "replay_gold.py"
    script.write_text(_CHECK, encoding="utf-8")
    return f"{sys.executable} {script}"


def test_nonzero_gold_replay_refuses_before_any_eval_spend(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    (work / "cand_1" / "GUARD").write_text("reason guard", encoding="utf-8")
    p = _round(run_dir, project, "cand_1", "--pregate-check", _check_cmd(tmp_path))
    assert p.returncode == 2, p.stdout + p.stderr
    err = json.loads(p.stdout)
    assert "cand_1" in err["error"] and "4 of 30" in err["invalid"]["cand_1"]
    # Nothing was paid: no candidate rollouts, no screen, no compliance/round event.
    assert not list((run_dir.rollouts / "val").glob("*__cand_1__*"))
    assert not _events(run_dir, "agent_optimize_compliance")
    assert [e["tag"] for e in _events(run_dir, "agent_optimize_pregate_invalid")] == ["cand_1"]


def test_zero_diffs_proceeds_normally(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _round(run_dir, project, "cand_1", "--pregate-check", _check_cmd(tmp_path))
    assert p.returncode == 0, p.stdout + p.stderr
    assert [r["tag"] for r in json.loads(p.stdout)["candidates"]] == ["cand_1"]
    assert not _events(run_dir, "agent_optimize_pregate_invalid")


def test_bundle_carrying_a_known_invalid_component_is_refused_in_a_later_round(tmp_path):
    """cand_15's case: the check is registered once, then a later round's bundle carrying
    cand_1's guard is refused WITHOUT the flag being passed again, naming cand_1."""
    run_dir, project, work = _staged_run_dir(tmp_path)
    (work / "cand_1" / "GUARD").write_text("reason guard", encoding="utf-8")
    assert _round(run_dir, project, "cand_1", "--pregate-check", _check_cmd(tmp_path)
                  ).returncode == 2

    shutil.copytree(work / "cand_1", work / "cand_bundle")  # bundle carries cand_1's edit
    (work / "cand_bundle" / "OTHER_EDIT").write_text("x", encoding="utf-8")
    p = _round(run_dir, project, "cand_bundle")  # no --pregate-check: it is sticky
    assert p.returncode == 2, p.stdout + p.stderr
    err = json.loads(p.stdout)
    assert list(err["invalid"]) == ["cand_bundle"]
    assert err["known_invalid_earlier_in_run"] == ["cand_1"]
    assert not list((run_dir.rollouts / "val").glob("*__cand_bundle__*"))


def test_merge_that_fails_the_check_is_skipped_before_its_screen(tmp_path, monkeypatch):
    """A merge round.py builds itself is checked too, before its screen spends a rollout."""
    import merge
    import round as round_mod
    from cap_evolve import RunDir

    run_dir, project, work = _staged_run_dir(tmp_path)
    rd = RunDir.open(run_dir.root)
    shutil.copytree(work / "cand_1", work / "cand_2")

    def fake_merge(base, a, b, dest, **_kw):  # two valid parents composing into an invalid merge
        shutil.copytree(a, dest)
        (dest / "GUARD").write_text("g", encoding="utf-8")
        return {"built": True, "conflicts": [], "three_way_merged": []}

    monkeypatch.setattr(merge, "build_merge_dir", fake_merge)
    monkeypatch.setattr(round_mod, "cluster_ids_for", lambda *a: [])
    screened = []
    monkeypatch.setattr(round_mod, "_screen", lambda *a, **k: screened.append(a[2]) or {"rc": 0})
    out = round_mod.merge_stage(rd, project, "cur", ["cand_1", "cand_2"], {}, None, 1,
                                pregate_cmd=_check_cmd(tmp_path))
    assert out["merges"] == [] and screened == []
    assert out["skipped_pairs"][0]["reason"] == "merge fails the pre-gate check"
    assert [e["tag"] for e in _events(rd, "agent_optimize_pregate_invalid")] == [
        "merge_cand_1_cand_2"]


# ---- #708: the built-in deterministic pre-gate, with no registered check -------------------
_COMPOSITE = ("class T:\n    @is_tool(ToolType.WRITE)\n    def update_a(self): pass\n"
              "    @is_tool(ToolType.WRITE)\n    def update_both(self):\n        return self.update_a()\n")


def _stage_composite(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    (work / "cand_1" / "tools").mkdir(exist_ok=True)
    (work / "cand_1" / "tools" / "composite.py").write_text(_COMPOSITE, encoding="utf-8")
    return run_dir, project


def test_builtin_pregate_refuses_hidden_write_composite_before_any_spend(tmp_path):
    run_dir, project = _stage_composite(tmp_path)
    p = _round(run_dir, project, "cand_1")
    assert p.returncode == 2, p.stdout + p.stderr
    assert "update_both -> update_a" in json.loads(p.stdout)["invalid"]["cand_1"]
    assert not list((run_dir.rollouts / "val").glob("*__cand_1__*"))
    assert [e["tag"] for e in _events(run_dir, "agent_optimize_pregate_invalid")] == ["cand_1"]


def test_ablation_pregate_off_is_legacy_behaviour(tmp_path):
    from test_round_requires_screen_ladder import _run

    run_dir, project = _stage_composite(tmp_path)
    q = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root), "--project", str(project),
              "--candidates", "cand_1", "--n-trials", "1", "--skip-screen-justification", "x",
              *_JUSTIFY], env={"CAPEVOLVE_PREGATE": "off"})
    assert q.returncode == 0, q.stdout + q.stderr
    assert not _events(run_dir, "agent_optimize_pregate_invalid")


def test_invalid_sibling_is_dropped_not_the_whole_round(tmp_path):
    run_dir, project = _stage_composite(tmp_path)
    work = run_dir.root / "work"
    shutil.copytree(work / "cand_1", work / "cand_2")
    (work / "cand_2" / "tools" / "composite.py").unlink()  # cand_2 is clean
    p = _round(run_dir, project, "cand_1,cand_2")
    assert p.returncode == 0, p.stdout + p.stderr
    assert [r["tag"] for r in json.loads(p.stdout)["candidates"]] == ["cand_2"]
    assert [e["tag"] for e in _events(run_dir, "agent_optimize_pregate_invalid")] == ["cand_1"]
