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


def _warn_se_zero(run_dir, mode: str, context: str) -> None:
    """Log a ``gate_warning`` event when the SE collapses to 0.

    A 0 SE (e.g. ``n_trials=1`` so every per-task stderr is 0, or all tasks scored
    identically) makes the significance bar 0, so the gate silently degenerates to
    "any Δ>0 wins" — exactly the strict mode, but *unannounced*. We do NOT silently
    behave strict: we record a loud, auditable warning and then proceed with the
    documented strict fallback so the run still makes progress. Best-effort: a
    missing/limited run_dir just means no event is logged.
    """
    if run_dir is None:
        return
    log = getattr(run_dir, "log_event", None)
    if callable(log):
        log("gate_warning",
            mode=mode,
            reason=("combined/paired SE is 0 (likely n_trials=1 or identical trials) — "
                    "the significance gate cannot distinguish noise from signal and is "
                    "falling back to STRICT (accept any Δ>0). Increase n_trials and ensure "
                    "the runner forwards the per-trial seed to get real variance."),
            context=context)


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
    paired_deltas: list | None = None,
    run_dir=None,
) -> GateDecision:
    """Decide whether to accept the candidate.

    Modes:
      - ``paired``: accept iff mean(per-task Δ) > k * SE(Δ), where Δ[t] =
        cand_reward[t] - curr_reward[t] over the SAME val tasks. This is the
        correct, far more powerful test: candidate and current are scored on the
        same tasks, so the cross-task variance cancels and only the *paired*
        variance counts. Requires ``paired_deltas``; the loop uses it by default
        when per-task data is available, else falls back to ``significant``.
      - ``significant``: accept iff delta > k * combined_SE (treats cand & current
        as INDEPENDENT samples — correct only when they were not scored on the
        same tasks; less powerful than ``paired``).
      - ``threshold``:   accept iff delta > ``threshold`` (a flat margin).
      - ``strict``:      accept iff delta > 0 (any improvement).
      - ``simplicity_tiebreak``: like strict, but on a (near-)tie prefer the
        smaller candidate (``candidate_size`` < ``current_size``).

    ``run_dir`` (optional) is used only to log a ``gate_warning`` event when an SE
    collapses to 0 (so the silent degeneration to strict is auditable).
    """
    if split.lower() != "val":
        raise TrainGateError(
            f"Acceptance must be gated on VAL, got split={split!r}. Gating on "
            "train overfits the optimizer to the data it edits against."
        )

    delta = candidate_val - current_val

    if mode == "paired":
        deltas = list(paired_deltas or [])
        if not deltas:
            # No paired data — fall back to the independent significance test rather
            # than silently passing. (The loop should pass paired_deltas; this guards
            # a direct caller.)
            mode = "significant"
        else:
            n = len(deltas)
            mean_d = sum(deltas) / n
            if n >= 2:
                var = sum((d - mean_d) ** 2 for d in deltas) / (n - 1)
                se = math.sqrt(var / n)
            else:
                se = 0.0
            if se == 0.0:
                # Paired SE collapsed (n=1, or every task moved identically). Do not
                # silently act strict — warn loudly, then apply the documented strict
                # fallback (accept any positive mean delta).
                _warn_se_zero(run_dir, "paired", context=f"n={n}")
                ok = mean_d > 0
                return GateDecision(
                    accept=ok,
                    reason=(f"paired Δ̄={mean_d:+.4f} {'>' if ok else '<='} 0 "
                            f"(SE=0 → STRICT fallback, warned; n={n})"),
                    delta=mean_d, threshold=0.0,
                )
            bar = k_se * se
            ok = mean_d > bar
            return GateDecision(
                accept=ok,
                reason=(f"paired Δ̄={mean_d:+.4f} {'>' if ok else '<='} {k_se}·SE={bar:.4f} "
                        f"(SE={se:.4f}, n={n})"),
                delta=mean_d, threshold=bar,
            )

    if mode == "significant":
        se = math.sqrt(candidate_stderr ** 2 + current_stderr ** 2)
        if se == 0.0:
            # Combined SE collapsed (typically n_trials=1). Warn + strict fallback
            # rather than a silent "any Δ>0 wins".
            _warn_se_zero(run_dir, "significant", context="combined_se=0")
            ok = delta > 0
            return GateDecision(
                accept=ok,
                reason=(f"Δ={delta:+.4f} {'>' if ok else '<='} 0 "
                        f"(SE=0 → STRICT fallback, warned)"),
                delta=delta, threshold=0.0,
            )
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
