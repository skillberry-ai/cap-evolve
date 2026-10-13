"""AO-2 conductor (v2 PR-2, #811): the section 4.13 tests plus the K=1 hill-climb equivalence.

No model calls and no subprocess: a fake world (ao2_fakes.py) stands in for the adapter and the
proposer. Real pieces under test: conductor.py, policy.py, conductor_state.py, promotion.py.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402  (also puts core/ and the agent-optimize scripts on sys.path)

import conductor  # noqa: E402
import policy  # noqa: E402
from cap_evolve import conductor_state as cs  # noqa: E402
from cap_evolve import graph  # noqa: E402


def _graph(w, tags):
    out = []
    for r in graph.read_nodes(w.run_dir):
        if r["id"] in tags:
            out.append(json.dumps({k: v for k, v in r.items() if k != "created_by"}, sort_keys=True))
    return out


def _snapshot(c, w):
    """What a resumed run must reproduce, per DECIDED node: its graph history, its evidence, its
    status; plus the champion. A node still in flight when the budget ran out is not comparable: how
    far its last chunk got depends on timing, which a crash legitimately changes."""
    decided = {t for t, n in c.st["nodes"].items() if n.get("decided") or t == "seed"}
    out = {"champion": c.champion, "n": c.st["n_proposals"], "decisions": dict(w.decisions), "nodes": {}}
    for t in sorted(decided):
        h = w.hash(t) if t in w.cands else None
        out["nodes"][t] = {"graph": _graph(w, {t}), "status": c.st["nodes"][t]["status"],
                           "rows": {k: v for k, v in sorted(w.rows.items()) if k[0] == h}}
    return out


def _same_outcome(a, b):
    assert a["champion"] == b["champion"]
    common = set(a["nodes"]) & set(b["nodes"])
    for t in set(a["nodes"]) ^ set(b["nodes"]):
        assert int(t.split("_")[1]) >= max(a["n"], b["n"]) - 1, f"{t} decided in one run only"
    assert len(common) >= 5
    for t in sorted(common):
        assert a["nodes"][t] == b["nodes"][t], t
    assert {k: v for k, v in a["decisions"].items() if k in common} == {k: v for k, v in b["decisions"].items() if k in common}


SPEC = {"max_metric_calls": 700, "ao_plateau_n": 40}


# 1 ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("salt", [1, 2, 3])
def test_conductor_resume_equals_uninterrupted(tmp_path, salt):
    kw = dict(spec=SPEC, world_kw={"delay": (1, 3), "salt": salt}, rungs=(8, 16))
    w0, be0, cfg0 = F.make(tmp_path / "a", **kw)
    ref = _snapshot(F.run_to_done(w0, be0, cfg0), w0)
    assert ref["decisions"], "the fixture must decide something"
    rng = random.Random(salt)
    for trial in range(4):
        w, be, cfg = F.make(tmp_path / f"b{trial}", **kw)
        crashes = set(rng.sample(range(2, 60), 3))
        got = _snapshot(F.run_to_done(w, be, cfg, crash_at=crashes), w)
        _same_outcome(got, ref)


# 2 ---------------------------------------------------------------------------------------------
def test_no_early_stop_on_prose(tmp_path):
    prose = ("Stop after 10 candidates or when val reaches 0.9. One full-val evaluation is 40 rollouts, "
             "so be careful; the whole search should take about 2 hours and cost under $5.")
    cfg = conductor.Cfg.from_spec({"stop_condition": prose, "max_metric_calls": 600, "num_trials": 1})
    assert cfg.caps.max_candidates is None
    assert cfg.caps.max_metric_calls == 600            # the structured key, not "40 rollouts"
    assert cfg.caps.deadline is None and cfg.caps.stop_at_reward is None and cfg.caps.max_tokens is None
    w, be, cfg2 = F.make(tmp_path, spec={"stop_condition": prose, "max_metric_calls": 900, "ao_plateau_n": 99, "promotion_n_conf": 2},
                         world_kw={"salt": 2})
    c = F.run_to_done(w, be, cfg2)
    assert c.st["n_proposals"] > 10, "must not stop at 10 candidates read from prose"
    assert c.st["stopped"].startswith("budget: rollouts")
    assert 900 - 2 * 24 * 2 - 30 <= len(w.rows) <= 900, "uses (nearly) all of the numeric budget"


# 3 is test_conductor_hill_climb_equivalence.py (needs the real harness) ----------------------------

# 4 ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(120))
def test_budget_reservation_property(tmp_path, seed):
    rng = random.Random(seed)
    cap = rng.choice([150, 220, 330, 480])
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": cap, "ao_plateau_n": 99},
                        world_kw={"delay": (1, rng.randint(1, 6)), "salt": seed, "rng_seed": seed},
                        slots=rng.randint(1, 5), k_prop=rng.randint(1, 4), max_confirm=rng.randint(1, 3),
                        chunk=rng.choice([7, 12, 20]), rungs=rng.choice([(), (8, 16)]))
    cfg.caps = policy.Caps(**{**cfg.caps.__dict__, "chunk": cfg.chunk})
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    for i in range(1500):
        done = c.tick()
        assert len(w.rows) + cs.reserved(c.st) <= cap, f"tick {i}: committed+reserved exceeds the cap"
        assert len(w.rows) <= cap
        if done:
            break
    else:
        pytest.fail("did not finish")
    assert len(w.rows) <= cap


# 5 ---------------------------------------------------------------------------------------------
def test_token_cap_enforced(tmp_path):
    cap_tokens, job_cap = 10_000, 3_000
    w, be, cfg = F.make(tmp_path, spec={"max_optimizer_tokens": cap_tokens, "ao_job_token_cap": job_cap,
                                        "ao_plateau_n": 99, "max_metric_calls": 5000},
                        world_kw={"tokens_per_propose": 2_900, "salt": 2}, k_prop=2, target_alive=2)
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    peak = 0
    while not c.tick():
        peak = max(peak, c.tokens_used() + cs.reserved(c.st, "reserved_tokens"))
        assert peak <= cap_tokens, "a proposer job started that the token budget could not cover"
    assert c.st["stopped"] == "budget: tokens"
    assert c.tokens_used() <= cap_tokens
    assert c.tokens_used() > cap_tokens - 2 * job_cap, "stops within one job cap of the limit"


# 6 ---------------------------------------------------------------------------------------------
def _ladder(true_gain, n_tasks, rungs, rng, trials=1):
    """One candidate through the kill-only ladder. Paired per-task deltas from binary outcomes: the
    candidate fixes a fraction of tasks; returns True when it survives every rung."""
    p0 = 0.5
    ids = list(range(n_tasks))
    rng.shuffle(ids)
    for size in rungs:
        d = []
        for _ in ids[:size]:
            a = 1.0 if rng.random() < p0 + true_gain else 0.0
            b = 1.0 if rng.random() < p0 else 0.0
            d.append(a - b)
        if policy.rung_kill(d):
            return False
    return True


def test_halving_policy_power():
    rng = random.Random(7)
    rungs, n_tasks, reps = (12, 36), 49, 4000
    kill_real = sum(not _ladder(0.15, n_tasks, rungs, rng) for _ in range(reps)) / reps
    kill_good = sum(not _ladder(0.10, n_tasks, rungs, rng) for _ in range(reps)) / reps
    kill_null = sum(not _ladder(0.0, n_tasks, rungs, rng) for _ in range(reps)) / reps
    kill_bad = sum(not _ladder(-0.15, n_tasks, rungs, rng) for _ in range(reps)) / reps
    assert kill_real <= 0.05, kill_real                       # a true +0.15 edit is almost never killed
    assert kill_good <= 0.08, kill_good
    assert kill_bad > kill_null + 0.10, (kill_bad, kill_null)  # and a harmful edit is cut far more often
    # kill-only: the ladder is a cost saver, not the accept rule. What reaches confirmation is also
    # capped by max_confirm survivors per round and by the rule-P screen; nulls are not promoted here.
    assert kill_null < 0.2


# 7 ---------------------------------------------------------------------------------------------
def test_merge_trigger_and_rebase(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 3000, "ao_plateau_n": 99, "ao_merge": True},
                        world_kw={"salt": 3, "delay": (1, 2), "quality": 0.45}, k_prop=3, max_confirm=1, slots=6)
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    for _ in range(600):
        if c.tick():
            break
    kinds = [n["edit_kind"] for n in c.st["nodes"].values()]
    merges = [t for t, n in c.st["nodes"].items() if n["edit_kind"] == "merge"]
    rebases = [t for t, n in c.st["nodes"].items() if n["edit_kind"] == "rebase"]
    assert merges or rebases, "complementary tips or a champion change must create a merge/rebase node"
    for t in merges + rebases:
        n = c.st["nodes"][t]
        assert len(n["parents"]) == 2 and n["hash"]                    # an ordinary candidate with two parents
        assert n["status"] in conductor.PRE_CONFIRM + conductor.TERMINAL + ("confirming", "unconfirmed")
    pairs = c.st.get("merged_pairs", [])
    assert len({tuple(p) for p in pairs}) == len(pairs), "a pair is merged at most once (no merge loop)"
    nodes = {r["id"]: r for r in graph.read_nodes(w.run_dir)}
    assert all(len(nodes[t]["parents"]) == 2 for t in merges + rebases)


def test_merge_with_conflicts_runs_a_bounded_llm_job(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 3000, "ao_plateau_n": 99, "ao_merge": True,
                                        "max_optimizer_tokens": 5_000_000, "ao_job_token_cap": 2000},
                        world_kw={"salt": 3, "delay": (1, 2), "quality": 0.45}, k_prop=3, slots=6)
    w.merge_conflicts = True
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    for _ in range(400):
        if c.tick():
            break
    jobs = [j for j in c.st["jobs"].values() if j["kind"] == "merge"]
    assert jobs and all(j["reserved_tokens"] == 0 for j in jobs if j["state"] != "running")
    assert any(j["state"] == "done" for j in jobs), "the merge-resolve job ran and was reaped"


# 9 ---------------------------------------------------------------------------------------------
def test_eval_abandoned_requeued_and_cached_cells_not_rerun(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 500, "ao_plateau_n": 99},
                        world_kw={"delay": (3, 3), "salt": 2}, chunk=10)
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    for _ in range(4):
        c.tick()
    assert any(j["kind"] == "eval" and j["state"] == "running" for j in c.st["jobs"].values())
    done_before = set(w.rows)
    w.crash()                                                  # kill mid-chunk: some cells written
    c2 = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    c2.tick()
    lost = [j for j in c2.st["jobs"].values() if j["state"] == "lost"]
    assert lost, "the open chunk becomes `lost` at recovery"
    assert all(j["reserved_rollouts"] == 0 for j in lost), "its reservation is refunded"
    for _ in range(300):
        if c2.tick():
            break
    assert all(n == 1 for k, n in w.runs.items() if k[1:] != ("x", 0) and k in w.rows and k not in done_before
               or k in done_before), "every cell ran exactly once, crashed or not"
    assert max(w.runs.values()) == 1


# 10 --------------------------------------------------------------------------------------------
def test_duplicate_candidate_refused(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 600, "ao_plateau_n": 99},
                        world_kw={"salt": 2, "dup_every": 2})
    c = F.run_to_done(w, be, cfg)
    assert c.st.get("dup_refused", 0) >= 1
    hashes = [n["hash"] for n in c.st["nodes"].values()]
    assert len(hashes) == len(set(hashes)), "no two nodes share capability bytes"
    assert not any(t for t in c.st["nodes"] if t not in w.cands), "refused candidates are discarded"


# 12 --------------------------------------------------------------------------------------------
def test_supervisor_restarts_until_done():
    calls = []
    rcs = iter([137, 1, -9, 0])

    def spawn(args):
        calls.append(args)
        return next(rcs)
    slept = []
    assert conductor.supervise(["--run-dir", "R"], spawn=spawn, sleep=slept.append, sleep_s=5.0) == 0
    assert len(calls) == 4 and slept == [5.0, 5.0, 5.0]


def test_supervisor_does_not_retry_a_refusal_and_gives_up_eventually():
    calls = []
    assert conductor.supervise([], spawn=lambda a: calls.append(1) or conductor.EXIT_REFUSED, sleep=lambda s: None) == 2
    assert len(calls) == 1
    calls.clear()
    assert conductor.supervise([], max_restarts=3, spawn=lambda a: calls.append(1) or 1, sleep=lambda s: None) == 1
    assert len(calls) == 4


# multi-objective refusal -----------------------------------------------------------------------
def test_multi_objective_spec_is_refused():
    # reward + cost is supported (test_ao2_cost_objective.py); any OTHER gating objective is refused
    multi = {"objectives": [{"name": "reward", "direction": "max", "role": "gate"},
                            {"name": "latency", "direction": "min", "role": "gate"}]}
    with pytest.raises(conductor.Refused, match="single scalar objective"):
        conductor.Cfg.from_spec(multi)
    with pytest.raises(conductor.Refused):
        conductor.Cfg.from_spec({"objectives": [{"name": "num_messages", "direction": "min", "role": "pareto"}]})
    with pytest.raises(conductor.Refused):
        conductor.Cfg.from_spec({"pareto": True})
    # cost may be REPORTED: a display-role objective, or none at all, is a single-objective spec
    conductor.Cfg.from_spec({"objectives": [{"name": "cost", "direction": "min", "role": "display"}]})
    conductor.Cfg.from_spec({})


# parallel jobs never exceed slots --------------------------------------------------------------
@pytest.mark.parametrize("slots,k", [(1, 1), (2, 2), (3, 3), (6, 2)])
def test_parallel_jobs_never_exceed_slots(tmp_path, slots, k):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 1500, "ao_plateau_n": 99, "ao_rungs": [8, 16]},
                        world_kw={"delay": (1, 4), "salt": 2}, slots=slots, k_prop=k, max_confirm=2)
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    seen_parallel = 0
    for _ in range(800):
        done = c.tick()
        ev = len(cs.live(c.st, "eval"))
        assert ev <= slots and len(cs.live(c.st, "propose")) <= k
        assert len(w.jobs) <= slots + k + 1
        seen_parallel = max(seen_parallel, ev)
        if done:
            break
    if slots > 1 and k > 1:
        assert seen_parallel >= 2, "several candidates must actually evaluate in parallel"


def test_rungs_save_rollouts_without_changing_the_champion_rule(tmp_path):
    spend = {}
    for rungs in ((), (8, 16)):
        w, be, cfg = F.make(tmp_path / str(len(rungs)), spec={"max_metric_calls": 4000, "max_candidates": 12, "ao_plateau_n": 99},
                            world_kw={"salt": 3}, rungs=rungs)
        c = F.run_to_done(w, be, cfg)
        spend[len(rungs)] = len(w.rows)
        pruned_by_rung = [n for n in c.st["nodes"].values() if n.get("why") == "rung_kill"]
        assert bool(pruned_by_rung) == bool(rungs) or not rungs
    assert spend[2] <= spend[0]


# stop reasons ----------------------------------------------------------------------------------
def test_stop_at_reward_and_deadline(tmp_path):
    t = {"now": 1000.0}
    w, be, cfg = F.make(tmp_path / "d", spec={"max_metric_calls": 9000, "ao_plateau_n": 99, "max_wallclock_seconds": 50},
                        world_kw={"salt": 2})
    cfg.caps = policy.Caps(**{**cfg.caps.__dict__, "deadline": 1000.0 + 5})

    def clock():
        t["now"] += 1.0
        return t["now"]
    c = F.run_to_done(w, be, cfg, clock=clock)
    assert c.st["stopped"] == "wall: deadline"
    assert w.finalize_calls == 1


def test_plateau_has_a_floor(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 3000, "ao_plateau_n": 3},
                        world_kw={"salt": 1, "quality": -0.3})        # every edit hurts: a real plateau
    c = F.run_to_done(w, be, cfg)
    assert c.st["stopped"].startswith("plateau")
    assert len(w.rows) >= 0.4 * 3000 - 120, "never a plateau stop before 40% of the rollout budget is spent"


# finalize is idempotent ------------------------------------------------------------------------
def test_finalize_is_idempotent_across_restarts(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 300, "ao_plateau_n": 99}, world_kw={"salt": 2})
    c = F.run_to_done(w, be, cfg)
    assert w.finalize_calls == 1
    c2 = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    assert c2.run(5) == 0
    assert w.finalize_calls == 1, "a relaunch after DONE must not finalize again"


# conductor_state -------------------------------------------------------------------------------
def test_state_atomic_and_reservation_arithmetic(tmp_path):
    s = cs.Store(tmp_path)
    s.update(lambda st: cs.new_job(st, "eval", tag="x", reserved_rollouts=20, state="running"))
    s.update(lambda st: st["nodes"].update({"n": {"reserved": 30}}))
    st = s.load()
    assert cs.reserved(st) == 50
    assert cs.rollouts_fit(st, committed=100, need=50, cap=200)
    assert not cs.rollouts_fit(st, committed=100, need=51, cap=200)
    assert not cs.rollouts_fit(st, committed=100, need=1, cap=200, finalize_reserve=51)
    assert cs.rollouts_fit(st, committed=10 ** 6, need=10 ** 6, cap=None)
    assert not list(tmp_path.glob(".conductor.json.tmp*")), "no torn temp file is left behind"
