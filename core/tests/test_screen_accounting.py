"""Screen accounting (screen_accounting.py): composition, inclusion probabilities, unbiased estimate,
equal-size random control, scheduling-signal-only record; plus screen.py end to end (real tiny adapter)."""

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

from cap_evolve import screen_accounting as sa  # noqa: E402

POOL = [f"t{i:02d}" for i in range(12)]


def test_composition_and_inclusion_probabilities():
    s = sa.build_screen(POOL, affected=["t00", "t01"], sentinels=["t02", "t01"], k_random=3, seed=4)
    comp = s["components"]
    assert comp["t00"] == "affected" and comp["t01"] == "affected" and comp["t02"] == "sentinel"
    rand = [t for t, c in comp.items() if c == "random"]
    assert len(rand) == 3 and not set(rand) & {"t00", "t01", "t02"}
    assert s["n_rest"] == 9 and s["k_random"] == 3
    assert all(s["inclusion"][t] == 1.0 for t in ("t00", "t01", "t02"))
    assert all(s["inclusion"][t] == pytest.approx(3 / 9) for t in rand)
    assert s["mode"] == "accounted" and sorted(s["ids"]) == s["ids"]
    assert sa.build_screen(POOL, ["t00", "t01"], ["t02", "t01"], 3, 4) == s            # reproducible


def test_unknown_ids_are_dropped_and_k_random_is_clamped():
    s = sa.build_screen(POOL, affected=["nope", "t00"], sentinels=[], k_random=99, seed=0)
    assert "nope" not in s["components"] and s["k_random"] == 11 and s["inclusion"]["t05"] == 1.0
    z = sa.build_screen(POOL, affected=POOL, sentinels=[], k_random=3, seed=0)
    assert z["n_rest"] == 0 and z["k_random"] == 0 and len(z["ids"]) == 12


def test_horvitz_thompson_estimate_is_unbiased_by_exact_enumeration():
    delta = {t: (i % 4) * 0.1 - 0.05 for i, t in enumerate(POOL)}
    truth = sum(delta.values()) / len(POOL)
    affected, sentinels, k = ["t00", "t05"], ["t03"], 2
    rest = [t for t in POOL if t not in affected + sentinels]
    ests = []
    for combo in itertools.combinations(rest, k):
        comp = {**{t: "affected" for t in affected}, **{t: "sentinel" for t in sentinels}, **{t: "random" for t in combo}}
        scr = {"mode": "accounted", "components": comp, "n_pool": len(POOL), "n_rest": len(rest), "k_random": k}
        ests.append(sa.ht_estimate({t: delta[t] for t in comp}, scr)["estimate"])
    assert sum(ests) / len(ests) == pytest.approx(truth)


def test_control_has_equal_size_ignores_predictions_and_is_reproducible():
    acc = sa.build_screen(POOL, ["t00", "t01"], ["t02"], 3, seed=1)
    ctl = sa.build_control(POOL, size=len(acc["ids"]), seed=1)
    assert ctl["mode"] == "random_subset" and len(ctl["ids"]) == len(acc["ids"])
    assert set(ctl["components"].values()) == {"random"}
    assert all(p == pytest.approx(6 / 12) for p in ctl["inclusion"].values())
    assert sa.build_control(POOL, len(acc["ids"]), 1) == ctl
    est = sa.ht_estimate({t: 0.1 for t in ctl["ids"]}, ctl)
    assert est["estimate"] == pytest.approx(0.1)


def test_record_is_a_scheduling_signal_never_a_result():
    s = sa.build_screen(POOL, ["t00"], [], 2, 0)
    rec = sa.record(s, sa.ht_estimate({t: 0.0 for t in s["ids"]}, s))
    assert rec["role"] == "scheduling_signal" and rec["result"] is False
    assert "accept" not in json.dumps(rec).lower()
    assert rec["inclusion"] == s["inclusion"] and rec["control"] is False


# ---- screen.py end to end -------------------------------------------------------------------------

def _env():
    return dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"), CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


ADAPTER = '''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

NEEDS = {"t0": "MARK", "t1": "MARK"}

class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}") for i in range(10)]
    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id, output=(Path(ctx) / "tools.py").read_text())
    def run_trials(self, tasks, ctx, *, n_trials, base_seed):
        return run_trials_pool(lambda t, s: self.run_target(t, ctx, seed=s), tasks, n_trials=n_trials, base_seed=base_seed)
    def score(self, task, rollout):
        ok = NEEDS.get(task.id, "") in (rollout.output or "")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback="", trial_rewards=[1.0 if ok else 0.0])
'''


def _setup(tmp_path):
    import importlib.util
    from cap_evolve import Budget, RunDir, harness
    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(ADAPTER)
    spec = importlib.util.spec_from_file_location("pa", project / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="sa", budget=Budget(max_iterations=10))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "tools.py").write_text("base\n")
    ids = [f"t{i}" for i in range(10)]
    harness.ensure_splits(mod.Adapter(), run_dir, seed=0, split_ids={"val": ids, "train": [], "test": []})
    harness.baseline(mod.Adapter(), seed, run_dir=run_dir)
    cand = run_dir.root / "work" / "cand_1"
    cand.mkdir(parents=True)
    (cand / "tools.py").write_text("base MARK\n")
    return run_dir, project


def _screen(run_dir, project, *extra):
    p = subprocess.run([sys.executable, str(SCRIPTS / "screen.py"), "--run-dir", str(run_dir.root), "--project", str(project),
                        "--candidate", str(run_dir.root / "work" / "cand_1"), "--tag", "cand_1", "--tier", "1",
                        "--n-trials", "1", *extra], capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_screen_py_default_has_no_accounting(tmp_path):
    run_dir, project = _setup(tmp_path)
    out = _screen(run_dir, project)
    assert "accounting" not in out


def test_screen_py_accounting_records_design_and_keeps_the_kill_only_decision(tmp_path):
    run_dir, project = _setup(tmp_path)
    out = _screen(run_dir, project, "--accounting", "--affected", "t0,t1", "--sentinels", "t9", "--k-random", "2")
    acc = out["accounting"]
    assert acc["role"] == "scheduling_signal" and acc["result"] is False and acc["mode"] == "accounted"
    comp = acc["components"]
    assert comp["t0"] == "affected" and comp["t9"] == "sentinel" and sum(c == "random" for c in comp.values()) == 2
    assert out["subset"]["ids"] == sorted(comp)
    assert out["decision"] in ("kill", "promote") and out["decision"] != "accept"
    saved = json.loads(next((run_dir.root / "screens").glob("*.json")).read_text())
    assert saved["accounting"]["inclusion"] == acc["inclusion"]
    ev = [json.loads(l) for l in run_dir.events_path.read_text().splitlines() if '"screen"' in l][-1]
    assert ev["accounting_role"] == "scheduling_signal"


def test_screen_py_random_control_has_the_same_size_and_ignores_the_prediction(tmp_path):
    run_dir, project = _setup(tmp_path)
    acc = _screen(run_dir, project, "--accounting", "--affected", "t0,t1", "--sentinels", "t9", "--k-random", "2")["accounting"]
    (tmp_path / "c").mkdir()
    run2, project2 = _setup(tmp_path / "c")
    ctl = _screen(run2, project2, "--accounting", "--screen-control", "random_subset",
                  "--affected", "t0,t1", "--sentinels", "t9", "--k-random", "2")["accounting"]
    assert ctl["mode"] == "random_subset" and ctl["control"] is True
    assert len(ctl["components"]) == len(acc["components"])
    assert set(ctl["components"].values()) == {"random"}
