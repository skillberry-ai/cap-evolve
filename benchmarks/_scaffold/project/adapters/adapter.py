"""Project adapter — IMPLEMENT the 3 abstract methods, then run `cap-evolve check`.

This is the one place you wire cap-evolve to YOUR target agent, YOUR benchmark,
and YOUR capability. Everything else (splits, trials, gating, pass^k, memory) is
provided by cap_evolve and must NOT be reimplemented here.

Contract (authoritative: core/cap_evolve/adapter.py + docs/ADAPTER_CONTRACT.md):
  tasks(split)                   -> list[Task]   # 'train'|'val'|'test'|'all'; non-empty, STABLE across calls
  run_target(task, ctx, *, seed) -> Rollout      # run the agent under test; forward `seed` if the runner is
                                                 #   stochastic; set Rollout.error on an INFRA failure (timeout/API)
  score(task, rollout)           -> Score        # reward in [0,1] + general feedback (NEVER leak the gold answer)

Optional overrides (the base class has working defaults — don't reimplement unless needed):
  materialize(candidate_dir, edits=None) -> None     # PURE write of edits into candidate_dir (no global effect)
  live(candidate_dir)                    -> ctx (CM)  # make the candidate LIVE for ONE eval; yields ctx (default: the dir)
  apply(candidate_dir, edits=None)       -> None      # back-compat "inject" hook; default live() calls it on enter
  run_batch(tasks, ctx, *, seed)         -> dict|list # implement INSTEAD of run_target to drive a benchmark's OWN
                                                      #   batch runner (return {task_id: Rollout} or a list parallel to tasks)

Notes:
- During a run the harness calls `tasks("all")` and filters by the frozen split ids, so handle "all".
- Per-trial seeding: trial k is run with `seed = base_seed + k`. A stochastic runner MUST forward it.

`cap-evolve check` refuses to proceed until tasks/run_target/score are real and deterministic
(scorer determinism is required; target *stochasticity* is fine — it's handled by multi-trial eval).
"""

from __future__ import annotations

from pathlib import Path

# `cap_evolve` is importable once installed (`pip install ./core`) or via
# the skills bootstrap. The intake skill ensures this works.
from cap_evolve import CapabilityAdapter, Rollout, Score, Task
from cap_evolve.adapter import IMPLEMENT_MARKER


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        # e.g. read examples/<bench>/tasks.jsonl, return a Task per line. Handle "all".
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: tasks(split) — return your eval tasks")

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        # `ctx` is what live() yielded (default: the candidate dir). Run the target
        # agent on `task`, capture output/trace/tool_calls/cost into a Rollout.
        # Forward `seed` if the runner is stochastic; set Rollout.error on infra failure.
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: run_target(task, ctx, *, seed)")

    def score(self, task: Task, rollout: Rollout) -> Score:
        # Return reward in [0,1] + natural-language feedback (the learning signal).
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: score(task, rollout)")

    # ---- optional: override to inject the candidate into your target ----
    # The base class provides materialize() (pure write) + live() (context manager
    # that calls apply() on enter). Override apply() to make candidate_dir the
    # capability the target actually uses (e.g. patch a benchmark's policy/tools).
    # def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
    #     self.materialize(candidate_dir, edits)
    #     ...  # inject candidate_dir into the target
