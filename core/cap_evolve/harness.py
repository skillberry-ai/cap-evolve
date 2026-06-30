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
    has_run_trials = hasattr(adapter, "run_trials")

    # collect per-task trial rewards (+ last rollout/score) across trials
    per_task_trials: dict[str, list[float]] = {t.id: [] for t in tasks}
    per_task_feedback: dict[str, str] = {t.id: "" for t in tasks}
    per_task_errored: dict[str, bool] = {t.id: False for t in tasks}  # any trial an infra error?
    per_task_errored_trials: dict[str, int] = {t.id: 0 for t in tasks}  # how many trials errored
    task_by_id = {t.id: t for t in tasks}
    run_acc = {"cost": 0.0, "tokens": 0}    # RUNNER spend, summed over rollouts (mutable for closure)
    t0 = time.time()

    def _persist_trial(k: int, rollouts_for_k: dict) -> None:
        """Score + persist one trial's rollouts. The single source of truth for
        per-trial scoring/persistence/accumulation — called identically by the
        per-trial loop and the adapter.run_trials batch branch, so pass^k/SE and the
        on-disk t{k}.json files are byte-for-byte equivalent regardless of path."""
        for tid, task in task_by_id.items():
            rollout = rollouts_for_k.get(tid)
            if rollout is None:
                # A trial omitted this task (an error/timeout inside the runner).
                # Record it as a failed rollout (reward 0) — do NOT serially re-run
                # it here, which would add a slow tail to every batch evaluation.
                rollout = Rollout(task_id=tid, error="omitted from batch result")
            if getattr(rollout, "error", None):
                per_task_errored[tid] = True
                per_task_errored_trials[tid] += 1
            run_acc["cost"] += float(getattr(rollout, "cost_usd", 0.0) or 0.0)
            run_acc["tokens"] += int(getattr(rollout, "tokens", 0) or 0)
            sc = adapter.score(task, rollout)
            per_task_trials[tid].append(sc.reward)
            per_task_feedback[tid] = sc.feedback or per_task_feedback[tid]
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

    baseline_data = json.loads(prior_baseline.read_text(encoding="utf-8"))
    result = SplitResult.from_dict(baseline_data["val"])
    run_dir.log_event("baseline_reused", prior_run_dir=str(prior),
                      val=result.reward, stderr=result.stderr)
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
            raise RuntimeError(
                f"optimizer failed ({proc.returncode}): {_optimizer_failure_detail(proc)}")
        # Capture optimizer spend (cost_usd/tokens) from run-optimizer's JSON payload
        # so it counts against the budget and shows in the dashboard. Returns None
        # when the agent CLI emitted no structured cost (spend stays unmeasured).
        return _parse_optimizer_cost(proc.stdout)
    return _run


def _optimizer_failure_detail(proc: "subprocess.CompletedProcess") -> str:
    """Best-effort human-readable reason a failed optimizer subprocess gives.

    The optimizer runner (``run-optimizer``) reports the underlying agent CLI's
    real output as a JSON object on **stdout** (``stderr_tail``/``stdout_tail``),
    while its own stderr is usually empty. Prefer that detail so the
    ``optimizer_error`` event (and the dashboard) explains *why* it failed
    instead of an empty ``failed (1):``.
    """
    detail = (proc.stderr or "").strip()
    out = (proc.stdout or "").strip()
    if out:
        try:
            import json as _json
            info = _json.loads(out.splitlines()[-1])
            tail = str(info.get("stderr_tail") or info.get("stdout_tail") or "").strip()
            if tail:
                detail = f"{detail} {tail}".strip() if detail else tail
            elif not detail:
                detail = out[-2000:]
        except Exception:  # noqa: BLE001 — stdout wasn't the runner's JSON
            if not detail:
                detail = out[-2000:]
    return (detail or "no output from optimizer")[:2000]


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




# The optimizer's working dir carries FOUR cross-iteration files, with clean ownership
# so there is never confusion about who writes what (the recurring user complaint about
# the old MEMORY.md/STATE.md pair):
#   LEDGER.md   — FRAMEWORK-owned, FACTUAL, regenerated each iter (the objective record:
#                 per-iteration outcomes + the exact tasks each candidate broke/fixed).
#   JOURNAL.md  — OPTIMIZER-owned, JUDGMENT, append-only across the WHOLE run (what was
#                 tried, what worked, what regressed, refuted hypotheses, focus-next).
#   PROCESS.md  — OPTIMIZER-owned, EXPLAINABILITY, fresh each iter, snapshotted with the
#                 candidate (how this iteration was done: ranked issues, edits, verify,
#                 subagents/features used, what to preserve).
#   RUNMAP.md   — FRAMEWORK-owned manifest of every prior iteration's working dir, with
#                 each prior PROCESS.md + capability diff copied into ./prior_iterations/.
# Rule: FACTS are deterministic + framework-owned; JUDGMENT and PROCESS are agent-owned.

_JOURNAL_MARK = "<!-- cap-evolve:journal-append-below — add your Iteration entry under this line; do not edit anything above it -->"

_JOURNAL_SEED = (
    "# JOURNAL — optimizer handover (append-only, whole run)\n\n"
    "YOU (the optimizer) own this file. It is the running, accumulating handover across "
    "ALL iterations — accepted AND rejected — and it is NEVER reset. Each iteration you "
    "APPEND one new entry at the bottom (under the marker line); you do NOT edit or "
    "delete earlier entries. Read the whole journal before proposing, so you build on "
    "EVERY prior attempt (not just the last accepted one) and never re-test a refuted "
    "idea.\n\n"
    "You CANNOT know your own gate result while you write — the harness scores you AFTER "
    "you stop and stamps a **RESULT** line (outcome + Δ + the EXACT tasks you broke/fixed) "
    "right below your entry. So do NOT write 'what worked' as a guess. To learn what "
    "actually worked, READ the framework RESULT lines of prior entries (and LEDGER.md): an "
    "entry whose RESULT says `rejected` with `broke={...}` tells you which specific edits to "
    "drop or redesign — its diff.patch is in ./prior_iterations/<id>/.\n\n"
    "Append your entry for THIS iteration below the marker, using this shape (INTENT only — "
    "the framework appends the RESULT):\n\n"
    "    ## Iteration <your candidate id> — <one-line headline of what you tried>\n"
    "    - Changes I made (1 line per edit; name the file/tool + cluster it targets):\n"
    "    - Per change, the EXPECTED effect + why it's safe (which failing task it should fix;\n"
    "      why no passing task changes behavior):\n"
    "    - Building on prior RESULTS: which prior entries' broke/fixed I used, and what I\n"
    "      did NOT re-try because a prior RESULT showed it regressed (cite ids):\n"
    "    - Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test):\n"
    "    - High-value clusters still NOT cracked (and the guard/tool designs already tried):\n"
    "    - Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch\n"
    "      to — e.g. a NEW composite tool instead of another guard, or prompt instead of code):\n"
    "    - Focus next iteration:\n"
)

