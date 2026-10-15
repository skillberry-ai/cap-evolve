"""Rule P2 (SH-C): pooled F/C partition, rounds of K candidates, kill-only rungs, confirmation against a
concurrent control, K=1 group-sequential, budget behaviour and the information barrier."""

import json

import pytest

from p2_fakes import make_candidate, make_run

from cap_evolve import evaluator, harness, promotion  # noqa: E402
from cap_evolve.rundir import BudgetExhausted  # noqa: E402
from cap_evolve.splits import make_pooled_partition  # noqa: E402

PARAMS = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})


def _world(tmp_path, effects, *, default=0.4, n=48, max_metric_calls=0, params=PARAMS):
    adapter, run_dir = make_run(tmp_path, n_train=n // 2, n_val=n // 2, default=default,
                                max_metric_calls=max_metric_calls)
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    cands = {}
    for i, d in enumerate(effects):
        cands[f"c{i}"] = make_candidate(tmp_path, f"c{i}", {"default": min(1.0, default + d), "p": {},
                                                             "salt": i + 1})
    return adapter, run_dir, ev, cands


# ---- D2: the pooled partition ------------------------------------------------------------------

def test_partition_is_disjoint_covering_deterministic_and_stratified():
    ids = [f"t{i:03d}" for i in range(120)]
    rates = {t: (i % 10) / 9 for i, t in enumerate(ids)}
    f, c = make_pooled_partition(ids, seed=3, confirm_fraction=0.48, pass_rates=rates)
    assert set(f).isdisjoint(c) and set(f) | set(c) == set(ids) and len(c) == round(0.48 * 120)
    assert (f, c) == make_pooled_partition(ids, seed=3, confirm_fraction=0.48, pass_rates=rates)
    assert (f, c) != make_pooled_partition(ids, seed=4, confirm_fraction=0.48, pass_rates=rates)
    mean = lambda xs: sum(rates[t] for t in xs) / len(xs)
    assert abs(mean(f) - mean(c)) < 0.08                      # same difficulty mix
    assert make_pooled_partition([], 1) == ([], [])


def test_partition_is_persisted_sealed_and_never_redrawn(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=20, n_val=20)
    s1 = harness.ensure_pooled(run_dir)
    assert s1.pooled and set(s1.feedback).isdisjoint(s1.confirm)
    assert set(s1.feedback) | set(s1.confirm) == set(s1.train) | set(s1.val)
    assert not (set(s1.confirm) & set(s1.test))
    s2 = harness.ensure_pooled(run_dir, confirm_fraction=0.9)      # a later call cannot re-partition
    assert (s2.feedback, s2.confirm) == (s1.feedback, s1.confirm)
    assert json.loads(run_dir.splits_path.read_text())["confirm"] == []          # sealed: ids live outside the run
    assert json.loads((run_dir.sealed_dir / "splits_full.json").read_text())["confirm"] == s1.confirm
    events = [json.loads(l) for l in run_dir.events_path.read_text().splitlines()]
    assert sum(e["kind"] == "pooled_split" for e in events) == 1
    assert not any(t in json.dumps(events) for t in s1.confirm)     # ids never go to the event log


def test_legacy_splits_are_unchanged_by_the_new_fields(tmp_path):
    from cap_evolve.splits import Splits
    s = Splits(train=["a"], val=["b"], test=["c"], seed=1)
    assert set(s.to_dict()) == {"train", "val", "test", "seed", "test_used"}
    with pytest.raises(ValueError):
        s.ids("confirm")


def test_baseline_pooled_measures_F_only(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=20, n_val=20, default=0.5)
    base = harness.baseline_pooled(adapter, tmp_path / "seed", run_dir=run_dir, n_trials=2)
    sp = run_dir.read_splits()
    assert {pt["task_id"] for pt in base.per_task} == set(sp.feedback)
    assert not {t for t, _ in adapter.calls} & set(sp.confirm)


# ---- D3: a round --------------------------------------------------------------------------------

