"""Opt-in v2 gate/budget/split switches, resolved ONCE from env > the run's spec > the v1 default.

Every key defaults to today's behaviour, so a spec without them runs exactly as before. The spec is the
run's own (``specfile.spec_for_run``), which lets scripts that never inherited the CLI's flags (agent
mode, ``gate_check``) read the same config.

  coverage_policy       "veto" (v1: ``min_coverage`` is a hard veto) | "tipping" (retry the incumbent's
                        missing cells, quarantine what stays missing, coverage on the evaluable set,
                        floor ``min_joint_coverage`` plus a tipping-point check)
  min_joint_coverage    0.75   floor of joint coverage on the evaluable set (policy "tipping")
  missing_impute        -0.5   delta imputed for each missing pair by the tipping-point check
  missing_retries       2      attempts to re-run a missing cell
  budget_reserve        false  reserve rollouts before every ``evaluate_candidate``
  split_mode            "legacy" | "pooled" (pool = train + val, seeded F/C partition)
  confirm_fraction      0.48   share of the pool held as the hidden confirm stratum C
  ledger_noise_guard    false  below ``ledger_min_trials`` trials per task, no causal broke/fixed lists
  ledger_min_trials     3
  fault_attribution     false  tag exceptions raised by the candidate's own code (error_kind=candidate)
  hc_feedback_split     "auto" which split the legacy hill-climb PROPOSER learns from: "train" | "val" |
                        "auto" (train when the frozen train and val ids differ as sets, else val). The
                        gate always decides on val; under "train" the proposer's inputs and the run's
                        event/graph logs carry no val task id and val rollouts are sealed (splits.json
                        and baseline.json still list val: follow-up). Not used by pooled/P2/HC-2
                        (they have F/C); there an explicit "train" is a logged no-op.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

COVERAGE_POLICIES = ("veto", "tipping")
SPLIT_MODES = ("legacy", "pooled")
HC_FEEDBACK_SPLITS = ("auto", "train", "val")
ENV_PREFIX = "CAPEVOLVE_"


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def finalize_enabled(spec: dict | None, environ=None) -> bool:
    """Spec key ``finalize`` (default true). False: the run ends after the search loop with its champion
    recorded (no test FINAL, no train/val bookend, no final estimate, no report)."""
    env = (os.environ if environ is None else environ).get(ENV_PREFIX + "FINALIZE")
    v = env if env not in (None, "") else (spec or {}).get("finalize", True)
    return str(v).strip().lower() not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class GateConfig:
    coverage_policy: str = "veto"
    min_joint_coverage: float = 0.75
    missing_impute: float = -0.5
    missing_retries: int = 2
    budget_reserve: bool = False
    split_mode: str = "legacy"
    confirm_fraction: float = 0.48
    ledger_noise_guard: bool = False
    ledger_min_trials: int = 3
    fault_attribution: bool = False
    hc_feedback_split: str = "auto"

    @classmethod
    def from_mapping(cls, spec: dict | None, environ=None) -> "GateConfig":
        spec = dict(spec or {})
        env = os.environ if environ is None else environ
        for f in cls.__dataclass_fields__:
            v = env.get(ENV_PREFIX + f.upper())
            if v not in (None, ""):
                spec[f] = v
        d = cls()
        out = cls(
            coverage_policy=str(spec.get("coverage_policy") or d.coverage_policy),
            min_joint_coverage=float(spec.get("min_joint_coverage", d.min_joint_coverage)),
            missing_impute=float(spec.get("missing_impute", d.missing_impute)),
            missing_retries=int(spec.get("missing_retries", d.missing_retries)),
            budget_reserve=_truthy(spec.get("budget_reserve", d.budget_reserve)),
            split_mode=str(spec.get("split_mode") or d.split_mode),
            confirm_fraction=float(spec.get("confirm_fraction", d.confirm_fraction)),
            ledger_noise_guard=_truthy(spec.get("ledger_noise_guard", d.ledger_noise_guard)),
            ledger_min_trials=int(spec.get("ledger_min_trials", d.ledger_min_trials)),
            fault_attribution=_truthy(spec.get("fault_attribution", d.fault_attribution)),
            hc_feedback_split=str(spec.get("hc_feedback_split") or d.hc_feedback_split).strip().lower())
        if out.coverage_policy not in COVERAGE_POLICIES:
            raise ValueError(f"coverage_policy must be one of {COVERAGE_POLICIES}, got {out.coverage_policy!r}")
        if out.split_mode not in SPLIT_MODES:
            raise ValueError(f"split_mode must be one of {SPLIT_MODES}, got {out.split_mode!r}")
        if not 0.0 < out.confirm_fraction < 1.0:
            raise ValueError("confirm_fraction must be in (0, 1)")
        if not 0.0 <= out.min_joint_coverage <= 1.0:
            raise ValueError("min_joint_coverage must be in [0, 1]")
        if out.hc_feedback_split not in HC_FEEDBACK_SPLITS:
            raise ValueError(f"hc_feedback_split must be one of {HC_FEEDBACK_SPLITS}, "
                             f"got {out.hc_feedback_split!r}")
        return out

    @classmethod
    def for_run(cls, run_dir) -> "GateConfig":
        from .specfile import spec_for_run
        return cls.from_mapping(spec_for_run(run_dir) if run_dir is not None else {})


def hc_feedback_split_setting(spec: dict | None, environ=None) -> tuple[str, str]:
    """The REQUESTED ``hc_feedback_split`` (validated) and where it came from: ``env`` | ``spec`` | ``default``.

    Requested, not effective: ``harness.resolve_hc_feedback_split`` turns ``auto`` into ``train``/``val`` from
    the run's frozen splits, once per run."""
    env = (os.environ if environ is None else environ).get(ENV_PREFIX + "HC_FEEDBACK_SPLIT")
    if env not in (None, ""):
        source = "env"
    elif (spec or {}).get("hc_feedback_split") not in (None, ""):
        source = "spec"
    else:
        source = "default"
    return GateConfig.from_mapping(spec, environ).hc_feedback_split, source
