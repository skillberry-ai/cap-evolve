"""`./install.sh` must produce an install that can actually optimize (#143, #208).

This is the pytest face of ``ci/install_smoke.sh`` — the executing artifact that
justifies the ✅ on the `claude` destination row in ``docs/HOST_SUPPORT.md``. It is a
thin wrapper on purpose: the shell script is what CI runs, and duplicating its logic
in Python would be a second thing to keep in sync.

Why this test has to exist: nothing else in the suite runs the installer. Every other
path sets ``$CAPEVOLVE_SKILLS_DIR`` to the repo tree, which bypasses the ``--host``
mapping entirely — which is how ``skills/optimizers/registry.yaml`` went uninstalled
and left every stock install unable to run one optimizer iteration (#193).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "ci" / "install_smoke.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.skipif(shutil.which("git") is None, reason="git store needed for candidates")
def test_install_sh_produces_a_runnable_install():
    """Install via --host, then complete a zero-API run from outside the repo."""
    # The smoke script shells `python3`; point that at the interpreter running pytest so
    # a venv-only install of cap-evolve-core is still importable (it sets PYTHONPATH to
    # $REPO/core anyway, so the only requirement is a 3.10+ python3 on PATH).
    bindir = str(Path(sys.executable).parent)
    env = {**os.environ, "PATH": bindir + os.pathsep + os.environ.get("PATH", "")}
    env.pop("CAPEVOLVE_SKILLS_DIR", None)
    out = subprocess.run(["bash", str(SMOKE)], capture_output=True, text=True, env=env)
    assert out.returncode == 0, f"STDOUT:\n{out.stdout}\n\nSTDERR:\n{out.stderr}"
    assert '"test_reward": 1.0' in out.stdout, out.stdout
    assert "PASS:" in out.stdout