_PROCESS_SEED = (
    "# PROCESS — what I did this iteration (explainability; REQUIRED)\n\n"
    "Fill this in as you work. It is the human-readable record of HOW this iteration was "
    "done and is snapshotted with the candidate, so anyone — and the next iteration via "
    "./prior_iterations/ — can see your reasoning. Be concrete.\n\n"
    "## Ranked issue list (clusters by # failing tasks × trials, biggest first)\n"
    "| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |\n"
    "| --- | --- | --- | --- | --- | --- |\n\n"
    "## Changes made this iteration (one row per edit — aim for MULTIPLE classes, incl. a NEW tool when a cluster needs one)\n"
    "| cluster | edit class | file / tool | what & why it generalizes | protects passing? |\n"
    "| --- | --- | --- | --- | --- |\n\n"
    "## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)\n"
    "- \n\n"
    "## Process & features used\n"
    "- Subagents / worktrees / parallel features used (or: \"serial fallback because …\"):\n"
    "- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what I learned):\n\n"
    "## Good things to PRESERVE (do not let a future iteration undo these)\n"
    "- \n\n"
    "## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)\n"
    "- \n"
)


# State/handover files that are NOT part of the capability — excluded from any
# capability diff (kept in one place; mirrors dashboard._DIFF_SKIP).
_CAP_DIFF_SKIP = {"INSTRUCTIONS.md", "MEMORY.md", "STATE.md",
                  "LEDGER.md", "JOURNAL.md", "PROCESS.md", "RUNMAP.md"}


def _capability_files(d: Path) -> dict[str, str]:
    """Read a candidate snapshot's capability files (text), skipping injected scratch.

    Same source + skip-list the dashboard's ``build_diffs`` uses, so a diff built here
    shows only the real capability edit (not trajectories/guidance/state files)."""
    out: dict[str, str] = {}
    if not d.exists():
        return out
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(d))
        top = rel.split("/", 1)[0]
        if rel in _CAP_DIFF_SKIP or top in ("trajectories", "guidance", "prior_iterations"):
            continue
        try:
            out[rel] = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return out


def _diff_capabilities(parent_dir: Path, cand_dir: Path, *, max_chars: int = 8000) -> str:
    """Unified diff of capability files between a parent and candidate snapshot."""
    import difflib
    pf, cf = _capability_files(parent_dir), _capability_files(cand_dir)
    blocks: list[str] = []
    for path in sorted(set(cf) | set(pf)):
        a = pf.get(path, "").splitlines()
        b = cf.get(path, "").splitlines()
        if a == b:
            continue
        diff = "\n".join(ln for ln in difflib.unified_diff(
            a, b, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="", n=2))
        if diff.strip():
            blocks.append(diff)
    text = "\n".join(blocks)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


def _parent_map(run_dir: RunDir) -> dict[str, str]:
    """Map each candidate id -> the parent id it was forked from, from ``step`` events.

    Falls back to "seed" for any candidate whose parent is unknown. Best-effort: an
    unreadable/absent events log yields an empty map."""
    parent_of: dict[str, str] = {}
    try:
        if not run_dir.events_path.exists():
            return {}
        for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("kind") == "step" and rec.get("candidate"):
                parent_of[str(rec["candidate"])] = str(rec.get("parent") or "seed")
    except Exception:  # noqa: BLE001
        return parent_of
    return parent_of


def _per_task_rewards(run_dir: RunDir, tag: str, split: str = "val") -> dict[str, float]:
    """Per-task mean reward for ``tag``, rebuilt from persisted rollouts.

    Reuses the canonical ``split_result_from_rollouts`` so scores match the loop
    exactly (the same read the dashboard's ``_per_task_from_rollouts`` uses).
    Returns {} when no rollouts were persisted for this tag."""
    try:
        sr = split_result_from_rollouts(run_dir, tag, split)
    except Exception:  # noqa: BLE001
        return {}
    return {pt["task_id"]: float(pt.get("reward", 0.0)) for pt in (sr.per_task or [])}


def _candidate_task_impact(run_dir: RunDir, cid: str, split: str = "val",
                           parent_of: dict | None = None) -> dict | None:
    """Per-task reward Δ of candidate ``cid`` vs its PARENT, from rollouts.

    Returns ``{"broke": [...], "fixed": [...], "delta": float}`` where ``broke`` are
    tasks that were PASSING (reward ≈ 1) under the parent and DROPPED under the
    candidate, and ``fixed`` are tasks that were failing under the parent and now
    PASS. ``delta`` is the mean per-task reward change over shared tasks. Returns
    ``None`` when either side has no rollouts on disk (nothing to compare)."""
    parent_of = parent_of if parent_of is not None else _parent_map(run_dir)
    parent_id = parent_of.get(cid, "seed")
    cand = _per_task_rewards(run_dir, cid, split)
    par = _per_task_rewards(run_dir, parent_id, split)
    if not cand or not par:
        return None
    shared = [t for t in cand if t in par]
    if not shared:
        return None
    eps = 1e-9
    broke = sorted(t for t in shared
                   if par[t] >= 1.0 - eps and cand[t] < par[t] - eps)
    fixed = sorted(t for t in shared
                   if par[t] < 1.0 - eps and cand[t] >= 1.0 - eps)
    delta = sum(cand[t] - par[t] for t in shared) / len(shared)
    return {"broke": broke, "fixed": fixed, "delta": delta, "parent": parent_id}


def _journal_tail(workdir: Path) -> str:
    """The optimizer-authored text APPENDED below the journal marker this iteration.

    The harness seeds ``workdir/JOURNAL.md`` with the accumulated run journal ending in
    ``_JOURNAL_MARK``; the optimizer appends its new ``## Iteration …`` entry below it.
    This returns just that appended tail (trimmed), or "" when nothing was appended."""
    path = workdir / "JOURNAL.md"
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""
    if _JOURNAL_MARK in text:
        # Everything after the FIRST marker is the optimizer's new entry. Split on the
        # FIRST (not last) marker so a stray duplicate marker the optimizer may paste
        # inside its own entry doesn't truncate the entry to "".
        tail = text.split(_JOURNAL_MARK, 1)[1].strip()
    else:
        # Optimizer rewrote the file (no marker) — fall back to its last ## Iteration block.
        idx = text.rfind("\n## ")
        tail = text[idx:].strip() if idx != -1 else ""
    # Strip any marker the optimizer copied into its entry text.
    return tail.replace(_JOURNAL_MARK, "").strip()


def _latest_journal_note(workdir: Path, *, max_chars: int = 900) -> str | None:
    """The newest journal entry, capped — stored in the factual ledger as the candidate's
    one-line lineage note. Returns ``None`` when the optimizer appended nothing."""
    tail = _journal_tail(workdir)
    if not tail:
        return None
    if len(tail) > max_chars:
        tail = tail[:max_chars].rstrip() + " …"
    return tail


