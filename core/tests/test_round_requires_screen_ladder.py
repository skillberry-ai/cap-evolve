"""issue #420 item 4: full-val evaluation must go through the screen ladder by default.

Run 33492876620 paid a full 100-rollout sweep for every one of 7 candidates, including
``cand_scope`` (clearly harmful) and ``cand_e2_verifytype`` (flat) — exactly the cases
``screen.py`` exists to kill for a quarter of the price. It was never used because using it
was optional. ``round.py`` now refuses a candidate with no ``$R/screens/<tag>__screen*.json``
record unless the driver passes ``--skip-screen-ladder``.

Also covers issue #420 item 9: ``round.py`` records ``measurement_max_parallel`` alongside
``measurement_concurrency``, and warns when either drifts from the previous round.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(SCRIPTS))


def _project(tmp: Path, *, n: int) -> Path:
    project = tmp / "project"
    (project / "adapters").mkdir(parents=True, exist_ok=True)
    (project / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter\n\n\n"
        "class Adapter(SyntheticAdapter):\n"
        f"    def __init__(self):\n        super().__init__(n={n})\n",
        encoding="utf-8")
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        'stop_condition: "reach val mean >= 0.9, or stop after $5 or 30 minutes"\n',
        encoding="utf-8")
    return project


def _run(argv, env=None):
    e = dict(os.environ, CAPEVOLVE_CORE=str(CORE))
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=e)


def _staged_run_dir(tmp_path, *, n=24):
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=n)
    project = _project(tmp_path, n=n)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="chk")
    harness.ensure_splits(adapter, run_dir, seed=0)

    for i, tid in enumerate(run_dir.read_splits().ids("val")):
        from cap_evolve.skillcheck import write_val_rollout
        write_val_rollout(run_dir, tid, tag="cur", reward=float(i % 2), feedback="fb")
    run_dir.set_best("cur")
    run_dir.snapshot("cur", seed_capability_dir(tmp_path / "roundcap", level=12))

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copytree(seed_capability_dir(tmp_path / "_src", level=24), work / "cand_1")
    return run_dir, project, work


def test_round_refuses_an_unscreened_candidate(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1"])
    assert p.returncode != 0, f"round.py ran full val on an unscreened candidate: {p.stdout}"
    assert "screen.py" in p.stdout


def test_skip_screen_ladder_records_the_deliberate_override(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
              "--skip-screen-ladder"])
    assert p.returncode == 0, f"--skip-screen-ladder did not override the guard: {p.stdout}"
    out = json.loads(p.stdout)
    assert [x["tag"] for x in out.get("candidates") or []] == ["cand_1"]


def test_round_proceeds_once_the_candidate_has_a_screen_record(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_1__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1"])
    assert p.returncode == 0, f"round.py refused a screened candidate: {p.stdout}"


def test_round_records_max_parallel_and_warns_on_drift(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_1__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    p1 = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
               "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
               "--max-parallel", "2"])
    assert p1.returncode == 0, p1.stdout
    out1 = json.loads(p1.stdout)
    assert out1["measurement_max_parallel"] == 2
    assert out1["parallel_warning"] is None, "the first round has nothing to drift from"

    # Advance to a fresh iteration and re-run with a different --max-parallel.
    from cap_evolve import RunDir, harness
    harness.record_iteration(run_dir, work / "cand_1", "cand_1", parent_id="cur",
                             accepted=False, reason="test", val=0.5, parent_val=0.5)

    import shutil
    from cap_evolve.skillcheck import seed_capability_dir
    shutil.copytree(seed_capability_dir(tmp_path / "_src2", level=24), work / "cand_2")
    (screens / "cand_2__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    p2 = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
               "--project", str(project), "--candidates", "cand_2", "--n-trials", "1",
               "--max-parallel", "4"])
    assert p2.returncode == 0, p2.stdout
    out2 = json.loads(p2.stdout)
    assert out2["measurement_max_parallel"] == 4
    assert out2["parallel_warning"] is not None, (
        "round 2 silently doubled --max-parallel from round 1's 2 and nothing warned about it")
    assert "2" in out2["parallel_warning"] and "4" in out2["parallel_warning"]
