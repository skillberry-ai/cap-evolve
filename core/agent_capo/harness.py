"""Executable pipeline logic shared by the phase/algorithm skills.

The skills are the user-facing, self-describing layer; the *mechanics* they all
need — make splits once, evaluate a candidate with multi-trial honesty, run one
propose→gate step, finalize on the sealed test set — live here so they aren't
re-derived (and subtly broken) per skill. Every honesty-critical operation routes
through ``splits``/``stats``/``gate``/``rundir``.

An "optimizer" is any callable ``(workdir: Path, instructions: str) -> None`` that
edits files in ``workdir`` in place (prior agent-optimization work's model). ``optimizer_from_command``
builds one from a skill's ``run.py`` so external agents plug in the same way.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from . import gate as gate_mod
from .loop import SplitResult, aggregate_scores, select_parent
from .rundir import RunDir
from .splits import Splits, make_splits
from .types import Rollout, Score, Task

OptimizerFn = Callable[[Path, str], None]


# ---- splits ---------------------------------------------------------------

def ensure_splits(adapter, run_dir: RunDir, *, seed: int = 0, ratios=(0.5, 0.25, 0.25),
                  split_ids: dict | None = None) -> Splits:
    """Create the frozen split once (from ``adapter.tasks('all')``) or load it.

    ``split_ids`` (``{"train": [...], "val": [...], "test": [...]}``) sets the
    split explicitly — use it to pin a benchmark's official split, or to fit on
    the whole set (train==val==test==all ids; a deliberate no-holdout choice).
    Otherwise the ids from ``adapter.tasks('all')`` are partitioned by ``ratios``.
    """
    if run_dir.splits_path.exists():
        return run_dir.read_splits()
    if split_ids:
        splits = Splits(train=[str(t) for t in split_ids.get("train", [])],
                        val=[str(t) for t in split_ids.get("val", [])],
                        test=[str(t) for t in split_ids.get("test", [])], seed=seed)
        if set(splits.train) & set(splits.test) or set(splits.val) & set(splits.test):
            run_dir.log_event("splits_warning",
                              msg="test overlaps train/val (no-holdout fit) — the test "
                                  "number is NOT held out; report it as a fit metric")
    else:
        all_tasks = adapter.tasks("all")
        splits = make_splits([t.id for t in all_tasks], seed=seed, ratios=ratios)
    run_dir.write_splits(splits)
    run_dir.log_event("splits", train=len(splits.train), val=len(splits.val),
                      test=len(splits.test), seed=seed)
    return splits


def _tasks_for(adapter, run_dir: RunDir, split: str) -> list[Task]:
    """Tasks for a split, filtered by the frozen split ids."""
    splits = run_dir.read_splits()
    ids = set(splits.ids(split))
    return [t for t in adapter.tasks("all") if t.id in ids]


# ---- evaluation -----------------------------------------------------------

def evaluate_candidate(
    adapter,
    candidate_dir: Path,
    *,
    run_dir: RunDir,
    split: str,
    n_trials: int = 1,
    ks=(1, 2),
    tag: str = "cand",
) -> SplitResult:
    """Run + score a candidate on a split with multi-trial honesty.

    Writes per-rollout JSON under the run dir, returns the aggregate SplitResult.
    Scoring the **test** split flips the seal (raising on a second attempt), so the
    held-out set can only ever be scored once — that is ``finalize``'s job.
    """
    if split == "test":
        run_dir.consume_test()  # raises TestSealError on reuse

    adapter.apply(candidate_dir)  # make this candidate live
    tasks = _tasks_for(adapter, run_dir, split)
    out_dir = run_dir.rollouts / split
    out_dir.mkdir(parents=True, exist_ok=True)

    from .stats import mean, stderr
    has_batch = hasattr(adapter, "run_batch")

    # collect per-task trial rewards (+ last rollout/score) across trials
    per_task_trials: dict[str, list[float]] = {t.id: [] for t in tasks}
    per_task_feedback: dict[str, str] = {t.id: "" for t in tasks}
    task_by_id = {t.id: t for t in tasks}
    run_cost, run_tokens = 0.0, 0           # RUNNER spend, summed over rollouts
    t0 = time.time()

    for k in range(n_trials):
        if has_batch:
            rb = adapter.run_batch(tasks, candidate_dir, split)
            # accept either {task_id: Rollout} or a list parallel to `tasks`
            rollouts = rb if isinstance(rb, dict) else {t.id: r for t, r in zip(tasks, rb)}
        else:
            rollouts = {t.id: adapter.run_target(t, candidate_dir, split) for t in tasks}
        for tid, task in task_by_id.items():
            rollout = rollouts.get(tid)
            if rollout is None:
                # The batch omitted this task (an error/timeout inside the runner).
                # Record it as a failed rollout (reward 0) — do NOT serially re-run
                # it here, which would add a slow tail to every batch evaluation.
                rollout = Rollout(task_id=tid, error="omitted from batch result")
            run_cost += float(getattr(rollout, "cost_usd", 0.0) or 0.0)
            run_tokens += int(getattr(rollout, "tokens", 0) or 0)
            sc = adapter.score(task, rollout)
            per_task_trials[tid].append(sc.reward)
            per_task_feedback[tid] = sc.feedback or per_task_feedback[tid]
            (out_dir / f"{tid}__{tag}__t{k}.json").write_text(
                json.dumps({"input": task.input, "rollout": rollout.to_dict(),
                            "score": sc.to_dict()}, default=str),
                encoding="utf-8",
            )

    scores: list[Score] = []
    for tid in task_by_id:
        tr = per_task_trials[tid]
        scores.append(Score(
            task_id=tid, reward=mean(tr), feedback=per_task_feedback[tid],
            n=n_trials, stderr=stderr(tr), trial_rewards=tr,
        ))

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
    """
    import json as _json
    from .stats import mean, stderr
    vdir = run_dir.rollouts / split
    by_task: dict[str, list[float]] = {}
    feedback: dict[str, str] = {}
    if vdir.exists():
        for f in sorted(vdir.glob(f"*__{tag}__t*.json")):
            rec = _json.loads(f.read_text(encoding="utf-8"))
            sc = rec.get("score", {})
            tid = sc.get("task_id") or f.name.split("__")[0]
            by_task.setdefault(tid, []).append(float(sc.get("reward", 0.0)))
            feedback[tid] = sc.get("feedback", feedback.get(tid, ""))
    scores = [Score(task_id=t, reward=mean(r), feedback=feedback.get(t, ""),
                    n=len(r), stderr=stderr(r), trial_rewards=r) for t, r in by_task.items()]
    return aggregate_scores(split, scores, ks=ks)


