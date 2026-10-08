"""Subset (minibatch) screening for val — cheap TRIAGE that may never accept.

Why this exists: a full-val evaluation is the unit of cost in cap-evolve (``val_n ×
num_trials`` rollouts, once per candidate, per round). Most proposed edits are not
close calls — they are obviously neutral or obviously harmful — and paying full val to
learn that is the single biggest waste in a run. GEPA already solves this for train
(``gepa._eval_minibatch`` + its ``sum(child) > sum(parent)`` local gate); this module
is the same economy made **variance-aware** and pointed at val, where the honest gate
lives.

The hard rule, enforced by the caller (``scripts/screen.py`` prints
``decision: kill|promote`` and never ``accept``):

    A subset screen may KILL a candidate. It may never ACCEPT one.
    Acceptance is always the full-val paired significance gate + no-regression veto.

Two pure functions, both deterministic:

  * :func:`select_screen_subset` — which val tasks to screen on. Informative
    (currently-failing + high-variance) plus a **random holdout** of tasks the parent
    currently passes, so a screen can see a regression it would otherwise be blind to.
  * :func:`screen_decision` — kill or promote, from the paired deltas on that subset.

Both are stdlib-only and take plain dicts/lists, so they are unit-testable without a
run dir, an adapter, or a model call.

### Which way the bias runs, and why

With k≈4 tasks and one trial, the subset's SE is large and the delta vector is coarse
(values in {-1, 0, +1}). Two errors are possible and they are **not** symmetric:

  * a **false kill** throws away a genuinely good edit, and leaves no trace — the run
    just quietly fails to improve, and nothing in the artifacts says why;
  * a **false promote** costs exactly one full-val evaluation, after which the honest
    gate reaches the correct answer anyway.

So the screen is deliberately biased toward **promote**. Everything that is not a
gross failure — including "no signal at all" — promotes, and says
``inconclusive: true`` when it promoted a subset that still read net-negative, so the
reason is auditable.

### issue #684 item 5 — kill is a gross-failure check, not a significance test

**This is a deliberate behavior change, not a tuning tweak.** The old rule killed on
``mean(Δ) + k_se·SE < 0`` — i.e. it required the subset to be *statistically
significant*. Measured on a real run: tier-1 subsets were 5-11 tasks, giving SEs of
0.11-0.17, while the round deltas that actually mattered were 0.02-0.09. A screen's own
SE was ALWAYS larger than the effect it needed to resolve, so the significance bar
could structurally never clear itself — 0 screen-kills across 7 candidates in that run
(and 0/8 in an earlier one), while the screen's own rollouts cost 51 more than they
saved. A kill rule that can never fire is not a conservative gate; it is dead code with
a cost attached.

Per GEPA's own validated design (``gepa._eval_minibatch``'s local gate: did the child
beat the parent on this minibatch, yes or no — no significance test, because the
EXPENSIVE full eval is the real decision point, not the cheap gate), ``screen_decision``
now kills on a **gross negative signal**: ``mean(Δ) <= gross_kill_threshold``,
regardless of SE. :data:`GROSS_KILL_DELTA` (``-0.15``) is the default threshold — see
its docstring for why that number. Promote is everything else, including a subset that
reads mildly negative but above the gross-kill bar: that is exactly the gray zone the
old significance test could never resolve anyway, and the full-val gate is where it
gets resolved honestly. ``inconclusive: true`` on a promote now means "the subset read
net-negative but not grossly so" rather than "not statistically significant" — the
distinction that mattered under the old rule (significant vs. not) no longer exists at
this stage by design.

### The overfitting tension, stated honestly

Selecting the subset from the parent's currently-failing tasks makes the screen much
more informative per rollout, and also makes it **biased**: it measures the edit on the
tasks the edit was designed for. That is fine for triage (we only want to know "is this
worth full val?") and would be fatal for acceptance (it is why acceptance stays on full
val). The ``holdout_frac`` portion — sampled from the tasks the parent PASSES — is the
partial correction: it is the only part of the screen that can catch the classic churn
failure (fix two tasks, break two others). It cannot be a complete correction, because
k is small; a candidate that regresses a passing task outside the holdout will screen
clean and be caught later by the full-val no-regression veto.
"""

from __future__ import annotations

import math
import random

