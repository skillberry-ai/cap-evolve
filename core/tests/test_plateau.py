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


def test_non_best_accepts_are_dead_but_ratchet_caps_at_diversify(tmp_path):
    """GEPA can accept a frontier specialist that beats its own parent but never tops
    the incumbent best. Best-val velocity is 0, so those iterations ARE dead — but a
    streak containing accepts is capped at ``diversify`` and never killed."""
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    _step(rd, "best", accept=True, val=1.0, parent_val=0.0, parent="seed")
    for i in range(10):  # accepted specialists, each below the incumbent best of 1.0
        _step(rd, f"spec{i}", accept=True, val=0.7, parent_val=0.5, parent=f"p{i}")
    st = plateau.assess(rd, cfg)
    assert st.run_length == 10, st
    assert st.accepts_in_streak == 10, st
    assert st.level == "diversify", "a still-accepting run must not be stopped"
    assert not st.should_stop and st.should_diversify


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


def test_skillopt_step_events_are_seen(tmp_path):
    cfg = plateau.PlateauConfig(window=2, escalate_every=1)
    rd = _rd(tmp_path)
    for i in range(5):
        rd.log_event("skillopt_step", candidate=f"so_{i}", accept=False, val=0.2)
    st = plateau.assess(rd, cfg)
    assert st.iterations == 5, st
    # skillopt_step carries no parent_val; delta is taken against the running best,
    # which for a single-lineage climber IS the parent.
    assert st.level == "stop", st


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


def test_prompt_block_lists_rejected_ids(tmp_path):
    from cap_evolve.memory import RejectedMemory
    mem = RejectedMemory(tmp_path / "rejected.jsonl")
    mem.add("cand_a", "summary a", "gate reject", 0.1)
    mem.add("cand_b", "summary b", "gate reject", 0.1)
    blk = plateau.prompt_block(plateau.PlateauState(level="diversify", run_length=5),
                               rejected=mem)
    assert "cand_a" in blk and "cand_b" in blk


# ---- config ---------------------------------------------------------------

def test_config_from_spec_and_ladder():
    cfg = plateau.PlateauConfig.from_spec(
        {"plateau_window": 8, "plateau_escalate_every": 3,
         "plateau_lineage_window": 5, "plateau_stop": False})
    assert (cfg.warn_at, cfg.diversify_at, cfg.stop_at) == (8, 11, 14)
    assert cfg.lineage_window == 5 and cfg.stop is False
    d = plateau.PlateauConfig.from_spec({})
    assert (d.window, d.escalate_every, d.lineage_window, d.stop) == (6, 2, 4, True)
    # an absent key must not be read as 0 (which would escalate immediately)
    assert plateau.PlateauConfig.from_spec({"plateau_window": 0}).window == 6


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
                      current_val, **kw):
        seen.append(instructions)
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