# ---- baseline -------------------------------------------------------------

def baseline(adapter, seed_dir: Path, *, run_dir: RunDir, n_trials: int = 1, ks=(1, 2)) -> SplitResult:
    """Snapshot the seed capability as candidate ``seed``, score it on val, set best.

    Establishes the starting point every algorithm compares against. Assumes
    ``ensure_splits`` has been called.
    """
    run_dir.snapshot("seed", Path(seed_dir))
    run_dir.set_best("seed")
    result = evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                               split="val", n_trials=n_trials, ks=ks, tag="seed")
    (run_dir.root / "baseline.json").write_text(
        json.dumps({"val": result.to_dict(), "best_id": "seed"}, indent=2), encoding="utf-8")
    run_dir.log_event("baseline", val=result.reward, stderr=result.stderr)
    return result


# ---- optimizer plumbing ---------------------------------------------------

def optimizer_from_command(cmd_template: list[str]) -> OptimizerFn:
    """Build an OptimizerFn that shells out to a skill's run.py.

    ``cmd_template`` is a list with ``{workdir}`` and ``{prompt}`` placeholders,
    e.g. ``["python", ".../optimizers/mock/scripts/run.py", "--workdir",
    "{workdir}", "--prompt", "{prompt}"]``. The subprocess edits files in workdir.
    """
    def _run(workdir: Path, instructions: str) -> None:
        prompt_path = workdir / "INSTRUCTIONS.md"
        prompt_path.write_text(instructions, encoding="utf-8")
        cmd = [c.format(workdir=str(workdir), prompt=str(prompt_path)) for c in cmd_template]
        env = dict(os.environ)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise RuntimeError(f"optimizer failed ({proc.returncode}): {proc.stderr[:2000]}")
    return _run


# ---- one propose -> gate step ---------------------------------------------

