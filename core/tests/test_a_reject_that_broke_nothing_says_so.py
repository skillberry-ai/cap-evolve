"""A reject's journal guidance assumed the reject was caused by a regression. Usually it isn't.

The RESULT line the framework stamps under every journal entry exists to tell the NEXT iteration
what to do differently. For a reject it said, unconditionally:

    its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above,
    dropping/redesigning the ones that did.

Read that against the line it was stamped on, from smoke spreadsheetbench run 33046360451:

    REJECTED (champion unchanged) · val=0.553 Δ=+0.043 · fixed={47484, 53161} · broke={—}

The candidate fixed two tasks, broke none, and gained +0.043 — it was rejected because +0.043 did
not clear a 0.048 threshold. So the guidance instructed the next iteration to drop nothing and
redesign nothing, while telling it the batch was reverted: the one sentence that was supposed to
say what to do next said nothing actionable at all. Worse, "redesign the ones that did" invites a
rewrite of edits that had just been measured HELPING, which is how a run talks itself out of its
own best lever.

A reject with no regressions is a different instruction from a reject with them: the edits did not
harm anything, they simply did not clear the bar, so the lever is more measurement power or a
bigger effect — not a redesign. This is not agent-mode specific; every algorithm's below-threshold
reject reaches the same stamp through ``record_iteration``.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _journal_after(tmp_path, *, broke: list[str], fixed: list[str], accepted=False,
                   indecisive=False) -> str:
    """Stamp a journal RESULT line for a candidate with a known per-task impact.

    The impact is derived from rollouts on disk, so it is staged by writing the parent's and the
    candidate's per-task rewards rather than by patching the reader.
    """
    import json

    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=6)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)

    tasks = sorted(set(broke) | set(fixed) | {"steady"})
    roll = run_dir.rollouts / "val"
    roll.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        # parent passes what the candidate broke, fails what the candidate fixed
        par = 1.0 if (task in broke or task == "steady") else 0.0
        cand = 0.0 if task in broke else 1.0
        (roll / f"{task}__seed__t0.json").write_text(
            json.dumps({"score": {"task_id": task, "reward": par}}), encoding="utf-8")
        (roll / f"{task}__cand_x__t0.json").write_text(
            json.dumps({"score": {"task_id": task, "reward": cand}}), encoding="utf-8")

    workdir = tmp_path / "wd"
    workdir.mkdir()
    harness.record_iteration(run_dir, workdir, "cand_x", parent_id="seed", accepted=accepted,
                             reason="below threshold", val=0.553, parent_val=0.51,
                             indecisive=indecisive)
    return (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")


def test_a_reject_with_no_regressions_is_not_told_to_redesign_the_edits_that_broke_a_task(
        tmp_path):
    text = _journal_after(tmp_path, broke=[], fixed=["47484", "53161"])
    entry = text[text.rindex("RESULT (framework"):]
    assert "broke={—}" in entry, f"the fixture did not produce a no-regression reject: {entry}"
    assert "dropping/redesigning the ones that did" not in entry, (
        "the reject guidance still tells the next iteration to redesign the edits that broke a "
        f"task, on a round where nothing broke: {entry}")


def test_a_reject_with_no_regressions_says_what_to_do_instead(tmp_path):
    """Not enough to delete the wrong sentence — the line exists to say what to do next."""
    text = _journal_after(tmp_path, broke=[], fixed=["47484", "53161"])
    entry = text[text.rindex("RESULT (framework"):]
    assert "did not clear" in entry or "below the bar" in entry or "threshold" in entry, (
        f"the reject does not say the batch failed on the BAR rather than on a regression: {entry}")
    # The two real levers for an unregressed near-miss.
    assert "trials" in entry or "power" in entry, (
        f"no mention of buying measurement power: {entry}")
    assert "fixed" in entry, f"the tasks it DID fix are not offered as the thing to build on: {entry}"


def test_a_reject_that_did_break_tasks_still_gets_the_redesign_guidance(tmp_path):
    """Control: the original guidance is right when a regression actually caused the reject."""
    text = _journal_after(tmp_path, broke=["160-6"], fixed=[])
    entry = text[text.rindex("RESULT (framework"):]
    assert "160-6" in entry and "dropping/redesigning the ones that did" in entry, (
        f"the regression case lost its guidance: {entry}")


def test_no_regression_claim_is_not_made_when_there_was_nothing_to_compare(tmp_path):
    """``_candidate_task_impact`` returns None when either side has no rollouts, and then
    ``broke={—}`` means "unknown", not "nothing broke". Claiming no regressions there would be
    an invented fact — the exact failure mode this file is about, inverted."""
    import json

    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=6)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    # Candidate rollouts only — no parent side, so no comparison is possible.
    roll = run_dir.rollouts / "val"
    roll.mkdir(parents=True, exist_ok=True)
    (roll / "t1__cand_x__t0.json").write_text(
        json.dumps({"score": {"task_id": "t1", "reward": 1.0}}), encoding="utf-8")
    workdir = tmp_path / "wd"
    workdir.mkdir()
    harness.record_iteration(run_dir, workdir, "cand_x", parent_id="seed", accepted=False,
                             reason="below threshold", val=0.553, parent_val=0.51)
    entry = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    entry = entry[entry.rindex("RESULT (framework"):]
    assert "no task that was passing" not in entry, (
        f"claims nothing regressed when no per-task comparison existed at all: {entry}")


def test_an_accept_is_unchanged(tmp_path):
    text = _journal_after(tmp_path, broke=[], fixed=["47484"], accepted=True)
    entry = text[text.rindex("RESULT (framework"):]
    assert "ACCEPTED (new champion)" in entry and "did not clear" not in entry, entry
