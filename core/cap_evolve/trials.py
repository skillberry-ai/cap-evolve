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

import contextlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .types import Rollout, Task


def run_trials_pool(
    run_one: Callable[[Task, int], Rollout],
    tasks: list[Task],
    *,
    n_trials: int,
    base_seed: int,
    max_workers: int = 1,
    on_progress: Callable[[], None] | None = None,
) -> dict[str, list[Rollout]]:
    """Run the ``task × trial`` grid concurrently and return trial-ordered rollouts.

    ``run_one(task, seed) -> Rollout`` produces ONE rollout. Returns
    ``{task_id: [rollout_t0, ..., rollout_t{n-1}]}`` (length ``n_trials`` per task,
    trial order preserved). An exception in ``run_one`` becomes an error ``Rollout``
    for that ``(task, trial)`` so one bad trial can't sink the batch. ``max_workers``
    bounds concurrency; ``1`` runs sequentially (identical result, no threads).

    ``on_progress`` (optional), if given, is called once per completed ``(task,
    trial)`` job — in this function's own thread, never a worker thread, so it needs
    no locking. This is the harness's hook for a heartbeat during a long eval (see
    #589): without it, generating hundreds of rollouts through this pool is
    completely silent from the first job to the last.
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
    # Adapters keep the stdout JSON-contract clean by redirecting their runner's stdout to
    # stderr (e.g. tau2's run_batch). contextlib.redirect_stdout swaps the PROCESS-GLOBAL
    # sys.stdout and is NOT thread-safe: with concurrent per-call redirects, one thread's
    # exit can restore real stdout while another is still printing, leaking runner output
    # into the pure-JSON stdout. Wrap the whole pool once so real stdout is never the
    # "current" target during the threads — inner per-call redirects then only ever
    # save/restore sys.stderr, so nothing can leak.
    with contextlib.redirect_stdout(sys.stderr):
        if max_workers == 1:
            for job in jobs:
                tid, k, rollout = _one(job)
                results[tid][k] = rollout
                if on_progress is not None:
                    on_progress()
        else:
            # as_completed (not ex.map) so ``on_progress`` fires as each job ACTUALLY
            # finishes, not merely in submission order — a slow first job must not
            # block the progress signal for jobs that finished behind it.
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(_one, job) for job in jobs]
                for fut in as_completed(futures):
                    tid, k, rollout = fut.result()
                    results[tid][k] = rollout
                    if on_progress is not None:
                        on_progress()
    return results