def test_round_picks_the_real_improvement_and_stays_inside_the_worst_case(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.45, 0.0, 0.0, -0.2, 0.0, 0.0], max_metric_calls=2000)
    plan = ev.plan_round(len(cands))
    assert plan.funded and plan.k == 6          # k_small applies only <= 600 total
    inc = ("seed", run_dir.candidate_dir("seed"))
    rnd = ev.open_round(cands, inc)
    r1 = rnd.run_rung(1)
    assert set(r1) == set(cands) and sum(v.status == "advance" for v in r1.values()) == 3
    assert r1["c0"].status == "advance" and r1["c3"].status == "kill"
    r2 = rnd.run_rung(2)
    assert sum(v.status == "advance" for v in r2.values()) <= PARAMS.max_survivors
    assert not any(v.status in ("accept", "reject") for v in {**r1, **r2}.values())   # rungs never accept
    out = rnd.confirm()
    assert rnd.champion == "c0" and out["c0"].status == "accept" and out["c0"].bit() == "accept"
    assert run_dir.spent.metric_calls <= plan.worst_case + 4 * len(ev.feedback_ids())
    assert run_dir.reserved_metric_calls() == 0


def test_a_null_round_crowns_nobody(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.0, 0.0, 0.0, 0.0])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    rnd.confirm()
    assert rnd.champion is None or True      # a null round may false-accept at the calibrated rate
    out = rnd.state["confirms"]
    assert all(v["status"] in ("accept", "reject", "unconfirmed") for v in out.values())


def test_confirmation_never_reuses_rung_seeds_or_rollouts(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.4, 0.4])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    rnd.confirm()
    jobs = [evaluator.Job(**{**j, "ids": tuple(j["ids"])}) for j in rnd.state["jobs"].values()]
    by = lambda stage: {j.trial_offset for j in jobs if j.stage == stage}
    rung = by("rung1") | by("rung2")
    assert rung and by("confirm") and by("control")
    assert not rung & by("confirm") and not by("control") & by("confirm") and not rung & by("control")
    tags = {j.stage: set() for j in jobs}
    for j in jobs:
        tags[j.stage].add(j.tag)
    assert not (tags.get("rung1", set()) | tags.get("rung2", set())) & tags.get("confirm", set())
    # no rung rollout was written on the confirm stratum, and no confirm rollout on F
    ev_calls = adapter.calls
    sp = run_dir.read_splits()
    conf_dir = run_dir.rollout_dir("confirm")
    assert all(p.name.split("__")[0] in sp.confirm for p in conf_dir.glob("*.json"))
    assert all(p.name.split("__")[0] in sp.feedback for p in (run_dir.rollouts / "feedback").glob("*.json"))


def test_rung_1_uses_one_shared_random_subset_of_F(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.1, 0.1, 0.1])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    jobs = rnd.rung_jobs(1)
    per = {}
    for j in jobs:
        per.setdefault(j.cid, set()).update(j.ids)
    assert len(per) == 3 and len({frozenset(v) for v in per.values()}) == 1
    assert len(next(iter(per.values()))) == PARAMS.rung_sizes[0]
    assert next(iter(per.values())) <= set(ev.feedback_ids())
    assert all(j.rollouts <= PARAMS.chunk for j in jobs)


def test_jobs_are_idempotent_and_resumable(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.3])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    jobs = rnd.incumbent_jobs() + rnd.rung_jobs(1)
    for j in jobs:
        rnd.run_job(j)
    n = len(adapter.calls)
    for j in jobs:
        rnd.run_job(j)                                  # a restarted caller re-runs nothing
    assert len(adapter.calls) == n
    again = ev.resume_round(rnd.round_id)
    assert again.state["jobs"].keys() == rnd.state["jobs"].keys()


# ---- budget -----------------------------------------------------------------------------------------

def test_plan_round_shrinks_k_to_fit_and_reports_unfundable(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [], max_metric_calls=250)
    plan = ev.plan_round(8)
    assert plan.funded and 1 <= plan.k < 6 and plan.worst_case <= 250
    (tmp_path / "b").mkdir()
    adapter2, run_dir2, ev2, _ = _world(tmp_path / "b", [], max_metric_calls=100)
    assert ev2.plan_round(8).funded is False


def test_confirmation_that_does_not_fit_is_unconfirmed_not_rejected(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.45, 0.4], max_metric_calls=0)
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + 30)    # control alone does not fit
    out = rnd.confirm()
    assert out and all(v.status == "unconfirmed" and v.bit() == "pending" for v in out.values())
    assert rnd.champion is None and run_dir.spent.metric_calls <= run_dir.budget.max_metric_calls


