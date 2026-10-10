"""Optimizer ablation switches: ONE resolver for all seven, one documented precedence (#712).

The switches (what each turns off is the *legacy* behaviour it falls back to):

==================  =======  ==========================================================
key                 default  off =
==================  =======  ==========================================================
dag_parallel        on       single parent = best_id, serial (no ``--parent`` branching)
active_eval         OFF      full-val tiers instead of ledger-driven cells / posterior rule
smart_merge         on       whole-file pairwise merge (merge_search without ``--nway``)
cost_gating         on       legacy gate mode instead of ``reward_gated``
failure_clustering  on       per-task listing, no multi-task hypothesis rule
pregate             on       skip the deterministic candidate checks
context_digest      on       agent gets the raw tables, no digest
==================  =======  ==========================================================

Precedence, highest first (the first one that is set wins; the rest are not consulted):

1. env ``CAPEVOLVE_<NAME>`` (``CAPEVOLVE_DAG_PARALLEL`` ...), non-empty;
2. spec ``optimizer.ablation.<name>``;
3. legacy spec top-level ``ablation.<name>`` (accepted for runs written before this module);
4. the default in the table.

Values are booleans; env accepts 0/false/no/off and 1/true/yes/on. An unknown key under
``optimizer.ablation`` / ``ablation`` or a non-boolean value raises ``ValueError``: a typo must
not silently run the wrong experiment. ``new_engine`` (dag_parallel AND active_eval) is the
single predicate that lets the ceremonies of the legacy round loop (mandatory null control,
minimum 3 siblings) be dropped; with it false every legacy path is untouched.
"""

from __future__ import annotations

import os

#: key -> default
DEFAULTS = {"dag_parallel": True, "active_eval": False, "smart_merge": True, "cost_gating": True,
            "failure_clustering": True, "pregate": True, "context_digest": True}
_TRUE, _FALSE = {"1", "true", "yes", "on"}, {"0", "false", "no", "off"}


def _tables(spec) -> list[dict]:
    """The ablation tables present in ``spec``, highest precedence first."""
    spec = spec if isinstance(spec, dict) else {}
    opt = spec.get("optimizer")
    return [t for t in ((opt.get("ablation") if isinstance(opt, dict) else None), spec.get("ablation"))
            if isinstance(t, dict)]


def _env(key: str):
    raw = os.environ.get(f"CAPEVOLVE_{key.upper()}", "").strip().lower()
    if not raw:
        return None
    if raw in _TRUE | _FALSE:
        return raw in _TRUE
    raise ValueError(f"CAPEVOLVE_{key.upper()}={raw!r}: expected one of {sorted(_TRUE | _FALSE)}")


def resolve(spec: dict | None = None) -> dict[str, bool]:
    """All seven switches for ``spec`` (see module docstring for the precedence)."""
    tables = _tables(spec)
    for t in tables:
        bad = sorted(set(t) - set(DEFAULTS))
        if bad:
            raise ValueError(f"unknown ablation key(s) {bad}; valid keys: {sorted(DEFAULTS)}")
        for k, v in t.items():
            if not isinstance(v, bool):
                raise ValueError(f"ablation.{k} must be true or false, got {v!r}")
    out = {}
    for k, default in DEFAULTS.items():
        v = _env(k)
        if v is None:
            v = next((t[k] for t in tables if k in t), default)
        out[k] = v
    return out


def enabled(key: str, spec: dict | None = None) -> bool:
    if key not in DEFAULTS:
        raise ValueError(f"unknown ablation key {key!r}; valid keys: {sorted(DEFAULTS)}")
    return resolve(spec)[key]


def new_engine(spec: dict | None = None) -> bool:
    """True only when the DAG engine is fully on: concurrent branches AND ledger-driven eval."""
    r = resolve(spec)
    return r["dag_parallel"] and r["active_eval"]
