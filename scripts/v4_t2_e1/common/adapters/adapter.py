#!/usr/bin/env python3
"""Harbor adapter for v4_t2_e1 — single-task, system-prompt-only cap-evolve
optimization of parsec v4.

Shared by all 21 per-task projects via a symlink chain
(project/adapters -> .capevolve/v4_t2_e1_common/adapters -> this file's own
directory). Since load_adapter() (core/cap_evolve/check.py) instantiates
Adapter() with zero constructor arguments, this adapter reads a required
TASK_ID environment variable — set by scripts/v4_t2_e1/run_one_task.py
immediately before each `cap-evolve run` invocation — to know which of the
21 tasks it is running.

Candidate delivery: system_prompt.py's get_agent_prompt() re-reads
config/prompts/*.md from disk on every request, keyed by mtime (see the
design doc) — so apply() just overwrites those files in the live
parsec-live clone. No process restart, no Harbor injection flag needed.

Note on PARSEC_LIVE_PROMPTS_DIR: this is read into an INSTANCE attribute
(self.live_prompts_dir) inside __init__, evaluated fresh every time an
Adapter is constructed — NOT a module-level constant computed once at
import time. A module-level constant would freeze the default path in at
first import, so a test (or a caller) that patches the env var AFTER this
module has already been imported would silently miss it — apply() would
keep writing to the real default directory instead of the caller's chosen
one. Reading it per-instance is what makes the env var actually override
the default at every construction, which is exactly what
TestAdapterApply relies on.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# This file is reached through a chain of symlinks (project/adapters ->
# v4_t2_e1_common/adapters -> scripts/v4_t2_e1/common/adapters). .resolve()
# fully follows every hop, landing on the real physical path regardless —
# so this always finds the actual repo root, not wherever the caller's
# --project happened to point.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from capevolve_harbor.results import build_feedback, parse_job_dir  # noqa: E402
from cap_evolve import CapabilityAdapter, Rollout, Score, Task  # noqa: E402

V4N = Path(os.environ.get("PARSEC_V4N", "/Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16"))
TASKS_DIR = V4N / "_run" / "tasks"
JOBS_ROOT = V4N / "_run" / "jobs" / "v4_t2_e1"
TRIAL_TIMEOUT_SEC = 20 * 60

PROMPT_FILES = [
    "orchestrator.md",
    "shared_context.md",
    "aap2_agent.md",
    "babylon_agent.md",
    "cost_agent.md",
    "icinga_agent.md",
    "ocpv_agent.md",
    "security_agent.md",
]

MCP_PORTS = {
    "PLATFORM_MCP_URL": 8086,
    "GITHUB_MCP_URL": 8087,
    "ICINGA_MCP_URL": 8088,
    "COST_MCP_URL": 8089,
    "CLOUD_MCP_URL": 8090,
}


def _resolve_docker_host() -> str:
    out = subprocess.run(
        ["podman", "machine", "inspect", "podman-machine-default"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    data = json.loads(out.stdout)
    path = data[0]["ConnectionInfo"]["PodmanSocket"]["Path"]
    return f"unix://{path}"


class Adapter(CapabilityAdapter):
    def __init__(self) -> None:
        task_id = os.environ.get("TASK_ID", "").strip()
        if not task_id:
            raise RuntimeError(
                "TASK_ID environment variable is required — this adapter is shared by "
                "all 21 v4_t2_e1 projects via a symlink and has no other way to know "
                "which task it is running. Set it before invoking `cap-evolve run`."
            )
        task_dir = TASKS_DIR / f"bench-v4-{task_id}"
        if not task_dir.exists():
            raise FileNotFoundError(f"no such bench-v4 task directory: {task_dir}")
        self.task_id = task_id
        self.task_dir = task_dir
        # Read fresh on every construction (see module docstring) so a caller —
        # e.g. a test — that sets PARSEC_LIVE_PROMPTS_DIR before constructing an
        # Adapter always gets it; a module-level constant would not.
        self.live_prompts_dir = Path(
            os.environ.get(
                "PARSEC_LIVE_PROMPTS_DIR",
                str(V4N / "_run" / "parsec-live" / "config" / "prompts"),
            )
        )

    # ------------------------------------------------------------------
    # tasks() ignores the split argument: train == val == test == the one
    # task pinned via split_ids.json (see Task 2's capevolve.yaml).
    # ------------------------------------------------------------------
    def tasks(self, split: str) -> list[Task]:
        return [Task(id=self.task_id, metadata={"task_dir": str(self.task_dir)})]

    # ------------------------------------------------------------------
    # Candidate delivery: overwrite whichever *.md files the candidate
    # snapshot contains. The framework always hands apply() a FULL
    # directory snapshot (harness.py's run_dir.snapshot("seed", seed_dir)
    # copies the whole seed_capability tree as the run's first candidate),
    # so there is no partial-edit case to special-case here.
    # ------------------------------------------------------------------
    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        for name in PROMPT_FILES:
            src = Path(candidate_dir) / name
            if src.exists():
                (self.live_prompts_dir / name).write_text(
                    src.read_text(encoding="utf-8"), encoding="utf-8"
                )

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        task_dir = task.metadata["task_dir"]
        trial_dir = JOBS_ROOT / self.task_id / f"seed-{seed}" / str(int(time.time() * 1000))
        trial_dir.mkdir(parents=True, exist_ok=True)

        try:
            docker_host = _resolve_docker_host()
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, KeyError, IndexError) as exc:
            return Rollout(task_id=task.id, error=f"could not resolve docker host: {exc}")

        cfg_path = trial_dir / "harbor_config.json"
        cfg = {
            "jobs_dir": str(trial_dir),
            "agents": [{"name": "parsec_harbor_agent:ParsecAgent"}],
            "tasks": [{"path": task_dir}],
        }
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

        env = dict(os.environ)
        env["PYTHONPATH"] = "."
        env["PARSEC_URL"] = "http://127.0.0.1:8000"
        env["PARSEC_SIM_TRACE"] = str(V4N / "_run" / "logs" / "parsec-trace" / "trace.jsonl")
        env["DOCKER_HOST"] = docker_host
        for var, port in MCP_PORTS.items():
            env[var] = f"http://localhost:{port}/mcp/sse"

        log_path = trial_dir / "harbor_run.log"
        try:
            with open(log_path, "w", encoding="utf-8") as logf:
                proc = subprocess.run(
                    ["harbor", "run", "--config", str(cfg_path), "--n-concurrent", "1"],
                    cwd=str(V4N), env=env, stdout=logf, stderr=subprocess.STDOUT,
                    timeout=TRIAL_TIMEOUT_SEC,
                )
        except subprocess.TimeoutExpired:
            return Rollout(task_id=task.id, error=f"harbor run timed out after {TRIAL_TIMEOUT_SEC}s",
                           metadata={"trial_dir": str(trial_dir)})

        if proc.returncode != 0:
            return Rollout(task_id=task.id, error=f"harbor run exited {proc.returncode}",
                           metadata={"trial_dir": str(trial_dir)})

        results = parse_job_dir(trial_dir)
        if not results:
            return Rollout(task_id=task.id, error="harbor produced no parseable result",
                           metadata={"trial_dir": str(trial_dir)})
        trial_result = next(iter(results.values()))[0]

        # TrialResult (capevolve_harbor.results) has no .feedback attribute —
        # build_feedback() is the module's own accessor for a gold-safe summary.
        # Store it alongside the raw trial_result dict so score() need not
        # reconstruct a TrialResult from a plain dict to recompute it.
        feedback = build_feedback(trial_result)

        return Rollout(
            task_id=task.id,
            output=feedback,
            metadata={
                "trial_dir": str(trial_dir),
                "trial_result": trial_result.__dict__,
                "feedback": feedback,
            },
        )

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            return Score(task_id=task.id, reward=0.0, feedback=rollout.error, n=1)
        meta = rollout.metadata or {}
        tr = meta.get("trial_result") or {}
        reward = float(tr.get("reward") or 0.0)
        feedback = str(meta.get("feedback") or tr.get("feedback") or "")
        return Score(task_id=task.id, reward=reward, feedback=feedback, n=1)

    def trajectories(self, split: str, ctx=None) -> Path | None:
        candidates = sorted(glob.glob(str(JOBS_ROOT / self.task_id / "**" / "agent"), recursive=True))
        return Path(candidates[-1]) if candidates else None
