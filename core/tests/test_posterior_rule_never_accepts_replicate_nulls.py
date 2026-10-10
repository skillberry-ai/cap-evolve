"""The paired posterior rule + allocator: no false accepts on identical-bytes replicates (reduced
replay of research/design/sim_eval.py on committed fixtures), prunes losers, accepts a big effect."""

import json
import random
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import Budget, RunDir, eval_index, harness, posterior, sched  # noqa: E402
from cap_evolve.posterior import Pair, k_vector  # noqa: E402

FIX = json.loads((REPO / "core/tests/fixtures/posterior_replicates.json").read_text())
T = 30


def _null_split(cap, rng):
    """Disjoint replicate evals of one capability: half the batches are 'candidate', half 'parent'."""
    bs = FIX[cap]
    perm = rng.sample(range(len(bs)), len(bs))
    half = max(1, len(bs) // 2)

    def pool(idx):
        lst = [[] for _ in range(T)]
        for i in idx:
            for t in range(T):
                v = list(bs[i][str(t)]); rng.shuffle(v); lst[t] += v
        return lst
    cl, pl = pool(perm[:half]), pool(perm[half:])
    sp = [float(sum(pl[t][:3])) for t in range(T)]          # parent's gating eval = ledger start
    pl = [pl[t][3:] for t in range(T)]
    pos = [[0] * T, [0] * T]
    src = [cl, pl]

    def draw(arm, t):
        r = src[arm][t][pos[arm][t]]; pos[arm][t] += 1
        return r
    caps = ([len(x) for x in cl], [len(x) for x in pl])
    return draw, caps, sp


def test_no_false_accept_on_replicate_nulls():
    rng = random.Random(1)
    for cap in ("cand_1", "cand_4"):
        for _ in range(6):
            draw, (cc, cp), sp = _null_split(cap, rng)
            P = Pair(k_vector([(s + .5) / 4 for s in sp]), sp, [3.0] * T)
            dec, used, _ = sched.run(P, draw, cc, cp, rng, m=150)
            assert dec != "accept", (cap, used)


def test_clear_loser_is_pruned_within_forty_rollouts_plus_one_round():
    rng = random.Random(0)
    p_par = [.5] * T
    P = Pair(k_vector(p_par), [1.5] * T, [3.0] * T)
    dec, used, _ = sched.run(P, lambda arm, t: float(rng.random() < (.1 if arm == 0 else .5)),
                             [10**6] * T, [10**6] * T, rng, m=150)
    assert dec == "prune" and used <= 60


def test_large_coherent_effect_is_accepted():
    rng = random.Random(0)
    q = [.2] * T
    P = Pair(k_vector(q), [.6] * T, [3.0] * T)
    dec, _, v = sched.run(P, lambda arm, t: float(rng.random() < (.8 if arm == 0 else .2)),
                          [10**6] * T, [10**6] * T, rng, cap_new=450, m=150)
    assert dec == "accept" and v["p_beat"] >= posterior.P_ACC


def test_global_slot_cap_and_stable_tasks_get_only_the_canary_floor():
    rng = random.Random(0)
    p = [1.0] * 10 + [.5] * 20
    P = Pair(k_vector(p), [3 * x for x in p], [3.0] * T)
    seen = []
    slots = [45]
    sched.run(P, lambda arm, t: seen.append(t) or 0.5, [10**6] * T, [10**6] * T, rng, slots=slots, m=50)
    assert len(seen) <= 45 and slots[0] >= 0
    assert sum(t < 10 for t in seen) == 10 * posterior.CANARY_MIN  # reserved floor, then information-driven


def _ledger_run(tmp_path):
    class A:
        def tasks(self, split):
            from cap_evolve.types import Task
            return [Task(id="a"), Task(id="b")]

        def run_target(self, task, ctx, *, seed=0):
            from cap_evolve.types import Rollout
            return Rollout(task_id=task.id)

        def score(self, task, rollout):
            from cap_evolve.types import Score
            return Score(task_id=task.id, reward=1.0 if task.id == "a" else 0.0)
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(A(), rd, seed=0, split_ids={"train": [], "val": ["a", "b"], "test": []})
    for name, txt in (("par", "x"), ("cand", "y")):
        d = tmp_path / name; d.mkdir(); (d / "p.md").write_text(txt)
        harness.evaluate_candidate(A(), d, run_dir=rd, split="val", n_trials=3, tag=name)
        shutil.copytree(d, rd.candidate_dir(name))  # real runs keep candidates under work/<tag>
    return rd


def test_from_ledger_pools_hashes(tmp_path):
    rd = _ledger_run(tmp_path)
    P = posterior.from_ledger(rd, eval_index.cap_hash(tmp_path / "cand"),
                              eval_index.cap_hash(tmp_path / "par"), ["a", "b"])
    assert P.np_ == [3.0, 3.0] and P.sp == [3.0, 0.0] and P.nc == [3.0, 3.0]
    assert P.verdict(random.Random(0), 6, m=50)["decision"] is None


def test_active_eval_ablation_default_off_and_env_overrides(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_ACTIVE_EVAL", raising=False)
    assert posterior.enabled({}) is False
    assert posterior.enabled({"optimizer": {"ablation": {"active_eval": True}}}) is True
    monkeypatch.setenv("CAPEVOLVE_ACTIVE_EVAL", "0")
    assert posterior.enabled({"optimizer": {"ablation": {"active_eval": True}}}) is False
    monkeypatch.setenv("CAPEVOLVE_ACTIVE_EVAL", "1")
    assert posterior.enabled({}) is True


def test_posterior_check_cli_prints_candidates(tmp_path, capsys):
    import importlib.util
    scripts = REPO / "skills/algorithms/agent-optimize/scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("posterior_check", scripts / "posterior_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rd = _ledger_run(tmp_path)
    assert mod.main(["--run-dir", str(rd.root), "--parent", "par"]) == 0
    assert "cand" in capsys.readouterr().out


def test_unsampled_frozen_val_tasks_widen_the_pair(tmp_path):
    rd = _ledger_run(tmp_path)
    sp = json.loads(rd.splits_path.read_text())
    sp["val"] = sp["val"] + ["never_sampled"]
    rd.splits_path.write_text(json.dumps(sp))
    P = posterior.from_ledger(rd, eval_index.cap_hash(tmp_path / "cand"), eval_index.cap_hash(tmp_path / "par"))
    assert P.T == 3 and P.nc[-1] == 0 and P.np_[-1] == 0


def test_bad_inputs_error_clearly_and_advisory_path_never_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        Pair([], [], [])
    with pytest.raises(ValueError):
        Pair([3.0], [2.0], [1.0])  # reward sum above trials, i.e. reward > 1
    rd = _ledger_run(tmp_path)
    assert "error" in posterior.safe_summarize(rd, "cand", "par", split=None)


def test_canary_fires_on_stable_parent_vs_zero_of_three():
    P = Pair([6.0] + [3.0], [9.0, 1.0], [9.0, 3.0], [0.0, 1.0], [3.0, 3.0])
    v = P.verdict(random.Random(0), 6, m=200)
    assert v["canary_tasks"] == [0] and v["decision"] == "prune"


def _collapse_run(rng, m, cap_new=270):
    """10 parent-stable tasks (.95) collapse to .05 while 20 flaky ones rise .3 -> .7 (true D = -0.033)."""
    p = [.95] * 10 + [.3] * 20
    q = [.05] * 10 + [.7] * 20
    sp = [float(sum(rng.random() < p[t] for _ in range(3))) for t in range(T)]
    P = Pair(k_vector([(s + .5) / 4 for s in sp]), sp, [3.0] * T)
    dec, _, _ = sched.run(P, lambda a, t: float(rng.random() < (q if a == 0 else p)[t]),
                          [10**6] * T, [10**6] * T, rng, cap_new=cap_new, m=m)
    return dec


def test_collapse_on_stable_tasks_is_not_accepted():
    rng = random.Random(5)
    acc = sum(_collapse_run(rng, 100) == "accept" for _ in range(30))
    assert acc <= 1  # <= 5% of 30 (review repro was 15/30)


def test_cumulative_looks_false_accept_rate_at_small_and_production_m():
    rates = [sum(x for b in FIX["seed"] + FIX["cand_1"] for x in b[str(t)]) /
             sum(len(b[str(t)]) for b in FIX["seed"] + FIX["cand_1"]) for t in range(T)]
    for m, n in ((100, 60), (400, 12)):
        rng = random.Random(m)
        fa = 0
        for _ in range(n):  # identical arms; sched.run applies the rule at every 20-rollout look
            sp = [float(sum(rng.random() < rates[t] for _ in range(3))) for t in range(T)]
            P = Pair(k_vector([(s + .5) / 4 for s in sp]), sp, [3.0] * T)
            dec, _, _ = sched.run(P, lambda a, t: float(rng.random() < rates[t]),
                                  [10**6] * T, [10**6] * T, rng, m=m)
            fa += dec == "accept"
        assert fa / n <= 0.05, (m, fa)


def test_halve_keeps_the_better_half_and_stages_advance():
    assert sched.halve({"a": .9, "b": .5, "c": .3, "d": .05}, 40) == ["a"]
    assert sched.next_budget(40) == 100 and sched.next_budget(450) is None
