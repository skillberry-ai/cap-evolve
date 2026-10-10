"""#713 framework correctness regressions: pooled --current in grow.py, screen savings priced
at the FULL-val trial count, the opt-in SE guard on kills, champion best_val, commit --val
verified against rollouts, and the per-tag round lock. Offline, zero API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(Path(__file__).parent))

from test_agent_optimize_provisional import (  # noqa: E402
    _SCRIPTED_ADAPTER, _commit, _run_dir)


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    yield
    os.environ.clear()
    os.environ.update(old)


def _setup(tmp_path, ts):
    from cap_evolve import harness
    from cap_evolve.check import load_adapter
    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(_SCRIPTED_ADAPTER, encoding="utf-8")
    run_dir = _run_dir(tmp_path, ts)
    seed = tmp_path / "seed"
    seed.mkdir()
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")
    adapter = load_adapter(project)
    run_dir.write_splits(harness.Splits(train=[], val=["t1", "t2", "t3", "t4"], test=[], seed=0))
    cand = tmp_path / "cand_1"
    cand.mkdir()
    run_dir.snapshot("cand_1", cand)
    return project, run_dir, adapter, seed, cand


def _script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True,
                          text=True, env=dict(os.environ, PYTHONPATH=str(CORE)),
                          cwd=str(SCRIPTS))


def test_grow_pools_comma_separated_current_and_rejects_an_empty_reference(tmp_path):
    from cap_evolve import harness
    project, run_dir, adapter, seed, cand = _setup(tmp_path, "g")
    for tag in ("ctl_a", "ctl_b"):
        harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val", n_trials=1, tag=tag)
    harness.evaluate_candidate(adapter, cand, run_dir=run_dir, split="val", n_trials=1, tag="cand_1")
    base = ["--run-dir", str(run_dir.root), "--project", str(project), "--candidate", "cand_1",
            "--add-trials", "1", "--growth-round", "1"]

    ok = _script("grow.py", *base, "--current", "ctl_a,ctl_b")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    cur = json.loads(ok.stdout)["current"]
    assert cur["tags"] == ["ctl_a", "ctl_b"]
    assert cur["reward"] == pytest.approx(0.75)  # the real pooled reference, not a phantom 0.0

    bad = _script("grow.py", *base, "--current", "ctl_a,nope")  # pooled with a ghost: fine
    assert bad.returncode == 0
    none = _script("grow.py", *base[:-2], "--growth-round", "2", "--current", "nope1,nope2")
    assert none.returncode == 2 and "no rollouts" in none.stdout


def test_screen_savings_use_the_frozen_full_val_trial_count(tmp_path):
    from cap_evolve import harness
    project, run_dir, adapter, seed, cand = _setup(tmp_path, "s")
    harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val", n_trials=3, tag="seed")
    harness.freeze_screening_economics(run_dir, 3)
    out = _script("screen.py", "--run-dir", str(run_dir.root), "--project", str(project),
                  "--candidate", str(cand), "--k", "2")
    assert out.returncode == 0, out.stdout + out.stderr
    assert json.loads(out.stdout)["savings"]["full_val_rollouts"] == 4 * 3
    over = _script("screen.py", "--run-dir", str(run_dir.root), "--project", str(project),
                   "--candidate", str(cand), "--k", "2", "--tag", "c2", "--full-trials", "5")
    assert json.loads(over.stdout)["savings"]["full_val_rollouts"] == 4 * 5


def test_kill_requires_se_support_only_when_kill_z_is_set():
    from cap_evolve.subsample import screen_decision
    # cand_9: mean -0.1667, SE 0.1667 (5 of 8 informative: 1 sigma from zero)
    deltas = [-1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    legacy = screen_decision(deltas)
    assert legacy["mean_delta"] == pytest.approx(-0.25) and legacy["decision"] == "kill"
    assert screen_decision(deltas, kill_z=1.0)["decision"] == "promote"
    # a clearly gross failure still dies under the guard
    gross = [-1.0] * 6
    assert screen_decision(gross, kill_z=1.0)["decision"] == "kill"
    # too few informative tasks: never kill under the guard
    assert screen_decision([-1.0, -1.0], kill_z=1.0)["decision"] == "promote"


def test_set_best_with_val_sets_the_champions_own_best_val(tmp_path):
    run_dir = _run_dir(tmp_path, "b")
    run_dir.update_spent(best_val=0.644)
    run_dir.set_best("cand_7", val=0.567)
    assert run_dir.best_id == "cand_7" and run_dir.spent.best_val == pytest.approx(0.567)


def test_commit_refuses_a_val_that_disagrees_with_the_rollouts(tmp_path):
    from cap_evolve import harness
    project, run_dir, adapter, seed, cand = _setup(tmp_path, "c")
    harness.evaluate_candidate(adapter, cand, run_dir=run_dir, split="val", n_trials=1, tag="cand_1")
    real = harness.split_result_from_rollouts(run_dir, "cand_1", "val").reward
    bad = _commit(run_dir, "cand_1", cand, "reject", val=round(real + 0.2, 4))
    assert bad.returncode == 2 and "does not match" in bad.stdout
    good = _commit(run_dir, "cand_1", cand, "reject", val=round(real, 4))
    assert good.returncode == 0, good.stdout + good.stderr


def test_a_second_launch_on_the_same_round_tag_fails_fast(tmp_path):
    run_dir = _run_dir(tmp_path, "l")
    code = ("import sys; from pathlib import Path; from cap_evolve import RunDir; "
            "r = RunDir.open(Path(sys.argv[1])); r.run_lock('round_cand_1'); print('held', flush=True); "
            "sys.stdin.readline()")
    holder = subprocess.Popen([sys.executable, "-c", code, str(run_dir.root)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                              env=dict(os.environ, PYTHONPATH=str(CORE)))
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(RuntimeError, match="already running"):
            run_dir.run_lock("round_cand_1")
        run_dir.run_lock("round_cand_2")  # a different tag is unaffected
    finally:
        holder.stdin.write("\n")
        holder.stdin.flush()
        holder.wait(timeout=10)