def _augment_instructions(instructions: str, workdir: Path, run_dir: RunDir,
                          rejected, history) -> str:
    """Give the optimizer its memory + the whole process to learn from.

    Writes MEMORY.md into the workdir (rejected approaches + accepted history) and
    appends, to the prompt, the memory, a pointer to the persistent STATE.md
    scratchpad, and the run-output directory (prior candidates/rollouts/events) so
    every iteration can inspect the full process so far.
    """
    mem = ""
    if rejected is not None:
        mem += rejected.render() + "\n\n"
    if history is not None:
        mem += history.render()
    (workdir / "MEMORY.md").write_text(mem or "_no memory yet_\n", encoding="utf-8")
    if not (workdir / "STATE.md").exists():
        (workdir / "STATE.md").write_text(
            "# Optimizer scratchpad\n\nRecord your running diagnosis + plan here; it "
            "carries across iterations when this candidate is accepted.\n", encoding="utf-8")
    return (
        f"{instructions}\n\n"
        f"## Memory (read MEMORY.md in this dir)\n{mem or '_none yet_'}\n\n"
        f"## Your scratchpad\nUpdate `STATE.md` in this dir with your diagnosis and plan; "
        f"it persists across accepted iterations.\n\n"
        f"## The process so far\nThe full run output (prior candidates, rollouts, "
        f"events) is at: {run_dir.root}\n"
    )


def run_step(
    adapter,
    *,
    run_dir: RunDir,
    parent_dir: Path,
    optimizer: OptimizerFn,
    instructions: str,
    current_val: SplitResult,
    n_trials: int = 1,
    gate_kwargs: dict | None = None,
    candidate_id: str | None = None,
    no_regression: bool = False,
    rejected=None,
    history=None,
    store=None,
) -> dict:
    """Materialize parent → optimize → evaluate on val → gate → accept/reject.

    Returns a dict describing the step. On accept, the candidate is snapshotted
    and becomes the run's best.

    ``no_regression`` adds a SWE-bench-style dual gate: even if the mean improves,
    reject the candidate if it breaks any val task the parent already passed.
    """
    gate_kwargs = dict(gate_kwargs or {})
    cid = candidate_id or f"cand_{run_dir.spent.iterations + 1:04d}"
    workdir = run_dir.root / "work" / cid
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(parent_dir, workdir)

    instructions = _augment_instructions(instructions, workdir, run_dir, rejected, history)

    optimizer_error = None
    _opt_t0 = time.time()
    try:
        optimizer(workdir, instructions)  # mutates workdir in place
    except Exception as e:  # noqa: BLE001
        # A failed proposal (e.g. a transient optimizer/API error) must not abort a
        # long run — leave the workdir as the parent copy so the candidate == parent
        # and the gate simply rejects it (a wasted iteration, not a crash).
        optimizer_error = str(e)
        run_dir.log_event("optimizer_error", candidate=cid, error=optimizer_error[:500])
    optimizer_seconds = time.time() - _opt_t0
    run_dir.update_spent(optimizer_seconds=optimizer_seconds)

    cand_val = evaluate_candidate(adapter, workdir, run_dir=run_dir, split="val",
                                  n_trials=n_trials, tag=cid)
    decision = gate_mod.decide(
        current_val.reward, cand_val.reward, split="val",
        candidate_stderr=cand_val.stderr, current_stderr=current_val.stderr,
        **gate_kwargs,
    )

    accepted = decision.accept
    regressions = []
    if accepted and no_regression:
        # A regression is ANY task whose reward strictly dropped (works for graded
        # rewards too, not just binary pass/fail).
        eps = 1e-9
        parent_reward = {pt["task_id"]: pt.get("reward", 0.0) for pt in current_val.per_task}
        cand_reward = {pt["task_id"]: pt.get("reward", 0.0) for pt in cand_val.per_task}
        regressions = sorted(t for t, pr in parent_reward.items()
                             if cand_reward.get(t, 0.0) < pr - eps)
        if regressions:
            accepted = False
            decision.reason += f"; REJECTED by no-regression gate (broke {regressions})"
    if accepted:
        run_dir.snapshot(cid, workdir)
        run_dir.set_best(cid)
    run_dir.update_spent(iterations=1, accepted=accepted)
    run_dir.log_event("step", candidate=cid, accept=accepted, reason=decision.reason,
                      val=cand_val.reward, parent_val=current_val.reward,
                      optimizer_seconds=round(optimizer_seconds, 2),
                      runner_seconds=round(cand_val.seconds, 2),
                      cost_usd=cand_val.cost_usd, tokens=cand_val.tokens)

    # update optimizer memory + commit the iteration to the version store so the
    # whole process stays inspectable (git log / MEMORY.md / REJECTED.md).
    summary = f"candidate {cid} (val {cand_val.reward:.3f}, Δ {cand_val.reward - current_val.reward:+.3f})"
    if accepted:
        if history is not None:
            history.add(cid, summary, cand_val.reward)
    else:
        if rejected is not None:
            rejected.add(cid, summary, decision.reason, cand_val.reward)
    if store is not None:
        store.commit(f"iter {run_dir.spent.iterations}: "
                     f"{'ACCEPT' if accepted else 'reject'} {summary}",
                     tag=("best" if accepted else None), accepted=accepted)

    return {
        "candidate_id": cid,
        "accepted": accepted,
        "decision": decision.to_dict(),
        "candidate_val": cand_val.to_dict(),
        "parent_val": current_val.to_dict(),
        "regressions": regressions,
        "optimizer_seconds": optimizer_seconds,
        "optimizer_error": optimizer_error,
        "workdir": str(workdir),
    }


