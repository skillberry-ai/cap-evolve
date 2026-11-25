"""reuse_baseline: a relative yaml value resolves against the work dir, and --resume of a
run whose baseline already ran is not blocked by a reuse_baseline dir that is gone.

Offline, toy adapter, zero API.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"
TEMPLATE_SPEC = REPO / "benchmarks" / "_scaffold" / "project" / "capevolve.yaml"
BASELINE_RUN = REPO / "skills" / "phases" / "baseline" / "scripts" / "run.py"


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _project(work, extra_yaml=""):
    project = work / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", work / "seed_capability")
    spec = project / "capevolve.yaml"
    spec.write_text(TEMPLATE_SPEC.read_text(encoding="utf-8") + extra_yaml, encoding="utf-8")
    return project, spec


def test_yaml_relative_reuse_baseline_resolves_against_work_dir(tmp_path, capsys, monkeypatch):
    work = tmp_path / "work"
    project, spec = _project(work, "\nreuse_baseline: .capevolve/run_prior\n")
    prior = work / ".capevolve" / "run_prior"
    prior.mkdir()
    # Started from the work dir's parent, with an absolute --project.
    monkeypatch.chdir(tmp_path)
    from cap_evolve import cli
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--plan-only",
                   "--dashboard", "off"])
    assert rc == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["spec"]["reuse_baseline"] == str(prior.resolve())

    # The up-front check reads the same place: the dir is found, so the error names the
    # missing file rather than a missing directory.
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project),
                   "--dashboard", "off", "--run-ts", "t"])
    out = capsys.readouterr()
    assert rc != 0
    err = json.loads(out.out.strip().splitlines()[-1])["error"]
    assert str(prior.resolve()) in err and "no splits.json" in err


def test_baseline_script_resume_ignores_gone_reuse_dir(tmp_path):
    project, _ = _project(tmp_path)
    base = tmp_path / ".capevolve"
    env = {**os.environ, "PYTHONPATH": str(CORE)}
    common = [sys.executable, str(BASELINE_RUN), "--base", str(base), "--project", str(project),
              "--capability", str(tmp_path / "seed_capability"), "--run-ts", "b1"]
    r1 = subprocess.run(common, capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert r1.returncode == 0, r1.stderr
    r2 = subprocess.run(common + ["--resume", "--reuse-baseline", str(tmp_path / "gone")],
                        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert r2.returncode == 0, r2.stderr
    assert json.loads(r2.stdout)["resumed"] is True


def test_cli_resume_ignores_gone_reuse_dir(tmp_path, capsys, monkeypatch):
    project, spec = _project(tmp_path, "\nreuse_baseline: gone_prior\n")
    base = tmp_path / ".capevolve"
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(base, ts="r1", budget=Budget(max_iterations=1))
    (rd.root / "baseline.json").write_text("{}", encoding="utf-8")

    # Stop at the first step the CLI launches: reaching it means the up-front reuse
    # check did not block the resume.
    calls = []

    class _Stop(Exception):
        pass

    def _fake_run(cmd, *a, **kw):
        calls.append(cmd)
        raise _Stop

    monkeypatch.setattr(subprocess, "run", _fake_run)
    from cap_evolve import cli
    with pytest.raises(_Stop):
        cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                  "--run-ts", "r1", "--resume"])
    assert "not a run dir" not in capsys.readouterr().out
    assert calls and "--resume" in calls[0]

    # Without --resume (a fresh run) the same gone dir still fails up front.
    monkeypatch.undo()
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                   "--run-ts", "fresh"])
    assert rc != 0
    assert "no such directory" in capsys.readouterr().out
    assert not (base / "run_fresh").exists()
