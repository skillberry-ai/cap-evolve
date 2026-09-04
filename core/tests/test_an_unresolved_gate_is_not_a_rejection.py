"""``round.py`` can return a verdict of ``inconclusive``; ``commit.py`` could only book accept
or reject. So an unresolvable measurement had to be recorded as one of two things it was not.

``round.py`` marks a candidate ``inconclusive`` when its verdict is not stable across the round's
byte-identical control replicates (``verdict_stable: false``) — it accepts against one replicate
and rejects against another, so the round cannot separate the edit from re-measurement. Its own
`reading` says such a candidate is "never accepted … Re-run it with more trials before believing
either answer". That is a THIRD outcome, and the loop had no way to write it down.

Observed on smoke spreadsheetbench run 33046360451 round i1: cand_2 at +0.0433 against a
threshold of 0.0492, `verdict_by_reference: {ctl_null_i1: reject, ctl_null_i1r1: accept}`. The
agent's only options were to book a reject — asserting the gate refuted an edit it had not — or
to book nothing, which ``host._unbooked_rounds`` correctly reports as a defective run.

Booking it as a reject is not a cosmetic misfiling. ``update_spent(accepted=False)`` increments
the STALL counter, and ``budget_exhausted()`` stops the run when stall hits its cap (3 here,
already at 1). Stall means "the optimizer has run out of ideas" — the one thing an ambiguous
measurement is no evidence of. Two ambiguous rounds could therefore end a run for a reason that
never happened, on a benchmark whose replicate noise makes ambiguity the common case.

``harness.record_iteration`` has supported exactly this since #216/#224 — ``indecisive=True``
charges the iteration and leaves the stall counter alone — and the deterministic hill-climb uses
it. Agent mode simply could not reach it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

# The real round_i1.json from run 33046360451, trimmed: an unstable verdict.
UNSTABLE_TABLE = {
    "parent": {"tag": "seed", "reward": 0.51, "stderr": 0.1319184184858296, "n_tasks": 10},
    "gate_reference": {"tag": "ctl_null_i1", "mode": "control", "reward": 0.4966666666666667},
    "gated_against": {"tag": "ctl_null_i1", "mode": "control"},
    "null_delta_between_control_replicates": 0.0167,
    "evidence_bar": {"value": 0.0167, "basis": "gap between byte-identical control replicates"},
    "candidates": [{
        "tag": "cand_2", "reward": 0.54, "gate_delta": 0.04333333333333332,
        "gate_threshold": 0.04920353294552117, "verdict": "inconclusive",
        "verdict_by_reference": {"ctl_null_i1": "reject", "ctl_null_i1r1": "accept"},
        "verdict_stable": False, "regressions": ["40467"], "eval_rc": 0, "eval_error": None,
    }],
}


def _staged(tmp_path, cid="cand_2", table=UNSTABLE_TABLE):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=3, stall=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    work = run_dir.root / "work" / cid
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.root / "candidates" / "seed", work)
    if table is not None:
        (run_dir.root / "work" / "round_i0.json").write_text(json.dumps(table), encoding="utf-8")
    return run_dir, work


def _commit(run_dir, work, *extra, cid="cand_2", decision="inconclusive", val="0.54"):
    # This file tests the booking MECHANICS of `inconclusive` — issue #420 item 3 (a separate
    # test file) covers the newer, orthogonal rule that commit.py refuses that decision without
    # a prior scripts/grow.py run. `--force` here is that override, not a re-test of it.
    force = ["--force"] if decision == "inconclusive" and "--force" not in extra else []
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", cid, "--from-dir", str(work),
         "--decision", decision, "--val", val,
         "--note", "verdict flipped between control replicates; not resolvable this round",
         *extra, *force],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})


def _ok(p):
    assert p.returncode == 0, f"commit.py failed: {p.stdout}\n{p.stderr}"
    return json.loads(p.stdout)


def test_an_inconclusive_round_can_be_booked_at_all(tmp_path):
    run_dir, work = _staged(tmp_path)
    out = _ok(_commit(run_dir, work))
    assert out["decision"] == "inconclusive"


def test_an_inconclusive_round_charges_the_iteration_but_not_the_stall(tmp_path):
    """The budget was really spent, so the iteration is charged. The stall counter means "the
    optimizer is out of ideas" and must not move on a measurement that failed to resolve."""
    from cap_evolve import RunDir

    run_dir, work = _staged(tmp_path)
    _ok(_commit(run_dir, work))

    spent = RunDir.open(run_dir.root).spent
    assert spent.iterations == 1, f"the round's real spend was not charged: {spent.to_dict()}"
    assert spent.stall == 0, (
        "an unresolved measurement incremented the stall counter, which is what ends a run "
        f"early for 'no ideas left': {spent.to_dict()}")


