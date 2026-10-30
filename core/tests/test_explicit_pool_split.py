"""A split file may name the pooled F/C partition itself; pooled mode then adopts it and still seals C."""

import json

import pytest

from cap_evolve import RunDir, harness  # noqa: E402

F = [f"f{i}" for i in range(6)]
C = [f"c{i}" for i in range(5)]
T = [f"t{i}" for i in range(4)]


def _run(tmp_path, split_mode="pooled"):
    spec = tmp_path / "capevolve.yaml"
    spec.write_text(f"split_mode: {split_mode}\npromotion_rule: P2\n")
    run_dir = RunDir.create(tmp_path / "proj" / ".capevolve", ts="x")
    run_dir.log_event("spec_resolved", spec=str(spec))
    return run_dir


def test_explicit_feedback_and_confirm_become_the_partition(tmp_path):
    run_dir = _run(tmp_path)
    harness.ensure_splits(None, run_dir, seed=3, split_ids={"feedback": F, "confirm": C, "test": T})
    s = harness.ensure_pooled(run_dir)
    assert (s.feedback, s.confirm, s.test) == (F, C, T)
    assert json.loads(run_dir.splits_path.read_text())["confirm"] == []          # C still sealed
    assert json.loads((run_dir.sealed_dir / "splits_full.json").read_text())["confirm"] == C
    ev = [json.loads(l) for l in run_dir.events_path.read_text().splitlines() if '"pooled_split"' in l]
    assert ev[0]["explicit"] is True and ev[0]["n_confirm"] == len(C)
    assert not any(t in run_dir.events_path.read_text() for t in C)            # ids never reach the log


def test_the_explicit_partition_is_never_redrawn(tmp_path):
    run_dir = _run(tmp_path)
    harness.ensure_splits(None, run_dir, seed=3, split_ids={"feedback": F, "confirm": C, "test": T})
    first = harness.ensure_pooled(run_dir)
    again = harness.ensure_pooled(run_dir, confirm_fraction=0.9)
    assert (again.feedback, again.confirm) == (first.feedback, first.confirm)


def test_refused_outside_pooled_mode(tmp_path):
    run_dir = _run(tmp_path, split_mode="legacy")
    with pytest.raises(ValueError, match="split_mode: pooled"):
        harness.ensure_splits(None, run_dir, split_ids={"feedback": F, "confirm": C, "test": T})


@pytest.mark.parametrize("ids, match", [
    ({"feedback": F, "confirm": F[:1], "test": T}, "feedback and confirm overlap"),
    ({"feedback": F, "confirm": C, "test": C[:1]}, "confirm and test overlap"),
    ({"feedback": F, "confirm": [], "test": T}, "non-empty"),
    ({"feedback": F, "confirm": C, "train": F, "test": T}, "not both"),
])
def test_malformed_explicit_splits_are_refused(tmp_path, ids, match):
    with pytest.raises(ValueError, match=match):
        harness.ensure_splits(None, _run(tmp_path), split_ids=ids)


def test_legacy_split_files_are_untouched(tmp_path):
    run_dir = _run(tmp_path, split_mode="legacy")
    s = harness.ensure_splits(None, run_dir, split_ids={"train": F, "val": C, "test": T})
    assert not s.explicit_pool
    assert "explicit_pool" not in json.loads(run_dir.splits_path.read_text())
