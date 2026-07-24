"""Resume tests — offline, deterministic, zero API.

Covers the pieces that make ``cap-evolve run --resume`` correct:
  * ``RunDir.create(exist_ok=True)`` reopens a run WITHOUT resetting state.json
    (best_id/budget/spent preserved), and still initializes a torn/empty dir.
  * ``RunDir.update_budget`` extends only the fields passed (to keep climbing past
    the original cap on resume), leaving spend untouched.
  * gepa persists ``gepa_state.json`` and, on ``resume``, reconstructs its
    pool/lineage/counters from the run dir so the Pareto search continues and new
    candidate ids never collide with the ones already on disk.
  * baseline's ``--resume`` fast-path reopens an existing run and skips the eval.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"
BASELINE_RUN = REPO / "skills" / "phases" / "baseline" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(EXAMPLE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    toy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toy)
    return toy.Adapter()


def _mock_optimizer():
    from cap_evolve import harness
    return harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"])


# ---- RunDir.create(exist_ok) + update_budget ------------------------------

def test_create_exist_ok_preserves_state(tmp_path):
    from cap_evolve import Budget, RunDir
    base = tmp_path / ".capevolve"
    rd = RunDir.create(base, ts="r1", budget=Budget(max_iterations=5))
    rd.set_best("cand_0003")
    rd.update_spent(iterations=3, usd=1.25, accepted=True)

    # Reopen with exist_ok — must NOT reset best/budget/spent.
    rd2 = RunDir.create(base, ts="r1", budget=Budget(max_iterations=99), exist_ok=True)
    assert rd2.root == rd.root
    assert rd2.best_id == "cand_0003"
    assert rd2.spent.iterations == 3
    assert rd2.spent.usd == pytest.approx(1.25)
    assert rd2.budget.max_iterations == 5  # original budget kept, not the new 99


def test_create_strict_default_raises_on_collision(tmp_path):
    from cap_evolve import RunDir
    base = tmp_path / ".capevolve"
    RunDir.create(base, ts="r2")
    with pytest.raises(FileExistsError):
        RunDir.create(base, ts="r2")  # exist_ok defaults False


def test_create_exist_ok_initializes_torn_dir(tmp_path):
    from cap_evolve import RunDir
    base = tmp_path / ".capevolve"
    (base / "run_r3").mkdir(parents=True)  # dir exists but no state.json (torn create)
    rd = RunDir.create(base, ts="r3", exist_ok=True)
    assert rd.state_path.exists()
    assert rd.best_id is None


def test_update_budget_extends_only_passed(tmp_path):
    from cap_evolve import Budget, RunDir
    base = tmp_path / ".capevolve"
    rd = RunDir.create(base, ts="r4", budget=Budget(max_iterations=5, max_usd=2.0))
    rd.update_spent(iterations=2)
    rd.update_budget(max_iterations=20, bogus_key=123)  # unknown key ignored
    assert rd.budget.max_iterations == 20
    assert rd.budget.max_usd == pytest.approx(2.0)  # untouched
    assert rd.spent.iterations == 2                 # spend untouched


# ---- gepa resume: persist + reconstruct -----------------------------------

def _gepa_run(tmp_path, ts, *, resume=False, **kw):
    from cap_evolve import Budget, RunDir, gepa, harness
    adapter = _toy_adapter()
    run_dir = RunDir.create(tmp_path / ".capevolve", ts=ts,
                            budget=Budget(max_iterations=kw.pop("max_iterations", 6)),
                            exist_ok=resume)
    if not resume:
        seed = tmp_path / f"seed_{ts}"
        shutil.copytree(EXAMPLE / "capability", seed)
        harness.ensure_splits(adapter, run_dir, seed=0)
        base = harness.baseline(adapter, seed, run_dir=run_dir)
    else:
        base = harness.split_result_from_rollouts(run_dir, "seed", "val")
    res = gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=_mock_optimizer(),
                         seed_val=base, minibatch_size=3, max_merges=0, seed=0,
                         gate_kwargs={"mode": "significant", "k_se": 1.0},
                         resume=resume, **kw)
    return run_dir, res


def test_gepa_persists_state_and_reconstructs(tmp_path):
    from cap_evolve import gepa
    run_dir, res = _gepa_run(tmp_path, "gr1", max_metric_calls=400, max_iterations=6)
    assert res["accepts"] >= 1 and res["best_val"] == 1.0

    # gepa_state.json checkpoint was written and matches the run.
    state = json.loads((run_dir.root / "gepa_state.json").read_text())
    assert state["steps"] == res["iterations"]
    accepted_ids = [c for c in state["lineage"] if c != "seed"]
    assert accepted_ids  # at least one accepted candidate recorded

    # Reconstruction rebuilds the pool (seed + accepted) with faithful lineage.
    pool, lineage, accepts, merges, cursor, offset = gepa._reconstruct_gepa(
        run_dir, gepa.split_result_from_rollouts(run_dir, "seed", "val"))
    assert {c["id"] for c in pool} >= {"seed", *accepted_ids}
    assert lineage["seed"] is None
    assert offset == res["iterations"] and accepts == res["accepts"]


def test_gepa_resume_continues_without_collision(tmp_path):
    run_dir, res1 = _gepa_run(tmp_path, "gr2", max_metric_calls=200, max_iterations=3)
    pool1 = res1["pool_size"]
    ids_before = {p.name for p in run_dir.candidates.iterdir()}

    # Resume the SAME run dir: frontier retained, best kept, ids continue past prior.
    run_dir2, res2 = _gepa_run(tmp_path, "gr2", resume=True, max_metric_calls=400, max_iterations=6)
    assert run_dir2.root == run_dir.root
    assert res2["pool_size"] >= pool1           # accepted candidates were reloaded
    assert res2["best_val"] == 1.0
    assert res2["iterations"] >= res1["iterations"]  # total steps span both sessions
    new_ids = {p.name for p in run_dir2.candidates.iterdir()} - ids_before
    # any freshly-created gepa candidate must not reuse an id that already existed
    assert not (new_ids & ids_before)
    assert run_dir2.read_splits().test_used is False


# ---- baseline --resume fast-path ------------------------------------------

def test_baseline_resume_skips_eval(tmp_path):
    # Build a real project layout (adapters/adapter.py + seed capability), as run.sh does.
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    base = tmp_path / ".capevolve"
    common = ["--base", str(base), "--project", str(project),
              "--capability", str(seed), "--run-ts", "b1"]
    env = {**os.environ, "PYTHONPATH": str(CORE)}
    r1 = subprocess.run([sys.executable, str(BASELINE_RUN), *common],
                        capture_output=True, text=True, env=env)
    assert r1.returncode == 0, r1.stderr
    first = json.loads(r1.stdout)
    assert not first.get("resumed")

    # Second invocation with --resume must reopen and skip the eval.
    r2 = subprocess.run([sys.executable, str(BASELINE_RUN), *common, "--resume"],
                        capture_output=True, text=True, env=env)
    assert r2.returncode == 0, r2.stderr
    second = json.loads(r2.stdout)
    assert second["resumed"] is True
    assert second["run_dir"] == first["run_dir"]
    assert second["baseline_val"] == first["baseline_val"]