def test_a_reject_still_charges_the_stall(tmp_path):
    """Control: the new decision must not weaken a real reject, which IS stall evidence."""
    from cap_evolve import RunDir

    run_dir, work = _staged(tmp_path)
    _ok(_commit(run_dir, work, decision="reject"))
    assert RunDir.open(run_dir.root).spent.stall == 1


def test_an_inconclusive_round_neither_takes_the_champion_nor_files_a_refutation(tmp_path):
    from cap_evolve import RunDir

    run_dir, work = _staged(tmp_path)
    _ok(_commit(run_dir, work))

    assert RunDir.open(run_dir.root).best_id in ("seed", None), (
        "an unresolved candidate became the champion")
    rejected = Path(run_dir.rejected_path)
    text = rejected.read_text(encoding="utf-8") if rejected.exists() else ""
    assert "cand_2" not in text, (
        "an unresolved candidate was filed as a REFUTED approach, so a later round is taught "
        "to avoid an edit that was never actually judged")


def test_the_iteration_record_marks_it_unresolved_not_rejected(tmp_path):
    """A reader of the event stream — dashboard, TUI, CI report — must be able to tell an
    unresolved round from a refuted one, or the run's own history is wrong."""
    run_dir, work = _staged(tmp_path)
    _ok(_commit(run_dir, work))

    kinds = []
    for line in Path(run_dir.events_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            kinds.append(json.loads(line).get("kind"))
    assert "step_indecisive" in kinds, (
        f"nothing in the event stream marks the round unresolved: {kinds}")
    assert "reject" not in kinds, f"an unresolved round logged a reject event: {kinds}"


def test_claiming_the_gate_rejected_an_unresolved_candidate_is_refused(tmp_path):
    """``--reject-basis gate`` asserts a full-val paired gate ran AND rejected. Against an
    ``inconclusive`` verdict that is the same misattribution the existing guard already catches
    for an ACCEPTED verdict: the gate did not refute the edit, it failed to resolve it."""
    run_dir, work = _staged(tmp_path)
    p = _commit(run_dir, work, "--reject-basis", "gate", decision="reject")

    assert p.returncode != 0, (
        "commit.py let the run record 'the gate rejected cand_2' when the gate returned "
        f"inconclusive: {p.stdout}")
    assert "inconclusive" in p.stdout


def test_reject_basis_is_meaningless_on_an_inconclusive_decision(tmp_path):
    run_dir, work = _staged(tmp_path)
    p = _commit(run_dir, work, "--reject-basis", "gate")
    assert p.returncode != 0, f"--reject-basis was accepted on a non-reject: {p.stdout}"


def test_an_inconclusive_candidate_cannot_be_silently_rebooked_under_its_own_tag(tmp_path):
    """The tag-reuse guard exists because rollouts are ``<task>__<tag>__t<k>.json``: re-running
    a tag overwrites its evidence. Resolving an inconclusive candidate therefore needs a FRESH
    tag, and re-booking the old one must be refused like any other double decision."""
    run_dir, work = _staged(tmp_path)
    _ok(_commit(run_dir, work))
    p = _commit(run_dir, work, decision="accept")

    assert p.returncode != 0, (
        f"the same tag was booked twice, the second time as an accept: {p.stdout}")
    assert "already has" in p.stdout


def test_the_journal_does_not_tell_the_next_round_its_batch_was_refuted(tmp_path):
    """``JOURNAL.md`` is the handover the NEXT round reads. Its framework RESULT line said
    "REJECTED (champion unchanged) … its WHOLE batch was reverted; re-introduce only the edits
    that did NOT break a task above" for every non-accept — including a step whose measurement
    was void. That is the misattribution of this whole file, written into the one artifact whose
    job is to stop the next round repeating a refuted idea. An unresolved edit is not refuted;
    it is unmeasured, and the correct next move is to re-measure it, not to redesign it."""
    run_dir, work = _staged(tmp_path)
    (work / "JOURNAL.md").write_text(
        "## Iteration cand_2 — replay rationale + write-only-required-cells\n", encoding="utf-8")
    _ok(_commit(run_dir, work))

    journal = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    assert "REJECTED" not in journal, (
        f"an unresolved round is stamped REJECTED in the handover the next round reads:\n{journal}")
    assert "WHOLE batch was reverted" not in journal, (
        "the next round is told to redesign an edit that was never actually judged")
    assert "UNRESOLVED" in journal, f"nothing marks the round unresolved:\n{journal}"


def test_every_algorithms_void_step_gets_the_same_journal_treatment(tmp_path):
    """The stamp is written by ``_reconcile_journal``, which every algorithm reaches through
    ``record_iteration`` — so fixing it there also fixes the tamper-voided steps in the
    deterministic hill-climb (``harness``) and ``gepa``, which have always stamped a void
    measurement as REJECTED too."""
    from cap_evolve import harness

    run_dir, work = _staged(tmp_path, table=None)
    (work / "JOURNAL.md").write_text("## Iteration cand_2 — whatever\n", encoding="utf-8")
    harness.record_iteration(run_dir, work, "cand_2", parent_id="seed", accepted=False,
                             reason="indecisive (integrity): capability dir was mutated",
                             val=None, indecisive=True)

    journal = (run_dir.root / "JOURNAL.md").read_text(encoding="utf-8")
    assert "UNRESOLVED" in journal and "REJECTED" not in journal, journal


# --- the guidance that makes the third decision reachable --------------------------------

def test_round_offers_the_driver_the_decision_it_actually_needs():
    """``round.py``'s `next` line is the driver's instruction for what to do with the table it
    just read. It said "commit.py --decision accept|reject per candidate" — so a driver holding
    an INCONCLUSIVE verdict was told, by the same tool that produced that verdict, to book one
    of the two dispositions that verdict rules out."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    assert "accept|reject|inconclusive" in src, (
        "round.py can return `inconclusive` but still tells the driver to book accept|reject")


def test_round_says_how_to_re_measure_not_just_that_it_should():
    """"Re-run it with more trials" is unactionable in a system where trials are written
    ``<task>__<tag>__t{k}.json`` for ``k in range(n_trials)``: re-running the SAME tag replaces
    t0..t9 rather than adding t10..t19. Following the advice literally is what happened on run
    33046360451 — the agent re-measured control ``ctl_null_i1`` under its own tag, spent 100
    metric calls, and swapped a 0.4967 replicate for a 0.5067 one instead of adding one, WIDENING
    the round's replicate spread."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    lo = src.lower()
    assert "fresh tag" in lo, (
        "nothing tells the driver that re-measuring needs a fresh tag, so 'more trials' reads "
        "as 're-run this tag' — which destroys the reading it meant to add to")


def test_the_evidence_bar_is_not_presented_as_the_only_number_that_matters():
    """"Judge every candidate's delta against `evidence_bar`, not against any other number here"
    is true about which NOISE FLOOR to use, and false as stated: `gate_threshold` (k·SE on the
    paired per-task differences) is the number the verdict is actually computed from, and it is
    the stricter of the two. Live on run 33046360451 i1, cand_2 cleared evidence_bar 0.0167 with
    Δ +0.0433 and still did not clear its threshold of 0.0492 — a driver following the sentence
    literally would read the table as an accept."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    assert "gate_threshold" in src, "the reading never names the number the verdict is computed from"
    lo = src.lower()
    assert "necessary" in lo and "not sufficient" in lo, (
        "the reading still presents clearing `evidence_bar` as the whole test, inviting a driver "
        "to book an accept the paired gate did not give")


def _load_host():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ao_host_unresolved", SCRIPTS / "host.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def test_an_honestly_booked_unresolved_round_is_not_reported_as_abandoned(tmp_path):
    """``host._unbooked_rounds`` names candidates a round GATED that nobody booked, and it drives
    the run-quality diagnosis ("gated but never booked with commit.py") and the ``finished_itself``
    branch. It recognises a booking by its event kind, so an ``inconclusive`` booking would read as
    no booking at all — punishing the driver for recording the honest outcome and telling the
    operator a completed round was abandoned."""
    host = _load_host()
    run_dir, work = _staged(tmp_path)
    # round.py's table lives under work/ where _unbooked_rounds scans for it.
    (run_dir.root / "work" / "round_i0.json").write_text(json.dumps(UNSTABLE_TABLE),
                                                         encoding="utf-8")
    _ok(_commit(run_dir, work))

    assert "cand_2" in host._decided_candidates(run_dir.root), (
        "an inconclusive booking is not recognised as a decision")
    assert host._unbooked_rounds(run_dir.root) == [], (
        "a round booked as inconclusive is reported as gated-but-never-booked, so the run is "
        f"diagnosed as defective for doing the right thing: {host._unbooked_rounds(run_dir.root)}")


def test_the_host_brief_tells_the_agent_the_third_decision_exists():
    """The host brief is the agent's only instruction sheet. Its per-round checklist said
    ``commit.py | always, accept or reject`` — an agent reading only that has no way to know an
    unresolved round is bookable, and will pick whichever of the two it thinks is safer."""
    src = (SCRIPTS / "host.py").read_text(encoding="utf-8")
    assert "inconclusive" in src, (
        "the host brief never mentions --decision inconclusive, so the agent cannot use it")


def test_the_skill_documents_the_third_decision():
    md = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
    assert "--decision inconclusive" in md or "inconclusive" in md, (
        "SKILL.md documents only accept/reject")
