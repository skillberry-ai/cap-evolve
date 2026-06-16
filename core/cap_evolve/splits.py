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

    def ids(self, split: str) -> list:
        split = split.lower()
        if split == "train":
            return list(self.train)
        if split == "val":
            return list(self.val)
        if split == "test":
            return list(self.test)
        raise ValueError(f"unknown split: {split!r} (use train|val|test)")

    def mark_test_used(self) -> None:
        if self.test_used:
            raise TestSealError(
                "TEST split already scored once this run. The held-out test set "
                "is sealed — re-scoring it would invalidate the headline number. "
                "Score val during optimization; test is for finalize() only."
            )
        self.test_used = True

    def to_dict(self) -> dict:
        return {
            "train": list(self.train),
            "val": list(self.val),
            "test": list(self.test),
            "seed": self.seed,
            "test_used": self.test_used,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Splits":
        return cls(
            train=list(d.get("train") or []),
            val=list(d.get("val") or []),
            test=list(d.get("test") or []),
            seed=int(d.get("seed") or 0),
            test_used=bool(d.get("test_used") or False),
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
