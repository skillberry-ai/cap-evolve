"""policy -- the AO-2 conductor's decisions as pure functions (no clock, no I/O, no subprocess).

Everything here takes plain values and returns plain values, so it is unit-testable without a
run dir. The conductor (conductor.py) owns state and side effects; it asks this module:

  chunks / rung_ids     which cells to evaluate next, in <= ``chunk`` rollouts per job
  paired_deltas         the per-task paired delta vector rule P reads (same as harness._paired_deltas)
  rung_kill             kill-only successive-halving rule for a subset rung
  rank_survivors        which screened nodes may take a confirmation slot
  pick_parent           exploit slot 0 = the champion; other slots = best alive tips
  merge_pairs           complementary, unmerged, unrelated pairs of alive tips
  stop_reason           the structured stopping rule (budget, tokens, wall, reward, plateau)

Prose is never read here: a free-text ``stop_condition`` cannot set a cap. Only the numeric keys
passed in ``Caps`` can.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist

CHUNK = 20                 # rollouts per eval job (== sched.ROUND)
COMPLEMENTARY = 0.5        # merge opportunity bar (digest.COMPLEMENTARY)
P_ALIVE = 0.2              # a tip is worth continuing while P(beat champion) exceeds this
SD_FLOOR = 0.3             # per-task paired-delta sd floor: a 10-task batch cannot claim certainty
_N = NormalDist()


# ---- cells ------------------------------------------------------------------------------------

def chunks(missing: dict[str, int], size: int = CHUNK) -> list[dict]:
    """Group ``{task: trials needed}`` into jobs of at most ``size`` rollouts (a task that alone
    needs more than ``size`` is its own job). Deterministic: tasks in sorted order."""
    out, cur, n = [], [], 0
    for t in sorted(missing):
        need = int(missing[t])
        if need <= 0:
            continue
        if cur and n + need > size:
            out.append({"ids": cur, "rollouts": n})
            cur, n = [], 0
        cur.append(t)
        n += need
    if cur:
        out.append({"ids": cur, "rollouts": n})
    return out


def rung_ids(all_ids, size: int, seed: int = 0) -> list[str]:
    """First ``size`` ids of a seeded shuffle: rung r+1's subset contains rung r's, so a
    candidate's rung-0 rollouts are reused, never repeated."""
    ids = sorted(map(str, all_ids))
    random.Random(seed).shuffle(ids)
    return sorted(ids[:size]) if size < len(ids) else sorted(ids)


# ---- statistics -------------------------------------------------------------------------------

def paired_deltas(cand: dict[str, list[float]], ref: dict[str, list[float]], ids=None) -> list[float]:
    """Per-task ``mean(cand) - mean(ref)`` over tasks BOTH sides measured (tasks measured on one side
    only are dropped, never read as a regression). ``ids`` restricts the task set."""
    keep = None if ids is None else set(map(str, ids))
    out = []
    for t in sorted(set(cand) & set(ref)):
        if keep is not None and t not in keep:
            continue
        if cand[t] and ref[t]:
            out.append(sum(cand[t]) / len(cand[t]) - sum(ref[t]) / len(ref[t]))
    return out


def mean_se(xs, sd_floor: float = 0.0) -> tuple[float, float, int]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0
    m = sum(xs) / n
    if n < 2:
        return m, max(sd_floor, 0.0), n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m, max(sd, sd_floor) / math.sqrt(n), n


def p_beat(deltas, sd_floor: float = SD_FLOOR) -> float:
    """P(true mean delta > 0) under a normal approximation with a floored sd. 0.5 with no data."""
    m, se, n = mean_se(deltas, sd_floor)
    if n == 0 or se <= 0:
        return 0.5
    return _N.cdf(m / se)


def rung_kill(deltas, z_kill: float = 1.64, sd_floor: float = SD_FLOOR) -> bool:
    """Kill-only: drop a candidate when the UPPER confidence bound of its mean delta vs the
    incumbent is below zero. A rung subset can therefore never end a candidate on a lucky or
    unlucky draw unless the evidence is lopsided; it only removes the clearly-worse."""
    m, se, n = mean_se(deltas, sd_floor)
    if n == 0:
        return False
    return m + z_kill * se < 0.0


def rank_survivors(scored: dict[str, float], slots: int) -> list[str]:
    """Best ``slots`` tags by score (ties broken by tag, so replays agree)."""
    return [t for t, _ in sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))[:max(slots, 0)]]


# ---- second objective: cost per success (opt-in, a ``cost`` objective in the spec) ------------
MARGIN = 0.03              # reward non-inferiority margin for a cost-only win


