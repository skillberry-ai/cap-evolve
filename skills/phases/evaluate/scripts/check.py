"""Contract: evaluate aggregates split × trials HONESTLY — it scores exactly the
tasks in the requested split, runs n_trials per task, reports a mean over the VALID
trials of the SCORED tasks, and reports a non-zero SE when the tasks disagree.

The last two are the properties the skill exists for: an infra-errored trial must
leave the mean (so a crash is missing data, not a capability failure of 0.0), and
the SE must actually be measured (an SE of 0 degenerates the significance gate).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import Rollout, Score, Task, harness
from cap_evolve.skillcheck import Checker, import_run, temp_run_dir

# 8 ids at a 50/25/25 split give a val of 2 — enough for a between-task SE to exist
# at all (stats.combined_stderr defines it as 0 below 2 tasks).
_IDS = ("a", "b", "c", "d", "e", "f", "g", "h")


class _Adapter:
    """Synthetic adapter: reward = 1 on even trials, 0 on odd → mean 0.5 over 2 trials."""

    def tasks(self, split):
        return [Task(id=t, input={}) for t in _IDS]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id, output=str(seed))

    def score(self, task, rollout):
        # An errored rollout is still handed to score() — the harness discards the
        # number afterwards, but the scorer must not crash on it.
        if rollout.output is None:
            return Score(task_id=task.id, reward=0.0)
        return Score(task_id=task.id, reward=1.0 if int(rollout.output) % 2 == 0 else 0.0)

    def materialize(self, candidate_dir):
        return {}


class _SplitAdapter(_Adapter):
    """Tasks disagree (reward keyed off the task id), so the between-task SE is > 0."""

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=1.0 if task.id in ("a", "c", "e", "g") else 0.0)


class _FlakyAdapter(_Adapter):
    """One task's runner always errors: the target never ran on it."""

    def __init__(self, dead: str):
        self.dead = dead

    def run_target(self, task, ctx, *, seed=0):
        if task.id == self.dead:
            return Rollout(task_id=task.id, error="infra: runner exploded")
        return super().run_target(task, ctx, seed=seed)


def main() -> int:
    c = Checker("evaluate")
    c.require_main(import_run())

    with tempfile.TemporaryDirectory() as d:
        rd, splits = temp_run_dir(Path(d), ids=_IDS, seed=0)
        cand = Path(d) / "cand"
        cand.mkdir()

        res = harness.evaluate_candidate(_Adapter(), cand, run_dir=rd, split="val",
                                         n_trials=2, base_seed=0, tag="chk")
        # only the val split's tasks are scored
        c.check(len(res.per_task) == len(splits.val),
                f"evaluated {len(res.per_task)} tasks, val has {len(splits.val)}",
                note=f"scored exactly the val split ({len(splits.val)} tasks)")
        # 2 trials (seed 0 -> reward 1, seed 1 -> reward 0) average to 0.5 per task
        c.check(all(abs(pt["reward"] - 0.5) < 1e-9 for pt in res.per_task),
                f"per-task mean over trials wrong: {[pt['reward'] for pt in res.per_task]}",
                note="reward is the mean over n_trials per task")
        c.check(all(pt.get("n", 0) == 2 for pt in res.per_task),
                "n_trials not recorded per task")
        c.check(res.n_scored == res.n_tasks == len(splits.val),
                f"honest denominator wrong on a healthy split: "
                f"n_scored={res.n_scored} n_tasks={res.n_tasks}",
                note="n_scored == n_tasks when nothing errored")

        # An infra-errored task is MISSING DATA, not a 0.0: it leaves the mean and
        # shrinks the denominator, so coverage exposes the decimated split.
        dead = sorted(splits.val)[0]
        flaky = harness.evaluate_candidate(_FlakyAdapter(dead), cand, run_dir=rd,
                                           split="val", n_trials=2, base_seed=0, tag="flaky")
        c.check(flaky.n_scored < flaky.n_tasks and flaky.coverage < 1.0,
                f"errored task not excluded from the denominator: "
                f"n_scored={flaky.n_scored} n_tasks={flaky.n_tasks}",
                note=f"errored trials leave the mean (coverage {flaky.coverage:.2f})")
        c.check(abs(flaky.reward - 0.5) < 1e-9,
                f"errored task dragged the mean to {flaky.reward} instead of leaving it "
                "at the scored tasks' 0.5 (a crash was averaged in as a 0.0)")
        c.check((rd.rollouts / "val" / f"{dead}__flaky__t0.json").exists(),
                "errored rollout file not kept for forensics")

        # A measured SE: tasks that disagree must produce stderr > 0, otherwise the
        # significance gate has no bar and silently degenerates to strict.
        spread = harness.evaluate_candidate(_SplitAdapter(), cand, run_dir=rd, split="val",
                                            n_trials=2, base_seed=0, tag="spread")
        c.check(spread.stderr > 0.0,
                f"stderr is {spread.stderr} on a split whose tasks disagree "
                f"({[pt['reward'] for pt in spread.per_task]}) — the gate bar would be 0",
                note=f"between-task SE is measured (stderr={spread.stderr:.4f})")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
