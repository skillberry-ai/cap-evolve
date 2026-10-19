"""Promotion rule P: the one accept rule both search algorithms can share (opt-in).

Why a shared module: hill-climb's paired k_se gate and agent-optimize's reward_gated test have
different effective bars (``objectives.NOISE_FLOOR``), so comparing the algorithms compares gate
strictness too. Rule P (frozen promotion rule):

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

RULES = ("P", "P2")


@dataclass(frozen=True)
class PromotionParams:
    k_se: float = 1.0
    n_conf: int = 10
    dmin: float = 0.02
    z_conf: float = 2.0
    min_coverage: float = 0.6       # confirmation must cover this fraction of the screen's task set

    @classmethod
    def from_spec(cls, spec: dict | None):
        """``None`` when the spec does not ask for rule P (the default); else validated params."""
        spec = spec or {}
        rule = spec.get("promotion_rule")
        if rule in (None, "", "none", False):
            return None
        if rule not in RULES:
            raise ValueError(f"promotion_rule must be one of {RULES} or unset, got {rule!r}")
        if rule == "P2":
            return None     # rule P2 has its own evaluator (``P2Params`` / ``evaluator.P2Evaluator``)
        d = cls()
        out = cls(k_se=float(spec.get("promotion_k_se", d.k_se)),
                  n_conf=int(spec.get("promotion_n_conf", d.n_conf)),
                  dmin=float(spec.get("promotion_dmin", d.dmin)),
                  z_conf=float(spec.get("promotion_z_conf", d.z_conf)),
                  min_coverage=float(spec.get("promotion_min_coverage", d.min_coverage)))
        if out.n_conf < 1:
            raise ValueError("promotion_n_conf must be >= 1")
        return out


@dataclass(frozen=True)
class P2Params:
    """Rule P2 ("SH-C", see ``evaluator``): K-candidate rounds, kill-only rungs on the feedback stratum
    F, one fresh confirmation on the hidden stratum C against a concurrently measured incumbent.
    Spec keys are ``p2_<field>``; ``promotion_rule: P2`` turns the rule on (rule P is untouched).

    One error convention for both paths: every accept test is one-sided with a per-test false-accept
    rate of about 0.05 (``z_conf`` 1.7 for the K >= 2 confirmation, ``gs_c`` 1.6 for the K = 1
    group-sequential test). A round of K >= 2 sends at most ``max_survivors`` (2) candidates to
    confirmation, which bounds the round false-accept rate by about 0.10; a K = 1 round has one test, so
    its round rate is about 0.05."""
    k: int = 8                       # candidates per round
    k_small: int = 6                 # ... when max_metric_calls <= small_budget
    small_budget: int = 600
    rung_sizes: tuple = (12, 36)     # CUMULATIVE distinct F tasks per candidate after rung 1 / rung 2 (x trials rollouts)
    max_survivors: int = 2           # candidates sent to confirmation per round
    conf_n: int = 147                # fresh rollouts per confirmed candidate on C; 0 = trials * |C| (auto)
    trials: int = 1                  # num_trials: trials per task at every stage (rung sizes are in TASKS)
    ctrl_m: int = 4                  # incumbent control trials per C task
    incumbent_trials: int = 4        # incumbent trials per F task (ranking only)
    z_conf: float = 1.7              # one-sided; <= max_survivors tests per round (round FWER <= 0.10, also with heterogeneous per-task effects)
    dmin: float = 0.02
    min_coverage: float = 0.6
    chunk: int = 20                  # rollouts per Job
    gs_looks: tuple = (12, 24, 49, 98, 147)
    gs_c: float = 1.6                # O'Brien-Fleming-type boundary constant: false accept ~0.05 per candidate
    gs_futility: tuple = (-0.5, 0.0, 0.3, 0.7)

    @classmethod
    def from_spec(cls, spec: dict | None):
        """``None`` unless ``promotion_rule: P2``; else validated params."""
        spec = spec or {}
        if spec.get("promotion_rule") != "P2":
            return None
        d = cls()
        trials = max(1, int(spec.get("p2_trials", spec.get("num_trials", 1)) or 1))
        # ``num_trials`` is honoured at every stage: the incumbent's ranking draws, the control and (unless
        # ``p2_conf_n`` is set explicitly) the confirmation each get at least ``trials`` draws per task, and
        # every rung evaluates each of its tasks ``trials`` times. trials = 1 changes nothing.
        out = cls(
            trials=trials,
            k=int(spec.get("p2_k", d.k)), k_small=int(spec.get("p2_k_small", d.k_small)),
            small_budget=int(spec.get("p2_small_budget", d.small_budget)),
            rung_sizes=tuple(int(x) for x in spec.get("p2_rung_sizes", d.rung_sizes)),
            max_survivors=int(spec.get("p2_max_survivors", d.max_survivors)),
            conf_n=int(spec["p2_conf_n"]) if "p2_conf_n" in spec else (0 if trials > 1 else d.conf_n),
            ctrl_m=max(trials, int(spec.get("p2_ctrl_m", d.ctrl_m))),
            incumbent_trials=max(trials, int(spec.get("p2_incumbent_trials", d.incumbent_trials))),
            z_conf=float(spec.get("p2_z_conf", d.z_conf)), dmin=float(spec.get("p2_dmin", d.dmin)),
            min_coverage=float(spec.get("promotion_min_coverage", d.min_coverage)),
            chunk=int(spec.get("p2_chunk", d.chunk)),
            gs_looks=tuple(int(x) for x in spec.get("p2_gs_looks", d.gs_looks)),
            gs_c=float(spec.get("p2_gs_c", d.gs_c)),
            gs_futility=tuple(float(x) for x in spec.get("p2_gs_futility", d.gs_futility)))
        if out.conf_n < 0 or min(out.k, out.ctrl_m, out.chunk, out.max_survivors, out.incumbent_trials) < 1:
            raise ValueError("p2_k, p2_conf_n, p2_ctrl_m, p2_chunk, p2_max_survivors and "
                             "p2_incumbent_trials must be >= 1")
        if len(out.rung_sizes) != 2 or not 0 < out.rung_sizes[0] <= out.rung_sizes[1]:
            raise ValueError("p2_rung_sizes must be two cumulative sizes, 0 < r1 <= r2")
        if not out.gs_looks or list(out.gs_looks) != sorted(out.gs_looks):
            raise ValueError("p2_gs_looks must be increasing")
        return out

    def k_for_budget(self, max_metric_calls: int) -> int:
        return self.k_small if 0 < max_metric_calls <= self.small_budget else self.k

    def conf_n_for(self, n_confirm_tasks: int) -> int:
        """Fresh rollouts per confirmed candidate: ``conf_n``, or ``trials * |C|`` when it is auto (0)."""
        return self.conf_n if self.conf_n > 0 else max(1, self.trials * int(n_confirm_tasks))

    def worst_case_cost(self, k: int, n_control_tasks: int) -> int:
        """Rollouts a round of ``k`` can cost: rung 1 + rung 2 + control + the confirmations."""
        r1, r2 = self.rung_sizes
        survivors = min(self.max_survivors, max(1, k // 4))
        t = self.trials
        return (k * r1 * t + max(1, k // 2) * (r2 - r1) * t + self.ctrl_m * n_control_tasks
                + survivors * self.conf_n_for(n_control_tasks))



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


def confirm(deltas, dmin: float = 0.02, z_conf: float = 2.0, n_planned: int | None = None,
            min_coverage: float = 0.6) -> dict:
    """Stage 2 on FRESH-trial deltas: mean >= dmin and mean/SE >= z_conf (SE=0 with mean>0 passes).
    ``n_planned`` = the screen's task count: if fewer than ``min_coverage`` of them survived the
    confirmation (errored trials dropped from the paired vector), the confirmation is void, never a
    pass on whichever tasks happened to survive."""
    m, se, n = paired_stats(deltas)
    z = _z(m, se)
    cov = 1.0 if not n_planned else n / n_planned
    ok = n >= 2 and m >= dmin and m > 0 and z >= z_conf and cov >= min_coverage
    return {"pass": bool(ok), "mean": m, "se": se, "z": z, "n": n, "dmin": dmin, "z_conf": z_conf,
            "coverage": cov, "min_coverage": min_coverage}


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


def decide(screen_deltas, confirm_fn, params: PromotionParams | None = None,
           n_planned: int | None = None) -> PromotionResult:
    """Run rule P. ``confirm_fn() -> fresh paired delta vector`` is called only after a screen pass."""
    p = params or PromotionParams()
    s = screen(screen_deltas, p.k_se)
    pd = asdict(p)
    if not s["pass"]:
        return PromotionResult(False, "screen_reject", s, None,
                               f"P screen: mean {s['mean']:+.4f} <= {p.k_se:g}*SE {s['se']:.4f} (n={s['n']})", pd)
    c = confirm(confirm_fn(), p.dmin, p.z_conf, n_planned or s["n"], p.min_coverage)
    if not c["pass"]:
        return PromotionResult(False, "confirm_reject", s, c,
                               f"P confirm: fresh mean {c['mean']:+.4f}, z {c['z']:.2f} "
                               f"(need >= {p.dmin:g} and z >= {p.z_conf:g}; n={c['n']}, "
                               f"coverage {c['coverage']:.2f} of the screen's tasks, need >= {p.min_coverage:g})", pd)
    return PromotionResult(True, "promoted", s, c,
                           f"P promoted: screen {s['mean']:+.4f}, fresh {c['mean']:+.4f}, z {c['z']:.2f}", pd)
