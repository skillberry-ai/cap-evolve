"""Candidate evaluation — the per-task rollout loop and its honest aggregation.

Split out of ``harness.py`` (#115). This module owns the ONE path by which a candidate
becomes a number: materialize it live, run every task (optionally multi-trial), score
each rollout, persist them, aggregate with variance, and verify the protected paths on
both sides of the eval. ``split_result_from_rollouts`` is the read-back of that same
record, and ``_paired_deltas`` the per-task pairing the gate consumes.

Kept deliberately free of prompt/handover/optimizer concerns so the honesty-critical
scoring path can be read on its own.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

from . import protect as protect_mod
from .loop import SplitResult, aggregate_scores
from .rundir import RunDir
from .types import Rollout, Score, Task

def _tasks_for(adapter, run_dir: RunDir, split: str) -> list[Task]:
    """Tasks for a split, filtered by the frozen split ids."""
    splits = run_dir.read_splits()
    ids = set(splits.ids(split))
    return [t for t in adapter.tasks("all") if t.id in ids]


@contextlib.contextmanager
def _live(adapter, candidate_dir: Path):
    """Enter the adapter's ``live()`` context, with a default for older adapters.

    New adapters (subclassing ``CapabilityAdapter``) get ``live`` for free. An
    adapter that predates the contract (a bare object defining only the abstract
    methods + ``apply``) won't have ``live``; we synthesize the same default here —
    call ``apply(candidate_dir)`` on enter, yield ``candidate_dir`` as ``ctx`` — so
    such adapters keep working without change. If it has neither, we just yield the
    dir (a pure-file adapter the runner reads directly).
    """
    live = getattr(adapter, "live", None)
    if callable(live):
        with live(candidate_dir) as ctx:
            yield ctx
        return
    apply = getattr(adapter, "apply", None)
    if callable(apply):
        apply(candidate_dir)
    yield candidate_dir


# ---- evaluation -----------------------------------------------------------

def _aggregate_metrics(per_trial_metrics: list, reduced_reward: float) -> list:
    """Reduce per-trial metric catalogs into one display catalog for the reduced Score.

    Secondary metrics are averaged across the trials that report them; the primary
    metric's value is pinned to ``reduced_reward`` so it stays consistent with the
    gate scalar (and satisfies Score's primary-value==reward invariant). Metric
    identity is by ``name``; ``primary``/``direction`` come from the first trial that
    names the metric. Returns [] when no trial reported any metric.
    """
    from .stats import mean as _mean
    order: list[str] = []
    vals: dict[str, list[float]] = {}
    meta: dict[str, dict] = {}
    for cat in per_trial_metrics or []:
        for m in cat or []:
            name = m.get("name")
            if name is None:
                continue
            if name not in vals:
                order.append(name)
                vals[name] = []
                meta[name] = {"primary": bool(m.get("primary")), "direction": m.get("direction")}
            vals[name].append(float(m.get("value", 0.0)))
    out = []
    for name in order:
        value = reduced_reward if meta[name]["primary"] else _mean(vals[name])
        out.append({"name": name, "value": value,
                    "primary": meta[name]["primary"], "direction": meta[name]["direction"]})
    return out


def evaluate_candidate(
    adapter,
    candidate_dir: Path,
    *,
    run_dir: RunDir,
    split: str,
    n_trials: int = 1,
    ks=(1, 2),
    tag: str = "cand",
    base_seed: int | None = None,
) -> SplitResult:
    """Run + score a candidate on a split with multi-trial honesty.

    Writes per-rollout JSON under the run dir, returns the aggregate SplitResult.

    Per-trial seeds (W1): trial ``k`` is run with ``seed = base_seed + k`` so distinct
    trials are independent draws (real variance ⇒ honest pass^k + significance gate).
    ``base_seed`` defaults to the frozen splits seed; the runner is responsible for
    forwarding ``seed`` to any stochastic component (see the adapter contract).

    Seal-on-success (W1): scoring the **test** split *reserves* the seal up front
    (raising on reuse) but only *commits* (burns) it once the test SplitResult has
    been computed and written — a crash mid-scoring leaves the seal unused so a
    retry can still score test exactly once. That is ``finalize``'s job.
    """
    # Protected-paths tamper guard (#142). This is THE chokepoint every evaluation
    # goes through — baseline, each iteration's val eval, and finalize — so the guard
    # is on the path every run takes rather than an opt-in extra. It raises
    # ``TamperError`` BEFORE any scoring, snapshot, ``set_best`` or ``commit_test``,
    # so a candidate produced alongside an edited scorer can neither advance nor seal.
    protect_mod.verify(run_dir, context=f"{split} eval of {tag}")

    if split == "test":
        run_dir.reserve_test()  # raises TestSealError on reuse; does NOT burn the seal yet

    if base_seed is None:
        # Default the per-trial base to the run's frozen splits seed so the whole
        # run is reproducible from one number.
        try:
            base_seed = int(run_dir.read_splits().seed)
        except Exception:  # noqa: BLE001
            base_seed = 0

    tasks = _tasks_for(adapter, run_dir, split)
    out_dir = run_dir.rollouts / split
    out_dir.mkdir(parents=True, exist_ok=True)

    from .stats import mean, stderr
    has_batch = hasattr(adapter, "run_batch")
    has_run_trials = hasattr(adapter, "run_trials")
    has_score_batch = hasattr(adapter, "score_batch")

    # collect per-task trial rewards (+ last rollout/score) across trials
    per_task_trials: dict[str, list[float]] = {t.id: [] for t in tasks}
    per_task_feedback: dict[str, str] = {t.id: "" for t in tasks}
    per_task_metrics: dict[str, list] = {t.id: [] for t in tasks}  # per-trial metric catalogs
    per_task_errored: dict[str, bool] = {t.id: False for t in tasks}  # any trial an infra error?
    per_task_errored_trials: dict[str, int] = {t.id: 0 for t in tasks}  # how many trials errored
    task_by_id = {t.id: t for t in tasks}
    run_acc = {"cost": 0.0, "tokens": 0}    # RUNNER spend, summed over rollouts (mutable for closure)
    t0 = time.time()

    def _persist_trial(k: int, rollouts_for_k: dict) -> None:
        """Score + persist one trial's rollouts. The single source of truth for
        per-trial scoring/persistence/accumulation — called identically by the
        per-trial loop and the adapter.run_trials batch branch, so pass^k/SE and the
        on-disk t{k}.json files are byte-for-byte equivalent regardless of path.

        If the adapter exposes ``score_batch(tasks, rollouts) -> {task_id: Score}``,
        the whole trial is scored in ONE call (e.g. one Docker harness invocation for
        swebench) instead of one ``adapter.score()`` call per task. Any task id the
        batch omits falls back to a single ``adapter.score()`` call, so a partial
        implementation can never silently drop a score."""
        filled = {
            tid: (rollouts_for_k.get(tid) or Rollout(task_id=tid, error="omitted from batch result"))
            for tid in task_by_id
        }
        if has_score_batch:
            sb = adapter.score_batch(list(task_by_id.values()), filled) or {}
            scores_by_id = sb if isinstance(sb, dict) else {t.id: s for t, s in zip(task_by_id.values(), sb)}
        else:
            scores_by_id = {}

        for tid, task in task_by_id.items():
            # A trial may have omitted this task (an error/timeout inside the runner) —
            # `filled` already turned that into a failed rollout above. Do NOT serially
            # re-run it here, which would add a slow tail to every batch evaluation.
            rollout = filled[tid]
            if getattr(rollout, "error", None):
                per_task_errored[tid] = True
                per_task_errored_trials[tid] += 1
            run_acc["cost"] += float(getattr(rollout, "cost_usd", 0.0) or 0.0)
            run_acc["tokens"] += int(getattr(rollout, "tokens", 0) or 0)
            sc = scores_by_id.get(tid)
            if sc is None:  # not in has_score_batch mode, or the batch omitted this id
                sc = adapter.score(task, rollout)
            per_task_trials[tid].append(sc.reward)
            per_task_feedback[tid] = sc.feedback or per_task_feedback[tid]
            per_task_metrics[tid].append(sc.metrics)
            (out_dir / f"{tid}__{tag}__t{k}.json").write_text(
                json.dumps({"input": task.input, "rollout": rollout.to_dict(),
                            "score": sc.to_dict()}, default=str),
                encoding="utf-8",
            )

    # ``live()`` makes the candidate the one the target uses for this evaluation and
    # yields the ``ctx`` the runner consumes (default ctx == candidate_dir). Using a
    # context manager (instead of a bare global ``apply``) means the live state is
    # scoped + torn down per evaluation, which is what lets independent candidates be
    # evaluated without clobbering a single shared global slot.
    with _live(adapter, candidate_dir) as ctx:
        if has_run_trials:
            # Adapter-owned fast path: ask for ALL trials in one batch
            # ({task_id: [rollout_t0, rollout_t1, ...]}, trial-ordered), then run the
            # SAME per-trial persistence/scoring body for each k. Tolerate missing
            # trial entries (short/absent lists) as omitted rollouts.
            rollouts_by_task = adapter.run_trials(tasks, ctx, n_trials=n_trials, base_seed=base_seed)
            rollouts_by_task = rollouts_by_task or {}
            for k in range(n_trials):
                rollouts_for_k: dict = {}
                for tid in task_by_id:
                    trials = rollouts_by_task.get(tid) or []
                    rollouts_for_k[tid] = (trials[k] if k < len(trials)
                                           else Rollout(task_id=tid, error="omitted"))
                _persist_trial(k, rollouts_for_k)
        else:
            for k in range(n_trials):
                seed = base_seed + k
                if has_batch:
                    rb = adapter.run_batch(tasks, ctx, seed=seed)
                    # accept either {task_id: Rollout} or a list parallel to `tasks`
                    rollouts = rb if isinstance(rb, dict) else {t.id: r for t, r in zip(tasks, rb)}
                else:
                    rollouts = {t.id: adapter.run_target(t, ctx, seed=seed) for t in tasks}
                _persist_trial(k, rollouts)

    run_cost, run_tokens = run_acc["cost"], run_acc["tokens"]

    scores: list[Score] = []
    for tid in task_by_id:
        tr = per_task_trials[tid]
        # ``raw.errored`` carries the structured infra signal (rollout.error was set
        # on some trial) into the per-task record, so the focus builder can classify
        # uncontrollable failures without substring-matching feedback prose.
        scores.append(Score(
            task_id=tid, reward=mean(tr), feedback=per_task_feedback[tid],
            n=n_trials, stderr=stderr(tr), trial_rewards=tr,
            raw={"errored": per_task_errored[tid],
                 "errored_trials": per_task_errored_trials[tid],
                 "n_trials": n_trials},
            metrics=_aggregate_metrics(per_task_metrics[tid], mean(tr)),
        ))

    # POST-scoring tamper guard (#142 step 3). The pre-check above proves the grader
    # was clean when scoring STARTED; on its own that is a TOCTOU fence with the whole
    # scoring window open behind it. ``optimizer_from_command`` uses ``subprocess.run``,
    # which waits only on the direct child — a ``Popen(start_new_session=True)``
    # grandchild outlives it and can rewrite ground truth WHILE ``run_target`` and
    # ``score`` read it. Re-verifying here, before ``aggregate_scores`` produces the
    # number and before any caller can ``set_best`` / ``commit_test``, means the
    # manifest is checked against the state the scorer actually observed: the score is
    # discarded rather than recorded, for val and for the sealed test alike.
    #
    # ponytail: bracketing, not locking. The residual window is the gap between the
    # last ``score()`` read and this hash — a writer that lands inside it and is
    # reverted before the hash still wins. Closing that needs the scorer to hash the
    # bytes it reads (per-read verification), which is a much bigger change; the honest
    # claim is a bracket, and HONEST_EVAL.md states it as one.
    protect_mod.verify(run_dir, context=f"post-{split} eval of {tag}")

    elapsed = time.time() - t0
    run_dir.update_spent(metric_calls=len(tasks) * n_trials, usd=run_cost,
                         runner_tokens=run_tokens, runner_seconds=elapsed)
    result = aggregate_scores(split, scores, ks=ks)
    result.cost_usd, result.tokens, result.seconds = run_cost, run_tokens, elapsed
    run_dir.log_event("evaluate", split=split, tag=tag, reward=result.reward,
                      stderr=result.stderr, cost_usd=run_cost, tokens=run_tokens, seconds=round(elapsed, 2))
    return result


def split_result_from_rollouts(run_dir: RunDir, tag: str, split: str = "val", ks=(1, 2)) -> SplitResult:
    """Reconstruct a candidate's SplitResult from its persisted rollouts.

    Used to RESUME a run from the current best candidate (its val score is read
    back from disk) without re-scoring it.

    Deliberately NOT tamper-guarded (#142): it re-reads rollouts already persisted and
    already verified by the ``evaluate_candidate`` that produced them, and produces no
    new score. Verifying here would only re-check the manifest at an arbitrary later
    moment and could fail a resume for a change that post-dates the number being read.
    """
    import json as _json
    from .stats import mean, stderr
    vdir = run_dir.rollouts / split
    by_task: dict[str, list[float]] = {}
    feedback: dict[str, str] = {}
    raw: dict[str, dict] = {}
    metrics_by_task: dict[str, list] = {}
    if vdir.exists():
        for f in sorted(vdir.glob(f"*__{tag}__t*.json")):
            rec = _json.loads(f.read_text(encoding="utf-8"))
            sc = rec.get("score", {})
            tid = sc.get("task_id") or f.name.split("__")[0]
            by_task.setdefault(tid, []).append(float(sc.get("reward", 0.0)))
            feedback[tid] = sc.get("feedback", feedback.get(tid, ""))
            metrics_by_task.setdefault(tid, []).append(sc.get("metrics") or [])
            # carry the structured infra flag + trial counts forward across resume.
            # Each rollout file is one trial, so count an errored trial here and tally
            # the total trials seen — letting _is_infra_ignore reconstruct the
            # majority-errored condition from disk.
            r0 = raw.setdefault(tid, {})
            r0["n_trials"] = int(r0.get("n_trials", 0)) + 1
            if (sc.get("raw") or {}).get("errored"):
                r0["errored"] = True
                r0["errored_trials"] = int(r0.get("errored_trials", 0)) + 1
    scores = [Score(task_id=t, reward=mean(r), feedback=feedback.get(t, ""),
                    n=len(r), stderr=stderr(r), trial_rewards=r, raw=raw.get(t, {}),
                    metrics=_aggregate_metrics(metrics_by_task.get(t, []), mean(r)))
              for t, r in by_task.items()]
    return aggregate_scores(split, scores, ks=ks)


# ---- one propose -> gate step ---------------------------------------------

def _paired_deltas(current_val: SplitResult, cand_val: SplitResult) -> list | None:
    """Aligned per-task ``cand_reward[t] - curr_reward[t]`` over shared val tasks.

    Returns ``None`` if either side lacks per-task data or they share no task ids
    (so the caller falls back to the unpaired significance test). Tasks present in
    only one side are dropped — a paired test needs both halves of the pair.
    """
    cur = {pt.get("task_id"): pt.get("reward", 0.0) for pt in (current_val.per_task or [])}
    cand = {pt.get("task_id"): pt.get("reward", 0.0) for pt in (cand_val.per_task or [])}
    shared = [t for t in cand if t in cur]
    if not shared:
        return None
    return [float(cand[t]) - float(cur[t]) for t in sorted(shared)]
