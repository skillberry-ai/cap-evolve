"""Executable pipeline logic shared by the phase/algorithm skills.

The skills are the user-facing, self-describing layer; the *mechanics* they all
need — make splits once, evaluate a candidate with multi-trial honesty, run one
propose→gate step, finalize on the sealed test set — live here so they aren't
re-derived (and subtly broken) per skill. Every honesty-critical operation routes
through ``splits``/``stats``/``gate``/``rundir``.

An "optimizer" is any callable ``(workdir: Path, instructions: str) -> None`` that
edits files in ``workdir`` in place (prior agent-optimization work's model). ``optimizer_from_command``
builds one from a skill's ``run.py`` so external agents plug in the same way.

MODULE MAP (#115 split this file; it was 2,526 lines mixing eight concerns)
-------------------------------------------------------------------------
What still lives HERE is the run LIFECYCLE — the three points where a run touches its
own boundaries: freeze the split, establish the baseline, seal the test set.

  ``optimizer_proc``   — build an ``OptimizerFn`` from a shell command; cost parsing.
  ``evaluate``         — the per-task rollout loop, aggregation, paired deltas.
  ``capdiff``          — capability snapshot reads/diffs + per-task impact.
  ``insights``         — INSIGHTS.md, the durable synthesized priors (#128).
  ``handover``         — LEDGER / JOURNAL / PROCESS / RUNMAP + dead-end constraints,
                         and ``_augment_instructions``, the ONE prompt chokepoint.
  ``context_inject``   — the FILE side of the optimizer-context seam.
  ``instructions``     — prompt templating: failure index, briefs, notes.
  ``step``             — ``run_step``, ONE propose->gate step, shared by all three
                         algorithms (the shared/hill-climb-specific boundary #115 asked
                         for). ``hill_climb_loop`` itself stays here, next to the other
                         run-lifecycle entry points and in the same namespace as the
                         ``run_step`` it calls.
  ``optimizer_context``— the PUBLIC seam (``OptimizerContext``, ``inject``,
                         ``render_instructions``); predates this split (#109).

Every name this module used to export is RE-EXPORTED below, so ``from
cap_evolve.harness import X`` keeps resolving for every caller in ``core/``, ``skills/``
and ``dashboard/``. New code should import from the owning module.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: F401  (harness.subprocess is a monkeypatch target; same module
                   # object optimizer_proc uses, so patching it still reaches the CLI call)
from pathlib import Path

from . import plateau
from . import protect as protect_mod
from . import splits as splits_mod
from .loop import SplitResult
from .rundir import RunDir, _atomic_write
from .splits import Splits, check_val_size, make_splits
from .types import Task

# ---------------------------------------------------------------------------
# Re-exports: the pre-#115 public (and de-facto public) surface of this module.
#
# These are NOT convenience aliases — ``harness.X`` is the import path used across
# core/, skills/, dashboard/ and the test suite, and #115 was required to be a pure
# refactor. Re-exporting keeps every one of those call sites working unchanged.
# ---------------------------------------------------------------------------
from .capdiff import (  # noqa: F401
    _CAP_DIFF_SKIP,
    _CAP_DIFF_SKIP_DIRS,
    _candidate_task_impact,
    _capability_files,
    _diff_capabilities,
    _parent_map,
    _per_task_rewards,
)
from .context_inject import (  # noqa: F401
    _NATIVE_POINTER_MARK,
    _copy_step_trajectories,
    _inject_native_skills,
    _inject_optimizer_context,
    _write_instructions_pointer,
)
from .evaluate import (  # noqa: F401
    _aggregate_metrics,
    _live,
    _paired_deltas,
    _tasks_for,
    evaluate_candidate,
    split_result_from_rollouts,
)
from .handover import (  # noqa: F401
    _CTRL_STRIP,
    _JOURNAL_MARK,
    _JOURNAL_SEED,
    _MAX_APPROACH_CHARS,
    _MAX_DEAD_ENDS,
    _PROCESS_SEED,
    _augment_instructions,
    _build_ledger,
    _build_runmap,
    _journal_tail,
    _reconcile_journal,
    _seed_journal,
    approach_signature,
    dead_end_constraints,
)
from .step import _SNAPSHOT_IGNORE, _init_memory_store, run_step  # noqa: F401
from .insights import (  # noqa: F401
    _INSIGHT_KEEP,
    _INSIGHT_OPEN,
    _INSIGHT_TASKS,
    _INSIGHT_TRUNC,
    _REASON_MAX,
    MAX_INSIGHT_CHARS,
    _build_insights,
    _insight_reason,
    _insight_rows,
)
from .instructions import (  # noqa: F401
    _CAP_EDIT_SPACE,
    _DEFAULT_INSTRUCTIONS_TEMPLATE,
    _algorithm_brief,
    _capability_brief,
    _capability_is_empty,
    _classify,
    _empty_seed_note,
    _failures_block,
    _fmt,
    _focus_instructions,
    _is_infra,
    _is_infra_ignore,
    _optimizer_parallel,
    _parallel_note,
    _passing_block,
)
from .optimizer_proc import (  # noqa: F401
    OptimizerFn,
    _optimizer_failure_detail,
    _parse_optimizer_cost,
    optimizer_from_command,
)

# Incidental names that were importable from this module before the split purely because
# it imported them for its own use. Nothing in core/, skills/ or dashboard/ imports any of
# them THROUGH harness (verified by grep), but `from cap_evolve.harness import X` used to
# work for each, and #115 is a pure refactor — so they keep working.
import contextlib  # noqa: E402,F401
import hashlib  # noqa: E402,F401
import os  # noqa: E402,F401
import sys  # noqa: E402,F401
import time  # noqa: E402,F401
from typing import Callable  # noqa: E402,F401

from . import gate as gate_mod  # noqa: E402,F401
from . import optimizer_context as _oc  # noqa: E402,F401
from .loop import aggregate_scores  # noqa: E402,F401
from .rundir import NON_CAPABILITY_NAMES, SCRATCH_NAMES, iteration_candidate  # noqa: E402,F401
from .types import Rollout, Score  # noqa: E402,F401

# ---- splits ---------------------------------------------------------------

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
    # Refuse an unusable val split BEFORE freezing it — an empty/1-task val makes the
    # acceptance gate meaningless, and the whole point of the gate is honesty.
    check_val_size(splits, context="at split freeze", run_dir=run_dir)
    run_dir.write_splits(splits)
    run_dir.log_event("splits", train=len(splits.train), val=len(splits.val),
                      test=len(splits.test), seed=seed)
    return splits


# ---- baseline -------------------------------------------------------------

# ---- baseline -------------------------------------------------------------

def baseline(adapter, seed_dir: Path, *, run_dir: RunDir, n_trials: int = 1, ks=(1, 2)) -> SplitResult:
    """Snapshot the seed capability as candidate ``seed``, score it on val, set best.

    Establishes the starting point every algorithm compares against. Assumes
    ``ensure_splits`` has been called.

    An empty ``seed_dir`` (no files) is accepted — the directory is created if
    needed and snapshotted as an empty candidate. The optimizer will create the
    initial capability content from the failing trajectories.
    """
    # Second guard point: a hand-written / resumed splits.json never went through
    # ensure_splits, so re-check before spending any budget on a run whose gate
    # could not possibly be honest.
    check_val_size(run_dir.read_splits(), context="at baseline", run_dir=run_dir)
    seed_dir = Path(seed_dir)
    if not seed_dir.exists():
        # Accept an empty seed, but make it auditable: a typo'd capability_path would
        # otherwise silently become a brand-new empty dir and look like an empty seed.
        run_dir.log_event("seed_dir_created", path=str(seed_dir),
                          msg="seed capability dir did not exist — created empty (empty-seed start)")
        seed_dir.mkdir(parents=True, exist_ok=True)
    run_dir.snapshot("seed", seed_dir)
    run_dir.set_best("seed")
    result = evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                               split="val", n_trials=n_trials, ks=ks, tag="seed")
    (run_dir.root / "baseline.json").write_text(
        json.dumps({"val": result.to_dict(), "best_id": "seed"}, indent=2), encoding="utf-8")
    run_dir.log_event("baseline", val=result.reward, stderr=result.stderr)
    return result


def reuse_baseline(prior_run_dir: Path, *, run_dir: RunDir) -> SplitResult:
    """Reuse a PRIOR run's baseline instead of recomputing it.

    Copies the prior run's frozen ``splits.json``, ``baseline.json``, the seed
    candidate snapshot (``candidates/seed``), and the seed's val rollouts
    (``rollouts/val``) into this fresh run dir, registers ``seed`` as the best
    candidate, and returns the prior baseline val SplitResult — SKIPPING the
    (expensive) baseline eval. The test seal stays intact: only ``splits.json`` is
    copied, and its ``test_used`` flag is forced unused so this run can still score
    test exactly once at finalize.

    Used by ``baseline``'s ``--reuse-baseline`` flag. Backward compatible: when not
    invoked, baseline behaves exactly as before.
    """
    prior = Path(prior_run_dir)
    prior_splits = prior / "splits.json"
    prior_baseline = prior / "baseline.json"
    if not prior_splits.exists():
        raise FileNotFoundError(f"prior run has no splits.json: {prior_splits}")
    if not prior_baseline.exists():
        raise FileNotFoundError(f"prior run has no baseline.json: {prior_baseline}")

    # Copy the frozen split, but reset the test seal so this run can finalize once.
    prior_split_obj = Splits.from_dict(json.loads(prior_splits.read_text(encoding="utf-8")))
    fresh_split = Splits(train=list(prior_split_obj.train), val=list(prior_split_obj.val),
                         test=list(prior_split_obj.test), seed=prior_split_obj.seed)
    # Guard BEFORE writing: a prior run created under CAPEVOLVE_ALLOW_TINY_VAL must not
    # become a reusable seed for a fresh run that nothing marks as dishonest. Checking
    # first also means nothing is frozen into this run dir on refusal.
    check_val_size(fresh_split, context="at baseline reuse", run_dir=run_dir)
    run_dir.write_splits(fresh_split)

    # Copy baseline.json verbatim (the recorded seed val score + best_id).
    shutil.copyfile(prior_baseline, run_dir.root / "baseline.json")

    # Copy the seed candidate snapshot so this run can read/serve it as best.
    prior_seed = prior / "candidates" / "seed"
    if prior_seed.is_dir():
        run_dir.snapshot("seed", prior_seed)

    # Copy the seed's val rollouts so diagnose/algorithm can read them without a re-run.
    prior_val_rollouts = prior / "rollouts" / "val"
    if prior_val_rollouts.is_dir():
        dst = run_dir.rollouts / "val"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(prior_val_rollouts, dst)

    run_dir.set_best("seed")

    # Tamper provenance for an INHERITED baseline (#142). This number was produced by
    # another run's grader, which this run never hashed. If that run logged a tamper the
    # baseline is fiction, so refuse it; otherwise carry its manifest forward so this
    # run verifies against the tree the reused number was actually scored on, instead of
    # re-recording whatever the tree looks like now.
    prior_events = prior / "events.jsonl"
    if prior_events.exists():
        for line in prior_events.read_text(encoding="utf-8").splitlines():
            if '"tamper_detected"' in line:
                raise protect_mod.TamperError(
                    f"cap-evolve: refusing to reuse the baseline from {prior} — that run "
                    "logged a tamper_detected event, so its baseline was scored against a "
                    "grader that changed mid-run. Reusing it would inherit a fabricated "
                    "number as this run's reference point. Re-run baseline from a clean "
                    "checkout."
                )
    prior_manifest = prior / protect_mod.MANIFEST_NAME
    if prior_manifest.exists() and not (run_dir.root / protect_mod.MANIFEST_NAME).exists():
        shutil.copyfile(prior_manifest, run_dir.root / protect_mod.MANIFEST_NAME)
        try:
            payload = json.loads(prior_manifest.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — an unreadable prior manifest is no provenance
            payload = None
        if payload is not None:
            run_dir.log_event("protected_manifest", n_files=len(payload.get("files") or {}),
                              globs=payload.get("globs") or [],
                              digest=protect_mod.manifest_digest(payload),
                              inherited_from=str(prior))

    baseline_data = json.loads(prior_baseline.read_text(encoding="utf-8"))
    result = SplitResult.from_dict(baseline_data["val"])
    run_dir.log_event("baseline_reused", prior_run_dir=str(prior),
                      val=result.reward, stderr=result.stderr,
                      protected_manifest_inherited=prior_manifest.exists())
    return result


# ---- hill-climb loop (hill-climb ONLY; run_step above is the shared part) --

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
    ctx=None,
    capabilities=None,
    instructions_file=None,
    bench_repo: str | None = None,
    optimizer_name: str | None = None,
    capability_sources=None,
    project_dir: Path | None = None,
    target_model: str = "",
    target_profile_file: str | None = None,
    plateau_cfg: "plateau.PlateauConfig | None" = None,
) -> dict:
    """The loop behind the ``hill-climb`` skill's three ``--focus`` schedules
    (all / cyclic / hardest-first).

    They differ only in the *focus schedule* — which tasks each iteration's
    reflection emphasizes — and (for hardest-first) the order. Parent is always
    the current best (global hill-climb). The ``gepa`` algorithm uses its own
    per-instance frontier and parent selection (see ``cap_evolve.gepa``).

    ``ctx`` is an ``optimizer_context.OptimizerContext`` bundling what the optimizer is
    given (capabilities, instructions template, bench repo, optimizer name, capability
    sources, consuming-LLM profile) — the same bundle ``gepa_loop`` / ``skillopt_loop``
    take. The individual kwargs remain for direct callers and build a ctx when none is
    passed.
    """
    gate_kwargs = dict(gate_kwargs or {})
    rejected, history, store = _init_memory_store(run_dir, store)

    from .optimizer_context import OptimizerContext, render_instructions
    ctx = ctx or OptimizerContext(
        capabilities=capabilities or [], optimizer_name=optimizer_name,
        instructions_file=instructions_file, bench_repo=bench_repo,
        capability_sources=capability_sources or [], project_dir=project_dir,
        target_model=target_model, target_profile_file=target_profile_file)

    # establish a focus order over the train tasks when needed
    train_ids = run_dir.read_splits().train
    order = list(train_ids)
    if focus == "hardest-first":
        seed_dir = run_dir.candidate_dir("seed")
        train_res = evaluate_candidate(adapter, seed_dir, run_dir=run_dir, split="train",
                                       n_trials=n_trials, tag="seed_train")
        score_by = {pt["task_id"]: pt["reward"] for pt in train_res.per_task}
        order.sort(key=lambda t: score_by.get(t, 0.0))  # hardest (lowest) first

    # Plateau/convergence detection (see cap_evolve.plateau): a THIRD stop condition,
    # orthogonal to budget and to the `stall` reject-counter. It escalates
    # warn -> diversify (prompt intervention) -> stop.
    pcfg = plateau_cfg or plateau.PlateauConfig()
    pstate = plateau.PlateauState()

    steps = []
    why = ""   # read after the loop, so it must be bound when the body never runs
               # (max_iterations=0, or a resume whose budget is already spent).
    for i in range(max_iterations):
        exhausted, why = run_dir.budget_exhausted()
        if exhausted:
            break
        pstate = plateau.check(run_dir, pcfg, last=pstate, algorithm=algorithm)
        if pstate.should_stop:
            why = f"plateaued ({pstate.reason})"
            break
        if focus == "all":
            focus_ids, label = None, "whole train set"
        elif focus in ("cyclic", "hardest-first"):
            focus_ids = [order[i % len(order)]] if order else None
            label = f"task {focus_ids[0]}" if focus_ids else "train"
        else:
            focus_ids, label = None, focus
        instructions = render_instructions(current_val, focus_ids, label, ctx=ctx,
                                          algorithm=algorithm, run_dir=run_dir)
        step = run_step(
            adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir(run_dir.best_id),
            optimizer=optimizer, instructions=instructions, current_val=current_val,
            extra_instructions=plateau.prompt_block(pstate),
            n_trials=n_trials, gate_kwargs=gate_kwargs, no_regression=no_regression,
            rejected=rejected, history=history, store=store, ctx=ctx,
        )
        steps.append(step)
        if step["accepted"]:
            current_val = SplitResult.from_dict(step["candidate_val"])

    pstate = plateau.check(run_dir, pcfg, last=pstate, algorithm=algorithm)
    stop_why = why if why and why.startswith("plateaued") else None
    _, budget_why = run_dir.budget_exhausted()
    return {
        "algorithm": algorithm,
        "best_id": run_dir.best_id,
        "best_val": current_val.reward,
        "iterations": len(steps),
        "accepts": sum(1 for s in steps if s["accepted"]),
        "stop_reason": stop_why or budget_why or "max_iterations",
        "plateau": pstate.to_dict(),
        "steps": steps,
    }


# ---- finalize -------------------------------------------------------------

# ---- finalize -------------------------------------------------------------

def finalize(adapter, *, run_dir: RunDir, best_dir: Path, n_trials: int = 1, ks=(1, 2),
             baseline_dir: Path | None = None) -> dict:
    """Score the best candidate on the SEALED test split exactly once.

    Also scores the BASELINE (seed) capability on the SAME sealed test split, so the
    headline is the honest *improvement* on held-out data — optimized vs. baseline —
    not just an absolute number that might equal the baseline. Both are scored inside
    this single sealed finalize: ``evaluate_candidate`` only *reserves* (checks) the
    seal, so scoring two candidates here is fine; the seal is *committed* once at the
    end. Pass ``baseline_dir`` (the ``seed`` candidate dir) to enable the comparison;
    if the best candidate IS the seed (no accepted gain), the two are equal by
    construction and the second eval is skipped.

    Seal-on-success: we compute + persist the test result(s) FIRST and only then
    ``commit_test`` to burn the seal, so a crash mid-scoring leaves the seal unused
    and a retry can still score test once.
    """
    result = evaluate_candidate(adapter, best_dir, run_dir=run_dir, split="test",
                                n_trials=n_trials, ks=ks, tag="FINAL")
    payload = {"test": result.to_dict(), "best_id": run_dir.best_id}

    # Baseline-on-test: the honest held-out comparison (optimized skills vs seed skills).
    if baseline_dir is not None and Path(baseline_dir).resolve() != Path(best_dir).resolve():
        base = evaluate_candidate(adapter, baseline_dir, run_dir=run_dir, split="test",
                                  n_trials=n_trials, ks=ks, tag="FINAL_seed")
        payload["test_baseline"] = base.to_dict()
        payload["baseline_id"] = "seed"
        payload["test_delta"] = round(result.reward - base.reward, 6)
    else:
        # Best IS the seed (no accepted improvement) → baseline == optimized on test.
        payload["test_baseline"] = result.to_dict()
        payload["baseline_id"] = run_dir.best_id
        payload["test_delta"] = 0.0

    # Last gate before the seal burns (#142). ``evaluate_candidate`` already
    # pre- and post-checks each test eval; this covers the remaining gap between the
    # final ``score()`` and the irreversible ``commit_test``, so the headline number is
    # never sealed against a grader that changed at any point during finalize.
    protect_mod.verify(run_dir, context="finalize (pre-seal)")

    # Brand a bypassed run in the durable artifact. A run whose acceptance gate was
    # not a significance test must not produce a final.json that is byte-identical in
    # shape to an honest one — report.md and the dashboard both read this back.
    bypass = splits_mod.bypassed(run_dir)
    if bypass:
        payload["honest_gate"] = False
        payload["warnings"] = [splits_mod.BYPASS_BANNER]
        payload["tiny_val_bypass"] = bypass

    _atomic_write(run_dir.root / "final.json", json.dumps(payload, indent=2))
    run_dir.commit_test()  # burn the seal ONLY now that the result(s) are computed + written
    run_dir.log_event("finalize", test_reward=result.reward,
                      test_baseline_reward=payload["test_baseline"]["reward"],
                      test_delta=payload["test_delta"], best_id=run_dir.best_id)
    return payload
