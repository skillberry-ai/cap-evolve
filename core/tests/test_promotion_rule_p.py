"""Shared promotion rule P (analysis_plan section 8): screen (unmasked, k_se) then fresh-trial confirm.

Pure-function tests plus a hill-climb integration with a fake noisy adapter. The key is OPT-IN: with
no ``promotion_rule`` the step is exactly today's.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import promotion  # noqa: E402


def test_params_default_and_from_spec():
    p = promotion.PromotionParams()
    assert (p.k_se, p.n_conf, p.dmin, p.z_conf) == (1.0, 10, 0.02, 2.0)
    assert promotion.PromotionParams.from_spec({}) is None
    q = promotion.PromotionParams.from_spec({"promotion_rule": "P", "promotion_n_conf": 5, "promotion_dmin": 0.0})
    assert q.n_conf == 5 and q.dmin == 0.0 and q.z_conf == 2.0
    with pytest.raises(ValueError):
        promotion.PromotionParams.from_spec({"promotion_rule": "Q"})


def test_screen_is_strict_k_se():
    d = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    r = promotion.screen(d, 1.0)
    assert r["mean"] == pytest.approx(0.125) and r["pass"] is (r["mean"] > r["se"])
    assert promotion.screen([0.0] * 5, 1.0)["pass"] is False
    assert promotion.screen([0.1], 1.0)["pass"] is False      # n<2: no SE, no screening pass


def test_confirm_needs_dmin_and_z():
    big = [0.1, 0.12, 0.08, 0.11, 0.09, 0.1]
    assert promotion.confirm(big, 0.02, 2.0)["pass"] is True
    assert promotion.confirm([0.01] * 6, 0.02, 2.0)["pass"] is False          # SE 0 but below dmin
    assert promotion.confirm([0.1] * 6, 0.02, 2.0)["pass"] is True           # SE 0, mean>=dmin
    noisy = [0.5, -0.4, 0.45, -0.35, 0.4, -0.3]
    assert promotion.confirm(noisy, 0.02, 2.0)["pass"] is False
    assert promotion.confirm([0.5], 0.02, 2.0)["pass"] is False


def test_decide_calls_confirm_only_after_screen_pass():
    calls = []
    res = promotion.decide([0.0] * 6, lambda: calls.append(1) or [0.1] * 6, promotion.PromotionParams())
    assert not res.promote and res.stage == "screen_reject" and not calls
    res = promotion.decide([0.1, 0.12, 0.08, 0.1], lambda: calls.append(1) or [0.0, 0.01, -0.01, 0.0],
                           promotion.PromotionParams())
    assert not res.promote and res.stage == "confirm_reject" and calls
    res = promotion.decide([0.1, 0.12, 0.08, 0.1], lambda: [0.1, 0.12, 0.08, 0.1], promotion.PromotionParams())
    assert res.promote and res.stage == "promoted"
    d = res.to_dict()
    assert d["rule"] == "P" and d["screen"]["pass"] and d["confirm"]["pass"]


# ---- hill-climb integration ---------------------------------------------------------------

TASKS = [f"t{i:02d}" for i in range(24)]


class _Adapter:
    """Reward is a per-task probability from cfg.json; the trial outcome is a seeded Bernoulli, so a
    screening fluke does NOT repeat on fresh seeds."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in TASKS]

    def run_target(self, task, ctx, *, seed=0):
        import random
        from cap_evolve import Rollout
        cfg = json.loads((Path(ctx) / "cfg.json").read_text())
        p = cfg["p"].get(task.id, cfg["default"])
        u = random.Random(f"{task.id}:{seed}:{cfg.get('salt', 0)}").random()
        return Rollout(task_id=task.id, output="pass" if u < p else "fail", trace="x")

    def score(self, task, rollout):
        from cap_evolve import Score
        r = 1.0 if rollout.output == "pass" else 0.0
        return Score(task_id=task.id, reward=r, trial_rewards=[r])

    def apply(self, candidate_dir, edits=None):
        return None


