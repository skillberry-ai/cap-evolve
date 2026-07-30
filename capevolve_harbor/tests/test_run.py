"""Tests for capevolve_harbor.run — signal handling and harbor binary discovery."""
import os
import signal
from unittest.mock import patch

from capevolve_harbor.run import (
    find_harbor_bin,
    _install_signal_forwarding,
    _restore_signal_handlers,
)


def test_find_harbor_bin_from_env(tmp_path):
    fake = tmp_path / "harbor"
    fake.touch()
    with patch.dict(os.environ, {"HARBOR_BIN": str(fake)}):
        assert find_harbor_bin() == str(fake)


def test_find_harbor_bin_from_venv(tmp_path):
    venv = tmp_path / "venv"
    bin_dir = venv / "bin"
    bin_dir.mkdir(parents=True)
    harbor = bin_dir / "harbor"
    harbor.touch()
    with patch.dict(os.environ, {"VIRTUAL_ENV": str(venv)}, clear=False):
        # Clear HARBOR_BIN to avoid short-circuit
        env = os.environ.copy()
        env.pop("HARBOR_BIN", None)
        env["VIRTUAL_ENV"] = str(venv)
        with patch.dict(os.environ, env, clear=True):
            assert find_harbor_bin() == str(harbor)


def test_find_harbor_bin_raises_when_missing():
    with patch.dict(os.environ, {}, clear=True):
        with patch("shutil.which", return_value=None):
            try:
                find_harbor_bin()
                assert False, "Should have raised"
            except FileNotFoundError as e:
                assert "harbor" in str(e)


def test_signal_handlers_restored():
    """Signal handlers must be restored after _restore_signal_handlers."""
    original_sigint = signal.getsignal(signal.SIGINT)

    class FakeProc:
        def send_signal(self, sig):
            pass

    saved = _install_signal_forwarding(FakeProc())
    # Handlers should now be different
    current = signal.getsignal(signal.SIGINT)
    assert current != original_sigint

    _restore_signal_handlers(saved)
    # Handlers should be back to original
    restored = signal.getsignal(signal.SIGINT)
    assert restored == original_sigint
