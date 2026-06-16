"""json_extract adapter — a second, different-domain benchmark from scratch.

Demonstrates AgentCapTune extensibility: a brand-new benchmark plugs in by writing
ONLY this adapter + data + a seed prompt. No core or skill changes. The scoring
is JSON-aware (parse the agent's output, check a field) — a different paradigm
from toy_calc's exact-match — proving the adapter contract generalizes.

The deterministic stand-in agent outputs strict JSON {"answer": ...} only when the
prompt instructs it to ([STRICT_JSON] marker); otherwise it emits prose that fails
JSON parsing. So adding that instruction is the optimization that raises the score.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agent_capo import CapabilityAdapter, Rollout, Score, Task

_DATA = Path(os.environ.get("ACAPO_JSON_DATA", Path(__file__).resolve().parent))


def _extract(record: str, field: str) -> str:
    m = re.search(rf"{re.escape(field)}:\s*([^;]+)", record)
    return m.group(1).strip() if m else ""


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        tasks = []
        for line in (_DATA / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                d = json.loads(line)
                tasks.append(Task(id=d["id"], input={"record": d["input"], "field": d["field"]},
                                  target=d["target"]))
        return tasks

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        prompt = (Path(candidate_dir) / "prompt.txt").read_text(encoding="utf-8")
        rec, field = task.input["record"], task.input["field"]
        value = _extract(rec, field)
        if "[STRICT_JSON]" in prompt:
            out = json.dumps({"answer": value})
        else:
            out = f"The {field} in the record appears to be {value}, I think."
        return Rollout(task_id=task.id, output=out)

    def score(self, task: Task, rollout: Rollout) -> Score:
        want = str(task.target).strip()
        got_raw = (rollout.output or "").strip()
        try:
            parsed = json.loads(got_raw)
            got = str(parsed.get("answer", "")).strip()
            valid_json = True
        except Exception:
            got, valid_json = "", False
        ok = valid_json and got == want
        if ok:
            fb = "correct strict-JSON answer"
        elif not valid_json:
            fb = (f"output was not valid JSON (got prose). The eval requires a strict JSON "
                  f"object {{'answer': '{want}'}}; instruct the agent to output ONLY JSON.")
        else:
            fb = f"valid JSON but answer was '{got}', expected '{want}'"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                     trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        return None
