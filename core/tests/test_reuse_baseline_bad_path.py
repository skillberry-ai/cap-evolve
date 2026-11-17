"""``--reuse-baseline <bad path>`` fails up front with a plain error and leaves no run dir.

Covers both entry points: ``cap-evolve run`` (cli.py) and the baseline phase script
called on its own. Offline, toy adapter, zero API.
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


@pytest.fixture
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _project(tmp_path):
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")
    spec = project / "capevolve.yaml"
    spec.write_text(TEMPLATE_SPEC.read_text(encoding="utf-8"), encoding="utf-8")
    return project, spec


def _run_dirs(tmp_path):
    return sorted((tmp_path / ".capevolve").glob("run_*"))


def _cli(tmp_path, reuse, capsys):
    from cap_evolve import cli
    project, spec = _project(tmp_path)
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project),
                   "--dashboard", "off", "--run-ts", "t", "--reuse-baseline", str(reuse)])
    out = capsys.readouterr()
    return rc, out


def test_cli_missing_dir_fails_cleanly(tmp_path, capsys, _env):
    rc, out = _cli(tmp_path, tmp_path / "nope", capsys)
    assert rc != 0
    assert "Traceback" not in out.out + out.err
    err = json.loads(out.out)["error"]
    assert "--reuse-baseline" in err and "not a run dir" in err
    assert _run_dirs(tmp_path) == []


@pytest.mark.parametrize("present,missing", [((), "splits.json"),
                                              (("splits.json",), "baseline.json")])
def test_cli_dir_without_run_files_fails_cleanly(tmp_path, capsys, _env, present, missing):
    prior = tmp_path / "prior"
    prior.mkdir()
    for name in present:
        (prior / name).write_text("{}", encoding="utf-8")
    rc, out = _cli(tmp_path, prior, capsys)
    assert rc != 0
    assert "Traceback" not in out.out + out.err
    assert f"no {missing}" in json.loads(out.out)["error"]
    assert _run_dirs(tmp_path) == []


def test_cli_relative_path_is_resolved_against_cwd(tmp_path, capsys, _env, monkeypatch):
    # A valid-looking prior run dir that exists ONLY relative to the user's cwd. The
    # steps run with cwd = project's grandparent, so an unresolved path would miss it.
    user_cwd = tmp_path / "elsewhere"
    (user_cwd / "prior").mkdir(parents=True)
    monkeypatch.chdir(user_cwd)
    from cap_evolve import cli
    project, spec = _project(tmp_path)
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--plan-only",
                   "--dashboard", "off", "--reuse-baseline", "prior"])
    assert rc == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["spec"]["reuse_baseline"] == str((user_cwd / "prior").resolve())

    # And the check reads from the cwd too: the relative dir is found, so the error names
    # the missing file, not a missing directory.
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project),
                   "--dashboard", "off", "--run-ts", "t", "--reuse-baseline", "prior"])
    out = capsys.readouterr()
    assert rc != 0
    err = json.loads(out.out)["error"]
    assert str((user_cwd / "prior").resolve()) in err and "no splits.json" in err
    assert _run_dirs(tmp_path) == []


@pytest.mark.parametrize("make_prior", [False, True])
def test_baseline_script_bad_reuse_path_leaves_no_run_dir(tmp_path, _env, make_prior):
    project, _ = _project(tmp_path)
    prior = tmp_path / "prior"
    if make_prior:
        prior.mkdir()
    base = tmp_path / ".capevolve"
    env = dict(os.environ, PYTHONPATH=str(CORE))
    proc = subprocess.run(
        [sys.executable, str(BASELINE_RUN), "--base", str(base), "--project", str(project),
         "--capability", str(tmp_path / "seed_capability"), "--run-ts", "t",
         "--reuse-baseline", str(prior)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert proc.returncode != 0
    assert "Traceback" not in proc.stdout + proc.stderr
    err = json.loads(proc.stderr.strip().splitlines()[-1])["error"]
    assert "not a run dir" in err
    assert _run_dirs(tmp_path) == []
