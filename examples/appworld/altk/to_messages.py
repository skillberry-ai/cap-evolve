"""Convert one cap-evolve AppWorld rollout JSON to the OpenAI message list ALTK-Evolve mines (README: ALTK-Evolve arm).

The bare task instruction comes first: ALTK uses the first user message as the task. The stock
demo and the API docs are not included (they would become the "task"). No outcome label is
passed, so the library judges success from the trajectory itself (its default).
"""

from __future__ import annotations

import json
from pathlib import Path


def rollout_to_messages(rollout_json: dict) -> list[dict]:
    inp = rollout_json.get("input") or {}
    msgs = [{"role": "user", "content": f"{inp.get('instruction', '')}\nSupervisor: {inp.get('supervisor', '')}"}]
    for step in (rollout_json.get("rollout") or {}).get("trace") or []:
        thought = (step.get("thought") or "").strip()
        code = (step.get("code") or "").strip()
        content = (thought + "\n" if thought else "") + (f"```python\n{code}\n```" if code else "")
        msgs.append({"role": "assistant", "content": content or "(no code)"})
        msgs.append({"role": "user", "content": f"Output:\n```\n{step.get('output', '')}\n```"})
    return msgs


def load(path: Path) -> list[dict]:
    return rollout_to_messages(json.loads(Path(path).read_text()))
