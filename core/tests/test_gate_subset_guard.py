"""A candidate evaluated on a SUBSET of val must never clear the accept gate.

``screen.py --ids`` / ``evaluate.py --ids`` (#469) let the optimizer restrict an eval to
tasks it chose itself. That is fine for triage and train, and explicitly forbidden by
SKILL.md for the full-val accept gate — but the prohibition was prose only.
``harness.split_result_from_rollouts`` reconstructs a ``SplitResult`` purely from whatever
rollout files exist for a tag, so a subset-evaluated candidate's own ``coverage`` reads
1.0 (every task it measured, it measured) — invisible to ``gate.decide``'s low-coverage
guard, which compares coverage against nothing but itself.

``gate_check._frozen_coverage`` fixes this by measuring coverage against the run's actual
frozen val split instead, so the guard can see a subset for what it is regardless of why
it exists (a deliberate ``--ids``, or a half-finished eval).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "gate_check.py"


def _load_gate_check():
    spec = importlib.util.spec_from_file_location("_gc_subset_guard", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT.parent))
    spec.loader.exec_module(mod)
    return mod


class _Adapter:
    """5 tasks; a task passes iff the candidate's cfg file contains its id."""

    IDS = ["t0", "t1", "t2", "t3", "t4"]

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in self.IDS]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        cfg = Path(ctx) / "cfg.txt"
        text = cfg.read_text() if cfg.exists() else ""
        return Rollout(task_id=task.id, output=("pass" if task.id in text else "fail"))

    def score(self, task, rollout):
        from cap_evolve import Score
        ok = rollout.output == "pass"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                     trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir, edits=None):
        return None


def _setup(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits

    adapter = _Adapter()
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.txt").write_text("")  # 0/5

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="gsg")
    run_dir.write_splits(Splits(train=[], val=list(adapter.IDS), test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")
    harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                                split="val", tag="seed")

    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "cfg.txt").write_text(" ".join(adapter.IDS))  # would score 5/5 in full
    run_dir.snapshot("cand1", cand)
    return adapter, run_dir


def _run_gate(run_dir, **extra):
    gc = _load_gate_check()
    args = ["--run-dir", str(run_dir.root), "--candidate", "cand1",
            "--mode", "paired", "--no-footprint", "--k-se", "1.0"]
    for k, v in extra.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return gc, args


def test_subset_evaluated_candidate_is_refused_not_accepted(tmp_path, capsys):
    from cap_evolve import harness

    adapter, run_dir = _setup(tmp_path)
    # Only 2 of 5 frozen val ids measured — exactly what `evaluate.py --ids`/`screen.py
    # --ids` produce, and exactly the shape that would otherwise sail through as a
    # too-good-to-be-true accept.
    harness.evaluate_candidate(adapter, run_dir.candidate_dir("cand1"), run_dir=run_dir,
                                split="val", tag="cand1", ids=["t0", "t1"])

    gc, args = _run_gate(run_dir)
    rc = gc.main(args)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0

    assert out["candidate"]["coverage"] == 1.0, (
        "sanity: the per-attempted-task coverage IS 1.0 -- that is the blind spot")
    assert out["candidate"]["coverage_of_frozen_val"] < 0.6, out["candidate"]
    assert set(out["candidate"]["missing_from_frozen_val"]) == {"t2", "t3", "t4"}
    assert out["gate"]["indecisive"] is True
    assert out["gate"]["accept"] is False
    assert out["verdict"] == "indecisive"


def test_full_val_candidate_is_unaffected(tmp_path, capsys):
    """The fix must not turn a genuine full-val eval into a false indecisive."""
    from cap_evolve import harness

    adapter, run_dir = _setup(tmp_path)
    harness.evaluate_candidate(adapter, run_dir.candidate_dir("cand1"), run_dir=run_dir,
                                split="val", tag="cand1")  # full split, no ids=

    gc, args = _run_gate(run_dir)
    rc = gc.main(args)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0

    assert out["candidate"]["coverage_of_frozen_val"] == 1.0
    assert out["candidate"]["missing_from_frozen_val"] == []
    assert out["gate"]["indecisive"] is False
    assert out["gate"]["accept"] is True, out["gate"]
