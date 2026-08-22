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
import shlex
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
HARBOR_EXTRA_FLAGS = shlex.split(os.environ.get("HARBOR_EXTRA_FLAGS", ""))
HARBOR_JOBS_DIR = os.environ.get("HARBOR_JOBS_DIR", "")

# ``HARBOR_LOCAL_ASIS=1`` — when set, a local dataset dir is passed to ``harbor
# run`` VERBATIM (no ``package_dataset`` repacking). Use this when the local
# dataset already ships everything Harbor needs per task — task.toml, tests/
# with a real verifier + expected.json, and any pre-built Dockerfile — and the
# default repackaging (which overwrites those with generic templates) would
# destroy semantic content. Downstream benchmarks that want to hand-author
# rich task dirs (Parsec, etc.) set this in their overrides.env.
HARBOR_LOCAL_ASIS = os.environ.get("HARBOR_LOCAL_ASIS", "").strip() in ("1", "true", "yes")

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
# Host directory holding a pre-warmed npm cache (see ci_setup.sh). Empty disables the whole
# mechanism and the agent bootstraps from the network exactly as before.
HARBOR_NPM_CACHE = os.environ.get("HARBOR_NPM_CACHE", "")
_NPM_CACHE_TARGET = "/opt/npm-cache"
HARBOR_AGENT_API_KEY = os.environ.get("HARBOR_AGENT_API_KEY", "")


def _is_registry_dataset(ds: str) -> bool:
    """True if the dataset name is a Harbor registry reference (org/name)."""
    return "/" in ds and not Path(ds).is_dir()