__all__ = ["select_screen_subset", "screen_decision", "screen_savings",
           "paired_deltas_on", "full_val_ceiling", "screening_economics",
           "TIER_FRAC", "MIN_K", "SCREEN_BREAKEVEN_CEILING", "GROSS_KILL_DELTA"]

#: Rung → fraction of val screened (``scripts/screen.py --tier``). Tier 3 is "almost full val"
#: for the rare case where full val is very large; the real gate is still a separate full-val
#: eval. Lives here, not in screen.py, so :func:`screening_economics` — computed at baseline
#: time, before any skill script runs — prices the SAME rung screen.py will actually fire.
TIER_FRAC = {1: 0.25, 2: 0.5, 3: 0.75}

#: Absolute floor on subset width, independent of the fraction. Was 3, and 3 is
#: MEASURED to be too narrow: on a 12-task val, tier 1 = round(0.25·12) = 3, and the
#: run in docs/RESULTS.md produced a screen that reported ``fixed: ["44"]`` on a 3-task
#: subset when full val showed task 44 was never fixed — a false positive on a third of
#: the evidence. 6 is the smallest width where the paired SE over {-1,0,+1} deltas is
#: not dominated by a single task. It only binds on small val splits; a 100-task val
#: still screens at the 25% fraction.
MIN_K = 6

#: Above this tier-1 ``breakeven_kill_rate``, subset screening is STRUCTURALLY uneconomical on
#: a run: the screen would have to prove more than one candidate in four harmful merely to
#: recover its own rollouts. The screen is biased against kills by design (module docstring),
#: and the documented record is 1 kill in 11 screens (docs/RESULTS.md: 0/8 and 1/3) — so a
#: break-even above this is not reachable on any evidence we have. Deliberately generous to
#: screening (above the ~0.09 observed kill rate) because the screen also buys what the kill
#: arithmetic does not count: round.py's merge stage (#438) only runs on screened survivors.
SCREEN_BREAKEVEN_CEILING = 0.25

#: Default gross-kill threshold (issue #684 item 5): a screen kills iff the subset's
#: mean per-task Δ is at or below this, REGARDLESS of SE. Chosen to sit strictly between
#: the two numbers a real run actually measured: re-measurement DRIFT between byte-
#: identical control replicates ran ~0.10 (round.py's own null-control mechanism), and
#: the real effect sizes the optimizer was chasing ran 0.02-0.09 — so -0.15 never fires
#: on ordinary noise or a genuine close call. The same run's one confirmed GROSS failure
#: (cand_7, an infra-broken edit) screened at Δ̄=-0.2, comfortably below -0.15, so the
#: threshold still catches what it exists to catch. Configurable per call
#: (``screen.py --gross-kill-threshold``) because a noisier scorer or a wider screen
#: subset will have a different noise ceiling; -0.15 is a sensible default, not a law.
GROSS_KILL_DELTA = -0.15


def _valid(pt: dict) -> bool:
    """Did this per-task record produce at least one real measurement?

    Mirrors ``loop.has_valid_trials`` but on plain dicts and without importing it, so
    this module stays a leaf. A task with no valid trial is MISSING DATA — it must not
    be treated as a 0.0 reward, and it must not be chosen for a screen (we would be
    re-measuring an infra outage, not the edit).
    """
    raw = pt.get("raw") or {}
    if "valid_trials" in raw:
        return int(raw.get("valid_trials") or 0) > 0
    if raw.get("errored"):
        return False
    return bool(pt.get("trial_rewards")) or pt.get("reward") is not None


def _informativeness(pt: dict) -> float:
    """How much a screen rollout on this task is likely to teach us.

    ``(1 - reward)`` — headroom: a task already at 1.0 can only go down, and the
    holdout half of the subset is what watches for that.
    ``+ stderr`` — instability: a task that flips between trials carries variance the
    screen should sample rather than assume away.
    """
    reward = float(pt.get("reward") or 0.0)
    return (1.0 - reward) + float(pt.get("stderr") or 0.0)


