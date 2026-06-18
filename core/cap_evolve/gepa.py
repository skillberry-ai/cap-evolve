"""GEPA — the sample-efficient reflective Pareto optimizer (arXiv:2507.19457).

This is the *real* GEPA loop, distinct from a plain hill-climb: it
adds the economy that makes GEPA sample-efficient — a cheap **minibatch** stage in
front of the expensive full-val gate — plus a **reflective dataset** built from
traces, a **per-instance Pareto frontier** with frequency-weighted parent
sampling, **round-robin component focus**, **system-aware merge**, an **eval
cache**, and a **rollout/metric-call budget**.

Why it lives here and not in ``harness.py``: the task spec asks for all the new
loop logic in one module that only *imports* from harness/loop/selection. So this
file owns the GEPA control flow and reuses the honesty-critical primitives
(``evaluate_candidate``, ``run_step``, ``gate.decide``, the seal) unchanged.

The shape of the loop (each numbered step maps to GEPA §3):

  1. Seed the pool with the baseline candidate (already val-scored = ``seed_val``)
     and build a per-instance Pareto frontier over its per-task val rewards.
  2. **Select a parent** by sampling the frontier weighted by how many val
     instances each non-dominated candidate is best at (``pareto_per_instance``),
     with a seeded, logged RNG.
  3. Sample a **minibatch** of train ids.
  4. Eval the parent on the minibatch (with traces) — cheap, cached.
  5. Build a **reflective dataset** over the parent's FAILING minibatch tasks
     (input + output/trajectory + feedback) → ``REFLECTION.md``, plus a round-robin
     **component focus** → ``FOCUS.md``, then invoke the optimizer.
  6. Eval the **child on the same minibatch**; **local gate** ``sum(child) >
     sum(parent)``. Only on pass do we spend more.
  7. On local-gate pass: pay for a **full val** eval and apply the honest
     significance ``gate.decide`` (val-only, paired) via ``run_step``'s accept
     path; on accept the child joins the pool + frontier.
  8. Budget is in **metric-calls** (primary) with a secondary iteration cap; both
     minibatch and full-val evals count via ``run_dir.update_spent``.
  9. The **eval cache** dedupes ``(candidate-hash, task_id)`` rollouts.
 10. **System-aware merge** (gated by ``--max-merges``/cadence): after an accept,
     occasionally find two frontier dominators sharing a common ancestor that both
     beat, build a merged candidate component-wise, minibatch-gate it, then
     full-val + standard gate.
 11. Test is never touched; minibatch/merge evals draw from train/val only.

Pure stdlib + the cap_evolve engine.
"""

from __future__ import annotations

import json
import random
import shutil
import time
from pathlib import Path
from typing import Callable

from . import gate as gate_mod
from . import selection
from .cache import EvalCache, hash_candidate_dir
from .harness import (
    _augment_instructions,
    _init_memory_store,
    _live,
    _paired_deltas,
    evaluate_candidate,
)
from .loop import SplitResult, aggregate_scores
from .rundir import RunDir
from .types import Rollout, Score

OptimizerFn = Callable[[Path, str], None]

# Optimizer-scratch / non-capability files that must NOT count as editable
# "components" (they perturb neither the capability nor the content hash).
_NON_COMPONENT = {
    "MEMORY.md", "STATE.md", "INSTRUCTIONS.md", "REJECTED.md",
    "FOCUS.md", "REFLECTION.md",
}
_NON_COMPONENT_DIRS = {".git", "__pycache__"}


# ---- components (editable capability files) -------------------------------

def _components(candidate_dir: Path) -> list[str]:
    """Editable capability files of a candidate, as sorted relative paths.

    These are GEPA's "components": the units the optimizer edits and the merge
    recombines. Scratch/memory files and vcs dirs are excluded (same exclusions
    the eval cache uses) so the component list is the *capability* surface only.
    For a monolithic single-file capability this returns one path; the merge step
    degrades gracefully in that case.
    """
    cdir = Path(candidate_dir)
    out: list[str] = []
    if not cdir.exists():
        return out
    for p in sorted(cdir.rglob("*"), key=lambda x: str(x)):
        if not p.is_file():
            continue
        rel = p.relative_to(cdir)
        if p.name in _NON_COMPONENT:
            continue
        if any(part in _NON_COMPONENT_DIRS for part in rel.parts):
            continue
        out.append(str(rel).replace("\\", "/"))
    return out


