"""`backup_run.sh` archives a leg's raw run data on the runner, outside the workspace.

WHY THIS EXISTS

The published results (ci_runs/, ci_ui/, the dashboard record) are a summary. The raw run data,
the run dir with every candidate, trace and rollout, is lost when the next job's checkout cleans
the workspace. Until CI can upload to Box, each run is archived on the runner in the same layout
as the Box folder "skillberry-runs-backup", so moving it there is a plain copy.

WHAT THIS PINS

1. The archive lands at <root>/user/<user>/<repo>/<run_id>__<slug>.tar.zst and holds both the
   output dir and the project's .capevolve/ (project + run dir); backup.json says where it is,
   with a matching sha256. The user name cannot escape its folder.
2. The repo comes from the dashboard's sections.json; if that can't be read, the bench name.
3. Too little disk -> skipped with a warning, exit 0. Nothing to archive -> exit 0.
4. No zstd on the runner -> a .tar.gz, with a warning.
5. The run folder (run_folder.py) carries backup.json and its README names the archive.
6. The workflow runs it best-effort (continue-on-error), before publishing, with the user name
   passed through the environment.
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
SCRIPT = LIB / "backup_run.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
NAME = "999000111__smoke-tau2"


def _work(tmp_path: Path) -> Path:
    out = tmp_path / ".work" / "suite_smoke_tau2"
    (out / "optimized").mkdir(parents=True)
    (out / "runmeta.json").write_text(json.dumps({"run_id": 999000111, "bench": "tau2", "tier": "smoke"}))
    (out / "report.md").write_text("report\n")
    run = tmp_path / ".work" / "suite_smoke_tau2_proj" / ".capevolve" / "run_suite" / "candidates" / "cand_0001"
    run.mkdir(parents=True)
    (run / "policy.md").write_text("p\n")
    (run.parents[1] / "final.json").write_text("{}")
    return out


def _run(tmp_path, out, **env):
    e = {**os.environ, "BACKUP_ROOT": str(tmp_path / "backup"), "BACKUP_USER": "bcarmeli",
         "BACKUP_REPO": "tau", "PY": sys.executable, "RUNNER_NAME": "test-runner", **env}
    e.pop("GITHUB_STEP_SUMMARY", None)
    return subprocess.run(["bash", str(SCRIPT), str(out), "999000111", "smoke-tau2"],
                          capture_output=True, text=True, env=e, timeout=120)


def _members(archive: Path) -> list[str]:
    if archive.suffix == ".zst":
        data = subprocess.run(["zstd", "-dc", str(archive)], capture_output=True, check=True).stdout
        return subprocess.run(["tar", "-tf", "-"], input=data, capture_output=True, check=True).stdout.decode().split()
    return subprocess.run(["tar", "-tzf", str(archive)], capture_output=True, check=True, text=True).stdout.split()


@pytest.mark.skipif(not shutil.which("zstd"), reason="needs zstd")
def test_archives_the_output_dir_and_the_run_dir_where_box_expects_them(tmp_path):
    out = _work(tmp_path)
    r = _run(tmp_path, out)
    assert r.returncode == 0, r.stdout + r.stderr
    archive = tmp_path / "backup" / "user" / "bcarmeli" / "tau" / f"{NAME}.tar.zst"
    assert archive.is_file()
    m = _members(archive)
    assert "suite_smoke_tau2/report.md" in m
    assert "suite_smoke_tau2_proj/.capevolve/run_suite/final.json" in m
    assert "suite_smoke_tau2_proj/.capevolve/run_suite/candidates/cand_0001/policy.md" in m
    b = json.loads((out / "backup.json").read_text())
    assert b["archive"] == f"user/bcarmeli/tau/{NAME}.tar.zst"
    assert b["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert b["bytes"] == archive.stat().st_size and "test-runner" in b["location"]
    assert not list(archive.parent.glob("*.partial"))


def test_the_user_name_cannot_escape_its_folder(tmp_path):
    r = _run(tmp_path, _work(tmp_path), BACKUP_USER="../../etc")
    assert r.returncode == 0, r.stdout + r.stderr
    users = [p.name for p in (tmp_path / "backup" / "user").iterdir()]
    assert users == [".._.._etc"], users          # one folder name, not a path
    assert not (tmp_path / "etc").exists()


def test_without_sections_json_the_bench_name_is_the_folder(tmp_path):
    env = {"BACKUP_REPO": "", "SECTIONS_URL": f"file://{tmp_path}/missing.json"}
    r = _run(tmp_path, _work(tmp_path), **env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "filing it under 'tau2'" in r.stdout
    assert list((tmp_path / "backup" / "user" / "bcarmeli" / "tau2").glob(f"{NAME}.tar.*"))


def test_repo_comes_from_sections_json(tmp_path):
    (tmp_path / "sections.json").write_text(json.dumps([{"repo": "tau", "title": "tau2", "benches": ["tau2"]}]))
    r = _run(tmp_path, _work(tmp_path), BACKUP_REPO="", SECTIONS_URL=f"file://{tmp_path}/sections.json")
    assert r.returncode == 0, r.stdout + r.stderr
    assert list((tmp_path / "backup" / "user" / "bcarmeli" / "tau").glob(f"{NAME}.tar.*"))


def test_too_little_disk_skips_with_a_warning(tmp_path):
    out = _work(tmp_path)
    r = _run(tmp_path, out, BACKUP_MIN_FREE_GB="100000000")
    assert r.returncode == 0
    assert "::warning::not backing up" in r.stdout
    assert not list((tmp_path / "backup").rglob("*.tar.*")) and not (out / "backup.json").exists()


def test_nothing_to_archive_is_not_an_error(tmp_path):
    r = _run(tmp_path, tmp_path / "nowhere")
    assert r.returncode == 0 and "nothing to back up" in r.stdout


@pytest.mark.skipif(any(Path(d, "zstd").exists() for d in ("/usr/bin", "/bin")),
                    reason="zstd is in the system path here, so it can't be hidden")
def test_without_zstd_it_falls_back_to_gzip(tmp_path):
    r = _run(tmp_path, _work(tmp_path), PATH="/usr/bin:/bin")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "zstd is not installed" in r.stdout
    archive = tmp_path / "backup" / "user" / "bcarmeli" / "tau" / f"{NAME}.tar.gz"
    assert "suite_smoke_tau2/report.md" in _members(archive)


def test_the_run_folder_says_where_the_archive_is(tmp_path):
    sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location("run_folder", LIB / "run_folder.py")
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)
    out = _work(tmp_path)
    (out / "backup.json").write_text(json.dumps({"archive": f"user/bcarmeli/tau/{NAME}.tar.zst",
                                                 "location": "on runner r1 in ~/skillberry-runs-backup/, to be moved to Box",
                                                 "bytes": 5_000_000}))
    d = rf.build(out, tmp_path / "folder", None, None, None, None, "tau", False)
    assert (d / "backup.json").is_file()
    readme = (d / "README.md").read_text()
    assert f"`user/bcarmeli/tau/{NAME}.tar.zst` in the `skillberry-runs-backup` archive" in readme


def test_workflow_backs_up_best_effort_before_publishing():
    src = WORKFLOW.read_text()
    names = re.findall(r"^      - name: (.+)$", src, re.M)
    assert names.index("Write run metadata") < names.index("Back up the raw run data on the runner") \
        < names.index("Publish results to skillberry-runs")
    step = src[src.index("      - name: Back up the raw run data on the runner"):]
    step = step[:step.index("\n      - name:", 10)]
    assert "continue-on-error: true" in step and "if: always()" in step and "timeout-minutes:" in step
    assert "BACKUP_USER: ${{ github.triggering_actor }}" in step
    assert "${{ github.triggering_actor }}" not in step[step.index("run: |"):], "user name must not be in the shell source"
