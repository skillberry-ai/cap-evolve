"""ParetoArchive — issue #684 item 1's persistent bounded non-dominated frontier.

Covers: insertion/eviction correctness on synthetic objective vectors (dominance,
non-dominated tradeoffs, maintenance pruning of newly-dominated points, crowding-distance
eviction keeps the frontier spread rather than clumped), the significance floor refusing a
noise-level "win" on the cost objective (the same adversarial case the earlier gate.py bug
was about — a tie on reward plus a float-noise cost delta must NOT get archived), and
persistence surviving a simulated process restart (write, reload, confirm state matches).
"""

from __future__ import annotations

import pytest

from cap_evolve.gate import ParetoObjectiveError
from cap_evolve.pareto_archive import ArchivePoint, ParetoArchive

OBJECTIVES = [{"name": "reward", "direction": "maximize"},
              {"name": "cost", "direction": "minimize"}]


def _pt(reward, cost, reward_se=0.0, cost_se=0.0):
    return {"reward": reward, "cost": cost}, {"reward": reward_se, "cost": cost_se}


# ---- membership: dominance / non-domination -------------------------------

def test_first_point_always_inserted():
    archive = ParetoArchive(OBJECTIVES)
    v, s = _pt(0.5, 1.0)
    inserted, reason = archive.try_insert("c1", v, s)
    assert inserted and "first point" in reason
    assert [p.tag for p in archive.points] == ["c1"]


def test_insert_rejects_candidate_dominated_by_archive():
    archive = ParetoArchive(OBJECTIVES)
    archive.try_insert("c1", *_pt(0.8, 1.0))
    # c2 is worse on reward AND worse (higher) on cost -> dominated by c1.
    inserted, reason = archive.try_insert("c2", *_pt(0.5, 2.0))
    assert not inserted
    assert "dominated by archive point 'c1'" in reason
    assert [p.tag for p in archive.points] == ["c1"]


def test_insert_accepts_nondominated_tradeoff_and_keeps_both():
    archive = ParetoArchive(OBJECTIVES)
    archive.try_insert("c1", *_pt(0.8, 2.0))   # high reward, high cost
    inserted, reason = archive.try_insert("c2", *_pt(0.5, 0.5))  # low reward, low cost
    assert inserted, reason
    assert {p.tag for p in archive.points} == {"c1", "c2"}


def test_insert_rejects_tie_with_no_significant_win():
    archive = ParetoArchive(OBJECTIVES)
    archive.try_insert("c1", *_pt(0.5, 1.0))
    inserted, reason = archive.try_insert("c2", *_pt(0.5, 1.0))
    assert not inserted
    assert "no significant improvement" in reason
    assert [p.tag for p in archive.points] == ["c1"]


def test_insert_prunes_existing_points_newly_dominated():
    archive = ParetoArchive(OBJECTIVES)
    archive.try_insert("c1", *_pt(0.4, 2.0))
    archive.try_insert("c2", *_pt(0.5, 1.5))  # non-dominated tradeoff vs c1 so far? better both -> dominates c1
    # c2 beats c1 on BOTH objectives (higher reward, lower cost) -> c1 is pruned.
    assert {p.tag for p in archive.points} == {"c2"}


# ---- significance floor: the #667 fix this module must not regress --------

def test_refuses_noise_cost_win_tie_on_reward():
    """Reproduces the earlier gate.py adversarial case inside the archive: a candidate that
    ties on reward and shows only a pure float-noise cost delta (no tracked cost stderr) must
    not be archived — the significance floor refuses rather than reading $0.0000001 as a win."""
    archive = ParetoArchive(OBJECTIVES)
    # "cost" deliberately absent from the stderr dicts — a REAL tracked SE of 0.0 is a
    # legitimate (if trivial) measurement; an absent key is what "no stderr tracked" means.
    archive.try_insert("c1", {"reward": 0.5, "cost": 1.0}, {"reward": 0.0})
    with pytest.raises(ParetoObjectiveError):
        archive.try_insert("c2", {"reward": 0.5, "cost": 0.9999999}, {"reward": 0.0})


def test_insert_against_existing_point_missing_declared_objective_raises_not_keyerror():
    """Reviewer-reproduced crash: round.py's archive seeding (``_objective_metrics`` ->
    ``ArchivePoint``) can silently omit a declared objective (e.g. ``harness.
    candidate_cost_objective`` returning ``(None, None)``), so an existing archive point
    may be incomplete even though ``try_insert`` validates every NEW candidate's values.
    The next candidate that DOES carry the missing objective must get the designed
    ``ParetoObjectiveError`` refusal, not a raw ``KeyError``."""
    archive = ParetoArchive(OBJECTIVES)
    archive.points.append(ArchivePoint(tag="baseline", values={"reward": 0.5},
                                       stderr={"reward": 0.0}))
    with pytest.raises(ParetoObjectiveError):
        archive.try_insert("cand_1", {"reward": 0.6, "cost": 1.0}, {"reward": 0.0, "cost": 0.1})


def test_real_cost_win_with_tracked_stderr_is_accepted():
    archive = ParetoArchive(OBJECTIVES)
    archive.try_insert("c1", *_pt(0.5, 1.0, cost_se=0.01))
    inserted, _ = archive.try_insert("c2", *_pt(0.5, 0.5, cost_se=0.01))
    assert inserted