def _build_ledger(workdir: Path, run_dir: RunDir, rejected, history) -> None:
    """Write the FACTUAL, framework-owned LEDGER.md: one row per prior iteration with
    its outcome + the exact tasks it broke/fixed. Deterministic — the objective record;
    the optimizer's own narrative lives in JOURNAL.md."""
    parent_of = _parent_map(run_dir)
    # Outcome per candidate from step events (accept/reject + val + parent).
    rows: list[dict] = []
    try:
        if run_dir.events_path.exists():
            for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("kind") == "step" and rec.get("candidate"):
                    rows.append(rec)
    except Exception:  # noqa: BLE001
        rows = []

    table = ["| iter | candidate | parent | outcome | val | Δ vs parent | broke (were passing) | fixed |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, rec in enumerate(rows, 1):
        cid = str(rec.get("candidate"))
        par = str(rec.get("parent") or "seed")
        outcome = "ACCEPT" if rec.get("accept") else "reject"
        val = rec.get("val")
        pval = rec.get("parent_val")
        d = (f"{val - pval:+.3f}" if isinstance(val, (int, float))
             and isinstance(pval, (int, float)) else "")
        imp = _candidate_task_impact(run_dir, cid, "val", parent_of=parent_of) or {}
        broke = "{" + ", ".join(str(t) for t in (imp.get("broke") or [])[:20]) + "}"
        fixed = "{" + ", ".join(str(t) for t in (imp.get("fixed") or [])[:20]) + "}"
        vstr = f"{val:.3f}" if isinstance(val, (int, float)) else ""
        table.append(f"| {i} | {cid} | {par} | {outcome} | {vstr} | {d} | {broke} | {fixed} |")
    if len(table) == 2:
        table.append("| — | (baseline only) | — | — | — | — | {} | {} |")

    best = run_dir.best_id or "seed"
    text = (
        "# LEDGER — factual run record (framework-maintained; READ-ONLY)\n\n"
        "The objective record of every iteration: which candidate, its parent, whether the "
        "gate ACCEPTED it, the val reward + Δ, and the EXACT tasks it broke / fixed. Facts "
        "only — your own narrative, lessons, and refuted hypotheses go in JOURNAL.md. Use "
        "this to never re-introduce a change that broke a task, and to see which approaches "
        "the gate accepted vs rejected.\n\n"
        "## Iterations\n" + "\n".join(table) + "\n\n"
        f"## Current best: {best}\n"
    )
    (workdir / "LEDGER.md").write_text(text, encoding="utf-8")


def _seed_journal(workdir: Path, run_dir: RunDir) -> None:
    """Copy the run-level append-only JOURNAL into the workdir (or seed it on iter 1).

    The run-level JOURNAL at ``run_dir.root/JOURNAL.md`` accumulates across ALL
    iterations (accepted and rejected). We copy it into the workdir so the optimizer
    reads the full handover history; it appends its new entry below ``_JOURNAL_MARK``,
    and ``_reconcile_journal`` folds that back into the run-level file after the step."""
    run_journal = run_dir.root / "JOURNAL.md"
    if run_journal.exists():
        try:
            text = run_journal.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            text = _JOURNAL_SEED
    else:
        text = _JOURNAL_SEED
    # The run-level file holds ONLY accumulated entries (no marker). Append the marker
    # transiently here so the optimizer appends its new entry below it; the marker is
    # stripped again when we fold the entry back into the run-level file.
    text = text.replace(_JOURNAL_MARK, "").rstrip()
    text = text + "\n\n" + _JOURNAL_MARK + "\n"
    (workdir / "JOURNAL.md").write_text(text, encoding="utf-8")


def _reconcile_journal(workdir: Path, run_dir: RunDir, cid: str, *,
                       accepted: bool, val: float, delta: float) -> None:
    """Fold the optimizer's newly-appended journal entry into the run-level JOURNAL,
    stamped with the framework's objective outcome. Append-only at the run level so the
    handover truly accumulates across accepted AND rejected iterations."""
    tail = _journal_tail(workdir)
    run_journal = run_dir.root / "JOURNAL.md"
    base = run_journal.read_text(encoding="utf-8") if run_journal.exists() else _JOURNAL_SEED
    # Run-level file is pure accumulated entries — strip any marker before appending.
    base = base.replace(_JOURNAL_MARK, "").rstrip()
    # Framework-owned RESULT: the objective gate outcome + the EXACT tasks this candidate
    # broke/fixed (vs its parent), folded VISIBLY into the journal so the next iteration
    # learns what actually worked/regressed from the narrative — not just a terse comment.
    impact = _candidate_task_impact(run_dir, cid, "val") or {}
    broke = ", ".join(str(t) for t in (impact.get("broke") or [])[:30]) or "—"
    fixed = ", ".join(str(t) for t in (impact.get("fixed") or [])[:30]) or "—"
    verdict = "ACCEPTED (new champion)" if accepted else "REJECTED (champion unchanged)"
    guidance = ("" if accepted else
                " — its WHOLE batch was reverted; re-introduce only the edits that did NOT "
                "break a task above, dropping/redesigning the ones that did.")
    stamp = (f"\n\n> **RESULT (framework, objective):** {verdict} · val={val:.3f} "
             f"Δ={delta:+.3f} · fixed={{{fixed}}} · broke={{{broke}}}.{guidance}\n"
             f"<!-- {cid}: {'ACCEPTED' if accepted else 'rejected'} "
             f"val={val:.3f} Δ={delta:+.3f} -->")
    tail = tail.strip()
    # Dedup guard: if the optimizer dropped the marker without appending (so the tail
    # fallback returned an entry already recorded in the run-level journal), do NOT
    # re-append it — that would duplicate a prior iteration's entry under this cid.
    if not tail or (tail and tail in base):
        tail = f"## Iteration {cid} — (no handover written by the optimizer)"
    new = base + "\n\n" + tail + stamp + "\n"
    try:
        run_journal.write_text(new, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        run_dir.log_event("optimizer_context_warning", what="JOURNAL.md", error=str(e)[:300])


def _build_runmap(workdir: Path, run_dir: RunDir) -> None:
    """Write RUNMAP.md + copy every prior iteration's PROCESS.md + capability diff into
    ``workdir/prior_iterations/<cid>/`` so the optimizer has REAL in-dir access to all
    prior iterations' working dirs (not just the parent's trajectories)."""
    parent_of = _parent_map(run_dir)
    rows: list[dict] = []
    try:
        if run_dir.events_path.exists():
            for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("kind") == "step" and rec.get("candidate"):
                    rows.append(rec)
    except Exception:  # noqa: BLE001
        rows = []

    prior_root = workdir / "prior_iterations"
    table = ["| iter | candidate | parent | outcome | val | ./prior_iterations/<id>/ |",
             "| --- | --- | --- | --- | --- | --- |"]
    for i, rec in enumerate(rows, 1):
        cid = str(rec.get("candidate"))
        par = str(rec.get("parent") or "seed")
        outcome = "ACCEPT" if rec.get("accept") else "reject"
        val = rec.get("val")
        vstr = f"{val:.3f}" if isinstance(val, (int, float)) else ""
        # Copy this prior iteration's PROCESS.md + diff-vs-parent into the workdir.
        dst = prior_root / cid
        try:
            dst.mkdir(parents=True, exist_ok=True)
            proc = run_dir.candidate_dir(cid) / "PROCESS.md"
            if proc.is_file():
                shutil.copyfile(proc, dst / "PROCESS.md")
            diff = _diff_capabilities(run_dir.candidate_dir(par), run_dir.candidate_dir(cid))
            if diff.strip():
                (dst / "diff.patch").write_text(diff, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning",
                              what=f"prior_iterations/{cid}", error=str(e)[:300])
        present = [n for n in ("PROCESS.md", "diff.patch") if (dst / n).exists()]
        have = " + ".join(present) if present else "(none)"
        table.append(f"| {i} | {cid} | {par} | {outcome} | {vstr} | {have} |")
    if len(table) == 2:
        table.append("| — | (no prior iterations yet) | — | — | — | — |")

    text = (
        "# RUNMAP — every prior iteration's working dir (read these before proposing)\n\n"
        "For each prior iteration, its artifacts are copied into "
        "`./prior_iterations/<candidate>/`:\n"
        "- `PROCESS.md` — what that iteration did (ranked issues, changes, verify-the-fix, process)\n"
        "- `diff.patch` — the EXACT capability edit it made vs its parent\n\n"
        f"The live run dir (read-only) is at `{run_dir.root}` if you need "
        "`rollouts/<split>/` traces or the git log.\n\n"
        + "\n".join(table) + "\n\n"
        "Before proposing, read the PROCESS.md + diff.patch of the prior iterations that "
        "targeted the SAME cluster you are about to work on — so you BUILD ON them rather "
        "than repeat a rejected or already-tried edit. Cross-reference LEDGER.md for which "
        "of them the gate accepted vs rejected, and JOURNAL.md for the lessons.\n"
    )
    (workdir / "RUNMAP.md").write_text(text, encoding="utf-8")


def _augment_instructions(instructions: str, workdir: Path, run_dir: RunDir,
                          rejected, history) -> str:
    """Give the optimizer its four cross-iteration files + a prompt pointer to each.

    Clean ownership (see the file-header comment near ``_JOURNAL_SEED``):
      - LEDGER.md  — framework-written facts (outcomes + per-task broke/fixed);
      - JOURNAL.md — optimizer-authored, append-only handover across the whole run;
      - PROCESS.md — optimizer-authored explainability, fresh each iteration;
      - RUNMAP.md + prior_iterations/ — framework manifest + copies of every prior
        iteration's PROCESS.md and capability diff (real prior-work-dir access).
    """
    _build_ledger(workdir, run_dir, rejected, history)
    _seed_journal(workdir, run_dir)
    if not (workdir / "PROCESS.md").exists():
        (workdir / "PROCESS.md").write_text(_PROCESS_SEED, encoding="utf-8")
    _build_runmap(workdir, run_dir)

    pointer = (
        "## Cross-iteration files in THIS working dir (clean ownership — read all four)\n"
        "- `LEDGER.md` — FACTS (framework, read-only): every iteration's outcome + the exact "
        "tasks it broke/fixed. Never re-introduce a change that broke a task.\n"
        "- `JOURNAL.md` — HANDOVER (yours, append-only across the whole run): read the whole "
        "thing, then APPEND your entry for this iteration below the marker line. Do NOT edit "
        "earlier entries. This is how you avoid repeating refuted ideas and hitting the same "
        "plateau.\n"
        "- `PROCESS.md` — EXPLAINABILITY (yours, REQUIRED this iteration): fill it in as you "
        "work (ranked issues, every edit + class, verify-the-fix, subagents/features used, "
        "what to preserve, what you skipped). It is snapshotted with your candidate.\n"
        "- `RUNMAP.md` + `./prior_iterations/<id>/` — every prior iteration's PROCESS.md + "
        "capability diff, copied in for you. Read the ones targeting your cluster BEFORE "
        "proposing, so you build on prior work instead of repeating it.\n"
    )
    return f"{instructions}\n\n{pointer}\n"


def _copy_step_trajectories(adapter, run_dir: RunDir, workdir: Path, split: str) -> None:
    """Copy ONLY the current best/parent candidate's per-tag rollouts for ``split``
    into ``workdir/trajectories/`` — the single step the optimizer builds on.

    The run dir's ``rollouts/<split>/`` mixes the seed plus every accepted AND
    rejected candidate's trials, so copying it wholesale would make the optimizer
    analyze stale, irrelevant trajectories. We scope to the BEST candidate's tag
    (``rollouts/<split>/*__<best_id>__t*.json``) — the parent this iteration forks
    from. Fallbacks preserve the existing "always something to read" guarantee:
      1. per-tag rollout copy for the resolved best tag (preferred — scoped);
      2. if no best tag has rollouts yet, the ``seed`` tag;
      3. if neither exists on disk, the adapter's native trajectories dir (if any);
      4. as a last resort, the whole ``rollouts/<split>/`` dir.
    The per-tag copy is preferred even when the adapter returns a native dir, because
    the native dir generally cannot be scoped to one candidate.
    """
    dst = workdir / "trajectories"

    def _copy_tag(tag: str) -> bool:
        vdir = run_dir.rollouts / split
        if not vdir.is_dir():
            return False
        files = sorted(vdir.glob(f"*__{tag}__t*.json"))
        if not files:
            return False
        try:
            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copyfile(f, dst / f.name)
            return True
        except Exception as e:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning",
                              what=f"trajectories/{tag}", error=str(e)[:300])
            return False

    # Resolve the best/parent candidate id from run state (the parent this step forks
    # from), falling back to the seed tag when no candidate has been accepted yet.
    best_id = None
    try:
        best_id = run_dir.best_id
    except Exception:  # noqa: BLE001
        best_id = None

    if best_id and _copy_tag(str(best_id)):
        return
    if _copy_tag("seed"):
        return

    # Fallbacks: adapter native dir, then the whole rollouts/<split>/ — so there is
    # ALWAYS something for the optimizer to read.
    traj_src = None
    try:
        traj_src = adapter.trajectories(split)
    except Exception:  # noqa: BLE001 — never let optional context break a step
        traj_src = None
    if not traj_src:
        traj_src = run_dir.rollouts / split
    try:
        traj_src = Path(traj_src)
        if traj_src.is_dir() and any(traj_src.iterdir()):
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(traj_src, dst)
    except Exception as e:  # noqa: BLE001
        run_dir.log_event("optimizer_context_warning", what="trajectories", error=str(e)[:300])


def _inject_optimizer_context(adapter, run_dir: RunDir, workdir: Path, *, split: str,
                              capabilities=None, optimizer_name: str | None = None,
                              capability_sources=None, project_dir: Path | None = None) -> None:
    """Give the optimizer everything it needs to read, inside its own working dir.

    Copies, VERBATIM and without parsing:
      - the CURRENT BEST/PARENT candidate's per-tag trajectories for the most recent
        ``split`` eval into ``workdir/trajectories/`` — ONLY the step the optimizer
        builds on, not the seed + every rejected candidate (see ``_copy_step_trajectories``);
      - the selected capability skill(s) into ``workdir/guidance/<cap>/`` so the
        optimizer can read the full edit-space guidance + examples without leaving
        its dir;
      - any ``capability_sources`` files (data models / types the tools import) into
        ``workdir/guidance/sources/<basename>`` so the optimizer can write correct code;
      - the diagnose phase skill into ``workdir/guidance/diagnose/`` (the
        failure-clustering method);
      - the resolved optimizer's features reference into
        ``workdir/guidance/optimizer/<optimizer_name>.md`` (parallel-subagent
        capabilities etc.), when ``optimizer_name`` is known and the file exists.
    No benchmark assumptions: the trajectory directory may be any structure / format.
    """
    # 1) trajectories (verbatim) — ONLY the current best/parent candidate's tag for
    # this split, so the optimizer analyzes the step it builds on (not seed + every
    # rejected candidate mixed together). Always preserves the "something to read"
    # guarantee via per-tag fallback then the native dir.
    _copy_step_trajectories(adapter, run_dir, workdir, split)

    # 2) capability skills as local guidance
    caps = [c for c in (capabilities or []) if c]
    if caps:
        skills_root = Path(__file__).resolve().parents[2] / "skills" / "capabilities"
        for c in caps:
            src = skills_root / c
            if not src.is_dir():
                continue
            try:
                shutil.copytree(
                    src, workdir / "guidance" / c,
                    ignore=shutil.ignore_patterns("__pycache__", "scripts", "*.pyc"),
                )
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning", what=f"guidance/{c}", error=str(e)[:300])

    # 2b) capability_sources — supporting source files (data models / types the tools
    # import) copied VERBATIM into ./guidance/sources/<basename> so the optimizer can
    # write correct code against them. Paths resolve relative to the project dir;
    # missing files are tolerated.
    sources = [s for s in (capability_sources or []) if s]
    if sources:
        sdst = workdir / "guidance" / "sources"
        for s in sources:
            try:
                sp = Path(s)
                if not sp.is_absolute() and project_dir is not None:
                    sp = Path(project_dir) / s
                if not sp.is_file():
                    continue
                sdst.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(sp, sdst / sp.name)
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning",
                                  what=f"guidance/sources/{s}", error=str(e)[:300])

    repo_root = Path(__file__).resolve().parents[2]

    # 3) the diagnose phase skill (the failure-clustering method) as local guidance.
    diag_src = repo_root / "skills" / "phases" / "diagnose"
    if diag_src.is_dir():
        try:
            dst = workdir / "guidance" / "diagnose"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                diag_src, dst,
                ignore=shutil.ignore_patterns("__pycache__", "scripts", "*.pyc"),
            )
        except Exception as e:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning", what="guidance/diagnose", error=str(e)[:300])

    # 4) the resolved optimizer's features reference (parallel subagents etc.).
    if optimizer_name:
        ref_src = (repo_root / "skills" / "optimizers" / "run-optimizer"
                   / "references" / f"{optimizer_name}.md")
        if ref_src.is_file():
            try:
                dst_dir = workdir / "guidance" / "optimizer"
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ref_src, dst_dir / f"{optimizer_name}.md")
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning",
                                  what=f"guidance/optimizer/{optimizer_name}", error=str(e)[:300])

    # 5) NATIVE per-agent skill injection. The capability + diagnose skills live under
    # ./guidance/ for every agent (above), but a headless coding-agent CLI loads skills
    # most reliably from the path it NATIVELY scans (e.g. claude-code .claude/skills/),
    # plus its always-on instructions file. Resolve the optimizer row and, when it
    # declares those paths, place the skills natively and write a pointer into the
    # instructions file. All best-effort: a missing registry / unknown agent just skips
    # native placement (./guidance/ still works).
    if optimizer_name:
        _inject_native_skills(run_dir, workdir, caps, repo_root, optimizer_name)


