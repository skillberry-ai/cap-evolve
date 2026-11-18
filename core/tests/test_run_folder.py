"""`run_folder.py` builds a run's standard folder (ci_runs/<run_id>__<tier>-<bench>/).

publish_results.sh covers the published result end to end (test_publish_results.py); this pins
the edge cases of the folder itself:

1. Something over the size limit is left out, and the README says so (a run's optimized
   capability or diff must not turn a results repo into a dump).
2. A folder built without the project dir (a backfill from a CI artifact, which never held
   it) says where the recipe lives instead of silently lacking it.
3. A failed run gets a folder that says it has no result, not a table of zeros.
"""

import importlib.util
import json
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "ci" / "benchmarks" / "lib"
sys.path.insert(0, str(LIB))
_spec = importlib.util.spec_from_file_location("run_folder", LIB / "run_folder.py")
run_folder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_folder)


def _out(tmp_path, conclusion="success"):
    out = tmp_path / "out"
    (out / "optimized" / "optimized_capability").mkdir(parents=True)
    (out / "runmeta.json").write_text(json.dumps({
        "run_id": 42, "bench": "tau2", "tier": "smoke", "conclusion": conclusion, "sha": "abcdef0123",
        "run_url": "https://github.com/skillberry-ai/cap-evolve/actions/runs/42", "pr": 7,
        "iterations": 3, "trials": 3, "agent_model": "a", "optimizer_model": "o", "algorithm": "hill-climb-all"}))
    (out / "metrics.jsonl").write_text(json.dumps({"task": "1", "reward_baseline": 0.25, "reward_opt": 0.5}) + "\n")
    (out / "steps.jsonl").write_text(json.dumps({"iter": 0, "eval_usd": 0.5, "optimizer_usd": 1.0}) + "\n")
    (out / "report.md").write_text("report\n")
    (out / "optimized" / "capability.diff").write_text("+x\n")
    (out / "optimized" / "optimized_capability" / "policy.md").write_text("p\n")
    return out


def test_an_oversized_part_is_left_out_and_named(tmp_path, monkeypatch):
    monkeypatch.setattr(run_folder, "MAX_BYTES", 10)
    out = _out(tmp_path)
    (out / "optimized" / "capability.diff").write_text("+" * 100)
    d = run_folder.build(out, tmp_path / "dest", None, None, None, None, "tau", False)
    assert not (d / "capability.diff").exists()
    assert "not included: capability.diff" in (d / "README.md").read_text()


def test_without_the_project_the_readme_points_at_the_tier_definition(tmp_path):
    d = run_folder.build(_out(tmp_path), tmp_path / "dest", None, None, None, None, "tau", False)
    readme = (d / "README.md").read_text()
    assert not (d / "recipe").exists()
    assert "`ci/benchmarks/tau2/smoke/` at the commit above" in readme
    assert "**Reward:** 0.250 → 0.500 (1 task)" in readme
    assert "[PR #7](https://github.com/skillberry-ai/cap-evolve/pull/7)" in readme
    assert "Open UI" not in readme                      # not published with it


def test_a_failed_run_says_it_has_no_result(tmp_path):
    d = run_folder.build(_out(tmp_path, conclusion="failure"), tmp_path / "dest", None, None, None, None, "tau", True)
    readme = (d / "README.md").read_text()
    assert "No suite result: the run did not finish successfully" in readme
    assert "**Reward:**" not in readme
    assert "[Open UI](https://skillberry-runs.github.io/dashboard/viewer/index.html?dataBase=" in readme
