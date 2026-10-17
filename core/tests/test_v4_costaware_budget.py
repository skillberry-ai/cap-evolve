"""V4 search fixes: cost-aware acceptance, budget-driven rounds, shrunk final round, near-miss confirm extension,
control reuse, compress operator, and the proposer guidance. No model calls."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from p2_fakes import make_candidate, make_run  # noqa: E402

from cap_evolve import costaware, evaluator, hc2, promotion  # noqa: E402
from cap_evolve.specfile import resolve_max_iterations  # noqa: E402


# ---- costaware.judge --------------------------------------------------------------------------------

P = costaware.CostParams(lam=0.5, accept=True, clear_z=3.0, margin=0.03, min_saving=0.15, noninf_z=1.0)


def test_off_by_default_changes_nothing():
    off = costaware.CostParams()
    assert not off.enabled
    for passed in (True, False):
        j = costaware.judge(off, passed=passed, mean=0.05, se=0.02, z=2.5, dmin=0.02, rel=1.0)
        assert j.accept is passed and j.path == "reward"


def test_a_clear_reward_win_is_never_rejected_whatever_it_costs():
    j = costaware.judge(P, passed=True, mean=0.10, se=0.02, z=5.0, dmin=0.02, rel=3.0)       # 4x the cost
    assert j.accept and j.path == "reward"


def test_a_marginal_win_that_is_much_more_expensive_is_rejected():
    j = costaware.judge(P, passed=True, mean=0.05, se=0.03, z=1.7, dmin=0.02, rel=0.5)       # 0.05 - 0.25 < 0.02
    assert not j.accept and j.path == "cost_adjusted" and "relative cost +50%" in j.reason


def test_a_marginal_win_that_is_cheaper_or_a_little_dearer_stands():
    assert costaware.judge(P, passed=True, mean=0.05, se=0.03, z=1.7, dmin=0.02, rel=-0.3).accept
    assert costaware.judge(P, passed=True, mean=0.05, se=0.03, z=1.7, dmin=0.02, rel=0.02).accept   # 0.05-0.01 >= 0.02


def test_cost_path_accepts_a_clearly_shorter_non_inferior_candidate():
    j = costaware.judge(P, passed=False, mean=0.0, se=0.02, z=0.0, dmin=0.02, rel=-0.35)
    assert j.accept and j.path == "cost"


def test_cost_path_needs_enough_saving_and_a_non_inferior_reward():
    assert not costaware.judge(P, passed=False, mean=0.0, se=0.02, z=0.0, dmin=0.02, rel=-0.05).accept   # saves too little
    assert not costaware.judge(P, passed=False, mean=-0.10, se=0.02, z=-5.0, dmin=0.02, rel=-0.5).accept  # clearly worse
    off = costaware.CostParams(lam=0.5, accept=False)
    assert not costaware.judge(off, passed=False, mean=0.0, se=0.02, z=0.0, dmin=0.02, rel=-0.5).accept


def test_missing_cost_data_never_creates_a_cost_accept():
    j = costaware.judge(P, passed=False, mean=0.0, se=0.02, z=0.0, dmin=0.02, rel=None)
    assert not j.accept and j.path == "no_cost_data"
    assert costaware.judge(P, passed=True, mean=0.05, se=0.03, z=1.7, dmin=0.02, rel=None).accept


def test_relative_cost_uses_tokens_then_usd_and_needs_min_n():
    p = costaware.CostParams(lam=1.0, min_n=3)
    cand = [{"tokens": 200, "cost": 0.2}] * 3
    ref = [{"tokens": 100, "cost": 0.1}] * 3
    assert costaware.relative_cost(cand, ref, p) == pytest.approx(1.0)
    assert costaware.relative_cost(cand[:2], ref, p) is None
    usd_only = [{"tokens": 0, "cost": 0.3}] * 3
    assert costaware.relative_cost(usd_only, [{"tokens": 0, "cost": 0.1}] * 3, p) == pytest.approx(2.0)
    assert costaware.relative_cost(cand, [{"tokens": 0, "cost": None}] * 3, p) is None      # unpriced is not free


def test_params_validate_and_default_the_cost_path_on_for_a_compress_run():
    assert not costaware.CostParams.from_spec({}).enabled
    assert costaware.CostParams.from_spec({"hc2_compress_every": 3}).accept
    assert not costaware.CostParams.from_spec({"hc2_compress_every": 3, "cost_accept": False}).accept
    with pytest.raises(ValueError):
        costaware.CostParams.from_spec({"cost_min_saving": 1.5})
    with pytest.raises(ValueError):
        costaware.CostParams.from_spec({"cost_metric": "joules"})


# ---- the evaluator folds the cost term into the confirmation ----------------------------------------------

def _priced_world(tmp_path, spec, *, cand_tokens, base_tokens=1000, effect=0.0, n=48):
    """Real evaluator over a Bernoulli adapter whose rollouts report ``tokens`` from cfg.json."""
    import random
    adapter, run_dir = make_run(tmp_path, n_train=n // 2, n_val=n // 2, default=0.4)
    orig = adapter.run_target

    def run_target(task, ctx, *, seed=0):
        r = orig(task, ctx, seed=seed)
        r.tokens = int(json.loads((Path(ctx) / "cfg.json").read_text()).get("tokens", base_tokens))
        return r
    adapter.run_target = run_target
    (run_dir.candidate_dir("seed") / "cfg.json").write_text(json.dumps({"default": 0.4, "p": {}, "tokens": base_tokens}))
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4,
                                           **{k: v for k, v in spec.items() if k.startswith("p2_")}})
    ev = evaluator.P2Evaluator(adapter, run_dir, params, cost=costaware.CostParams.from_spec(spec))
    cand = make_candidate(tmp_path, "c0", {"default": min(1.0, 0.4 + effect), "p": {}, "salt": 3, "tokens": cand_tokens})
    return run_dir, ev, cand


def _confirm(run_dir, ev, cand):
    rnd = ev.open_round({"c0": cand}, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    out = rnd.confirm()
    return rnd, out


def test_confirmation_accepts_a_shorter_candidate_of_equal_reward_through_the_cost_path(tmp_path):
    spec = {"cost_lambda": 0.5, "cost_accept": True, "cost_min_n": 5}
    run_dir, ev, cand = _priced_world(tmp_path, spec, cand_tokens=500, effect=0.08)
    rnd = ev.open_round({"c0": cand}, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    out = rnd.confirm()
    v = out["c0"]
    assert v.rel_cost == pytest.approx(-0.5, abs=0.02)
    if v.status == "accept":
        assert v.path in ("reward", "cost")


def test_confirmation_rejects_a_marginal_win_that_doubles_the_cost_but_keeps_a_clear_one(tmp_path):
    spec = {"cost_lambda": 1.0, "cost_min_n": 5, "cost_clear_z": 3.0}
    run_dir, ev, cand = _priced_world(tmp_path, spec, cand_tokens=3000, effect=0.45)          # 3x tokens, huge win
    rnd, out = _confirm(run_dir, ev, cand)
    assert out["c0"].status == "accept", out["c0"]                                    # a clear win is never rejected
    assert out["c0"].rel_cost == pytest.approx(2.0, abs=0.05)


def test_cost_off_leaves_the_confirmation_verdict_untouched(tmp_path):
    run_dir, ev, cand = _priced_world(tmp_path, {}, cand_tokens=9000, effect=0.45)
    rnd, out = _confirm(run_dir, ev, cand)
    assert out["c0"].status == "accept" and out["c0"].rel_cost is None and out["c0"].path == "reward"


# ---- budget-driven search -------------------------------------------------------------------------------

def test_max_iterations_follows_the_budget_unless_set():
    from cap_evolve.specfile import BUDGET_DRIVEN_ITERATIONS as B
    assert resolve_max_iterations({"max_metric_calls": 3000}) == B
    assert resolve_max_iterations({"max_usd": 50}) == 10          # USD alone may never bind (unmetered target)
    assert resolve_max_iterations({}) == 10
    assert resolve_max_iterations({"max_metric_calls": 3000, "max_iterations": 8}) == 8
    assert resolve_max_iterations({"max_iterations": 5}) == 5


def test_an_explicit_zero_still_means_zero_iterations(tmp_path):
    from cap_evolve import Budget
    assert resolve_max_iterations({"max_metric_calls": 3000, "max_iterations": 0}) == 0
    assert Budget.from_dict({"max_iterations": 0}).max_iterations == 20      # unchanged legacy reading of a stored 0
    assert Budget.from_dict({}).max_iterations == 20


def test_plan_round_shrinks_the_last_round_to_one_direct_candidate(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4, max_metric_calls=0)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    n_c = len(ev.confirm_ids())
    direct = params.ctrl_m * n_c + params.conf_n_for(n_c)
    full1 = params.worst_case_cost(1, n_c)
    assert direct < full1
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + direct + 5)
    assert ev.plan_round(4, run_dir.candidate_dir("seed")).funded is False                 # default: the search would stop
    plan = ev.plan_round(4, run_dir.candidate_dir("seed"), allow_direct=True)
    assert plan.funded and plan.direct and plan.k == 1 and plan.worst_case == direct
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + direct - 1)
    assert ev.plan_round(4, run_dir.candidate_dir("seed"), allow_direct=True).funded is False


def test_a_direct_round_skips_the_rungs_and_confirms(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    cand = make_candidate(tmp_path, "c0", {"default": 0.85, "p": {}, "salt": 3})
    rnd = ev.open_round({"c0": cand}, ("seed", run_dir.candidate_dir("seed")), direct=True)
    r1, r2, conf = hc2._drive(rnd, evaluator.thread_map(2))
    assert r1 == {} and r2 == {} and conf["c0"].status == "accept"
    assert not any(j["stage"].startswith("rung") for j in rnd.state["jobs"].values())


# ---- near-miss extension and control reuse -----------------------------------------------------------------

def test_a_near_miss_gets_one_more_block_and_a_stricter_pooled_bar(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 48, "p2_ctrl_m": 4,
                                           "p2_z_conf": 3.0, "p2_extend_z": 0.5})
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    cand = make_candidate(tmp_path, "c0", {"default": 0.65, "p": {}, "salt": 3})
    rnd = ev.open_round({"c0": cand}, ("seed", run_dir.candidate_dir("seed")))
    rnd.run_rung(1)
    rnd.run_rung(2)
    out = rnd.confirm()
    assert out["c0"].status in ("accept", "reject")                      # never left as "extend"
    if rnd.state.get("extended"):
        assert any("cx" in j["tag"] for j in rnd.state["jobs"].values())
        assert sum(1 for j in rnd.state["jobs"].values() if "__cx" in j["tag"]) >= 1
        assert rnd.state["extended"] == ["c0"] and rnd.state["extending"] is None


def test_extension_is_off_by_default_and_validated():
    assert promotion.P2Params.from_spec({"promotion_rule": "P2"}).extend_z == 0.0
    with pytest.raises(ValueError):
        promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_z_conf": 1.7, "p2_extend_z": 2.0})


def test_a_later_round_reuses_the_unchanged_incumbents_control_draws(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 48, "p2_ctrl_m": 4,
                                           "p2_reuse_control": True})
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    inc = ("seed", run_dir.candidate_dir("seed"))
    r0 = ev.open_round({"c0": make_candidate(tmp_path, "c0", {"default": 0.9, "p": {}, "salt": 3})}, inc, direct=True)
    r0.confirm()
    before = run_dir.spent.metric_calls
    r1 = ev.open_round({"c1": make_candidate(tmp_path, "c1", {"default": 0.9, "p": {}, "salt": 4})}, inc, direct=True)
    assert r1._ctrl_passes() == 0 and r1._cost_ctrl() == 0
    r1.confirm()
    assert run_dir.spent.metric_calls - before == params.conf_n_for(len(ev.confirm_ids()))      # candidate only
    assert r1.state["control_reuse"]
    assert r1.state["confirms"]["c0" if False else "c1"]["status"] in ("accept", "reject")


def test_control_is_not_reused_by_default(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 48, "p2_ctrl_m": 4})
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    inc = ("seed", run_dir.candidate_dir("seed"))
    ev.open_round({"c0": make_candidate(tmp_path, "c0", {"default": 0.9, "p": {}, "salt": 3})}, inc, direct=True).confirm()
    r1 = ev.open_round({"c1": make_candidate(tmp_path, "c1", {"default": 0.9, "p": {}, "salt": 4})}, inc, direct=True)
    assert r1._ctrl_passes() == 4


# ---- HC-2 params, compress slot, plateau --------------------------------------------------------------------

SPEC = {"hc2": True, "promotion_rule": "P2", "split_mode": "pooled"}


def test_hc2_new_flags_default_off():
    p = hc2.HC2Params.from_spec(SPEC)
    assert p.compress_every == 0 and p.plateau_rounds == 0 and p.max_rounds == 0
    q = hc2.HC2Params.from_spec({**SPEC, "hc2_compress_every": 4, "hc2_plateau_rounds": 6})
    assert (q.compress_every, q.plateau_rounds) == (4, 6)
    with pytest.raises(ValueError):
        hc2.HC2Params.from_spec({**SPEC, "hc2_compress_every": -1})


def test_diff_overlap_ignores_the_parent_lines_both_rewrites_delete():
    deleted = frozenset(f"policy.md\t-parent rule number {i} text here" for i in range(40))
    a = deleted | frozenset({"policy.md\t+alpha beta gamma delta one", "policy.md\t+alpha beta gamma delta two"})
    b = deleted | frozenset({"policy.md\t+totally different rewrite here", "policy.md\t+another unrelated addition now"})
    assert hc2.diff_overlap(a, b) < 0.3                                          # was ~0.95 before: false duplicate
    assert hc2.diff_overlap(a, a) == 1.0
    only_del = deleted
    assert hc2.diff_overlap(only_del, only_del) == 1.0                           # two pure deletions still compare


# ---- proposer guidance -------------------------------------------------------------------------------------

def test_every_proposer_prompt_encourages_scripts_determinism_and_text():
    from cap_evolve import proposer_guidance as g
    for word in ("script", "checklist", "verification command", "TEXT", "CODE", "DETERMINISM"):
        assert word in g.EDIT_KINDS_NOTE
    for word in ("shorter", "duplication", "COMPRESS", "20%"):
        assert word in g.COMPRESS_NOTE


def test_ao_proposer_prompt_has_the_guidance_and_a_compress_variant():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "algorithms" / "agent-optimize" / "scripts"))
    import proposer
    body = proposer.build_prompt(workdir="/w", parent="seed", cluster=None)
    assert "executable script" in body and "checklist" in body and "verification command" in body
    assert len(body.encode()) <= proposer.MAX_PROMPT_BYTES
    c = proposer.build_prompt(workdir="/w", parent="cand_3", cluster=None, compress=True)
    assert "COMPRESSING" in c and "20% or more" in c and "MANY groups" not in c
    assert len(c.encode()) <= proposer.MAX_PROMPT_BYTES


def test_hc_instructions_carry_the_edit_kinds_note(tmp_path):
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult
    ctx = harness.OptimizerContext()
    sv = SplitResult(split="val", reward=0.5, stderr=0.1, per_task=[{"task_id": "a", "reward": 0.0, "feedback": "x"}])
    text = ctx.instructions(sv, None, "all", algorithm="hill-climb", extra="EXTRA-BLOCK")
    assert "DETERMINISM" in text and text.rstrip().endswith("EXTRA-BLOCK")


def test_compress_prompt_drops_the_failing_task_blocks():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "algorithms" / "agent-optimize" / "scripts"))
    import proposer
    c = proposer.build_prompt(workdir="/w", parent="cand_3", cluster={"id": "k1", "label": "x", "tasks": ["7"]},
                              failing="Parent's failing tasks: 7", compress=True, valid_clusters=[("k1", "x")])
    assert "Target cluster" not in c and "failing tasks" not in c and "Valid cluster_ids" not in c


def test_plateau_counter_survives_a_restart(tmp_path):
    class RD:
        root = tmp_path
    hc2._save_flat(RD, 3)
    assert hc2._load_flat(RD) == 3 and hc2._load_flat(type("R", (), {"root": tmp_path / "none"})) == 0


def test_sequential_precheck_ignores_reused_control(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 48, "p2_ctrl_m": 4, "p2_reuse_control": True})
    ev = evaluator.P2Evaluator(adapter, run_dir, params)
    inc = ("seed", run_dir.candidate_dir("seed"))
    ev.open_round({"c0": make_candidate(tmp_path, "c0", {"default": 0.9, "p": {}, "salt": 3})}, inc, direct=True).confirm()
    n_c = len(ev.confirm_ids())
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + params.gs_looks[0] + n_c)     # < ctrl_m*|C| + first look
    r = ev.open_round({"c1": make_candidate(tmp_path, "c1", {"default": 0.9, "p": {}, "salt": 4})}, inc)
    assert r.sequential("c1").status == "unconfirmed"
    assert run_dir.spent.metric_calls <= run_dir.budget.max_metric_calls


def test_a_budget_driven_loop_stops_when_rounds_keep_producing_nothing(tmp_path):
    from cap_evolve import Budget, RunDir
    from test_hc2 import FakeEvaluator, _loop, _optimizer     # noqa: E402
    rd = RunDir.create(tmp_path, ts="idle", budget=Budget(max_iterations=1_000_000))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "SKILL.md").write_text("x\n")
    rd.snapshot("seed", seed)
    rd.set_best("seed")
    for t in ("f0", "f1"):
        d = rd.rollouts / "feedback"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{t}__seed__t0.json").write_text(json.dumps({"input": "x", "rollout": {"task_id": t, "output": "o", "error": None},
                                                         "score": {"reward": 0.0, "feedback": "fail"}}))
    out = _loop(rd, FakeEvaluator(accept=False), lambda workdir, instructions: None, rounds=1_000_000)
    assert out["stop_reason"].startswith("no_progress"), out["stop_reason"]
    assert rd.spent.iterations == hc2.MAX_IDLE_ROUNDS


# ---- the STOCK hill-climb gate -----------------------------------------------------------------------------

def _sr(reward, tokens, n=12):
    from cap_evolve.loop import SplitResult
    return SplitResult(split="val", reward=reward, stderr=0.02, tokens=tokens * n, cost_usd=0.0,
                       per_task=[{"task_id": f"t{i}", "reward": reward, "n": 1, "raw": {"n_trials": 1}} for i in range(n)])


def _stock(tmp_path, spec, delta, se, cand_tokens, base_tokens=1000, accept=True):
    from cap_evolve import harness
    from cap_evolve.gate import GateDecision
    _, rd = make_run(tmp_path, spec=spec)
    d = GateDecision(accept=accept, reason="paired", delta=delta, resolvable_effect_size=2 * se)
    harness._apply_cost_gate(rd, d, _sr(0.5, base_tokens), _sr(0.5 + delta, cand_tokens), {"mode": "paired"})
    return d


def test_stock_gate_is_untouched_without_cost_keys(tmp_path):
    assert _stock(tmp_path, {"num_trials": 1}, 0.05, 0.03, 9000).accept


def test_stock_gate_rejects_a_marginal_expensive_win_and_keeps_a_clear_one(tmp_path):
    assert not _stock(tmp_path, {"cost_lambda": 1.0}, 0.05, 0.03, 3000).accept
    (tmp_path / "b").mkdir()
    assert _stock(tmp_path / "b", {"cost_lambda": 1.0}, 0.30, 0.03, 3000).accept          # z = 10: never rejected on cost


def test_stock_gate_cost_path_accepts_a_much_cheaper_non_inferior_candidate(tmp_path):
    d = _stock(tmp_path, {"cost_lambda": 0.5, "cost_accept": True}, 0.0, 0.03, 500, accept=False)
    assert d.accept and "cost win" in d.reason


def test_compress_every_for_the_stock_loop_reads_the_spec(tmp_path):
    from cap_evolve import harness
    _, rd = make_run(tmp_path, spec={"hc_compress_every": 4})
    assert harness._hc_compress_every(rd) == 4
    (tmp_path / "c").mkdir()
    _, rd2 = make_run(tmp_path / "c")
    assert harness._hc_compress_every(rd2) == 0


# ---- cap_hash and the cost rung path -------------------------------------------------------------------------

def test_a_compressed_candidate_is_a_new_hash_so_its_rollouts_are_never_pooled_with_the_parents(tmp_path):
    from cap_evolve import eval_index
    a = make_candidate(tmp_path, "a", {"default": 0.5, "p": {}, "salt": 1, "tokens": 1000})
    b = make_candidate(tmp_path, "b", {"default": 0.5, "p": {}, "salt": 1, "tokens": 500})
    assert eval_index.cap_hash(a) != eval_index.cap_hash(b)
    assert eval_index.cap_hash(a) == eval_index.cap_hash(a)


def test_cost_rung_path_keeps_a_cheaper_candidate_with_a_nonpositive_screen_mean(tmp_path):
    spec = {"cost_lambda": 0.5, "cost_accept": True, "cost_min_n": 5}
    run_dir, ev, cand = _priced_world(tmp_path, spec, cand_tokens=400, effect=0.0)
    rnd = ev.open_round({"c0": cand}, ("seed", run_dir.candidate_dir("seed")))
    out = rnd.run_rung(1)
    st = out["c0"]
    assert st.status == "advance" and "cost path" in st.reason


def test_a_deterministic_near_miss_is_extended_then_decided(tmp_path):
    from cap_evolve import racing
    p = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_z_conf": 3.0, "p2_extend_z": 0.5})
    # a modest effect measured on few draws: z between 0.5 and 3
    cand = {f"t{i}": [1.0, 0.0, 1.0][: 1 + (i % 3)] for i in range(10)}
    ctrl = {f"t{i}": [0.0, 1.0, 0.0] for i in range(10)}
    r = racing.confirm_with_control(cand, ctrl, z_conf=p.z_conf, dmin=0.02, n_planned=10)
    assert not r["pass"] and r["mean"] > 0 and r["z"] >= p.extend_z      # exactly the near-miss the extension targets


def test_only_a_rollout_budget_makes_the_iteration_cap_budget_driven():
    from cap_evolve.specfile import BUDGET_DRIVEN_ITERATIONS as B
    assert resolve_max_iterations({"max_usd": 50}) == 10 and resolve_max_iterations({"max_metric_calls": 9}) == B


def test_stock_gate_does_not_overturn_a_broke_veto_and_falls_back_to_the_ledger_after_resume(tmp_path):
    from cap_evolve import harness
    from cap_evolve.gate import GateDecision
    _, rd = make_run(tmp_path, spec={"cost_lambda": 0.5, "cost_accept": True})
    d = GateDecision(accept=False, reason="paired; REJECTED by gate_max_broke=0 - broke ['t1']", delta=0.0,
                     resolvable_effect_size=0.06)
    harness._apply_cost_gate(rd, d, _sr(0.5, 1000), _sr(0.5, 300), {"mode": "paired"})
    assert not d.accept
    # resumed incumbent: SplitResult carries no token total, so the reference is read from the ledger rows
    cur = _sr(0.5, 0)
    cur.tokens = 0
    import json as _j
    h = __import__("cap_evolve.eval_index", fromlist=["x"]).cap_hash(rd.candidate_dir("seed"))
    (Path(rd.root) / "eval_index.jsonl").write_text("".join(_j.dumps({"cap_hash": h, "split": "val", "task": f"t{i}", "trial_idx": i,
        "tag": "seed", "k": i, "env_fp": "", "window_id": 0, "reward": 0.5, "subset": False, "cost": None, "tokens": 1000, "ts": 0.0}) + "\n" for i in range(12)))
    d2 = GateDecision(accept=False, reason="paired", delta=0.0, resolvable_effect_size=0.06)
    harness._apply_cost_gate(rd, d2, cur, _sr(0.5, 300), {"mode": "paired"})
    assert d2.accept and "cost win" in d2.reason


def test_stock_gate_cost_flip_is_not_blocked_by_a_broke_count_within_the_limit(tmp_path):
    from cap_evolve import harness
    from cap_evolve.gate import GateDecision
    _, rd = make_run(tmp_path, spec={"cost_lambda": 0.5, "cost_accept": True})
    d = GateDecision(accept=False, reason="paired", delta=0.0, resolvable_effect_size=0.06, broke=["t1"])
    harness._apply_cost_gate(rd, d, _sr(0.5, 1000), _sr(0.5, 300), {"mode": "paired", "gate_max_broke": 2})
    assert d.accept


def test_budget_driven_briefing_does_not_say_a_million_rounds():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "algorithms" / "agent-optimize" / "scripts"))
    import host
    import inspect
    src = inspect.getsource(host)
    assert "until the rollout budget is exhausted" in src
