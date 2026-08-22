"""An optimizer step that did not get what it needed must not look like a step that
had nothing to propose.

Three regressions, one theme (see #251, #252):
  A. a named-but-missing ``--prompt`` file used to become an EMPTY prompt at exit 0,
     so the 10 ``{prompt_text}`` registry rows billed a real agent CLI to run with no
     instructions at all;
  B. the optimizer's stderr was discarded on the ZERO-exit path by three layers
     (run.py / harness / cli), so a CLI that explained itself and exited 0 was silent;
  C. a relative ``optimizer_instructions_file`` resolved differently under ``check``
     than under ``run``, and ``run`` fell back to the generic template without a word.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import specfile  # noqa: E402
from cap_evolve.harness import optimizer_from_command  # noqa: E402

RUN_PY = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"
SELFTEST = REPO / "skills" / "phases" / "implement-and-check" / "scripts" / "pipeline_selftest.py"


def _run_optimizer(*args, env=None):
    e = {**__import__("os").environ, "PYTHONPATH": str(CORE)}
    if env:
        e.update(env)
    return subprocess.run([sys.executable, str(RUN_PY), *args],
                          capture_output=True, text=True, env=e)


# ---- A. a missing prompt file is a hard, loud failure ----------------------

def test_missing_prompt_file_is_a_hard_error_not_an_empty_prompt(tmp_path):
    proc = _run_optimizer("--name", "mock", "--workdir", str(tmp_path),
                          "--prompt", str(tmp_path / "NOPE.md"))
    assert proc.returncode != 0, "a named-but-missing --prompt must NOT exit 0"
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "NOPE.md" in payload["error"], payload
    # and the agent CLI must never have been reached with an empty prompt
    assert "returncode" not in payload, payload


def test_existing_prompt_file_still_runs(tmp_path):
    (tmp_path / "INSTRUCTIONS.md").write_text("do the thing", encoding="utf-8")
    proc = _run_optimizer("--name", "mock", "--workdir", str(tmp_path),
                          "--prompt", str(tmp_path / "INSTRUCTIONS.md"))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1])["cli_present"] is True


# ---- B. stderr survives the zero-exit path --------------------------------

def _stub_agent(tmp_path, msg="STUB-DIAGNOSTIC: model fell back"):
    stub = tmp_path / "stub_agent.sh"
    stub.write_text(f'#!/bin/sh\necho "{msg}" >&2\nexit 0\n', encoding="utf-8")
    stub.chmod(0o755)
    return stub


def test_run_py_relays_child_stderr_on_success_and_keeps_stdout_one_json(tmp_path):
    stub = _stub_agent(tmp_path)
    (tmp_path / "INSTRUCTIONS.md").write_text("x", encoding="utf-8")
    proc = _run_optimizer("--name", "generic", "--workdir", str(tmp_path),
                          "--prompt", str(tmp_path / "INSTRUCTIONS.md"),
                          env={"CAPEVOLVE_OPTIMIZER_CMD": f"{stub} --workdir {{workdir}}"})
    assert proc.returncode == 0
    assert "STUB-DIAGNOSTIC" in proc.stderr, "child stderr was discarded on exit 0"
    # #217: stdout stays exactly one JSON object, so the relay cannot corrupt it.
    assert json.loads(proc.stdout)["returncode"] == 0


def test_harness_keeps_optimizer_stderr_on_the_zero_exit_path(tmp_path):
    stub = _stub_agent(tmp_path)
    import os
    os.environ["CAPEVOLVE_OPTIMIZER_CMD"] = f"{stub} --workdir {{workdir}}"
    try:
        run = optimizer_from_command([sys.executable, str(RUN_PY), "--name", "generic",
                                      "--workdir", "{workdir}", "--prompt", "{prompt}"])
        report = run(tmp_path, "instructions")
    finally:
        os.environ.pop("CAPEVOLVE_OPTIMIZER_CMD", None)
    assert isinstance(report, dict), "stderr-carrying report must not collapse to None"
    assert "STUB-DIAGNOSTIC" in report["stderr"]


def test_recorded_optimizer_stderr_is_persisted_and_logged(tmp_path):
    from cap_evolve.harness import _record_optimizer_stderr
    from cap_evolve.rundir import RunDir
    rd = RunDir.create(tmp_path, ts="t")
    _record_optimizer_stderr(rd, "cand_0001", "rate limited, retrying\n")
    saved = rd.root / "work" / "cand_0001.optimizer.stderr"
    assert saved.read_text(encoding="utf-8") == "rate limited, retrying\n"
    kinds = [json.loads(l)["kind"] for l in rd.events_path.read_text().splitlines() if l.strip()]
    assert "optimizer_stderr" in kinds
    # nothing to say when the optimizer said nothing
    _record_optimizer_stderr(rd, "cand_0002", "   ")
    assert not (rd.root / "work" / "cand_0002.optimizer.stderr").exists()


# ---- C. one resolution rule, and a loud fallback --------------------------

def test_relative_spec_path_is_project_relative_regardless_of_cwd(tmp_path, monkeypatch):
    project = tmp_path / ".capevolve" / "project"
    (project / "optimizer").mkdir(parents=True)
    want = project / "optimizer" / "INSTRUCTIONS.md"
    want.write_text("t", encoding="utf-8")
    # a cwd-relative decoy at the SAME relative path must never win
    (tmp_path / "optimizer").mkdir()
    (tmp_path / "optimizer" / "INSTRUCTIONS.md").write_text("decoy", encoding="utf-8")
    for cwd in (tmp_path, Path(tmp_path.anchor)):
        monkeypatch.chdir(cwd)
        got = specfile.resolve_project_path(project, "optimizer/INSTRUCTIONS.md")
        assert got.resolve() == want.resolve(), f"cwd {cwd} changed the resolution"
    assert specfile.resolve_project_path(project, "/abs/x.md") == Path("/abs/x.md")


def test_check_and_run_share_the_resolver():
    """`check` (pipeline_selftest) and `run` (cli) must call the SAME resolver, so a
    spec the gate passes cannot have a path the run resolves to a different file."""
    for f in (SELFTEST, REPO / "core" / "cap_evolve" / "cli.py"):
        src = f.read_text(encoding="utf-8")
        assert "resolve_project_path" in src, f"{f.name} resolves spec paths its own way"


def test_named_but_unrenderable_template_warns_instead_of_falling_back_silently(tmp_path, capsys):
    from cap_evolve.harness import _focus_instructions
    from cap_evolve.loop import SplitResult
    val = SplitResult(split="val", reward=0.0, stderr=0.0,
                      per_task=[{"task_id": "t", "reward": 0.0, "trial_rewards": [0.0],
                                 "feedback": "nope"}])
    bad = tmp_path / "INSTRUCTIONS.md"
    bad.write_text("a template with no placeholder at all", encoding="utf-8")
    for path in (bad, tmp_path / "GONE.md"):
        _focus_instructions(val, None, "focus", instructions_file=path)
        assert str(path) in capsys.readouterr().err, f"silent fallback for {path.name}"
    # an UNNAMED template (the built-in default) has nothing to warn about
    _focus_instructions(val, None, "focus", instructions_file=None)
    assert "falling back" not in capsys.readouterr().err
