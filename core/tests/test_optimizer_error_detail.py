"""A failed optimizer must surface WHY it failed: run-optimizer reports the agent
CLI's real output as JSON on stdout (stderr_tail/stdout_tail), and the harness
must lift that into the error (and thus the optimizer_error event/dashboard)."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve.harness import _optimizer_failure_detail  # noqa: E402


def _proc(returncode=1, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["x"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_lifts_stderr_tail_from_runner_json():
    out = json.dumps({"optimizer": "claude-code", "returncode": 1,
                      "stderr_tail": "anthropic: overloaded_error 529", "stdout_tail": ""})
    assert "overloaded_error 529" in _optimizer_failure_detail(_proc(stdout=out))


def test_falls_back_to_stdout_tail():
    out = json.dumps({"returncode": 1, "stderr_tail": "", "stdout_tail": "model refused to edit"})
    assert "model refused to edit" in _optimizer_failure_detail(_proc(stdout=out))


def test_prefers_real_stderr_and_appends_tail():
    out = json.dumps({"stderr_tail": "CLI tail"})
    d = _optimizer_failure_detail(_proc(stdout=out, stderr="proc stderr"))
    assert "proc stderr" in d and "CLI tail" in d


def test_non_json_stdout_is_used_raw():
    assert "boom traceback" in _optimizer_failure_detail(_proc(stdout="boom traceback"))


def test_empty_everything_is_explained_not_blank():
    d = _optimizer_failure_detail(_proc(stdout="", stderr=""))
    assert d and d != ""  # never a bare "failed (1): "
