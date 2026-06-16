"""Acceptance gate — the rule that decides whether a candidate edit is kept.

The default is the *significance* gate (prior agent-optimization work's ``val_improvement_significant``):
accept only when the val improvement exceeds k standard errors, so noise does
not get mistaken for progress. All gates compare on VAL and never on TRAIN —
``decide`` takes an explicit ``split`` and refuses anything but ``val``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class GateDecision:
    accept: bool
    reason: str
    delta: float
    threshold: float = 0.0

    def to_dict(self) -> dict:
        return {
            "accept": self.accept,
            "reason": self.reason,
            "delta": self.delta,
            "threshold": self.threshold,
        }


class TrainGateError(RuntimeError):
    """Raised if someone tries to gate acceptance on the train split."""


def decide(
    current_val: float,
    candidate_val: float,
    *,
    split: str = "val",
    mode: str = "significant",
    k_se: float = 1.0,
    candidate_stderr: float = 0.0,
    current_stderr: float = 0.0,
    threshold: float = 0.0,
    candidate_size: int | None = None,
    current_size: int | None = None,
) -> GateDecision:
    """Decide whether to accept the candidate.

    Modes:
      - ``significant``: accept iff delta > k * combined_SE (default, honest).
      - ``threshold``:   accept iff delta > ``threshold`` (a flat margin).
      - ``strict``:      accept iff delta > 0 (any improvement).
      - ``simplicity_tiebreak``: like strict, but on a (near-)tie prefer the
        smaller candidate (``candidate_size`` < ``current_size``).
    """
    if split.lower() != "val":
        raise TrainGateError(
            f"Acceptance must be gated on VAL, got split={split!r}. Gating on "
            "train overfits the optimizer to the data it edits against."
        )

    delta = candidate_val - current_val

    if mode == "significant":
        se = math.sqrt(candidate_stderr ** 2 + current_stderr ** 2)
        bar = k_se * se
        ok = delta > bar
        return GateDecision(
            accept=ok,
            reason=(
                f"Δ={delta:+.4f} {'>' if ok else '<='} {k_se}·SE={bar:.4f} "
                f"(SE={se:.4f})"
            ),
            delta=delta,
            threshold=bar,
        )

    if mode == "threshold":
        ok = delta > threshold
        return GateDecision(ok, f"Δ={delta:+.4f} {'>' if ok else '<='} {threshold:.4f}", delta, threshold)

    if mode == "strict":
        ok = delta > 0
        return GateDecision(ok, f"Δ={delta:+.4f} {'>' if ok else '<='} 0", delta, 0.0)

    if mode == "simplicity_tiebreak":
        if delta > 0:
            return GateDecision(True, f"Δ={delta:+.4f} > 0", delta, 0.0)
        tie = abs(delta) <= 1e-9
        if tie and candidate_size is not None and current_size is not None and candidate_size < current_size:
            return GateDecision(
                True,
                f"tie (Δ={delta:+.4f}); accepted smaller candidate "
                f"({candidate_size} < {current_size})",
                delta,
                0.0,
            )
        return GateDecision(False, f"Δ={delta:+.4f} <= 0 (no simpler tie)", delta, 0.0)

    raise ValueError(f"unknown gate mode: {mode!r}")
