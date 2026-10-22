"""Seeded train / val / test splitting with a SEALED test set.

The single most important honesty guarantee: the test split is scored exactly
once, ever, per run. ``make_splits`` is deterministic given a seed so a run is
reproducible; ``Splits`` tracks a ``test_used`` flag (persisted in the run dir)
and ``mark_test_used`` raises on a second access.

Skills NEVER re-split or peek at test — they ask the run dir for the frozen
splits written at intake/baseline time.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence


class TestSealError(RuntimeError):
    """Raised when something tries to score the test split more than once."""

    __test__ = False  # not a pytest test class despite the leading 'Test'


@dataclass
class Splits:
    train: list = field(default_factory=list)  # list[str] of task ids
    val: list = field(default_factory=list)
    test: list = field(default_factory=list)
    seed: int = 0
    test_used: bool = False
    # ``split_mode: pooled`` (see ``make_pooled_partition``): pool = train + val, partitioned ONCE into
    # a feedback stratum F (proposer and rungs) and a hidden confirm stratum C (confirmation only).
    # Persisted with the splits and never re-drawn. ``pooled`` False = the legacy three-way split.
    pooled: bool = False
    feedback: list = field(default_factory=list)
    confirm: list = field(default_factory=list)
    pool_seed: int = 0
    # The split file named F and C itself (``feedback``/``confirm`` keys): train holds F and val holds C
    # until ``ensure_pooled`` adopts them as the partition instead of drawing one.
    explicit_pool: bool = False

    def ids(self, split: str) -> list:
        split = split.lower()
        if split == "train":
            return list(self.train)
        if split == "val":
            return list(self.val)
        if split == "test":
            return list(self.test)
        if split in ("feedback", "confirm", "pool"):
            if not self.pooled:
                raise ValueError(f"split {split!r} needs split_mode: pooled (this run has the legacy split)")
            if split == "feedback":
                return list(self.feedback)
            if split == "confirm":
                return list(self.confirm)
            return list(self.train) + list(self.val)
        raise ValueError(f"unknown split: {split!r} (use train|val|test|feedback|confirm|pool)")

    def mark_test_used(self) -> None:
        if self.test_used:
            raise TestSealError(
                "TEST split already scored once this run. The held-out test set "
                "is sealed — re-scoring it would invalidate the headline number. "
                "Score val during optimization; test is for finalize() only."
            )
        self.test_used = True

    def check_test_unused(self) -> None:
        """Raise if the seal is already burned, WITHOUT flipping it.

        Used by ``reserve_test()`` to fail fast at the *start* of finalize, so a
        second finalize is refused — but the seal is only actually flipped by
        ``mark_test_used`` once the test score has been computed and written
        (seal-on-success). A crash between reserve and commit must NOT burn it.
        """
        if self.test_used:
            raise TestSealError(
                "TEST split already scored once this run. The held-out test set "
                "is sealed — re-scoring it would invalidate the headline number. "
                "Score val during optimization; test is for finalize() only."
            )

    def to_dict(self) -> dict:
        d = {
            "train": list(self.train),
            "val": list(self.val),
            "test": list(self.test),
            "seed": self.seed,
            "test_used": self.test_used,
        }
        if self.pooled:         # legacy files stay byte-identical
            d.update(pooled=True, feedback=list(self.feedback), confirm=list(self.confirm),
                     pool_seed=self.pool_seed)
        if self.explicit_pool:
            d["explicit_pool"] = True
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Splits":
        return cls(
            train=list(d.get("train") or []),
            val=list(d.get("val") or []),
            test=list(d.get("test") or []),
            seed=int(d.get("seed") or 0),
            test_used=bool(d.get("test_used") or False),
            pooled=bool(d.get("pooled") or False),
            feedback=list(d.get("feedback") or []),
            confirm=list(d.get("confirm") or []),
            pool_seed=int(d.get("pool_seed") or 0),
            explicit_pool=bool(d.get("explicit_pool") or False),
        )


def make_splits(
    task_ids: Sequence[str],
    seed: int = 0,
    ratios: tuple = (0.5, 0.25, 0.25),
    counts: tuple | None = None,
) -> Splits:
    """Deterministically partition task ids into train/val/test.

    ``ratios`` (train, val, test) is used unless ``counts`` (absolute sizes) is
    given. Shuffling is seeded so identical inputs yield identical splits.
    """
    ids = list(dict.fromkeys(str(t) for t in task_ids))  # de-dup, preserve type
    rng = random.Random(seed)
    rng.shuffle(ids)
    n = len(ids)

    if counts is not None:
        n_tr, n_va, n_te = (int(c) for c in counts)
    else:
        r_tr, r_va, r_te = ratios
        total = r_tr + r_va + r_te
        r_tr, r_va, r_te = r_tr / total, r_va / total, r_te / total
        n_tr = int(round(n * r_tr))
        n_va = int(round(n * r_va))
        n_te = n - n_tr - n_va

    n_tr = max(0, min(n, n_tr))
    n_va = max(0, min(n - n_tr, n_va))
    n_te = max(0, n - n_tr - n_va)

    train = ids[:n_tr]
    val = ids[n_tr:n_tr + n_va]
    test = ids[n_tr + n_va:n_tr + n_va + n_te]
    return Splits(train=train, val=val, test=test, seed=seed)


def make_pooled_partition(pool_ids: Sequence[str], seed: int = 0, confirm_fraction: float = 0.48,
                          pass_rates: dict | None = None, n_strata: int = 3) -> tuple[list, list]:
    """Partition the pool into ``(feedback, confirm)``: seeded, deterministic, stratified.

    Stratified by the seed's pass rate (tertiles of ``pass_rates[task]``; tasks without a rate form
    their own stratum) so F and C see the same difficulty mix, then C takes ``confirm_fraction`` of
    each stratum (largest-remainder rounding so |C| = round(fraction * |pool|)). Without
    ``pass_rates`` the draw is a plain seeded split. The two parts are disjoint and cover the pool.
    """
    ids = list(dict.fromkeys(str(t) for t in pool_ids))
    if not ids:
        return [], []
    rng = random.Random(f"pool:{seed}")
    rates = {str(k): float(v) for k, v in (pass_rates or {}).items()}
    known = sorted((t for t in ids if t in rates), key=lambda t: (rates[t], t))
    strata: list[list] = []
    if known:
        n_strata = max(1, min(int(n_strata), len(known)))
        for i in range(n_strata):
            strata.append(known[i * len(known) // n_strata:(i + 1) * len(known) // n_strata])
    rest = [t for t in ids if t not in rates]
    if rest:
        strata.append(rest)
    target = int(round(confirm_fraction * len(ids)))
    quotas, rems = [], []
    for st in strata:
        q = confirm_fraction * len(st)
        quotas.append(int(q))
        rems.append(q - int(q))
    short = max(0, min(target, len(ids)) - sum(quotas))
    for i in sorted(range(len(strata)), key=lambda i: (-rems[i], i))[:short]:
        quotas[i] += 1
    confirm: set = set()
    for st, q in zip(strata, quotas):
        st = sorted(st)
        rng.shuffle(st)
        confirm.update(st[:q])
    feedback = [t for t in ids if t not in confirm]
    return feedback, [t for t in ids if t in confirm]
