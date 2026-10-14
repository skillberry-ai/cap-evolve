"""AO-2 conductor, focus rule (``ao_focus``): a candidate is judged only on the champion's failing tasks
plus a few passing canaries and promoted directly; no full-set screen, no fresh-trial confirmation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402

import conductor  # noqa: E402
import policy  # noqa: E402


def test_focus_verdict_table():
    fixed = [1.0, 0.5, 1.0, 0.5, 1.0, 0.5, 1.0, 0.5]                  # 8 failing tasks, large jumps
    assert policy.focus_verdict(fixed, [0.0] * 6, 30, 16)["verdict"] == "accept"
    assert policy.focus_verdict([0.0] * 8, [0.0] * 6, 30, 16)["verdict"] == "kill"
    assert policy.focus_verdict(fixed, [-0.5] * 6, 30, 16)["verdict"] == "kill"      # breaks the passing stratum
    assert policy.focus_verdict([0.5, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0], [0.0] * 6, 30, 16)["verdict"] == "more"
    assert policy.focus_verdict([], [], 30, 16)["verdict"] == "more"
    v = policy.focus_verdict([1.0] * 4, [-1.0, 0.0], 10, 6)                          # gain = (4 - 6*0.5)/10
    assert v["gain"] == pytest.approx(0.1)


def _cells(w, tag):
    h = w.hash(tag)
    return {t for (hh, t, k) in w.rows if hh == h}


def test_focus_promotes_on_failing_tasks_without_full_evals(tmp_path):
    spend, champs = {}, {}
    for focus in (False, True):
        spec = {"max_metric_calls": 6000, "max_candidates": 12, "ao_plateau_n": 99, "ao_focus": focus}
        w, be, cfg = F.make(tmp_path / str(focus), spec=spec, world_kw={"salt": 4, "seed_trials": 3, "base": 0.85},
                            rungs=() if focus else (8, 16), k_prop=2)
        c = F.run_to_done(w, be, cfg, max_ticks=6000)
        spend[focus] = len(w.rows) - 3 * len(F.TASKS)
        champs[focus] = [t for t, n in c.st["nodes"].items() if n.get("why") == "promoted"]
        if focus:
            assert champs[True], "a focus run promotes real fixes"
            full = [t for t in c.st["nodes"] if t != "seed" and t not in champs[True] and _cells(w, t) >= set(F.TASKS)]
            assert not full, f"non-champion candidates must never be evaluated on every task: {full}"
            # every promotion really improved the true pass probability of the incumbent
            def truth(t):
                return sum(F.p_of(w.cands[t]["genes"], x) for x in F.TASKS) / len(F.TASKS)
            seq = ["seed"] + champs[True]
            assert all(truth(b) > truth(a) for a, b in zip(seq, seq[1:])), [round(truth(t), 3) for t in seq]
    assert spend[True] < spend[False], spend


def test_focus_is_opt_in():
    assert conductor.Cfg.from_spec({}).focus is False
    c = conductor.Cfg.from_spec({"ao_focus": True, "ao_focus_n": 3, "ao_focus_canary": 2})
    assert (c.focus, c.focus_n, c.focus_canary) == (True, 3, 2)


def test_a_new_champion_is_judged_against_a_fresh_fill_not_its_winning_trials(tmp_path):
    spec = {"max_metric_calls": 6000, "max_candidates": 12, "ao_plateau_n": 99, "ao_focus": True}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"salt": 4, "seed_trials": 3, "base": 0.85}, k_prop=2)
    c = F.run_to_done(w, be, cfg, max_ticks=6000)
    champs = [t for t, n in c.st["nodes"].items() if n.get("why") == "promoted"]
    assert champs
    for t in champs:
        lo, hi = c.st["nodes"][t]["ref_window"]
        assert lo >= conductor.FILL_BASE and hi - lo == conductor.FILL_N
        h = w.hash(t)
        assert all((h, x, k) in w.rows for x in F.TASKS for k in range(lo, hi)), "fresh fill on every task"


def test_focus_near_misses_with_disjoint_wins_are_merged(tmp_path):
    spec = {"max_metric_calls": 9000, "max_candidates": 30, "ao_plateau_n": 99, "ao_focus": True,
            "ao_merge": True, "ao_merge_bar": 0.3}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"salt": 6, "seed_trials": 3, "base": 0.85, "quality": 0.25},
                        k_prop=3)
    be.wins = lambda tags, base: {t: {f"w{t}"} for t in tags}          # every pair fully complementary
    c = F.run_to_done(w, be, cfg, max_ticks=8000)
    merges = [t for t, n in c.st["nodes"].items() if n.get("edit_kind") == "merge"]
    assert merges, "near misses (gain > 0, not accepted) get merged under focus"


def test_proposer_failing_block_lists_rates_traces_primary_and_rejected():
    import proposer
    txt = proposer.failing_block({"7": [0.0, 0.0, 0.0], "3": [1.0, 0.0], "0": [1.0, 1.0]},
                                 {"7": ["7__seed__t0.json"], "3": ["3__seed__t1.json"]}, ["7"],
                                 ["cand_1: transfer rule -> focus_no_gain gain +0.01"])
    assert "7: 0/3" in txt and "3: 1/2" in txt and "0:" not in txt.split("traces")[0]
    assert "PRIMARY tasks (sibling jobs take the others): 7" in txt and "7__seed__t0.json" in txt
    assert "3__seed__t1.json" not in txt, "a slot reads its primary tasks' traces"
    assert "cand_1: transfer rule" in txt


def test_a_champion_that_passes_everything_prunes_candidates_instead_of_parking_them(tmp_path):
    spec = {"max_metric_calls": 3000, "max_candidates": 4, "ao_plateau_n": 99, "ao_focus": True}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"seed_trials": 3, "reward_fn": lambda cand, task, k: 1.0})
    c = F.run_to_done(w, be, cfg, max_ticks=3000)
    assert all(n.get("why") == "no_focus_targets" for t, n in c.st["nodes"].items() if t != "seed")


def test_small_proposals_are_refused_with_a_reason_under_focus(tmp_path):
    from types import SimpleNamespace
    import unittest.mock as m
    import conductor_backend
    import proposer
    parent, work = tmp_path / "p", tmp_path / "w"
    for d in (parent, work):
        (d / "tools").mkdir(parents=True)
        (d / "tools" / "tools.py").write_text("x = 1\n")
    (work / "JOURNAL.md").write_text("\n".join(f"note {i}" for i in range(200)))       # memory, not the edit
    assert proposer.capability_diff_lines(parent, work) == 0
    fake = SimpleNamespace(cfg=SimpleNamespace(focus=True), spec={}, run_dir=tmp_path)
    with m.patch.object(conductor_backend.digest, "cand_dir", lambda rd, t: parent):
        small = conductor_backend.RealBackend._too_small(fake, {"kind": "propose"}, work, "seed", {"predicted_tasks": ["1"]})
        assert "too small" in small and "0 changed" in small
        (work / "tools" / "tools.py").write_text("x = 1\n" + "\n".join(f"def f{i}(): return {i}" for i in range(45)))
        assert conductor_backend.RealBackend._too_small(fake, {"kind": "propose"}, work, "seed",
                                                        {"predicted_tasks": ["1", "2", "3"]}) == ""
        assert conductor_backend.RealBackend._too_small(fake, {"kind": "merge"}, work, "seed", {}) == ""
        fake.cfg.focus = False
        assert conductor_backend.RealBackend._too_small(fake, {"kind": "propose"}, parent, "seed", {}) == ""


def _rate(task):
    return 1.0 if int(task[1:]) % 3 else 0.0             # a third of the tasks fail for everyone


def test_a_lucky_promotion_is_reverted_by_the_fresh_fill(tmp_path):
    """Candidates look perfect on their selection-era trials but are the seed on fresh trials (seen live):
    the fill check reverts every such promotion, so the champion stays the seed."""
    def reward(cand, task, trial):
        if cand["genes"] and trial < conductor.FILL_BASE:
            return 1.0
        return _rate(task)
    spec = {"max_metric_calls": 3000, "max_candidates": 4, "ao_plateau_n": 99, "ao_focus": True}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"seed_trials": 3, "reward_fn": reward}, k_prop=1)
    c = F.run_to_done(w, be, cfg, max_ticks=4000)
    assert c.champion == "seed"
    assert any(n.get("why") == "fill_reject" for n in c.st["nodes"].values())


def test_a_real_gain_survives_the_fill_check(tmp_path):
    def reward(cand, task, trial):
        return 1.0 if cand["genes"] else _rate(task)
    spec = {"max_metric_calls": 3000, "max_candidates": 3, "ao_plateau_n": 99, "ao_focus": True}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"seed_trials": 3, "reward_fn": reward}, k_prop=1)
    c = F.run_to_done(w, be, cfg, max_ticks=4000)
    assert c.champion != "seed" and c.st["nodes"][c.champion]["fill"]["fill_mean_delta"] > 0


def test_one_trial_never_accepts(tmp_path):
    spec = {"max_metric_calls": 3000, "max_candidates": 3, "ao_plateau_n": 99, "ao_focus": True}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"seed_trials": 3, "reward_fn": lambda c, t, k: 1.0 if c["genes"] else _rate(t)},
                        k_prop=1)
    c = F.run_to_done(w, be, cfg, max_ticks=4000)
    assert all(n.get("trials", 2) >= 2 for n in c.st["nodes"].values() if n.get("why") == "promoted")


def test_a_revert_restores_the_runs_best_and_an_unfundable_fill_reverts(tmp_path):
    def reward(cand, task, trial):
        if cand["genes"] and trial < conductor.FILL_BASE:
            return 1.0
        return _rate(task)
    restored = []
    spec = {"max_metric_calls": 3000, "max_candidates": 3, "ao_plateau_n": 99, "ao_focus": True}
    w, be, cfg = F.make(tmp_path, spec=spec, world_kw={"seed_trials": 3, "reward_fn": reward}, k_prop=1)
    be.restore_champion = restored.append
    c = F.run_to_done(w, be, cfg, max_ticks=4000)
    assert c.champion == "seed" and restored and set(restored) == {"seed"}
    # a promotion whose fill can no longer be funded is reverted at drain, never finalized unchecked
    c.st["champion"] = "cand_1"
    c.node("cand_1").update(status="champion", fill_check="seed", ref_window=[9000, 9002])
    c.fits = lambda need: False
    assert c.drain() and c.champion == "seed" and c.node("cand_1")["why"] == "fill_unfunded"
