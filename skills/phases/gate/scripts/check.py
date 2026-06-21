"""Contract: the gate refuses split=train, and at SE=0 the significance mode
falls back to strict (accept any Δ>0) instead of silently mis-acting.
"""

from __future__ import annotations

import sys

import _bootstrap  # noqa: F401

from cap_evolve.gate import TrainGateError, decide
from cap_evolve.skillcheck import Checker, import_run


def main() -> int:
    c = Checker("gate")
    c.require_main(import_run())

    # 1. refuses gating on train
    try:
        decide(0.5, 0.9, split="train")
        c.fail("gate accepted split=train (must raise TrainGateError)")
    except TrainGateError:
        c.note("refuses split=train")

    # 2. SE=0 → strict fallback: a positive delta accepts, a zero delta does not
    d_up = decide(0.5, 0.6, split="val", mode="significant",
                  candidate_stderr=0.0, current_stderr=0.0)
    d_flat = decide(0.5, 0.5, split="val", mode="significant",
                    candidate_stderr=0.0, current_stderr=0.0)
    c.check(d_up.accept and "STRICT fallback" in d_up.reason,
            f"SE=0 positive Δ should accept via strict fallback: {d_up.to_dict()}")
    c.check(not d_flat.accept,
            f"SE=0 zero Δ must not accept: {d_flat.to_dict()}",
            note="SE=0 collapses to strict (Δ>0), not a silent pass")

    # 3. with real variance the significance bar gates a tiny improvement
    d_noise = decide(0.5, 0.52, split="val", mode="significant",
                     candidate_stderr=0.1, current_stderr=0.1, k_se=1.0)
    c.check(not d_noise.accept,
            f"tiny Δ below the SE bar should be rejected: {d_noise.to_dict()}",
            note="improvement within noise is rejected")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
