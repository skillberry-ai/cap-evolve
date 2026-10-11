"""Promotion rule P: the one accept rule both search algorithms can share (opt-in).

Why a shared module: hill-climb's paired k_se gate and agent-optimize's reward_gated test have
different effective bars (``objectives.NOISE_FLOOR``), so comparing the algorithms compares gate
strictness too. Rule P (research/capevolve-paper/protocol/analysis_plan.md section 8):

  1. SCREEN   paired gate on the full UNMASKED per-task delta vector: mean > k_se * SE.
  2. CONFIRM  re-measure candidate AND incumbent with ``n_conf`` FRESH trials (new seeds) on the
              same tasks; promote iff mean >= ``dmin`` and mean / SE >= ``z_conf``.
  3. The incumbent's confirmation measurement is the baseline for the next iteration (the screen
     measurement selected the candidate, so it is biased upward).

Pure and stdlib-only: callers own the evaluations. ``confirm_fn`` is invoked only after a screen
pass, so a rejected candidate costs nothing extra. Spec keys (all optional, ``promotion_rule``
absent = today's gates): ``promotion_rule: P``, ``promotion_k_se``, ``promotion_n_conf``,
``promotion_dmin``, ``promotion_z_conf``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

RULES = ("P",)


@dataclass(frozen=True)
class PromotionParams:
    k_se: float = 1.0
    n_conf: int = 10
    dmin: float = 0.02
    z_conf: float = 2.0

    @classmethod
    def from_spec(cls, spec: dict | None):
        """``None`` when the spec does not ask for rule P (the default); else validated params."""
        spec = spec or {}
        rule = spec.get("promotion_rule")
        if rule in (None, "", "none", False):
            return None
        if rule not in RULES:
            raise ValueError(f"promotion_rule must be one of {RULES} or unset, got {rule!r}")
        d = cls()
        out = cls(k_se=float(spec.get("promotion_k_se", d.k_se)),
                  n_conf=int(spec.get("promotion_n_conf", d.n_conf)),
                  dmin=float(spec.get("promotion_dmin", d.dmin)),
                  z_conf=float(spec.get("promotion_z_conf", d.z_conf)))
        if out.n_conf < 1:
            raise ValueError("promotion_n_conf must be >= 1")
        return out


def paired_stats(deltas) -> tuple[float, float, int]:
    """(mean, SE, n) of a per-task delta vector; SE = sd / sqrt(n), 0.0 when n < 2."""
    d = [float(x) for x in deltas]
    n = len(d)
    if n == 0:
        return 0.0, 0.0, 0
    m = sum(d) / n
    if n < 2:
        return m, 0.0, n
    return m, math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1) / n), n


def _z(mean: float, se: float) -> float:
    if se > 0:
        return mean / se
    return math.inf if mean > 0 else (-math.inf if mean < 0 else 0.0)


def screen(deltas, k_se: float = 1.0) -> dict:
    """Stage 1. With fewer than two tasks there is no SE, so nothing passes."""
    m, se, n = paired_stats(deltas)
    ok = n >= 2 and m > k_se * se and m > 0
    return {"pass": bool(ok), "mean": m, "se": se, "z": _z(m, se), "n": n, "k_se": k_se}


def confirm(deltas, dmin: float = 0.02, z_conf: float = 2.0) -> dict:
    """Stage 2 on FRESH-trial deltas: mean >= dmin and mean/SE >= z_conf (SE=0 with mean>0 passes)."""
    m, se, n = paired_stats(deltas)
    z = _z(m, se)
    ok = n >= 2 and m >= dmin and m > 0 and z >= z_conf
    return {"pass": bool(ok), "mean": m, "se": se, "z": z, "n": n, "dmin": dmin, "z_conf": z_conf}


@dataclass
class PromotionResult:
    promote: bool
    stage: str                      # screen_reject | confirm_reject | promoted
    screen: dict
    confirm: dict | None = None
    reason: str = ""
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        def clean(x):
            return None if x is None else {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                                           for k, v in x.items()}
        return {"rule": "P", "promote": self.promote, "stage": self.stage, "screen": clean(self.screen),
                "confirm": clean(self.confirm), "reason": self.reason, "params": self.params}


def decide(screen_deltas, confirm_fn, params: PromotionParams | None = None) -> PromotionResult:
    """Run rule P. ``confirm_fn() -> fresh paired delta vector`` is called only after a screen pass."""
    p = params or PromotionParams()
    s = screen(screen_deltas, p.k_se)
    pd = asdict(p)
    if not s["pass"]:
        return PromotionResult(False, "screen_reject", s, None,
                               f"P screen: mean {s['mean']:+.4f} <= {p.k_se:g}*SE {s['se']:.4f} (n={s['n']})", pd)
    c = confirm(confirm_fn(), p.dmin, p.z_conf)
    if not c["pass"]:
        return PromotionResult(False, "confirm_reject", s, c,
                               f"P confirm: fresh mean {c['mean']:+.4f}, z {c['z']:.2f} "
                               f"(need >= {p.dmin:g} and z >= {p.z_conf:g}; n={c['n']})", pd)
    return PromotionResult(True, "promoted", s, c,
                           f"P promoted: screen {s['mean']:+.4f}, fresh {c['mean']:+.4f}, z {c['z']:.2f}", pd)
