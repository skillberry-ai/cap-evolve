"""Project adapter — IMPLEMENT the 4 methods, then run `cap-evolve check`.

This is the one place you wire cap-evolve to YOUR target agent, YOUR benchmark,
and YOUR capability. Everything else (splits, trials, gating, pass^k, memory) is
provided by cap_evolve and must not be reimplemented here.

`cap-evolve check` refuses to proceed until all four are real and deterministic.
"""

from __future__ import annotations

import json
import os
import sys
import importlib.util
from pathlib import Path

# `cap_evolve` is importable once installed (`pip install ./core`) or via
# the FORGE skills bootstrap. The intake skill ensures this works.
from cap_evolve import CapabilityAdapter, Rollout, Score, Task
from cap_evolve.adapter import IMPLEMENT_MARKER


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        """Read tasks from JSONL file specified in CAPEVOLVE_DT_TASKS env var."""
        tasks_path = os.environ.get("CAPEVOLVE_DT_TASKS")
        if not tasks_path:
            raise ValueError("CAPEVOLVE_DT_TASKS environment variable not set")
        
        tasks = []
        with open(tasks_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                tasks.append(Task(
                    id=obj["id"],
                    input=obj["input"],
                    target=obj["target"]
                ))
        return tasks

    def run_target(self, task: Task, candidate_dir: Path, split: str) -> Rollout:
        """Import parse_date from candidate_dir and run it on task.input."""
        try:
            # Import parse_date.py from candidate_dir
            parse_date_path = candidate_dir / "parse_date.py"
            spec = importlib.util.spec_from_file_location("parse_date", parse_date_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load parse_date.py from {candidate_dir}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Call parse_date function
            result = module.parse_date(task.input)
            
            return Rollout(task_id=task.id, output=str(result))
        except Exception as e:
            return Rollout(task_id=task.id, error=str(e))

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Return 1.0 if output matches target, else 0.0 with feedback."""
        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=f"Input: '{task.input}' | Expected: '{task.target}' | Error: {rollout.error}"
            )
        
        if rollout.output == task.target:
            return Score(
                task_id=task.id,
                reward=1.0,
                feedback=f"Input: '{task.input}' | Expected: '{task.target}' | Got: '{rollout.output}' ✓"
            )
        else:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=f"Input: '{task.input}' | Expected: '{task.target}' | Got: '{rollout.output}'"
            )

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """No-op: candidate_dir is already the tool directory that run_target imports from."""
        pass