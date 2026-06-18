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

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from . import gate as gate_mod
from .loop import SplitResult, aggregate_scores
from .rundir import RunDir, _atomic_write
from .splits import Splits, make_splits
from .types import Rollout, Score, Task

# An optimizer mutates ``workdir`` in place. It MAY return a dict reporting its own
# cost, e.g. ``{"cost_usd": 0.42, "tokens": 1234}`` (or ``None`` when unknown) so the
# loop can count optimizer spend against ``max_usd``. Older optimizers returning
# ``None`` keep working — cost simply stays unmeasured for them.
OptimizerFn = Callable[[Path, str], "dict | None"]


def _parse_optimizer_cost(stdout: str) -> dict | None:
    """Pull ``{"cost_usd","tokens"}`` from a ``run-optimizer`` stdout payload.

    ``run-optimizer`` prints a single JSON object whose ``cost`` field is
    ``{"total_cost_usd": <float|None>, "tokens": <int|None>}`` (only when invoked
    with ``--json`` against a CLI that emits structured output). We read the last
    JSON line that carries a ``cost`` block. Returns ``None`` when no cost is
    present so callers can leave optimizer spend unmeasured.
    """
    if not stdout or not stdout.strip():
        return None
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and isinstance(obj.get("cost"), dict):
            c = obj["cost"]
            usd = c.get("total_cost_usd")
            tokens = c.get("tokens")
            if usd is None and tokens is None:
                return None
            return {"cost_usd": float(usd or 0.0), "tokens": int(tokens or 0)}
    return None


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

    # collect per-task trial rewards (+ last rollout/score) across trials
    per_task_trials: dict[str, list[float]] = {t.id: [] for t in tasks}
    per_task_feedback: dict[str, str] = {t.id: "" for t in tasks}
    per_task_errored: dict[str, bool] = {t.id: False for t in tasks}  # any trial an infra error?
    task_by_id = {t.id: t for t in tasks}
    run_cost, run_tokens = 0.0, 0           # RUNNER spend, summed over rollouts
    t0 = time.time()

    # ``live()`` makes the candidate the one the target uses for this evaluation and
    # yields the ``ctx`` the runner consumes (default ctx == candidate_dir). Using a
    # context manager (instead of a bare global ``apply``) means the live state is
    # scoped + torn down per evaluation, which is what lets independent candidates be
    # evaluated without clobbering a single shared global slot.
    with _live(adapter, candidate_dir) as ctx:
        for k in range(n_trials):
            seed = base_seed + k
            if has_batch:
                rb = adapter.run_batch(tasks, ctx, seed=seed)
                # accept either {task_id: Rollout} or a list parallel to `tasks`
                rollouts = rb if isinstance(rb, dict) else {t.id: r for t, r in zip(tasks, rb)}
            else:
                rollouts = {t.id: adapter.run_target(t, ctx, seed=seed) for t in tasks}
            for tid, task in task_by_id.items():
                rollout = rollouts.get(tid)
                if rollout is None:
                    # The batch omitted this task (an error/timeout inside the runner).
                    # Record it as a failed rollout (reward 0) — do NOT serially re-run
                    # it here, which would add a slow tail to every batch evaluation.
                    rollout = Rollout(task_id=tid, error="omitted from batch result")
                if getattr(rollout, "error", None):
                    per_task_errored[tid] = True
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
        # ``raw.errored`` carries the structured infra signal (rollout.error was set
        # on some trial) into the per-task record, so the focus builder can classify
        # uncontrollable failures without substring-matching feedback prose.
        scores.append(Score(
            task_id=tid, reward=mean(tr), feedback=per_task_feedback[tid],
            n=n_trials, stderr=stderr(tr), trial_rewards=tr,
            raw={"errored": per_task_errored[tid]},
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
    raw: dict[str, dict] = {}
    if vdir.exists():
        for f in sorted(vdir.glob(f"*__{tag}__t*.json")):
            rec = _json.loads(f.read_text(encoding="utf-8"))
            sc = rec.get("score", {})
            tid = sc.get("task_id") or f.name.split("__")[0]
            by_task.setdefault(tid, []).append(float(sc.get("reward", 0.0)))
            feedback[tid] = sc.get("feedback", feedback.get(tid, ""))
            # carry the structured infra flag forward across resume (errored on any trial)
            r0 = raw.setdefault(tid, {})
            if (sc.get("raw") or {}).get("errored"):
                r0["errored"] = True
    scores = [Score(task_id=t, reward=mean(r), feedback=feedback.get(t, ""),
                    n=len(r), stderr=stderr(r), trial_rewards=r, raw=raw.get(t, {}))
              for t, r in by_task.items()]
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
    e.g. ``["python", ".../optimizers/run-optimizer/scripts/run.py", "--name",
    "mock", "--workdir", "{workdir}", "--prompt", "{prompt}"]``. The subprocess
    edits files in workdir.
    """
    def _run(workdir: Path, instructions: str) -> dict | None:
        prompt_path = workdir / "INSTRUCTIONS.md"
        prompt_path.write_text(instructions, encoding="utf-8")
        cmd = [c.format(workdir=str(workdir), prompt=str(prompt_path)) for c in cmd_template]
        env = dict(os.environ)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise RuntimeError(f"optimizer failed ({proc.returncode}): {proc.stderr[:2000]}")
        # Best-effort: if run-optimizer reported its cost (it does under --json), hand
        # it back so the loop counts optimizer spend against the budget.
        return _parse_optimizer_cost(proc.stdout)
    return _run


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
    parent_id: str | None = None,
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
    # Lineage edge for the dashboard/report: the parent is the candidate this step
    # was forked from (the current best by default in a global hill-climb). Captured
    # before any accept flips ``best_id`` so the edge points at the true parent.
    parent_id = parent_id or run_dir.best_id
    workdir = run_dir.root / "work" / cid
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(parent_dir, workdir)

    instructions = _augment_instructions(instructions, workdir, run_dir, rejected, history)

    optimizer_error = None
    opt_cost_usd, opt_tokens = 0.0, 0
    _opt_t0 = time.time()
    try:
        opt_report = optimizer(workdir, instructions)  # mutates workdir in place
        if isinstance(opt_report, dict):
            opt_cost_usd = float(opt_report.get("cost_usd") or 0.0)
            opt_tokens = int(opt_report.get("tokens") or 0)
    except Exception as e:  # noqa: BLE001
        # A failed proposal (e.g. a transient optimizer/API error) must not abort a
        # long run — leave the workdir as the parent copy so the candidate == parent
        # and the gate simply rejects it (a wasted iteration, not a crash).
        optimizer_error = str(e)
        run_dir.log_event("optimizer_error", candidate=cid, error=optimizer_error[:500])
    optimizer_seconds = time.time() - _opt_t0
    run_dir.update_spent(optimizer_seconds=optimizer_seconds, optimizer_usd=opt_cost_usd,
                         optimizer_tokens=opt_tokens)

    cand_val = evaluate_candidate(adapter, workdir, run_dir=run_dir, split="val",
                                  n_trials=n_trials, tag=cid)

    # Paired gate is the default when per-task data is available: candidate and
    # current were scored on the SAME val tasks, so the correct (and far more
    # powerful) test is mean(per-task Δ) vs the SE of those paired deltas. Build the
    # aligned delta vector here; fall back to the unpaired ``significant`` test when
    # the caller has pinned a different mode or the per-task data isn't aligned.
    paired_deltas = _paired_deltas(current_val, cand_val)
    if "mode" not in gate_kwargs and paired_deltas is not None:
        gate_kwargs["mode"] = "paired"
    decision = gate_mod.decide(
        current_val.reward, cand_val.reward, split="val",
        candidate_stderr=cand_val.stderr, current_stderr=current_val.stderr,
        paired_deltas=paired_deltas, run_dir=run_dir,
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
                      val=cand_val.reward, parent=parent_id, parent_val=current_val.reward,
                      optimizer_seconds=round(optimizer_seconds, 2),
                      runner_seconds=round(cand_val.seconds, 2),
                      cost_usd=cand_val.cost_usd, tokens=cand_val.tokens,
                      opt_cost_usd=round(opt_cost_usd, 6), opt_tokens=opt_tokens)
    run_dir.record_spend_warnings()

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
        "optimizer_usd": opt_cost_usd,
        "optimizer_tokens": opt_tokens,
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

def _is_infra(pt) -> bool:
    """Structured infra signal: did this task's rollout carry ``error``?

    The harness records ``raw.errored = True`` when any trial's ``Rollout.error``
    was set (a timeout, API/run error, omitted batch result). We classify
    uncontrollable failures by that STRUCTURED field — not by substring-matching
    feedback prose, which dropped real "error" bugs and misfired on capability
    feedback that merely *mentions* an exception.
    """
    return bool((pt.get("raw") or {}).get("errored"))


def _focus_instructions(current_val: SplitResult, focus_ids, label: str) -> str:
    per = current_val.per_task
    if focus_ids is not None:
        per = [pt for pt in per if pt.get("task_id") in set(focus_ids)]
    passed = [pt for pt in per if (pt.get("reward", 0) or 0) >= 1.0]
    failing = [pt for pt in per if (pt.get("reward", 0) or 0) < 1.0]

    actionable = [pt for pt in failing if not _is_infra(pt)]
    errored = [pt for pt in failing if _is_infra(pt)]

    lines = [
        "# Optimize the capability",
        "",
        f"Focus: {label}. Current val reward: {current_val.reward:.3f} "
        f"({len(passed)}/{len(per)} tasks already pass). Edit the capability files in "
        "this working directory to raise the reward on the ACTIONABLE failures below.",
        "",
    ]
    if errored:
        ids = ", ".join(str(pt.get("task_id")) for pt in errored[:25])
        lines += [
            f"## Ignore — {len(errored)} task(s) failed with run/infrastructure errors",
            "These are environment noise (a flaky/aborted run), NOT a capability problem; "
            "no edit can fix them, so do not change anything on their account: " + ids,
            "",
        ]
    lines.append(f"## {len(actionable)} actionable failing task(s) — find the COMMON rule across them:")
    for pt in actionable[:10]:
        lines.append(f"- {pt.get('task_id')}: {str(pt.get('feedback', ''))[:500]}")
    if not actionable:
        lines.append("- (no actionable failures in focus; seek robustness/generalization gains)")
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
    """The loop behind the ``hill-climb`` skill's three ``--focus`` schedules
    (all / cyclic / hardest-first).

    They differ only in the *focus schedule* — which tasks each iteration's
    reflection emphasizes — and (for hardest-first) the order. Parent is always
    the current best (global hill-climb). The ``gepa`` algorithm uses its own
    per-instance frontier and parent selection (see ``cap_evolve.gepa``).
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


# ---- finalize -------------------------------------------------------------

def finalize(adapter, *, run_dir: RunDir, best_dir: Path, n_trials: int = 1, ks=(1, 2)) -> dict:
    """Score the best candidate on the SEALED test split exactly once.

    Seal-on-success: ``evaluate_candidate`` *reserves* the seal (raises if already
    burned) but does not flip it. We compute + persist the test result FIRST, and
    only then ``commit_test`` to burn the seal. So a crash anywhere in scoring or
    in writing ``final.json`` leaves the seal unused and a retry can still score
    test once — a transient failure no longer permanently destroys the headline.
    """
    result = evaluate_candidate(adapter, best_dir, run_dir=run_dir, split="test",
                                n_trials=n_trials, ks=ks, tag="FINAL")
    payload = {"test": result.to_dict(), "best_id": run_dir.best_id}
    _atomic_write(run_dir.root / "final.json", json.dumps(payload, indent=2))
    run_dir.commit_test()  # burn the seal ONLY now that the result is computed + written
    run_dir.log_event("finalize", test_reward=result.reward, best_id=run_dir.best_id)
    return payload