def _setup(tmp_path, n_trials):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.json").write_text(json.dumps({"default": 0.5, "p": {}}))
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="pp")
    run_dir.write_splits(Splits(train=[], val=list(TASKS), test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")
    adapter = _Adapter()
    base = harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                                      split="val", tag="seed", n_trials=n_trials)
    return adapter, run_dir, base


def _opt(cfg):
    import tempfile
    from cap_evolve import harness
    f = Path(tempfile.mkdtemp()) / "c.json"
    f.write_text(json.dumps(cfg))
    code = "import sys,pathlib; w=pathlib.Path(sys.argv[1]); (w/'cfg.json').write_text(pathlib.Path(sys.argv[2]).read_text())"
    return harness.optimizer_from_command(["python3", "-c", code, "{workdir}", str(f)])


def _run(tmp_path, cand_cfg, gate_kwargs, n_trials=2):
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, n_trials)
    step = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                            optimizer=_opt(cand_cfg), instructions="x", current_val=base, n_trials=n_trials,
                            gate_kwargs={"mode": "paired", "k_se": 1.0, **gate_kwargs})
    return run_dir, step, base


def _events(run_dir, kind):
    return [json.loads(l) for l in run_dir.events_path.read_text().splitlines() if l.strip()
            and json.loads(l).get("kind") == kind]


def test_true_improvement_is_promoted_and_baseline_is_the_confirmation(tmp_path):
    cfg = {"default": 0.9, "p": {}}
    run_dir, step, base = _run(tmp_path, cfg, {"promotion_rule": "P", "promotion_n_conf": 6})
    assert step["accepted"] is True
    assert step["promotion"]["stage"] == "promoted"
    assert step["baseline_val"] is not None and step["baseline_val"] != step["candidate_val"]
    ev = _events(run_dir, "step")[-1]
    assert ev["promotion"]["confirm"]["n"] == len(TASKS)


def test_null_edit_that_wins_the_screen_is_rejected_by_fresh_confirmation(tmp_path):
    """Search seeds until the null edit passes the screen by luck; fresh trials must then reject it."""
    from cap_evolve import harness
    found = 0
    for i in range(80):
        sub = tmp_path / f"r{i}"
        sub.mkdir()
        adapter, run_dir, base = _setup(sub, 1)
        # candidate is behaviourally identical (p=0.5) but a different capability: new tag, same seeds
        cand = {"default": 0.5, "p": {}, "salt": i + 1}
        step = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                                optimizer=_opt(cand), instructions="x", current_val=base, n_trials=1,
                                candidate_id=f"cand_{i}",
                                gate_kwargs={"mode": "paired", "k_se": 1.0, "promotion_rule": "P",
                                             "promotion_n_conf": 8})
        if step["promotion"]["screen"]["pass"]:
            found += 1
            assert step["accepted"] is False and step["promotion"]["stage"] == "confirm_reject"
            assert step.get("baseline_val") is None
            break
    assert found >= 1, "test setup never produced a lucky screen"


def test_default_has_no_promotion_stage(tmp_path):
    run_dir, step, _ = _run(tmp_path, {"default": 0.9, "p": {}}, {})
    assert "promotion" not in step and "baseline_val" not in step
    assert "promotion" not in _events(run_dir, "step")[-1]


def test_p_unmasks_the_footprint_and_ignores_noise_floor_keys(tmp_path):
    run_dir, step, _ = _run(tmp_path, {"default": 0.9, "p": {}}, {"promotion_rule": "P", "promotion_n_conf": 4})
    ev = _events(run_dir, "step")[-1]
    assert ev["delta_masked"] == ev["delta_full"]


# ---- agent-optimize judge_p: same function, no reward_gated, fresh trials only ---------------

def _ao():
    scripts = str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import act
    return act


class _SR:
    def __init__(self, rewards, reward=0.5):
        self.per_task = [{"task_id": f"t{i}", "reward": r, "raw": {"n_trials": 2, "errored_trials": 0}}
                         for i, r in enumerate(rewards)]
        self.reward = reward


def _fake_ctx(tmp_path, spec):
    from types import SimpleNamespace
    (tmp_path / "rollouts" / "val").mkdir(parents=True)
    run_dir = SimpleNamespace(rollouts=tmp_path / "rollouts")
    return SimpleNamespace(spec=spec, root=tmp_path, run_dir=run_dir, val_ids=lambda: [f"t{i}" for i in range(8)],
                           check_budget=lambda a: None, cfg={"cost_gating": True})


