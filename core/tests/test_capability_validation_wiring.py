"""Wiring proofs for the per-capability ``validate()`` hook in ``run_step``.

The capability handlers are unit-tested by each skill's own ``scripts/check.py``. What is
proved HERE is the wiring into the optimization loop, because the failure mode is
**silent-off** — if the hook stops firing, the loop happily scores invalid candidates again
and nothing else in the suite notices:

* a candidate the capability calls invalid is INDECISIVE, not rejected at 0.0: no reward,
  best_id and the stall counter untouched, and **no rollouts paid for** (validation runs
  before ``evaluate_candidate``);
* a clean candidate under the same wiring still accepts;
* a problem the PARENT already had does not void the step (a pre-existing violation must
  not wedge a run);
* no ``capabilities`` ⇒ no validation, i.e. the old behavior is unchanged;
* a capability that cannot be loaded or whose ``validate()`` raises is REPORTED
  (``capability_validate_unavailable``) instead of quietly disabling enforcement.

Mirrors ``test_integrity_wiring.py``, which proves the same discipline for the tamper path.
"""

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

CAPS = ["skill-package"]


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


class CountingAdapter:
    """Counts rollouts, so a test can prove an invalid candidate cost nothing."""

    def __init__(self, inner):
        self._inner = inner
        self.rollouts = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run_target(self, task, ctx, *, seed: int = 0):
        self.rollouts += 1
        return self._inner.run_target(task, ctx, seed=seed)


def _fresh_run(tmp_path: Path, adapter, ts: str, seed_extra=None):
    from cap_evolve import Budget, RunDir, harness
    seed = tmp_path / ts / "seed_capability"
    shutil.copytree(EXAMPLE / "seed_capability", seed)
    if seed_extra:
        seed_extra(seed)
    rd = RunDir.create(tmp_path / ts / ".capevolve", ts=ts,
                       budget=Budget(max_iterations=5, stall=2))
    # 4 val tasks (3 of them messy) so a real gain clears the significance bar; the
    # default 0.25 ratio leaves 2, where k=1·SE swallows any delta.
    harness.ensure_splits(adapter, rd, seed=0, ratios=(0.2, 0.4, 0.4))
    return rd, harness.baseline(adapter, seed, run_dir=rd)


# The good edit is the example's own mock script, so the test cannot drift from the
# edit the shipped example claims works.
_GOOD_EDITS = json.loads((EXAMPLE / "mock_script.json").read_text(encoding="utf-8"))["edits"]


def _good_edit(workdir: Path, instructions: str):
    """A working bundled script + the SKILL.md pointer that tells the agent to run it."""
    for e in _GOOD_EDITS:
        target = workdir / e["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        cur = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(e["text"] if e["op"] == "set" else cur + e["text"], encoding="utf-8")


def _broken_script(workdir: Path, instructions: str):
    """Ships a bundled script that does not compile — deterministic code that isn't."""
    (workdir / "scripts").mkdir(exist_ok=True)
    (workdir / "scripts" / "helper.py").write_text("def broken(:\n", encoding="utf-8")


def _events(run_dir, kind: str) -> list[dict]:
    out = []
    for line in (run_dir.root / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("kind") == kind:
                out.append(e)
    return out


def _step(rd, adapter, base, optimizer, capabilities=(), **kw):
    from cap_evolve import harness
    # ``capabilities`` reaches run_step through the shared OptimizerContext (#355).
    ctx = harness.OptimizerContext(capabilities=tuple(capabilities))
    return harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=optimizer, instructions="improve val",
                            current_val=base, ctx=ctx,
                            gate_kwargs={"mode": "significant", "k_se": 1.0}, **kw)


# --- the catch ---------------------------------------------------------------

def test_invalid_candidate_is_indecisive_and_costs_nothing(tmp_path):
    adapter = CountingAdapter(_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "invalid")
    best_before, stall_before, rollouts_before = rd.best_id, rd.spent.stall, adapter.rollouts

    step = _step(rd, adapter, base, _broken_script, capabilities=CAPS)

    # 1. indecisive, NOT a rejection at 0.0 — the candidate was never measured.
    assert step["candidate_val"] is None
    assert step["decision"]["indecisive"] is True
    assert step["accepted"] is False
    assert "does not compile" in json.dumps(step["validation"]["problems"])
    # 2/3. best and the stall counter are untouched (an unjudged candidate is not a reject).
    assert rd.best_id == best_before
    assert rd.spent.stall == stall_before
    # 4. the iteration is still counted as spent.
    assert rd.spent.iterations == 1
    # 5. NO rollouts were paid for: validation runs before evaluate_candidate.
    assert adapter.rollouts == rollouts_before
    assert not list((rd.root / "rollouts" / "val").glob(f"{step['candidate_id']}*"))
    # 6. auditable.
    ev = _events(rd, "capability_invalid")
    assert len(ev) == 1 and "skill-package" in json.dumps(ev[0]["report"])
    assert len(_events(rd, "step_indecisive")) == 1


def test_valid_candidate_under_the_same_wiring_still_accepts(tmp_path):
    adapter = _adapter()
    rd, base = _fresh_run(tmp_path, adapter, "valid")
    step = _step(rd, adapter, base, _good_edit, capabilities=CAPS)

    assert step["candidate_val"] is not None
    assert step["accepted"] is True
    assert step["candidate_val"]["reward"] > base.reward
    assert rd.best_id == step["candidate_id"]
    assert _events(rd, "capability_invalid") == []


def test_pre_existing_problem_does_not_void_the_step(tmp_path):
    """A seed that is ALREADY invalid must not make every future step indecisive."""
    def overlong_body(seed: Path):
        p = seed / "SKILL.md"
        p.write_text(p.read_text(encoding="utf-8") + "filler\n" * 600, encoding="utf-8")

    adapter = _adapter()
    rd, base = _fresh_run(tmp_path, adapter, "preexisting", seed_extra=overlong_body)
    # the seed really is invalid on the rule we rely on
    from cap_evolve import harness
    seed_report = harness._capability_validate(CAPS, rd.candidate_dir("seed"))
    assert any("lines" in p for p in seed_report.problems)

    step = _step(rd, adapter, base, _good_edit, capabilities=CAPS)
    assert step["candidate_val"] is not None      # measured, not voided
    assert step["decision"]["indecisive"] is False


def test_no_capabilities_means_no_validation(tmp_path):
    """Back-compat: a caller that passes no capabilities behaves exactly as before."""
    adapter = _adapter()
    rd, base = _fresh_run(tmp_path, adapter, "off")
    step = _step(rd, adapter, base, _broken_script)      # same broken edit, no capabilities

    assert step["candidate_val"] is not None              # it WAS measured
    assert "validation" not in step
    assert _events(rd, "capability_invalid") == []


def test_unloadable_capability_is_reported_not_silently_ignored(tmp_path):
    """Enforcement that turns itself off must say so — silent-off is the defect."""
    adapter = _adapter()
    rd, base = _fresh_run(tmp_path, adapter, "missing")
    step = _step(rd, adapter, base, _good_edit, capabilities=["no-such-capability"])

    assert step["candidate_val"] is not None              # no signal ⇒ no gating
    ev = _events(rd, "capability_validate_unavailable")
    assert len(ev) == 1
    assert ev[0]["capability"] == "no-such-capability" and "no abstract.py" in ev[0]["reason"]
