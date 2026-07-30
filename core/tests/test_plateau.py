"""Plateau/convergence detection (#130).

The load-bearing test is ``test_spiky_but_progressing_never_escalates``: the whole
design risk is a heuristic that kills a productive-but-slow run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cap_evolve import plateau
from cap_evolve.rundir import Budget, RunDir


def _rd(tmp_path) -> RunDir:
    return RunDir.create(tmp_path, budget=Budget(max_iterations=50))


def _step(rd, cid, *, accept, val, parent_val, kind="step", parent=None):
    rd.log_event(kind, candidate=cid, accept=accept, val=val,
                 parent_val=parent_val, parent=parent)


# ---- the criterion --------------------------------------------------------

def test_dead_run_escalates_warn_then_diversify_then_stop(tmp_path):
    """Every child scores at or below its parent -> the full ladder."""
    cfg = plateau.PlateauConfig(window=3, escalate_every=2)
    rd = _rd(tmp_path)
    seen = []
    for i in range(1, 8):
        _step(rd, f"c{i}", accept=False, val=0.5, parent_val=0.5, parent="seed")
        seen.append(plateau.assess(rd, cfg).level)
    # run_length 1,2 -> ok; 3,4 -> warn; 5,6 -> diversify; 7 -> stop
    assert seen == ["ok", "ok", "warn", "warn", "diversify", "diversify", "stop"], seen


def test_spiky_but_progressing_never_escalates(tmp_path):
    """THE anti-false-positive test.

    A healthy run on a small val split under #113's Student-t bar produces long
    stretches of *near-misses*: rejected because Δ did not clear k_eff·SE, but Δ>0.
    That is progress-in-flight, not a plateau, and must never escalate — even for
    far more consecutive rejections than the plateau window.
    """
    cfg = plateau.PlateauConfig(window=3, escalate_every=2)
    rd = _rd(tmp_path)
    # 12 consecutive REJECTIONS, all with Δ>0 (sub-significant improvements).
    for i, v in enumerate([0.51, 0.53, 0.52, 0.55, 0.54, 0.57,
                           0.56, 0.58, 0.59, 0.57, 0.60, 0.62], 1):
        _step(rd, f"c{i}", accept=False, val=v, parent_val=0.50, parent="seed")
    st = plateau.assess(rd, cfg)
    assert st.level == "ok", st
    assert st.run_length == 0, st
    assert st.near_misses > 0, st
    # And the naive heuristic WOULD have fired: 12 rejects in a row >> window 3.
    assert st.iterations == 12


def test_one_near_miss_resets_the_streak(tmp_path):
    """A single Δ>0 rejection mid-streak resets, so a run can't be killed by noise."""
    cfg = plateau.PlateauConfig(window=3, escalate_every=2)
    rd = _rd(tmp_path)
    for i in range(4):  # dead
        _step(rd, f"d{i}", accept=False, val=0.5, parent_val=0.5, parent="seed")
    assert plateau.assess(rd, cfg).level == "warn"
    _step(rd, "near", accept=False, val=0.55, parent_val=0.50, parent="seed")  # Δ>0
    st = plateau.assess(rd, cfg)
    assert st.level == "ok" and st.run_length == 0, st


def test_accept_resets_the_streak(tmp_path):
    cfg = plateau.PlateauConfig(window=3, escalate_every=2)
    rd = _rd(tmp_path)
    for i in range(6):
        _step(rd, f"d{i}", accept=False, val=0.5, parent_val=0.5, parent="seed")
    assert plateau.assess(rd, cfg).level == "diversify"
    _step(rd, "win", accept=True, val=0.9, parent_val=0.5, parent="seed")
    st = plateau.assess(rd, cfg)
    assert st.level == "ok" and st.run_length == 0 and st.accepts == 1, st


