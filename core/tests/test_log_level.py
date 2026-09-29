"""#589: "no debug/verbose logging mode exists anywhere in core/cap_evolve" —
``CAPEVOLVE_LOG_LEVEL`` wires cap_evolve's stdlib ``logging`` calls (e.g. the
per-task/per-trial detail in ``harness.evaluate_candidate``'s ``_persist_trial``)
to a real, opt-in verbosity.

Logging config is a process-wide side effect at ``cap_evolve`` import time (see
``cap_evolve/__init__.py``, matching the existing ``faulthandler.enable()``
precedent there), so this is exercised via a subprocess rather than mutating the
already-imported test process's logging state.
"""
import os
import subprocess
import sys
from pathlib import Path

CORE = str(Path(__file__).resolve().parents[1])

_PROBE = (
    "import logging, cap_evolve, cap_evolve.harness as h; "
    "print(logging.getLogger('cap_evolve.harness').getEffectiveLevel())"
)


def _run(env_extra: dict) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = CORE + os.pathsep + env.get("PYTHONPATH", "")
    env.update(env_extra)
    p = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    return int(p.stdout.strip())


def test_capevolve_log_level_debug_lowers_the_effective_level():
    import logging
    assert _run({"CAPEVOLVE_LOG_LEVEL": "DEBUG"}) == logging.DEBUG


def test_no_env_var_leaves_pythons_default_untouched():
    import logging
    env = dict(os.environ)
    env.pop("CAPEVOLVE_LOG_LEVEL", None)
    level = _run({"CAPEVOLVE_LOG_LEVEL": ""})
    # An empty/unset value must not opt this process into any config: Python's own
    # default effective level for a fresh, unconfigured logger is WARNING.
    assert level == logging.WARNING


def test_harness_debug_logging_surfaces_per_task_detail(tmp_path, capsys):
    """With DEBUG on, evaluating even a tiny candidate logs a per-task/per-trial
    line — the concrete detail #589 asked for ("surfaces per-task/per-trial detail
    when enabled"). Exercised in-process via the stdlib ``logging`` API directly
    (no subprocess needed here since we control the handler, not import-time
    config) to keep this test fast and deterministic.
    """
    import contextlib
    import io
    import logging
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits

    class _Adapter:
        def tasks(self, split):
            from cap_evolve import Task
            return [Task(id="only", input={})]

        def run_target(self, task, ctx, *, seed=0):
            from cap_evolve import Rollout
            return Rollout(task_id=task.id, output="ok")

        def score(self, task, rollout):
            from cap_evolve import Score
            return Score(task_id=task.id, reward=1.0, feedback="ok")

        def apply(self, candidate_dir, edits=None):
            return None

    rd = RunDir.create(tmp_path / ".capevolve", ts="dbg")
    rd.write_splits(Splits(train=[], val=["only"], test=[], seed=0))
    cand = tmp_path / "c"
    cand.mkdir()
    rd.snapshot("dbg", cand)

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    harness.logger.addHandler(handler)
    harness.logger.setLevel(logging.DEBUG)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            harness.evaluate_candidate(_Adapter(), rd.candidate_dir("dbg"), run_dir=rd,
                                       split="val", n_trials=1, tag="dbg", workers=1)
    finally:
        harness.logger.removeHandler(handler)
        harness.logger.setLevel(logging.NOTSET)

    out = buf.getvalue()
    assert "task=only" in out and "trial=0" in out and "reward=1.0" in out