def select_screen_subset(
    per_task: list,
    *,
    k: int = 4,
    seed: int = 0,
    holdout_frac: float = 0.34,
    broken_ids: list | None = None,
) -> dict:
    """Choose ``k`` val task ids to screen a candidate on. Deterministic.

    ``per_task`` is the PARENT's per-task val records (``SplitResult.per_task``): the
    screen is designed around what the current best actually does, which is why the
    parent side of the comparison is free (its rollouts are already on disk).

    Composition of the returned ``ids``:

      1. ``broken_ids`` first — tasks a previous edit is known to have broken (the
         per-task causal feedback the harness already records). These are the highest
         value rollouts in the run: they are the concrete regressions to re-check.
      2. then the most **informative** remaining tasks (failing / high-variance),
         ranked by ``_informativeness`` with the task id as a deterministic tiebreak.
      3. finally a **random holdout** of ``round(k · holdout_frac)`` tasks drawn
         (seeded) from the tasks the parent PASSES, so the screen is not blind to
         regressions. Sampling is over a *sorted* pool, so the result depends only on
         ``seed``, never on dict/file iteration order.

    Tasks with no valid measurement are excluded entirely (missing data, not a 0.0).

    Returns ``{"ids", "informative", "holdout", "broken", "k", "requested_k", "seed",
    "holdout_frac", "pool_n"}`` — written verbatim into the run dir by
    ``scripts/screen.py`` so any screen decision is reproducible and auditable.
    """
    k = max(1, int(k))
    pool = [pt for pt in (per_task or []) if pt.get("task_id") and _valid(pt)]
    by_id = {str(pt["task_id"]): pt for pt in pool}
    ids_sorted = sorted(by_id)

    broken = [str(t) for t in (broken_ids or []) if str(t) in by_id][:k]
    taken = list(dict.fromkeys(broken))

    n_hold = min(max(0, int(round(k * float(holdout_frac)))), max(0, k - len(taken)))
    passing = sorted(t for t in ids_sorted
                     if t not in taken and float(by_id[t].get("reward") or 0.0) >= 1.0 - 1e-9)
    rng = random.Random(seed)
    holdout = rng.sample(passing, min(n_hold, len(passing))) if passing else []
    holdout.sort()
    taken += [t for t in holdout if t not in taken]

    remaining = [t for t in ids_sorted if t not in taken]
    remaining.sort(key=lambda t: (-_informativeness(by_id[t]), t))
    informative = remaining[: max(0, k - len(taken))]
    taken += informative

    return {
        "ids": sorted(taken),
        "broken": broken,
        "holdout": holdout,
        "informative": sorted(informative),
        "k": len(taken),
        "requested_k": k,
        "seed": int(seed),
        "holdout_frac": float(holdout_frac),
        "pool_n": len(pool),
        "rationale": _subset_rationale(broken=broken, informative=informative, holdout=holdout,
                                       seed=seed),
    }


def _subset_rationale(*, broken: list, informative: list, holdout: list, seed: int) -> str:
    """One sentence explaining WHICH tasks are in the subset and WHY — issue #437's

    ``subset.rationale``: a screen must say why its subset looks the way it does, not
    just what the ids are.
    """
    parts = []
    if broken:
        parts.append(f"{len(broken)} previously-broken task(s) {broken} (a prior edit's "
                     "known regression, highest-value to re-check)")
    if informative:
        parts.append(f"{len(informative)} most-informative failing/high-variance task(s) "
                     f"{informative}")
    if holdout:
        parts.append(f"{len(holdout)} random regression-canary task(s) {holdout} drawn "
                     f"(seed {seed}) from tasks the parent currently passes")
    if not parts:
        return "empty subset — no valid parent measurements to screen against"
    return "; ".join(parts)


def paired_deltas_on(parent_per_task: list, cand_per_task: list, ids: list) -> dict:
    """Aligned ``cand - parent`` deltas restricted to ``ids``, plus the veto material.

    Same honesty rule as ``harness._paired_deltas``: a task either side failed to
    measure is DROPPED, never counted as a -1.0. Returns ``{"deltas", "ids",
    "regressed", "fixed", "dropped"}`` where ``regressed`` is the subset tasks the
    parent measured-and-passed that the candidate strictly worsened.
    """
    want = [str(i) for i in (ids or [])]
    par = {str(pt.get("task_id")): pt for pt in (parent_per_task or [])}
    can = {str(pt.get("task_id")): pt for pt in (cand_per_task or [])}
    deltas, used, dropped, regressed, fixed = [], [], [], [], []
    for tid in want:
        p, c = par.get(tid), can.get(tid)
        if not p or not c or not _valid(p) or not _valid(c):
            dropped.append(tid)
            continue
        pr = float(p.get("reward") or 0.0)
        cr = float(c.get("reward") or 0.0)
        deltas.append(cr - pr)
        used.append(tid)
        if cr < pr - 1e-9:
            regressed.append(tid)
        elif cr > pr + 1e-9:
            fixed.append(tid)
    return {"deltas": deltas, "ids": used, "regressed": regressed,
            "fixed": fixed, "dropped": dropped}


