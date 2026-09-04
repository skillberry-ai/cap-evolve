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

So the screen is deliberately biased toward **promote**: it kills only on evidence of
*significant harm* (``mean(Δ) + k_se·SE < 0``), or on a unanimous negative subset where
the SE legitimately collapses to 0. Everything else — including "no signal at all" —
promotes, and says ``inconclusive: true`` so the reason is auditable.

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
           "paired_deltas_on", "full_val_ceiling"]


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


def screen_decision(deltas: list, *, k_se: float = 1.0, regressed: list | None = None) -> dict:
    """``kill`` or ``promote`` from a subset's paired deltas. Never ``accept``.

    Kill only on evidence of significant HARM:

      * ``mean(Δ) + k_se·SE < 0`` — the subset says the edit is worse, beyond noise; or
      * ``SE == 0 and mean(Δ) < 0`` — every screened task moved the same way and that
        way was down (a unanimous negative; there is no noise to hide behind).

    Everything else promotes. In particular ``mean(Δ) == 0`` promotes: a subset of 4
    tasks cannot distinguish "no effect" from "an effect on the other 11", and paying
    one full-val eval to find out is cheaper than silently discarding the edit.

    ``regressed`` (subset tasks the parent passed and the candidate broke) never kills
    on its own — the no-regression veto belongs to the full-val gate, where the whole
    split is visible. It is reported so the proposer sees it early.
    """
    ds = [float(d) for d in (deltas or [])]
    n = len(ds)
    if n == 0:
        return {"decision": "promote", "inconclusive": True, "n": 0,
                "mean_delta": 0.0, "se": 0.0, "threshold": 0.0,
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

    if se == 0.0:
        kill = mean_d < 0
        reason = (f"subset Δ̄={mean_d:+.4f} over n={n} with SE=0 (unanimous) → "
                  f"{'kill' if kill else 'promote'}")
    else:
        bar = k_se * se
        kill = (mean_d + bar) < 0
        reason = (f"subset Δ̄={mean_d:+.4f}, SE={se:.4f}, n={n}: "
                  f"{'harm beyond noise (Δ̄+' + f'{k_se}·SE' + f'={mean_d + bar:+.4f} < 0)' if kill else 'not significantly harmful'}"
                  f" → {'kill' if kill else 'promote'}")

    inconclusive = (not kill) and (mean_d - k_se * se) <= 0
    return {
        "decision": "kill" if kill else "promote",
        "inconclusive": bool(inconclusive),
        "n": n,
        "mean_delta": mean_d,
        "se": se,
        "threshold": -k_se * se,
        "regressed": list(regressed or []),
        "reason": reason + (" (inconclusive: promoted without positive evidence — the "
                            "screen is biased against false kills)" if inconclusive and not kill else ""),
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