# ---- minibatch evaluation (subset of train, with traces + cache) ----------

def _eval_minibatch(
    adapter,
    candidate_dir: Path,
    task_ids: list[str],
    *,
    run_dir: RunDir,
    cache: EvalCache | None,
    tag: str,
    seed: int = 0,
) -> SplitResult:
    """Run + score a candidate on a SPECIFIC set of train task ids (one trial).

    ``evaluate_candidate`` always scores a whole split, so the minibatch stage —
    which is the entire point of GEPA's economy — gets a focused evaluator here.
    It mirrors ``evaluate_candidate``'s mechanics (``_live`` ctx, persisted
    rollouts in the same on-disk shape, ``update_spent(metric_calls=...)``,
    ``aggregate_scores``) and additionally:

      * keeps full traces in the per-task ``raw`` (``output`` + ``trace``) so the
        reflective dataset can show the agent's actual behavior, and
      * consults the **eval cache** keyed on ``(candidate-hash, task_id)`` to skip
        a rollout that was already scored for byte-identical candidate files.

    Minibatch tasks are drawn from TRAIN only (test stays sealed; val is for the
    honest gate). One trial per task — the minibatch is a cheap signal, not the
    significance test.
    """
    all_train = {t.id: t for t in adapter.tasks("all")}
    tasks = [all_train[tid] for tid in task_ids if tid in all_train]
    out_dir = run_dir.rollouts / "train"
    out_dir.mkdir(parents=True, exist_ok=True)

    chash = hash_candidate_dir(candidate_dir) if cache is not None else None
    scores: list[Score] = []
    run_cost, run_tokens, n_called = 0.0, 0, 0
    t0 = time.time()

    with _live(adapter, candidate_dir) as ctx:
        for task in tasks:
            cached = cache.get(chash, task.id) if cache is not None else None
            if cached is not None:
                reward = float(cached.get("reward", 0.0))
                fb = str(cached.get("feedback", ""))
                scores.append(Score(task_id=task.id, reward=reward, feedback=fb,
                                    n=1, stderr=0.0, trial_rewards=[reward],
                                    raw={"cached": True}))
                continue
            rollout = adapter.run_target(task, ctx, seed=seed)
            if rollout is None:
                rollout = Rollout(task_id=task.id, error="no rollout")
            errored = bool(getattr(rollout, "error", None))
            run_cost += float(getattr(rollout, "cost_usd", 0.0) or 0.0)
            run_tokens += int(getattr(rollout, "tokens", 0) or 0)
            sc = adapter.score(task, rollout)
            n_called += 1
            scores.append(Score(
                task_id=task.id, reward=sc.reward, feedback=sc.feedback or "",
                n=1, stderr=0.0, trial_rewards=[sc.reward],
                raw={"errored": errored,
                     "output": _short(getattr(rollout, "output", None)),
                     "trace": _short(getattr(rollout, "trace", None))},
            ))
            (out_dir / f"{task.id}__{tag}__t0.json").write_text(
                json.dumps({"input": task.input, "rollout": rollout.to_dict(),
                            "score": sc.to_dict()}, default=str),
                encoding="utf-8",
            )
            if cache is not None:
                cache.put(chash, task.id, sc.reward, sc.feedback or "")

    elapsed = time.time() - t0
    # Count ONLY rollouts actually fired (cache hits cost nothing) toward budget.
    run_dir.update_spent(metric_calls=n_called, usd=run_cost,
                         runner_tokens=run_tokens, runner_seconds=elapsed)
    result = aggregate_scores("train", scores, ks=(1,))
    result.cost_usd, result.tokens, result.seconds = run_cost, run_tokens, elapsed
    run_dir.log_event("minibatch", tag=tag, ids=list(task_ids),
                      reward=result.reward, fired=n_called,
                      cached=len(task_ids) - n_called)
    return result


