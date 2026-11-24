"""`backup_run.sh` keeps a leg's raw run data on the runner, outside the workspace.

WHY THIS EXISTS

The published results (ci_runs/, ci_ui/, the dashboard record) are a summary. The raw run data,
the run dir with every candidate, trace and rollout, is lost when the next job's checkout cleans
the workspace. So each leg keeps it on the runner as a capture SOURCE for docs/FULL_BACKUP.md
(§5.3(b)): an operator later unpacks, verifies, organizes and uploads it. It is not laid out like
the backup location and is never copied into it as is.

WHAT THIS PINS

1. The capture dir is <root>/<run_id>__<slug>/ with the archive (output dir + the project's
   .capevolve/ + the sealed dir when there is one), members.sha256 (source hashes, matching the archive's members byte for byte),
   symlinks.txt and backup.json (archive sha256 and size, who triggered it, bench, tier); a copy
   of backup.json lands in the output dir.
2. A capture dir is never overwritten; a re-run attempt gets <run_id>__<slug>.a<N>/.
3. The user name is recorded as given, never used in a path.
4. The results repo comes from the dashboard's sections.json; if that can't be read, the bench name.
5. Too little disk -> skipped with a warning, exit 0. Nothing to archive -> exit 0.
6. No zstd on the runner -> a .tar.gz, with a warning.
7. The run folder (run_folder.py) carries backup.json and its README names the capture dir.
8. An unreadable file or directory does not stop the capture: it is listed in unreadable.txt and
   backup.json, and the rest is kept.
9. The workflow runs it best-effort (continue-on-error), before publishing, with the user name
   passed through the environment, and only on a dispatch that names a staging area
   (raw_data_location, empty by default); the rclone config comes from a secret, via the environment.
10. Staging: with RAW_DATA_LOCATION the capture dir is uploaded write-once and checked, and only then
   removed from the runner; <out_dir>/backup.json says where it is staged. The rclone config is a
   0600 temp file, removed afterwards. A failed upload (bad path, unknown remote) leaves the capture
   on the runner and says why.
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
    e = {**os.environ, "CI_CAPTURE_ROOT": str(tmp_path / "capture"), "BACKUP_USER": "bcarmeli",
         "BACKUP_REPO": "tau", "PY": sys.executable, "RUNNER_NAME": "test-runner", **env}
    e.pop("GITHUB_STEP_SUMMARY", None)
    if "GITHUB_RUN_ATTEMPT" not in env:
        e.pop("GITHUB_RUN_ATTEMPT", None)
    return subprocess.run(["bash", str(SCRIPT), str(out), "999000111", "smoke-tau2"],
                          capture_output=True, text=True, env=e, timeout=120)


def _tar(archive: Path, *args: str, cwd=None) -> bytes:
    if archive.suffix == ".zst":
        data = subprocess.run(["zstd", "-dc", str(archive)], capture_output=True, check=True).stdout
        return subprocess.run(["tar", *args, "-f", "-"], input=data, capture_output=True, check=True, cwd=cwd).stdout
    return subprocess.run(["tar", "-z", *args, "-f", str(archive)], capture_output=True, check=True, cwd=cwd).stdout


def _members(archive: Path) -> list[str]:
    return _tar(archive, "-t").decode().split()


CAP = Path("capture") / NAME


@pytest.mark.skipif(not shutil.which("zstd"), reason="needs zstd")
def test_keeps_the_output_dir_and_the_run_dir_with_source_hashes(tmp_path):
    out = _work(tmp_path)
    (out / "link").symlink_to("report.md")
    r = _run(tmp_path, out)
    assert r.returncode == 0, r.stdout + r.stderr
    cap = tmp_path / CAP
    archive = cap / f"{NAME}.tar.zst"
    assert archive.is_file()
    m = _members(archive)
    assert "suite_smoke_tau2/report.md" in m
    assert "suite_smoke_tau2_proj/.capevolve/run_suite/final.json" in m
    assert "suite_smoke_tau2_proj/.capevolve/run_suite/candidates/cand_0001/policy.md" in m
    # members.sha256 is taken on the source and matches what the archive holds, byte for byte
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    _tar(archive, "-x", cwd=unpacked)
    lines = (cap / "members.sha256").read_text().splitlines()
    hashes = {ln.split("  ", 1)[1]: ln.split("  ", 1)[0] for ln in lines}
    files = sorted(str(p.relative_to(unpacked)) for p in unpacked.rglob("*") if p.is_file() and not p.is_symlink())
    assert sorted(hashes) == files
    for rel, h in hashes.items():
        assert hashlib.sha256((unpacked / rel).read_bytes()).hexdigest() == h, rel
    assert "suite_smoke_tau2/link -> report.md" in (cap / "symlinks.txt").read_text()
    b = json.loads((cap / "backup.json").read_text())
    assert b["schema"] == "ci-capture v1" and "FULL_BACKUP" in b["what"]
    assert b["archive"] == f"{NAME}.tar.zst" and b["capture_dir"] == str(cap)
    assert b["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert b["bytes"] == archive.stat().st_size and b["runner"] == "test-runner"
    assert b["member_count"] == len(files) and b["run_attempt"] == 1
    assert (b["tier"], b["bench"], b["results_repo"], b["triggering_actor"]) == ("smoke", "tau2", "tau", "bcarmeli")
    assert json.loads((out / "backup.json").read_text()) == b
    assert not list((tmp_path / "capture").glob("*.partial"))


def test_a_capture_dir_is_never_overwritten_and_attempts_get_their_own(tmp_path):
    out = _work(tmp_path)
    assert _run(tmp_path, out).returncode == 0
    first = (tmp_path / CAP / "backup.json").read_bytes()
    r = _run(tmp_path, out)
    assert r.returncode == 0 and "never overwritten" in r.stdout
    assert (tmp_path / CAP / "backup.json").read_bytes() == first
    r = _run(tmp_path, out, GITHUB_RUN_ATTEMPT="2")
    assert r.returncode == 0, r.stdout + r.stderr
    b = json.loads((tmp_path / "capture" / f"{NAME}.a2" / "backup.json").read_text())
    assert b["run_attempt"] == 2


def test_the_user_name_is_recorded_not_used_in_a_path(tmp_path):
    r = _run(tmp_path, _work(tmp_path), BACKUP_USER="../../etc")
    assert r.returncode == 0, r.stdout + r.stderr
    assert [p.name for p in (tmp_path / "capture").iterdir()] == [NAME]
    assert json.loads((tmp_path / CAP / "backup.json").read_text())["triggering_actor"] == "../../etc"
    assert not (tmp_path / "etc").exists()


def test_the_sealed_dir_is_kept_too(tmp_path):
    out = _work(tmp_path)
    sealed = tmp_path / ".work" / "suite_smoke_tau2_proj.sealed" / "run_suite"
    (sealed / "rollouts" / "confirm").mkdir(parents=True)
    (sealed / "splits_full.json").write_text("{}")
    r = _run(tmp_path, out)
    assert r.returncode == 0, r.stdout + r.stderr
    m = _members(next((tmp_path / CAP).glob(f"{NAME}.tar.*")))
    assert "suite_smoke_tau2_proj.sealed/run_suite/splits_full.json" in m
    assert "suite_smoke_tau2_proj.sealed/run_suite/splits_full.json" in (tmp_path / CAP / "members.sha256").read_text()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads every file")
def test_an_unreadable_file_is_listed_and_the_rest_kept(tmp_path):
    out = _work(tmp_path)
    locked = out / "root_owned.log"
    locked.write_text("x\n")
    locked.chmod(0)
    try:
        r = _run(tmp_path, out)
    finally:
        locked.chmod(0o644)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "not readable by the job" in r.stdout
    cap = tmp_path / CAP
    assert (cap / "unreadable.txt").read_text().split() == ["suite_smoke_tau2/root_owned.log"]
    assert json.loads((cap / "backup.json").read_text())["unreadable"] == ["suite_smoke_tau2/root_owned.log"]
    m = _members(next(cap.glob(f"{NAME}.tar.*")))
    assert "suite_smoke_tau2/report.md" in m and "suite_smoke_tau2/root_owned.log" not in m
    assert "root_owned.log" not in (cap / "members.sha256").read_text()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads every dir")
@pytest.mark.parametrize("mode", [0o000, 0o600], ids=["no-read", "read-no-enter"])
def test_an_unreadable_dir_is_listed_and_the_rest_kept(tmp_path, mode):
    out = _work(tmp_path)
    locked = out / "container_out"
    locked.mkdir()
    (locked / "f.txt").write_text("y\n")
    locked.chmod(mode)
    try:
        r = _run(tmp_path, out)
    finally:
        locked.chmod(0o755)
    assert r.returncode == 0, r.stdout + r.stderr
    cap = tmp_path / CAP
    assert cap.is_dir(), r.stdout + r.stderr
    assert (cap / "unreadable.txt").read_text().split() == ["suite_smoke_tau2/container_out"]
    assert json.loads((cap / "backup.json").read_text())["unreadable"] == ["suite_smoke_tau2/container_out"]
    assert "suite_smoke_tau2/report.md" in _members(next(cap.glob(f"{NAME}.tar.*")))
    hashed = (cap / "members.sha256").read_text()
    assert "suite_smoke_tau2/report.md" in hashed and "container_out" not in hashed


def test_without_sections_json_the_bench_name_is_the_results_repo(tmp_path):
    env = {"BACKUP_REPO": "", "SECTIONS_URL": f"file://{tmp_path}/missing.json"}
    r = _run(tmp_path, _work(tmp_path), **env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "recording results repo 'tau2'" in r.stdout
    assert json.loads((tmp_path / CAP / "backup.json").read_text())["results_repo"] == "tau2"


def test_results_repo_comes_from_sections_json(tmp_path):
    (tmp_path / "sections.json").write_text(json.dumps([{"repo": "tau", "title": "tau2", "benches": ["tau2"]}]))
    r = _run(tmp_path, _work(tmp_path), BACKUP_REPO="", SECTIONS_URL=f"file://{tmp_path}/sections.json")
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads((tmp_path / CAP / "backup.json").read_text())["results_repo"] == "tau"


def test_too_little_disk_skips_with_a_warning(tmp_path):
    out = _work(tmp_path)
    r = _run(tmp_path, out, BACKUP_MIN_FREE_GB="100000000")
    assert r.returncode == 0
    assert "::warning::not keeping" in r.stdout
    assert not list((tmp_path / "capture").rglob("*.tar.*")) and not (out / "backup.json").exists()


def test_nothing_to_archive_is_not_an_error(tmp_path):
    r = _run(tmp_path, tmp_path / "nowhere")
    assert r.returncode == 0 and "nothing to keep" in r.stdout


@pytest.mark.skipif(any(Path(d, "zstd").exists() for d in ("/usr/bin", "/bin")),
                    reason="zstd is in the system path here, so it can't be hidden")
def test_without_zstd_it_falls_back_to_gzip(tmp_path):
    r = _run(tmp_path, _work(tmp_path), PATH="/usr/bin:/bin")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "zstd is not installed" in r.stdout
    archive = tmp_path / CAP / f"{NAME}.tar.gz"
    assert "suite_smoke_tau2/report.md" in _members(archive)


def test_the_run_folder_says_where_the_archive_is(tmp_path):
    sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location("run_folder", LIB / "run_folder.py")
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)
    out = _work(tmp_path)
    (out / "backup.json").write_text(json.dumps({"archive": f"{NAME}.tar.zst", "runner": "r1",
                                                 "capture_dir": f"/home/ci/capevolve-ci-capture/{NAME}",
                                                 "bytes": 5_000_000}))
    d = rf.build(out, tmp_path / "folder", None, None, None, None, "tau", False)
    assert (d / "backup.json").is_file()
    readme = (d / "README.md").read_text()
    assert f"kept on runner `r1` in `/home/ci/capevolve-ci-capture/{NAME}/`" in readme
    assert "docs/FULL_BACKUP.md" in readme


def test_workflow_keeps_the_raw_data_best_effort_before_publishing():
    src = WORKFLOW.read_text()
    names = re.findall(r"^      - name: (.+)$", src, re.M)
    assert names.index("Write run metadata") < names.index("Keep the raw run data for the full backup") \
        < names.index("Publish results to skillberry-runs")
    step = src[src.index("      - name: Keep the raw run data for the full backup"):]
    step = step[:step.index("\n      - name:", 10)]
    assert "continue-on-error: true" in step and "timeout-minutes:" in step
    # opt-in: runs only on a dispatch that names a staging area (empty by default, never on PR labels)
    assert re.search(r"^        if: always\(\) && github\.event_name == 'workflow_dispatch' "
                     r"&& inputs\.raw_data_location != ''$", step, re.M)
    inp = src[src.index("      raw_data_location:"):]
    inp = inp[:inp.index("\n  pull_request:")]
    assert "type: string" in inp and 'default: ""' in inp
    run = step[step.index("run: |"):]
    assert "BACKUP_USER: ${{ github.triggering_actor }}" in step
    assert "RAW_DATA_LOCATION: ${{ inputs.raw_data_location }}" in step
    assert "RAW_DATA_RCLONE_CONFIG: ${{ secrets.RAW_DATA_RCLONE_CONFIG }}" in step
    # rclone is installed (pinned) before the script, and its install never fails the step
    assert run.index("bash ci/benchmarks/lib/install_rclone.sh || true") < run.index('export PATH="$HOME/.local/bin:$PATH"') \
        < run.index("bash ci/benchmarks/lib/backup_run.sh")
    for expr in ("${{ github.triggering_actor }}", "inputs.raw_data_location", "secrets."):
        assert expr not in run, f"{expr} must reach the script through the environment, not the shell source"


# ---- staging --------------------------------------------------------------------------------------

needs_rclone = pytest.mark.skipif(not shutil.which("rclone"), reason="needs rclone")
STG_CONF = "[stg]\ntype = local\n"


def _stage(tmp_path, out, loc, conf=STG_CONF, **env):
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return _run(tmp_path, out, RAW_DATA_LOCATION=loc, RAW_DATA_RCLONE_CONFIG=conf, TMPDIR=str(tmpdir),
                RCLONE_CONFIG=str(tmp_path / "no-such-rclone.conf"), **env)


@needs_rclone
def test_staging_uploads_checks_then_frees_the_runner(tmp_path):
    out = _work(tmp_path)
    r = _stage(tmp_path, out, f"stg:{tmp_path}/staging/")
    assert r.returncode == 0, r.stdout + r.stderr
    staged = tmp_path / "staging" / NAME
    files = sorted(p.name for p in staged.iterdir())
    assert files == sorted([next(staged.glob(f"{NAME}.tar.*")).name, "backup.json", "members.sha256",
                            "symlinks.txt", "unreadable.txt"])
    b = json.loads((staged / "backup.json").read_text())
    assert b["sha256"] == hashlib.sha256(next(staged.glob(f"{NAME}.tar.*")).read_bytes()).hexdigest()
    assert not (tmp_path / CAP).exists(), "the runner's copy is removed once the upload is checked"
    o = json.loads((out / "backup.json").read_text())
    assert o["staged"] == f"stg:{tmp_path}/staging/{NAME}/" and o["kept_on_runner"] is False
    assert "staging_error" not in o and o["sha256"] == b["sha256"]
    assert not list((tmp_path / "tmpdir").iterdir()), "the rclone config temp file is removed"
    assert "[stg]" not in r.stdout + r.stderr


@needs_rclone
@pytest.mark.parametrize("loc,why", [("nope:x", "remote 'nope' is not defined"),
                                     ("stg:", "not of the form"), ("/a/local/path", "not of the form")])
def test_a_failed_staging_keeps_the_capture_on_the_runner(tmp_path, loc, why):
    out = _work(tmp_path)
    r = _stage(tmp_path, out, loc)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "::warning::staging the raw run data" in r.stdout and why in r.stdout
    assert (tmp_path / CAP / "backup.json").is_file()
    o = json.loads((out / "backup.json").read_text())
    assert o["staged"] is None and o["kept_on_runner"] is True and why in o["staging_error"]
    assert not list((tmp_path / "tmpdir").iterdir())


INSTALL = LIB / "install_rclone.sh"


def test_install_rclone_pins_a_version_and_its_hashes():
    src = INSTALL.read_text()
    assert re.search(r'^RCLONE_VERSION="\d+\.\d+\.\d+"$', src, re.M)
    hashes = re.findall(r'^  \[(amd64|arm64)\]="([0-9a-f]{64})"$', src, re.M)
    assert sorted(a for a, _ in hashes) == ["amd64", "arm64"]


def _fake_release(tmp_path, payload: bytes):
    import zipfile
    v = re.search(r'^RCLONE_VERSION="(.+)"$', INSTALL.read_text(), re.M).group(1)
    arch = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}[os.uname().machine]
    d = tmp_path / "dl" / f"v{v}"
    d.mkdir(parents=True)
    with zipfile.ZipFile(d / f"rclone-v{v}-linux-{arch}.zip", "w") as z:
        z.writestr(f"rclone-v{v}-linux-{arch}/rclone", payload)
    return v


@pytest.mark.skipif(os.uname().sysname != "Linux", reason="pinned builds are Linux")
def test_install_rclone_refuses_a_download_with_the_wrong_hash(tmp_path):
    _fake_release(tmp_path, b"#!/bin/sh\necho tampered\n")
    r = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "RCLONE_PREFIX": str(tmp_path / "prefix"),
                            "RCLONE_BASE_URL": f"file://{tmp_path}/dl", "PY": sys.executable})
    assert r.returncode == 1 and "expected" in r.stdout and "not installed" in r.stdout
    assert not (tmp_path / "prefix" / "bin" / "rclone").exists()


def test_install_rclone_is_a_no_op_when_the_version_is_there(tmp_path):
    v = re.search(r'^RCLONE_VERSION="(.+)"$', INSTALL.read_text(), re.M).group(1)
    b = tmp_path / "prefix" / "bin"
    b.mkdir(parents=True)
    (b / "rclone").write_text(f"#!/bin/sh\necho 'rclone v{v}'\n")
    (b / "rclone").chmod(0o755)
    r = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "RCLONE_PREFIX": str(tmp_path / "prefix"),
                            "RCLONE_BASE_URL": "file:///nonexistent", "PY": sys.executable})
    assert r.returncode == 0 and "already at" in r.stdout


def test_the_run_folder_says_where_the_staged_archive_is(tmp_path):
    sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location("run_folder", LIB / "run_folder.py")
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)
    out = _work(tmp_path)
    (out / "backup.json").write_text(json.dumps({"archive": f"{NAME}.tar.zst", "runner": "r1",
                                                 "capture_dir": f"/home/ci/capevolve-ci-capture/{NAME}",
                                                 "bytes": 5_000_000, "staged": f"stg:raw/{NAME}/",
                                                 "kept_on_runner": False}))
    readme = (rf.build(out, tmp_path / "folder", None, None, None, None, "tau", False) / "README.md").read_text()
    assert f"staged at `stg:raw/{NAME}/`" in readme and "kept on runner" not in readme
