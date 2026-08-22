"""Toy-skill adapter — a zero-API, deterministic run whose capability IS a skill package.

The `toy_calc` example proves the pipeline on a prompt. This one proves it on the
part of a skill package that prose cannot fix: the tasks are arithmetic written
the way people write it ("two thousand", "3 plus 4", "1,200 + 5"), and the
deterministic stand-in agent can only get those right by RUNNING a bundled
`scripts/normalize.py` that the SKILL.md points it at. Following the seed skill's
prose alone fails every messy task — so the score can only rise when the
optimizer writes bundled CODE, which is exactly the determinism lever the
`skill-package` capability is supposed to push.

Set ``CAPEVOLVE_TOY_DATA`` to this example dir (or leave it — it defaults here).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

_DATA = Path(os.environ.get("CAPEVOLVE_TOY_DATA", Path(__file__).resolve().parent))

# (expression as a user writes it, exact answer)
TASKS = [
    ("2 + 3", "5"),
    ("10 - 4", "6"),
    ("6 * 7", "42"),
    ("3 plus 4", "7"),
    ("9 minus 5", "4"),
    ("8 times 3", "24"),
    ("1,200 + 5", "1205"),
    ("2,000 minus 1,000", "1000"),
    ("12 plus 1,000", "1012"),
    ("4 times 1,100", "4400"),
]

_SAFE = set("0123456789 +-*")


def _eval(expr: str) -> str:
    if not set(expr) <= _SAFE:
        raise ValueError(f"cannot parse {expr!r}")
    return str(int(eval(expr, {"__builtins__": {}}, {})))  # noqa: S307 (charset-limited)


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        return [Task(id=f"t{i:02d}", input=x, target=y) for i, (x, y) in enumerate(TASKS)]

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        pkg = Path(ctx)
        body = (pkg / "SKILL.md").read_text(encoding="utf-8") if (pkg / "SKILL.md").exists() else ""
        expr = str(task.input)
        # The agent runs a bundled script only when the skill TELLS it to (by naming a
        # `scripts/<file>` command in the body) AND the script is there — the same
        # contract a real agent follows. Any filename works; the pointer is what matters.
        helper = next((pkg / m for m in re.findall(r"(scripts/[\w./-]+\.py)", body)
                       if (pkg / m).exists()), None)
        if helper is not None:
            p = subprocess.run([sys.executable, str(helper), expr],
                               capture_output=True, text=True, timeout=30)
            out = (p.stdout or "").strip() or f"error: {(p.stderr or '').strip()[:120]}"
            return Rollout(task_id=task.id, output=out, trace=f"ran {helper.name}")
        # Prose-only path: it handles the tidy cases and fumbles the rest.
        try:
            out = _eval(re.sub(r"\s+", " ", expr).strip())
        except Exception as e:  # noqa: BLE001
            out = f"error: {e}"
        return Rollout(task_id=task.id, output=out, trace="followed the SKILL.md body only")

    def score(self, task: Task, rollout: Rollout) -> Score:
        got = (rollout.output or "").strip()
        ok = got == str(task.target).strip()
        fb = ("correct" if ok else
              f"expected '{task.target}' but got '{got}': the input is not plain "
              "arithmetic (number words, thousands separators), and the skill gives no "
              "deterministic way to normalize it before computing")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                     trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        # The stand-in reads the candidate package directly, so going "live" is a no-op.
        return None