def _short(x, n: int = 1500) -> str:
    if x is None:
        return ""
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    return s if len(s) <= n else s[:n] + " …[truncated]"


def _sum_reward(result: SplitResult) -> float:
    return sum(float(pt.get("reward", 0.0)) for pt in result.per_task)


# ---- reflective dataset + focus (files in the optimizer workdir) ----------

def _write_reflection(workdir: Path, parent_mb: SplitResult) -> str:
    """Write ``REFLECTION.md`` — GEPA's reflective dataset for the FAILING minibatch.

    Each failing task contributes its input, the agent's output/compacted
    trajectory, and the scorer's feedback. Agents read a file far better than a
    giant inlined prompt, so the rich dataset goes to disk and the prompt points at
    it. Returns a short prompt-side summary.
    """
    per = parent_mb.per_task
    failing = [pt for pt in per if (pt.get("reward", 0) or 0) < 1.0]
    passing = [pt for pt in per if (pt.get("reward", 0) or 0) >= 1.0]
    actionable = [pt for pt in failing if not (pt.get("raw") or {}).get("errored")]
    errored = [pt for pt in failing if (pt.get("raw") or {}).get("errored")]

    lines = [
        "# Reflective dataset (GEPA)",
        "",
        f"Parent minibatch reward: {parent_mb.reward:.3f} "
        f"({len(passing)}/{len(per)} sampled tasks pass). Below are the FAILING "
        "tasks with the agent's actual output/trajectory and the scorer's feedback. "
        "Diagnose the COMMON root cause and edit the capability to fix the general "
        "pattern — not one task.",
        "",
    ]
    if errored:
        ids = ", ".join(str(pt.get("task_id")) for pt in errored[:25])
        lines += [
            f"## Ignore — {len(errored)} task(s) failed with run/infra errors",
            "Environment noise (a flaky/aborted run), not a capability problem: " + ids,
            "",
        ]
    lines.append(f"## {len(actionable)} actionable failing task(s)")
    for pt in actionable[:12]:
        raw = pt.get("raw") or {}
        lines += [
            f"### task {pt.get('task_id')}",
            f"- Agent output: {str(raw.get('output', ''))[:800]}",
        ]
        if raw.get("trace"):
            lines.append(f"- Trajectory: {str(raw.get('trace'))[:800]}")
        lines.append(f"- Feedback: {str(pt.get('feedback', ''))[:800]}")
        lines.append("")
    if not actionable:
        lines.append("- (no actionable failures sampled; pursue robustness/generalization)")
    (workdir / "REFLECTION.md").write_text("\n".join(lines), encoding="utf-8")
    return (f"{len(actionable)} actionable failing minibatch task(s); "
            "full reflective dataset in REFLECTION.md")


def _write_focus(workdir: Path, components: list[str], focus: list[str] | None) -> str:
    """Write ``FOCUS.md`` — which component(s) this iteration should edit.

    ``round_robin`` focuses one component per iteration (cycled by the caller);
    ``all`` lists every component. A targeted focus is GEPA's way of making each
    proposal a small, attributable change rather than a sprawling rewrite.
    """
    if focus is None:
        focus = components
    lines = [
        "# Component focus",
        "",
        "Edit ONLY the component(s) below this iteration (other files exist but are "
        "out of scope right now):",
        "",
    ]
    lines += [f"- {c}" for c in focus] or ["- (no components detected; edit the capability files)"]
    lines += ["", "## All components in this capability", ""]
    lines += [f"- {c}" for c in components] or ["- (none)"]
    (workdir / "FOCUS.md").write_text("\n".join(lines), encoding="utf-8")
    return ", ".join(focus) if focus else "(all)"


def _instructions(reflection_summary: str, focus_label: str, mb_ids: list[str]) -> str:
    return (
        "# GEPA reflective optimization step\n\n"
        f"Minibatch task ids: {', '.join(map(str, mb_ids))}\n"
        f"Component focus: {focus_label}\n\n"
        "Read `REFLECTION.md` (the reflective dataset over the parent's failing "
        "minibatch tasks: inputs, the agent's output/trajectory, and feedback) and "
        "`FOCUS.md` (which component(s) to edit). Diagnose the common root cause and "
        "make ONE targeted edit to the focused component(s) that should fix the "
        "general pattern.\n\n"
        f"Summary: {reflection_summary}\n"
    )


