"""json_extract's runner + a CUSTOM scorer — the two things a manifest can't declare.

A deterministic zero-API stand-in extractor. The candidate prompt controls its
behavior through two markers, so prompt edits provably move the score with no model
calls:

  ``[JSON]``   emit a JSON object instead of prose
  ``[FIELDS]`` include all three fields (name/city/year) rather than just the name

Scoring is ``custom`` because partial credit over parsed JSON fields is real logic
(a per-field comparison after a parse that can fail) — exactly the kind of thing a
config language should NOT try to express. Everything else is in ``benchmark.yaml``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from cap_evolve import Score

_FIELDS = ("name", "city", "year")


def _extract(text: str) -> dict:
    """The stand-in's (deterministic) understanding of one sentence."""
    m = re.match(r"(?P<name>.+?) was born in (?P<city>.+?) in (?P<year>\d{4})", text)
    if not m:
        return {}
    return {"name": m["name"], "city": m["city"], "year": int(m["year"])}


def run(task, ctx, *, seed: int = 0):
    prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
    facts = _extract(str(task.input))
    if "[JSON]" not in prompt:
        return {"output": f"Sure! That sentence is about {facts.get('name', 'someone')}.",
                "trace": "prose (prompt did not ask for JSON)"}
    keep = _FIELDS if "[FIELDS]" in prompt else ("name",)
    return {"output": json.dumps({k: facts[k] for k in keep if k in facts},
                                 sort_keys=True),
            "trace": f"json fields={list(keep)}"}


def score(task, rollout) -> Score:
    """Per-field partial credit over parsed JSON — the bespoke half, as code."""
    if rollout.error:
        return Score(task_id=task.id, reward=0.0, trial_rewards=[0.0],
                     feedback=f"Rollout failed ({rollout.error}); infrastructure "
                              "noise, not a prompt defect.")
    want = json.loads(str(task.target))
    try:
        got = json.loads(str(rollout.output or ""))
        if not isinstance(got, dict):
            raise ValueError("top level is not an object")
    except Exception as e:  # noqa: BLE001
        return Score(task_id=task.id, reward=0.0, trial_rewards=[0.0],
                     feedback=f"output was not a JSON object ({e}); the prompt must "
                              "instruct the agent to reply with a single JSON object "
                              f"holding the {list(_FIELDS)} fields.")
    hits = [k for k in _FIELDS if str(got.get(k, "")) == str(want[k])]
    reward = len(hits) / len(_FIELDS)
    missing = [k for k in _FIELDS if k not in hits]
    fb = ("all fields correct" if not missing else
          f"got {len(hits)}/{len(_FIELDS)} fields; wrong or absent: {missing}. The "
          "prompt should name every required field explicitly — never hard-code values.")
    return Score(task_id=task.id, reward=reward, feedback=fb, trial_rewards=[reward])
