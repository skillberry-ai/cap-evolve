"""Shared harness for skill ``scripts/check.py`` contract tests.

Every skill ships a ``check.py`` that must prove a *behavioral* contract, not
merely that ``run.py`` imports. This module gives those checks a common shape so
they stay short and uniform:

  * ``Checker`` — collects ``problems`` / ``notes`` and emits the standard JSON
    report (``{"skill", "ok", "problems", "notes"}``) + the right exit code.
  * ``import_run`` / ``import_module`` — load the skill's own ``run.py`` /
    ``abstract.py`` (the scripts dir is already on ``sys.path`` because the check
    is invoked from inside it).
  * ``temp_run_dir`` — a throwaway ``RunDir`` with a frozen split, for checks that
    need to exercise harness code against real run state.
  * ``write_val_rollout`` — drop a synthetic scored rollout into the run dir in the
    exact on-disk shape ``evaluate_candidate`` writes, so a check can feed
    ``diagnose`` / ``evaluate`` deterministic input.

The import-smoke base (``Checker.require_main``) is kept, but every skill adds at
least one real assertion on top of it.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path


@contextlib.contextmanager
def quiet():
    """Swallow a callee's stdout so a check that invokes ``run.main()`` still emits
    exactly one JSON object (its own report). Stderr is left alone."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


class Checker:
    """Accumulate problems/notes and emit the standard check report."""

    def __init__(self, skill: str):
        self.skill = skill
        self.problems: list[str] = []
        self.notes: list[str] = []

    def check(self, cond: bool, problem: str, *, note: str | None = None) -> bool:
        if cond:
            if note:
                self.notes.append(note)
        else:
            self.problems.append(problem)
        return cond

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def fail(self, msg: str) -> None:
        self.problems.append(msg)

    def require_main(self, module) -> None:
        """Import-smoke base: the run entry must expose ``main()``."""
        self.check(hasattr(module, "main"), f"{module.__name__} missing main()",
                   note="run entry exposes main()")

    def emit(self) -> int:
        ok = not self.problems
        print(json.dumps({"skill": self.skill, "ok": ok,
                          "problems": self.problems, "notes": self.notes}, indent=2))
        return 0 if ok else 1


def import_run():
    """Import the skill's own ``run.py`` (scripts dir is on sys.path)."""
    import run  # type: ignore
    return run


def import_module(name: str):
    return __import__(name)


# ---- synthetic run state for behavioral checks ----------------------------

def temp_run_dir(tmp: Path, *, ids=("a", "b", "c", "d"), seed: int = 0,
                 ratios=(0.5, 0.25, 0.25)):
    """A throwaway RunDir with a frozen seeded split over synthetic task ids."""
    from cap_evolve import RunDir
    from cap_evolve.splits import make_splits
    rd = RunDir.create(Path(tmp) / ".capevolve", ts="chk")
    splits = make_splits(list(ids), seed=seed, ratios=ratios)
    rd.write_splits(splits)
    return rd, splits


def write_val_rollout(run_dir, task_id: str, *, tag: str = "seed", trial: int = 0,
                      reward: float = 0.0, feedback: str = "", output: str = "",
                      task_input=None, errored: bool = False) -> Path:
    """Write one scored val rollout in the on-disk shape evaluate_candidate uses.

    Lets diagnose/evaluate checks feed deterministic input. ``task_input`` is the
    real task INPUT carried through to the reflective dataset (not the task id).
    """
    out_dir = run_dir.rollouts / "val"
    out_dir.mkdir(parents=True, exist_ok=True)
    rec = {
        "input": task_input,
        "rollout": {"task_id": task_id, "output": output,
                    "error": "boom" if errored else None},
        "score": {"task_id": task_id, "reward": reward, "feedback": feedback,
                  "n": 1, "stderr": 0.0, "trial_rewards": [reward],
                  "raw": {"errored": errored}},
    }
    f = out_dir / f"{task_id}__{tag}__t{trial}.json"
    f.write_text(json.dumps(rec, default=str), encoding="utf-8")
    return f


# ---- tiny synthetic adapter + mock optimizer (offline, zero-API) ----------
#
# Shared so an algorithm's behavioral ``check.py`` AND the pytest e2e drive the
# SAME deterministic, model-free target. The "agent" reads ``level.txt`` from the
# live candidate dir: the higher the level, the more tasks it solves. The mock
# optimizer simply bumps that integer, so each accepted edit raises the score —
# a clean, reproducible proof of an epoch/step loop without any model call.

class SyntheticAdapter:
    """A deterministic CapabilityAdapter parameterized by ``n`` tasks.

    Task ``i`` is "solved" iff the candidate's integer level >= ``i+1``; a missing
    ``level.txt`` is level 0 (nothing solved). Reward is binary 0/1, feedback
    names the level needed (never leaks a gold answer for a real benchmark, but
    here there is none to leak).
    """

    def __init__(self, n: int = 8):
        self.n = n

    def tasks(self, split: str):
        from .types import Task
        return [Task(id=f"t{i}", input=f"solve-{i}", target=str(i + 1)) for i in range(self.n)]

    def run_target(self, task, ctx, *, seed: int = 0):
        from .types import Rollout
        lvl_file = Path(ctx) / "level.txt"
        try:
            level = int(lvl_file.read_text(encoding="utf-8").strip())
        except Exception:  # noqa: BLE001
            level = 0
        need = int(task.target)
        return Rollout(task_id=task.id, output=str(level), trace=f"level={level}")

    def score(self, task, rollout):
        from .types import Score
        level = int(rollout.output or 0)
        need = int(task.target)
        ok = level >= need
        fb = ("solved" if ok
              else f"needs capability level {need}; current level only reaches {level} "
                   f"— raise the skill level to cover this task")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                     trial_rewards=[1.0 if ok else 0.0])


def make_mock_optimizer(*, bump: int = 1):
    """An in-process OptimizerFn that bumps ``level.txt`` by ``bump`` each call.

    Models a real optimizer that makes a bounded edit; combined with
    ``SyntheticAdapter`` it produces a monotonically-improving lineage so the
    gate accepts, then plateaus once every task is solved (so later steps reject —
    exercising the rejected-edit buffer too)."""
    def _opt(workdir: Path, instructions: str) -> None:
        f = Path(workdir) / "level.txt"
        try:
            cur = int(f.read_text(encoding="utf-8").strip())
        except Exception:  # noqa: BLE001
            cur = 0
        f.write_text(str(cur + bump), encoding="utf-8")
    return _opt


def seed_capability_dir(tmp: Path, *, level: int = 0) -> Path:
    """Create a seed capability dir with a ``level.txt`` for SyntheticAdapter."""
    d = Path(tmp) / "seed_capability"
    d.mkdir(parents=True, exist_ok=True)
    (d / "level.txt").write_text(str(level), encoding="utf-8")
    return d