# ---- candidate pool entry --------------------------------------------------

def _entry(cid: str, candidate_dir: Path, result: SplitResult, parent: str | None) -> dict:
    """A pool/frontier entry. ``per_task`` drives the per-instance frontier; the
    full ``result`` is kept for re-prompting; ``parent`` is the lineage edge."""
    return {
        "id": cid,
        "dir": str(candidate_dir),
        "val": result.reward,
        "per_task": result.per_task,
        "result": result,
        "parent": parent,
    }


# ---- merge (system-aware crossover across complementary lineages) ---------

def _ancestors(cid: str, lineage: dict[str, str | None]) -> list[str]:
    """Chain of ancestor ids from ``cid`` up to (and including) the root."""
    out, cur = [], cid
    seen = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = lineage.get(cur)
    return out


def _find_merge_pair(frontier: list[dict], lineage: dict[str, str | None],
                     pool: list[dict] | None = None):
    """Two frontier dominators sharing a common ancestor that BOTH improved on.

    GEPA's system-aware merge crosses two complementary descendants of a shared
    ancestor (each fixed different components). We pick the first frontier pair
    whose lineages meet at a common ancestor with strictly lower val than both —
    so the merge genuinely recombines two independent gains. Returns
    ``(a, b, ancestor_id)`` or ``None``.

    The ancestor's val is looked up in the FULL ``pool`` (not just ``frontier``):
    a shared ancestor has almost always been superseded by its own children, so it
    is no longer on the frontier — looking it up in ``frontier`` alone would always
    miss and the merge would never fire. ``pool`` defaults to ``frontier`` only for
    backward compatibility with direct callers.
    """
    lookup = pool if pool is not None else frontier
    by_id = {c["id"]: c for c in frontier}
    ids = [c["id"] for c in frontier]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = by_id[ids[i]], by_id[ids[j]]
            anc_a = _ancestors(a["id"], lineage)
            anc_b = set(_ancestors(b["id"], lineage))
            common = [x for x in anc_a if x in anc_b]
            for anc in common:
                if anc in (a["id"], b["id"]):
                    continue
                av = _val_of(anc, lookup, lineage)
                if av is None:
                    continue
                if a["val"] > av and b["val"] > av:
                    return a, b, anc
    return None


def _val_of(cid: str, candidates: list[dict], lineage: dict[str, str | None]) -> float | None:
    for c in candidates:
        if c["id"] == cid:
            return c["val"]
    return None


def _build_merge(ancestor_dir: Path, a_dir: Path, b_dir: Path, dst: Path) -> dict:
    """Component-wise merge: start from the ancestor, then for each component take
    whichever descendant CHANGED it relative to the ancestor.

    If both changed the same component, keep ``a``'s version (deterministic tie).
    For a monolithic single-component capability there is nothing to recombine
    independently; the caller skips the merge gracefully in that case. Returns a
    small report of which side each component came from.
    """
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ancestor_dir, dst)
    comps = sorted(set(_components(a_dir)) | set(_components(b_dir)) | set(_components(ancestor_dir)))
    origin: dict[str, str] = {}
    for rel in comps:
        anc_f, a_f, b_f, d_f = (ancestor_dir / rel, a_dir / rel, b_dir / rel, dst / rel)
        anc_b = anc_f.read_bytes() if anc_f.exists() else None
        a_b = a_f.read_bytes() if a_f.exists() else None
        b_b = b_f.read_bytes() if b_f.exists() else None
        a_changed = a_b is not None and a_b != anc_b
        b_changed = b_b is not None and b_b != anc_b
        src_b, who = (anc_b, "ancestor")
        if a_changed:
            src_b, who = a_b, "a"
        elif b_changed:
            src_b, who = b_b, "b"
        origin[rel] = who
        if src_b is not None:
            d_f.parent.mkdir(parents=True, exist_ok=True)
            d_f.write_bytes(src_b)
    return {"origin": origin,
            "recombined": any(v == "b" for v in origin.values())
                          and any(v == "a" for v in origin.values())}


