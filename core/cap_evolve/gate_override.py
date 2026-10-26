"""Experiment-only gate overrides for the K02R searches (off unless the spec sets ``gate_override``).

    gate_override: naive   # accept iff the paired mean delta >= 0 (no significance test)
    gate_override: none    # accept every scored, decisive candidate (no gate)

The stock gate's decision is still computed and kept (``gate_override_shadow`` on the step record).
Indecisive steps (coverage below the bar) and steps with no scored task are never accepted, as in the stock path.
Absent key: nothing here runs, the stock path is byte-identical.
"""
from __future__ import annotations

MODES = ("naive", "none")


def mode(run_dir) -> str | None:
    from .specfile import spec_for_run
    v = (spec_for_run(run_dir) or {}).get("gate_override")
    if v in (None, "", False):
        return None
    v = str(v).strip().lower()
    if v not in MODES:
        raise ValueError(f"gate_override must be one of {MODES}, got {v!r}")
    return v


def apply(decision, m: str, n_scored: int) -> dict:
    """Mutate ``decision`` per mode ``m``; return the stock decision as a dict (the shadow)."""
    shadow = decision.to_dict()
    if decision.indecisive or n_scored <= 0:
        return shadow
    stock = bool(decision.accept)
    if m == "none":
        decision.accept = True
        decision.reason = f"GATE-NONE: accepted without test; stock gate would have said accept={stock} ({shadow.get('reason')})"
    else:
        ok = decision.delta is not None and float(decision.delta) >= 0.0
        decision.accept = ok
        decision.reason = (f"GATE-NAIVE: delta {float(decision.delta or 0.0):+.4f} {'>=' if ok else '<'} 0 -> {'accept' if ok else 'reject'}; "
                           f"stock gate would have said accept={stock} ({shadow.get('reason')})")
    return shadow