def cost_per_success(cand_r, cand_c, ref_r, ref_c) -> dict:
    """Paired cost per success (sum cost / sum reward, ``objectives.cost_per_success``) of the
    candidate vs the reference, on the same cells the reward rule reads. ``*_c`` lists are aligned
    with ``*_r``; a cell without a recorded cost is dropped, never read as free."""
    from cap_evolve.objectives import TrialRec, cost_per_success as cps

    def arm(r, c):
        return [TrialRec(t, k, rr, cc) for t in sorted(r) for k, (rr, cc) in enumerate(zip(r[t], c.get(t) or []))
                if cc is not None]
    return cps(arm(ref_r, ref_c), arm(cand_r, cand_c))


def mo_verdict(reward_pass: bool, r_mean: float, r_se: float, n: int, cps: dict, eps: float, z: float) -> tuple[bool, str]:
    """Reward and cost per success, reward first. ``reward``: the reward rule passed and cost per
    success is at most ``eps`` (relative) worse. ``cost``: reward is non-inferior on ``n >= 2`` paired
    tasks (one-SE lower bound above ``-MARGIN``) and cost per success is at least ``eps`` lower with paired z <= ``-z``.
    Else ``cost_regression`` (reward passed, cost grew) or ``no_gain``."""
    rel, cz = float(cps.get("rel") or 0.0), float(cps.get("z") or 0.0)
    if cps.get("n", 0) == 0:
        return reward_pass, "reward_no_cost_data" if reward_pass else "no_gain"     # reward alone, flagged
    if reward_pass:
        return (True, "reward") if rel <= eps else (False, "cost_regression")
    if n >= 2 and r_mean - r_se >= -MARGIN and rel <= -eps and cz <= -z:
        return True, "cost"
    return False, "no_gain"


# ---- focus rule (ao_focus) ------------------------------------------------------------------------
FOCUS_SD_FLOOR = 0.25      # per-task paired-delta sd floor (one or two trials cannot claim certainty)
FOCUS_Z = 1.8              # one-sided ACCEPT bar (simulated on real tau2 rates: false accept ~5% per null)
FOCUS_Z_KILL = 0.8         # lighter KILL bar: a wrong kill costs one idea, a wrong accept costs the champion
FOCUS_MIN_GAIN = 0.07      # accept only gains of >= 2 tasks of 30: large, resolvable improvements


def focus_verdict(focus_d, canary_d, n_all: int, n_pass: int) -> dict:
    """Stratified estimate of the FULL-set gain from two strata of the champion's tasks: the failing
    stratum is measured in full (``focus_d``, one paired delta per task), the passing stratum through
    ``canary_d``, a random sample of it scaled to its ``n_pass`` tasks. Unbiased for the full-set
    change even though both strata were picked by the champion's own (noisy) results: the regression
    to the mean that inflates focus deltas is the one that deflates canary deltas.
    ``accept``: lower bound > 0 and gain >= FOCUS_MIN_GAIN; ``kill``: (lighter) upper bound < FOCUS_MIN_GAIN."""
    nf, nc, N = len(focus_d), len(canary_d), max(n_all, 1)
    _, se_f, _ = mean_se(focus_d, FOCUS_SD_FLOOR)                 # se of the focus MEAN
    mc, se_c, _ = mean_se(canary_d, FOCUS_SD_FLOOR) if nc else (0.0, 0.0, 0)
    gain = (sum(focus_d) + n_pass * mc) / N
    se = math.sqrt((nf * se_f) ** 2 + (n_pass * se_c) ** 2) / N
    out = {"gain": gain, "se": se, "mean": sum(focus_d) / nf if nf else 0.0, "canary": mc, "n": nf,
           "p_beat": _N.cdf(gain / se) if se > 0 else 0.5}
    if nf == 0:
        return {**out, "verdict": "more", "why": "no_data"}
    if gain - FOCUS_Z * se > 0 and gain >= FOCUS_MIN_GAIN:
        return {**out, "verdict": "accept", "why": "focus_gain"}
    if gain + FOCUS_Z_KILL * se < FOCUS_MIN_GAIN:
        return {**out, "verdict": "kill", "why": "no_gain"}
    return {**out, "verdict": "more", "why": "undecided"}


# ---- parents and merges -----------------------------------------------------------------------

def pick_parent(slot: int, champion: str, tips: dict[str, float], rng: random.Random,
                stuck: dict[str, int] | None = None, max_stuck: int = 3) -> str:
    """Parent for proposal slot ``slot``. Slot 0 is always the champion (so K=1 is hill-climb).
    Later slots: a Thompson draw over alive non-champion tips with P(beat champion) > ``P_ALIVE``
    (``tips`` = tag -> that probability), dropping tips that produced ``max_stuck`` failed
    children; the champion when none is eligible."""
    if slot == 0:
        return champion
    stuck = stuck or {}
    pool = {t: p for t, p in sorted(tips.items()) if p > P_ALIVE and t != champion and stuck.get(t, 0) < max_stuck}
    if not pool:
        return champion
    draws = {t: rng.betavariate(1 + 9 * p, 1 + 9 * (1 - p)) for t, p in pool.items()}
    return max(sorted(draws), key=lambda t: draws[t])