def _inject_native_skills(run_dir: RunDir, workdir: Path, caps, repo_root: Path,
                          optimizer_name: str) -> None:
    """Place capability + diagnose skills where ``optimizer_name`` natively discovers
    them, and write a pointer into its always-on instructions file.

    Reads ``skills/optimizers/registry.yaml`` for the per-row ``skills_dir`` /
    ``instructions_file`` fields. Wholly best-effort — any failure (missing registry,
    unknown agent, unreadable row) is logged and skipped so guidance/ remains the
    guaranteed channel.
    """
    try:
        reg_path = repo_root / "skills" / "optimizers" / "registry.yaml"
        if not reg_path.is_file():
            return
        try:
            from .specfile import read_yaml
            registry = read_yaml(reg_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return
        row = (registry.get(optimizer_name) or {}) if isinstance(registry, dict) else {}
        if not isinstance(row, dict):
            return
        skills_dir = str(row.get("skills_dir") or "").strip()
        instructions_file = str(row.get("instructions_file") or "").strip()

        cap_root = repo_root / "skills" / "capabilities"
        diag_src = repo_root / "skills" / "phases" / "diagnose"
        ignore = shutil.ignore_patterns("__pycache__", "scripts", "*.pyc")

        # Native skills dir: copy each chosen capability skill + the diagnose skill.
        if skills_dir:
            native_root = workdir / skills_dir
            for c in [x for x in (caps or []) if x]:
                src = cap_root / c
                if not src.is_dir():
                    continue
                try:
                    dst = native_root / c
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, ignore=ignore)
                except Exception as e:  # noqa: BLE001
                    run_dir.log_event("optimizer_context_warning",
                                      what=f"{skills_dir}/{c}", error=str(e)[:300])
            if diag_src.is_dir():
                try:
                    dst = native_root / "diagnose"
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(diag_src, dst, ignore=ignore)
                except Exception as e:  # noqa: BLE001
                    run_dir.log_event("optimizer_context_warning",
                                      what=f"{skills_dir}/diagnose", error=str(e)[:300])

        # Always-on instructions file: write a short, generic, idempotent pointer block.
        if instructions_file:
            try:
                _write_instructions_pointer(workdir / instructions_file, skills_dir)
            except Exception as e:  # noqa: BLE001
                run_dir.log_event("optimizer_context_warning",
                                  what=f"instructions/{instructions_file}", error=str(e)[:300])
    except Exception as e:  # noqa: BLE001 — native placement must never break a step
        run_dir.log_event("optimizer_context_warning", what="native_skills", error=str(e)[:300])