# ---- memory + version store wiring ----------------------------------------

def _init_memory_store(run_dir: RunDir, store):
    """Create the optimizer memory (rejected + accepted history) and ensure a
    version store (default git) is initialized + holds an initial 'seed' commit."""
    from .memory import History, RejectedMemory
    from .store import VersionStore
    rejected = RejectedMemory(run_dir.rejected_path)
    history = History(run_dir.history_path)
    if store is None:
        store = VersionStore(kind="git", root=run_dir.root)
    store.init()
    # Only stamp the seed commit on a FRESH run; on --resume the store already has
    # history, so re-committing would add a duplicate 'seed' and move the seed tag
    # off the real baseline.
    if not store.log():
        store.commit("seed: baseline candidate", tag="seed")
    return rejected, history, store


# ---- shared hill-climb loop (parameterized by focus) ----------------------

def _focus_instructions(current_val: SplitResult, focus_ids, label: str) -> str:
    failing = [pt for pt in current_val.per_task if pt.get("reward", 0) < 1.0]
    if focus_ids is not None:
        failing = [pt for pt in failing if pt.get("task_id") in set(focus_ids)]
    lines = [
        "# Optimize the capability",
        "",
        f"Focus: {label}. Current val reward: {current_val.reward:.3f}. Edit the "
        "capability files in this working directory to raise it.",
        "",
        "## Failing tasks (learn from their feedback):",
    ]
    for pt in failing[:10]:
        lines.append(f"- {pt.get('task_id')}: {str(pt.get('feedback',''))[:300]}")
    if not failing:
        lines.append("- (none failing in focus; seek robustness gains)")
    return "\n".join(lines)


def hill_climb_loop(
    adapter,
    *,
    run_dir: RunDir,
    optimizer: OptimizerFn,
    current_val: SplitResult,
    focus: str = "all",
    max_iterations: int = 10,
    n_trials: int = 1,
    gate_kwargs: dict | None = None,
    algorithm: str = "hill_climb",
    no_regression: bool = False,
    store=None,
) -> dict:
    """The loop shared by all-at-once / cyclic / hardest-first.

    They differ only in the *focus schedule* — which tasks each iteration's
    reflection emphasizes — and (for hardest-first) the order. Parent is always
    the current best (global hill-climb). gepa-reflective overrides parent
    selection separately.
    """
    gate_kwargs = dict(gate_kwargs or {})
    rejected, history, store = _init_memory_store(run_dir, store)

    # establish a focus order over the train tasks when needed
    train_ids = run_dir.read_splits().train
    order = list(train_ids)
    if focus == "hardest-first":
        seed_dir = run_dir.candidate_dir("seed")
        train_res = evaluate_candidate(adapter, seed_dir, run_dir=run_dir, split="train",
                                       n_trials=n_trials, tag="seed_train")
        score_by = {pt["task_id"]: pt["reward"] for pt in train_res.per_task}
        order.sort(key=lambda t: score_by.get(t, 0.0))  # hardest (lowest) first

    steps = []
    for i in range(max_iterations):
        exhausted, why = run_dir.budget_exhausted()
        if exhausted:
            break
        if focus == "all":
            focus_ids, label = None, "whole train set"
        elif focus in ("cyclic", "hardest-first"):
            focus_ids = [order[i % len(order)]] if order else None
            label = f"task {focus_ids[0]}" if focus_ids else "train"
        else:
            focus_ids, label = None, focus
        instructions = _focus_instructions(current_val, focus_ids, label)
        step = run_step(
            adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir(run_dir.best_id),
            optimizer=optimizer, instructions=instructions, current_val=current_val,
            n_trials=n_trials, gate_kwargs=gate_kwargs, no_regression=no_regression,
            rejected=rejected, history=history, store=store,
        )
        steps.append(step)
        if step["accepted"]:
            current_val = SplitResult.from_dict(step["candidate_val"])

    _, why = run_dir.budget_exhausted()
    return {
        "algorithm": algorithm,
        "best_id": run_dir.best_id,
        "best_val": current_val.reward,
        "iterations": len(steps),
        "accepts": sum(1 for s in steps if s["accepted"]),
        "stop_reason": why or "max_iterations",
        "steps": steps,
    }