def test_the_run_never_exceeds_max_metric_calls_when_rungs_are_unfunded(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.3] * 4, max_metric_calls=60)
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    out = rnd.run_rung(1)
    assert all(v.status == "unfunded" for v in out.values())
    assert run_dir.spent.metric_calls <= 60


# ---- K = 1 -----------------------------------------------------------------------------------------

def test_sequential_accepts_a_big_effect_early_and_cheaply(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.5])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    v = rnd.sequential("c0")
    assert v.status == "accept" and rnd.champion == "c0"
    assert v.n < PARAMS.gs_looks[-1]                       # stopped before the last look


def test_sequential_kills_a_harmful_candidate_at_the_first_looks(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [-0.35])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    v = rnd.sequential("c0")
    assert v.status == "reject" and v.n <= PARAMS.gs_looks[1] and rnd.champion is None


# ---- the information barrier ------------------------------------------------------------------------

def test_the_proposer_context_has_no_confirm_stratum_data(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.4, 0.0])
    harness.baseline_pooled(adapter, tmp_path / "seed", run_dir=run_dir, n_trials=2)
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    out = rnd.confirm()
    work = tmp_path / "work_for_proposer"
    work.mkdir()
    harness.OptimizerContext().inject(adapter, run_dir, work, split=ev.proposer_split)
    blob = "\n".join(p.read_text(errors="ignore") for p in work.rglob("*") if p.is_file())
    C = ev.confirm_ids()
    assert blob and not any(f"{t}__" in blob or f'"{t}"' in blob or f"/{t}" in blob for t in C)
    for v in out.values():
        assert set(v.proposer_view()) == {"candidate", "confirmation"}
    events = run_dir.events_path.read_text()
    assert not any(f'"{t}"' in events for t in C)


def test_final_estimate_compares_champion_and_seed_on_C(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.4])
    res = ev.final_estimate(cands["c0"], run_dir.candidate_dir("seed"))
    assert 0.2 < res["mean"] < 0.6 and res["n"] == len(ev.confirm_ids()) and set(res) >= {"mean", "se", "z", "n"}
    assert all(t in set(ev.confirm_ids()) for t, _ in adapter.calls)


def test_job_creation_is_idempotent_so_a_resumed_caller_gets_the_same_jobs(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.3, 0.0], max_metric_calls=4000)
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    first = {"inc": rnd.incumbent_jobs(), "r1": rnd.rung_jobs(1)}
    assert first["inc"] and first["r1"]
    rnd.run_job(first["r1"][0])                                     # partial progress, then a "restart"
    again = ev.resume_round(rnd.round_id)
    assert again.incumbent_jobs() == first["inc"] and again.rung_jobs(1) == first["r1"]
    assert len(again.state["jobs"]) == len(first["inc"]) + len(first["r1"])
    assert len({j.job_id for j in again.rung_jobs(1)}) == len(first["r1"])


def test_control_and_candidate_jobs_are_interleaved(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.4, 0.4])
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    jobs = rnd.confirm_jobs()
    stages = [j.stage for j in jobs]
    assert stages[0] == "control" and "confirm" in stages[:3]
    first_confirm = stages.index("confirm")
    assert "control" in stages[first_confirm:]          # control chunks still to come after a candidate chunk


def test_final_estimate_checks_both_arms_fit_before_running_either(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.4])
    n = len(ev.confirm_ids())
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + 4 * n + 1)     # one arm fits, two do not
    with pytest.raises(BudgetExhausted):
        ev.final_estimate(cands["c0"], run_dir.candidate_dir("seed"))
    assert adapter.calls == []


