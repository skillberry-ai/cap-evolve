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


def test_global_slot_cap_and_stable_tasks_get_nothing():
    rng = random.Random(0)
    p = [1.0] * 10 + [.5] * 20
    P = Pair(k_vector(p), [3 * x for x in p], [3.0] * T)
    seen = []
    slots = [25]
    sched.run(P, lambda arm, t: seen.append(t) or 0.5, [10**6] * T, [10**6] * T, rng, slots=slots, m=50)
    assert len(seen) <= 25 and slots[0] >= 0
    assert sum(t < 10 for t in seen) <= len(seen) // 4  # stable-pass tasks carry little information


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
    assert posterior.enabled({"ablation": {"active_eval": True}}) is True
    monkeypatch.setenv("CAPEVOLVE_ACTIVE_EVAL", "0")
    assert posterior.enabled({"ablation": {"active_eval": True}}) is False
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
