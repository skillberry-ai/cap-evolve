"""Acceptance gate — the rule that decides whether a candidate edit is kept.

**The default for every real run is the ``paired`` gate.** The optimization loop
builds the aligned per-task delta vector and selects ``paired`` unless the caller
pinned a mode (``harness.py:1524-1526``, ``gepa.py:741-743``), and the shipped
config says so (``templates/project/capevolve.yaml``: ``gate_mode: paired``).
``decide``'s own ``mode=`` parameter defaults to ``significant`` only as the
fallback for a bare caller that has no per-task data.

The bar is ``Δ > k·SE``, not ``Δ > 0``, because search is a noise amplifier:
screen enough candidates and the best-looking one is best by luck, so a ``Δ > 0``
rule banks noise as progress and the val curve climbs while nothing improved.
Requiring the gain to clear ``k`` standard errors of its own measurement error is
what makes an accept mean something.

All gates compare on VAL and never on TRAIN — ``decide`` takes an explicit
``split`` and refuses anything but ``val``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class GateDecision:
    accept: bool
    reason: str
    delta: float
    threshold: float = 0.0
    #: True when the gate declined to judge at all (not "the edit was bad"). The
    #: caller must not treat this as a content rejection: it should not count
    #: toward the stall counter and it says nothing about the candidate's quality.
    indecisive: bool = False
    #: The smallest true effect this verdict could have resolved, i.e. ``2 * SE`` of the
    #: measurement that produced ``delta``. ``None`` when no SE was computable (threshold/
    #: strict modes, or too few paired samples). Reported so the driver reads "this round can
    #: resolve ±X" BEFORE reading the delta — four runs of null results on tau2_airline were
    #: read as "the edits were bad" when the gate simply could not resolve anything that small
    #: (see docs/TAU2_SUMMARY.md).
    resolvable_effect_size: float | None = None
    #: The COMPOSITION of the change behind ``delta``: which val tasks this candidate broke
    #: (were passing under the parent, dropped measurably) and which it fixed. The gate
    #: decides on the MEAN, so a candidate that TRADES tasks passes whenever the net is
    #: positive — and until these were recorded, nothing said so. Run 36175707483's champion
    #: was accepted on a positive net while breaking a task against BOTH concurrent controls,
    #: and on the sealed 280-task split its composition was 54 improved / 17 regressed, every
    #: sampled regression a 1.000 → 0.000. They are DESCRIPTIVE: they do not move the verdict
    #: unless the caller opts in with ``gate_max_broke``. Classified by ``harness.movement``,
    #: which is also what LEDGER.md publishes, so a run cannot say two different things about
    #: what its accepted candidate did.
    broke: list = field(default_factory=list)
    fixed: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "accept": self.accept,
            "reason": self.reason,
            "delta": self.delta,
            "threshold": self.threshold,
            "indecisive": self.indecisive,
            "resolvable_effect_size": self.resolvable_effect_size,
            "broke": list(self.broke),
            "fixed": list(self.fixed),
            "n_broke": len(self.broke),
            "n_fixed": len(self.fixed),
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


def _warn_low_coverage(run_dir, *, coverage: float, min_coverage: float) -> None:
    """Log a ``gate_warning`` when too little of the split actually ran.

    Loud and auditable on purpose: a run that keeps producing indecisive steps is
    burning budget on an infrastructure fault, and the event stream is where an
    operator (or the CI assert) can see that rather than reading a plausible-looking
    val score that happens to be meaningless.
    """
    if run_dir is None:
        return
    log = getattr(run_dir, "log_event", None)
    if callable(log):
        log("gate_warning",
            mode="coverage",
            reason=("too few val tasks produced a valid score — the gate is "
                    "declining to judge this candidate. This is an infrastructure "
                    "failure (runner/environment), not a bad edit: fix the runner "
                    "before spending more budget."),
            context=f"coverage={coverage:.3f} < min_coverage={min_coverage:.3f}")


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
    paired_deltas: list | None = None,
    paired_se_floor: float = 0.0,
    coverage: float | None = None,
    min_coverage: float = 0.6,
    run_dir=None,
    broke: list | None = None,
    fixed: list | None = None,
    gate_max_broke: int | None = None,
) -> GateDecision:
    """Decide whether to accept the candidate — see ``_verdict`` for the statistics.

    ``broke``/``fixed`` are the val tasks the candidate broke and fixed versus its parent
    (from ``harness.movement``). They are RECORDED on the decision and, unless
    ``gate_max_broke`` is set, change nothing: the verdict is exactly ``_verdict``'s. That
    split is the point of this function. The gate decides on the MEAN, so a candidate that
    trades tasks — fixing some, breaking others — is accepted whenever the net is positive,
    and run 36175707483's champion was accepted while breaking a task against BOTH of its
    concurrent controls. On the sealed 280-task split its composition was 54 improved / 17
    regressed, every sampled regression a 1.000 → 0.000. The net was genuinely positive, so
    the gate was not WRONG; it was indifferent to composition, and nothing forced the
    trade-off to be examined.

    ``gate_max_broke`` (None = off, today's behaviour) is the opt-in veto: at most this many
    broken tasks, or the candidate is rejected with a reason naming the ids. It only ever
    SUBTRACTS — it can turn an accept into a reject, never the reverse, and it never touches
    an ``indecisive`` verdict (an unjudged candidate has no composition to hold against it).

    Regressions deliberately do NOT auto-reject. On a 40-task val split with SE ≈ 0.079 a
    hard no-regression rule rejects nearly everything, and it would be noise-driven: these
    runs show tasks flipping 1.0 → 0.0 between two BYTE-IDENTICAL control replicates. The
    per-task ``2·SE`` bar in ``harness.move_is_resolved`` removes the worst of that, not all
    of it. So: measure and surface always, veto only on request.
    """
    d = _verdict(current_val, candidate_val, split=split, mode=mode, k_se=k_se,
                 candidate_stderr=candidate_stderr, current_stderr=current_stderr,
                 threshold=threshold, paired_deltas=paired_deltas,
                 paired_se_floor=paired_se_floor, coverage=coverage,
                 min_coverage=min_coverage, run_dir=run_dir)
    d.broke = [str(t) for t in (broke or [])]
    d.fixed = [str(t) for t in (fixed or [])]
    if gate_max_broke is None or d.indecisive or not d.accept:
        # Unset, unjudged, or already rejected: nothing to subtract. With the knob unset this
        # returns ``_verdict``'s decision untouched down to the reason STRING — which matters
        # beyond history comparability, because ``dashboard.reduce_run`` regexes the gate's
        # numbers back out of exactly that string.
        return d
    if len(d.broke) > int(gate_max_broke):
        d.accept = False
        d.reason += (f"; REJECTED by gate_max_broke={int(gate_max_broke)} — broke "
                     f"{d.broke} (fixed {d.fixed})")
    return d


def _verdict(
    current_val: float,
    candidate_val: float,
    *,
    split: str = "val",
    mode: str = "significant",
    k_se: float = 1.0,
    candidate_stderr: float = 0.0,
    current_stderr: float = 0.0,
    threshold: float = 0.0,
    paired_deltas: list | None = None,
    paired_se_floor: float = 0.0,
    coverage: float | None = None,
    min_coverage: float = 0.6,
    run_dir=None,
) -> GateDecision:
    """The gate's STATISTICS — the accept/reject test itself, and nothing else.

    Deliberately knows nothing about per-task composition: ``decide`` records that on top
    and applies the opt-in ``gate_max_broke`` veto afterwards, so reading this function is
    enough to know what the bar is, and a change to the reporting cannot move the bar.

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
      - ``strict``:      accept iff delta > 0 (any improvement). Only safe with a
        near-zero-variance scorer: with a noisy one it banks noise as progress.

    ``coverage`` is the fraction of val tasks that produced a real measurement
    (``SplitResult.coverage``). Below ``min_coverage`` the gate REFUSES TO JUDGE and
    returns an ``indecisive`` decision rather than a rejection: when most of the
    split never ran, the val number describes the infrastructure, not the edit, and
    calling that a regression both discards a possibly-good candidate and tells the
    optimizer to go fix content that was never evaluated. Pass ``min_coverage=0.0``
    to disable the guard.

    ``paired_se_floor`` (paired mode only, 0 = off) is a lower bound on the paired SE,
    for when the CROSS-TASK SPREAD of ``paired_deltas`` is known to understate the real
    uncertainty. The paired SE is estimated from how much the per-task deltas differ from
    each other, which silently assumes each per-task delta is measured precisely. On a few
    tasks it is not: a footprint-restricted vector of 4 real deltas whose values happen to
    be {0, +0.1, 0, +0.1} yields SE 0.0046 and an ACCEPT, while each of those +0.1 moves is
    one flipped rollout out of ten — moves ``harness.move_is_resolved`` refuses to call real
    at all. Pass ``sqrt(Σ_t (par_se_t² + cand_se_t²)) / n`` (see
    ``harness.paired_se_floor``) and the two tests stop contradicting each other. Measured
    on run_finalrun6's cand_7 — a docstring-only edit — this is the difference between a
    fabricated accept at SE 0.0046 and a reject at the floor's 0.0113.
    """
    if split.lower() != "val":
        raise TrainGateError(
            f"Acceptance must be gated on VAL, got split={split!r}. Gating on "
            "train overfits the optimizer to the data it edits against."
        )

    delta = candidate_val - current_val

    if coverage is not None and min_coverage > 0.0 and coverage < min_coverage:
        pct, bar = coverage * 100.0, min_coverage * 100.0
        reason = (
            f"INDECISIVE: only {pct:.0f}% of val tasks produced a valid score "
            f"(< {bar:.0f}% required). The evaluation measured the infrastructure, "
            "not the edit — not counted as a rejection."
        )
        _warn_low_coverage(run_dir, coverage=coverage, min_coverage=min_coverage)
        return GateDecision(accept=False, reason=reason, delta=delta,
                            threshold=0.0, indecisive=True)

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
            # The cross-task spread cannot go below what per-task trial noise implies.
            se = max(se, float(paired_se_floor or 0.0))
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
                        f"(SE={se:.4f}, n={n}, resolvable effect size 2·SE={2 * se:.4f})"),
                delta=mean_d, threshold=bar,
                resolvable_effect_size=round(2 * se, 6),
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
                f"(SE={se:.4f}, resolvable effect size 2·SE={2 * se:.4f})"
            ),
            delta=delta,
            threshold=bar,
            resolvable_effect_size=round(2 * se, 6),
        )

    if mode == "threshold":
        ok = delta > threshold
        return GateDecision(ok, f"Δ={delta:+.4f} {'>' if ok else '<='} {threshold:.4f}", delta, threshold)

    if mode == "strict":
        ok = delta > 0
        return GateDecision(ok, f"Δ={delta:+.4f} {'>' if ok else '<='} 0", delta, 0.0)

    raise ValueError(f"unknown gate mode: {mode!r}")