def screen_decision(deltas: list, *, k_se: float = 1.0, regressed: list | None = None,
                    gross_kill_threshold: float = GROSS_KILL_DELTA) -> dict:
    """``kill`` or ``promote`` from a subset's paired deltas. Never ``accept``.

    issue #684 item 5: kill is a GROSS-failure check, not a significance test —

      * ``mean(Δ) <= gross_kill_threshold`` → kill, REGARDLESS of SE.

    Everything else promotes, including a mildly negative mean that does not clear the
    gross-kill bar: that gray zone is exactly what a significance test at tier-1 widths
    could never reliably resolve anyway (see module docstring), so it is left to the
    full-val gate rather than guessed at here. ``mean(Δ) == 0`` also promotes: a subset
    of 4 tasks cannot distinguish "no effect" from "an effect on the other 11", and
    paying one full-val eval to find out is cheaper than silently discarding the edit.

    ``se`` is still computed and reported (useful diagnostic context, and other code
    reads it), but it no longer decides anything — ``k_se`` is accepted only for
    backward-compatible call signatures and is otherwise unused.

    ``regressed`` (subset tasks the parent passed and the candidate broke) never kills
    on its own — the no-regression veto belongs to the full-val gate, where the whole
    split is visible. It is reported so the proposer sees it early.
    """
    ds = [float(d) for d in (deltas or [])]
    n = len(ds)
    if n == 0:
        return {"decision": "promote", "inconclusive": True, "n": 0,
                "mean_delta": 0.0, "se": 0.0, "threshold": gross_kill_threshold,
                "regressed": list(regressed or []),
                "reason": ("no usable paired deltas on the subset (missing data, not a "
                           "measurement) — promoting to full val rather than killing on "
                           "an infra fault")}
    mean_d = sum(ds) / n
    if n >= 2:
        var = sum((d - mean_d) ** 2 for d in ds) / (n - 1)
        se = math.sqrt(var / n)
    else:
        se = 0.0

    kill = mean_d <= gross_kill_threshold
    reason = (f"subset Δ̄={mean_d:+.4f} over n={n} (SE={se:.4f}, informational — kill no "
              f"longer requires significance): "
              + (f"GROSS negative (<= {gross_kill_threshold:+.4f}) → kill" if kill else
                 f"above the gross-kill bar ({gross_kill_threshold:+.4f}) → promote"))

    inconclusive = (not kill) and mean_d < 0
    return {
        "decision": "kill" if kill else "promote",
        "inconclusive": bool(inconclusive),
        "n": n,
        "mean_delta": mean_d,
        "se": se,
        "threshold": gross_kill_threshold,
        "regressed": list(regressed or []),
        "reason": reason + (" (inconclusive: net-negative subset, but not grossly so — "
                            "promoted to let the full-val gate resolve the close call)"
                            if inconclusive else ""),
    }


def screen_savings(*, fired: int, val_n: int, n_trials: int, decision: str) -> dict:
    """MEASURED rollout economics of one screen. No estimates.

    ``fired`` is the number of rollouts the screen actually paid for (cache hits and
    dropped tasks excluded by the caller). ``val_n × n_trials`` is what the full-val
    eval this screen might replace would have cost.

    On ``kill`` the screen saved ``val_n·n_trials - fired`` rollouts. On ``promote``
    it saved nothing and *cost* ``fired`` — reported as a negative ``net_rollouts`` so
    a run's ledger sums to the truth rather than to a flattering number.
    """
    full = max(0, int(val_n)) * max(1, int(n_trials))
    fired = max(0, int(fired))
    killed = decision == "kill"
    return {
        "fired": fired,
        "full_val_rollouts": full,
        "avoided": (full - fired) if killed else 0,
        "net_rollouts": (full - fired) if killed else -fired,
        "decision": decision,
        # The kill rate at which this screen width breaks even. A screen costs ``fired``
        # on every candidate and saves ``full - fired`` on a kill, so screening only
        # pays when kills / candidates > fired / full. Reported so a run can SEE that a
        # narrow val makes the ladder uneconomic instead of discovering it in the ledger.
        "breakeven_kill_rate": (round(fired / full, 4) if full else None),
    }


