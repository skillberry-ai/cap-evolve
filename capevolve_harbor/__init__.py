"""cap-evolve <-> Harbor integration.

Generates self-contained Harbor task packages from cap-evolve tasks,
runs them via the ``harbor`` CLI, and parses results back into
cap-evolve's Rollout/Score types.

Usage pattern (from a cap-evolve adapter)::

    from capevolve_harbor import package_dataset, harbor_run, parse_job_dir

    # 1. Package cap-evolve tasks as Harbor task dirs
    dataset_dir = package_dataset(tasks, candidate_dir, tmp / "tasks", config=cfg)

    # 2. Run Harbor
    result = harbor_run(dataset_dir, agent="claude-code", model="claude-sonnet-4-6")

    # 3. Parse results
    trial_results = parse_job_dir(result.job_dir)
"""

from .tasks import package_task, package_dataset
from .run import harbor_run, find_harbor_bin, HarborRunResult
from .results import parse_job_dir, TrialResult, build_feedback

__all__ = [
    "package_task",
    "package_dataset",
    "harbor_run",
    "find_harbor_bin",
    "HarborRunResult",
    "parse_job_dir",
    "TrialResult",
    "build_feedback",
]
