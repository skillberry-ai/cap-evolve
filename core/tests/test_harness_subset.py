"""``evaluate_candidate(ids=…)`` — the subset-eval seam the screen ladder runs on.

Additive and backward-compatible: ``ids=None`` must behave exactly as before.
"""

from __future__ import annotations

import json
from pathlib import Path

from cap_evolve import Budget, RunDir, harness
from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir


def _run(tmp_path: Path):
    adapter = SyntheticAdapter(n=12)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget())
    harness.ensure_splits(adapter, run_dir, seed=0)
    seed = seed_capability_dir(tmp_path, level=3)
    return adapter, run_dir, seed


def _events(run_dir, kind):
    out = []
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("kind") == kind:
            out.append(rec)
    return out


def test_full_split_eval_is_unchanged_when_ids_is_none(tmp_path):
    adapter, run_dir, seed = _run(tmp_path)
    val_ids = run_dir.read_splits().ids("val")
    res = harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                                     n_trials=1, tag="full")
    assert res.n_tasks == len(val_ids)
    assert run_dir.spent.metric_calls == len(val_ids)
    ev = _events(run_dir, "evaluate")[-1]
    assert "subset" not in ev and "subset_ids" not in ev


def test_subset_eval_scores_and_charges_only_the_subset(tmp_path):
    adapter, run_dir, seed = _run(tmp_path)
    val_ids = run_dir.read_splits().ids("val")
    pick = sorted(val_ids)[:2]
    res = harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                                     n_trials=1, tag="sub", ids=pick)
    assert sorted(pt["task_id"] for pt in res.per_task) == pick
    assert res.n_tasks == 2
    assert run_dir.spent.metric_calls == 2, "a subset eval must not be billed as a full split"
    files = sorted(p.name for p in (run_dir.rollouts / "val").glob("*__sub__t*.json"))
    assert len(files) == 2


def test_subset_eval_is_flagged_in_the_event_stream(tmp_path):
    """A subset reward is a triage signal, so the audit log must say it is one."""
    adapter, run_dir, seed = _run(tmp_path)
    pick = sorted(run_dir.read_splits().ids("val"))[:2]
    harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                               n_trials=1, tag="sub", ids=pick)
    ev = _events(run_dir, "evaluate")[-1]
    assert ev["subset"] is True and sorted(ev["subset_ids"]) == pick


def test_ids_can_never_widen_a_split(tmp_path):
    """Passing a test/train id while scoring val must not smuggle it in."""
    adapter, run_dir, seed = _run(tmp_path)
    splits = run_dir.read_splits()
    outsider = splits.ids("test")[0]
    pick = [sorted(splits.ids("val"))[0], outsider, "does-not-exist"]
    res = harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                                     n_trials=1, tag="sub", ids=pick)
    assert [pt["task_id"] for pt in res.per_task] == [sorted(splits.ids("val"))[0]]
    assert not run_dir.read_splits().test_used


def test_a_subset_tag_does_not_collide_with_the_full_val_tag(tmp_path):
    """``<tag>__screenN`` rollouts must not be read back as ``<tag>``'s full-val score.

    This is the whole reason the screen uses its own tag: if the glob matched, a 2-task
    triage would overwrite a 3-task gate score.
    """
    adapter, run_dir, seed = _run(tmp_path)
    val_ids = sorted(run_dir.read_splits().ids("val"))
    harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                               n_trials=1, tag="cand_1")
    harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                               n_trials=1, tag="cand_1__screen1", ids=val_ids[:1])
    full = harness.split_result_from_rollouts(run_dir, "cand_1", "val")
    scr = harness.split_result_from_rollouts(run_dir, "cand_1__screen1", "val")
    assert full.n_tasks == len(val_ids)
    assert scr.n_tasks == 1


# ---- CAPEVOLVE_WORKERS: opt-in concurrency for hosts with no --workers flag ----

def test_workers_default_stays_serial(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_WORKERS", raising=False)
    assert harness._resolve_workers(None) == 1


def test_workers_env_var_is_honoured_when_no_argument_is_given(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_WORKERS", "4")
    assert harness._resolve_workers(None) == 4
    assert harness._resolve_workers(1) == 1, "an explicit argument must win over the env"


def test_a_bad_workers_env_var_never_crashes_an_evaluation(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_WORKERS", "lots")
    assert harness._resolve_workers(None) == 1