def _patch(monkeypatch, act, screen_c, screen_r, fresh_c, fresh_r, calls):
    def split(run_dir, tag, split_name, min_trial=0, **kw):
        fresh = min_trial > 0
        return _SR((fresh_c if tag == "cand" else fresh_r) if fresh else (screen_c if tag == "cand" else screen_r))
    monkeypatch.setattr(act.harness, "split_result_from_rollouts", split)
    monkeypatch.setattr(act, "sh", lambda cmd, env=None: calls.append(cmd) or (0, "", ""))
    monkeypatch.setattr(act, "topup_cmd", lambda ctx, t, n, ids: ["topup", t, str(n)])
    monkeypatch.setattr(act, "_next_trial", lambda ctx, t: 5)
    monkeypatch.setattr(act.digest, "cand_dir", lambda rd, t: tmp_dir)
    monkeypatch.setattr(act.eval_index, "cap_hash", lambda d: "h")
    monkeypatch.setattr(act.eval_index, "counts", lambda *a, **k: {"x": ("x", 2)})


tmp_dir = Path("/nonexistent")


def test_ao_judge_p_accepts_only_if_fresh_trials_confirm(tmp_path, monkeypatch):
    from types import SimpleNamespace
    act, calls = _ao(), []
    up = [0.3, 0.2, 0.25, 0.3, 0.2, 0.3, 0.25, 0.2]
    _patch(monkeypatch, act, up, [0.0] * 8, up, [0.0] * 8, calls)
    ctx = _fake_ctx(tmp_path, {"promotion_rule": "P", "promotion_n_conf": 4})
    j = act.judge_p(ctx, SimpleNamespace(), "cand", "ref", act.promotion_params(ctx))
    assert j["verdict"] == "accept" and j["gate_mode"] == "promotion_P"
    assert len(calls) == 2 and calls[0][2] == "6"            # 2 existing + n_conf, both tags topped up
    assert json.loads((tmp_path / "promotion_p.json").read_text()) == {"cand": 5}


def test_ao_judge_p_rejects_a_screen_fluke_on_fresh_trials(tmp_path, monkeypatch):
    from types import SimpleNamespace
    act, calls = _ao(), []
    up = [0.3, 0.2, 0.25, 0.3, 0.2, 0.3, 0.25, 0.2]
    flat = [0.0, 0.01, -0.01, 0.0, 0.0, 0.01, 0.0, -0.01]
    _patch(monkeypatch, act, up, [0.0] * 8, flat, [0.0] * 8, calls)
    ctx = _fake_ctx(tmp_path, {"promotion_rule": "P"})
    j = act.judge_p(ctx, SimpleNamespace(), "cand", "ref", act.promotion_params(ctx))
    assert j["verdict"] == "reject" and not (tmp_path / "promotion_p.json").exists()


def test_ao_screen_reject_buys_nothing(tmp_path, monkeypatch):
    from types import SimpleNamespace
    act, calls = _ao(), []
    _patch(monkeypatch, act, [0.0] * 8, [0.0] * 8, [1.0] * 8, [0.0] * 8, calls)
    ctx = _fake_ctx(tmp_path, {"promotion_rule": "P"})
    j = act.judge_p(ctx, SimpleNamespace(), "cand", "ref", act.promotion_params(ctx))
    assert calls == [] and j["verdict"] == "reject"


def test_ao_default_spec_has_no_rule_p(tmp_path):
    act = _ao()
    assert act.promotion_params(_fake_ctx(tmp_path, {})) is None


def test_reference_confirmation_trials_become_the_next_baseline(tmp_path, monkeypatch):
    """After a promotion the champion's recorded fresh index is the min_trial for the next screen."""
    from types import SimpleNamespace
    act, seen = _ao(), []
    (tmp_path / "promotion_p.json").write_text(json.dumps({"ref": 7}))
    orig = lambda run_dir, tag, sp, min_trial=0, **kw: (seen.append((tag, min_trial)) or _SR([0.0] * 8))
    monkeypatch.setattr(act.harness, "split_result_from_rollouts", orig)
    ctx = _fake_ctx(tmp_path, {"promotion_rule": "P"})
    act.judge_p(ctx, SimpleNamespace(), "cand", "ref", act.promotion_params(ctx))
    assert ("ref", 7) in seen
