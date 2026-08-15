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