# ---- the GEPA loop ---------------------------------------------------------

def gepa_loop(
    adapter,
    *,
    run_dir: RunDir,
    optimizer: OptimizerFn,
    seed_val: SplitResult,
    max_metric_calls: int = 0,
    max_iterations: int = 50,
    minibatch_size: int = 4,
    n_trials: int = 1,
    component_selector: str = "round_robin",
    selection_strategy: str = "pareto_per_instance",
    max_merges: int = 2,
    merge_cadence: int = 3,
    gate_kwargs: dict | None = None,
    no_regression: bool = False,
    seed: int = 0,
    store=None,
) -> dict:
    """Run GEPA's sample-efficient reflective Pareto loop.

    Parameters
    ----------
    seed_val : the baseline candidate's full val ``SplitResult`` (it is already
        eval'd on val; the loop seeds the pool/frontier from it without re-scoring).
    max_metric_calls : PRIMARY budget — total rollouts (minibatch + full-val).
        ``0`` means unlimited (then ``max_iterations`` bounds the run).
    max_iterations : SECONDARY cap on propose→gate iterations.
    minibatch_size : train ids sampled per iteration for the cheap local gate.
    component_selector : ``round_robin`` (one component/iteration) or ``all``.
    selection_strategy : frontier parent picker (default ``pareto_per_instance``,
        frequency-weighted as GEPA prescribes).
    max_merges / merge_cadence : system-aware merge budget + how often to attempt
        a merge (every Nth accept).

    Returns a result dict in the same shape as ``hill_climb_loop`` /
    ``hill_climb_loop`` (plus GEPA-specific fields). The run's ``best_id`` is set to the
    highest-val pool member; the test split is never touched.
    """
    gate_kwargs = dict(gate_kwargs or {})
    rejected, history, store = _init_memory_store(run_dir, store)
    cache = EvalCache(run_dir.root / "eval_cache.json")
    rng = random.Random(seed)
    run_dir.log_event("gepa_start", seed=seed, minibatch_size=minibatch_size,
                      max_metric_calls=max_metric_calls, max_iterations=max_iterations,
                      component_selector=component_selector,
                      selection_strategy=selection_strategy)

    seed_dir = run_dir.candidate_dir("seed")
    pool: list[dict] = [_entry("seed", seed_dir, seed_val, parent=None)]
    lineage: dict[str, str | None] = {"seed": None}
    train_ids = list(run_dir.read_splits().train) or list(run_dir.read_splits().val)

    steps: list[dict] = []
    accepts = 0
    merges_done = 0
    comp_cursor = 0  # round-robin pointer over the parent's components

    def _budget_left() -> tuple[bool, str]:
        exhausted, why = run_dir.budget_exhausted()
        if exhausted:
            return False, why
        if max_metric_calls and run_dir.spent.metric_calls >= max_metric_calls:
            return False, f"max_metric_calls reached ({run_dir.spent.metric_calls}/{max_metric_calls})"
        if max_iterations and len(steps) >= max_iterations:
            return False, f"max_iterations reached ({len(steps)}/{max_iterations})"
        return True, ""

    while True:
        ok, why = _budget_left()
        if not ok:
            break

        # 2. select a parent from the per-instance frontier (frequency-weighted).
        sel_seed = rng.randrange(2 ** 31)
        ranked, _ = selection.pick(pool, selection_strategy, seed=sel_seed)
        parent = ranked[0]
        run_dir.log_event("gepa_select", parent=parent["id"], strategy=selection_strategy,
                          sel_seed=sel_seed, pool=len(pool))
        parent_dir = Path(parent["dir"])

        # 3. sample a minibatch of TRAIN ids.
        mb = _sample_minibatch(train_ids, minibatch_size, rng)
        if not mb:
            run_dir.log_event("gepa_stop", reason="no train ids for minibatch")
            why = why or "no train ids for minibatch"
            break

        # 4. eval parent on the minibatch (cheap, cached, traced).
        parent_mb = _eval_minibatch(adapter, parent_dir, mb, run_dir=run_dir,
                                    cache=cache, tag=f"mb_p_{len(steps):04d}", seed=seed)

        # 5. build the reflective dataset + component focus, then optimize a child.
        cid = f"gepa_{len(steps) + 1:04d}"
        workdir = run_dir.root / "work" / cid
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(parent_dir, workdir)

        comps = _components(workdir)
        if component_selector == "round_robin" and comps:
            focus = [comps[comp_cursor % len(comps)]]
            comp_cursor += 1
        else:
            focus = None  # 'all'
        refl_summary = _write_reflection(workdir, parent_mb)
        focus_label = _write_focus(workdir, comps, focus)
        instructions = _instructions(refl_summary, focus_label, mb)
        instructions = _augment_instructions(instructions, workdir, run_dir, rejected, history)

        opt_error = None
        opt_cost_usd, opt_tokens = 0.0, 0
        _t0 = time.time()
        try:
            opt_report = optimizer(workdir, instructions)
            if isinstance(opt_report, dict):
                opt_cost_usd = float(opt_report.get("cost_usd") or 0.0)
                opt_tokens = int(opt_report.get("tokens") or 0)
        except Exception as e:  # noqa: BLE001
            opt_error = str(e)
            run_dir.log_event("optimizer_error", candidate=cid, error=opt_error[:500])
        run_dir.update_spent(optimizer_seconds=time.time() - _t0, optimizer_usd=opt_cost_usd,
                             optimizer_tokens=opt_tokens)

        # 6. eval child on the SAME minibatch; cheap LOCAL gate sum(child)>sum(parent).
        child_mb = _eval_minibatch(adapter, workdir, mb, run_dir=run_dir,
                                   cache=cache, tag=f"mb_c_{len(steps):04d}", seed=seed)
        local_pass = _sum_reward(child_mb) > _sum_reward(parent_mb)
        run_dir.log_event("gepa_local_gate", candidate=cid, parent=parent["id"],
                          child_sum=_sum_reward(child_mb), parent_sum=_sum_reward(parent_mb),
                          passed=local_pass)

        step: dict = {
            "candidate_id": cid, "parent_id": parent["id"], "minibatch": mb,
            "parent_mb": parent_mb.reward, "child_mb": child_mb.reward,
            "local_gate": local_pass, "accepted": False, "optimizer_error": opt_error,
            "focus": focus_label, "workdir": str(workdir),
        }

        if not local_pass:
            # Cheap rejection — no full-val spend. Record it for memory + audit.
            run_dir.update_spent(iterations=1, accepted=False)
            rejected.add(cid, f"candidate {cid} (mb {child_mb.reward:.3f} vs parent "
                              f"{parent_mb.reward:.3f})",
                         "local minibatch gate: sum(child) <= sum(parent)", child_mb.reward)
            if store is not None:
                store.commit(f"iter {len(steps)+1}: reject(local) {cid}", accepted=False)
            steps.append(step)
            run_dir.record_spend_warnings()
            continue

        # 7. local gate PASSED → pay for full val + the honest significance gate.
        parent_result: SplitResult = parent["result"]
        decision_dict, accepted, cand_val = _full_val_gate(
            adapter, run_dir=run_dir, workdir=workdir, parent_result=parent_result,
            cid=cid, n_trials=n_trials, gate_kwargs=gate_kwargs,
            no_regression=no_regression, parent_id=parent["id"],
        )
        step["decision"] = decision_dict
        step["candidate_val"] = cand_val.to_dict()
        step["accepted"] = accepted
        run_dir.update_spent(iterations=1, accepted=accepted)

        summary = (f"candidate {cid} (val {cand_val.reward:.3f}, "
                   f"Δ {cand_val.reward - parent_result.reward:+.3f})")
        if accepted:
            run_dir.snapshot(cid, workdir)
            child_dir = run_dir.candidate_dir(cid)
            pool.append(_entry(cid, child_dir, cand_val, parent=parent["id"]))
            lineage[cid] = parent["id"]
            history.add(cid, summary, cand_val.reward)
            accepts += 1
            if store is not None:
                store.commit(f"iter {len(steps)+1}: ACCEPT {summary}", tag="best", accepted=True)
        else:
            rejected.add(cid, summary, decision_dict.get("reason", "val gate"), cand_val.reward)
            if store is not None:
                store.commit(f"iter {len(steps)+1}: reject(val) {summary}", accepted=False)
        steps.append(step)
        run_dir.record_spend_warnings()

        # 10. system-aware merge (gated by cadence + budget).
        if (accepted and merges_done < max_merges and accepts % max(1, merge_cadence) == 0):
            merge_step = _try_merge(
                adapter, run_dir=run_dir, pool=pool, lineage=lineage, cache=cache,
                mb_size=minibatch_size, rng=rng, n_trials=n_trials,
                gate_kwargs=gate_kwargs, no_regression=no_regression,
                store=store, history=history, rejected=rejected, train_ids=train_ids,
                idx=len(steps), seed=seed,
            )
            if merge_step is not None:
                steps.append(merge_step)
                merges_done += 1
                if merge_step.get("accepted"):
                    accepts += 1

    best = max(pool, key=lambda c: c["val"])
    run_dir.set_best(best["id"])
    _, why2 = run_dir.budget_exhausted()
    return {
        "algorithm": "gepa",
        "best_id": best["id"],
        "best_val": best["val"],
        "frontier_size": len(selection.pareto_frontier(pool)),
        "pool_size": len(pool),
        "iterations": len(steps),
        "accepts": accepts,
        "merges": merges_done,
        "metric_calls": run_dir.spent.metric_calls,
        "stop_reason": why or why2 or "max_iterations",
        "steps": steps,
    }


