"""The optimizer profile (CAPEVOLVE_OPTIMIZER_PROFILE) is off by default and each feature does
exactly one thing. These are the switches for the weak-optimizer (Gemma) experiments (#538)."""

import json
import subprocess
import sys
from pathlib import Path

from cap_evolve import optimizer_profile as op

REPO = Path(__file__).resolve().parents[2]

INSTR = """# Iteration
intro
## THE READER (who consumes what you edit)
reader text
## The THREE TESTS every change must pass (this is the whole game)
tests text
## Choose the lever by FAILURE TYPE
lever text
## (a) 13 ALWAYS-failing task(s) — fix the shared root cause
- 227-40 failed
## Self-check before STOP
check text
## Run budget (iteration 2/5)
"""


def test_unset_changes_nothing():
    assert op.features({}) == frozenset()
    assert op.apply_to_instructions(INSTR, {}) == INSTR
    assert op.extra_disallowed_tools("claude-code", {}) == []


def test_alias_enables_all_and_unknown_names_are_ignored():
    assert op.features({op.ENV: "gemma"}) == frozenset(op.FEATURES)
    assert op.features({op.ENV: "output_guard, typo_feature"}) == {"output_guard"}


def test_short_instructions_drops_method_sections_and_keeps_the_task():
    out = op.apply_to_instructions(INSTR, {op.ENV: "short_instructions"})
    for gone in ("THREE TESTS", "Choose the lever", "Self-check before STOP"):
        assert gone not in out
    for kept in ("intro", "THE READER", "227-40 failed", "Run budget"):
        assert kept in out
    assert "Reading large files" not in out


def test_output_guard_appends_the_rule_only():
    out = op.apply_to_instructions(INSTR, {op.ENV: "output_guard"})
    assert out.startswith(INSTR.rstrip("\n"))
    assert "## Reading large files (REQUIRED)" in out and "do NOT `cat`" in out


def test_no_subagents_only_for_claude_code():
    env = {op.ENV: "no_subagents"}
    assert op.extra_disallowed_tools("claude-code", env) == ["Agent", "Task"]
    assert op.extra_disallowed_tools("codex", env) == []


def _rollout():
    long = "x" * 5000
    trace = [{"role": "user", "content": "TASK " + "p" * 3000}]
    trace += [{"role": "assistant", "content": "same code"}, {"role": "user", "content": "same error"}] * 25
    trace += [{"role": "assistant", "content": long}, {"role": "user", "content": "final error"}]
    return {"input": {"instruction": "do it"},
            "rollout": {"task_id": "227-40", "output": "o" * 3000, "trace": trace, "error": None},
            "score": {"reward": 0.0, "feedback": "MISMATCH: 5 cells"}}


def test_digest_keeps_diagnosis_fields_and_shrinks_the_trace():
    raw = _rollout()
    d = op.digest_trajectory(raw)
    assert d["score"] == raw["score"] and d["input"] == raw["input"]
    tr = d["rollout"]["trace"]
    assert tr[0]["content"].startswith("TASK ") and "more chars cut" in tr[0]["content"]
    assert tr[-1]["content"] == "final error"
    assert all(len(t["content"]) < op.DIGEST_FIRST_TURN_CHARS + 40 for t in tr)
    assert len(json.dumps(d)) < len(json.dumps(raw)) / 2
    assert d["rollout"]["trace_digest"]["turns_original"] == len(raw["rollout"]["trace"])
    assert raw["rollout"]["trace"][0]["content"].startswith("TASK ")  # input not mutated


def test_digest_collapses_repeated_turns():
    trace = [{"role": "user", "content": "t"}] + [{"role": "assistant", "content": "a"}] * 4
    d = op.digest_trajectory({"rollout": {"trace": trace}})
    assert d["rollout"]["trace"][1] == {"role": "assistant", "content": "a", "repeated": 4}


def test_run_py_appends_subagent_tools_to_the_existing_deny_list(tmp_path):
    prompt = tmp_path / "INSTRUCTIONS.md"
    prompt.write_text("hi")
    code = (
        "import sys; sys.argv=['run.py']; "
        f"sys.path.insert(0, {str(REPO / 'skills/optimizers/run-optimizer/scripts')!r}); "
        "import run, shlex; "
        "row = run.load_registry()['claude-code']; "
        f"cmd = run.build_command(row['command_template'], workdir='.', prompt={str(prompt)!r}, "
        "prompt_text='hi', model='m', self_dir=run._self_dir()); "
        "extra = run._profile_extra_disallowed('claude-code'); "
        "i = cmd.index('--disallowedTools') + 1; cmd[i + 1:i + 1] = extra; "
        "print(cmd[i:i + 4])"
    )
    env = {"PYTHONPATH": str(REPO / "core"), op.ENV: "no_subagents", "PATH": "/usr/bin:/bin"}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert "'Monitor', 'Agent', 'Task'" in out.stdout


def test_harness_and_run_py_call_the_profile():
    harness = (REPO / "core/cap_evolve/harness.py").read_text(encoding="utf-8")
    assert "optimizer_profile.apply_to_instructions(instructions)" in harness
    assert 'optimizer_profile.enabled("digest_trajectories")' in harness
    run_py = (REPO / "skills/optimizers/run-optimizer/scripts/run.py").read_text(encoding="utf-8")
    assert "_profile_extra_disallowed(name)" in run_py
