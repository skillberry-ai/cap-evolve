"""Project adapter — IMPLEMENT the 4 methods, then run `acapo check`.

This is the one place you wire agent-capo to YOUR target agent, YOUR benchmark,
and YOUR capability. Everything else (splits, trials, gating, pass^k, memory) is
provided by agent_capo and must not be reimplemented here.

`acapo check` refuses to proceed until all four are real and deterministic.
"""

from __future__ import annotations

from pathlib import Path

# `agent_capo` is importable once installed (`pip install ./core`) or via
# the FORGE skills bootstrap. The intake skill ensures this works.
from agent_capo import CapabilityAdapter, Rollout, Score, Task
from agent_capo.adapter import IMPLEMENT_MARKER


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        # e.g. read examples/<bench>/tasks.jsonl, return Task per line.
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: tasks(split) — return your eval tasks")

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        # Make the candidate live (self.apply(candidate_dir)), run the target
        # agent on `task`, capture output/trace/tool_calls/cost into a Rollout.
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: run_target(task, candidate_dir, split)")

    def score(self, task: Task, rollout: Rollout) -> Score:
        # Return reward in [0,1] + natural-language feedback (the learning signal).
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: score(task, rollout)")

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        # Write `edits` into candidate_dir (if any), then make it the capability
        # the target actually uses (env var / config patch / copy into skills dir).
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: apply(candidate_dir, edits)")