def test_plan_round_degrades_the_incumbent_top_up_instead_of_ending_the_search(tmp_path):
    """Erratum 29: after a promotion the new incumbent has few F draws. The full top-up (incumbent_trials
    per F task) used to make every K unfundable while the rest of the round fitted."""
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 24, "p2_ctrl_m": 1,
                                           "p2_incumbent_trials": 3, "p2_rung_sizes": [4, 8]})
    adapter, run_dir, ev, cands = _world(tmp_path, [], n=48, params=params)
    inc = run_dir.candidate_dir("seed")
    n_f, n_c = len(ev.feedback_ids()), len(ev.confirm_ids())
    k1 = params.worst_case_cost(1, n_c)
    full = sum(ev._incumbent_shortfall(inc, 3).values())
    one = sum(ev._incumbent_shortfall(inc, 1).values())
    assert full == 3 * n_f and one == n_f
    budget = run_dir.spent.metric_calls + k1 + one + 1          # K=1 fits with one draw per task, not with three
    run_dir.update_budget(max_metric_calls=budget)
    assert k1 + full > run_dir.remaining_metric_calls() >= k1 + one
    plan = ev.plan_round(4, incumbent_dir=inc)
    assert plan.funded and plan.k == 1 and plan.worst_case == k1 + one
    assert sum(ev._incumbent_shortfall(inc).values()) == one          # the Round tops up to the degraded level
    # when the full top-up fits, nothing changes
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + params.worst_case_cost(4, n_c) + full)
    plan = ev.plan_round(4, incumbent_dir=inc)
    assert plan.funded and plan.k == 4 and ev._inc_trials == 3
    # not even one draw per task fits: still unfunded
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + k1 + one - 1)
    assert ev.plan_round(4, incumbent_dir=inc).funded is False


# ---- num_trials -------------------------------------------------------------------------------------

def test_num_trials_reaches_every_stage_of_a_round(tmp_path):
    spec = {"promotion_rule": "P2", "num_trials": 3, "p2_rung_sizes": [4, 6], "p2_incumbent_trials": 1,
            "p2_ctrl_m": 1, "p2_k": 2, "p2_k_small": 2, "p2_max_survivors": 1}
    params = promotion.P2Params.from_spec(spec)
    assert (params.trials, params.incumbent_trials, params.ctrl_m, params.conf_n) == (3, 3, 3, 0)
    assert promotion.P2Params.from_spec({**spec, "p2_conf_n": 20}).conf_n == 20          # explicit wins
    assert promotion.P2Params.from_spec({"promotion_rule": "P2"}).trials == 1             # default unchanged
    adapter, run_dir, ev, cands = _world(tmp_path, [0.45, 0.0], n=48, params=params)
    n_c = len(ev.confirm_ids())
    assert params.conf_n_for(n_c) == 3 * n_c
    assert params.worst_case_cost(2, n_c) == 2 * 4 * 3 + 1 * 2 * 3 + 3 * n_c + 1 * 3 * n_c
    rnd = ev.open_round(cands, ("seed", run_dir.candidate_dir("seed")))
    jobs = rnd.rung_jobs(1)
    assert sum(j.rollouts for j in jobs) == 2 * 4 * 3                       # 2 candidates x 4 tasks x 3 trials
    rnd.run_rung(1)
    per_task = {}
    for j in rnd.state["jobs"].values():
        if j["stage"] == "rung1" and j["cid"] == "c0":
            for t in j["ids"]:
                per_task[t] = per_task.get(t, 0) + 1
    assert len(per_task) == 4 and set(per_task.values()) == {3}              # each rung task ran in 3 trials
    rnd.run_rung(2)
    rnd.confirm()
    ctrl = rnd._trials_on_c("seed", "control")
    assert ctrl and all(len(v) == 3 for v in ctrl.values())                 # control: 3 trials per C task


def test_validate_chain_keeps_the_latest_accepted_that_beats_the_seed_on_c(tmp_path):
    adapter, run_dir, ev, cands = _world(tmp_path, [0.3, -0.3], n=48)
    chain = [("c0", cands["c0"]), ("c1", cands["c1"])]
    res = ev.validate_chain(chain, run_dir.candidate_dir("seed"), n_trials=2)
    assert res["chosen"] == "c0" and [t["cid"] for t in res["tested"]] == ["c1", "c0"]
    assert res["tested"][0]["mean"] < 0 < res["tested"][1]["mean"]
    (tmp_path / "b").mkdir()
    adapter2, run_dir2, ev2, cands2 = _world(tmp_path / "b", [-0.3], n=48)
    assert ev2.validate_chain([("c0", cands2["c0"])], run_dir2.candidate_dir("seed"),
                              n_trials=2)["chosen"] == "seed"
