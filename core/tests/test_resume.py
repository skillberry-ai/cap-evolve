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
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"
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


def test_baseline_materializes_guidance_for_every_declared_capability(tmp_path):
    """A run in EITHER orchestration_mode goes through this one baseline phase (see
    cli.py's ``sequence``), so this is where ``guidance/<cap>/SKILL.md`` must land for a
    driving agent to read directly — agent mode has no per-iteration optimizer subprocess
    to piggyback the deterministic path's materialization on."""
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    (project / "capevolve.yaml").write_text(
        "capabilities: [system-prompt]\n", encoding="utf-8")
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    base = tmp_path / ".capevolve"
    common = ["--base", str(base), "--project", str(project),
              "--capability", str(seed), "--run-ts", "g1"]
    env = {**os.environ, "PYTHONPATH": str(CORE)}
    r = subprocess.run([sys.executable, str(BASELINE_RUN), *common],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    run_dir = Path(json.loads(r.stdout)["run_dir"])
    assert (run_dir / "guidance" / "system-prompt" / "SKILL.md").exists()
    assert (run_dir / "guidance" / "diagnose" / "SKILL.md").exists()


# ---- --resume with a --run-ts that does not exist -------------------------

def _baseline_project(tmp_path):
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    seed = tmp_path / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    return project, seed


def test_baseline_resume_unknown_run_ts_fails_without_creating_a_run(tmp_path):
    project, seed = _baseline_project(tmp_path)
    base = tmp_path / ".capevolve"
    env = {**os.environ, "PYTHONPATH": str(CORE)}
    r = subprocess.run([sys.executable, str(BASELINE_RUN), "--base", str(base),
                        "--project", str(project), "--capability", str(seed),
                        "--run-ts", "nosuch", "--resume"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 1
    err = json.loads(r.stderr.strip().splitlines()[-1])
    assert err["step"] == "resume" and "run_nosuch" in err["error"]
    assert not (base / "run_nosuch").exists()


def test_cli_resume_unknown_run_ts_fails_and_names_existing_runs(tmp_path, capsys):
    from cap_evolve import cli
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    project, _seed = _baseline_project(tmp_path)
    spec = project / "capevolve.yaml"
    spec.write_text((REPO / "benchmarks" / "_scaffold" / "project" / "capevolve.yaml")
                    .read_text(encoding="utf-8"), encoding="utf-8")
    base = tmp_path / ".capevolve"
    from cap_evolve import Budget, RunDir
    RunDir.create(base, ts="real1", budget=Budget(max_iterations=1))
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                   "--run-ts", "nosuch", "--resume"])
    assert rc == 1
    out = capsys.readouterr().out
    err = json.loads(out.strip().splitlines()[-1])
    assert err["step"] == "resume"
    assert "run_nosuch" in err["error"] and str(base) in err["error"]
    assert "run_real1" in err["error"]
    assert not (base / "run_nosuch").exists()


# ---- a --run-ts that already exists, without --resume ---------------------

def test_baseline_existing_run_ts_without_resume_fails_plainly(tmp_path):
    project, seed = _baseline_project(tmp_path)
    base = tmp_path / ".capevolve"
    env = {**os.environ, "PYTHONPATH": str(CORE)}
    common = [sys.executable, str(BASELINE_RUN), "--base", str(base),
              "--project", str(project), "--capability", str(seed), "--run-ts", "dup1"]
    r1 = subprocess.run(common, capture_output=True, text=True, env=env)
    assert r1.returncode == 0, r1.stderr
    r2 = subprocess.run(common, capture_output=True, text=True, env=env)
    assert r2.returncode != 0
    assert "Traceback" not in r2.stderr and "FileExistsError" not in r2.stderr
    err = json.loads(r2.stderr.strip().splitlines()[-1])
    assert "run_dup1 already exists" in err["error"] and str(base) in err["error"]
    assert "--resume" in err["error"]
    # --resume on the same run still reopens it.
    r3 = subprocess.run([*common, "--resume"], capture_output=True, text=True, env=env)
    assert r3.returncode == 0, r3.stderr
    assert json.loads(r3.stdout)["resumed"] is True


def test_cli_existing_run_ts_without_resume_fails_plainly(tmp_path, capsys):
    from cap_evolve import cli
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    project, _seed = _baseline_project(tmp_path)
    spec = project / "capevolve.yaml"
    spec.write_text((REPO / "benchmarks" / "_scaffold" / "project" / "capevolve.yaml")
                    .read_text(encoding="utf-8"), encoding="utf-8")
    base = tmp_path / ".capevolve"
    from cap_evolve import Budget, RunDir
    RunDir.create(base, ts="dup2", budget=Budget(max_iterations=1))
    rc = cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                   "--run-ts", "dup2"])
    assert rc != 0
    cap = capsys.readouterr()
    assert "Traceback" not in cap.out + cap.err
    err = json.loads(cap.out.strip().splitlines()[-1])
    assert "run_dup2 already exists" in err["error"] and str(base) in err["error"]
    assert "--resume" in err["error"]


def test_existing_run_error_helper(tmp_path):
    from cap_evolve.rundir import existing_run_error
    assert existing_run_error(tmp_path, None) is None
    assert existing_run_error(tmp_path, "x") is None
    (tmp_path / "run_x").mkdir()
    assert "run_x already exists" in existing_run_error(tmp_path, "x")


# ---- gepa --resume on a corrupt gepa_state.json ---------------------------

_BAD_GEPA_STATES = {"truncated": '{"lineage":', "not_an_object": "[]",
                    "not_utf8": b"\xff\xfe{}"}


@pytest.mark.parametrize("kind", sorted(_BAD_GEPA_STATES))
def test_gepa_resume_corrupt_state_stops_with_clear_error(tmp_path, kind):
    run_dir, _ = _gepa_run(tmp_path, "grbad", max_metric_calls=200, max_iterations=2)
    state = run_dir.root / "gepa_state.json"
    bad = _BAD_GEPA_STATES[kind]
    state.write_bytes(bad if isinstance(bad, bytes) else bad.encode())

    # In-process: a clean SystemExit naming the file and the way out, never a
    # silent seed-only pool (that would drop the saved lineage without a word).
    with pytest.raises(SystemExit) as ei:
        _gepa_run(tmp_path, "grbad", resume=True, max_metric_calls=200, max_iterations=4)
    msg = str(ei.value)
    assert str(state) in msg and "--resume" in msg
    assert "delete" in msg or "restore" in msg

    # As a process (how the gepa skill runs it): exit 1, the message, no traceback.
    code = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from cap_evolve import RunDir, gepa\n"
        "rd = RunDir.open(sys.argv[2])\n"
        "gepa._reconstruct_gepa(rd, gepa.split_result_from_rollouts(rd, 'seed', 'val'))\n")
    proc = subprocess.run([sys.executable, "-c", code, str(CORE), str(run_dir.root)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    assert "gepa_state.json" in proc.stderr
