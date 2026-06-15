"""The adapter contract — the small set of methods the OPTIMIZER agent implements.

This is agent-capo's generalization device (prior agent-optimization work had 3 adapters, SkillOpt had 5;
we use 4, cleaner). The using-agent implements these once in
``.agentcapo/project/adapters/`` so that *any* target agent, *any* benchmark, and
*any* capability can be driven by the same pipeline:

    tasks(split)                        -> list[Task]   # where eval data comes from
    run_target(task, candidate_dir, split) -> Rollout   # run the agent under test
    score(task, rollout)                -> Score        # 0..1 reward + ASI feedback
    apply(candidate_dir, edits=None)     -> None         # make the candidate LIVE

``apply(edits=None)`` means "make the capability in ``candidate_dir`` the one the
target actually uses" (prior agent-optimization work's *inject*). With ``edits`` it also writes those edits
first. Splits, trials, gating, pass^k, memory and the run dir are provided by
``core`` and must NOT be reimplemented here — that is what keeps eval honest.

Stub methods raise ``NotImplementedError`` with an ``IMPLEMENT ME`` marker so the
checker can detect and report exactly what is unfilled.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .types import Rollout, Score, Task

IMPLEMENT_MARKER = "IMPLEMENT ME"


class CapabilityAdapter(ABC):
    """Implement this in ``.agentcapo/project/adapters/adapter.py``."""

    @abstractmethod
    def tasks(self, split: str) -> list[Task]:
        """Return the tasks for ``split`` ('train'|'val'|'test').

        Source is yours: a jsonl file, a benchmark export, a generator. Return
        the SAME tasks for the same split across calls (determinism).
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: tasks(split)")

    @abstractmethod
    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        """Run the target agent on ``task`` with the candidate in ``candidate_dir``.

        Call ``apply(candidate_dir)`` (or rely on the loop having applied it) so
        the target actually uses the candidate. Capture output + trace + tool
        calls + cost into the returned ``Rollout``. Do NOT score here.
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: run_target(task, candidate_dir, split)")

    @abstractmethod
    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score one rollout in [0, 1] with natural-language ``feedback``.

        ``feedback`` is the learning signal (gepa's ASI) — describe WHY it scored
        as it did in general terms; never leak the gold answer into feedback.
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: score(task, rollout)")

    @abstractmethod
    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Make the capability in ``candidate_dir`` the one the target uses.

        With ``edits`` (component->text or a capability-specific patch), write
        them into ``candidate_dir`` first, then make it live (env var, config
        patch, copy into the host's skills dir, etc.).
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: apply(candidate_dir, edits)")


def stub_methods(adapter: object) -> list[str]:
    """Return the names of adapter methods that are still unimplemented.

    A method counts as a stub if calling it raises ``NotImplementedError`` whose
    message carries the IMPLEMENT marker. We probe with throwaway args; any other
    exception means the method is implemented (it ran far enough to fail on the
    fake input), so it is NOT reported as a stub.
    """
    import inspect
    from pathlib import Path as _P

    probes = {
        "tasks": lambda m: m("val"),
        "run_target": lambda m: m(Task(id="__probe__"), _P("."), "val"),
        "score": lambda m: m(Task(id="__probe__"), Rollout(task_id="__probe__")),
        "apply": lambda m: m(_P("."), None),
    }
    stubs = []
    for name, probe in probes.items():
        m = getattr(adapter, name, None)
        if m is None:
            stubs.append(name)
            continue
        try:
            probe(m)
        except NotImplementedError as e:
            if IMPLEMENT_MARKER in str(e):
                stubs.append(name)
        except Exception:
            pass  # implemented (failed on fake input, which is fine)
    return stubs
