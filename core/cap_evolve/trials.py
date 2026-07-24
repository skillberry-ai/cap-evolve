"""Concurrent multi-trial helper for adapters.

The harness (``harness._run_and_score``) has a fast path: if an adapter exposes
``run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id: [rollout_t0, ...]}``
it asks for the whole ``task × trial`` grid in one call instead of looping trials
sequentially. This helper builds that return value by running each ``(task, trial)``
rollout through the adapter's existing per-rollout function, concurrently, bounded
by ``max_workers``.

Seed contract (see ``adapter.py``): trial ``k`` runs with ``seed = base_seed + k`` so
distinct trials are independent draws (honest pass^k + significance gate). Scoring is
NOT done here — the harness scores each returned rollout, so this only parallelizes
rollout *generation*.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .types import Rollout, Task


def run_trials_pool(
    run_one: Callable[[Task, int], Rollout],
    tasks: list[Task],
    *,
    n_trials: int,
    base_seed: int,
    max_workers: int = 1,
) -> dict[str, list[Rollout]]:
    """Run the ``task × trial`` grid concurrently and return trial-ordered rollouts.

    ``run_one(task, seed) -> Rollout`` produces ONE rollout. Returns
    ``{task_id: [rollout_t0, ..., rollout_t{n-1}]}`` (length ``n_trials`` per task,
    trial order preserved). An exception in ``run_one`` becomes an error ``Rollout``
    for that ``(task, trial)`` so one bad trial can't sink the batch. ``max_workers``
    bounds concurrency; ``1`` runs sequentially (identical result, no threads).
    """
    n_trials = max(0, int(n_trials))
    max_workers = max(1, int(max_workers))
    results: dict[str, list[Rollout]] = {t.id: [None] * n_trials for t in tasks}  # type: ignore[list-item]
    jobs = [(t, k) for t in tasks for k in range(n_trials)]

    def _one(job):
        task, k = job
        try:
            return task.id, k, run_one(task, base_seed + k)
        except Exception as e:  # infra error, not a scored failure
            return task.id, k, Rollout(task_id=task.id, error=f"trial {k} raised: {e}")

    if not jobs:
        return results
    if max_workers == 1:
        for job in jobs:
            tid, k, rollout = _one(job)
            results[tid][k] = rollout
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for tid, k, rollout in ex.map(_one, jobs):
                results[tid][k] = rollout
    return results