def _sample_minibatch(train_ids: list[str], size: int, rng: random.Random) -> list[str]:
    if not train_ids:
        return []
    k = min(max(1, size), len(train_ids))
    return rng.sample(train_ids, k)


def _full_val_gate(
    adapter, *, run_dir: RunDir, workdir: Path, parent_result: SplitResult,
    cid: str, n_trials: int, gate_kwargs: dict, no_regression: bool,
    parent_id: str | None = None,
) -> tuple[dict, bool, SplitResult]:
    """Full-val eval + the honest significance gate (the same path ``run_step``
    uses, replicated WITHOUT bypassing gate/seal).

    We don't call ``run_step`` because it re-runs the optimizer and re-copies the
    parent; here the child already exists in ``workdir`` (the optimizer ran in the
    minibatch stage). So we eval the existing child on full val and apply the
    identical paired/significance gate + optional no-regression dual gate.
    """
    cand_val = evaluate_candidate(adapter, workdir, run_dir=run_dir, split="val",
                                  n_trials=n_trials, tag=cid)
    gk = dict(gate_kwargs or {})
    paired = _paired_deltas(parent_result, cand_val)
    if "mode" not in gk and paired is not None:
        gk["mode"] = "paired"
    decision = gate_mod.decide(
        parent_result.reward, cand_val.reward, split="val",
        candidate_stderr=cand_val.stderr, current_stderr=parent_result.stderr,
        paired_deltas=paired, run_dir=run_dir, **gk,
    )
    accepted = decision.accept
    if accepted and no_regression:
        eps = 1e-9
        pr = {pt["task_id"]: pt.get("reward", 0.0) for pt in parent_result.per_task}
        cr = {pt["task_id"]: pt.get("reward", 0.0) for pt in cand_val.per_task}
        regressions = sorted(t for t, v in pr.items() if cr.get(t, 0.0) < v - eps)
        if regressions:
            accepted = False
            decision.reason += f"; REJECTED by no-regression gate (broke {regressions})"
    run_dir.log_event("gepa_val_gate", candidate=cid, accept=accepted,
                      reason=decision.reason, val=cand_val.reward,
                      parent=parent_id, parent_val=parent_result.reward)
    return decision.to_dict(), accepted, cand_val


