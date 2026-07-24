"""JSONL + litellm adapter template — the most common cap-evolve pattern.

Onboarding a new eval is **config, not code**:

  1. Point ``TASKS_FILE`` at your ``.jsonl`` (or drop a ``tasks.jsonl`` next to this
     file). Each line is one task: ``{"id": "...", "input": "...", "target": "..."}``.
  2. Set ``MODEL`` + credentials — see ``model_config.py`` (any litellm provider).
  3. Pick ``SCORING`` = ``exact`` | ``contains`` | ``regex``.
  4. ``cap-evolve check`` && ``cap-evolve run``.

What gets optimized is the agent's **system prompt** in ``seed_capability/prompt.txt``
— that is the file the optimizer edits each iteration.

    import model_config   # provider-agnostic model wiring (drop it next to this file)

Everything except *where tasks come from* and *how to score* is provided here.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # shared model_config.py

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import model_config

# --- configuration (all via env / .env) -------------------------------------
TASKS_FILE = os.environ.get(
    "TASKS_FILE", str(Path(__file__).resolve().parent / "tasks.jsonl")
)
SCORING = os.environ.get("SCORING", "exact").lower()  # exact | contains | regex


def _score(output: str, target: str, mode: str) -> bool:
    """Return True if ``output`` matches ``target`` under ``mode``."""
    out = (output or "").strip()
    tgt = (target or "").strip()
    if mode == "contains":
        return tgt.lower() in out.lower()
    if mode == "regex":
        return re.search(tgt, out) is not None
    # default: exact (case-insensitive, whitespace-trimmed)
    return out.lower() == tgt.lower()


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        """Load tasks from the JSONL file. Split filtering is handled by the harness."""
        tasks: list[Task] = []
        for line in Path(TASKS_FILE).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            tasks.append(Task(id=str(d["id"]), input=d["input"], target=d.get("target")))
        return tasks

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Call the configured model with the candidate prompt + task input."""
        system_prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
        try:
            import litellm

            resp = litellm.completion(
                model=model_config.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": str(task.input)},
                ],
                seed=seed,  # forwarded so distinct trials are independent draws
                **model_config.llm_kwargs(),
            )
            output = resp.choices[0].message.content or ""
            cost = float(getattr(resp, "_hidden_params", {}).get("response_cost", 0) or 0)
            usage = getattr(resp, "usage", None)
            return Rollout(
                task_id=task.id,
                output=output,
                trace=output,
                cost_usd=cost,
                tokens=(usage.total_tokens if usage else 0),
                metadata={"model": model_config.MODEL, "seed": seed},
            )
        except Exception as e:  # noqa: BLE001 — infra error, not a prompt defect
            return Rollout(task_id=task.id, error=f"LLM call failed: {e}")

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=f"Rollout failed ({rollout.error}); infrastructure noise, "
                "not a prompt defect — do not optimize against it.",
            )
        ok = _score(rollout.output or "", str(task.target), SCORING)
        snippet = (rollout.output or "").strip().replace("\n", " ")[:200]
        fb = (
            "correct"
            if ok
            else f"output did not match the expected answer under '{SCORING}' scoring. "
            f"Model produced: {snippet!r}. Guide the model toward the required "
            "answer format/content — do not hard-code answers."
        )
        return Score(
            task_id=task.id,
            reward=1.0 if ok else 0.0,
            feedback=fb,
            trial_rewards=[1.0 if ok else 0.0],
        )


if __name__ == "__main__":
    # ponytail self-check: the scoring logic (no model call).
    assert _score("Paris", "paris", "exact")
    assert not _score("Paris, France", "paris", "exact")
    assert _score("The capital is Paris.", "Paris", "contains")
    assert _score("answer: 42", r"\d+", "regex")
    assert not _score("no digits here", r"\d+", "regex")
    print("jsonl_litellm scoring self-check: OK")
