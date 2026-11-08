"""HuggingFace dataset + litellm adapter template.

Identical to ``jsonl_litellm`` but tasks come from a HuggingFace dataset instead
of a local file. Onboarding is **config, not code** — map your dataset's columns
with env vars, no code edits:

  1. Set ``HF_DATASET`` (+ optional ``HF_SPLIT``, ``HF_CONFIG``).
  2. Map columns: ``INPUT_FIELD``, ``TARGET_FIELD``, ``ID_FIELD``.
  3. Set ``MODEL`` + credentials — see ``model_config.py`` (any litellm provider).
  4. Pick ``SCORING`` = ``exact`` | ``contains`` | ``regex``.
  5. ``cap-evolve check`` && ``cap-evolve run``.

Example (GSM8K-style):
    HF_DATASET=openai/gsm8k  HF_CONFIG=main  HF_SPLIT=test
    INPUT_FIELD=question  TARGET_FIELD=answer  SCORING=contains

What gets optimized is ``seed_capability/prompt.txt`` (the agent's system prompt).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # shared model_config.py

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import model_config

# --- configuration (all via env / .env) -------------------------------------
HF_DATASET = os.environ.get("HF_DATASET", "")
HF_CONFIG = os.environ.get("HF_CONFIG", "") or None
HF_SPLIT = os.environ.get("HF_SPLIT", "test")
INPUT_FIELD = os.environ.get("INPUT_FIELD", "question")
TARGET_FIELD = os.environ.get("TARGET_FIELD", "answer")
ID_FIELD = os.environ.get("ID_FIELD", "")  # "" → use the row index as the id
SCORING = os.environ.get("SCORING", "exact").lower()  # exact | contains | regex

_cache: list[Task] | None = None


def _score(output: str, target: str, mode: str) -> bool:
    out = (output or "").strip()
    tgt = (target or "").strip()
    if mode == "contains":
        return tgt.lower() in out.lower()
    if mode == "regex":
        return re.search(tgt, out) is not None
    return out.lower() == tgt.lower()


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        """Load tasks from a HuggingFace dataset (cached). Harness handles splits."""
        global _cache
        if _cache is not None:
            return _cache
        if not HF_DATASET:
            raise RuntimeError("Set HF_DATASET (and INPUT_FIELD/TARGET_FIELD) in .env.")
        from datasets import load_dataset  # lazy: keeps `check` offline-friendly

        ds = load_dataset(HF_DATASET, HF_CONFIG, split=HF_SPLIT)
        _cache = [
            Task(
                id=str(row[ID_FIELD]) if ID_FIELD else f"{HF_SPLIT}-{i}",
                input=row[INPUT_FIELD],
                target=row.get(TARGET_FIELD),
            )
            for i, row in enumerate(ds)
        ]
        return _cache

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        system_prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
        try:
            import litellm

            resp = litellm.completion(
                model=model_config.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": str(task.input)},
                ],
                seed=seed,
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
    # ponytail self-check: the scoring logic (no dataset / model call).
    assert _score("Paris", "paris", "exact")
    assert _score("The answer is 42", "42", "contains")
    assert _score("answer: 42", r"\d+", "regex")
    assert not _score("nope", r"\d+", "regex")
    print("huggingface_litellm scoring self-check: OK")
