"""Seeded train / val / test splitting with a SEALED test set.

The single most important honesty guarantee: the test split is scored exactly
once, ever, per run. ``make_splits`` is deterministic given a seed so a run is
reproducible; ``Splits`` tracks a ``test_used`` flag (persisted in the run dir)
and ``mark_test_used`` raises on a second access.

Skills NEVER re-split or peek at test — they ask the run dir for the frozen
splits written at intake/baseline time.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Sequence

#: Below this many val tasks the significance gate is statistically meaningless.
#: n=0 → nothing to decide on; n=1 → SE(Δ) is undefined (df=0) so the gate always
#: degenerates to "any Δ>0 wins". Both are hard errors.
MIN_VAL_TASKS = 2

#: Below this many val tasks the gate still runs but is flagged low-confidence:
#: with df=n-1 <= 3 the t bar is wide and a couple of lucky per-task deltas
#: dominate. Warned, not refused.
LOW_CONFIDENCE_VAL_TASKS = 5

#: Escape hatch for deliberately degenerate runs (smoke tests, single-task
#: debugging). Setting it means you accept that the acceptance gate is NOT an
#: honest significance test for that run.
_ALLOW_TINY_ENV = "CAPEVOLVE_ALLOW_TINY_VAL"


class TinyValSplitError(RuntimeError):
    """Raised when the val split is too small for the gate to mean anything."""


def check_val_size(splits: "Splits", *, context: str = "", run_dir=None) -> str | None:
    """Refuse an unusable val split; warn on a merely small one.

    Called at split-freeze time (``ensure_splits``) and again at ``baseline`` — the
    two moments a run commits to a val split — so a hand-written or resumed
    ``splits.json`` cannot sneak past. Returns the warning text when val is small
    but usable (also logged as a ``split_warning`` event), else ``None``.
    """
    n = len(splits.val)
    where = f" ({context})" if context else ""
    if n < MIN_VAL_TASKS and not os.environ.get(_ALLOW_TINY_ENV):
        detail = ("is EMPTY" if n == 0 else
                  "has exactly 1 task, so the paired delta has 0 degrees of freedom "
                  "(SE undefined) and the gate degenerates to 'any Δ>0 wins'")
        raise TinyValSplitError(
            f"val split{where} {detail} — the acceptance gate would produce a "
            f"meaningless decision, so cap-evolve refuses to start.\n"
            f"  train={len(splits.train)} val={n} test={len(splits.test)}\n"
            f"Fix one of:\n"
            f"  1. Add tasks: with the default 0.5/0.25/0.25 ratios you need >= 6 "
            f"tasks for val >= 2, and >= 20 for val >= 5 (recommended).\n"
            f"  2. Set explicit ratios, e.g. split_val: 0.4 in capevolve.yaml.\n"
            f"  3. Pin the split yourself via split_ids_file "
            f"({{\"train\": [...], \"val\": [...], \"test\": [...]}}).\n"
            f"  4. Only if you accept a non-honest gate: export "
            f"{_ALLOW_TINY_ENV}=1."
        )
    if n < LOW_CONFIDENCE_VAL_TASKS:
        msg = (f"val split{where} has only {n} tasks (< {LOW_CONFIDENCE_VAL_TASKS}) — "
               f"acceptance decisions are LOW CONFIDENCE. The gate applies a "
               f"Student-t small-sample correction (df={max(n - 1, 0)}), which widens "
               f"the bar, but the honest fix is more val tasks.")
        if run_dir is not None:
            log = getattr(run_dir, "log_event", None)
            if callable(log):
                log("split_warning", val=n, min_recommended=LOW_CONFIDENCE_VAL_TASKS,
                    reason=msg)
        return msg
    return None


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
