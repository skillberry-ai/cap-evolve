"""Acceptance gate — the rule that decides whether a candidate edit is kept.

The default mode for every real run is ``paired``. The harness scores candidate and
current on the SAME val tasks, so it passes ``paired_deltas`` and sets
``mode="paired"`` whenever the caller has not pinned a mode and per-task data
aligns (``harness.py`` ``_gate_and_record``, ``gepa.py`` ``_full_val_gate``); the
shipped ``gate_mode`` in ``templates/project/capevolve.yaml`` is ``paired`` too.
Paired tests mean(per-task Δ) against the SE of those deltas, which cancels the
cross-task variance and is far more powerful than the unpaired test.

``decide``'s own ``mode`` parameter still defaults to ``significant`` (prior
agent-optimization work's ``val_improvement_significant``) because that is the only
mode a bare caller with no per-task data can honestly apply; ``paired`` also falls
back to it when ``paired_deltas`` is empty.

Modes: ``paired`` (default in runs) | ``significant`` | ``threshold`` | ``strict``
| ``simplicity_tiebreak`` — see ``decide``'s docstring and the "Gate modes" table
in ``docs/HONEST_EVAL.md``. Every mode's bar is a form of Δ > bar, every mode
compares on VAL and never on TRAIN — ``decide`` takes an explicit ``split`` and
refuses anything but ``val``.
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

    Modes (``paired`` is the default for real runs — the harness selects it; the
    ``mode`` parameter below defaults to ``significant`` only for bare callers that
    have no per-task data to pair):
      - ``paired`` (DEFAULT in runs): accept iff mean(per-task Δ) > k * SE(Δ), where Δ[t] =
        cand_reward[t] - curr_reward[t] over the SAME val tasks. This is the
        correct, far more powerful test: candidate and current are scored on the
        same tasks, so the cross-task variance cancels and only the *paired*
        variance counts. Requires ``paired_deltas``; the loop uses it by default
        when per-task data is available, else falls back to ``significant`` (which is
        announced: the reason is prefixed ``paired→significant`` and a
        ``gate_warning`` is logged). NOTE at ``k_se=1.0``: a gain on exactly ONE of
        n tasks gives mean(Δ) = SE(Δ) *exactly*, so the strict ``>`` rejects it —
        regardless of n and regardless of how large that one gain is. Banking needs
        ≥2 improved tasks, or ``k_se < 1.0``.
      - ``significant``: accept iff delta > k * combined_SE (treats cand & current
        as INDEPENDENT samples — correct only when they were not scored on the
        same tasks; less powerful than ``paired``).
      - ``threshold``:   accept iff delta > ``threshold`` (a flat margin). Note
        ``threshold`` defaults to ``0.0``, so leaving it unset makes this mode
        identical to ``strict``.
      - ``strict``:      accept iff delta > 0 (any improvement).
      - ``simplicity_tiebreak``: like strict, but on a (near-)tie prefer the
        smaller candidate (``candidate_size`` < ``current_size``). PRECONDITION:
        needs both sizes; nothing in the harness or the algorithms populates them
        today, so in a real run this mode behaves exactly like ``strict`` (issue
        #206 tracks plumbing the sizes).

    ``run_dir`` (optional) is used only to log a ``gate_warning`` event when an SE
    collapses to 0 or ``paired`` falls back to ``significant`` (so neither
    degradation is silent).
    """
    if split.lower() != "val":
        raise TrainGateError(
            f"Acceptance must be gated on VAL, got split={split!r}. Gating on "
            "train overfits the optimizer to the data it edits against."
        )

    delta = candidate_val - current_val
    fell_back = ""

    if mode == "paired":
        deltas = list(paired_deltas or [])
        if not deltas:
            # No paired data — fall back to the independent significance test rather
            # than silently passing. (The loop should pass paired_deltas; this guards
            # a direct caller.) Announce it: asking for the strongest test and getting
            # the weaker one must not be invisible, same posture as _warn_se_zero.
            mode = "significant"
            fell_back = "paired→significant (no per-task deltas): "
            log = getattr(run_dir, "log_event", None) if run_dir is not None else None
            if callable(log):
                log("gate_warning", mode="paired",
                    reason=("mode='paired' was requested but no paired_deltas were "
                            "supplied, so the weaker unpaired 'significant' test was "
                            "applied instead. Pass per-task cand-curr deltas over the "
                            "same val tasks to get the paired test."))
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
                reason=(f"{fell_back}Δ={delta:+.4f} {'>' if ok else '<='} 0 "
                        f"(SE=0 → STRICT fallback, warned)"),
                delta=delta, threshold=0.0,
            )
        bar = k_se * se
        ok = delta > bar
        return GateDecision(
            accept=ok,
            reason=(
                f"{fell_back}Δ={delta:+.4f} {'>' if ok else '<='} {k_se}·SE={bar:.4f} "
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
