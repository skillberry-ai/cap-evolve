"""Optimizer isolation (#875): config, mode choice, command wrapping, and a real namespace run."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from cap_evolve import isolation as iso

NS_OK, NS_WHY = iso.namespace_available()
needs_ns = pytest.mark.skipif(not NS_OK, reason=f"no unprivileged user namespaces: {NS_WHY}")


def test_from_spec_off_by_default_and_validates():
    assert iso.from_spec({}) is None
    assert iso.from_spec({"optimizer_isolation": "off"}) is None
    assert iso.from_spec({"optimizer_isolation": False}) is None            # bare `off` in YAML
    assert iso.from_spec({"optimizer_isolation": True, "optimizer_hide": ["/a"]})["mode"] == "auto"
    with pytest.raises(iso.IsolationError):
        iso.from_spec({"optimizer_isolation": "bogus", "optimizer_hide": ["/x"]})
    with pytest.raises(iso.IsolationError, match="lists no path"):
        iso.from_spec({"optimizer_isolation": "auto"})
    cfg = iso.from_spec({"optimizer_isolation": "AUTO", "optimizer_hide": "/a, ~/b",
                         "optimizer_expose": ["/a/pub"]})
    assert cfg["mode"] == "auto" and cfg["hide"][0] == "/a" and not cfg["hide"][1].startswith("~")
    assert cfg["expose"] == ["/a/pub"]


def test_export_load_round_trip():
    env: dict = {}
    iso.export({"mode": "namespace", "hide": ["/a"], "expose": []}, env)
    assert iso.load(env)["hide"] == ["/a"]
    iso.export(None, env)
    assert iso.load(env) is None


def test_choose_mode_prefers_sandbox_for_claude_and_fails_closed():
    cfg = {"mode": "auto", "hide": ["/a"]}
    with mock.patch.object(iso, "sandbox_available", return_value=(True, "ok")):
        assert iso.choose_mode(cfg, "claude-code") == "sandbox"
    with mock.patch.object(iso, "sandbox_available", return_value=(False, "no bwrap")), \
         mock.patch.object(iso, "namespace_available", return_value=(True, "ok")):
        assert iso.choose_mode(cfg, "claude-code") == "namespace"
        assert iso.choose_mode(cfg, "codex") == "namespace"
        with pytest.raises(iso.IsolationError, match="no bwrap"):
            iso.choose_mode({"mode": "sandbox", "hide": ["/a"]}, "claude-code")
    with pytest.raises(iso.IsolationError, match="claude-code only"):
        iso.choose_mode({"mode": "sandbox", "hide": ["/a"]}, "codex")
    with mock.patch.object(iso, "namespace_available", return_value=(False, "disabled")):
        with pytest.raises(iso.IsolationError, match="disabled"):
            iso.choose_mode({"mode": "namespace", "hide": ["/a"]}, "codex")


def test_claude_settings_cover_read_tools_and_sandbox():
    s = iso.claude_settings({"hide": ["/data/gold"]}, sandbox=True)
    assert "Read(//data/gold/**)" in s["permissions"]["deny"]
    assert s["sandbox"]["filesystem"]["denyRead"] == ["/data/gold"]
    assert s["sandbox"]["allowUnsandboxedCommands"] is False and s["sandbox"]["failIfUnavailable"] is True
    assert "sandbox" not in iso.claude_settings({"hide": ["/data/gold"]}, sandbox=False)


def test_wrap_namespace_prefixes_wrapper_and_adds_inline_settings(tmp_path):
    cfg = {"mode": "namespace", "hide": ["/data/gold"], "expose": []}
    with mock.patch.object(iso, "namespace_available", return_value=(True, "ok")):
        argv, env, mode = iso.wrap(["claude", "-p", "x"], cfg, workdir=str(tmp_path), optimizer="claude-code")
    assert mode == "namespace" and argv[:2] == ["bash", str(iso.WRAPPER)] and argv[2:5] == ["claude", "-p", "x"]
    assert json.loads(argv[argv.index("--settings") + 1])["permissions"]["deny"]
    assert env["CE_ISO_HIDE"] == "/data/gold" and env["CE_ISO_WORK"] == str(tmp_path.resolve())


@needs_ns
def test_namespace_wrapper_hides_files_and_keeps_work_writable(tmp_path):
    gold, pub, work = tmp_path / "gold", tmp_path / "gold" / "pub", tmp_path / "work"
    pub.mkdir(parents=True)
    work.mkdir()
    (gold / "answer.json").write_text("SECRET")
    (pub / "doc.txt").write_text("DOC")
    secret_file = tmp_path / "dotenv"
    secret_file.write_text("KEY")
    cfg = {"mode": "namespace", "hide": [str(gold), str(secret_file)], "expose": [str(pub)]}
    probe = (f"cat {gold}/answer.json 2>/dev/null; echo; cat {pub}/doc.txt; echo; cat {secret_file}; echo; "
             f"touch {work}/w && echo WORK_OK; umount {gold} 2>/dev/null && echo UNMOUNTED; true")
    argv, env, _ = iso.wrap(["sh", "-c", probe], cfg, workdir=str(work), optimizer="generic")
    out = subprocess.run(argv, capture_output=True, text=True, env={**os.environ, **env}, timeout=60).stdout
    assert "SECRET" not in out and "KEY" not in out          # hidden dir and hidden file are empty
    assert "DOC" in out and "WORK_OK" in out                 # exposed path readable, workdir writable
    assert "UNMOUNTED" not in out                            # the cover cannot be undone
    assert (work / "w").exists() and (gold / "answer.json").read_text() == "SECRET"   # host untouched


@needs_ns
def test_self_check_passes_and_reports_a_visible_path(tmp_path):
    gold, work = tmp_path / "gold", tmp_path / "work"
    gold.mkdir()
    work.mkdir()
    cfg = {"mode": "namespace", "hide": [str(gold)], "expose": []}
    assert iso.self_check(cfg, workdir=str(work), optimizer="codex") == []
    assert not list(gold.iterdir())                          # probe marker removed again


@needs_ns
def test_run_optimizer_refuses_or_wraps(tmp_path, monkeypatch):
    """run-optimizer applies the env config to a real (offline mock) optimizer call."""
    work = tmp_path / "work"
    work.mkdir()
    prompt = tmp_path / "INSTRUCTIONS.md"
    prompt.write_text("noop")
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "answer.json").write_text("SECRET")
    script = Path(__file__).resolve().parents[2] / "skills/optimizers/run-optimizer/scripts/run.py"
    env = {**os.environ, iso.ENV: json.dumps({"mode": "namespace", "hide": [str(gold)], "expose": []})}
    r = subprocess.run([sys.executable, str(script), "--name", "mock", "--workdir", str(work),
                        "--prompt", str(prompt)], capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]).get("isolation") == "namespace"
    bad = {**env, iso.ENV: json.dumps({"mode": "sandbox", "hide": [str(gold)], "expose": []})}
    r = subprocess.run([sys.executable, str(script), "--name", "mock", "--workdir", str(work),
                        "--prompt", str(prompt)], capture_output=True, text=True, env=bad, timeout=120)
    assert r.returncode == 2 and "claude-code only" in r.stdout