_NATIVE_POINTER_MARK = "<!-- cap-evolve:native-skills -->"


def _write_instructions_pointer(path: Path, skills_dir: str) -> None:
    """Write (or append) a short generic pointer block into the agent's instructions
    file, idempotently (keyed on a marker comment so it is not duplicated)."""
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            existing = ""
    if _NATIVE_POINTER_MARK in existing:
        return
    skills_note = (f"the optimization skills are available natively under `{skills_dir}/` and "
                   if skills_dir else "the optimization skills are available under ")
    block = (
        f"{_NATIVE_POINTER_MARK}\n"
        "## cap-evolve optimization task\n"
        "You are running as the edit proposer for a cap-evolve optimization iteration.\n"
        "Read `./INSTRUCTIONS.md` in this directory FIRST and follow it — it states the "
        "capability to improve, the failures to fix, and how your edit is judged.\n"
        f"For method/edit-space guidance, {skills_note}under `./guidance/` "
        "(capability skill(s) + the diagnose failure-clustering method).\n"
        "Cross-iteration files (clean ownership): `./LEDGER.md` (framework facts — every "
        "iteration's outcome + tasks broken/fixed), `./JOURNAL.md` (YOUR append-only "
        "handover across the whole run — append your entry below the marker), `./PROCESS.md` "
        "(YOUR required explainability for this iteration), and `./RUNMAP.md` + "
        "`./prior_iterations/<id>/` (every prior iteration's PROCESS.md + diff — read before "
        "proposing). Read all of these before you start.\n"
    )
    sep = "" if (not existing or existing.endswith("\n\n")) else ("\n" if existing.endswith("\n") else "\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing + sep + block, encoding="utf-8")


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
    capabilities=None,
    eval_split: str = "val",
    optimizer_name: str | None = None,
    capability_sources=None,
    project_dir: Path | None = None,
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

    # Give the optimizer the full trajectories + capability guidance, in its own dir.
    _inject_optimizer_context(adapter, run_dir, workdir, split=eval_split,
                              capabilities=capabilities, optimizer_name=optimizer_name,
                              capability_sources=capability_sources, project_dir=project_dir)

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

    # update optimizer memory + commit the iteration to the version store so the
    # whole process stays inspectable (git log / LEDGER / JOURNAL). The `note` is the
    # optimizer's own handover (its approach + lesson), taken from the entry it appended
    # to JOURNAL.md this iteration so the lineage record carries what was tried, not just Δ/SE.
    delta = cand_val.reward - current_val.reward
    summary = f"candidate {cid} (val {cand_val.reward:.3f}, Δ {delta:+.3f})"
    # Fold the optimizer's appended JOURNAL entry into the run-level append-only journal
    # (so handover accumulates across accepted AND rejected iterations), and reuse it as
    # the candidate's lineage note in the factual ledger.
    _reconcile_journal(workdir, run_dir, cid, accepted=accepted,
                       val=cand_val.reward, delta=delta)
    note = _latest_journal_note(workdir)
    # Per-task broke/fixed lists vs the parent (from the rollouts just persisted), so
    # MEMORY records the SPECIFIC tasks a candidate broke — not just a category — and
    # the next iteration won't retry the regression. Best-effort; None when not
    # comparable (e.g. parent rollouts absent).
    impact = _candidate_task_impact(run_dir, cid, "val",
                                    parent_of={cid: parent_id})
    if accepted:
        if history is not None:
            history.add(cid, summary, cand_val.reward, note=note, impact=impact)
    else:
        if rejected is not None:
            rejected.add(cid, summary, decision.reason, cand_val.reward, note=note, impact=impact)
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
    """Structured infra signal: did ANY of this task's trials carry ``error``?

    The harness records ``raw.errored = True`` when any trial's ``Rollout.error``
    was set (a timeout, API/run error, omitted batch result). This is the raw
    *signal* — true the moment a single trial errored. It does NOT by itself mean
    the task is uncontrollable; ``_is_infra_ignore`` adds the majority-errored +
    low-mean condition that justifies telling the optimizer to ignore the task.
    We use the STRUCTURED field — not substring-matching feedback prose, which
    dropped real "error" bugs and misfired on feedback that merely *mentions* an
    exception.
    """
    return bool((pt.get("raw") or {}).get("errored"))


def _is_infra_ignore(pt) -> bool:
    """Is this task TRULY uncontrollable (safe to tell the optimizer to ignore)?

    A task belongs in the ignore/infra bucket ONLY when MOST of its trials errored
    AND its mean reward is ≈ 0 — i.e. the failure is dominated by infrastructure
    noise, not by capability. A mostly-passing task that merely had ONE errored
    trial is solid/flaky and must be PROTECTED, never called "noise / no edit can
    fix it" — that misclassification is what let prior regressions hide.

    Trial-level data: ``raw.errored_trials`` / ``raw.n_trials`` give the exact
    counts when present. We fall back to the boolean ``raw.errored`` (any-trial
    errored) combined with the aggregate reward when the per-trial counts are not
    recorded (older rollouts), still requiring mean ≈ 0 so a passing task is never
    bucketed as ignore.
    """
    raw = pt.get("raw") or {}
    if not raw.get("errored"):
        return False
    eps = 1e-9
    mean_reward = float(pt.get("reward", 0) or 0)
    if mean_reward > eps:
        return False  # it passes (at least partially) — controllable, protect it
    errored_trials = raw.get("errored_trials")
    n_trials = raw.get("n_trials") or pt.get("n")
    if errored_trials is not None and n_trials:
        return int(errored_trials) * 2 > int(n_trials)  # strict majority errored
    # No per-trial counts: any-trial-errored + mean≈0 is the best we can do.
    return True


# Per-capability edit-space brief surfaced to the optimizer. Kept short and
# general; the long-form guidance lives in each capability skill's SKILL.md, which
# the optimizer can open via the pointer we emit. ``summary`` is read from the
# capability's meta.yaml at runtime so this never drifts from the skill.
_CAP_EDIT_SPACE = {
    "tools": "Edit tool names/descriptions, per-parameter docs, in-description examples, "
             "the JSON schema, and the handler code. HIGHEST-LEVERAGE EDIT: WRITE A NEW "
             "CODE-BEARING TOOL (a real body — loops, validation, calls to existing tools), "
             "because a deterministic tool can't be 'forgotten' the way a prompt rule can. "
             "Two patterns to prefer: (1) a VALIDATION/RULE-ENFORCEMENT tool that wraps a "
             "primitive — validate/normalize inputs, enforce a GENERAL rule, then delegate "
             "to the primitive (e.g. cancel_record_safely(id) checks cancellable then calls "
             "cancel_record), and REMOVE the raw primitive so the only path is the safe one; "
             "(2) a WORKFLOW/LOOP tool that collapses a recurring multi-step sequence or N "
             "repeated calls into ONE call with real loops (e.g. loop get_record over a list "
             "of ids). Keep the toolset LEAN — REPLACE/consolidate, don't accumulate. The "
             "body must be real code, never '...' or docstring-only. Selection is driven by "
             "the name+description; argument-filling by the parameter schema/enums.",
    "system-prompt": "Edit the prompt/policy text: instructions, decision policy, and the "
                     "output contract. Prefer sharpening rules the traces show the agent "
                     "breaking; do not just append more preamble.",
    "skill-package": "Edit the SKILL.md (frontmatter + body), its references, and bundled "
                     "scripts, staying within skill-creator rules (valid frontmatter, "
                     "progressive disclosure, one-level references, concise body).",
    "mcp-tool": "ONLY safe edits: tool/parameter documentation, in-description examples, and "
                "adding/removing tools from the exposed set. The wire schema and tool code "
                "are owned by the external server and are NOT editable here.",
}


def _capability_brief(capabilities) -> str:
    """A compact 'what you are allowed to edit' block for the optimizer prompt.

    ``capabilities`` is the list from the spec (e.g. ``["system-prompt", "tools"]``).
    For each we emit its one-line meta summary plus the allowed edit space, and a
    pointer to the full capability SKILL.md so the optimizer can use the whole
    edit space (e.g. composite tools) rather than guessing from the files alone.
    Returns "" when no capabilities are known (older callers) so behavior is additive.
    """
    caps = [c for c in (capabilities or []) if c]
    if not caps:
        return ""
    skills_root = Path(__file__).resolve().parents[2] / "skills" / "capabilities"
    lines = ["## What you are editing (the allowed edit space)",
             "The capability under optimization is composed of these editable artifact(s). "
             "Use the FULL edit space below — do not limit yourself to trivial wording tweaks."]
    for c in caps:
        summary = ""
        meta = skills_root / c / "meta.yaml"
        if meta.exists():
            for ln in meta.read_text(encoding="utf-8").splitlines():
                if ln.startswith("summary:"):
                    summary = ln.split(":", 1)[1].strip()
                    break
        edit = _CAP_EDIT_SPACE.get(c, "")
        skill_md = skills_root / c / "SKILL.md"
        lines.append(f"- **{c}** — {summary}")
        if edit:
            lines.append(f"  - Allowed edits: {edit}")
        if skill_md.exists():
            # The full skill is copied into the workdir at ./guidance/<c>/ (see
            # run_step) so the optimizer can read it without leaving its dir.
            lines.append(f"  - Full guidance (read it): ./guidance/{c}/SKILL.md")
    return "\n".join(lines)


def _algorithm_brief(current_val: SplitResult, algorithm: str) -> str:
    """How acceptance works, so the optimizer aims for a real, significant gain."""
    return (
        "## How your edit is judged\n"
        f"Algorithm: {algorithm}. Your edited candidate is re-scored on the SAME held-out "
        f"val tasks and compared to the current best (val reward {current_val.reward:.3f}). "
        "It is ACCEPTED only if the per-task improvement clears a significance bar (a noise "
        "margin), so a tiny or lucky change is rejected. Aim for a real, generalizing gain "
        "across a CLASS of failures — not a one-off patch to a single task (that overfits "
        "and gets rejected or hurts the held-out test)."
    )


def _classify(per):
    """Split focus tasks into infra-ignore / always-failing / flaky / solid.

    Uses the AGGREGATE reward (mean over trials), so a task that passes only some
    of the time is 'flaky' (0 < reward < 1) — a sometimes-good behavior to make
    CONSISTENT — distinct from an always-failing task (reward ~ 0) whose root cause
    must be fixed. (Per-task feedback is from the last trial and can disagree with a
    graded mean; the reward is the honest signal, so we classify by it.)

    The infra-IGNORE bucket is reserved for TRULY uncontrollable tasks
    (``_is_infra_ignore``: most trials errored AND mean ≈ 0). A task that merely had
    an errored trial but still mostly passes is NOT ignored — it falls through to
    solid/flaky and is therefore PROTECTED. Returns the four buckets; ``solid`` is
    the protected set callers must not regress."""
    errored = [pt for pt in per if _is_infra_ignore(pt)]
    rest = [pt for pt in per if not _is_infra_ignore(pt)]
    eps = 1e-9
    always_fail = [pt for pt in rest if (pt.get("reward", 0) or 0) <= eps]
    flaky = [pt for pt in rest if eps < (pt.get("reward", 0) or 0) < 1.0 - eps]
    solid = [pt for pt in rest if (pt.get("reward", 0) or 0) >= 1.0 - eps]
    return errored, always_fail, flaky, solid


def _fmt(pt) -> str:
    return f"- {pt.get('task_id')} (reward {float(pt.get('reward', 0) or 0):.2f}): " \
           f"{str(pt.get('feedback', '')).strip()[:400]}"


def _passing_block(solid, *, max_ids: int = 60) -> str:
    """A block listing currently-PASSING (solid, reward≈1) task ids to PROTECT.

    The optimizer is only ever shown failures; without the wins it cannot tell
    which behaviors its edit must preserve, and prior candidates fixed a few tasks
    while silently breaking many passing ones (net ≈ 0). Surfacing the passing ids
    makes non-regression a checkable, explicit constraint."""
    if not solid:
        return ""
    ids = [str(pt.get("task_id")) for pt in solid]
    shown = ", ".join(ids[:max_ids])
    more = f" … (+{len(ids) - max_ids} more)" if len(ids) > max_ids else ""
    return (
        f"## Currently PASSING ({len(solid)} task(s)) — your edit MUST NOT regress these\n"
        f"These tasks already score ~1.0. Preserve their behavior: any edit that changes "
        f"their trajectory is a regression and will be rejected. Protect: {shown}{more}\n"
    )


# The optimizer-instructions template ships in the repo as a project default and is
# what the intake phase copies + customizes per benchmark. The harness renders it by
# substituting the per-iteration dynamic blocks below; nothing benchmark-specific lives
# here. ``{{...}}`` placeholders: FOCUS_SUMMARY, FAILURES, PASSING, CAP_BRIEF, ALGO_BRIEF, BENCH_REPO.
_DEFAULT_INSTRUCTIONS_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / "project" / "optimizer" / "INSTRUCTIONS.md"
)
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
_SNAPSHOT_IGNORE = ("trajectories", "guidance", "prior_iterations",
                    "LEDGER.md", "JOURNAL.md", "RUNMAP.md",
                    ".claude", ".agents", ".gemini", ".opencode", ".bob",
                    "CLAUDE.md", "AGENTS.md", "GEMINI.md")