def test_regression_counts_as_dead(tmp_path):
    """Δ<0 (an edit that made things worse) is dead, not a near-miss."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    for i, v in enumerate([0.4, 0.3, 0.2, 0.1], 1):
        _step(rd, f"r{i}", accept=False, val=v, parent_val=0.5, parent="seed")
    st = plateau.assess(rd, cfg)
    assert st.run_length == 4 and st.level == "stop", st


def test_plateau_stop_false_caps_at_diversify(tmp_path):
    cfg = plateau.PlateauConfig(window=2, escalate_every=1, stop=False)
    rd = _rd(tmp_path)
    for i in range(10):
        _step(rd, f"d{i}", accept=False, val=0.0, parent_val=0.0, parent="seed")
    st = plateau.assess(rd, cfg)
    assert st.level == "diversify" and not st.should_stop, st
    assert st.should_diversify


def test_non_best_accepts_are_dead_but_ratchet_caps_at_warn(tmp_path):
    """GEPA can accept a frontier specialist that beats its own parent but never tops
    the incumbent best. Best-val velocity is 0, so those iterations ARE dead for the
    streak — but a streak containing accepts is capped at ``warn``: no stop, and no
    behavioural prompt block either, because telling an optimizer that is clearing the
    honest val gate every iteration "the direction is dead" would be false."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    _step(rd, "best", accept=True, val=1.0, parent_val=0.0, parent="seed")
    for i in range(10):  # accepted specialists, each below the incumbent best of 1.0
        _step(rd, f"spec{i}", accept=True, val=0.7, parent_val=0.5, parent=f"p{i}")
    st = plateau.assess(rd, cfg)
    assert st.run_length == 10, st
    assert st.accepts_in_streak == 10, st
    assert st.level == "warn", "a still-accepting run must not be stopped or redirected"
    assert not st.should_stop and not st.should_diversify
    # The reason must not contradict its own ratchet clause (review #6).
    assert "no near-miss" not in st.reason, st.reason
    assert "frontier still widening" in st.reason, st.reason
    # No prompt block on this path: the block asserts the direction failed.
    assert plateau.prompt_block(st) == ""


def test_zero_accept_streak_does_reach_stop(tmp_path):
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    _step(rd, "best", accept=True, val=1.0, parent_val=0.0, parent="seed")
    for i in range(6):
        _step(rd, f"d{i}", accept=False, val=1.0, parent_val=1.0, parent="best")
    st = plateau.assess(rd, cfg)
    assert st.accepts_in_streak == 0 and st.level == "stop", st


def test_new_best_accept_resets_the_streak(tmp_path):
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    for i in range(6):
        _step(rd, f"d{i}", accept=False, val=0.5, parent_val=0.5, parent="seed")
    assert plateau.assess(rd, cfg).level == "stop"
    _step(rd, "up", accept=True, val=0.9, parent_val=0.5, parent="seed")
    st = plateau.assess(rd, cfg)
    assert st.run_length == 0 and st.level == "ok", st


# ---- GEPA: the event kind that used to be invisible -----------------------

def test_gepa_val_gate_events_are_seen(tmp_path):
    """#199's bug class: filtering kind == 'step' makes GEPA's history empty.

    Plateau detection must see ``gepa_val_gate``, or it can never fire for GEPA.
    """
    cfg = plateau.PlateauConfig(window=3, escalate_every=2)
    rd = _rd(tmp_path)
    for i in range(1, 8):
        _step(rd, f"gepa_{i:04d}", accept=False, val=0.5, parent_val=0.5,
              kind="gepa_val_gate", parent="seed")
    st = plateau.assess(rd, cfg)
    assert st.iterations == 7, st
    assert st.level == "stop", st


