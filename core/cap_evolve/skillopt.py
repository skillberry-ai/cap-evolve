"""SkillOpt — a disciplined single-lineage climber with a textual learning rate.

SkillOpt (arXiv:2605.23904) sits *between* the two siblings already in the
engine:

  * ``hill_climb_loop`` proposes against the whole train set every iteration
    (one-shot, no notion of an epoch or a shrinking step), and
  * ``gepa`` maintains a Pareto FRONTIER of specialists and samples
    a parent from it.

SkillOpt keeps gepa's *epochs × mini-batches* economy but stays a STRICT
single-lineage climb (parent is always the current best, like hill-climb), and
adds three things straight out of the deep-learning analogy:

  1. **Textual learning rate** — an integer *edit budget* ``L`` per step on a
     ``constant | linear | cosine`` schedule (``lr_schedule.build_schedule``):
     many edits early (explore), few edits late (consolidate). ``L`` is
     communicated to the optimizer in NATURAL LANGUAGE only ("make at most L
     bounded edits") — the LLM is not mechanically clipped — so we log
     *requested vs applied* to detect an optimizer that ignores its budget.
  2. **Within-epoch rejected-edit buffer + failure-pattern block** — every step
     appends to a per-epoch buffer (accepted?, n_fail, clustered failure
     patterns, and the rejected candidate id + val delta on a reject). The buffer
     is injected into the next step's prompt ("avoid these rejected edits; these
     failure patterns remain unsolved") and is RESET + BOUNDED each epoch so the
     prompt cannot balloon.
  3. **Epoch-boundary slow / meta update** (paper §3.6) — at the end of each
     epoch (from epoch 2 on) the skill snapshot taken at the *start* of the epoch
     is re-evaluated against the current best on a small sampled TRAIN subset,
     each task categorised improved / regressed / persistent_fail / stable_success,
     and ONE extra step is run with a longitudinal instruction ("fix the
     regressions without breaking the stable successes"). This extra step is
     **GATED ON VAL exactly like a normal step** — never force-accepted, never
     bypassing the gate to mutate best.

Everything honesty-critical (materialize → optimize → eval-val → gate →
accept/reject → snapshot/best, RejectedMemory/History, the sealed test) is
delegated to ``harness.run_step`` / ``harness.evaluate_candidate``; this module
only owns the *schedule*, the *buffer*, and the *slow update*. The result-dict
shape mirrors ``hill_climb_loop`` (plus per-epoch stats + slow-update records).

Gated on val; test stays sealed.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from . import harness
from .lr_schedule import build_schedule
from .loop import SplitResult
from .rundir import RunDir

# Buffer bounds (PITFALL: the rejected-edit buffer must be reset + bounded per
# epoch so the optimizer prompt does not balloon).
_MAX_FAILURES_PER_STEP = 10      # failure-pattern clusters carried per step
_MAX_TASK_IDS_PER_PATTERN = 3    # task ids shown per cluster
_MAX_BUFFER_STEPS = 12           # most recent steps kept in the per-epoch buffer


# ---- failure-pattern clustering -------------------------------------------

def _failure_patterns(per_task: list, focus_ids=None) -> list[dict]:
    """Cluster the focus tasks' failing feedback by a normalized prefix.

    Returns ``[{pattern, task_ids, n}]`` — the common failure signatures across
    the (focused) failing tasks, so the buffer carries *patterns* not raw prose.
    Infra-errored tasks are excluded (no edit fixes environment noise). Mirrors
    the engine's structured ``raw.errored`` classification used by
    ``_focus_instructions``.
    """
    per = per_task or []
    if focus_ids is not None:
        keep = set(focus_ids)
        per = [pt for pt in per if pt.get("task_id") in keep]
    clusters: dict[str, list[str]] = {}
    for pt in per:
        if (pt.get("reward", 0.0) or 0.0) >= 1.0:
            continue
        if (pt.get("raw") or {}).get("errored"):
            continue  # infra noise, not an actionable failure pattern
        fb = str(pt.get("feedback", "") or "").strip()
        # Normalized signature: first ~8 words, lowercased — a cheap, deterministic
        # clustering key (same idea as diagnose's default signature fn).
        sig = " ".join(fb.lower().split()[:8]) or "(no feedback)"
        clusters.setdefault(sig, []).append(str(pt.get("task_id")))
    out = [{"pattern": sig, "task_ids": ids[:_MAX_TASK_IDS_PER_PATTERN], "n": len(ids)}
           for sig, ids in clusters.items()]
    # Most-frequent patterns first; cap the count.
    out.sort(key=lambda c: c["n"], reverse=True)
    return out[:_MAX_FAILURES_PER_STEP]


def _n_fail(per_task: list, focus_ids=None) -> int:
    per = per_task or []
    if focus_ids is not None:
        keep = set(focus_ids)
        per = [pt for pt in per if pt.get("task_id") in keep]
    return sum(1 for pt in per if (pt.get("reward", 0.0) or 0.0) < 1.0)


# ---- prompt building -------------------------------------------------------

def _buffer_block(edit_budget: int, step_buffer: list[dict], rejected_this_epoch: list[dict]) -> str:
    """The SkillOpt-specific block appended to the focus instructions.

    Carries: the textual learning rate L (edit budget), the previously-rejected
    edits to avoid (this epoch), and the failure patterns still unsolved.
    """
    lines = [
        "",
        "## SkillOpt step budget (textual learning rate)",
        f"You may make **at most L = {edit_budget}** bounded edits this step "
        "(an add, delete, or replace each count as one). Prefer fewer, surgical "
        "edits over a rewrite — this budget shrinks over the run to consolidate "
        "gains. Do not exceed L.",
    ]
    if rejected_this_epoch:
        lines += ["", "## Avoid these previously-rejected edits (this epoch)"]
        for r in rejected_this_epoch[-_MAX_BUFFER_STEPS:]:
            d = r.get("val_delta")
            dtxt = f" (val Δ {d:+.3f})" if isinstance(d, (int, float)) else ""
            lines.append(f"- {r.get('candidate_id')}: rejected{dtxt}")
    # Aggregate the unsolved failure patterns seen across the epoch's steps.
    patterns: dict[str, set] = {}
    for s in step_buffer[-_MAX_BUFFER_STEPS:]:
        for fp in s.get("failure_patterns", []):
            patterns.setdefault(fp["pattern"], set()).update(fp.get("task_ids", []))
    if patterns:
        lines += ["", "## Failure patterns still unsolved (cluster of focus tasks)"]
        for sig, ids in list(patterns.items())[:_MAX_FAILURES_PER_STEP]:
            shown = ", ".join(sorted(ids)[:_MAX_TASK_IDS_PER_PATTERN])
            lines.append(f"- {sig} — e.g. tasks: {shown}")
    return "\n".join(lines)


def _slow_update_instructions(epoch: int, categories: dict[str, list[dict]]) -> str:
    """Longitudinal (epoch N vs N-1) instruction for the gated slow update."""
    regressed = categories.get("regressed", [])
    persistent = categories.get("persistent_fail", [])
    stable = categories.get("stable_success", [])
    lines = [
        f"# SkillOpt slow / meta update — epoch {epoch} vs epoch {epoch - 1}",
        "",
        "Comparing the skill at the START of this epoch to the current best on a "
        "sampled TRAIN subset, the tasks below changed. Make a CONSOLIDATING edit: "
        "fix the REGRESSIONS and chip at the PERSISTENT failures WITHOUT breaking "
        "any STABLE SUCCESS. This is a careful meta-step, so keep it small.",
        "",
        f"## REGRESSED — passed at epoch start, now failing ({len(regressed)})",
    ]
    for pt in regressed[:_MAX_FAILURES_PER_STEP]:
        lines.append(f"- {pt.get('task_id')}: {str(pt.get('feedback', ''))[:300]}")
    if not regressed:
        lines.append("- (none — good; do not destabilize current passes)")
    lines += ["", f"## PERSISTENT failures — failing both epochs ({len(persistent)})"]
    for pt in persistent[:_MAX_FAILURES_PER_STEP]:
        lines.append(f"- {pt.get('task_id')}: {str(pt.get('feedback', ''))[:300]}")
    if not persistent:
        lines.append("- (none)")
    lines += ["", f"## STABLE SUCCESS — passing both epochs, DO NOT BREAK ({len(stable)})",
              "- " + ", ".join(str(pt.get("task_id")) for pt in stable[:25])
              if stable else "- (none)"]
    return "\n".join(lines)


def _categorize(prev_pt: list, cur_pt: list) -> dict[str, list[dict]]:
    """Categorize each task improved / regressed / persistent_fail / stable_success
    from two per-task reward maps (carrying the CURRENT feedback)."""
    prev = {pt.get("task_id"): float(pt.get("reward", 0.0) or 0.0) for pt in (prev_pt or [])}
    cur = {pt.get("task_id"): pt for pt in (cur_pt or [])}
    cats: dict[str, list[dict]] = {"improved": [], "regressed": [],
                                   "persistent_fail": [], "stable_success": []}
    eps = 1e-9
    for tid, pt in cur.items():
        if tid not in prev:
            continue
        before = prev[tid]
        after = float(pt.get("reward", 0.0) or 0.0)
        passed_before = before >= 1.0
        passed_after = after >= 1.0
        if after > before + eps:
            cats["improved"].append(pt)
        if passed_before and not passed_after:
            cats["regressed"].append(pt)
        elif not passed_before and not passed_after:
            cats["persistent_fail"].append(pt)
        elif passed_before and passed_after:
            cats["stable_success"].append(pt)
    return cats


# ---- the loop --------------------------------------------------------------

def skillopt_loop(
    adapter,
    *,
    run_dir: RunDir,
    optimizer: harness.OptimizerFn,
    current_val: SplitResult,
    epochs: int = 4,
    batch_size: int | None = None,
    accumulation: int = 1,
    edit_budget: int = 4,
    min_edit_budget: int = 2,
    lr_schedule: str = "cosine",
    n_trials: int = 1,
    gate_kwargs: dict | None = None,
    no_regression: bool = False,
    slow_update: bool = True,
    slow_update_sample: int = 20,
    algorithm: str = "skillopt",
    store=None,
) -> dict:
    """Run the SkillOpt epochs × mini-batches climb.

    Parameters mirror the SkillOpt spec; the loop is modeled on
    ``harness.hill_climb_loop`` (single lineage, parent = current best) and reuses
    ``harness.run_step`` for the honesty-critical materialize→gate→accept cycle.

    Returns a result dict shaped like ``hill_climb_loop``'s, plus ``epochs`` /
    ``edit_budget_schedule`` / ``slow_updates`` / per-epoch ``epoch_stats``.
    """
    gate_kwargs = dict(gate_kwargs or {})
    rejected, history, store = harness._init_memory_store(run_dir, store)

    train_ids = list(run_dir.read_splits().train)
    n_train = len(train_ids)
    if batch_size is None:
        batch_size = min(8, n_train) or 1
    batch_size = max(1, int(batch_size))
    accumulation = max(1, int(accumulation))
    epochs = max(1, int(epochs))

    # steps_per_epoch over the accumulated mini-batch size; total_steps drives the
    # textual-LR schedule (one edit budget per *training* step; slow-update steps
    # reuse the epoch's final budget).
    group = batch_size * accumulation
    steps_per_epoch = max(1, math.ceil(n_train / group)) if n_train else 1
    total_steps = epochs * steps_per_epoch
    schedule = build_schedule(lr_schedule, max_lr=edit_budget, min_lr=min_edit_budget,
                              total_steps=total_steps)

    run_dir.log_event("skillopt_start", epochs=epochs, steps_per_epoch=steps_per_epoch,
                      total_steps=total_steps, batch_size=batch_size, accumulation=accumulation,
                      edit_budget=edit_budget, min_edit_budget=min_edit_budget,
                      lr_schedule=lr_schedule, schedule=schedule, slow_update=slow_update)

    steps: list[dict] = []
    slow_updates: list[dict] = []
    epoch_stats: list[dict] = []
    global_step = 0
    stop_reason = None

    for epoch in range(1, epochs + 1):
        exhausted, why = run_dir.budget_exhausted()
        if exhausted:
            stop_reason = why
            break

        # Per-epoch: shuffle ids (seeded by epoch for reproducibility), reset the
        # within-epoch rejected-edit buffer, snapshot the epoch-start skill.
        rng = random.Random(1000 + epoch)
        order = list(train_ids)
        rng.shuffle(order)
        step_buffer: list[dict] = []          # bounded, per-epoch
        rejected_this_epoch: list[dict] = []  # rejected candidate ids + deltas, per-epoch
        prev_epoch_skill = SplitResult.from_dict(current_val.to_dict())
        prev_epoch_best_id = run_dir.best_id
        epoch_accepts = 0
        epoch_steps = 0

        for s in range(steps_per_epoch):
            exhausted, why = run_dir.budget_exhausted()
            if exhausted:
                stop_reason = why
                break

            # mini-batch(es): the accumulation window of the shuffled order.
            start = s * group
            minibatch_ids = order[start:start + group]
            if not minibatch_ids:
                break
            L = schedule[global_step] if global_step < len(schedule) else (schedule[-1] if schedule else edit_budget)

            label = f"epoch {epoch}/{epochs} step {s + 1}/{steps_per_epoch} "
            label += f"(mini-batch of {len(minibatch_ids)} train tasks, L={L})"
            instructions = harness._focus_instructions(current_val, minibatch_ids, label)
            instructions += "\n" + _buffer_block(L, step_buffer, rejected_this_epoch)

            cid = f"so_e{epoch:02d}s{s + 1:02d}"
            parent_dir = run_dir.candidate_dir(run_dir.best_id)  # single lineage: always best
            step = harness.run_step(
                adapter, run_dir=run_dir, parent_dir=parent_dir,
                optimizer=optimizer, instructions=instructions, current_val=current_val,
                n_trials=n_trials, gate_kwargs=gate_kwargs, candidate_id=cid,
                no_regression=no_regression, rejected=rejected, history=history, store=store,
            )
            cand_val = SplitResult.from_dict(step["candidate_val"])
            accepted = bool(step["accepted"])

            # Buffer the step (bounded + scoped to this epoch).
            patterns = _failure_patterns(cand_val.per_task, focus_ids=minibatch_ids)
            entry = {
                "step": global_step, "epoch": epoch, "step_in_epoch": s + 1,
                "accepted": accepted,
                "n_fail": _n_fail(cand_val.per_task, focus_ids=minibatch_ids),
                "failure_patterns": patterns,
            }
            if not accepted:
                delta = cand_val.reward - current_val.reward
                entry["rejected_candidate_id"] = step["candidate_id"]
                entry["val_delta"] = delta
                rejected_this_epoch.append({"candidate_id": step["candidate_id"],
                                            "val_delta": delta})
            step_buffer.append(entry)
            if len(step_buffer) > _MAX_BUFFER_STEPS:
                step_buffer = step_buffer[-_MAX_BUFFER_STEPS:]

            # requested-vs-applied (best-effort): did the optimizer change anything?
            # Compare the optimized workdir against the PARENT it was copied from
            # (not the post-accept best, which IS this candidate).
            applied = _changed_components(parent_dir, Path(step["workdir"]))
            run_dir.log_event("skillopt_step", epoch=epoch, step_in_epoch=s + 1,
                              global_step=global_step, edit_budget=L,
                              requested_edits=L, applied_changes=applied,
                              accept=accepted, candidate=step["candidate_id"],
                              val=cand_val.reward)

            step["epoch"] = epoch
            step["step_in_epoch"] = s + 1
            step["edit_budget"] = L
            step["applied_changes"] = applied
            steps.append(step)
            epoch_steps += 1
            if accepted:
                current_val = cand_val  # update best only on accept (read-back below is equiv)
                epoch_accepts += 1
            global_step += 1

        # ---- epoch-boundary slow / meta update (gated on val) --------------
        slow_rec = None
        if slow_update and epoch >= 2 and not run_dir.budget_exhausted()[0]:
            slow_rec = _run_slow_update(
                adapter, run_dir=run_dir, optimizer=optimizer, current_val=current_val,
                prev_epoch_skill=prev_epoch_skill, prev_epoch_best_id=prev_epoch_best_id,
                epoch=epoch, sample=slow_update_sample, edit_budget=schedule[-1] if schedule else edit_budget,
                n_trials=n_trials, gate_kwargs=gate_kwargs, no_regression=no_regression,
                rejected=rejected, history=history, store=store,
            )
            if slow_rec is not None:
                slow_updates.append(slow_rec)
                steps.append(slow_rec["step"])
                if slow_rec["step"]["accepted"]:
                    current_val = SplitResult.from_dict(slow_rec["step"]["candidate_val"])
                    epoch_accepts += 1

        epoch_stats.append({
            "epoch": epoch, "steps": epoch_steps, "accepts": epoch_accepts,
            "best_val": current_val.reward,
            "slow_update": (slow_rec["action"] if slow_rec else "skipped"),
        })

    if stop_reason is None:
        _, why = run_dir.budget_exhausted()
        stop_reason = why or "epochs_exhausted"

    return {
        "algorithm": algorithm,
        "best_id": run_dir.best_id,
        "best_val": current_val.reward,
        "epochs": epochs,
        "iterations": len(steps),
        "accepts": sum(1 for s in steps if s.get("accepted")),
        "rejects": sum(1 for s in steps if not s.get("accepted")),
        "edit_budget_schedule": schedule,
        "epoch_stats": epoch_stats,
        "slow_updates": [{"epoch": r["epoch"], "action": r["action"],
                          "accepted": r["step"]["accepted"]} for r in slow_updates],
        "stop_reason": stop_reason,
        "steps": steps,
    }


def _changed_components(parent_dir: Path, workdir: Path) -> int:
    """Best-effort count of files whose content differs between parent and the
    optimized workdir — a proxy for *applied* edits to compare against the
    *requested* budget L (PITFALL: the LLM is not mechanically clipped, so we log
    requested-vs-applied to surface an optimizer that ignores its budget)."""
    parent_dir, workdir = Path(parent_dir), Path(workdir)
    try:
        changed = 0
        seen = set()
        for f in workdir.rglob("*"):
            if not f.is_file() or ".git" in f.parts:
                continue
            rel = f.relative_to(workdir)
            # ignore harness-injected scaffolding files
            if rel.name in ("INSTRUCTIONS.md", "MEMORY.md", "STATE.md"):
                continue
            seen.add(rel)
            pf = parent_dir / rel
            if not pf.exists() or pf.read_bytes() != f.read_bytes():
                changed += 1
        for f in parent_dir.rglob("*"):
            if f.is_file() and ".git" not in f.parts:
                rel = f.relative_to(parent_dir)
                if rel.name in ("INSTRUCTIONS.md", "MEMORY.md", "STATE.md"):
                    continue
                if rel not in seen:
                    changed += 1  # a deletion
        return changed
    except Exception:  # noqa: BLE001
        return -1  # unknown


def _run_slow_update(
    adapter, *, run_dir: RunDir, optimizer, current_val: SplitResult,
    prev_epoch_skill: SplitResult, prev_epoch_best_id, epoch: int, sample: int,
    edit_budget: int, n_trials: int, gate_kwargs: dict, no_regression: bool,
    rejected, history, store,
) -> dict | None:
    """Re-evaluate the epoch-start skill vs current best on a small TRAIN subset,
    categorize, and run ONE extra gated step. Counted in budget; sample is small
    + toggleable. Returns a record or ``None`` if it could not run."""
    train_ids = list(run_dir.read_splits().train)
    if not train_ids:
        return None
    rng = random.Random(7000 + epoch)
    n = min(int(sample) if sample else len(train_ids), len(train_ids))
    sample_ids = rng.sample(train_ids, n) if n < len(train_ids) else list(train_ids)

    # Categorize using the per-task maps already on hand for current best, plus a
    # cheap re-eval of the epoch-start skill on the sampled subset. If the
    # epoch-start snapshot still exists, evaluate it on the sample; else fall back
    # to its stored per_task (prev_epoch_skill is the val result from epoch start).
    prev_dir = run_dir.candidate_dir(prev_epoch_best_id) if prev_epoch_best_id else None
    prev_pt = prev_epoch_skill.per_task
    cur_pt = current_val.per_task
    if prev_dir is not None and Path(prev_dir).exists() and prev_epoch_best_id != run_dir.best_id:
        # Re-eval BOTH on the same sampled TRAIN subset for an apples-to-apples
        # longitudinal comparison (a tiny, counted cost).
        prev_res = harness.evaluate_candidate(
            adapter, Path(prev_dir), run_dir=run_dir, split="train", n_trials=n_trials,
            tag=f"slow_prev_e{epoch}")
        cur_res = harness.evaluate_candidate(
            adapter, run_dir.candidate_dir(run_dir.best_id), run_dir=run_dir, split="train",
            n_trials=n_trials, tag=f"slow_cur_e{epoch}")
        keep = set(sample_ids)
        prev_pt = [pt for pt in prev_res.per_task if pt.get("task_id") in keep]
        cur_pt = [pt for pt in cur_res.per_task if pt.get("task_id") in keep]

    categories = _categorize(prev_pt, cur_pt)
    run_dir.log_event("skillopt_slow_eval", epoch=epoch, sample=len(sample_ids),
                      regressed=len(categories["regressed"]),
                      persistent_fail=len(categories["persistent_fail"]),
                      stable_success=len(categories["stable_success"]),
                      improved=len(categories["improved"]))

    instructions = _slow_update_instructions(epoch, categories)
    instructions += "\n" + _buffer_block(edit_budget, [], [])  # carry the consolidating L budget

    cid = f"so_e{epoch:02d}_slow"
    step = harness.run_step(
        adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir(run_dir.best_id),
        optimizer=optimizer, instructions=instructions, current_val=current_val,
        n_trials=n_trials, gate_kwargs=gate_kwargs, candidate_id=cid,
        no_regression=no_regression, rejected=rejected, history=history, store=store,
    )
    step["epoch"] = epoch
    step["step_in_epoch"] = "slow"
    step["edit_budget"] = edit_budget
    action = "accepted" if step["accepted"] else "rejected"
    run_dir.log_event("skillopt_slow_update", epoch=epoch, candidate=cid,
                      accept=step["accepted"], action=action,
                      regressed=len(categories["regressed"]))
    return {
        "epoch": epoch,
        "action": action,
        "sample_size": len(sample_ids),
        "categories": {k: [pt.get("task_id") for pt in v] for k, v in categories.items()},
        "step": step,
    }