def screening_economics(val_n: int, n_trials: int) -> dict:
    """Does a tier-1 screen pay for itself on THIS split at THIS trial count? Computed once.

    Issue #631: whether skipping the screen is justified was re-litigated in free text every
    round, and an agent that always skips can always vary the wording. But the economics are
    not a judgement — they are :func:`screen_savings`' own ``breakeven_kill_rate`` for the
    tier-1 rung screen.py fires (``max(MIN_K, 25% of val)`` tasks at 1 trial, capped at val),
    against the full-val eval it would replace (``val_n × n_trials``). Both inputs are frozen
    at baseline, so the answer is too.
    """
    val_n, n_trials = max(0, int(val_n)), max(1, int(n_trials))
    fired = min(val_n, max(MIN_K, int(round(TIER_FRAC[1] * val_n))))
    be = screen_savings(fired=fired, val_n=val_n, n_trials=n_trials,
                        decision="promote")["breakeven_kill_rate"]
    return {"screening_structurally_uneconomical": be is None or be > SCREEN_BREAKEVEN_CEILING,
            "tier1_fired": fired, "full_val_rollouts": val_n * n_trials,
            "breakeven_kill_rate": be, "ceiling": SCREEN_BREAKEVEN_CEILING,
            "val_n": val_n, "n_trials": n_trials}


def full_val_ceiling(parent_per_task: list, cand_per_task: list, subset_ids: list,
                     val_ids: list) -> dict:
    """Could a FULL-val eval of this candidate still clear the gate? Arithmetic, not stats.

    A screen measures the candidate on ``subset_ids``. Every val task OUTSIDE the subset
    is unknown, but bounded: a reward can be at most 1.0. So the candidate's best
    conceivable full-val total is ``sum(measured on subset) + |unscreened|``, and its
    best conceivable paired Δ̄ against the parent follows.

    The gate accepts only when ``Δ̄ > k_se·SE`` with ``k_se·SE >= 0``, so when the best
    conceivable Δ̄ is ``<= 0`` an accept is **impossible** — no full-val eval can change
    the answer, and paying for one buys nothing. That happens exactly when the subset
    already covers every task the parent fails (the unscreened remainder is all tasks the
    parent passes, which can only stay level or regress).

    This is the one case where a screen may kill without a statistical argument, and it
    does not violate "a screen may never accept": it can only ever conclude *reject*.
    ``accept_possible: true`` means "unknown, go pay for full val" — never "accept".
    """
    par = {str(pt.get("task_id")): pt for pt in (parent_per_task or []) if _valid(pt)}
    can = {str(pt.get("task_id")): pt for pt in (cand_per_task or []) if _valid(pt)}
    ids = [str(i) for i in (val_ids or [])]
    measured = [i for i in (str(s) for s in (subset_ids or [])) if i in can and i in par]
    # Only tasks the PARENT measured can enter a paired comparison.
    paired_pool = [i for i in ids if i in par]
    if not paired_pool or not measured:
        return {"status": "not computable — parent or candidate coverage too thin"}
    unscreened = [i for i in paired_pool if i not in set(measured)]
    cand_best = (sum(float(can[i].get("reward") or 0.0) for i in measured)
                 + float(len(unscreened)))
    parent_total = sum(float(par[i].get("reward") or 0.0) for i in paired_pool)
    n = len(paired_pool)
    best_delta = (cand_best - parent_total) / n
    return {
        "n_paired_val": n,
        "n_screened": len(measured),
        "n_unscreened_assumed_perfect": len(unscreened),
        "candidate_best_case_mean": round(cand_best / n, 6),
        "parent_mean": round(parent_total / n, 6),
        "best_case_mean_delta": round(best_delta, 6),
        "accept_possible": best_delta > 1e-9,
        "reason": (
            f"even if all {len(unscreened)} unscreened val task(s) score 1.0, the "
            f"candidate's full-val mean is at most {cand_best / n:.4f} vs the parent's "
            f"{parent_total / n:.4f} (best-case Δ̄ {best_delta:+.4f} <= 0), and the gate "
            "needs Δ̄ > k_se·SE >= 0 — a full-val eval CANNOT accept this candidate"
            if best_delta <= 1e-9 else
            f"best-case Δ̄ {best_delta:+.4f} > 0, so a full-val eval could still clear the "
            "gate — the outcome is unknown, which is not the same as acceptable"),
    }
