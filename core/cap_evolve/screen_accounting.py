"""Screen accounting: a screen is a SAMPLING DESIGN with known inclusion probabilities (opt-in).

Every screen is the union of three components:

  * ``affected``  tasks the proposer predicts the edit reaches        (inclusion probability 1)
  * ``sentinel``  regression sentinels: tasks to re-check on purpose   (inclusion probability 1)
  * ``random``    ``k_random`` tasks drawn uniformly without replacement from the REST of the pool,
                  inclusion probability ``k_random / n_rest`` -- the only component that licenses an
                  estimate for the tasks nobody chose.

``ht_estimate`` is the Horvitz-Thompson estimate of the full-pool mean delta: the deterministic strata
exactly, the rest through the random stratum scaled by ``n_rest / k_random``. Its standard error comes
from the random stratum alone (finite-population correction included).

A screen score is a SCHEDULING SIGNAL (which candidate deserves a full evaluation), never a result:
:func:`record` stamps ``role: scheduling_signal, result: false`` and carries no accept field, and the kill-only rule
in ``subsample`` is untouched. ``build_control`` is the ablation arm: the same number of tasks drawn
uniformly from the whole pool, ignoring predictions, so targeted selection can be compared with random
selection at equal cost.

Pure, stdlib-only, deterministic given ``seed``. Prior art: stratified / Horvitz-Thompson sampling.
"""

from __future__ import annotations

import hashlib
import math
import random

ROLE = "scheduling_signal"


def derive_seed(run_seed: int, tier: int, tag: str, salt: str = "accounted") -> int:
    """Per-candidate seed: every candidate draws its OWN random stratum (a draw shared by all candidates
    would make 'the candidate that wins this one draw' a selection on that draw, adding winner's-curse
    bias to the estimate). ``salt`` keeps the control's draw independent of the accounted screen's."""
    h = hashlib.sha256(f"{run_seed}|{tier}|{tag}|{salt}".encode()).hexdigest()
    return int(h[:12], 16)


def build_screen(pool_ids, affected, sentinels, k_random: int, seed: int = 0) -> dict:
    pool = sorted({str(t) for t in pool_ids})
    inpool = set(pool)
    aff = [str(t) for t in dict.fromkeys(affected or []) if str(t) in inpool]
    sen = [str(t) for t in dict.fromkeys(sentinels or []) if str(t) in inpool and str(t) not in aff]
    rest = [t for t in pool if t not in set(aff) | set(sen)]
    k = max(0, min(int(k_random), len(rest)))
    drawn = sorted(random.Random(seed).sample(rest, k)) if k else []
    comp = {**{t: "affected" for t in aff}, **{t: "sentinel" for t in sen}, **{t: "random" for t in drawn}}
    p = (k / len(rest)) if rest else 0.0
    inc = {t: (p if c == "random" else 1.0) for t, c in comp.items()}
    return {"mode": "accounted", "ids": sorted(comp), "components": dict(sorted(comp.items())),
            "inclusion": dict(sorted(inc.items())), "n_pool": len(pool), "n_rest": len(rest),
            "k_random": k, "seed": int(seed)}


def build_control(pool_ids, size: int, seed: int = 0) -> dict:
    """Equal-size uniform random subset of the whole pool (prediction ignored)."""
    pool = sorted({str(t) for t in pool_ids})
    m = max(0, min(int(size), len(pool)))
    drawn = sorted(random.Random(seed).sample(pool, m)) if m else []
    p = (m / len(pool)) if pool else 0.0
    return {"mode": "random_subset", "ids": drawn, "components": {t: "random" for t in drawn},
            "inclusion": {t: p for t in drawn}, "n_pool": len(pool), "n_rest": len(pool),
            "k_random": m, "seed": int(seed)}


def _sd(v):
    n = len(v)
    if n < 2:
        return 0.0
    m = sum(v) / n
    return math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))


def ht_estimate(deltas: dict, screen: dict) -> dict:
    """Estimate of the full-pool mean delta from ``{task: delta}`` over the screened tasks that were
    measured. ``unbiased`` is False when the random stratum is empty but tasks remain unscreened."""
    comp = screen["components"]
    n_pool, n_rest, k = screen["n_pool"], screen["n_rest"], screen["k_random"]
    got = {t: float(d) for t, d in deltas.items() if t in comp}
    by = {c: [d for t, d in got.items() if comp[t] == c] for c in ("affected", "sentinel", "random")}
    counts = {c: len(v) for c, v in by.items()}
    planned = {c: sum(1 for x in comp.values() if x == c) for c in ("affected", "sentinel", "random")}
    complete = counts == planned          # every screened task was actually measured
    if not n_pool:
        return {"estimate": None, "se_random": None, "n_by_component": counts, "unbiased": False,
                "n_random_measured": counts["random"], "k_random": k}
    if screen["mode"] == "random_subset":
        v = by["random"]
        if not v:
            return {"estimate": None, "se_random": None, "n_by_component": counts, "unbiased": False,
                    "n_random_measured": 0, "k_random": k}
        fpc = 1 - len(v) / n_pool
        return {"estimate": sum(v) / len(v), "se_random": math.sqrt(max(fpc, 0.0)) * _sd(v) / math.sqrt(len(v)),
                "n_by_component": counts, "unbiased": complete, "n_random_measured": len(v), "k_random": k}
    det = sum(by["affected"]) + sum(by["sentinel"])
    r = by["random"]
    if n_rest and not r:
        return {"estimate": None, "se_random": None, "n_by_component": counts, "unbiased": False,
                "n_random_measured": 0, "k_random": k}
    rest_total = (n_rest / len(r)) * sum(r) if r else 0.0
    se = 0.0
    if r and n_rest:
        fpc = max(1 - len(r) / n_rest, 0.0)
        se = (n_rest / n_pool) * math.sqrt(fpc) * _sd(r) / math.sqrt(len(r))
    # Scaled by the measured count: a missing random task is treated as missing at random, so the
    # estimate stays usable but is NOT design-unbiased -> ``unbiased`` False and the counts say why.
    return {"estimate": (det + rest_total) / n_pool, "se_random": se, "n_by_component": counts,
            "unbiased": complete, "n_random_measured": len(r), "k_random": k}


def record(screen: dict, estimate: dict | None = None, *, n_val: int | None = None,
           pool_excluded=()) -> dict:
    """The auditable accounting block for a screen record. A scheduling signal; never a result.
    The pool is the val tasks with a valid PARENT measurement; ``n_val`` and ``pool_excluded`` record
    how many val tasks (and which) fell outside it, so the estimate's target population is explicit."""
    return {"role": ROLE, "result": False, "control": screen["mode"] == "random_subset",
            "mode": screen["mode"], "components": screen["components"], "inclusion": screen["inclusion"],
            "n_pool": screen["n_pool"], "n_rest": screen["n_rest"], "k_random": screen["k_random"],
            "seed": screen["seed"], "estimate": estimate, "n_val": n_val,
            "pool_excluded": sorted(map(str, pool_excluded))}