def _try_merge(
    adapter, *, run_dir: RunDir, pool: list[dict], lineage: dict[str, str | None],
    cache: EvalCache, mb_size: int, rng: random.Random, n_trials: int,
    gate_kwargs: dict, no_regression: bool, store, history, rejected,
    train_ids: list[str], idx: int, seed: int,
) -> dict | None:
    """Find a complementary frontier pair, build a component-wise merge, minibatch-
    gate it (>= max(parents) on the minibatch), then full-val + standard gate.

    Returns a step dict (or ``None`` if no eligible pair / nothing to recombine).
    """
    frontier = selection.pareto_frontier(pool)
    if len(frontier) < 2:
        return None
    pair = _find_merge_pair(frontier, lineage, pool=pool)
    if pair is None:
        return None
    a, b, anc = pair
    by_id = {c["id"]: c for c in pool}
    anc_dir = Path(by_id[anc]["dir"]) if anc in by_id else run_dir.candidate_dir(anc)
    mid = f"merge_{idx + 1:04d}"
    workdir = run_dir.root / "work" / mid
    report = _build_merge(anc_dir, Path(a["dir"]), Path(b["dir"]), workdir)
    if not report.get("recombined"):
        # Monolithic / single-side change — nothing independent to merge. Skip.
        run_dir.log_event("gepa_merge_skip", a=a["id"], b=b["id"], ancestor=anc,
                          reason="no independent components to recombine")
        shutil.rmtree(workdir, ignore_errors=True)
        return None

    mb = _sample_minibatch(train_ids, mb_size, rng)
    merged_mb = _eval_minibatch(adapter, workdir, mb, run_dir=run_dir, cache=cache,
                                tag=f"mb_merge_{idx:04d}", seed=seed)
    a_mb = _eval_minibatch(adapter, Path(a["dir"]), mb, run_dir=run_dir, cache=cache,
                           tag=f"mb_ma_{idx:04d}", seed=seed)
    b_mb = _eval_minibatch(adapter, Path(b["dir"]), mb, run_dir=run_dir, cache=cache,
                           tag=f"mb_mb_{idx:04d}", seed=seed)
    local_ok = _sum_reward(merged_mb) >= max(_sum_reward(a_mb), _sum_reward(b_mb))
    run_dir.log_event("gepa_merge_local", candidate=mid, a=a["id"], b=b["id"],
                      ancestor=anc, merged_sum=_sum_reward(merged_mb),
                      a_sum=_sum_reward(a_mb), b_sum=_sum_reward(b_mb), passed=local_ok)
    step = {"candidate_id": mid, "merge_of": [a["id"], b["id"]], "ancestor": anc,
            "origin": report["origin"], "local_gate": local_ok, "accepted": False}
    if not local_ok:
        rejected.add(mid, f"merge {a['id']}+{b['id']}", "merge local gate: < max(parents)")
        if store is not None:
            store.commit(f"merge {mid}: reject(local)", accepted=False)
        shutil.rmtree(workdir, ignore_errors=True)
        return step

    # Compare the merge against the BETTER parent on full val (the honest gate).
    base_parent = a if a["val"] >= b["val"] else b
    decision_dict, accepted, cand_val = _full_val_gate(
        adapter, run_dir=run_dir, workdir=workdir, parent_result=base_parent["result"],
        cid=mid, n_trials=n_trials, gate_kwargs=gate_kwargs, no_regression=no_regression,
        parent_id=base_parent["id"],
    )
    step["decision"] = decision_dict
    step["candidate_val"] = cand_val.to_dict()
    step["accepted"] = accepted
    run_dir.update_spent(iterations=1, accepted=accepted)
    summary = f"merge {mid} of {a['id']}+{b['id']} (val {cand_val.reward:.3f})"
    if accepted:
        run_dir.snapshot(mid, workdir)
        pool.append(_entry(mid, run_dir.candidate_dir(mid), cand_val, parent=base_parent["id"]))
        lineage[mid] = base_parent["id"]
        history.add(mid, summary, cand_val.reward)
        if store is not None:
            store.commit(f"merge {mid}: ACCEPT {summary}", tag="best", accepted=True)
    else:
        rejected.add(mid, summary, decision_dict.get("reason", "val gate"), cand_val.reward)
        if store is not None:
            store.commit(f"merge {mid}: reject(val)", accepted=False)
    return step
