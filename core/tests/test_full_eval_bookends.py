"""Start/end full-split evaluation guarantees for agent-optimize (and every other caller
of ``harness.baseline``/``harness.finalize``, since both are shared, not tau2-specific).

Start: ``baseline()`` must score the seed on the FULL train split too, not just val —
deduped (no second full eval) when train and val resolve to the identical id set.

End: ``finalize()`` must write the run's full seed-vs-best bookend (train + val + test)
into ``final.json``, reusing rollouts already on disk under the same tag instead of
re-buying a measurement that already happened, and without ever touching the test seal
more than once.

Uses the real, zero-cost ``toy_calc`` adapter (8 tasks; default 0.5/0.25/0.25 ratios give
train=4 val=2 test=2, all disjoint) so these are real evaluations, not mocks of the
function under test.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))


def _load_adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    return toy.Adapter()


def _seed_dir(tmp_path):
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    return seed


def _events(run_dir, kind=None, **fields):
    """Events from this run's events.jsonl matching ``kind`` + all of ``fields``."""
    out = []
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ev = json.loads(line)
        if kind is not None and ev.get("kind") != kind:
            continue
        if all(ev.get(k) == v for k, v in fields.items()):
            out.append(ev)
    return out


def test_baseline_evaluates_full_train_when_distinct_from_val(tmp_path):
    from cap_evolve import Budget, RunDir, harness

    adapter = _load_adapter()
    seed = _seed_dir(tmp_path)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t1", budget=Budget(max_iterations=1))

    harness.ensure_splits(adapter, run_dir, seed=0)  # 8 tasks -> train=4 val=2 test=2, disjoint
    splits = run_dir.read_splits()
    assert set(splits.train) != set(splits.val), "fixture assumption: default ratios must disjoint"

    harness.baseline(adapter, seed, run_dir=run_dir)

    baseline_payload = json.loads((run_dir.root / "baseline.json").read_text(encoding="utf-8"))
    assert "train" in baseline_payload, "a real (non-dedup) train split must be scored at baseline"
    assert baseline_payload["train"]["n_tasks"] == len(splits.train)
    assert "train_note" not in baseline_payload

    # A real full-split eval happened: exactly the frozen train ids, no subset.
    train_evals = _events(run_dir, kind="evaluate", split="train", tag="seed")
    assert len(train_evals) == 1
    val_evals = _events(run_dir, kind="evaluate", split="val", tag="seed")
    assert len(val_evals) == 1


def test_baseline_dedups_when_train_equals_val(tmp_path):
    """No wasted rollouts: identical train/val ids must not be scored twice."""
    from cap_evolve import Budget, RunDir, harness

    adapter = _load_adapter()
    seed = _seed_dir(tmp_path)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t2", budget=Budget(max_iterations=1))

    ids = [f"a{i}" for i in range(1, 9)]
    harness.ensure_splits(adapter, run_dir, split_ids={"train": ids, "val": ids, "test": ids[:2]})

    harness.baseline(adapter, seed, run_dir=run_dir)

    baseline_payload = json.loads((run_dir.root / "baseline.json").read_text(encoding="utf-8"))
    assert "train" not in baseline_payload, "train == val must not be re-evaluated as a separate cost"
    assert "identical to val" in baseline_payload.get("train_note", "")

    # Exactly one full-split eval happened (val); no second one for train.
    train_evals = _events(run_dir, kind="evaluate", split="train", tag="seed")
    assert len(train_evals) == 0
    val_evals = _events(run_dir, kind="evaluate", split="val", tag="seed")
    assert len(val_evals) == 1


def test_finalize_writes_full_seed_vs_best_bookend(tmp_path):
    from cap_evolve import Budget, RunDir, harness

    adapter = _load_adapter()
    seed = _seed_dir(tmp_path)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t3", budget=Budget(max_iterations=5, stall=2))

    harness.ensure_splits(adapter, run_dir, seed=0)
    splits = run_dir.read_splits()
    base_val = harness.baseline(adapter, seed, run_dir=run_dir)
    assert base_val.reward == 0.0  # seed prompt lacks [CALC]

    # Accept a real improving edit so best != seed, exercising the two-sided comparison.
    optimizer = harness.optimizer_from_command(
        ["python3",
         str(REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"),
         "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])
    import os
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    try:
        step = harness.run_step(adapter, run_dir=run_dir,
                                parent_dir=run_dir.candidate_dir("seed"),
                                optimizer=optimizer, instructions="add [CALC]",
                                current_val=base_val,
                                gate_kwargs={"mode": "significant", "k_se": 1.0})
    finally:
        os.environ.clear()
        os.environ.update(old)
    assert step["accepted"] is True
    assert run_dir.best_id != "seed"

    best_dir = run_dir.candidate_dir(run_dir.best_id)
    seed_dir_snap = run_dir.candidate_dir("seed")
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir,
                               baseline_dir=seed_dir_snap)

    # The classic fields are unchanged.
    assert payload["test"]["reward"] == 1.0
    assert payload["test_baseline"]["reward"] == 0.0

    # The new bookend: both candidates, every split.
    for who in ("seed", "best"):
        assert who in payload, f"final.json must carry a {who!r} bookend"
        for split in ("train", "val", "test"):
            assert split in payload[who], f"{who}.{split} missing from the bookend"
    assert payload["best"]["train"]["reward"] == 1.0
    assert payload["seed"]["train"]["reward"] == 0.0
    assert payload["best"]["val"]["reward"] == 1.0
    assert payload["seed"]["val"]["reward"] == 0.0
    assert payload["train_equals_val"] is False

    # val is FREE: reused straight off rollouts already on disk. No new full-split val
    # eval fired during finalize (the seed's own baseline eval, and the accepted
    # candidate's own gate eval, are the only two).
    val_evals = _events(run_dir, kind="evaluate", split="val")
    assert len(val_evals) == 2  # seed (baseline) + the accepted candidate (its gate eval)

    persisted = json.loads((run_dir.root / "final.json").read_text(encoding="utf-8"))
    assert persisted == payload

    # The seal held: a second finalize is refused.
    from cap_evolve import TestSealError
    with pytest.raises(TestSealError):
        harness.finalize(adapter, run_dir=run_dir, best_dir=best_dir, baseline_dir=seed_dir_snap)


def test_finalize_reuses_rollouts_instead_of_re_measuring_train(tmp_path):
    """The 'don't double-pay' guarantee: seed's train was already fully measured at
    baseline time, so finalize must reuse those rollouts rather than buying a second
    full-split train eval under the same tag."""
    from cap_evolve import Budget, RunDir, harness

    adapter = _load_adapter()
    seed = _seed_dir(tmp_path)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t4", budget=Budget(max_iterations=1))

    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)  # scores seed on train too (tag="seed")
    assert len(_events(run_dir, kind="evaluate", split="train", tag="seed")) == 1

    seed_dir_snap = run_dir.candidate_dir("seed")
    payload = harness.finalize(adapter, run_dir=run_dir, best_dir=seed_dir_snap,
                               baseline_dir=seed_dir_snap)

    # best == seed here, so both bookend sides reuse the SAME train rollouts baseline
    # already wrote — no second full-split train eval for tag "seed" at finalize time.
    assert len(_events(run_dir, kind="evaluate", split="train", tag="seed")) == 1
    assert payload["best"]["train"].get("reused_rollouts") is True
    assert payload["seed"]["train"].get("reused_rollouts") is True
    assert payload["best"]["train"]["reward"] == payload["seed"]["train"]["reward"] == 0.0
