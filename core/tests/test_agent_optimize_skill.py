"""agent-optimize is prose-as-implementation, so its SKILL.md commands are the code.

Two guards:
  1. the skill's own ``check.py`` — which now *executes* every command SKILL.md
     documents against a temp run dir — must report ``ok: true``;
  2. SKILL.md must not carry the known-broken patterns that once shipped (a gate
     invocation with a ``--mode`` the phase CLI rejects; a quoted heredoc that
     never expands ``$R``; a ``cp`` into a ``work/`` nobody creates).
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "skills" / "algorithms" / "agent-optimize"


def test_check_py_reports_ok():
    p = subprocess.run([sys.executable, str(SKILL / "scripts" / "check.py")],
                       capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "CAPEVOLVE_CORE": str(REPO / "core"),
                            "HOME": str(Path.home())})
    assert p.returncode == 0, f"check.py failed:\n{p.stdout}\n{p.stderr}"
    report = json.loads(p.stdout)
    assert report["ok"] is True, report["problems"]


def test_skill_md_has_no_known_broken_patterns():
    md = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    # Defect A: `--mode paired` used to be an invalid choice, so the documented gate
    # step exited 2. The phase CLI now reaches the paired gate, but ONLY in rollout mode
    # (--run-dir + both tags) — two scalar means cannot carry a per-task delta vector.
    # So a paired invocation in the skill must always come with a run dir.
    # Join backslash continuations first: a shell command split over lines is one command.
    for cmd in md.replace("\\\n", " ").splitlines():
        if "--mode paired" in cmd:
            assert "--run-dir" in cmd, (
                "paired gate needs rollout mode (--run-dir/--current-tag/--candidate-tag); "
                f"a scalar-mean invocation is refused: {cmd.strip()}")

    # Defect B: a quoted heredoc never expands $R, so RunDir.open("$R") opens a literal dir.
    assert "<<'PY'" not in md and '<<"PY"' not in md
    assert 'RunDir.open("$R")' not in md

    # Defect C: RunDir.create only mkdirs candidates/ and rollouts/.
    assert 'mkdir -p "$R/work"' in md

    # The parallel round and its non-negotiables are documented.
    assert "## Parallel round" in md
    for needle in ("unique per sibling", "gate stays serial", "re-gate"):
        assert needle in md, needle
    assert "Task" in md.split("---")[1], "frontmatter must allow the Task tool"


# ---- the churn case: a mean gain whose gains and losses cancel -------------
#
# Motivating real failure: two of three candidates in a live run had an IDENTICAL mean
# to their parent while a different set of tasks passed (each fixed 2, broke 2). A
# mean-only gate calls that a tie; the no-regression veto is what rejects it. These
# guard both halves of the ladder against it.

def _load_gate_check():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ao_gate_check", SKILL / "scripts" / "gate_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SKILL / "scripts"))
    spec.loader.exec_module(mod)
    return mod


class _R:
    def __init__(self, per_task):
        self.per_task = per_task


def _pt(tid, reward):
    return {"task_id": tid, "reward": reward,
            "raw": {"valid_trials": 1, "n_trials": 1}}


def test_no_regression_vetoes_a_churn_candidate():
    gc = _load_gate_check()
    parent = _R([_pt("a", 1.0), _pt("b", 1.0), _pt("c", 0.0), _pt("d", 0.0)])
    churn = _R([_pt("a", 0.0), _pt("b", 0.0), _pt("c", 1.0), _pt("d", 1.0)])
    # Identical mean (0.5 -> 0.5): the significance test sees nothing to reject.
    assert gc.regressions(parent, churn) == ["a", "b"]


def test_no_regression_ignores_tasks_the_candidate_never_measured():
    """An infra outage is missing data, not the largest regression a candidate can cause."""
    gc = _load_gate_check()
    parent = _R([_pt("a", 1.0), _pt("b", 1.0)])
    cand = _R([_pt("a", 1.0),
               {"task_id": "b", "reward": 0.0,
                "raw": {"valid_trials": 0, "n_trials": 1, "errored": True}}])
    assert gc.regressions(parent, cand) == []


def test_a_real_improvement_has_no_regressions():
    gc = _load_gate_check()
    parent = _R([_pt("a", 1.0), _pt("b", 0.0)])
    better = _R([_pt("a", 1.0), _pt("b", 1.0)])
    assert gc.regressions(parent, better) == []
