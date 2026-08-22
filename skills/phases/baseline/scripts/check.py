"""Contract: baseline freezes a deterministic seeded split — the same seed yields
the same train/val/test partition, and the split is written once. It also refuses
what it must refuse: a red `cap-evolve check`, and a ratio split with no val/test.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import RunDir, harness
from cap_evolve.check import load_adapter
from cap_evolve.skillcheck import Checker, import_run, quiet
from cap_evolve.splits import make_splits

ADAPTER = '''
import random  # noqa: F401
from cap_evolve import CapabilityAdapter
from cap_evolve.types import Task, Rollout, Score


class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}", input="x", target="1") for i in range(N)]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id, output="1")

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=REWARD, feedback="ok")
'''


def _project(tmp: Path, name: str, *, n: int, reward: str) -> Path:
    proj = tmp / name
    (proj / "adapters").mkdir(parents=True, exist_ok=True)
    (proj / "adapters" / "adapter.py").write_text(
        ADAPTER.replace("N", str(n)).replace("REWARD", reward), encoding="utf-8")
    cap = proj / "seed_capability"
    cap.mkdir(exist_ok=True)
    (cap / "policy.txt").write_text("seed\n", encoding="utf-8")
    return proj


def main() -> int:
    c = Checker("baseline")
    run = import_run()
    c.require_main(run)

    ids = [f"t{i}" for i in range(12)]
    s1 = make_splits(list(ids), seed=7, ratios=(0.5, 0.25, 0.25))
    s2 = make_splits(list(ids), seed=7, ratios=(0.5, 0.25, 0.25))
    s3 = make_splits(list(ids), seed=8, ratios=(0.5, 0.25, 0.25))
    c.check((s1.train, s1.val, s1.test) == (s2.train, s2.val, s2.test),
            "same seed produced different splits (non-deterministic)",
            note="seeded split is deterministic")
    c.check((s1.train, s1.val, s1.test) != (s3.train, s3.val, s3.test),
            "different seeds produced identical splits (seed ignored)")
    c.check(not (set(s1.train) & set(s1.test)), "train/test overlap in a held-out split")

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        # Written once: a second ensure_splits with a DIFFERENT seed and ratios must
        # return the frozen partition, not re-partition (harness.py:114-115).
        rd = RunDir.create(tmp / "once", ts="b")
        proj = _project(tmp, "green", n=12, reward="1.0")
        adapter = load_adapter(proj)
        first = harness.ensure_splits(adapter, rd, seed=1, ratios=(0.5, 0.25, 0.25))
        again = harness.ensure_splits(adapter, rd, seed=99, ratios=(0.8, 0.1, 0.1))
        c.check((first.train, first.val, first.test) == (again.train, again.val, again.test),
                "ensure_splits re-partitioned an existing run dir (split NOT written once)",
                note="split written once: a second ensure_splits returns the frozen partition")
        c.check(rd.read_splits().train == first.train,
                "splits did not round-trip through the run dir",
                note="split frozen + reloadable from the run dir")

        # A red `cap-evolve check` must stop baseline BEFORE a run dir exists (#358).
        red = _project(tmp, "red", n=12, reward="random.random()")
        base = tmp / "red_base"
        rc = run.main(["--base", str(base), "--project", str(red),
                       "--capability", str(red / "seed_capability"), "--run-ts", "x"])
        c.check(rc != 0, "baseline accepted a red cap-evolve check (non-deterministic scorer)",
                note="red adapter refused: baseline exits non-zero before freezing a split")
        c.check(not list(base.glob("run_*")), "baseline created a run dir despite a red check")

        # A ratio split with no val (n=2 -> 1/0/1) must be refused, not silently run.
        tiny = _project(tmp, "tiny", n=2, reward="1.0")
        rc = run.main(["--base", str(tmp / "tiny_base"), "--project", str(tiny),
                       "--capability", str(tiny / "seed_capability"), "--run-ts", "x"])
        c.check(rc != 0, "baseline accepted a ratio split with an empty val set",
                note="degenerate ratio split (empty val/test) refused")

        # Green path: runs, warns about the tiny val, and EMITS the headroom verdict.
        with quiet() as buf:
            rc = run.main(["--base", str(tmp / "ok_base"), "--project", str(proj),
                           "--capability", str(proj / "seed_capability"), "--run-ts", "x"])
        out = json.loads(buf.getvalue()) if rc == 0 else {}
        c.check(rc == 0, "baseline failed on a healthy 12-task project")
        c.check(out.get("headroom_verdict") == "saturated" and out.get("headroom") == 0.0,
                f"headroom not emitted for a seed that already scores 1.0 on val: {out!r}",
                note="headroom is computed and emitted (saturated at val=1.0)")
        events = (Path(out.get("run_dir", tmp)) / "events.jsonl")
        text = events.read_text(encoding="utf-8") if events.exists() else ""
        c.check('"headroom"' in text, "no headroom event logged for orchestrate to read")
        c.check("val has only" in text, "no splits_warning logged for a 3-task val split")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
