"""Harbor adapter template — optimize agent capabilities via Harbor benchmarks.

cap-evolve optimizes the skill; Harbor executes the benchmark in sandboxed
containers (Docker, OpenShift, or cloud). Each evaluation iteration invokes
one ``harbor run`` for the full task set.

SETUP:
  1. Install Harbor:  uv tool install harbor
  2. Docker/Podman running (local) or ``oc login`` (OpenShift)
  3. Copy this directory to .capevolve/project/adapters/
  4. Set env vars:
       HARBOR_DATASET=swe-bench/swe-bench-verified    # registry or local path
       HARBOR_AGENT=claude-code
       HARBOR_MODEL=claude-sonnet-4-6
       ANTHROPIC_API_KEY=sk-ant-...
       # For OpenShift with on-cluster vLLM:
       HARBOR_EXTRA_FLAGS=-e openshift
       HARBOR_AGENT_BASE_URL=http://vllm-svc.ns.svc:8000
  5. Run: cap-evolve check && cap-evolve run

HOW IT WORKS:
  - tasks()      → task IDs from HARBOR_TASK_IDS or auto-detected
  - run_batch()  → one ``harbor run`` for the full evaluation, parses job results
  - score()      → reads reward from Harbor's verifier output
  - live()       → yields the candidate dir (skill files read at run time)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HARBOR_DATASET = os.environ.get("HARBOR_DATASET", "")
HARBOR_AGENT = os.environ.get("HARBOR_AGENT", "claude-code")
HARBOR_MODEL = os.environ.get("HARBOR_MODEL", "")
HARBOR_PARALLEL = int(os.environ.get("HARBOR_PARALLEL", "4"))
HARBOR_TIMEOUT = int(os.environ.get("HARBOR_TIMEOUT", "1800"))
import shlex as _shlex
HARBOR_EXTRA_FLAGS = _shlex.split(os.environ.get("HARBOR_EXTRA_FLAGS", ""))
HARBOR_JOBS_DIR = os.environ.get("HARBOR_JOBS_DIR", "")

# Task IDs to include (comma-separated, without dataset prefix).
# e.g. "astropy__astropy-12907,django__django-11099"
HARBOR_TASK_IDS = [
    s.strip() for s in os.environ.get("HARBOR_TASK_IDS", "").split(",") if s.strip()
]

# Harbor prefixes task names with the dataset org — e.g. "swe-bench/astropy__astropy-12907".
# Set this to the prefix Harbor uses so the adapter can map IDs correctly.
HARBOR_TASK_PREFIX = os.environ.get("HARBOR_TASK_PREFIX", "")

# Agent env vars for model endpoint (on-cluster vLLM or API gateway)
HARBOR_AGENT_BASE_URL = os.environ.get("HARBOR_AGENT_BASE_URL", "")
HARBOR_AGENT_API_KEY = os.environ.get("HARBOR_AGENT_API_KEY", "")


def _is_registry_dataset(ds: str) -> bool:
    """True if the dataset name is a Harbor registry reference (org/name)."""
    return "/" in ds and not Path(ds).is_dir()


def _build_agent_env(candidate_dir: Path) -> dict[str, str]:
    """Build --ae flags for the Harbor agent from config + candidate skill."""
    ae: dict[str, str] = {}

    if HARBOR_AGENT_BASE_URL:
        ae["ANTHROPIC_BASE_URL"] = HARBOR_AGENT_BASE_URL
        ae["ANTHROPIC_API_KEY"] = HARBOR_AGENT_API_KEY or "dummy"
        ae["ANTHROPIC_MODEL"] = HARBOR_MODEL
        ae["ANTHROPIC_DEFAULT_SONNET_MODEL"] = HARBOR_MODEL
        ae["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = HARBOR_MODEL
        ae["ANTHROPIC_DEFAULT_OPUS_MODEL"] = HARBOR_MODEL

    # Inject the candidate skill content so the agent can use it
    skill_md = candidate_dir / "SKILL.md"
    prompt_md = candidate_dir / "prompt.md"
    if skill_md.exists():
        ae["CAPEVOLVE_SKILL_CONTENT"] = skill_md.read_text(encoding="utf-8")[:8000]
    elif prompt_md.exists():
        ae["CAPEVOLVE_PROMPT_CONTENT"] = prompt_md.read_text(encoding="utf-8")[:8000]

    return ae


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class Adapter(CapabilityAdapter):

    _last_jobs_dir: Path | None = None

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return tasks from config or auto-detect from the dataset."""
        if HARBOR_TASK_IDS:
            return [
                Task(id=tid, input="", metadata={"source": "HARBOR_TASK_IDS"})
                for tid in HARBOR_TASK_IDS
            ]

        if HARBOR_DATASET and not _is_registry_dataset(HARBOR_DATASET):
            return self._tasks_from_local(HARBOR_DATASET)

        if not HARBOR_DATASET:
            raise ValueError("HARBOR_DATASET env var is required.")

        # Registry dataset: task IDs must be specified via HARBOR_TASK_IDS
        raise ValueError(
            f"HARBOR_DATASET={HARBOR_DATASET} is a registry dataset. "
            "Set HARBOR_TASK_IDS to a comma-separated list of task IDs "
            "(e.g. swe-bench/astropy__astropy-12907,swe-bench/django__django-11099)."
        )

    def _tasks_from_local(self, dataset_path: str) -> list[Task]:
        """Load tasks from a local Harbor dataset directory."""
        dpath = Path(dataset_path)
        tasks = []
        for entry in sorted(dpath.iterdir()):
            if entry.is_dir() and (entry / "task.toml").exists():
                tasks.append(Task(
                    id=entry.name,
                    input=(entry / "instruction.md").read_text(encoding="utf-8")
                    if (entry / "instruction.md").exists() else "",
                ))
        if not tasks:
            raise ValueError(f"No Harbor tasks found in {dataset_path}.")
        return tasks

    # ---- running ---------------------------------------------------------

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run the full benchmark via one ``harbor run`` invocation."""
        from capevolve_harbor import harbor_run, parse_job_dir

        candidate_dir = Path(ctx)
        jobs_dir = Path(HARBOR_JOBS_DIR) if HARBOR_JOBS_DIR else Path(tempfile.mkdtemp(prefix="harbor_jobs_"))
        jobs_dir.mkdir(parents=True, exist_ok=True)

        agent_env = _build_agent_env(candidate_dir)

        is_registry = _is_registry_dataset(HARBOR_DATASET)
        prefix = HARBOR_TASK_PREFIX
        if is_registry and not prefix:
            prefix = HARBOR_DATASET.split("/")[0]

        harbor_task_names = [
            f"{prefix}/{t.id}" if prefix and not t.id.startswith(prefix) else t.id
            for t in tasks
        ] if is_registry else None

        result = harbor_run(
            dataset_path=None if is_registry else Path(HARBOR_DATASET),
            dataset=HARBOR_DATASET if is_registry else None,
            agent=HARBOR_AGENT,
            model=HARBOR_MODEL,
            parallel=HARBOR_PARALLEL,
            timeout=HARBOR_TIMEOUT * len(tasks) + 300,
            extra_flags=HARBOR_EXTRA_FLAGS or None,
            jobs_dir=jobs_dir,
            include_tasks=harbor_task_names,
            agent_env=agent_env or None,
        )

        Adapter._last_jobs_dir = result.job_dir
        rollouts: dict[str, Rollout] = {}

        if result.error and not result.job_dir:
            for t in tasks:
                rollouts[t.id] = Rollout(
                    task_id=t.id,
                    error=f"Harbor run failed: {result.error}",
                )
            return rollouts

        if result.job_dir:
            trial_results = parse_job_dir(result.job_dir)

            for t in tasks:
                trials = trial_results.get(t.id, [])
                if not trials:
                    prefixed = f"{prefix}/{t.id}" if prefix else t.id
                    trials = trial_results.get(prefixed, [])
                if not trials:
                    # Harbor trial dirs use __ for / and append a short hash
                    for key in trial_results:
                        if t.id in key or t.id.replace("/", "__") in key:
                            trials = trial_results[key]
                            break

                if trials:
                    tr = trials[0]
                    rollouts[t.id] = Rollout(
                        task_id=t.id,
                        output=tr.trajectory,
                        trace=tr.trajectory,
                        cost_usd=tr.cost_usd,
                        tokens=tr.tokens,
                        error=tr.error,
                        metadata={
                            "harbor_reward": tr.reward,
                            "reward_json": tr.reward_json,
                            "verifier_stdout": tr.verifier_stdout,
                            "verifier_stderr": tr.verifier_stderr,
                        },
                    )
                else:
                    rollouts[t.id] = Rollout(
                        task_id=t.id,
                        error=f"No Harbor trial result found for task {t.id}",
                    )

        for t in tasks:
            if t.id not in rollouts:
                rollouts[t.id] = Rollout(task_id=t.id, error="No rollout produced")

        return rollouts

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        batch = self.run_batch([task], ctx, seed=seed)
        return batch.get(task.id, Rollout(task_id=task.id, error="no rollout"))

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int) -> dict:
        """Run N trials — each is a full harbor run."""
        all_rollouts: dict[str, list[Rollout]] = {t.id: [] for t in tasks}
        for k in range(n_trials):
            batch = self.run_batch(tasks, ctx, seed=base_seed + k)
            for t in tasks:
                all_rollouts[t.id].append(
                    batch.get(t.id, Rollout(task_id=t.id, error="omitted"))
                )
        return all_rollouts

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        from capevolve_harbor.results import build_feedback, TrialResult

        meta = rollout.metadata or {}

        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=f"Rollout did not complete ({rollout.error}). "
                "This may be an infrastructure issue, not an agent failure.",
            )

        reward = float(meta.get("harbor_reward", 0.0) or 0.0)
        tr = TrialResult(
            task_id=task.id,
            reward=reward,
            reward_json=meta.get("reward_json", {}),
            verifier_stdout=meta.get("verifier_stdout", ""),
            verifier_stderr=meta.get("verifier_stderr", ""),
        )
        return Score(task_id=task.id, reward=reward, feedback=build_feedback(tr))

    # ---- candidate lifecycle ---------------------------------------------

    @contextmanager
    def live(self, candidate_dir: Path):
        """Yield the candidate directory — skill files are read at run time."""
        yield Path(candidate_dir)

    def trajectories(self, split: str, ctx=None) -> Path | None:
        return Adapter._last_jobs_dir
