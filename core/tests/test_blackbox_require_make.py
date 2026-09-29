"""`require_make()` -- the preflight fix for issue #573.

On a runner without `make`, ``_install_service``'s ``make install-requirements || pip install
-e .`` used to fall through to plain pip, which cannot resolve the store's local-version torch
pin (served only via ``[tool.uv.sources]``) -- so a missing build tool surfaced as a confusing
unresolvable-torch-pin error, with the real cause (``make: command not found``) buried mid-output.

These tests drive the REAL ``require_make()`` (and a real subprocess with `make` stripped from
PATH, for the end-to-end repro) rather than grepping the source, since the defect is exactly in
what gets reported and in what actually installs -- neither of which a source check sees.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

BLACKBOX_ENV = (Path(__file__).resolve().parents[2]
           / "skills/interventions/llm-proxies/blackbox/scripts/blackbox_env.py")


@pytest.fixture
def blackbox_env():
    """Fresh module per test: require_make() has no state, but tests monkeypatch sys.platform
    and shutil.which, and a shared module instance would leak that between tests otherwise."""
    spec = importlib.util.spec_from_file_location("blackbox_env_under_test_make", BLACKBOX_ENV)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Idempotence: make present -> nothing runs, nothing installs
# ---------------------------------------------------------------------------

def test_a_present_make_installs_nothing(blackbox_env, monkeypatch):
    monkeypatch.setattr(blackbox_env.shutil, "which",
                        lambda name: "/usr/bin/make" if name == "make" else None)
    calls = []
    monkeypatch.setattr(blackbox_env, "_run", lambda *a, **kw: calls.append(a) or (0, ""))

    blackbox_env.require_make()

    assert calls == [], "a present `make` must trigger no install command at all"


def test_repeated_calls_with_make_present_stay_a_no_op(blackbox_env, monkeypatch):
    """Idempotent across the two real call sites: once per provision(), once per service start."""
    monkeypatch.setattr(blackbox_env.shutil, "which",
                        lambda name: "/usr/bin/make" if name == "make" else None)
    calls = []
    monkeypatch.setattr(blackbox_env, "_run", lambda *a, **kw: calls.append(a) or (0, ""))

    for _ in range(3):
        blackbox_env.require_make()

    assert calls == []


# ---------------------------------------------------------------------------
# Missing make on Linux: auto-installs, by name, never mentioning torch
# ---------------------------------------------------------------------------

def test_missing_make_on_linux_auto_installs_via_the_first_present_manager(blackbox_env,
                                                                           monkeypatch):
    monkeypatch.setattr(blackbox_env.sys, "platform", "linux")
    present = {"make": None, "apt-get": None, "dnf": "/usr/bin/dnf", "yum": None}

    def which(name):
        return present.get(name)

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        present["make"] = "/usr/bin/make"      # the install "succeeded"
        return 0, ""

    monkeypatch.setattr(blackbox_env.shutil, "which", which)
    monkeypatch.setattr(blackbox_env, "_run", fake_run)

    blackbox_env.require_make()                # must not raise

    assert calls == [["sudo", "dnf", "install", "-y", "make"]], calls


def test_missing_make_on_linux_with_no_known_manager_names_make_not_torch(blackbox_env,
                                                                          monkeypatch):
    monkeypatch.setattr(blackbox_env.sys, "platform", "linux")
    monkeypatch.setattr(blackbox_env.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.require_make()

    msg = str(err.value)
    assert "make: command not found" in msg
    assert "torch" not in msg.lower()


def test_a_failed_linux_install_names_make_not_found_as_the_cause(blackbox_env, monkeypatch):
    monkeypatch.setattr(blackbox_env.sys, "platform", "linux")
    monkeypatch.setattr(blackbox_env.shutil, "which",
                        lambda name: "/usr/bin/apt-get" if name == "apt-get" else None)
    monkeypatch.setattr(blackbox_env, "_run", lambda *a, **kw: (1, "E: Unable to locate package"))

    with pytest.raises(RuntimeError) as err:
        blackbox_env.require_make()

    msg = str(err.value)
    assert "make: command not found" in msg
    assert "torch" not in msg.lower()


# ---------------------------------------------------------------------------
# Missing make on macOS: never brew, never auto-run xcode-select, correct guidance
# ---------------------------------------------------------------------------

def test_missing_make_on_macos_points_to_xcode_clt_not_brew(blackbox_env, monkeypatch):
    monkeypatch.setattr(blackbox_env.sys, "platform", "darwin")
    monkeypatch.setattr(blackbox_env.shutil, "which", lambda name: None)
    calls = []
    monkeypatch.setattr(blackbox_env, "_run", lambda *a, **kw: calls.append(a) or (0, ""))

    with pytest.raises(RuntimeError) as err:
        blackbox_env.require_make()

    msg = str(err.value)
    assert "make: command not found" in msg
    assert "xcode-select --install" in msg
    assert "brew install make" not in msg or "not `brew install make`" in msg
    assert "torch" not in msg.lower()
    assert calls == [], "macOS must never auto-run anything -- xcode-select --install blocks on a GUI dialog"


# ---------------------------------------------------------------------------
# End-to-end repro: a real subprocess with `make` genuinely absent from PATH
# ---------------------------------------------------------------------------

def _path_without_make(tmp_path: Path) -> str:
    """A PATH containing every real directory's non-`make` binaries via symlinks, so other tools
    (python, sh) keep working while `make` itself is absent -- a faithful "runner missing make",
    not a wholesale PATH wipe that would also break the test."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(d)
        if not p.is_dir():
            continue
        for entry in p.iterdir():
            if entry.name == "make" or (fake_bin / entry.name).exists():
                continue
            try:
                (fake_bin / entry.name).symlink_to(entry)
            except OSError:
                continue
    return str(fake_bin)


def test_require_make_genuinely_fails_with_make_stripped_from_path(blackbox_env, tmp_path):
    """The real repro for #573: no mocking of shutil.which, an actual subprocess whose PATH has
    no `make` anywhere on it."""
    path_without_make = _path_without_make(tmp_path)
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import blackbox_env\n"
            "blackbox_env.require_make()\n" % str(BLACKBOX_ENV.parent))

    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={**os.environ, "PATH": path_without_make})

    assert r.returncode != 0, "require_make() must fail when `make` is genuinely absent from PATH"
    assert "make: command not found" in r.stderr or "make: command not found" in r.stdout
    assert "torch" not in (r.stderr + r.stdout).lower(), (
        "the reported cause must never mention torch -- that was the whole bug")


def test_pip_fallback_never_reached_when_make_is_absent(blackbox_env, tmp_path, monkeypatch):
    """Regression test for the actual bug: before this fix, a missing `make` let
    `make install-requirements || pip install -e .` fall through to pip, which reported an
    unresolvable torch pin instead of the real cause. require_make() must stop that at the door,
    before `_install_service` ever reaches the pip fallback."""
    monkeypatch.setattr(blackbox_env.sys, "platform", "linux")
    monkeypatch.setattr(blackbox_env.shutil, "which",
                        lambda name: {"uv": "/usr/bin/uv"}.get(name))
    ran = []
    monkeypatch.setattr(blackbox_env, "_run", lambda *a, **kw: ran.append(a) or (0, ""))

    with pytest.raises(RuntimeError) as err:
        blackbox_env._install_service(tmp_path / "some-service")

    assert "make: command not found" in str(err.value)
    assert not any("pip install -e ." in (a[0] if a and isinstance(a[0], str) else "")
                  for a in ran), "the pip fallback must never run once require_make() has failed"
