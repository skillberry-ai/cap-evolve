"""Contract: the gate refuses split=train, at SE=0 the significance mode falls back
to strict (accept any Δ>0) instead of silently mis-acting, and the CLI's
``--paired-deltas`` refuses malformed or inconsistent input rather than gating on it.
"""

from __future__ import annotations

import sys

import _bootstrap  # noqa: F401

from cap_evolve.gate import TrainGateError, decide
from cap_evolve.skillcheck import Checker, import_run


def _paired_cli(run, deltas: str, current=0.5, candidate=0.6):
    """Parse deltas the way run.py's CLI does; return ('error', msg) on refusal."""
    box = []

    def error(msg):
        raise ValueError(msg)

    try:
        box.append(run.parse_paired_deltas(deltas, current, candidate, error))
    except ValueError as exc:
        return ("error", str(exc))
    return ("ok", box[0])


def main() -> int:
    c = Checker("gate")
    run = import_run()
    c.require_main(run)

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

    # 4. paired — the mode every real run uses. A gain on exactly 1 of n tasks lands
    #    mean(Δ)=SE(Δ) exactly, so k_se=1.0 REJECTS it at any n; 2 of n clears it.
    one_of_10 = [1.0] + [0.0] * 9
    d_one = decide(0.5, 0.6, split="val", mode="paired", k_se=1.0, paired_deltas=one_of_10)
    d_one_lenient = decide(0.5, 0.6, split="val", mode="paired", k_se=0.2,
                           paired_deltas=one_of_10)
    d_two = decide(0.5, 0.7, split="val", mode="paired", k_se=1.0,
                   paired_deltas=[1.0, 1.0] + [0.0] * 8)
    c.check(not d_one.accept and "n=10" in d_one.reason,
            f"1-of-n gain must NOT clear k_se=1.0 (mean=SE exactly): {d_one.to_dict()}",
            note="paired at k_se=1.0 rejects a 1-of-n gain (mean(Δ)=SE(Δ))")
    c.check(d_one_lenient.accept,
            f"1-of-n gain must clear k_se=0.2: {d_one_lenient.to_dict()}")
    c.check(d_two.accept,
            f"2-of-n gain must clear k_se=1.0: {d_two.to_dict()}",
            note="paired banks >=2 improved tasks at the default k_se")

    # 5. paired with no deltas falls back to significant, and SAYS SO
    d_fb = decide(0.5, 0.62, split="val", mode="paired", k_se=1.0,
                  candidate_stderr=0.03, current_stderr=0.03)
    c.check("paired→significant" in d_fb.reason,
            f"paired-without-deltas fallback must be announced in the reason: {d_fb.to_dict()}",
            note="paired→significant fallback is disclosed, not silent")

    # 6. the CLI refuses malformed and inconsistent --paired-deltas rather than
    #    printing a confident decision for an n the run never used.
    for bad, why in [("1,abc,0", "non-numeric"), ("1;0;0", "semicolons"),
                     ("1,0", "wrong length (mean 0.5 != candidate-current 0.1)")]:
        kind, msg = _paired_cli(run, bad)
        c.check(kind == "error", f"--paired-deltas {bad!r} ({why}) must be refused, got {msg!r}",
                note=f"--paired-deltas refuses {why}")
    kind, val = _paired_cli(run, "")
    c.check(kind == "ok" and val is None,
            f"empty --paired-deltas must yield None (documented fallback), got {val!r}")
    kind, val = _paired_cli(run, "1, 0, 0, 0, 0, 0, 0, 0, 0, 0,")
    c.check(kind == "ok" and val == one_of_10,
            f"consistent --paired-deltas must parse (whitespace/trailing comma ok), got {val!r}",
            note="happy path parses; mean(Δ) is cross-checked against candidate-current")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