def _build_agent_env() -> dict[str, str]:
    """Build --ae flags for the Harbor agent from model config.

    Supports three auth modes:
    1. On-cluster vLLM (HARBOR_AGENT_BASE_URL set)
    2. Vertex AI (CLAUDE_CODE_USE_VERTEX=1)
    3. Anthropic API key (ANTHROPIC_API_KEY)
    """
    ae: dict[str, str] = {}

    if HARBOR_AGENT_BASE_URL:
        ae["ANTHROPIC_BASE_URL"] = HARBOR_AGENT_BASE_URL
        ae["ANTHROPIC_API_KEY"] = HARBOR_AGENT_API_KEY or "dummy"
        ae["ANTHROPIC_MODEL"] = HARBOR_MODEL
        ae["ANTHROPIC_DEFAULT_SONNET_MODEL"] = HARBOR_MODEL
        ae["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = HARBOR_MODEL
        ae["ANTHROPIC_DEFAULT_OPUS_MODEL"] = HARBOR_MODEL
    elif os.environ.get("CLAUDE_CODE_USE_VERTEX", "").strip() == "1":
        ae["CLAUDE_CODE_USE_VERTEX"] = "1"
        ae["CLOUD_ML_REGION"] = os.environ.get("CLOUD_ML_REGION", "global")
        ae["ANTHROPIC_VERTEX_PROJECT_ID"] = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
        ae["ANTHROPIC_MODEL"] = HARBOR_MODEL
        creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if creds:
            ae["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/.config/gcloud/application_default_credentials.json"
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            ae["ANTHROPIC_API_KEY"] = api_key

    ae.update(_npm_cache_agent_env())
    return ae


def _npm_cache_agent_env() -> dict[str, str]:
    """Point the container's npm at a pre-warmed, host-mounted cache.

    Harbor's claude-code agent bootstraps with `npm install -g @anthropic-ai/claude-code`
    INSIDE every task container. At scale that is one network install per task, and it was
    the single largest failure source in pilot run 31274531220: of 34 infra-errored tasks,
    8 exits 126/128 and NetworkConnectionErrors came straight from that npm line, plus
    CancelledErrors from rollouts that ran out of time waiting on it.

    With HARBOR_NPM_CACHE pointing at a cache ci_setup.sh has already populated on the host,
    npm resolves the tarball locally instead of hitting the registry 50-250 times.
    `prefer-offline` (not `offline`) is deliberate: cache miss falls back to the network
    rather than hard-failing, so a stale cache degrades to today's behaviour instead of
    breaking the run.
    """
    if not HARBOR_NPM_CACHE:
        return {}
    return {
        "npm_config_cache": _NPM_CACHE_TARGET,
        "npm_config_prefer_offline": "true",
        # Silence per-container audit/funding network calls too — same rationale.
        "npm_config_audit": "false",
        "npm_config_fund": "false",
    }


def _build_harbor_mounts() -> list[dict] | None:
    """Build mount specs for Harbor containers (npm cache, GCP credentials)."""
    mounts: list[dict] = []

    # Pre-warmed npm cache, so the agent bootstrap does not hit the registry once per task.
    if HARBOR_NPM_CACHE and os.path.isdir(HARBOR_NPM_CACHE):
        mounts.append({"type": "bind", "source": HARBOR_NPM_CACHE,
                       "target": _NPM_CACHE_TARGET})

    if os.environ.get("CLAUDE_CODE_USE_VERTEX", "").strip() == "1":
        creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not creds:
            home = os.path.expanduser("~")
            creds = f"{home}/.config/gcloud/application_default_credentials.json"
        if os.path.exists(creds):
            mounts.append({"type": "bind", "source": creds,
                           "target": "/app/.config/gcloud/application_default_credentials.json"})

    return mounts or None


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
        """Run the full benchmark via one ``harbor run`` invocation.

        The candidate capability files are injected into the container via
        ``package_dataset`` — each task's environment/capability/ dir contains
        the current candidate's SKILL.md, scripts, references, etc.
        """
        from capevolve_harbor import harbor_run, parse_job_dir
        from capevolve_harbor.tasks import package_dataset

        candidate_dir = Path(ctx)
        jobs_dir = Path(HARBOR_JOBS_DIR) if HARBOR_JOBS_DIR else Path(tempfile.mkdtemp(prefix="harbor_jobs_"))
        jobs_dir.mkdir(parents=True, exist_ok=True)

        agent_env = _build_agent_env()
        agent_env["CAPEVOLVE_SEED"] = str(seed)

        is_registry = _is_registry_dataset(HARBOR_DATASET)
        prefix = HARBOR_TASK_PREFIX
        if is_registry and not prefix:
            prefix = HARBOR_DATASET.split("/")[0]

        # Inject the candidate capability into the agent's context.
        # Write the candidate prompt/skill to a temp file and pass it
        # via --extra-instruction-path so Harbor appends it to the task
        # instruction — works for both registry and local datasets.
        extra_flags = list(HARBOR_EXTRA_FLAGS or [])
        mounts = _build_harbor_mounts()
        if mounts:
            extra_flags += ["--mounts-json", json.dumps(mounts)]
        instruction_file = self._write_candidate_instruction(candidate_dir)
        if instruction_file:
            extra_flags += ["--extra-instruction-path", str(instruction_file)]

        if is_registry:
            harbor_task_names = [
                f"{prefix}/{t.id}" if prefix and not t.id.startswith(prefix) else t.id
                for t in tasks
            ]
            dataset_path = None
            dataset_name = HARBOR_DATASET
        elif HARBOR_LOCAL_ASIS:
            # Point harbor at the pre-built local dataset directly — no repacking.
            # Each task dir must already contain task.toml + tests/ + environment/
            # (Harbor's TaskModel.is_valid_dir requirement). Filter to the requested IDs.
            harbor_task_names = [t.id for t in tasks]
            dataset_path = Path(HARBOR_DATASET)
            dataset_name = None
        else:
            harbor_task_names = None
            packaged_dir = Path(tempfile.mkdtemp(prefix="harbor_dataset_"))
            package_dataset(
                tasks=[{"id": t.id, "input": t.input} for t in tasks],
                candidate_dir=candidate_dir,
                output_dir=packaged_dir,
            )
            dataset_path = packaged_dir
            dataset_name = None

        result = harbor_run(
            dataset_path=dataset_path,
            dataset=dataset_name,
            agent=HARBOR_AGENT,
            model=HARBOR_MODEL,
            parallel=HARBOR_PARALLEL,
            timeout=HARBOR_TIMEOUT * len(tasks) + 300,
            extra_flags=extra_flags or None,
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

        self._cleanup_tmp_files()
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

    _instruction_tmp_files: list[Path] = []

    @classmethod
    def _write_candidate_instruction(cls, candidate_dir: Path) -> Path | None:
        """Write the candidate prompt/skill to a temp file for Harbor injection."""
        candidate_dir = Path(candidate_dir)
        for name in ("prompt.md", "SKILL.md"):
            src = candidate_dir / name
            if src.exists():
                content = src.read_text(encoding="utf-8")
                if content.strip():
                    fd, tmp_str = tempfile.mkstemp(prefix="capevolve_instruction_", suffix=".md")
                    tmp = Path(tmp_str)
                    os.close(fd)
                    tmp.write_text(content, encoding="utf-8")
                    cls._instruction_tmp_files.append(tmp)
                    return tmp
        return None

    @classmethod
    def _cleanup_tmp_files(cls) -> None:
        for f in cls._instruction_tmp_files:
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        cls._instruction_tmp_files.clear()

    @contextmanager
    def live(self, candidate_dir: Path):
        """Yield the candidate directory — skill files are read at run time."""
        yield Path(candidate_dir)

    def trajectories(self, split: str, ctx=None) -> Path | None:
        return Adapter._last_jobs_dir
