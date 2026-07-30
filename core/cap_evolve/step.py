"""ONE propose->gate step — the shared machinery every algorithm drives.

Split out of ``harness.py`` (#115), and the split is what finally makes the distinction
this issue was filed about visible: ``run_step`` is SHARED (hill-climb, GEPA and SkillOpt
all call it, so a change here changes all three), whereas the hill-climb LOOP that used
to sit beside it is hill-climb-only and stays in ``harness.py``.

One step: materialize the parent live, inject the optimizer's read-context, assemble the
instructions through the single ``handover`` chokepoint, run the optimizer, evaluate the
child, gate it on val, snapshot, reconcile the journal, log.

``_SNAPSHOT_IGNORE`` lives here because ``run_step`` is its only caller and it is the
engine's single DESTRUCTIVE name filter (see the tier note in ``rundir.py``).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from . import gate as gate_mod
from . import optimizer_context as _oc
from . import protect as protect_mod
from .evaluate import _paired_deltas, evaluate_candidate
from .handover import _augment_instructions, _reconcile_journal, approach_signature
from .loop import SplitResult
from .optimizer_proc import OptimizerFn
from .rundir import SCRATCH_NAMES, RunDir

# Big read-context the harness injects into the workdir that must NOT be stored as part
# of the candidate snapshot (it would bloat candidates/ and pollute diffs). NOTE we keep
# INSTRUCTIONS.md and PROCESS.md in the snapshot — PROCESS.md is the optimizer's
# per-iteration explainability, surfaced via RUNMAP/prior_iterations. INSTRUCTIONS/PROCESS
# (and the legacy MEMORY/STATE names) are instead filtered out at DIFF time
# (see dashboard._DIFF_SKIP) so iteration diffs show only real capability edits.
# Also exclude the NATIVE per-agent skill dirs and always-on instructions files the
# harness drops into the workdir (e.g. .claude/skills/, CLAUDE.md) — they are injected
# read-context, not part of the capability, so they must not bloat candidates/ or pollute diffs.
# PROCESS.md is deliberately NOT ignored — it is the per-candidate explainability we
# snapshot and surface via RUNMAP/prior_iterations. LEDGER/JOURNAL/RUNMAP + prior_iterations/
# are framework-injected read-context (LEDGER/RUNMAP regenerated, JOURNAL is run-level),
# so they must not bloat candidates/ or pollute diffs.
#
# This is the one DESTRUCTIVE consumer of the shared list — snapshot() drops what it
# names — so it takes ``SCRATCH_NAMES`` (live writers) ONLY, never
# ``rundir.NON_CAPABILITY_NAMES``. A retired name with no live writer can only refer to
# a capability file that shares it, and deleting that is silent data loss the eval-cache
# key can't see. See the tier note in rundir.py.
_SNAPSHOT_IGNORE = _oc.INJECTED_DIRS + _oc.INJECTED_NAMES + SCRATCH_NAMES


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
    extra_instructions: str = "",
    candidate_id: str | None = None,
    parent_id: str | None = None,
    no_regression: bool = False,
    rejected=None,
    history=None,
    store=None,
    capabilities=None,
    eval_split: str = "val",
    optimizer_name: str | None = None,
    capability_sources=None,
    project_dir: Path | None = None,
    ctx=None,
) -> dict:
    """Materialize parent → optimize → evaluate on val → gate → accept/reject.

    ``ctx`` is an ``optimizer_context.OptimizerContext``; when given it supersedes the
    individual ``capabilities`` / ``optimizer_name`` / ``capability_sources`` /
    ``project_dir`` kwargs (kept for direct callers).

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

    # Give the optimizer the full trajectories + capability guidance, in its own dir —
    # through the shared seam, so hill-climb / GEPA / SkillOpt inject identically.
    from .optimizer_context import OptimizerContext, inject as _inject
    _inject(adapter, run_dir, workdir, split=eval_split,
            ctx=ctx or OptimizerContext(
                capabilities=capabilities or [], optimizer_name=optimizer_name,
                capability_sources=capability_sources or [], project_dir=project_dir))

    # ``extra_instructions`` (the plateau block) goes THROUGH _augment_instructions so it
    # lands in the capped, preserved tail rather than being appended past the cap.
    instructions = _augment_instructions(instructions, workdir, run_dir,
                                         extra=extra_instructions)

    # Record the pristine protected-path hashes BEFORE the optimizer can touch
    # anything. ``baseline`` normally does this first, but ``--reuse-baseline``
    # skips the baseline eval, so without this the first manifest would be taken
    # AFTER an optimizer step and would bless a tampered grader.
    #
    # This is also what makes the guard correct under ``--resume``: the call is
    # idempotent when the manifest is intact (it re-reads it), so a resumed run keeps
    # verifying against the ORIGINAL baseline hashes rather than re-recording from the
    # current tree. If the manifest is gone or altered it raises instead — deleting it
    # was the one way ``--resume`` could launder a tampered file.
    protect_mod.ensure_manifest(run_dir, project_dir)

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
        # The optimizer may have already spent real money before failing (e.g. it
        # hit its own --usd-budget/--max-turns cap mid-session) — recover that cost
        # instead of letting it disappear as an unmeasured $0.
        recovered_cost = getattr(e, "cost", None)
        if isinstance(recovered_cost, dict):
            opt_cost_usd = float(recovered_cost.get("cost_usd") or 0.0)
            opt_tokens = int(recovered_cost.get("tokens") or 0)
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
    # Snapshot EVERY candidate (accepted and rejected) so the dashboard can diff any
    # iteration's output against its parent. Exclude the optimizer's injected scratch
    # (trajectories/, guidance/, INSTRUCTIONS/MEMORY/STATE) so the stored candidate is
    # capability-only and the diff shows just the real edit. Only an accepted candidate
    # becomes the new best (parent for the next step).
    run_dir.snapshot(cid, workdir, ignore=_SNAPSHOT_IGNORE)
    if accepted:
        run_dir.set_best(cid)
    run_dir.update_spent(iterations=1, accepted=accepted)
    run_dir.log_event("step", candidate=cid, accept=accepted, reason=decision.reason,
                      val=cand_val.reward, parent=parent_id, parent_val=current_val.reward,
                      optimizer_seconds=round(optimizer_seconds, 2),
                      runner_seconds=round(cand_val.seconds, 2),
                      cost_usd=cand_val.cost_usd, tokens=cand_val.tokens,
                      opt_cost_usd=round(opt_cost_usd, 6), opt_tokens=opt_tokens)
    run_dir.record_spend_warnings()

    # Record the iteration for the dashboard's Memory/Insights panels + commit it to the
    # version store, so the whole process stays inspectable (git log / LEDGER / JOURNAL).
    delta = cand_val.reward - current_val.reward
    summary = f"candidate {cid} (val {cand_val.reward:.3f}, Δ {delta:+.3f})"
    # Fold the optimizer's appended JOURNAL entry into the run-level append-only journal
    # (so handover accumulates across accepted AND rejected iterations). This is the
    # channel the NEXT iteration actually reads; _reconcile_journal stamps the objective
    # outcome + the exact tasks broken/fixed into it.
    _reconcile_journal(workdir, run_dir, cid, accepted=accepted,
                       val=cand_val.reward, delta=delta)
    if accepted:
        if history is not None:
            history.add(cid, summary, cand_val.reward)
    else:
        if rejected is not None:
            # Record WHAT was tried, not only the score — that signature is what the
            # next iteration's dead-end constraint block is built from (#129).
            rejected.add(cid, summary, decision.reason, cand_val.reward,
                         approach=approach_signature(parent_dir, workdir))
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
