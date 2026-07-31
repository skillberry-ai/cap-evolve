"""A native crash in a phase process must leave evidence.

Run 30608405812's algorithm step died with `{"returncode": -11, "signal": "SIGSEGV"}` and
nothing else: no Python traceback (there isn't one for a segfault) and a stderr window that
held only the tail — tens of kilobytes of routine per-rollout scoring chatter emitted long
after the interesting output. The crash was undiagnosable from CI alone. These tests pin the
three things that make it diagnosable next time.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


class _Proc:
    def __init__(self, returncode, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


# ---- stderr window keeps the head, not just the tail ----------------------

def test_clip_keeps_head_and_tail():
    from cap_evolve.cli import _clip
    text = "HEAD" + ("x" * 50_000) + "TAIL"
    out = _clip(text, head=100, tail=200)
    assert out.startswith("HEAD")
    assert out.endswith("TAIL")
    assert "chars omitted" in out


def test_clip_passes_short_text_through():
    from cap_evolve.cli import _clip
    assert _clip("short", head=100, tail=200) == "short"
    assert _clip(None, head=10, tail=10) == ""


def test_crash_context_survives_a_chatty_scoring_tail():
    """The failure record must still show the crash even when scoring logged 40 KB after it."""
    from cap_evolve.cli import _step_failure
    stderr = ("Fatal Python error: Segmentation fault\n  File \"scorer.py\", line 1 in compare\n"
              + "Cell values in the specified range are identical.\n" * 1000)
    rec = _step_failure("algorithm", _Proc(-11, stderr=stderr))
    assert "Fatal Python error" in rec["error"]


# ---- the hint must not misdirect ------------------------------------------

def test_sigsegv_hint_does_not_blame_the_oom_killer():
    from cap_evolve.cli import _step_failure
    rec = _step_failure("algorithm", _Proc(-11, stderr="boom"))
    assert rec["signal"] == "SIGSEGV"
    assert "OOM" not in rec["hint"] and "dmesg" not in rec["hint"]
    assert "faulthandler" in rec["hint"]


def test_sigkill_hint_still_points_at_the_oom_killer():
    from cap_evolve.cli import _step_failure
    rec = _step_failure("algorithm", _Proc(-9, stderr="boom"))
    assert rec["signal"] == "SIGKILL"
    assert "OOM" in rec["hint"]


# ---- faulthandler is armed by importing cap_evolve -----------------------

def test_importing_cap_evolve_arms_faulthandler():
    """A real segfault in a child that imported cap_evolve must print a native traceback."""
    code = "import cap_evolve, faulthandler; faulthandler._sigsegv()"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env={"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin"})
    assert proc.returncode != 0
    assert "Fatal Python error" in proc.stderr, f"no native traceback: {proc.stderr!r}"
    assert proc.stdout == "", "faulthandler must never write to the JSON stdout contract"


def test_faulthandler_can_be_disabled_for_a_host_that_needs_default_signals():
    code = "import cap_evolve, faulthandler; print(faulthandler.is_enabled())"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env={"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin",
                               "CAPEVOLVE_NO_FAULTHANDLER": "1"})
    assert proc.stdout.strip() == "False", proc.stdout