def _failures_block(always_fail, flaky, errored) -> str:
    """The per-iteration (a)/(b)/errored failure index for the prompt."""
    lines: list[str] = []
    if always_fail:
        lines.append(f"## (a) {len(always_fail)} ALWAYS-failing task(s) — fix the shared "
                     "root cause (full traces in ./trajectories/):")
        lines += [_fmt(pt) for pt in always_fail[:10]]
        lines.append("")
    if flaky:
        lines.append(f"## (b) {len(flaky)} FLAKY task(s) — pass sometimes; make the good "
                     "behavior consistent (full traces in ./trajectories/):")
        lines.append("(reward is the mean over trials — the honest signal; the feedback line is "
                     "from the LAST trial and may say 'passed' even when the mean is below 1.)")
        lines += [_fmt(pt) for pt in flaky[:8]]
        lines.append("")
    if not always_fail and not flaky:
        lines.append("## No actionable failures in focus — seek a robustness/generalization gain "
                     "that does not regress the solid tasks.")
        lines.append("")
    if errored:
        ids = ", ".join(str(pt.get("task_id")) for pt in errored[:25])
        lines += [
            f"## Ignore — {len(errored)} task(s) are uncontrollable infrastructure errors",
            "These tasks had MOST of their trials abort with a run/infrastructure error "
            "AND a mean reward of ~0 — truly environment noise (timeouts/aborted runs), NOT "
            "a capability problem; no edit can fix them, so do not change anything on their "
            "account: " + ids,
            "(A task that merely had one errored trial but still mostly PASSES is NOT listed "
            "here — it is solid/flaky and must be protected, not ignored.)",
            "",
        ]
    return "\n".join(lines)