def test_gepa_local_gate_rejections_count(tmp_path):
    """A GEPA child killed by the cheap minibatch gate never reaches the val gate,
    but it IS a spent iteration with no movement."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    for i in range(5):
        rd.log_event("gepa_local_gate", candidate=f"g{i}", parent="seed",
                     child_sum=1.0, parent_sum=1.0, passed=False)
    st = plateau.assess(rd, cfg)
    assert st.iterations == 5 and st.level == "stop", st


def test_real_skillopt_iteration_is_counted_ONCE(tmp_path):
    """REGRESSION (review blocking #1) — the false positive that killed productive runs.

    A real SkillOpt iteration logs the event PAIR: ``harness.run_step`` logs ``step``
    (with parent + parent_val), then ``skillopt.py`` logs ``skillopt_step`` for the SAME
    candidate as an audit record. Counting both meant one iteration counted twice, so a
    ``window=6`` ladder reached ``stop`` at iteration 5 — with a *productive* run — and a
    genuine near-miss was recorded once alive and once dead (the duplicate carries no
    parent_val, so its delta was taken against the running best).

    The old ``test_skillopt_step_events_are_seen`` logged ``skillopt_step`` ALONE, a shape
    that never occurs in production, which is why 28 tests missed this.
    """
    cfg = plateau.PlateauConfig(window=6, escalate_every=2)   # shipped defaults
    rd = _rd(tmp_path)
    for i in range(1, 6):
        cid = f"so_e01s{i:02d}"
        # the production pair, in production order:
        rd.log_event("step", candidate=cid, accept=False, val=0.5,
                     parent_val=0.5, parent="seed")
        rd.log_event("skillopt_step", candidate=cid, accept=False, val=0.5, epoch=1)
    st = plateau.assess(rd, cfg)
    assert st.iterations == 5, f"5 real iterations must be 5 rows, got {st.iterations}"
    assert st.run_length == 5, st
    assert st.level == "ok", "a window=6 ladder must NOT fire at iteration 5"


def test_skillopt_near_miss_is_not_also_recorded_dead(tmp_path):
    """The nastier half of blocking #1: the duplicate row had no ``parent_val``, so a
    near-miss (Δ>0, sub-significant) was recorded alive by ``step`` and dead by
    ``skillopt_step`` — and the dead copy was the trailing row ``assess`` reads."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    _step(rd, "so_e01s01", accept=True, val=0.9, parent_val=0.0, parent="seed")
    for i in range(2, 8):   # a run of genuine near-misses against a best of 0.9
        cid = f"so_e01s{i:02d}"
        rd.log_event("step", candidate=cid, accept=False, val=0.95,
                     parent_val=0.90, parent="so_e01s01")
        rd.log_event("skillopt_step", candidate=cid, accept=False, val=0.95, epoch=1)
    st = plateau.assess(rd, cfg)
    assert st.run_length == 0, f"near-misses must keep the streak at 0, got {st.run_length}"
    assert st.level == "ok", st


# ---- per-lineage exhaustion vs GLOBAL plateau -----------------------------

def test_lineage_exhausted_while_global_search_progresses(tmp_path):
    """The distinction: one dead lineage, healthy run.

    ``dead_parent`` gets 4 dead children while ``live_parent`` keeps accepting. The
    global level stays ``ok`` (the trailing iteration is an accept) and only the one
    parent is reported exhausted.
    """
    cfg = plateau.PlateauConfig(window=3, escalate_every=2, lineage_window=4)
    rd = _rd(tmp_path)
    for i in range(4):
        # interleave so the streak is broken by the accepts on the other lineage
        _step(rd, f"dead{i}", accept=False, val=0.5, parent_val=0.5, parent="dead_parent")
        _step(rd, f"live{i}", accept=True, val=0.6 + i * 0.05, parent_val=0.5,
              parent="live_parent")
    st = plateau.assess(rd, cfg)
    assert st.level == "ok", st
    assert st.exhausted_lineages == ["dead_parent"], st.exhausted_lineages
    assert st.accepts == 4, st


def test_lineage_not_exhausted_below_window(tmp_path):
    cfg = plateau.PlateauConfig(lineage_window=4)
    rd = _rd(tmp_path)
    for i in range(3):
        _step(rd, f"d{i}", accept=False, val=0.5, parent_val=0.5, parent="p1")
    assert plateau.assess(rd, cfg).exhausted_lineages == []


def test_lineage_recovers_on_a_near_miss(tmp_path):
    cfg = plateau.PlateauConfig(lineage_window=3)
    rd = _rd(tmp_path)
    for i in range(3):
        _step(rd, f"d{i}", accept=False, val=0.5, parent_val=0.5, parent="p1")
    assert plateau.assess(rd, cfg).exhausted_lineages == ["p1"]
    _step(rd, "near", accept=False, val=0.55, parent_val=0.50, parent="p1")
    assert plateau.assess(rd, cfg).exhausted_lineages == []


# ---- events (surfacing) ---------------------------------------------------

def test_check_emits_plateau_and_lineage_events_once_per_change(tmp_path):
    cfg = plateau.PlateauConfig(window=2, escalate_every=1, lineage_window=3)
    rd = _rd(tmp_path)
    last = plateau.PlateauState()
    for i in range(6):
        _step(rd, f"d{i}", accept=False, val=0.0, parent_val=0.0, parent="seed")
        last = plateau.check(rd, cfg, last=last, algorithm="hill-climb:all")
    raw = [json.loads(l) for l in rd.events_path.read_text().splitlines()]
    levels = [e["level"] for e in raw if e["kind"] == "plateau"]
    assert levels == ["warn", "diversify", "stop"], levels  # one event per CHANGE
    ex = [e for e in raw if e["kind"] == "lineage_exhausted"]
    assert len(ex) == 1 and ex[0]["parent"] == "seed", ex


def test_plateau_event_fires_on_recovery(tmp_path):
    """A plateau that BROKE is news too — the dashboard must not stay red."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    last = plateau.PlateauState()
    for i in range(3):
        _step(rd, f"d{i}", accept=False, val=0.0, parent_val=0.0, parent="seed")
        last = plateau.check(rd, cfg, last=last)
    assert last.level in ("warn", "diversify", "stop")
    _step(rd, "win", accept=True, val=0.9, parent_val=0.0, parent="seed")
    last = plateau.check(rd, cfg, last=last)
    assert last.level == "ok"
    levels = [json.loads(l)["level"] for l in rd.events_path.read_text().splitlines()
              if json.loads(l)["kind"] == "plateau"]
    assert levels[-1] == "ok", levels


# ---- the intervention -----------------------------------------------------

def test_prompt_block_only_from_diversify(tmp_path):
    ok = plateau.PlateauState(level="ok")
    warn = plateau.PlateauState(level="warn", run_length=3)
    div = plateau.PlateauState(level="diversify", run_length=5, best_val=0.5,
                               exhausted_lineages=["p1"])
    assert plateau.prompt_block(ok) == ""
    assert plateau.prompt_block(warn) == "", "warn is observation only, no prompt change"
    blk = plateau.prompt_block(div)
    assert "MATERIALLY DIFFERENT" in blk
    assert "p1" in blk, "exhausted lineage named as dead ground"
    assert "5 iterations" in blk


def test_prompt_block_does_not_duplicate_222s_rejected_channel(tmp_path):
    """The block deliberately lists NO rejected candidate ids (review blocking #3b / #11).

    #129/PR222 already injects rejected approaches with normalized signatures and reasons;
    bare ids were strictly less informative and sat right next to that block. The old
    implementation also called ``RejectedMemory.entries()``, which #199 REMOVES, behind a
    bare ``except`` — so on the composed tree the line silently vanished with no error.
    Deleting the line fixes the overlap and the silent loss in one edit; ``prompt_block``
    no longer takes a ``rejected`` argument at all, so a caller passing one fails loudly.
    """
    st = plateau.PlateauState(level="diversify", run_length=5)
    blk = plateau.prompt_block(st)
    assert "MATERIALLY DIFFERENT" in blk
    assert "rejected candidates" not in blk
    with pytest.raises(TypeError):
        plateau.prompt_block(st, rejected=object())      # type: ignore[call-arg]


def test_prompt_block_is_bounded(tmp_path):
    """Blocking #3a, second half: the block itself had no ceiling — ``exhausted_lineages``
    was joined with no limit, so 200 lineages x 400-char ids grew it without bound."""
    st = plateau.PlateauState(level="diversify", run_length=9,
                              exhausted_lineages=[f"lineage_{i}_" + "x" * 400
                                                  for i in range(200)])
    blk = plateau.prompt_block(st)
    assert len(blk) < 2000, f"block must be bounded, got {len(blk)}"
    assert "+194 more" in blk, blk[-300:]


# ---- config ---------------------------------------------------------------

def test_config_from_spec_and_ladder():
    cfg = plateau.PlateauConfig.from_spec(
        {"plateau_window": 8, "plateau_escalate_every": 3,
         "plateau_lineage_window": 5, "plateau_stop": False})
    assert (cfg.warn_at, cfg.diversify_at, cfg.stop_at) == (8, 11, 14)
    assert cfg.lineage_window == 5 and cfg.stop is False
    d = plateau.PlateauConfig.from_spec({})
    assert (d.window, d.escalate_every, d.lineage_window, d.stop) == (6, 2, 4, True)
    # An absent key must not be read as 0 (which would escalate immediately)...
    assert plateau.PlateauConfig.from_spec({}).window == 6
    # ...but an EXPLICIT `plateau_window: 0` now means "off" (review #10), not "default 6".
    off = plateau.PlateauConfig.from_spec({"plateau_window": 0})
    assert off.stop is False and off.warn_at > 10 ** 6, off


def test_empty_and_unreadable_run_is_ok(tmp_path):
    rd = _rd(tmp_path)
    assert plateau.assess(rd).level == "ok"
    rd.events_path.write_text("{not json\n")
    assert plateau.assess(rd).level == "ok"


# ---- interaction with the existing stop conditions ------------------------

def test_plateau_does_not_preempt_budget_stop(tmp_path):
    """Budget still wins: a plateaued run whose budget is already gone stops on
    budget, and the plateau ladder does not change the reject/stall counters."""
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=2, stall=99))
    for i in range(6):
        _step(rd, f"d{i}", accept=False, val=0.0, parent_val=0.0, parent="seed")
        rd.update_spent(iterations=1, accepted=False)
    exhausted, why = rd.budget_exhausted()
    assert exhausted and "max_iterations" in why
    assert plateau.assess(rd, plateau.PlateauConfig(window=2, escalate_every=1)).level == "stop"
    # the plateau module is READ-ONLY over spend: stall is untouched by assess/check
    before = rd.spent.stall
    plateau.check(rd, plateau.PlateauConfig(window=2, escalate_every=1))
    assert rd.spent.stall == before


def test_stall_and_plateau_are_different_signals(tmp_path):
    """``stall`` counts rejections; plateau counts rejections WITH no movement.

    The spiky-but-progressing run trips ``stall`` (correctly — it is configurable and
    off by default at 0) but must not trip plateau. This is why plateau is a separate
    condition rather than a re-tuned ``stall``.
    """
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=50, stall=4))
    for i, v in enumerate([0.51, 0.53, 0.55, 0.57, 0.59, 0.61], 1):
        _step(rd, f"c{i}", accept=False, val=v, parent_val=0.50, parent="seed")
        rd.update_spent(iterations=1, accepted=False)
    exhausted, why = rd.budget_exhausted()
    assert exhausted and "stalled" in why, why
    assert plateau.assess(rd, plateau.PlateauConfig(window=3)).level == "ok"


# ---- loop integration -----------------------------------------------------

def test_hill_climb_loop_stops_on_plateau(tmp_path, monkeypatch):
    """End-to-end through the real loop with a no-op optimizer: the run must break
    out on plateau well before max_iterations and say so in ``stop_reason``."""
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult
    from cap_evolve.splits import Splits

    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=30))
    rd.write_splits(Splits(train=["t1"], val=["v1", "v2"], test=["s1"]))
    (rd.candidate_dir("seed")).mkdir(parents=True, exist_ok=True)
    (rd.candidate_dir("seed") / "prompt.txt").write_text("seed")
    rd.set_best("seed")

    base = SplitResult(split="val", reward=0.5, stderr=0.0,
                       per_task=[{"task_id": "v1", "reward": 0.5},
                                 {"task_id": "v2", "reward": 0.5}])

    calls = {"n": 0}

    def fake_run_step(adapter, *, run_dir, parent_dir, optimizer, instructions,
                      current_val, **kw):
        calls["n"] += 1
        cid = f"c{calls['n']:03d}"
        # A dead child: identical val to the parent, rejected.
        cand = SplitResult(split="val", reward=0.5, stderr=0.0,
                           per_task=[{"task_id": "v1", "reward": 0.5},
                                     {"task_id": "v2", "reward": 0.5}])
        run_dir.log_event("step", candidate=cid, accept=False, val=0.5,
                          parent=run_dir.best_id, parent_val=current_val.reward)
        run_dir.update_spent(iterations=1, accepted=False)
        return {"candidate_id": cid, "accepted": False,
                "candidate_val": cand.to_dict(), "workdir": str(parent_dir),
                "instructions": instructions}

    monkeypatch.setattr(harness, "run_step", fake_run_step)
    res = harness.hill_climb_loop(
        object(), run_dir=rd, optimizer=lambda w, i: None, current_val=base,
        max_iterations=30, plateau_cfg=plateau.PlateauConfig(window=3, escalate_every=2),
    )
    assert "plateaued" in res["stop_reason"], res["stop_reason"]
    assert res["iterations"] < 30, res["iterations"]
    assert res["plateau"]["level"] == "stop"


def test_hill_climb_loop_injects_diversify_block(tmp_path, monkeypatch):
    """At escalation level 1 the prompt gains the paradigm-shift block; before that
    it must be untouched."""
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult
    from cap_evolve.splits import Splits

    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=30))
    rd.write_splits(Splits(train=["t1"], val=["v1", "v2"], test=["s1"]))
    (rd.candidate_dir("seed")).mkdir(parents=True, exist_ok=True)
    (rd.candidate_dir("seed") / "prompt.txt").write_text("seed")
    rd.set_best("seed")
    base = SplitResult(split="val", reward=0.5, stderr=0.0, per_task=[{"task_id": "v1", "reward": 0.5}])

    seen: list[str] = []
    n = {"i": 0}

    def fake_run_step(adapter, *, run_dir, parent_dir, optimizer, instructions,
                      current_val, extra_instructions="", **kw):
        # The block now travels as `extra_instructions` so run_step can route it THROUGH
        # _augment_instructions (inside #222's cap, in its preserved tail) rather than
        # having it appended past the cap at the call site. Assert on what really ships.
        seen.append(instructions + extra_instructions)
        n["i"] += 1
        run_dir.log_event("step", candidate=f"c{n['i']}", accept=False, val=0.5,
                          parent="seed", parent_val=0.5)
        run_dir.update_spent(iterations=1, accepted=False)
        return {"candidate_id": f"c{n['i']}", "accepted": False,
                "candidate_val": base.to_dict(), "workdir": str(parent_dir)}

    monkeypatch.setattr(harness, "run_step", fake_run_step)
    harness.hill_climb_loop(
        object(), run_dir=rd, optimizer=lambda w, i: None, current_val=base,
        max_iterations=30, plateau_cfg=plateau.PlateauConfig(window=2, escalate_every=2),
    )
    # window=2, escalate=2 -> warn at 2, diversify at 4, stop at 6.
    assert not any("MATERIALLY DIFFERENT" in s for s in seen[:4]), \
        "diversify block leaked before the diversify threshold"
    assert any("MATERIALLY DIFFERENT" in s for s in seen[4:]), \
        "diversify block never injected"


def test_gepa_skips_exhausted_lineage_in_selection():
    """The steering behaviour, at the selection call: exhausted parents are dropped
    from the sampling pool, and the pool is never emptied."""
    from cap_evolve import selection

    pool = [{"id": "seed", "val": 0.5}, {"id": "a", "val": 0.6}, {"id": "b", "val": 0.7}]
    dead = {"a", "b"}
    sample_pool = [c for c in pool if c["id"] not in dead] or pool
    assert [c["id"] for c in sample_pool] == ["seed"]
    ranked, _ = selection.pick(sample_pool, "best", seed=0)
    assert ranked[0]["id"] == "seed"
    # every lineage dead -> fall back to the whole pool, the GLOBAL level decides
    sample_pool = [c for c in pool if c["id"] not in {"seed", "a", "b"}] or pool
    assert len(sample_pool) == 3


def test_all_accepted_lineage_is_NOT_exhausted(tmp_path):
    """REGRESSION (review blocking #4) — GEPA steering away from its BEST lineage.

    ``exhausted_lineages`` reused ``_dead()``, which counts accepted-but-not-global-best
    as dead. So a lineage whose children were ALL accepted was marked exhausted and
    dropped from GEPA's sampling pool — and unlike the global level there is no ratchet on
    this path, no stop event, nothing in the summary. Widening the per-instance Pareto
    frontier IS GEPA's mechanism, so an accept is never dead ground for a lineage.
    """
    cfg = plateau.PlateauConfig(lineage_window=4)
    rd = _rd(tmp_path)
    _step(rd, "champion", accept=True, val=1.0, parent_val=0.0, parent="other")
    for i in range(5):   # 5 children of `p_hot`, ALL ACCEPTED, all Δ>0, none topping 1.0
        _step(rd, f"hot{i}", accept=True, val=0.70 + i * 0.01, parent_val=0.60,
              parent="p_hot")
    st = plateau.assess(rd, cfg)
    assert st.exhausted_lineages == [], \
        f"an all-accepting lineage must stay in the pool, got {st.exhausted_lineages}"
    # ...while a genuinely dead lineage in the same run IS still reported.
    for i in range(4):
        _step(rd, f"cold{i}", accept=False, val=0.5, parent_val=0.5, parent="p_cold")
    assert plateau.assess(rd, cfg).exhausted_lineages == ["p_cold"]


def test_lineage_with_one_accept_in_the_tail_is_not_exhausted(tmp_path):
    """The narrower predicate at its boundary: a single accept inside the window keeps a
    lineage alive, whatever it did for the global best."""
    cfg = plateau.PlateauConfig(lineage_window=3)
    rd = _rd(tmp_path)
    _step(rd, "best", accept=True, val=1.0, parent_val=0.0, parent="seed")
    _step(rd, "a", accept=False, val=0.4, parent_val=0.5, parent="p1")
    _step(rd, "b", accept=True, val=0.6, parent_val=0.4, parent="p1")   # non-best accept
    _step(rd, "c", accept=False, val=0.4, parent_val=0.5, parent="p1")
    assert plateau.assess(rd, cfg).exhausted_lineages == []


def test_local_gate_tie_and_regression_are_distinguishable(tmp_path):
    """Review #7: ``series`` hardcoded ``delta: 0.0`` for every local-gate row, throwing
    away the ``child_sum``/``parent_sum`` the event already carries. Both are still dead
    (gepa's pass condition is a strict ``>``), but the series must not lie about which."""
    rd = _rd(tmp_path)
    rd.log_event("gepa_local_gate", candidate="tie", parent="seed",
                 child_sum=2.0, parent_sum=2.0, passed=False)
    rd.log_event("gepa_local_gate", candidate="reg", parent="seed",
                 child_sum=1.0, parent_sum=2.0, passed=False)
    rows = plateau.series(rd)
    assert rows[0]["delta"] == 0.0, rows[0]
    assert rows[1]["delta"] == -1.0, rows[1]
    assert all(plateau._dead(r) for r in rows), "both are still dead"


# ---- the crash and the prompt-assembly seam -------------------------------

def test_zero_iteration_loop_does_not_crash(tmp_path):
    """REGRESSION (review blocking #2) — ``NameError: cannot access local variable 'why'``.

    ``why`` was only bound inside the ``for i in range(max_iterations)`` body, but read
    after it. ``max_iterations=0`` — reachable from a spec and from a resume whose budget
    is already spent — crashed instead of returning a clean zero-iteration result.
    """
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult
    from cap_evolve.splits import Splits

    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=0))
    rd.write_splits(Splits(train=["t1"], val=["v1"], test=["s1"]))
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    rd.set_best("seed")
    base = SplitResult(split="val", reward=0.5, stderr=0.0,
                       per_task=[{"task_id": "v1", "reward": 0.5}])

    res = harness.hill_climb_loop(object(), run_dir=rd, optimizer=lambda w, i: None,
                                  current_val=base, max_iterations=0)
    assert res["iterations"] == 0 and res["steps"] == []
    assert res["stop_reason"], "a zero-iteration run must still report why"


def test_plateau_block_reaches_the_prompt_inside_the_cap(tmp_path):
    """REGRESSION (review blocking #3a + the #199 merge trap).

    Two things must hold at once and only one of them is about size:

    1. The block must be INSIDE whatever cap the tree has. It used to be appended after
       ``_augment_instructions``, escaping #222's ``MAX_INSTRUCTIONS_CHARS`` (measured
       64941 > 60000), and landing where truncation elides — so the one *behavioural*
       block would be dropped while the two context-only blocks survived.
    2. The block must actually ARRIVE. #199 replaces ``_focus_instructions`` with
       ``render_instructions`` and reassigns ``instructions``; resolving that conflict the
       obvious "keep both sides" way compiles clean with the plateau feature SILENTLY
       DEAD. This assertion is what makes a bad merge resolution fail loudly.
    """
    from cap_evolve import harness
    from cap_evolve.memory import History, RejectedMemory

    rd = _rd(tmp_path)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    block = plateau.prompt_block(plateau.PlateauState(level="diversify", run_length=9,
                                                      exhausted_lineages=["p1"]))
    assert block, "diversify must produce a block"
    # Signature-agnostic: #129/PR222 drops `rejected, history` from this function (it reads
    # them off the run dir instead). Only `extra` is #221's contract, so bind by NAME and
    # fill whatever positional memory params this tree still has.
    import inspect
    params = list(inspect.signature(harness._augment_instructions).parameters)
    extras = {"rejected": RejectedMemory(tmp_path / "r.jsonl"),
              "history": History(tmp_path / "h.jsonl")}
    kw = {k: v for k, v in extras.items() if k in params}
    out = harness._augment_instructions("BASE INSTRUCTIONS", workdir, rd, extra=block, **kw)
    assert "MATERIALLY DIFFERENT" in out, "the plateau block never reached the prompt"
    assert out.rstrip().endswith(block.rstrip()), \
        "the behavioural block must be LAST, in the tail truncation preserves"
    try:
        from cap_evolve.optimizer_context import MAX_INSTRUCTIONS_CHARS
    except Exception:                                  # pre-#222 tree: no cap to check
        return
    assert len(out) <= MAX_INSTRUCTIONS_CHARS, len(out)


def test_resume_carries_the_streak(tmp_path):
    """Review #9, documenting the intended behaviour rather than changing it: the streak
    is derived from the whole event log, so a resumed run re-derives ``stop`` before
    spending an iteration. A dead region is still dead after a restart; re-spending
    budget to rediscover it is the error this module exists to prevent. The escape hatch
    is ``plateau_stop: false`` / ``--no-plateau-stop``."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    for i in range(6):
        _step(rd, f"d{i}", accept=False, val=0.5, parent_val=0.5, parent="seed")
    assert plateau.assess(rd, cfg).level == "stop"

    reopened = RunDir(rd.root)                    # a fresh handle == what --resume does
    st = plateau.assess(reopened, cfg)
    assert st.level == "stop" and st.run_length == 6, st
    off = plateau.PlateauConfig(window=2, escalate_every=1, stop=False)
    assert plateau.assess(reopened, off).level == "diversify"


# ---- surfacing ------------------------------------------------------------

def test_dashboard_surfaces_plateau_state(tmp_path):
    from cap_evolve import dashboard

    rd = _rd(tmp_path)
    rd.log_event("splits", train=1, val=2, test=1)
    cfg = plateau.PlateauConfig(window=2, escalate_every=1, lineage_window=3)
    last = plateau.PlateauState()
    for i in range(5):
        _step(rd, f"d{i}", accept=False, val=0.0, parent_val=0.0, parent="seed")
        last = plateau.check(rd, cfg, last=last, algorithm="gepa")
    data = dashboard.reduce_run(rd)
    s = data["summary"]
    assert s["plateau"] and s["plateau"]["level"] == "stop", s["plateau"]
    assert s["exhausted_lineages"] == ["seed"], s["exhausted_lineages"]
    txt = dashboard.render_ansi(data)
    assert "PLATEAU" in txt and "exhausted lineage" in txt, txt


def test_plateau_state_is_not_liveness(tmp_path):
    """#118 classifies run LIVENESS (live/stalled/crashed/done) from events.jsonl
    mtime. Our vocabulary is disjoint by construction, so the two can never render
    contradictory words for the same condition."""
    assert set(plateau.LEVELS).isdisjoint({"live", "stalled", "crashed", "done", "idle",
                                           "failed", "incomplete"})
    # A plateaued run is by definition NOT stalled: it is appending events.
    rd = _rd(tmp_path)
    for i in range(8):
        _step(rd, f"d{i}", accept=False, val=0.0, parent_val=0.0, parent="seed")
    st = plateau.assess(rd, plateau.PlateauConfig(window=2, escalate_every=1))
    assert st.level == "stop" and st.iterations == 8, st
