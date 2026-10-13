"""AO-2 end to end on the REAL backend: ``cap-evolve run`` -> cli.py dispatch -> conductor.py supervise ->
RealBackend (subprocess eval chunks, run-optimizer ``mock`` proposer jobs, act verbs) on the toy_calc adapter.
No model calls: the optimizer is the offline mock and the target is the deterministic toy adapter."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
CONDUCTOR = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "conductor.py"
sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ.update(CAPEVOLVE_CORE=str(CORE), CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"),
                      CAPEVOLVE_TOY_DATA=str(EXAMPLE), CAPEVOLVE_MOCK_SCRIPT=str(EXAMPLE / "mock_script.json"),
                      PYTHONPATH=str(CORE), CAPEVOLVE_FAILURE_CLUSTERING="0")   # the mock proposer writes no hypothesis.json
    yield
    os.environ.clear()
    os.environ.update(old)


def _project(tmp_path: Path, extra: str = "") -> Path:
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(EXAMPLE / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(EXAMPLE / "capability", tmp_path / "seed_capability")
    text = (REPO / "templates" / "project" / "capevolve.yaml").read_text(encoding="utf-8")
    for a, b in (("algorithm_skill: hill-climb", "algorithm_skill: agent-optimize"),
                 ("orchestration_mode: deterministic", "orchestration_mode: agent")):
        assert a in text
        text = text.replace(a, b)
    spec = project / "capevolve.yaml"
    spec.write_text(text + "\nao_engine: conductor\nmax_metric_calls: 400\nao_plateau_n: 3\nao_max_idle_proposals: 3\nao_slots: 2\n"
                    "ao_k_prop: 1\nao_chunk: 4\nao_tick_s: 0.1\npromotion_n_conf: 3\n" + extra, encoding="utf-8")
    return spec


def _run(tmp_path, spec, ts):
    from cap_evolve import cli
    rc = cli.main(["run", "--spec", str(spec), "--project", str(tmp_path / ".capevolve" / "project"),
                   "--dashboard", "off", "--run-ts", ts])
    return rc, tmp_path / ".capevolve" / f"run_{ts}"


def _events(rd: Path):
    return [json.loads(x) for x in (rd / "events.jsonl").read_text().splitlines() if x.strip()]


def test_cli_dispatch_runs_the_real_conductor_to_a_finalized_run(tmp_path):
    spec = _project(tmp_path)
    rc, rd = _run(tmp_path, spec, "e2e")
    assert rc == 0
    state = json.loads((rd / "conductor.json").read_text())
    assert state["finalized"] and state["stopped"], state.get("stopped")
    assert state["stop_reason"] == "proposer_exhausted", "the mock proposer repeats one edit: the run must stop by itself"
    assert (rd / "final.json").exists(), "finalize sealed the run"
    assert state["n_proposals"] >= 1 and any(j["kind"] == "propose" and j["state"] == "done" for j in state["jobs"].values())
    assert any(j["kind"] == "eval" and j["state"] == "done" for j in state["jobs"].values()), "chunked evals ran"
    assert (rd / "graph.jsonl").exists()
    kinds = {e.get("kind") for e in _events(rd)}
    assert "conductor_done" in kinds
    # the conductor, not an agent turn, drove it: no job is left live and no reservation is held
    assert not [j for j in state["jobs"].values() if j["state"] in ("queued", "running")]
    assert not [j for j in state["jobs"].values() if j.get("reserved_rollouts") or j.get("reserved_tokens")]


def test_a_second_invocation_resumes_and_finalize_stays_idempotent(tmp_path):
    spec = _project(tmp_path)
    rc, rd = _run(tmp_path, spec, "again")
    assert rc == 0
    first = (rd / "final.json").read_text()
    n_done = sum(1 for e in _events(rd) if e.get("kind") == "conductor_done")
    proc = subprocess.run([sys.executable, str(CONDUCTOR), "run", "--run-dir", str(rd),
                           "--project", str(tmp_path / ".capevolve" / "project")], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (rd / "final.json").read_text() == first, "no second test look"
    assert sum(1 for e in _events(rd) if e.get("kind") == "conductor_done") >= n_done


def test_multi_objective_spec_is_refused_by_the_real_entry_point(tmp_path):
    # reward + cost is supported (test_ao2_cost_objective.py); any other gating objective is refused
    spec = _project(tmp_path, "objectives:\n  - {name: reward, direction: max, role: gate}\n"
                              "  - {name: latency, direction: min, role: pareto}\n")
    rc, rd = _run(tmp_path, spec, "multi")
    assert rc == 2
    assert not (rd / "final.json").exists()


def test_supervise_relaunches_a_sigkilled_conductor_and_the_run_still_finishes(tmp_path):
    """The real supervisor: the first conductor is SIGKILLed mid-run, the supervisor relaunches it, the
    run resumes from conductor.json + the ledger and ends with exit 0 and a sealed final.json."""
    spec = _project(tmp_path)
    from cap_evolve import cli
    # setup + baseline only: run through the cli once with the conductor disabled, then drive supervise by hand
    off = spec.read_text().replace("ao_engine: conductor", "ao_engine: off")
    spec.write_text(off)
    rc, rd = _run(tmp_path, spec, "sup")
    assert rc == 0 and not (rd / "conductor.json").exists()
    project = tmp_path / ".capevolve" / "project"
    argv = [sys.executable, str(CONDUCTOR), "supervise", "--run-dir", str(rd), "--project", str(project),
            "--sleep", "0.2", "--max-restarts", "10"]
    sup = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    killed = False
    deadline = time.time() + 240
    try:
        while sup.poll() is None and time.time() < deadline:
            pid = None
            lock = rd / "locks" / "conductor.lock"
            if not killed and lock.exists() and "pid=" in lock.read_text():
                pid = int(lock.read_text().split("pid=")[1].split()[0])
                st = rd / "conductor.json"
                if st.exists() and json.loads(st.read_text()).get("jobs"):
                    os.kill(pid, signal.SIGKILL)         # the conductor dies with work in flight
                    killed = True
            time.sleep(0.05)
        out = sup.communicate(timeout=240)[0] if sup.poll() is None else sup.stdout.read()
    finally:
        if sup.poll() is None:
            os.killpg(sup.pid, signal.SIGKILL)
    assert killed, "the test never caught a conductor with jobs in flight"
    assert sup.returncode == 0, out
    assert (rd / "final.json").exists()
    state = json.loads((rd / "conductor.json").read_text())
    assert state["finalized"]
    assert not [j for j in state["jobs"].values() if j["state"] in ("queued", "running")]