def _optimizer_parallel(optimizer_name: str | None) -> bool:
    """Whether the resolved optimizer's harness can spawn parallel subagents.

    Reads the optional ``parallel: "true"`` flag from the optimizer registry row.
    Best-effort: an unknown agent / unreadable registry ⇒ False (sequential). This
    gates ONLY the parallel fan-out guidance in {{PARALLEL_NOTE}}.
    """
    if not optimizer_name:
        return False
    try:
        repo_root = Path(__file__).resolve().parents[2]
        reg_path = repo_root / "skills" / "optimizers" / "registry.yaml"
        if not reg_path.is_file():
            return False
        from .specfile import read_yaml
        registry = read_yaml(reg_path.read_text(encoding="utf-8")) or {}
        row = registry.get(optimizer_name) or {}
        return str(row.get("parallel") or "").strip().lower() == "true"
    except Exception:  # noqa: BLE001
        return False


def _parallel_note(parallel: bool, optimizer_name: str | None) -> str:
    """The {{PARALLEL_NOTE}} block — gates the fan-out on the agent's capability."""
    if parallel:
        ref = f"./guidance/optimizer/{optimizer_name}.md" if optimizer_name else "./guidance/optimizer/"
        return ("Your agent supports parallel subagents/worktrees (see " + ref + "). FAN OUT to "
                "cover MANY clusters at once: one read-only subagent per trajectory-group to "
                "diagnose, then one edit-subagent per issue (each in its own worktree), then "
                "MERGE every edit into this ONE candidate with no conflicts. This is how a single "
                "iteration fixes many issues across many trajectories, not just the biggest one.")
    return ("Your agent runs single-threaded (no subagents). Still address as MANY clusters as you "
            "can in this ONE candidate — work through them in turn, drafting and keeping every "
            "real, safe fix, not just the biggest one.")


