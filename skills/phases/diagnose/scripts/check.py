"""Contract: diagnose emits a well-formed reflective dataset (the real task INPUT, a
pointer to the full trace) and clusters failures by root cause — one cause under
several phrasings must NOT fragment, and several causes under one scorer preamble
must NOT collapse.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run, temp_run_dir, write_val_rollout


def _clusters_of(run, feedbacks: dict[str, str]) -> list[dict]:
    """Cluster a set of ``task_id -> feedback`` failures, records-free."""
    return run.diagnose([{"input": {}, "rollout": {"output": ""},
                          "score": {"task_id": t, "reward": 0.0, "feedback": f}}
                         for t, f in sorted(feedbacks.items())])["clusters"]


def main() -> int:
    c = Checker("diagnose")
    run = import_run()
    c.require_main(run)

    with tempfile.TemporaryDirectory() as d:
        rd, _ = temp_run_dir(Path(d))
        # two failures with the SAME root cause but different numbers, one pass.
        write_val_rollout(rd, "a", reward=0.0, feedback="Expected 5 but got 7",
                          task_input={"expr": "2+3"}, output="7")
        write_val_rollout(rd, "b", reward=0.0, feedback="Expected 9 but got 2",
                          task_input={"expr": "4+5"}, output="2")
        write_val_rollout(rd, "c", reward=1.0, feedback="ok",
                          task_input={"expr": "1+1"}, output="2")

        records = run._load_records(rd, "seed")
        result = run.diagnose(records)

        rd_set = result["reflective_dataset"]
        c.check(len(rd_set) == 2, f"expected 2 failing entries, got {len(rd_set)}")
        c.check(result["kept_good"] == ["c"], f"passing task not kept-good: {result['kept_good']}")

        # Inputs must be the real task INPUT, not the task id.
        entry = next(e for e in rd_set if e["task_id"] == "a")
        c.check(entry["Inputs"] == {"expr": "2+3"},
                f"Inputs carries the wrong thing (should be the task input): {entry['Inputs']}",
                note="reflective dataset carries the actual task input")
        c.check(entry["Generated Outputs"] == "7", "Generated Outputs missing the rollout output")

        # Every entry must be traceable back to its FULL trace, or the failure SITE
        # (which is half the cluster key) is unrecoverable from the entry alone.
        c.check(Path(entry["Trajectory"]).exists(),
                f"Trajectory pointer does not resolve: {entry['Trajectory']}",
                note="each reflective entry points at its full trace")
        # ...and when the RUNNER has a native trace store, that pointer comes from
        # adapter.trajectories(split) — never from a hardcoded trace layout. A phase
        # skill that guessed the path would be bound to one runner.
        proj = Path(d) / "project"
        (proj / "adapters").mkdir(parents=True)
        (proj / "adapters" / "adapter.py").write_text(
            "from pathlib import Path\n"
            "from cap_evolve import CapabilityAdapter, Rollout, Score\n"
            "class Adapter(CapabilityAdapter):\n"
            "    def tasks(self, split): return []\n"
            "    def run_target(self, task, ctx, *, seed=0):\n"
            "        return Rollout(task_id='x', output='')\n"
            "    def score(self, task, rollout): return Score(task_id='x', reward=0.0)\n"
            "    def trajectories(self, split, ctx=None):\n"
            "        return Path('/native') / split\n", encoding="utf-8")
        native = run.trace_dir(str(proj), "val")
        c.check(native is not None and native.endswith("val"),
                f"adapter.trajectories(split) was not used for the trace path: {native}",
                note="trace location comes from adapter.trajectories(split), never a "
                     "hardcoded trace schema")
        c.check(run.diagnose(records, "root-cause", native)["reflective_dataset"][0]
                ["Trajectory"] == native,
                "the adapter's native trace dir did not reach the reflective dataset")
        c.check(run.trace_dir(None, "val") is None
                and run.trace_dir(str(Path(d) / "nope"), "val") is None,
                "trace_dir must degrade to None with no project / no adapter",
                note="a missing trace pointer never blocks a diagnosis")

        # the two same-root-cause failures cluster together under one signature.
        c.check(len(result["clusters"]) == 1
                and result["clusters"][0]["tasks"] == ["a", "b"],
                f"clustering did not group same-cause failures: {result['clusters']}",
                note="same cause, different values -> one cluster")
        c.check(result["clusters"][0]["score_lost"] == 2.0,
                f"cluster is not ranked by score lost: {result['clusters']}",
                note="clusters carry the score they can recover")

        # --split reads a DIFFERENT split's rollouts, and val stays the default. Four
        # other algorithms call this phase without --split, so the default must not
        # move; and diagnosing TRAIN must not silently return val's failures.
        c.check(run._load_records(rd, "seed", "train") == [],
                "diagnose read val rollouts when asked for train",
                note="--split train reads rollouts/train, never rollouts/val")
        train_dir = rd.rollouts / "train"
        train_dir.mkdir(parents=True, exist_ok=True)
        (train_dir / "z__seed__t0.json").write_text(
            '{"input": {"expr": "8+8"}, "rollout": {"task_id": "z", "output": "3", '
            '"error": null}, "score": {"task_id": "z", "reward": 0.0, '
            '"feedback": "Expected 16 but got 3", "n": 1, "stderr": 0.0, '
            '"trial_rewards": [0.0], "raw": {"errored": false}}}', encoding="utf-8")
        tr = run.diagnose(run._load_records(rd, "seed", "train"))
        c.check([e["task_id"] for e in tr["reflective_dataset"]] == ["z"],
                f"train diagnosis returned the wrong tasks: {tr['reflective_dataset']}",
                note="train is diagnosable — the honest learning surface when the gate "
                     "scores val")
        c.check([e["task_id"] for e in run.diagnose(
                    run._load_records(rd, "seed"))["reflective_dataset"]] == ["a", "b"],
                "the default split is no longer val — that would change every "
                "algorithm that calls diagnose without --split")

        # REGRESSION 1 — one root cause, three phrasings. A lexical prefix key splits
        # this into three clusters and the optimizer then writes three narrow patches.
        one = _clusters_of(run, {
            "p": "Task failed: the agent did not confirm the change with the user",
            "q": "Agent omitted required confirmation step",
            "r": "Missing confirmation before the write",
        })
        c.check(len(one) == 1 and one[0]["tasks"] == ["p", "q", "r"],
                f"one root cause fragmented into {len(one)} clusters: {one}",
                note="one cause under 3 phrasings -> 1 cluster (no fragmentation)")

        # REGRESSION 2 — three causes behind one long scorer preamble. A first-N-token
        # key collapses them into one cluster and the whole signal is lost.
        pre = "Grading failed for this trajectory because the expected outcome was not met: "
        many = _clusters_of(run, {
            "p": pre + "missing confirmation before the write",
            "q": pre + "wrong payment id supplied to the refund",
            "r": pre + "refused a valid booking request",
        })
        c.check(len(many) >= 3,
                f"3 distinct causes collapsed into {len(many)} cluster(s) behind a "
                f"shared preamble: {many}",
                note="shared scorer preamble is stripped -> distinct causes stay distinct")

        # Determinism: same input twice, byte-identical clusters.
        import json as _json
        again = _clusters_of(run, {
            "p": "Task failed: the agent did not confirm the change with the user",
            "q": "Agent omitted required confirmation step",
            "r": "Missing confirmation before the write",
        })
        c.check(_json.dumps(one, sort_keys=True) == _json.dumps(again, sort_keys=True),
                "clustering is not deterministic across runs",
                note="identical input -> identical output")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
