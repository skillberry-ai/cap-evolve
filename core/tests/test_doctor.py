"""``cap-evolve doctor`` — per-check pass/fail paths, exit codes, and the
no-secret-leak guarantee.

The security test (``test_secret_value_never_printed``) is non-negotiable: it plants a
recognizable fake token in every credential env var the doctor knows about and asserts
the literal value appears NOWHERE in the human output, the JSON output, or the raw
report — not even as a prefix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cap_evolve import doctor
from cap_evolve.cli import main as cli_main
from cap_evolve.doctor import FAIL, PASS, WARN, format_report, run_doctor


def _by_name(rep, name):
    return next(c for c in rep.checks if c.name == name)


# ---------------------------------------------------------------------------
# whole-report shape + exit codes
# ---------------------------------------------------------------------------

def test_healthy_report_is_ok_and_exits_zero(tmp_path, capsys):
    rep = run_doctor(tmp_path)
    names = [c.name for c in rep.checks]
    assert names == ["python", "core", "cli-path", "git", "skills",
                     "optimizer", "credentials", "run-dir", "project"]
    assert all(c.status in (PASS, WARN, FAIL) for c in rep.checks)
    # python/core/run-dir must be green in the test env itself
    for n in ("python", "core", "run-dir"):
        assert _by_name(rep, n).status == PASS, _by_name(rep, n)
    assert rep.ok is (not any(c.status == FAIL for c in rep.checks))

    code = cli_main(["doctor", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == (0 if rep.ok else 1)
    assert "cap-evolve doctor" in out


def test_warnings_alone_do_not_fail(tmp_path):
    rep = doctor.DoctorReport(checks=[doctor.Check("a", PASS), doctor.Check("b", WARN)])
    assert rep.ok is True
    rep.checks.append(doctor.Check("c", FAIL))
    assert rep.ok is False


def test_hard_failure_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "CHECKS", (lambda cwd: doctor.Check("git", FAIL, "no git", "install git"),))
    assert doctor._main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] git" in out and "install git" in out
    assert "FAIL: 1 failure(s), 0 warning(s)" in out


def test_json_output_is_machine_readable(tmp_path, capsys):
    code = doctor._main([str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is (code == 0)
    assert {c["name"] for c in data["checks"]} >= {"python", "core", "git", "credentials"}


def test_a_raising_check_fails_loudly_without_hiding_others(tmp_path):
    def boom(cwd):
        raise RuntimeError("kaboom")

    saved = doctor.CHECKS
    try:
        doctor.CHECKS = (boom, doctor._check_python)
        r = run_doctor(tmp_path)
    finally:
        doctor.CHECKS = saved
    assert [c.status for c in r.checks] == [FAIL, PASS]
    assert "kaboom" in r.checks[0].detail
    assert r.ok is False


# ---------------------------------------------------------------------------
# individual checks — pass AND fail paths
# ---------------------------------------------------------------------------

def test_python_pass_and_fail(monkeypatch, tmp_path):
    assert doctor._check_python(tmp_path).status == PASS      # we run on 3.10+

    class V(tuple):
        major, minor, micro = 3, 9, 0

    monkeypatch.setattr(doctor.sys, "version_info", V((3, 9, 0)))
    c = doctor._check_python(tmp_path)
    assert c.status == FAIL and "3.10+" in c.fix


def test_core_pass(tmp_path):
    c = doctor._check_core(tmp_path)
    assert c.status == PASS and "cap_evolve" in c.detail


def test_core_warns_on_wrong_venv(monkeypatch, tmp_path):
    other = tmp_path / "other-venv"
    (other / "bin").mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(other))
    c = doctor._check_core(tmp_path)
    assert c.status == WARN and "does not own" in c.detail and "re-activate" in c.fix


def test_cli_path_pass_and_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    c = doctor._check_cli_path(tmp_path)
    assert c.status == WARN and "pip install ./core" in c.fix

    exe = Path(doctor.sys.executable).parent / "cap-evolve"
    monkeypatch.setattr(doctor.shutil, "which", lambda _: str(exe))
    assert doctor._check_cli_path(tmp_path).status == PASS


def test_cli_path_detects_shadowing_install(monkeypatch, tmp_path):
    shadow = tmp_path / "elsewhere" / "cap-evolve"
    shadow.parent.mkdir(parents=True)
    shadow.write_text("#!/bin/sh\n")
    real = Path(doctor.sys.executable).parent / "cap-evolve"
    if not real.exists():          # ensure the "expected" side exists so the branch runs
        pytest.skip("no cap-evolve alongside this interpreter")
    monkeypatch.setattr(doctor.shutil, "which", lambda _: str(shadow))
    c = doctor._check_cli_path(tmp_path)
    assert c.status == WARN and "shadowing" in c.fix


def test_git_pass_and_fail(monkeypatch, tmp_path):
    assert doctor._check_git(tmp_path).status == PASS
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    c = doctor._check_git(tmp_path)
    assert c.status == FAIL and "install git" in c.fix


def test_skills_missing_dir_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "_skills_dir", lambda: None)
    c = doctor._check_skills(tmp_path)
    assert c.status == FAIL and "install.sh" in c.fix


def test_skills_missing_manifest_fails(monkeypatch, tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    monkeypatch.setattr(doctor, "_skills_dir", lambda: d)
    c = doctor._check_skills(tmp_path)
    assert c.status == FAIL and "build_manifest" in c.fix


def test_skills_stale_manifest_fails(monkeypatch, tmp_path):
    d = tmp_path / "skills"
    (d / "_registry").mkdir(parents=True)
    (d / "_registry" / "manifest.json").write_text(json.dumps(
        {"skills": {"ghost": {"path": "phases/ghost", "entry": "scripts/run.py"}}}))
    monkeypatch.setattr(doctor, "_skills_dir", lambda: d)
    c = doctor._check_skills(tmp_path)
    assert c.status == FAIL and "ghost" in c.detail and "stale manifest" in c.fix


def test_skills_pass_on_repo_source_layout(monkeypatch, tmp_path):
    d = tmp_path / "skills"
    (d / "_registry").mkdir(parents=True)
    (d / "optimizers").mkdir()
    (d / "optimizers" / "registry.yaml").write_text("mock:\n  command_template: \"x\"\n")
    (d / "phases" / "baseline" / "scripts").mkdir(parents=True)
    (d / "phases" / "baseline" / "scripts" / "run.py").write_text("")
    (d / "_registry" / "manifest.json").write_text(json.dumps(
        {"skills": {"baseline": {"path": "phases/baseline", "entry": "scripts/run.py"}}}))
    monkeypatch.setattr(doctor, "_skills_dir", lambda: d)
    c = doctor._check_skills(tmp_path)
    assert c.status == PASS and "repo source layout" in c.detail


def test_skills_warns_on_best_guess_host_dir(monkeypatch, tmp_path):
    """install.sh:38-40 admits several host dirs are guesses — flag them explicitly."""
    d = tmp_path / ".weirdhost" / "skills"
    (d / "_registry").mkdir(parents=True)
    (d / "_registry" / "manifest.json").write_text(json.dumps({"skills": {}}))
    monkeypatch.setattr(doctor, "_skills_dir", lambda: d)
    c = doctor._check_skills(tmp_path)
    assert c.status == WARN and "best-guess" in c.fix


def test_optimizer_pass_and_none_available(monkeypatch, tmp_path):
    reg = {"mock": {"command_template": "python3 x.py"},
           "nope": {"command_template": "definitely-not-installed-xyz -p"}}
    monkeypatch.setattr(doctor, "_optimizer_registry", lambda: reg)
    c = doctor._check_optimizer(tmp_path)
    assert c.status == PASS and "mock" in c.detail and "nope" in c.detail

    monkeypatch.setattr(doctor, "_optimizer_registry",
                        lambda: {"nope": {"command_template": "definitely-not-installed-xyz"}})
    c = doctor._check_optimizer(tmp_path)
    assert c.status == FAIL and "mock" in c.fix

    monkeypatch.setattr(doctor, "_optimizer_registry", lambda: {})
    assert doctor._check_optimizer(tmp_path).status == WARN


def test_credentials_absent_warns(monkeypatch, tmp_path):
    for _, keys in doctor._RUNNER_ENV_GROUPS:
        for k in keys:
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(doctor, "_optimizer_registry", lambda: {})
    c = doctor._check_credentials(tmp_path)
    assert c.status == WARN and c.present == [] and "INSTALL.md" in c.fix


def test_credentials_present_passes_with_names_only(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key-000000000000")
    monkeypatch.setattr(doctor, "_optimizer_registry", lambda: {})
    c = doctor._check_credentials(tmp_path)
    assert c.status == PASS
    assert "OPENAI_API_KEY" in c.present
    assert "sk-not-a-real-key-000000000000" not in json.dumps(c.to_dict())


def test_credentials_env_names_are_deduped(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "_optimizer_registry",
                        lambda: {"a": {"env_keys": "OPENAI_API_KEY,ANTHROPIC_API_KEY"}})
    c = doctor._check_credentials(tmp_path)
    names = c.present + c.absent
    assert len(names) == len(set(names)), names


def test_run_dir_pass_and_unwritable(tmp_path):
    assert doctor._check_run_dir(tmp_path).status == PASS
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        c = doctor._check_run_dir(ro)
        assert c.status == FAIL and "not writable" in c.detail
    finally:
        ro.chmod(0o700)


def test_project_skipped_outside_a_project(tmp_path):
    c = doctor._check_project(tmp_path)
    assert c.status == PASS and "not inside a cap-evolve project" in c.detail


def test_project_fails_on_stub_adapter(tmp_path):
    adapters = tmp_path / ".capevolve" / "project" / "adapters"
    adapters.mkdir(parents=True)
    (adapters / "adapter.py").write_text(
        "from cap_evolve.adapter import CapabilityAdapter\n"
        "class Adapter(CapabilityAdapter):\n    pass\n")
    c = doctor._check_project(tmp_path)
    assert c.status == FAIL and "ADAPTER_CONTRACT" in c.fix


def test_project_passes_on_a_working_adapter(tmp_path):
    adapters = tmp_path / ".capevolve" / "project" / "adapters"
    adapters.mkdir(parents=True)
    (adapters / "adapter.py").write_text(
        "from pathlib import Path\n"
        "from cap_evolve.adapter import CapabilityAdapter\n"
        "from cap_evolve.types import Rollout, Score, Task\n"
        "class Adapter(CapabilityAdapter):\n"
        "    def tasks(self, split='all'):\n"
        "        return [Task(id='t1', input='p')]\n"
        "    def run_target(self, task, candidate_dir, seed=0):\n"
        "        return Rollout(task_id=task.id, output='o')\n"
        "    def score(self, task, rollout):\n"
        "        return Score(task_id=task.id, reward=1.0)\n"
        "    def materialize(self, dest):\n"
        "        Path(dest).mkdir(parents=True, exist_ok=True)\n")
    c = doctor._check_project(tmp_path)
    assert c.status == PASS and "green" in c.detail


# ---------------------------------------------------------------------------
# SECURITY — the value of a credential must never be emitted anywhere
# ---------------------------------------------------------------------------

_FAKE = "sk-ANT-DOCTOR-LEAK-CANARY-abcdef0123456789"


def test_secret_value_never_printed(monkeypatch, tmp_path, capsys):
    """Plant a canary token in EVERY known credential var; assert it never surfaces.

    Also asserts no PREFIX of the canary leaks (a partially-revealed token is a leak),
    across all three surfaces: the human report, the --json report, and the raw dataclass.
    """
    names = [k for _, keys in doctor._RUNNER_ENV_GROUPS for k in keys]
    names += ["CAPEVOLVE_OPTIMIZER_CMD", "BOB_API_KEY", "GITHUB_TOKEN", "KIMI_API_KEY"]
    for k in names:
        monkeypatch.setenv(k, _FAKE)

    rep = run_doctor(tmp_path)
    human = format_report(rep)
    doctor._main([str(tmp_path), "--json"])
    json_out = capsys.readouterr().out
    raw = json.dumps(rep.to_dict())

    for surface in (human, json_out, raw):
        assert _FAKE not in surface
        # no partial reveal either — any 8+ char prefix of the secret body is a leak
        body = _FAKE.split("-", 2)[2]          # "DOCTOR-LEAK-CANARY-abcdef0123456789"
        for n in range(8, len(body) + 1):
            assert body[:n] not in surface, f"leaked {n}-char prefix in {surface[:200]!r}"

    # ...while still reporting PRESENCE, which is the point of the check.
    cred = _by_name(rep, "credentials")
    assert cred.status == PASS
    assert "OPENAI_API_KEY" in cred.present
    assert "OPENAI_API_KEY: set (hidden)" in human


def test_report_passes_through_redaction(tmp_path):
    """Defense in depth: even a check that somehow embeds a secret-shaped value in its
    detail is scrubbed by ``dashboard.redact`` before printing."""
    rep = doctor.DoctorReport(checks=[
        doctor.Check("rogue", WARN, f"OPENAI_API_KEY={_FAKE}", "")])
    text = format_report(rep)
    assert _FAKE not in text and "redacted" in text
