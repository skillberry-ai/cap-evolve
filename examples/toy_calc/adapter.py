"""Toy-calc adapter — a zero-API, fully deterministic CapabilityAdapter.

It demonstrates the contract end-to-end without any model calls: the "target
agent" is a deterministic stand-in whose behavior depends on the system prompt
being optimized. If the prompt contains the marker ``[CALC]``, the agent computes
the arithmetic correctly; otherwise it guesses and fails. So optimizing the prompt
(adding ``[CALC]``) is what raises the score — a clean, reproducible proof of the
whole pipeline.

Copy this to ``.agentcapo/project/adapters/adapter.py`` (the intake skill does this)
and set ``ACAPO_TOY_DATA`` to this example dir.
"""

from __future__ import annotations

import os
from pathlib import Path

from agent_capo import CapabilityAdapter, Rollout, Score, Task

_DATA = Path(os.environ.get("ACAPO_TOY_DATA", Path(__file__).resolve().parent))


def _safe_eval(expr: str) -> int:
    # arithmetic only: digits, + - * and spaces
    allowed = set("0123456789 +-*")
    if not set(expr) <= allowed:
        raise ValueError(f"unsafe expr: {expr!r}")
    return int(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 (sandboxed)


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        import json
        tasks = []
        for line in (_DATA / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                d = json.loads(line)
                tasks.append(Task(id=d["id"], input=d["input"], target=d["target"]))
        return tasks  # split filtering is handled by the harness via frozen splits

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        prompt = (Path(candidate_dir) / "prompt.txt").read_text(encoding="utf-8")
        expr = str(task.input)
        if "[CALC]" in prompt:
            try:
                out = str(_safe_eval(expr))
            except Exception as e:  # noqa: BLE001
                out = f"error: {e}"
        else:
            # without the instruction, the stand-in agent rambles and gets it wrong
            out = f"I think {expr} is roughly some number."
        return Rollout(task_id=task.id, output=out, trace=f"prompt_had_calc={'[CALC]' in prompt}")

    def score(self, task: Task, rollout: Rollout) -> Score:
        got = (rollout.output or "").strip()
        want = str(task.target).strip()
        ok = got == want
        fb = ("correct" if ok
              else f"expected '{want}' but agent produced '{got}'; the prompt likely "
                   "lacks an explicit instruction to compute and output only the number")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                     trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        # The stand-in reads candidate_dir/prompt.txt directly, so making a
        # candidate "live" is a no-op. A real adapter would copy the candidate
        # into the host's skills/config or set an env var here.
        return None
