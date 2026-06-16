"""tau2 airline adapter — real CapabilityAdapter over tau2-bench with RITS gpt-oss-120b.

Optimizes the airline **policy** (a system-prompt-style capability: policy.md).
Implements the 4 contract methods plus ``run_batch`` so the harness uses tau2's
concurrent runner. Scoring is tau2's own reward in [0,1] with rich, gold-aware
feedback the optimizer turns into general corrective rules.

Env:
  ACAPO_TAU2_TASK_IDS   comma-separated airline task ids to use (default: a small set)
  TAU2_MAX_CONCURRENCY  parallelism for the batch runner (default 20)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agent_capo import CapabilityAdapter, Rollout, Score, Task

import tau2_runtime as rt

_DATA = Path(os.environ.get("ACAPO_TAU2_DATA", Path(__file__).resolve().parent / "data"))
# Default: ALL airline tasks. Set ACAPO_TAU2_TASK_IDS="0,2,6,..." to use a fast subset.
_TASK_IDS_ENV = os.environ.get("ACAPO_TAU2_TASK_IDS", "").strip()


def _fmt_action(action) -> str:
    name = getattr(action, "name", "?")
    args = getattr(action, "arguments", {}) or {}
    cmp = getattr(action, "compare_args", None)
    if cmp:
        args = {k: v for k, v in args.items() if k in cmp}
    return f"{name}(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ")"


class Adapter(CapabilityAdapter):

    def __init__(self):
        self._all = None

    # ---- data ----
    def tasks(self, split: str) -> list[Task]:
        if self._all is None:
            rows = [json.loads(l) for l in (_DATA / "airline.jsonl").read_text().splitlines() if l.strip()]
            wanted = set(i.strip() for i in _TASK_IDS_ENV.split(",") if i.strip())  # empty => all
            self._all = [Task(id=str(r["id"]), input=r.get("input"), target=None,
                              metadata=r.get("metadata", {}))
                         for r in rows if (not wanted or str(r["id"]) in wanted)]
        return list(self._all)

    # ---- make candidate live (inject BOTH the policy and the tools) ----
    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        rt.inject(Path(candidate_dir))

    # ---- run (batch is the fast path the harness prefers) ----
    def run_batch(self, tasks: list[Task], candidate_dir: Path, split: str) -> dict:
        ids = [t.id for t in tasks]
        raw = rt.run_airline_batch(Path(candidate_dir), ids)
        return {tid: Rollout(task_id=tid, output=r["output"], trace=r["trace"],
                             cost_usd=float(r.get("cost", 0.0) or 0.0),
                             tokens=int(r.get("tokens", 0) or 0),
                             metadata={"reward": r["reward"], "reward_info": r["reward_info"],
                                       "termination": r["termination"]})
                for tid, r in raw.items()}

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        rolls = self.run_batch([task], candidate_dir, split)
        return rolls.get(task.id) or Rollout(task_id=task.id, error="no rollout produced")

    # ---- score (tau2 reward + gold-aware feedback) ----
    def score(self, task: Task, rollout: Rollout) -> Score:
        meta = rollout.metadata or {}
        reward = float(meta.get("reward", 0.0))
        ri = meta.get("reward_info")
        fb = f"reward={reward:.2f}; termination={meta.get('termination')}"
        if ri is not None and reward < 1.0:
            ac = getattr(ri, "action_checks", None) or []
            missed = [c for c in ac if not getattr(c, "action_match", getattr(c, "met", True))]
            if ac:
                fb += f"; required_actions_missed={len(missed)}/{len(ac)}"
            lines = [f"    - expected: {_fmt_action(getattr(c, 'action', None))}"
                     for c in missed[:6] if getattr(c, "action", None) is not None]
            if lines:
                fb += "\n  EXPECTED actions not performed (derive the general rule):\n" + "\n".join(lines)
            cc = getattr(ri, "communicate_checks", None) or []
            cm = [c for c in cc if not getattr(c, "met", True)]
            infos = [repr(getattr(c, "info", "")) for c in cm[:6] if getattr(c, "info", "")]
            if infos:
                fb += "\n  EXPECTED info to state to the user (missing): " + "; ".join(infos)
        if rollout.trace:
            fb += f"\n  agent trajectory:\n{rollout.trace}"
        return Score(task_id=task.id, reward=reward, feedback=fb, trial_rewards=[reward])