# ---- GEPA-style reflective Pareto loop ------------------------------------

def pareto_loop(
    adapter,
    *,
    run_dir: RunDir,
    optimizer: OptimizerFn,
    seed_val: SplitResult,
    max_iterations: int = 10,
    n_trials: int = 1,
    gate_kwargs: dict | None = None,
    no_regression: bool = False,
    store=None,
) -> dict:
    """GEPA-style reflective evolution with a per-task Pareto frontier.

    Differs from the hill-climb: instead of always extending the single global
    best, it selects a parent from the Pareto frontier over per-task val scores
    (keeping specialists that the aggregate mean would hide — gepa's insight), and
    the proposal prompt is a reflective dataset over the parent's failing tasks
    (gepa's Actionable Side Information). Acceptance still uses the val
    significance gate; test stays sealed.
    """
    gate_kwargs = dict(gate_kwargs or {})
    rejected, history, store = _init_memory_store(run_dir, store)
    # frontier entries: {id, dir, val(SplitResult), per_task}
    frontier = [{"id": "seed", "dir": str(run_dir.candidate_dir("seed")),
                 "val": seed_val.reward, "per_task": seed_val.per_task,
                 "result": seed_val}]
    steps = []

    for _ in range(max_iterations):
        exhausted, why = run_dir.budget_exhausted()
        if exhausted:
            break
        parent = select_parent(frontier, strategy="pareto")
        parent_result = parent["result"]
        instructions = _reflective_instructions(parent_result)
        step = run_step(
            adapter, run_dir=run_dir, parent_dir=Path(parent["dir"]),
            optimizer=optimizer, instructions=instructions, current_val=parent_result,
            n_trials=n_trials, gate_kwargs=gate_kwargs, no_regression=no_regression,
            rejected=rejected, history=history, store=store,
        )
        steps.append(step)
        if step["accepted"]:
            res = SplitResult.from_dict(step["candidate_val"])
            cid = step["candidate_id"]
            frontier.append({"id": cid, "dir": str(run_dir.candidate_dir(cid)),
                             "val": res.reward, "per_task": res.per_task, "result": res})

    best = max(frontier, key=lambda c: c["val"])
    run_dir.set_best(best["id"])
    _, why = run_dir.budget_exhausted()
    return {
        "algorithm": "gepa-reflective",
        "best_id": best["id"],
        "best_val": best["val"],
        "frontier_size": len(frontier),
        "iterations": len(steps),
        "accepts": sum(1 for s in steps if s["accepted"]),
        "stop_reason": why or "max_iterations",
        "steps": steps,
    }


def _reflective_instructions(parent_result: SplitResult) -> str:
    failing = [pt for pt in parent_result.per_task if pt.get("reward", 0) < 1.0]
    lines = [
        "# Reflective optimization (GEPA-style)",
        "",
        "Below is a reflective dataset of the parent candidate's FAILING val tasks "
        "(inputs, the agent's output, and feedback). Diagnose the common root cause "
        "and edit the capability to fix the general pattern — not one task.",
        "",
    ]
    for pt in failing[:10]:
        lines.append(f"## task {pt.get('task_id')}")
        lines.append(f"- Feedback: {str(pt.get('feedback',''))[:500]}")
    if not failing:
        lines.append("(parent passes all sampled val tasks; pursue robustness.)")
    return "\n".join(lines)


# ---- finalize -------------------------------------------------------------

def finalize(adapter, *, run_dir: RunDir, best_dir: Path, n_trials: int = 1, ks=(1, 2)) -> dict:
    """Score the best candidate on the SEALED test split exactly once."""
    result = evaluate_candidate(adapter, best_dir, run_dir=run_dir, split="test",
                                n_trials=n_trials, ks=ks, tag="FINAL")
    payload = {"test": result.to_dict(), "best_id": run_dir.best_id}
    (run_dir.root / "final.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    run_dir.log_event("finalize", test_reward=result.reward, best_id=run_dir.best_id)
    return payload
