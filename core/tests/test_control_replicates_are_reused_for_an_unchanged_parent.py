"""A null control re-measures the SAME bytes every round, and that was ~40% of all rollouts.

Across six real runs of one multi-turn benchmark, the mandatory two null-control replicates
(PR #402's safeguard: two byte-identical copies of the parent, so the round has its own noise
floor) consumed nearly as many rollouts as every candidate combined. The safeguard is right; the
re-measurement is not always necessary. While ``best_id`` has not moved the parent is the same
bytes, so its noise floor has already been established and paying for it again buys nothing.

The two properties that must hold together:

* the parent CHANGED (an accept happened) -> fresh replicates, always. A new parent has no
  established floor, and reusing the old parent's would be comparing a candidate to a null
  measured on different code.
* the parent is UNCHANGED since the round that measured them -> reuse, no rollouts spent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _load_round():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ao_round_reuse", SCRIPTS / "round.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class _Spent:
    def __init__(self, iterations):
        self.iterations = iterations


class _RD:
    """Just enough RunDir for the control-reuse helpers."""

    def __init__(self, root, iterations=1):
        self.root = Path(root)
        self.rollouts = Path(root) / "rollouts"
        self.spent = _Spent(iterations)


def _measured_round(rd, iteration, parent, measurement, tags=("ctl_a", "ctl_b"), n_trials=3):
    """Write a completed round: its table, plus the control rollouts the table cites."""
    work = rd.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / f"round_i{iteration}.json").write_text(json.dumps({
        "parent": {"tag": parent},
        "measurement": measurement,
        "control_replicates": [{"tag": t, "reward": 0.5} for t in tags],
    }), encoding="utf-8")
    roll = rd.rollouts / measurement["split"]
    roll.mkdir(parents=True, exist_ok=True)
    for t in tags:
        for k in range(n_trials):
            (roll / f"task1__{t}__t{k}.json").write_text("{}", encoding="utf-8")


def test_replicates_are_reused_when_the_parent_has_not_changed(tmp_path):
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=2)
    m = rnd.measurement_context("val", 3, 8)
    _measured_round(rd, 1, "cand_1", m)

    got = rnd.reusable_controls(rd, "cand_1", m, want=2)
    assert got is not None, (
        "iteration 1 already measured this exact parent's two replicates and they are still on "
        "disk — re-measuring the same bytes spends rollouts to learn nothing")
    assert got["tags"] == ["ctl_a", "ctl_b"] and got["from_iteration"] == 1


def test_fresh_replicates_are_required_when_the_parent_just_changed(tmp_path):
    """The safeguard itself is untouched: a NEW parent has no established noise floor."""
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=2)
    m = rnd.measurement_context("val", 3, 8)
    _measured_round(rd, 1, "cand_1", m)

    assert rnd.reusable_controls(rd, "cand_2", m, want=2) is None, (
        "an accept moved best_id, so those replicates measure a DIFFERENT capability's noise "
        "floor — the new parent must be measured")


def test_reuse_needs_the_same_measurement_context(tmp_path):
    """Trial count and load both move the reading, so a reading taken at another n or another
    concurrency is not a sample of this round's null."""
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=2)
    _measured_round(rd, 1, "cand_1", rnd.measurement_context("val", 3, 8))

    assert rnd.reusable_controls(rd, "cand_1", rnd.measurement_context("val", 5, 8), 2) is None
    assert rnd.reusable_controls(rd, "cand_1", rnd.measurement_context("val", 3, 25), 2) is None
    assert rnd.reusable_controls(rd, "cand_1", rnd.measurement_context("test", 3, 8), 2) is None


def test_reuse_needs_the_rollouts_to_still_be_on_disk(tmp_path):
    """The gate re-reads the replicates' rollouts, so a table alone is not enough."""
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=2)
    m = rnd.measurement_context("val", 3, 8)
    _measured_round(rd, 1, "cand_1", m)
    for p in (rd.rollouts / "val").glob("*__ctl_b__*"):
        p.unlink()

    assert rnd.reusable_controls(rd, "cand_1", m, want=2) is None


def test_reuse_never_weakens_the_two_replicate_requirement(tmp_path):
    """One replicate on disk cannot satisfy a round that needs two."""
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=2)
    m = rnd.measurement_context("val", 3, 8)
    _measured_round(rd, 1, "cand_1", m, tags=("ctl_a",))

    assert rnd.reusable_controls(rd, "cand_1", m, want=2) is None
    assert rnd.reusable_controls(rd, "cand_1", m, want=1) is not None


def test_this_iterations_own_attempts_are_not_reuse_material(tmp_path):
    """Same-iteration attempts are POOLED by prior_attempt_controls; reuse is across rounds
    only. Counting them here would let a re-gate answer itself with the readings it already had."""
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=1)
    m = rnd.measurement_context("val", 3, 8)
    _measured_round(rd, 1, "cand_1", m)

    assert rnd.reusable_controls(rd, "cand_1", m, want=2) is None


def test_an_old_table_without_a_measurement_context_is_not_reused(tmp_path):
    """Backwards safety: a table written before this field existed cannot prove it matches."""
    rnd = _load_round()
    rd = _RD(tmp_path, iterations=2)
    m = rnd.measurement_context("val", 3, 8)
    _measured_round(rd, 1, "cand_1", m)
    table = rd.root / "work" / "round_i1.json"
    body = json.loads(table.read_text(encoding="utf-8"))
    body.pop("measurement")
    table.write_text(json.dumps(body), encoding="utf-8")

    assert rnd.reusable_controls(rd, "cand_1", m, want=2) is None


def test_the_round_table_records_the_context_a_later_round_matches_on(tmp_path):
    """The reuse check reads `measurement` out of the table, so round.py must write it."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    assert '"measurement": MEASUREMENT' in src
    assert '"control_reuse"' in src, "the table must say whether it paid for its own controls"


def test_reuse_is_off_when_the_round_gates_against_a_concurrent_control(tmp_path):
    """--gate-against control exists to cancel drift by measuring the control alongside the
    candidates. A reused replicate is not concurrent, so reuse must not apply there."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    assert 'args.gate_against != "control"' in src and "ATTEMPT == 0" in src
