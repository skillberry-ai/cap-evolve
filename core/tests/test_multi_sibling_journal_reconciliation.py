"""Repro for #429: N sibling candidates proposed in one shared session/workdir all carry
the SAME multi-block JOURNAL.md tail (every sibling's own real '## Iteration' block).
Reconciling them one at a time used to fold only the first sibling's block, then discard
every other sibling's real, distinct entry as a false "duplicate handover" — because the
whole tail (all N blocks) became a substring of the run-level journal after the first
fold. Assert all N candidates' real content survives, with no false duplicate stamp, and
that a genuine collision (nothing left unbooked) is logged rather than silent.
"""

import json

from cap_evolve import Budget, RunDir, harness


def _sibling_workdir(tmp_path, name, entries):
    """A workdir whose JOURNAL.md tail holds ALL siblings' blocks (as a real batch does)."""
    workdir = tmp_path / name
    workdir.mkdir()
    blocks = "\n\n".join(entries)
    (workdir / "JOURNAL.md").write_text(
        harness._JOURNAL_SEED + "\n\n" + harness._JOURNAL_MARK + "\n\n" + blocks + "\n",
        encoding="utf-8")
    return workdir


def test_three_siblings_each_keep_their_own_real_journal_entry(tmp_path):
    entries = [
        "## Iteration i1_tools_netguard — added a network egress allowlist check",
        "## Iteration i1_prompt_verify_tier — require get_user_details before tier questions",
        "## Iteration i1_prompt_confirm_final — ask for confirmation before final booking",
    ]
    cids = ["i1_tools_netguard", "i1_prompt_verify_tier", "i1_prompt_confirm_final"]

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="sib3", budget=Budget(max_iterations=3))

    for cid in cids:
        workdir = _sibling_workdir(tmp_path, cid, entries)
        harness._reconcile_journal(workdir, run_dir, cid, accepted=False, val=0.5, delta=-0.02,
                                   reason=f"{cid}: rejected")

    journal = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")

    # Every sibling's REAL, distinct headline survives.
    assert "added a network egress allowlist check" in journal
    assert "require get_user_details before tier questions" in journal
    assert "ask for confirmation before final booking" in journal

    # None of them were falsely stamped as a duplicate handover.
    assert "duplicate handover" not in journal

    # Each candidate got exactly one RESULT stamp of its own.
    for cid in cids:
        assert journal.count(f"<!-- {cid}:") == 1


def test_genuine_stale_carry_forward_is_still_deduped(tmp_path):
    """Not every same-tail collision is a sibling batch: a workdir cloned from the last
    round that appends nothing new must still be deduped as before (no re-booking)."""
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="stale", budget=Budget(max_iterations=2))

    workdir1 = _sibling_workdir(tmp_path, "cand_1", ["## Iteration cand_1 — did the first thing"])
    harness._reconcile_journal(workdir1, run_dir, "cand_1", accepted=False, val=0.5, delta=-0.02,
                               reason="cand_1: rejected")

    # cand_2's workdir is a stale clone carrying cand_1's entry forward unchanged (no marker).
    workdir2 = tmp_path / "cand_2"
    workdir2.mkdir()
    journal_so_far = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    (workdir2 / "JOURNAL.md").write_text(journal_so_far, encoding="utf-8")
    harness._reconcile_journal(workdir2, run_dir, "cand_2", accepted=False, val=0.4, delta=-0.1,
                               reason="cand_2: rejected")

    journal = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    assert "## Iteration cand_2 — (duplicate handover; optimizer re-appended a prior entry unchanged)" in journal
    assert journal.count("did the first thing") == 1


def test_sibling_collision_with_no_unbooked_block_left_is_logged(tmp_path):
    """If every block in a multi-block tail is already booked (a genuine collision, not
    just one sibling among several still-pending), it must be logged, not silent."""
    entries = [
        "## Iteration cand_a — did thing A",
        "## Iteration cand_b — did thing B",
    ]
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="collide", budget=Budget(max_iterations=2))

    workdir_a = _sibling_workdir(tmp_path, "cand_a", entries)
    harness._reconcile_journal(workdir_a, run_dir, "cand_a", accepted=False, val=0.5, delta=-0.02,
                               reason="cand_a: rejected")
    workdir_b = _sibling_workdir(tmp_path, "cand_b", entries)
    harness._reconcile_journal(workdir_b, run_dir, "cand_b", accepted=False, val=0.4, delta=-0.1,
                               reason="cand_b: rejected")

    # A third call with the SAME already-fully-booked batch (nothing left unbooked) hits
    # the dedup guard for real, and must be logged as a collision.
    workdir_c = _sibling_workdir(tmp_path, "cand_c", entries)
    harness._reconcile_journal(workdir_c, run_dir, "cand_c", accepted=False, val=0.3, delta=-0.2,
                               reason="cand_c: rejected")

    events = [json.loads(ln) for ln in run_dir.events_path.read_text(encoding="utf-8").splitlines()
              if ln.strip()]
    assert any(e.get("kind") == "journal_sibling_collision" and e.get("candidate") == "cand_c"
               for e in events)
