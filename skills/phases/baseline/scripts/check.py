"""Contract: baseline freezes a deterministic seeded split — the same seed yields
the same train/val/test partition, and the split is written once (idempotent).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run
from cap_evolve.splits import make_splits


def main() -> int:
    c = Checker("baseline")
    c.require_main(import_run())

    ids = [f"t{i}" for i in range(12)]
    s1 = make_splits(list(ids), seed=7, ratios=(0.5, 0.25, 0.25))
    s2 = make_splits(list(ids), seed=7, ratios=(0.5, 0.25, 0.25))
    s3 = make_splits(list(ids), seed=8, ratios=(0.5, 0.25, 0.25))
    c.check((s1.train, s1.val, s1.test) == (s2.train, s2.val, s2.test),
            "same seed produced different splits (non-deterministic)",
            note="seeded split is deterministic")
    c.check((s1.train, s1.val, s1.test) != (s3.train, s3.val, s3.test),
            "different seeds produced identical splits (seed ignored)")
    c.check(not (set(s1.train) & set(s1.test)), "train/test overlap in a held-out split")

    # write_splits then read_splits round-trips and is stable (written once).
    with tempfile.TemporaryDirectory() as d:
        from cap_evolve import RunDir
        rd = RunDir.create(Path(d) / ".capevolve", ts="b")
        rd.write_splits(s1)
        back = rd.read_splits()
        c.check(back.train == s1.train and back.seed == s1.seed,
                "splits did not round-trip through the run dir",
                note="split frozen + reloadable from the run dir")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
