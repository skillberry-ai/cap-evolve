"""cap-evolve telemetry -- MLflow and OpenTelemetry observer backends.

Usage (from a cap-evolve skill script or programmatically)::

    from capevolve_telemetry import load_observers
    observers = load_observers(config, run_dir_root="/path/to/run_dir")
    for obs in observers:
        run_dir.add_observer(obs)

Resuming observers in a subsequent sub-process::

    from capevolve_telemetry import load_observers_from_state
    states = run_dir.load_observer_state()
    for obs in load_observers_from_state(states):
        run_dir.add_observer(obs)
"""

from .config import load_observers, load_observers_from_state

__all__ = ["load_observers", "load_observers_from_state"]