def _focus_instructions(current_val: SplitResult, focus_ids, label: str,
                        capabilities=None, algorithm: str = "hill-climb",
                        instructions_file=None, bench_repo: str | None = None,
                        optimizer_name: str | None = None) -> str:
    """Render one iteration's INSTRUCTIONS by substituting dynamic blocks into the
    optimizer-instructions template.

    The static framing (analyze → ideate → edit, the read-pointers, the code-bearing
    tools guidance, the economy footer) lives in the template file — authored by the
    intake phase per benchmark, with a generic default shipped in ``templates/``. Only
    the per-iteration data (the focus summary, the failure index, the capability/algorithm
    briefs, the benchmark-repo pointer) is computed here and substituted.
    """
    per = current_val.per_task
    if focus_ids is not None:
        per = [pt for pt in per if pt.get("task_id") in set(focus_ids)]
    errored, always_fail, flaky, solid = _classify(per)
    n = len(per)

    focus_summary = (
        f"Focus: {label}. Current val reward {current_val.reward:.3f}: "
        f"{len(solid)} solid / {len(flaky)} flaky / {len(always_fail)} failing"
        + (f" / {len(errored)} infra-errored" if errored else "") + f" of {n} tasks."
    )
    failures = _failures_block(always_fail, flaky, errored)
    passing = _passing_block(solid)
    cap = _capability_brief(capabilities)
    algo = _algorithm_brief(current_val, algorithm)
    bench = (f"- The benchmark / runner source is at `{bench_repo}` — read-only context "
             "you may consult to understand tools, scoring, or task structure."
             if bench_repo else "")

    parallel_note = _parallel_note(_optimizer_parallel(optimizer_name), optimizer_name)
    repl = {
        "{{FOCUS_SUMMARY}}": focus_summary,
        "{{FAILURES}}": failures,
        "{{PASSING}}": passing,
        "{{CAP_BRIEF}}": cap,
        "{{ALGO_BRIEF}}": algo,
        "{{BENCH_REPO}}": bench,
        "{{PARALLEL_NOTE}}": parallel_note,
    }

    tmpl_path = Path(instructions_file) if instructions_file else _DEFAULT_INSTRUCTIONS_TEMPLATE
    tmpl = None
    try:
        if tmpl_path.exists():
            tmpl = tmpl_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        tmpl = None
    if tmpl and "{{FOCUS_SUMMARY}}" in tmpl:
        for k, v in repl.items():
            tmpl = tmpl.replace(k, v)
        return tmpl

    # Fallback (template unreadable): assemble a minimal but complete prompt so a run
    # never breaks just because the template file is missing.
    parts = [
        "# Optimize the capability — analyze this step's trajectories in ./trajectories/, "
        "then fix MANY root causes in this ONE candidate and STOP.",
        focus_summary, "",
        "FIRST read ./guidance/<cap>/SKILL.md for EVERY capability and "
        "./guidance/optimizer/<name>.md (your subagent/parallelism features) IN FULL "
        "before diagnosing. Then read ./trajectories/ (full traces), ./guidance/sources/ "
        "(data models/types — read before writing tool code), ./LEDGER.md (facts), the "
        "whole ./JOURNAL.md (handover) and ./RUNMAP.md + ./prior_iterations/; fill "
        "./PROCESS.md and APPEND your entry to ./JOURNAL.md. "
        "The prompt and the tools are equally fair game.",
        bench, "", failures, passing, cap, "", algo, "",
        "Address EVERY failure cluster you found, not just the biggest. The DEFAULT fix "
        "for a violated rule/precondition/formula is to move it INTO THE CODE BODY of the "
        "EXISTING tool it governs — an in-body validation/normalization that raises an "
        "ACTIONABLE error — NOT a docstring or prompt restatement. Editing the CODE of "
        "MANY existing tools is the expected shape of a strong iteration; adding one new "
        "tool while leaving rules as prose is the failure mode to avoid. Prose/docstring "
        "edits are reserved for genuine KNOWLEDGE gaps (a format/criterion the agent "
        "cannot derive); rule VIOLATIONS go in code. A strong iteration also ships, where "
        "useful: validation/workflow/composite tools for behavioral clusters, enriched "
        "tool returns + actionable error messages, corrected handlers, and new tools. "
        "Non-regression is a design constraint on each INDIVIDUAL fix (scope each guard "
        "so it doesn't alter a passing task's code path), NOT a reason to make fewer "
        "fixes. If you edited the BODY of fewer than ~3 EXISTING tools or converted fewer "
        "than half the rule-violations you found into in-code checks, you under-used the "
        "iteration — new tools and docstring edits do NOT count toward that bar. The "
        "measure is how MANY real clusters you fix in-code, not how much you spend.",
    ]
    return "\n".join(p for p in parts if p is not None)


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
    capabilities=None,
    instructions_file=None,
    bench_repo: str | None = None,
    optimizer_name: str | None = None,
    capability_sources=None,
    project_dir: Path | None = None,
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
        instructions = _focus_instructions(current_val, focus_ids, label,
                                            capabilities=capabilities, algorithm=algorithm,
                                            instructions_file=instructions_file,
                                            bench_repo=bench_repo, optimizer_name=optimizer_name)
        step = run_step(
            adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir(run_dir.best_id),
            optimizer=optimizer, instructions=instructions, current_val=current_val,
            n_trials=n_trials, gate_kwargs=gate_kwargs, no_regression=no_regression,
            rejected=rejected, history=history, store=store, capabilities=capabilities,
            optimizer_name=optimizer_name, capability_sources=capability_sources,
            project_dir=project_dir,
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

    _atomic_write(run_dir.root / "final.json", json.dumps(payload, indent=2))
    run_dir.commit_test()  # burn the seal ONLY now that the result(s) are computed + written
    run_dir.log_event("finalize", test_reward=result.reward,
                      test_baseline_reward=payload["test_baseline"]["reward"],
                      test_delta=payload["test_delta"], best_id=run_dir.best_id)
    return payload
