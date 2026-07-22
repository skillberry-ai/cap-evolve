"""require_green_check Stop hook: agent-mode continuation nudge.

The hook blocks a Stop (exit 2) once per chain when an agent-mode run is not yet
finalized, so the coding agent keeps driving its loop until it seals with
`cap-evolve finalize`. Deterministic runs, finalized runs, and a relenting chain
(`stop_hook_active`) are all unaffected.

We unit-test `decide()` directly. The green-check itself (`_check_failed_reason`)
is monkeypatched to green so these cases isolate the agent-mode branch, which sits
after the green check passes.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "plugins" / "cap-evolve" / "hooks"
sys.path.insert(0, str(HOOKS))

import require_green_check as rgc  # noqa: E402


def _build_run(tmp_path: Path, mode: str, *, finalized: bool) -> Path:
    """Minimal run dir + sibling project with a capevolve.yaml.

    Layout mirrors what find_run_dir/project_dir_for expect:
      tmp/.capevolve/run_x/{splits.json[,state.json]}
      tmp/.capevolve/project/{capevolve.yaml, adapters/adapter.py}
    Returns the run dir. The hook's cwd is set to the run dir in the payload.
    """
    base = tmp_path / ".capevolve"
    run_dir = base / "run_x"
    run_dir.mkdir(parents=True)
    (run_dir / "splits.json").write_text(
        json.dumps({"train": [], "val": [], "test": ["t1"], "test_used": finalized}),
        encoding="utf-8",
    )
    if finalized:
        (run_dir / "state.json").write_text(json.dumps({"done": True}), encoding="utf-8")

    project = base / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text("# stub\n", encoding="utf-8")
    (project / "capevolve.yaml").write_text(
        f"orchestration_mode: {mode}\ncapabilities: [system-prompt]\n", encoding="utf-8"
    )
    return run_dir


@pytest.fixture(autouse=True)
def _green(monkeypatch):
    # Isolate the agent-mode branch: force the green check + regression check to pass.
    monkeypatch.setattr(rgc, "_check_failed_reason", lambda run_dir: None)
    monkeypatch.setattr(rgc, "_gate_regression_pending", lambda run_dir: None)
    monkeypatch.delenv("CAPEVOLVE_RUN_DIR", raising=False)
    monkeypatch.delenv("CAPEVOLVE_NO_GATE_HOOK", raising=False)


def test_agent_mode_not_finalized_blocks_stop(tmp_path):
    run_dir = _build_run(tmp_path, "agent", finalized=False)
    payload = {"cwd": str(run_dir), "hook_event_name": "Stop", "stop_hook_active": False}
    assert rgc.decide(payload) == 2


def test_agent_mode_finalized_allows_stop(tmp_path):
    run_dir = _build_run(tmp_path, "agent", finalized=True)
    payload = {"cwd": str(run_dir), "hook_event_name": "Stop", "stop_hook_active": False}
    assert rgc.decide(payload) == 0


def test_deterministic_mode_green_allows_stop(tmp_path):
    run_dir = _build_run(tmp_path, "deterministic", finalized=False)
    payload = {"cwd": str(run_dir), "hook_event_name": "Stop", "stop_hook_active": False}
    assert rgc.decide(payload) == 0


def test_agent_mode_sealed_without_state_json_allows_stop(tmp_path):
    # A sealed run (splits.json test_used=true) whose state.json is missing/corrupt
    # must still be recognized as finalized — the seal is authoritative, not state.json.
    run_dir = _build_run(tmp_path, "agent", finalized=True)
    (run_dir / "state.json").unlink()  # simulate missing/corrupt state
    payload = {"cwd": str(run_dir), "hook_event_name": "Stop", "stop_hook_active": False}
    assert rgc.decide(payload) == 0


def test_agent_mode_relents_when_stop_hook_active(tmp_path):
    run_dir = _build_run(tmp_path, "agent", finalized=False)
    payload = {"cwd": str(run_dir), "hook_event_name": "Stop", "stop_hook_active": True}
    assert rgc.decide(payload) == 0
