"""The stdout JSON contract must survive a *scoring* phase that prints.

``run_trials_pool`` already shields the caller's stdout during the RUN phase
(see test_trials.py) because adapters' runners print progress. Scoring was left
unguarded, and it prints too: SpreadsheetBench's vendored comparator does
``print("Cell values in the specified range are identical.")`` on every PASSING
comparison, and its LibreOffice recalculation helper prints on every failure
path. Those land on the phase subprocess's real stdout, so
``cap-evolve run``'s ``json.loads(proc.stdout)`` sees prose at char 0 and the
whole run dies right after a successful (expensive) baseline.

Two independent layers are asserted here:
  1. the harness never lets an adapter's ``score``/``score_batch`` output reach
     the caller's stdout, and
  2. the CLI still finds its JSON payload even when a subprocess does print.
"""

import contextlib
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

NOISE = "Cell values in the specified range are identical."


class _NoisyScoreAdapter:
    """Scores fine but prints to stdout while doing it (the vendored-comparator case)."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id="t0"), Task(id="t1")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        return Rollout(task_id=task.id, output="ok")

    def score(self, task, rollout):
        from cap_evolve import Score
        print(NOISE)
        return Score(task_id=task.id, reward=1.0, feedback="ok")

    def apply(self, candidate_dir, edits=None):
        return None


class _NoisyScoreBatchAdapter(_NoisyScoreAdapter):
    """Same leak, via the batch-scoring hook (swebench-style adapters)."""

    def score_batch(self, tasks, rollouts):
        from cap_evolve import Score
        print(NOISE)
        return {t.id: Score(task_id=t.id, reward=1.0, feedback="batched") for t in tasks}


def _evaluate(adapter, tmp_path, tag):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / ".capevolve", ts=tag)
    rd.write_splits(Splits(train=[], val=["t0", "t1"], test=[], seed=0))
    cand = tmp_path / "c"
    cand.mkdir()
    rd.snapshot(tag, cand)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = harness.evaluate_candidate(adapter, rd.candidate_dir(tag), run_dir=rd,
                                         split="val", n_trials=2, tag=tag)
    return res, buf.getvalue()


def test_score_output_does_not_leak_to_caller_stdout(tmp_path):
    res, leaked = _evaluate(_NoisyScoreAdapter(), tmp_path, "noisy")
    assert leaked == "", f"adapter.score() leaked to the caller's stdout: {leaked!r}"
    assert res.reward == 1.0  # and the scores still landed


def test_score_batch_output_does_not_leak_to_caller_stdout(tmp_path):
    res, leaked = _evaluate(_NoisyScoreBatchAdapter(), tmp_path, "noisybatch")
    assert leaked == "", f"adapter.score_batch() leaked to the caller's stdout: {leaked!r}"
    assert res.reward == 1.0


# ---- layer 2: the CLI tolerates a printing subprocess ---------------------

def test_json_payload_skips_non_json_prefix():
    """A phase subprocess that printed prose before its JSON is still parseable."""
    from cap_evolve.cli import _json_payload
    payload = '{\n  "run_dir": ".capevolve/run_x",\n  "splits": {"val": 2}\n}'
    assert _json_payload(f"{NOISE}\n{NOISE}\n{payload}\n")["run_dir"] == ".capevolve/run_x"


def test_json_payload_reads_clean_stdout_unchanged():
    from cap_evolve.cli import _json_payload
    assert _json_payload('{"run_dir": "x"}')["run_dir"] == "x"


def test_json_payload_prefers_the_last_json_object():
    """Phases print their own payload last; earlier JSON-ish noise must not win."""
    from cap_evolve.cli import _json_payload
    text = '{"run_dir": "stale"}\nsome prose\n{"run_dir": "real"}\n'
    assert _json_payload(text)["run_dir"] == "real"


def test_json_payload_raises_on_stdout_with_no_json():
    from cap_evolve.cli import _json_payload
    import json as _json
    try:
        _json_payload(f"{NOISE}\n")
    except _json.JSONDecodeError:
        return
    raise AssertionError("expected JSONDecodeError when stdout carries no JSON at all")
