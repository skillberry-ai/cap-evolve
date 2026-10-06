"""#665 workstream 4: the live dashboard launches by DEFAULT for
``orchestration_mode: agent`` runs too, not only deterministic ones — forensic
analysis of a real agent-optimize run found it dark for the whole 3-hour run because
every documented repro command passed ``--dashboard off`` explicitly (fixed in
docs/REPRODUCE_tau2.md + examples/tau2_airline/capevolve.agentopt*.yaml). This locks in
the CODE side: `cap-evolve run` with NO ``--dashboard`` flag and
``orchestration_mode: agent`` must still try to launch (mode resolves to "auto" and
the launch call is unconditional on orchestration_mode — see cli.py's run()).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _agent_mode_toy_project(tmp_path: Path):
    """The zero-API toy_calc project, flipped to orchestration_mode: agent +
    algorithm_skill: agent-optimize (optimizer_skill stays 'mock' — agent mode never
    invokes it; `cap-evolve run` does intake+check+baseline then hands off and
    returns, since no --agent-driver is passed, so this stays fast)."""
    example = REPO / "examples" / "toy_calc"
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    shutil.copy(example / "adapter.py", proj / "adapters" / "adapter.py")
    shutil.copytree(example / "capability", tmp_path / "seed_capability")
    spec_text = (REPO / "templates" / "project" / "capevolve.yaml").read_text(encoding="utf-8")
    spec_text = spec_text.replace("algorithm_skill: hill-climb", "algorithm_skill: agent-optimize")
    spec_text = spec_text.replace("orchestration_mode: deterministic", "orchestration_mode: agent")
    (proj / "capevolve.yaml").write_text(spec_text, encoding="utf-8")
    env = dict(os.environ)
    env.update(PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
               CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"),
               CAPEVOLVE_TOY_DATA=str(example),
               CAPEVOLVE_MOCK_SCRIPT=str(example / "mock_script.json"))
    return proj, env


def _kill_if_dashboard_url(url: str):
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
            h = json.load(r)
    except Exception:  # noqa: BLE001 — best-effort cleanup only
        return
    pid = h.get("pid")
    if isinstance(pid, int) and pid > 1:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def test_agent_mode_run_launches_the_dashboard_by_default(tmp_path):
    import importlib.util
    if importlib.util.find_spec("capevolve_dashboard") is None:
        import pytest
        pytest.skip("capevolve-dashboard not installed (pip install -e dashboard/backend)")

    proj, env = _agent_mode_toy_project(tmp_path)
    with socket.socket() as s:  # a free port, not the shared default 7878
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]

    proc = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run", "--project", str(proj),
         "--run-ts", "t", "--dashboard-port", str(free)],
        capture_output=True, text=True, env=env, timeout=120)
    try:
        assert proc.returncode == 0, proc.stderr[-3000:]
        out = json.loads(proc.stdout)
        assert out.get("mode") == "agent", proc.stdout
        # The status line printed by dashboard_launch.maybe_launch(): a real URL, never
        # "off"/"skipped" — this is the one line that regresses if the launch call is
        # ever moved behind an `if orchestration_mode != "agent":` guard.
        status_lines = [ln for ln in proc.stderr.splitlines() if '"dashboard"' in ln]
        assert status_lines, proc.stderr[-3000:]
        status = json.loads(status_lines[0])
        assert isinstance(status.get("dashboard"), str) and status["dashboard"].startswith("http"), status
        time.sleep(0.3)  # the server is a detached Popen; give it a moment to bind
        _kill_if_dashboard_url(status["dashboard"])
    finally:
        pass
