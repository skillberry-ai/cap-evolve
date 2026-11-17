"""T-13: the remaining capevolve.yaml readers read the spec strictly.

A typo like ``max_usd: "5`` (unclosed quote) must fail with the file name and the
line, not be read quietly as the string ``'"5'`` while every check says ok.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SELFTEST = REPO / "skills" / "phases" / "implement-and-check" / "scripts" / "pipeline_selftest.py"
HOST = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "host.py"
BASELINE = REPO / "skills" / "phases" / "baseline" / "scripts" / "run.py"

BROKEN = 'algorithm_skill: hill-climb\nmax_usd: "5\nnum_trials: 1\n'


def _env() -> dict:
    return dict(os.environ, PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
                CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


def _project(tmp: Path) -> Path:
    project = tmp / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter\n\n\n"
        "class Adapter(SyntheticAdapter):\n"
        "    def __init__(self):\n        super().__init__(n=12)\n", encoding="utf-8")
    (project / "capevolve.yaml").write_text(BROKEN, encoding="utf-8")
    return project


def test_pipeline_selftest_fails_on_unclosed_quote(tmp_path):
    project = _project(tmp_path)
    p = subprocess.run([sys.executable, str(SELFTEST), "--project", str(project)],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 1, p.stdout + p.stderr
    report = json.loads(p.stdout)
    assert report["ok"] is False
    msg = " ".join(report["problems"])
    assert "capevolve.yaml" in msg and "line" in msg


def test_host_spec_raises_spec_error(tmp_path):
    import pytest
    from cap_evolve.specfile import SpecError
    sys.path.insert(0, str(HOST.parent))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_t13_host", HOST)
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
    finally:
        sys.path.remove(str(HOST.parent))
    project = _project(tmp_path)
    with pytest.raises(SpecError) as ei:
        host._spec(project, None)
    assert "capevolve.yaml" in str(ei.value) and "line" in str(ei.value)


def test_host_main_prints_json_error(tmp_path):
    project = _project(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    p = subprocess.run([sys.executable, str(HOST), "--run-dir", str(run_dir),
                        "--project", str(project)],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 2, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert "capevolve.yaml" in out["error"] and "line" in out["error"]


def test_baseline_fails_on_unclosed_quote_and_leaves_no_run_dir(tmp_path):
    from cap_evolve.skillcheck import seed_capability_dir
    project = _project(tmp_path)
    seed = seed_capability_dir(tmp_path, level=3)
    base = tmp_path / ".capevolve"
    p = subprocess.run([sys.executable, str(BASELINE), "--base", str(base),
                        "--project", str(project), "--capability", str(seed),
                        "--run-ts", "broken"],
                       capture_output=True, text=True, cwd=tmp_path, env=_env())
    assert p.returncode == 1, p.stdout + p.stderr
    err = json.loads(p.stderr.strip().splitlines()[-1])
    assert "capevolve.yaml" in err["error"] and "line" in err["error"]
    assert not (base / "run_broken").exists()
