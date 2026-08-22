"""Contract: implement-and-check is a real gate, not a no-op.

Asserts the three behaviours the phase actually promises:
  1. a project with NO adapter is refused;
  2. a LOADABLE adapter whose method raises the IMPLEMENT-ME marker is named in
     ``rep.stubs`` (the old fixture was an ABC with unimplemented abstractmethods, so
     instantiation raised TypeError and ``stub_methods`` was never reached);
  3. a non-deterministic ``score()`` yields a "non-deterministic" problem — the one
     assertion the whole honesty story of this phase rests on.

Known gaps in the core gate are tracked in issue #358 and documented in SKILL.md under
"What the gate does and does not guarantee"; they are deliberately NOT asserted here.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.check import run_check
from cap_evolve.skillcheck import Checker, import_run

_HEAD = (
    "from cap_evolve import CapabilityAdapter\n"
    "from cap_evolve.types import Task, Rollout, Score\n"
)

# Loadable (all three abstract methods overridden) but `score` re-raises the marker.
_MARKER_STUB = _HEAD + (
    "class Adapter(CapabilityAdapter):\n"
    "    def tasks(self, split): return [Task(id='t1', input='1+1', target='2')]\n"
    "    def run_target(self, task, ctx, *, seed=0): return Rollout(task_id=task.id, output='2')\n"
    "    def score(self, task, rollout):\n"
    "        raise NotImplementedError('IMPLEMENT ME: score(task, rollout)')\n"
)

_RNG_SCORER = _HEAD + (
    "import random\n"
    "class Adapter(CapabilityAdapter):\n"
    "    def tasks(self, split): return [Task(id='t1', input='1+1', target='2')]\n"
    "    def run_target(self, task, ctx, *, seed=0): return Rollout(task_id=task.id, output='2')\n"
    "    def score(self, task, rollout):\n"
    "        return Score(task_id=task.id, reward=random.random(), feedback='rng')\n"
)


def _project(tmp: str, source: str) -> Path:
    proj = Path(tmp) / "project"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text(source, encoding="utf-8")
    return proj


def main() -> int:
    c = Checker("implement-and-check")
    c.require_main(import_run())

    # 1. No adapter at all must not pass the gate.
    with tempfile.TemporaryDirectory() as d:
        empty = Path(d) / "project"
        empty.mkdir()
        rep = run_check(empty)
        c.check(not rep.ok and bool(rep.problems),
                "check passed a project with no adapter (gate is a no-op)",
                note="refuses a project with no adapter")

    # 2. A loadable, marker-stubbed method must be NAMED in rep.stubs.
    with tempfile.TemporaryDirectory() as d:
        rep = run_check(_project(d, _MARKER_STUB))
        c.check(not rep.ok and "score" in rep.stubs,
                f"stubbed score() not reported in stubs (got stubs={rep.stubs}, "
                f"problems={rep.problems})",
                note="names the unimplemented method in stubs[]")

    # 3. A non-deterministic scorer must produce a "non-deterministic" problem.
    with tempfile.TemporaryDirectory() as d:
        rep = run_check(_project(d, _RNG_SCORER))
        c.check(not rep.ok and any("non-deterministic" in p for p in rep.problems),
                f"RNG scorer passed the determinism probe (problems={rep.problems})",
                note="detects a non-deterministic score()")

    # 4. SKILL.md's account of WHERE the gate is enforced must match the code. PR #374
    #    added run_check() to baseline/scripts/run.py after this SKILL.md was written,
    #    so the "the standalone chain is ungated" paragraph went stale and told the
    #    reader a closed hole was still open.
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    gated = "run_check(" in (Path(__file__).resolve().parents[2] / "baseline"
                             / "scripts" / "run.py").read_text(encoding="utf-8")
    claims_ungated = ("contains no check" in skill
                      or "has no gate of its own" in skill)
    c.check(gated != claims_ungated,
            "SKILL.md and baseline/scripts/run.py disagree about whether the standalone "
            f"chain is gated (baseline calls run_check={gated}, "
            f"SKILL.md says ungated={claims_ungated})",
            note="SKILL.md's standalone-gate claim matches baseline/scripts/run.py")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
