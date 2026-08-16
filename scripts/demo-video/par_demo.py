"""Measure framework eval parallelism: does it speed up, and does it stay honest?

A standalone parallelism check (it was once filmed for the demo video; that shot and
its card are no longer in the cut). Useful on its own as a
sanity check after touching ``harness.evaluate_candidate``.

The adapter's reward is a pure function of (task, seed), so a parallel run MUST return a
byte-identical ``SplitResult`` to a serial one. Parallelism is allowed to change the
wallclock and nothing else — that assertion is the point of the script, not the speedup.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import time
from pathlib import Path

# Run from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))

from cap_evolve import RunDir, Rollout, Score, Task, harness  # noqa: E402
from cap_evolve.splits import Splits  # noqa: E402

IDS = [f"t{i}" for i in range(16)]
SLEEP = 0.2
TRIALS = 2


class SlowAdapter:
    """Deterministic, but each rollout sleeps — stands in for a real runner's latency."""

    def tasks(self, split):
        return [Task(id=i, input={"n": n}) for n, i in enumerate(IDS)]

    def run_target(self, task, ctx, *, seed=0):
        time.sleep(SLEEP)
        return Rollout(task_id=task.id, output=f"{task.id}:{seed}")

    def score(self, task, rollout):
        n, seed = int(task.input["n"]), int(str(rollout.output).split(":")[1])
        return Score(task_id=task.id, reward=((n + seed) % 3) / 2.0, feedback=str(n))

    def apply(self, candidate_dir, edits=None):
        return None


def run(workers: int, tmp: str):
    rd = RunDir.create(Path(tmp) / f"rd{workers}", ts=f"w{workers}")
    rd.write_splits(Splits(train=[], val=list(IDS), test=[], seed=41))
    cand = Path(tmp) / f"c{workers}"
    cand.mkdir()
    rd.snapshot("c", cand)
    t0 = time.time()
    # The runner's own chatter would otherwise land in this script's stdout.
    with contextlib.redirect_stdout(io.StringIO()):
        res = harness.evaluate_candidate(
            SlowAdapter(), rd.candidate_dir("c"), run_dir=rd,
            split="val", n_trials=TRIALS, tag="c", workers=workers,
        )
    return time.time() - t0, res


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        results, timing = {}, {}
        for w in (1, 4, 8):
            elapsed, res = run(w, tmp)
            results[w] = res
            timing[w] = elapsed
            print(f"workers={w:<2} wallclock={elapsed:6.2f}s  "
                  f"reward={res.reward!r} stderr={res.stderr!r}")

        a, b = results[1], results[8]
        same = (a.reward == b.reward and a.stderr == b.stderr
                and a.per_task == b.per_task and a.pass_k == b.pass_k
                and a.n_scored == b.n_scored)
        print("identical SplitResult (workers=1 vs 8):", same)
        # Kept for anyone re-adding a parallelism shot; nothing in the demo video
        # build reads this file any more. Best-effort: the script's own assertion
        # is the point, not the json.
        out = Path("/tmp/video/par_results.json")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "tasks": len(IDS), "trials": TRIALS, "identical": same,
                "runs": {str(w): {"wallclock": round(timing[w], 2),
                                  "reward": results[w].reward,
                                  "stderr": results[w].stderr} for w in timing},
            }, indent=1))
        except OSError as exc:
            print(f"(could not write {out}: {exc})")
        print(f"{len(IDS) * TRIALS} rollouts x {SLEEP}s = {len(IDS) * TRIALS * SLEEP:.1f}s "
              f"of sleep; per_task order:",
              [pt["task_id"] for pt in b.per_task] == IDS)
        return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
