"""A measured drop on a 0-1 reward was reported as "nothing regressed".

``_classify_moves`` called a task ``broke`` only when the parent scored a FULL 1.0, and
``fixed`` only when the candidate reached one. On a continuous reward — an LLM judge's 0-1
score, a partial-credit grader — most tasks never reach 1.0, so a resolved move landed in no
list at all. From the rfe-creator full-v2 run (33 val tasks x 3 trials, Sonnet judge):

    cand_0001  paired Δ̄=-0.0858  broke=[]  fixed=[]
               rfe-case-005 0.70 -> 0.32, rfe-case-015 0.67 -> 0.32, rfe-case-014 0.70 -> 0.48

and the journal RESULT stamp took the "rejected with nothing regressed" branch on all three
iterations: "no task that was passing under the parent regressed ... Keep the edits". The
batch that caused those drops was the one the optimizer was told to build on.

``broke`` / ``fixed`` keep their pass/fail meaning (the opt-in ``gate_max_broke`` veto reads
them); resolved moves that cross neither are now ``regressed`` / ``improved``, published in
the step record, LEDGER.md and the RESULT stamp, and a regression steers the reject guidance
the same way a break does.
"""

from __future__ import annotations

import json

from cap_evolve import Budget, RunDir, harness, skillopt


def _pt(task_id, reward, stderr=0.0):
    return {"task_id": task_id, "reward": reward, "stderr": stderr, "n": 3,
            "raw": {"n_trials": 3, "valid_trials": 3}}


def test_resolved_moves_below_one_are_regressed_or_improved_with_their_values():
    par = {"a": 0.70, "b": 0.55, "c": 1.00, "d": 0.50, "e": 0.70}
    cand = {"a": 0.32, "b": 0.70, "c": 0.50, "d": 1.00, "e": 0.68}
    se = {t: 0.02 for t in par}
    mv = harness._classify_moves(par, cand, se, se, list(par))
    assert mv["regressed"] == ["a"]
    assert mv["improved"] == ["b"]
    assert mv["broke"] == ["c"] and mv["fixed"] == ["d"]      # pass/fail meaning unchanged
    assert mv["unresolved"] == ["e"]                           # 0.02 < 2·SE: no claim
    assert mv["values"]["a"] == [0.70, 0.32]
    assert "e" not in mv["values"]


def test_gate_time_movement_carries_the_new_lists():
    mv = harness.movement([_pt("t1", 0.70), _pt("t2", 0.55)],
                          [_pt("t1", 0.32), _pt("t2", 0.70)])
    assert mv["regressed"] == ["t1"] and mv["improved"] == ["t2"]
    assert mv["broke"] == [] and mv["fixed"] == []
    empty = harness.movement([], [])
    assert empty["regressed"] == [] and empty["improved"] == [] and empty["n_shared"] == 0


def _run_with(tmp_path, moves: dict) -> RunDir:
    """A run dir whose seed and cand_x rollouts carry the given {task: (parent, cand)} rewards."""
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=6)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    roll = run_dir.rollouts / "val"
    roll.mkdir(parents=True, exist_ok=True)
    for f in roll.glob("*.json"):
        f.unlink()
    for task, (par, cand) in moves.items():
        for tag, r in (("seed", par), ("cand_x", cand)):
            (roll / f"{task}__{tag}__t0.json").write_text(
                json.dumps({"score": {"task_id": task, "reward": r}}), encoding="utf-8")
    return run_dir


def _journal(tmp_path, moves: dict) -> str:
    run_dir = _run_with(tmp_path, moves)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    harness.record_iteration(run_dir, workdir, "cand_x", parent_id="seed", accepted=False,
                             reason="below threshold", val=0.57, parent_val=0.66)
    text = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    return text[text.rindex("RESULT (framework"):]


def test_a_reject_that_regressed_a_judge_scored_task_is_not_told_nothing_regressed(tmp_path):
    entry = _journal(tmp_path, {"rfe-005": (0.70, 0.32), "rfe-021": (0.55, 0.70),
                                "steady": (0.70, 0.70)})
    assert "regressed={rfe-005 (0.70→0.32)}" in entry, entry
    assert "improved={rfe-021 (0.55→0.70)}" in entry, entry
    assert "broke={—}" in entry
    assert "no task measurably regressed" not in entry, (
        f"a measured 0.70 -> 0.32 drop was stamped as a harmless reject: {entry}")
    assert "break or regress a task above" in entry


def test_a_reject_with_only_gains_below_one_still_gets_the_power_guidance(tmp_path):
    entry = _journal(tmp_path, {"rfe-021": (0.55, 0.70), "steady": (0.70, 0.70)})
    assert "regressed={—}" in entry and "improved={rfe-021 (0.55→0.70)}" in entry
    assert "no task measurably regressed" in entry
    assert "`fixed`/`improved` tasks" in entry


def test_the_ledger_publishes_regressed_and_improved(tmp_path):
    run_dir = _run_with(tmp_path, {"rfe-005": (0.70, 0.32), "rfe-021": (0.55, 0.70)})
    run_dir.log_event("step", candidate="cand_x", parent="seed", accept=False, val=0.51,
                      parent_val=0.625)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    harness._build_ledger(workdir, run_dir)
    ledger = (workdir / "LEDGER.md").read_text(encoding="utf-8")
    assert "| regressed (dropped, never passing) | improved (rose, still < 1) |" in ledger
    row = next(line for line in ledger.splitlines() if line.startswith("| 1 | cand_x"))
    assert "{rfe-005 (0.70→0.32)}" in row and "{rfe-021 (0.55→0.70)}" in row, row


def test_skillopt_counts_a_drop_below_one_as_regressed():
    prev = [_pt("a", 0.70, 0.02), _pt("b", 0.20, 0.02), _pt("c", 1.0, 0.0)]
    cur = [_pt("a", 0.32, 0.02), _pt("b", 0.20, 0.02), _pt("c", 1.0, 0.0)]
    cats = skillopt._categorize(prev, cur)
    assert [pt["task_id"] for pt in cats["regressed"]] == ["a"]
    assert [pt["task_id"] for pt in cats["persistent_fail"]] == ["b"]
    assert [pt["task_id"] for pt in cats["stable_success"]] == ["c"]