def test_nominal_cost_win_that_cannot_clear_its_own_se_is_not_a_win():
    archive = ParetoArchive(OBJECTIVES)
    archive.try_insert("c1", *_pt(0.50, 1.00, reward_se=0.2, cost_se=0.2))
    inserted, reason = archive.try_insert(
        "c2", *_pt(0.51, 0.99, reward_se=0.2, cost_se=0.2))
    assert not inserted
    assert "no significant improvement" in reason


# ---- crowding-distance eviction: keeps the frontier spread -----------------

def test_capacity_eviction_keeps_boundary_points():
    """A frontier of evenly-spaced tradeoff points beyond capacity: the two EXTREME points
    (highest reward/highest cost, lowest reward/lowest cost) must survive eviction — they
    always carry infinite crowding distance in NSGA-II's own definition."""
    archive = ParetoArchive(OBJECTIVES, capacity=5)
    # 10 points on a straight tradeoff line: higher i buys higher reward at higher cost, so
    # every pair is mutually non-dominated (a real tradeoff, not one point beating another
    # on both axes). Significant SEs so every pairwise comparison is a real win, not a tie.
    for i in range(10):
        reward, cost = i / 10.0, float(i)
        archive.try_insert(f"c{i}", *_pt(reward, cost, reward_se=0.001, cost_se=0.001))
    assert len(archive.points) == 5
    tags = {p.tag for p in archive.points}
    assert "c0" in tags and "c9" in tags  # the two extremes on this frontier


def test_capacity_eviction_prefers_dropping_clustered_point():
    """Among several points, eviction drops the one with the SMALLEST crowding distance —
    i.e. the one most tightly packed between its neighbors — not an arbitrary one."""
    archive = ParetoArchive(OBJECTIVES, capacity=3)
    # A monotonic tradeoff frontier (higher reward always costs more, so no point ever
    # dominates another): c0/c3 are the spread extremes, c1/c2 sit close together in the
    # middle. One of {c1, c2} must be evicted first since dropping an extreme costs
    # infinite crowding distance in NSGA-II's own definition.
    archive.try_insert("c0", *_pt(0.00, 0.0, reward_se=0.001, cost_se=0.001))
    archive.try_insert("c1", *_pt(0.50, 5.0, reward_se=0.001, cost_se=0.001))
    archive.try_insert("c2", *_pt(0.51, 5.1, reward_se=0.001, cost_se=0.001))
    archive.try_insert("c3", *_pt(1.00, 10.0, reward_se=0.001, cost_se=0.001))
    assert len(archive.points) == 3
    tags = {p.tag for p in archive.points}
    assert "c0" in tags and "c3" in tags
    assert len(tags & {"c1", "c2"}) == 1


# ---- persistence: survives a simulated process restart ---------------------

def test_persistence_round_trip_simulates_process_restart(tmp_path):
    path = tmp_path / "pareto_archive.json"
    archive = ParetoArchive(OBJECTIVES, capacity=10)
    archive.try_insert("c1", *_pt(0.5, 0.5))   # cheap, modest reward
    archive.try_insert("c2", *_pt(0.8, 2.0))   # expensive, high reward — tradeoff vs c1
    archive.save(path)

    # Simulate a fresh process: a brand-new ParetoArchive object, loaded only from disk.
    reloaded = ParetoArchive.load_or_create(path, OBJECTIVES)
    assert reloaded.capacity == 10
    assert {p.tag for p in reloaded.points} == {"c1", "c2"}
    c1 = next(p for p in reloaded.points if p.tag == "c1")
    assert c1.values == {"reward": 0.5, "cost": 0.5}

    # The reloaded archive behaves identically to the original for a further insertion —
    # a genuine tradeoff against BOTH existing points (better reward than c1, worse cost;
    # worse reward than c2, better cost), so nothing is pruned.
    inserted, _ = reloaded.try_insert("c3", *_pt(0.65, 1.0))
    assert inserted
    reloaded.save(path)
    again = ParetoArchive.load_or_create(path, OBJECTIVES)
    assert {p.tag for p in again.points} == {"c1", "c2", "c3"}


def test_load_or_create_starts_fresh_on_missing_or_corrupt_file(tmp_path):
    missing = tmp_path / "nope.json"
    archive = ParetoArchive.load_or_create(missing, OBJECTIVES, capacity=7)
    assert archive.points == [] and archive.capacity == 7

    corrupt = tmp_path / "bad.json"
    corrupt.write_text("not json", encoding="utf-8")
    archive2 = ParetoArchive.load_or_create(corrupt, OBJECTIVES, capacity=3)
    assert archive2.points == [] and archive2.capacity == 3


def test_to_dict_from_dict_round_trip():
    archive = ParetoArchive(OBJECTIVES, capacity=4,
                            points=[ArchivePoint("c1", {"reward": 0.5, "cost": 1.0},
                                                 {"reward": 0.0, "cost": 0.0}, round=2)])
    d = archive.to_dict()
    assert d["version"] == 1
    rebuilt = ParetoArchive.from_dict(d)
    assert rebuilt.capacity == 4
    assert rebuilt.points[0].to_dict() == archive.points[0].to_dict()
