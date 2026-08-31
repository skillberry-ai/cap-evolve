"""Wiring proofs for #286: an exception from evaluate_candidate (e.g. an adapter's
live()/rollout setup raising) must cost one candidate, not abort the run — the
same discipline ``run_step`` already applies to the optimizer call beside it.

* a single evaluate_candidate raise is an INDECISIVE step (parent unchanged, stall
  NOT counted, not filed in the rejected memory — the candidate was never measured,
  so it is neither evidence the optimizer ran out of ideas nor a fact about the
  edit), and the run keeps going to the next iteration;
* N consecutive raises look like a broken environment, not N unlucky candidates,
  and must surface loudly (raise out of run_step) instead of being swallowed.
"""

import contextlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_skill"

sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    yield
    os.environ.clear()
    os.environ.update(old)


def _adapter():
    spec = importlib.util.spec_from_file_location("toy_skill_adapter", EXAMPLE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


class RaisingLiveAdapter:
    """Wraps a real adapter; ``live()`` raises for the first ``fail_times`` calls
    AFTER ``skip`` calls (simulating an adapter's live()/rollout setup blowing up),
    then delegates. ``skip`` lets the baseline's own evaluate_candidate call (which
    happens before any run_step under test) go through cleanly."""

    def __init__(self, inner, fail_times: int, skip: int = 0):
        self._inner = inner
        self.fail_times = fail_times
        self.skip = skip
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    @contextlib.contextmanager
    def live(self, candidate_dir):
        self.calls += 1
        if self.skip < self.calls <= self.skip + self.fail_times:
            raise RuntimeError(f"adapter live() blew up on call {self.calls}")
        with self._inner.live(candidate_dir) as ctx:
            yield ctx


def _fresh_run(tmp_path: Path, adapter, ts: str):
    from cap_evolve import Budget, RunDir, harness
    seed = tmp_path / ts / "seed_capability"
    shutil.copytree(EXAMPLE / "seed_capability", seed)
    rd = RunDir.create(tmp_path / ts / ".capevolve", ts=ts,
                       budget=Budget(max_iterations=5, stall=2))
    harness.ensure_splits(adapter, rd, seed=0, ratios=(0.2, 0.4, 0.4))
    return rd, harness.baseline(adapter, seed, run_dir=rd)


_GOOD_EDITS = json.loads((EXAMPLE / "mock_script.json").read_text(encoding="utf-8"))["edits"]


def _good_edit(workdir: Path, instructions: str):
    for e in _GOOD_EDITS:
        target = workdir / e["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        cur = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(e["text"] if e["op"] == "set" else cur + e["text"], encoding="utf-8")


def _events(run_dir, kind: str) -> list[dict]:
    out = []
    for line in (run_dir.root / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("kind") == kind:
                out.append(e)
    return out


def _step(rd, adapter, base, optimizer, **kw):
    from cap_evolve import harness
    return harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=optimizer, instructions="improve val",
                            current_val=base,
                            gate_kwargs={"mode": "significant", "k_se": 1.0}, **kw)


def test_a_single_live_error_is_indecisive_and_the_run_continues(tmp_path):
    """One adapter raise costs an iteration, not the run — and is INDECISIVE, because
    an unmeasured candidate is missing data, not a rejection (test_infra_errors_not_zeros)."""
    from cap_evolve.memory import RejectedMemory
    inner = _adapter()
    adapter = RaisingLiveAdapter(inner, fail_times=1, skip=1)
    rd, base = _fresh_run(tmp_path, adapter, "single_error")
    best_before, stall_before = rd.best_id, rd.spent.stall
    rejected = RejectedMemory(tmp_path / "single_error" / "rejected.jsonl")

    step = _step(rd, adapter, base, _good_edit, rejected=rejected)

    assert step["candidate_val"] is None
    assert step["accepted"] is False
    assert step["decision"]["indecisive"] is True
    assert "eval_error" in step and "blew up" in step["eval_error"]
    # parent unchanged, the iteration IS charged, but the stall counter is NOT — the
    # candidate was never judged, so it is no evidence the optimizer ran out of ideas.
    assert rd.best_id == best_before
    assert rd.spent.stall == stall_before
    assert rd.spent.iterations == 1
    # and it is NOT taught to the optimizer as a failed edit: an infra failure says
    # nothing about the content of the candidate.
    assert not rejected.path.exists() or rejected.path.read_text(encoding="utf-8").strip() == ""
    ev = _events(rd, "evaluate_error")
    assert len(ev) == 1 and ev[0]["consecutive"] == 1
    assert len(_events(rd, "step_indecisive")) == 1

    # the run continues: a second, clean step on the same run_dir still works.
    step2 = _step(rd, adapter, base, _good_edit)
    assert step2["candidate_val"] is not None
    assert step2["accepted"] is True


def test_n_consecutive_live_errors_abort_loudly_as_an_infra_failure(tmp_path):
    """A truly broken adapter/environment must not look like N rejected candidates."""
    from cap_evolve import harness
    inner = _adapter()
    adapter = RaisingLiveAdapter(inner, fail_times=99, skip=1)  # never recovers
    rd, base = _fresh_run(tmp_path, adapter, "always_broken")

    for _ in range(harness._MAX_CONSECUTIVE_EVAL_ERRORS - 1):
        step = _step(rd, adapter, base, _good_edit)
        assert step["accepted"] is False

    with pytest.raises(RuntimeError, match="consecutive candidate evaluations raised"):
        _step(rd, adapter, base, _good_edit)


def test_a_success_after_failures_resets_the_streak(tmp_path):
    inner = _adapter()
    adapter = RaisingLiveAdapter(inner, fail_times=1, skip=1)
    rd, base = _fresh_run(tmp_path, adapter, "resets")

    _step(rd, adapter, base, _good_edit)  # fails once, streak -> 1
    _step(rd, adapter, base, _good_edit)  # succeeds, streak -> 0
    assert rd._consecutive_eval_errors == 0
