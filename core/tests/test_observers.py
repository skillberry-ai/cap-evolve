"""Tests for the observer protocol and RunDir integration."""

import json
import sys
from pathlib import Path

import pytest

from cap_evolve import RunDir, make_splits
from cap_evolve.observers import (
    CompositeObserver,
    NullObserver,
    RunObserver,
    observer_from_config,
    observers_from_config,
)


# ---- recording observer for tests -----------------------------------------

class RecordingObserver(RunObserver):
    """Captures all calls for assertion."""

    def __init__(self):
        self.started = []
        self.events = []
        self.ended = []
        self.flushed = 0
        self.closed = 0

    def on_run_start(self, run_id, metadata):
        self.started.append((run_id, metadata))

    def on_event(self, event):
        self.events.append(event)

    def on_run_end(self, summary):
        self.ended.append(summary)

    def flush(self):
        self.flushed += 1

    def close(self):
        self.closed += 1


class FailingObserver(RunObserver):
    """Raises on every hook — observers must not crash the run."""

    def on_run_start(self, run_id, metadata):
        raise RuntimeError("boom-start")

    def on_event(self, event):
        raise RuntimeError("boom-event")

    def on_run_end(self, summary):
        raise RuntimeError("boom-end")

    def flush(self):
        raise RuntimeError("boom-flush")

    def close(self):
        raise RuntimeError("boom-close")


# ---- NullObserver ---------------------------------------------------------

def test_null_observer_is_noop():
    obs = NullObserver()
    obs.on_run_start("r1", {})
    obs.on_event({"kind": "step", "t": 1.0})
    obs.on_run_end({"test_reward": 0.9})
    obs.flush()
    obs.close()


# ---- CompositeObserver ----------------------------------------------------

def test_composite_fans_out():
    a, b = RecordingObserver(), RecordingObserver()
    comp = CompositeObserver([a, b])

    comp.on_run_start("r1", {"budget": 10})
    comp.on_event({"kind": "step", "val": 0.5})
    comp.on_event({"kind": "evaluate", "reward": 0.8})
    comp.on_run_end({"test_reward": 0.9})
    comp.flush()
    comp.close()

    for obs in (a, b):
        assert len(obs.started) == 1
        assert obs.started[0] == ("r1", {"budget": 10})
        assert len(obs.events) == 2
        assert len(obs.ended) == 1
        assert obs.flushed == 1
        assert obs.closed == 1


def test_composite_add():
    comp = CompositeObserver()
    a = RecordingObserver()
    comp.add(a)
    comp.on_event({"kind": "test"})
    assert len(a.events) == 1
    assert comp.children == [a]


def test_composite_isolates_failures():
    good = RecordingObserver()
    bad = FailingObserver()
    comp = CompositeObserver([bad, good])

    # None of these should raise
    comp.on_run_start("r1", {})
    comp.on_event({"kind": "step"})
    comp.on_run_end({})
    comp.flush()
    comp.close()

    # Good observer still got its calls
    assert len(good.started) == 1
    assert len(good.events) == 1
    assert len(good.ended) == 1


# ---- RunDir integration ---------------------------------------------------

def test_rundir_log_event_notifies_observer(tmp_path):
    rd = RunDir.create(tmp_path)
    obs = RecordingObserver()
    rd.add_observer(obs)

    rd.log_event("step", candidate="c1", val=0.75)

    assert len(obs.events) == 1
    ev = obs.events[0]
    assert ev["kind"] == "step"
    assert ev["candidate"] == "c1"
    assert ev["val"] == 0.75
    assert "t" in ev  # timestamp


def test_rundir_multiple_observers(tmp_path):
    rd = RunDir.create(tmp_path)
    a, b = RecordingObserver(), RecordingObserver()
    rd.add_observer(a)
    rd.add_observer(b)

    rd.log_event("evaluate", reward=0.5)

    assert len(a.events) == 1
    assert len(b.events) == 1


def test_rundir_observer_failure_does_not_crash(tmp_path):
    rd = RunDir.create(tmp_path)
    rd.add_observer(FailingObserver())
    rd.add_observer(RecordingObserver())

    # Should not raise
    rd.log_event("step", candidate="c1")
    rd.notify_run_start({"budget": 5})
    rd.notify_run_end({"reward": 0.9})
    rd.flush_observers()
    rd.close_observers()

    # The event was still written to disk
    lines = rd.events_path.read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "step"


def test_rundir_notify_run_start_end(tmp_path):
    rd = RunDir.create(tmp_path)
    obs = RecordingObserver()
    rd.add_observer(obs)

    rd.notify_run_start({"budget": {"max_iterations": 10}})
    rd.log_event("step", val=0.5)
    rd.notify_run_end({"test_reward": 0.9})

    assert obs.started[0][0] == rd.root.name
    assert obs.started[0][1] == {"budget": {"max_iterations": 10}}
    assert len(obs.events) == 1
    assert obs.ended[0] == {"test_reward": 0.9}
    assert obs.flushed == 1  # notify_run_end calls flush


# ---- factory ---------------------------------------------------------------

def test_observer_from_config_null():
    obs = observer_from_config({"backend": "null"})
    assert isinstance(obs, NullObserver)


def test_observer_from_config_custom_dotted_path():
    obs = observer_from_config({"backend": "cap_evolve.observers:NullObserver"})
    assert isinstance(obs, NullObserver)


def test_observer_from_config_unknown_backend():
    with pytest.raises(ValueError, match="Unknown observer backend"):
        observer_from_config({"backend": "nonexistent_backend_xyz"})


def test_observer_from_config_missing_backend_key():
    with pytest.raises(ValueError, match="'backend' key"):
        observer_from_config({})


def test_observers_from_config_empty():
    obs = observers_from_config(None)
    assert isinstance(obs, NullObserver)

    obs = observers_from_config([])
    assert isinstance(obs, NullObserver)


def test_observers_from_config_single():
    obs = observers_from_config([{"backend": "null"}])
    assert isinstance(obs, NullObserver)


def test_observers_from_config_multiple():
    obs = observers_from_config([{"backend": "null"}, {"backend": "null"}])
    assert isinstance(obs, CompositeObserver)
    assert len(obs.children) == 2
