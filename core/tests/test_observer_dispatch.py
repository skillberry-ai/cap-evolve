"""Test RunDir observer dispatch -- core only, no capevolve_telemetry."""

from __future__ import annotations

import json
from pathlib import Path

from cap_evolve import Budget, RunDir, RunObserver


class FakeObserver:
    """Satisfies RunObserver protocol structurally."""

    def __init__(self):
        self.events: list[tuple[str, dict]] = []
        self.closed = False

    def on_event(self, kind: str, event: dict) -> None:
        self.events.append((kind, dict(event)))

    def state(self) -> dict:
        return {"backend": "fake", "n_events": len(self.events)}

    def close(self) -> None:
        self.closed = True


class CrashingObserver:
    def on_event(self, kind, event):
        raise RuntimeError("boom")

    def state(self):
        return {}

    def close(self):
        pass


def test_fake_observer_satisfies_protocol():
    assert isinstance(FakeObserver(), RunObserver)


def test_observer_receives_events(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    obs = FakeObserver()
    rd.add_observer(obs)
    rd.log_event("test_event", value=42)

    assert len(obs.events) == 1
    kind, ev = obs.events[0]
    assert kind == "test_event"
    assert ev["value"] == 42
    assert "t" in ev


def test_crashing_observer_does_not_break_log_event(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    rd.add_observer(CrashingObserver())
    rd.log_event("test_event", value=1)

    lines = rd.events_path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "test_event"


def test_crashing_observer_does_not_block_healthy_observer(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    rd.add_observer(CrashingObserver())
    healthy = FakeObserver()
    rd.add_observer(healthy)
    rd.log_event("test_event", value=1)

    assert len(healthy.events) == 1


def test_multiple_observers(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    obs1 = FakeObserver()
    obs2 = FakeObserver()
    rd.add_observer(obs1)
    rd.add_observer(obs2)
    rd.log_event("test", val=1)

    assert len(obs1.events) == 1
    assert len(obs2.events) == 1


def test_no_observers_is_noop(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    rd.log_event("test", val=1)
    rd.save_observer_state()
    rd.close_observers()


def test_observer_state_persistence(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    obs = FakeObserver()
    rd.add_observer(obs)
    rd.log_event("a", x=1)
    rd.save_observer_state()

    states = rd.load_observer_state()
    assert len(states) == 1
    assert states[0]["backend"] == "fake"
    assert states[0]["n_events"] == 1


def test_load_observer_state_missing_file(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    assert rd.load_observer_state() == []


def test_close_observers(tmp_path: Path):
    rd = RunDir.create(tmp_path, budget=Budget(max_iterations=1))
    obs = FakeObserver()
    rd.add_observer(obs)
    rd.log_event("a", x=1)
    rd.close_observers()

    assert obs.closed
    states = rd.load_observer_state()
    assert len(states) == 1
