"""Ablation-program switches (spec keys ``abl_*``). Inactive unless a key is set.

``load(run_dir_or_spec)`` validates and returns an :class:`AblConfig`; a typo raises
ValueError so it can never silently run the wrong experiment.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_CHOICES = {
    "capability": ("P", "TD", "TC"),
    "history": ("none", "state"),
    "info": ("reward", "eval", "fail"),
    "gate": ("none", "disjoint"),
}
_KEYS = ("abl_capability", "abl_history", "abl_info", "abl_gate",
         "abl_feedback_ids", "abl_gate_ids")


@dataclass(frozen=True)
class AblConfig:
    capability: str | None = None
    history: str | None = None
    info: str | None = None
    gate: str | None = None
    feedback_ids: tuple = field(default_factory=tuple)
    gate_ids: tuple = field(default_factory=tuple)

    @property
    def active(self) -> bool:
        return any((self.capability, self.history, self.info, self.gate))


def _ids(v, name):
    if v is None:
        return ()
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{name} must be a list of task ids")
    return tuple(str(x) for x in v)


def load(run_dir_or_spec) -> AblConfig:
    if isinstance(run_dir_or_spec, dict):
        spec = run_dir_or_spec
    else:
        from . import specfile
        spec = specfile.spec_for_run(run_dir_or_spec)
    spec = spec or {}
    vals = {}
    for name, allowed in _CHOICES.items():
        key = f"abl_{name}"
        v = spec.get(key)
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip().upper() if name == "capability" else v.strip().lower()
        if not isinstance(v, str) or v not in allowed:
            raise ValueError(f"{key}={v!r} is invalid; expected one of {list(allowed)}")
        vals[name] = v
    if len(vals) > 1:
        raise ValueError("at most one abl_* factor may be set per run, got: "
                         + ", ".join(f"abl_{k}" for k in vals))
    fb = _ids(spec.get("abl_feedback_ids"), "abl_feedback_ids")
    gt = _ids(spec.get("abl_gate_ids"), "abl_gate_ids")
    if vals.get("gate") == "disjoint":
        if not fb or not gt or set(fb) & set(gt):
            raise ValueError("abl_gate=disjoint needs two non-empty, disjoint id lists "
                             "(abl_feedback_ids, abl_gate_ids)")
    elif fb or gt:
        raise ValueError("abl_feedback_ids/abl_gate_ids are only valid with abl_gate=disjoint")
    if vals.get("gate") == "disjoint" and str(spec.get("coverage_policy", "")).strip().lower() == "tipping":
        raise ValueError("abl_gate: disjoint is not supported with coverage_policy: tipping")
    return AblConfig(feedback_ids=fb, gate_ids=gt, **vals)