def complementarity(wa, wb) -> float:
    u = set(wa) | set(wb)
    return round(len(set(wa) ^ set(wb)) / len(u), 3) if u else 0.0


def merge_pairs(tips: list[str], wins: dict[str, set], related, merged: set[frozenset],
                bar: float = COMPLEMENTARY, limit: int = 1) -> list[tuple[str, str, float]]:
    """Complementary pairs among ``tips`` that are neither ancestor/descendant (``related(a, b)``)
    nor already merged, best first. ``wins[t]`` = tasks where ``t`` beat the champion."""
    out = []
    for i, a in enumerate(tips):
        for b in tips[i + 1:]:
            if frozenset((a, b)) in merged or related(a, b):
                continue
            if a not in wins or b not in wins:
                continue
            c = complementarity(wins[a], wins[b])
            if c > bar:
                out.append((a, b, c))
    out.sort(key=lambda r: (-r[2], r[0], r[1]))
    return out[:limit]


def merge_allowed(n_merges: int, n_proposals: int, merge_won: bool, frac: float = 0.2) -> bool:
    """At most ``max(1, frac)`` of proposals are merges until a merge has been promoted or pruned:
    no merge loop. ``merge_won`` = some merge node already reached a terminal verdict."""
    if merge_won:
        return True
    return n_merges < max(1, int(frac * n_proposals))


# ---- stopping ---------------------------------------------------------------------------------

MAX_IDLE = 6          # consecutive proposals that yield no new evaluable candidate (refused, duplicate, failed)


@dataclass(frozen=True)
class Caps:
    """Numeric stopping inputs only. None / 0 = no such cap."""
    max_metric_calls: int | None = None
    max_tokens: int | None = None
    deadline: float | None = None            # epoch seconds
    stop_at_reward: float | None = None
    max_candidates: int | None = None        # only when the spec sets the numeric key explicitly
    plateau_n: int | None = None             # explicit proposals-without-gain; else derived
    plateau_floor: float = 0.4               # fraction of the rollout budget that must be spent first
    max_idle: int = MAX_IDLE                 # 0 = off; a proposer that cannot yield a new candidate must not spin
    chunk: int = CHUNK
    proposer_cap: int = 150_000
    finalize_rollouts: int = 0
    finalize_tokens: int = 0


def plateau_n(caps: Caps, n_proposals: int, spent_frac: float) -> int | None:
    """Proposals without a champion change that count as a plateau: ``max(6, 0.4 * budget_proposals)``
    where ``budget_proposals`` is projected from the spend so far. None until the projection is
    meaningful (5% of the rollout budget spent), so an early dry spell never stops a run."""
    if caps.plateau_n:
        return int(caps.plateau_n)
    if not caps.max_metric_calls or spent_frac < 0.05 or n_proposals <= 0:
        return None
    return max(6, int(math.ceil(0.4 * n_proposals / spent_frac)))


def stop_reason(*, caps: Caps, committed: int, reserved: int, tokens: int, tokens_reserved: int,
                now: float, best_reward: float | None, n_proposals: int,
                since_improve: int, alive_p: list[float], in_flight: int = 0, idle: int = 0) -> str | None:
    """Why the conductor should stop PROPOSING (then drain, finalize, exit 0), or None to go on.
    Only structured keys are read."""
    mc = caps.max_metric_calls
    if mc and committed + reserved + caps.chunk + caps.finalize_rollouts > mc:
        return "budget: rollouts"
    if caps.max_tokens and tokens + tokens_reserved + caps.proposer_cap + caps.finalize_tokens > caps.max_tokens:
        return "budget: tokens"
    if caps.deadline and now >= caps.deadline:
        return "wall: deadline"
    if caps.stop_at_reward and best_reward is not None and best_reward >= caps.stop_at_reward - 1e-9:
        return "reward: stop_at_reward reached"
    if caps.max_candidates and n_proposals >= caps.max_candidates and in_flight == 0:
        return "max_candidates (numeric key)"      # proposals already launched are allowed to finish
    if caps.max_idle and idle >= caps.max_idle:
        return "proposer_exhausted"             # idle proposals' tokens are already inside `tokens` above
    spent_frac = (committed / mc) if mc else 0.0
    n = plateau_n(caps, n_proposals, spent_frac)
    if n and since_improve >= n and (not mc or spent_frac >= caps.plateau_floor) and not any(p > P_ALIVE for p in alive_p):
        return f"plateau: {since_improve} proposals without a champion change at {spent_frac:.0%} of budget"
    return None
