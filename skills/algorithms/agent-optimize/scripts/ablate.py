"""ablate -- offline replay + ablation harness for the optimizer engine (#707).

SIMULATOR RESULTS ARE NOT EVIDENCE OF REAL PERFORMANCE. They show how the *decision machinery*
(the real ``posterior``/``sched`` code, plus switch plumbing) behaves in a toy world whose
task-outcome rates come from a recorded run and whose candidates are *assumed* per-task rate
shifts (``PARAMS``). A real-agent claim needs ``real`` mode run by a human/agent (see
docs/HOLDOUT_PROTOCOL.md). Every output carries ``LABEL``.

Sub-commands
  replay   decisions of the new engine on the recorded run_20261008_150326 (fixture, no network)
  sim      the config-switch matrix in a seeded task-outcome simulator (JSON + markdown)
  real     DRY RUN: write one spec per arm (``optimizer.ablation.*`` only) and print the commands

Arms are driven ONLY by ``optimizer.ablation.*`` resolved through ``cap_evolve.optimizer_config``
(env ``CAPEVOLVE_*`` is ignored while simulating). What the simulator models for each switch is in
``SWITCH_MODEL``; ``context_digest`` acts on LLM proposal quality, which a rate-shift simulator
cannot measure, so it is a declared no-op here.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from cap_evolve import optimizer_config, posterior, sched

HERE = Path(__file__).resolve()
FIXTURE = HERE.parents[4] / "core" / "tests" / "fixtures" / "replay_run_20261008.json"
LABEL = ("SIMULATED / REPLAYED OFFLINE -- NOT EVIDENCE OF REAL AGENT PERFORMANCE. Simulator candidate "
         "effects are assumed (PARAMS), not measured; only the decision machinery is real code.")

# ---- assumed simulator parameters (all of these are guesses; sweep them before believing a ranking) ----
PARAMS = {
    "budget": 1500,            # rollouts per run (the recorded run spent 2270)
    "siblings": 3,             # concurrent branches per round when dag_parallel is on
    "p_defect": 0.08,          # share of proposals with a hidden-write style defect (cand_10 class)
    "p_help": 0.3, "p_null": 0.4,   # real improvement / no-effect (noise-level, like cand_1..8); rest hurt
    "null_sd": 0.03, "harm_mu": -0.10,
    "blocks": 10, "edit_blocks": (1, 2),   # policy blocks an edit touches (merge conflicts are block-level)
    "single_tasks": (1, 3),    # tasks an edit targets WITHOUT failure_clustering
    "cluster_tasks": (4, 8),   # ... WITH failure_clustering (cluster-level edits)
    "shift_mu": 0.30, "shift_sd": 0.20,   # per-targeted-task rate shift when the edit helps
    "p_side": 0.30, "side_sd": 0.04,      # side-effect noise on untargeted tasks
    "p_cost_bloat": 0.25, "cost_bloat": 0.15, "cost_noise": 0.06,   # +15% cost edits (cand_1/4/7: +14..17%)
    "cost_tol": 1.05,          # cost_gating rejects estimated cost ratio above this
    "tau": 0.028,              # eval-window drift sd on a rate (eval_statistics.md); common-mode if interleaved
    "p_pair_merge_ok": 0.3,    # legacy whole-file merge success even when edits touch disjoint blocks
    "optimizer_usd": 1.0,      # $ per proposal (assumed)
    "par": 8, "prop_waves": 12,   # workers per eval; wall-time units one proposal round costs
}
SWITCH_MODEL = {
    "dag_parallel": "3 sibling proposals per round + merge phase; off = serial single candidate, no merge",
    "active_eval": "real posterior.Pair + sched.run on a pooled parent ledger, no null controls; off = legacy "
                   "8-task screen -> 3-trial full-val gate (0.2 SE bar) vs a fresh 90-rollout control",
    "smart_merge": "N-way block merge succeeds iff edits touch disjoint policy blocks; off = whole-file pairwise, "
                   "succeeds with prob PARAMS.p_pair_merge_ok even when disjoint",
    "cost_gating": "accept needs estimated matched cost ratio <= PARAMS.cost_tol; off = reward only",
    "failure_clustering": "edits target PARAMS.cluster_tasks tasks instead of PARAMS.single_tasks",
    "pregate": "defective proposals rejected before any rollout; off = evaluated like any other",
    "context_digest": "NO-OP in the simulator (acts on LLM proposal quality, not measurable here)",
}
KEYS = tuple(optimizer_config.DEFAULTS)
_ORDER = ("dag_parallel", "active_eval", "smart_merge", "cost_gating", "pregate", "failure_clustering",
          "context_digest")
ARMS = {"baseline_original": (), "dag_only": ("dag_parallel",), "adaptive_only": ("active_eval",),
        "dag_adaptive": ("dag_parallel", "active_eval"),
        "plus_smart_merge": ("dag_parallel", "active_eval", "smart_merge"),
        "plus_cost_gating": ("dag_parallel", "active_eval", "smart_merge", "cost_gating"),
        "full": _ORDER}
ARMS.update({f"full_no_{k}": tuple(x for x in _ORDER if x != k) for k in _ORDER})
ARMS["shipped_default"] = tuple(k for k, v in optimizer_config.DEFAULTS.items() if v)


def arm_config(name: str) -> dict[str, bool]:
    """The explicit, validated ``optimizer.ablation`` table of an arm (all seven keys set)."""
    on = ARMS[name]
    return {k: k in on for k in KEYS}


def resolve_arm(name: str) -> dict[str, bool]:
    """Resolve through the product resolver with CAPEVOLVE_* env removed (spec config only)."""
    saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("CAPEVOLVE_")
             and k[len("CAPEVOLVE_"):].lower() in KEYS}
    try:
        return optimizer_config.resolve({"optimizer": {"ablation": arm_config(name)}})
    finally:
        os.environ.update(saved)


# ---- recorded data -------------------------------------------------------------------------------

def load_fixture(path: Path = FIXTURE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def group_of(fx: dict, tag: str) -> str:
    """Capability (bytes) group of a tag: ctl_null_* belong to the capability they duplicate."""
    return next((g for g, ctl in fx["same_bytes"].items() if tag in ctl), tag)


def pools(fx: dict) -> dict[str, dict[str, list[float]]]:
    """group -> task -> every recorded reward of that capability (pooled over identical bytes)."""
    out: dict[str, dict[str, list[float]]] = {}
    for tag, rec in fx["tags"].items():
        g = out.setdefault(group_of(fx, tag), {})
        for t, rs in rec["rewards"].items():
            g.setdefault(t, []).extend(rs)
    return out


def task_ids(fx: dict) -> list[str]:
    return sorted(fx["tags"]["seed"]["rewards"], key=int)


# ---- replay ----------------------------------------------------------------------------------------

def legacy_gate_accepts(c: list[list[float]], p: list[list[float]]) -> bool:
    """The original gate on one candidate eval vs one parent eval (3 trials/task): accept when the
    val-mean difference exceeds 0.2 standard errors (eval_statistics.md section 0: ~44% false accept)."""
    def mv(xs):
        m = sum(xs) / len(xs)
        return m, sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1)
    d = var = 0.0
    for xc, xp in zip(c, p):
        (mc, vc), (mp, vp) = mv(xc), mv(xp)
        d += mc - mp; var += vc / len(xc) + vp / len(xp)
    T = len(c)
    return d / T > 0.2 * math.sqrt(var) / T


def _draw_from(pool_by_task: list[list[float]], rng: random.Random):
    """Draw without replacement from the recorded rewards of one capability, shuffled per task."""
    rem = [rng.sample(v, len(v)) for v in pool_by_task]
    return (lambda arm_unused, t: rem[t].pop()), [len(v) for v in rem]


def _run_pair(cpool, ppool, extra, rng, m, cap=sched.CAP_NEW):
    """One engine run: candidate trials ``cpool[task]``, parent's own gating eval = first 3 of ``ppool``
    (its ledger start), later parent top-ups from ``ppool[3:] + extra`` (more recorded trials of the
    same bytes). Returns (decision, rollouts, looks, legacy_gate_accepts)."""
    T = len(cpool)
    leg = legacy_gate_accepts([x[:3] for x in cpool], [x[:3] for x in ppool])
    sp = [float(sum(x[:3])) for x in ppool]
    top = [list(x[3:]) + list(e) for x, e in zip(ppool, extra)]
    dc, capc = _draw_from(cpool, rng); dp, capp = _draw_from(top, rng)
    Pr = posterior.Pair(posterior.k_vector([(s + .5) / 4 for s in sp]), sp, [3.0] * T)
    dec, used, _ = sched.run(Pr, lambda a, t: (dc if a == 0 else dp)(a, t), capc, capp, rng, cap, m=m)
    return dec, used, math.ceil(used / sched.ROUND), leg


def replay_identical_pairs(fx: dict, seed: int = 0, m: int = 150) -> dict:
    """The recorded ctl_null duplicates: every ordered pair (A, B) of full evals of byte-identical
    capabilities (A as 'candidate', B as 'parent'; the group's other evals are parent top-ups). The new
    engine must never accept one at any look; the original 0.2-SE gate on the same pairs is shown."""
    rng, tids = random.Random(seed), task_ids(fx)
    out, tot = {}, {"pairs": 0, "new_engine_accepts": 0, "looks": 0, "rollouts": 0, "legacy_gate_false_accepts": 0}
    for g, ctl in fx["same_bytes"].items():
        tags = [g] + ctl
        ev = {t: [fx["tags"][t]["rewards"][i] for i in tids] for t in tags}
        r = {"pairs": 0, "new_engine_accepts": 0, "looks": 0, "rollouts": 0, "legacy_gate_false_accepts": 0}
        for a in tags:
            for b in tags:
                if a == b:
                    continue
                extra = [sum((ev[o][i] for o in tags if o not in (a, b)), []) for i in range(len(tids))]
                dec, used, looks, leg = _run_pair(ev[a], ev[b], extra, rng, m)
                r["pairs"] += 1; r["new_engine_accepts"] += dec == "accept"; r["looks"] += looks
                r["rollouts"] += used; r["legacy_gate_false_accepts"] += leg
        out[g] = r
        for k in tot: tot[k] += r[k]
    return {"per_capability": out, "total": tot}


def replay_resplits(fx: dict, n_splits: int = 10, seed: int = 0, m: int = 150) -> dict:
    """Supplementary: random disjoint trial-level halves of one capability's pooled recorded trials
    (a harsher null than whole evals because half the pool can differ by chance)."""
    rng, P0, tids = random.Random(seed), pools(fx), task_ids(fx)
    out = {}
    for g in ("seed", "cand_1", "cand_4", "cand_7"):
        acc = leg = 0
        for _ in range(n_splits):
            cl, pl = [], []
            for t in tids:
                v = rng.sample(P0[g][t], len(P0[g][t])); h = len(v) // 2
                cl.append(v[:h]); pl.append(v[h:])
            dec, _, _, lg = _run_pair(cl, pl, [[] for _ in tids], rng, m)
            acc += dec == "accept"; leg += lg
        out[g] = {"splits": n_splits, "new_engine_accepts": acc, "legacy_gate_false_accepts": leg}
    return out


def replay_candidates(fx: dict, pregate_rejects=(), seed: int = 0, m: int = 150, cap: int = sched.CAP_NEW,
                      resamples: int = 10) -> dict:
    """Drive the posterior engine with each recorded candidate vs its recorded parent. Rollouts are
    drawn without replacement from the recorded ones of that capability (``resamples`` shuffles);
    ledger pooling means no null control is ever requested. Conditional on the ORIGINAL lineage (a
    different accept would change later parents)."""
    P0, tids = pools(fx), task_ids(fx)
    pooled = lambda g: sum(sum(v) for v in P0[g].values()) / sum(len(v) for v in P0[g].values())
    rows = {}
    for cand in sorted(fx["parent"], key=lambda c: int(c.split("_")[1])):
        if cand == "cand_9":                       # only an 8-task x 1 screen was ever run: not replayable
            continue
        par = group_of(fx, fx["parent"][cand])
        row = {"parent": par, "original": fx["original_decision"][cand],
               "pooled_delta_all_data": round(pooled(cand) - pooled(par), 4)}
        if cand in pregate_rejects:
            rows[cand] = {**row, "decisions": {"pregate_reject": resamples}, "p_accept": 0.0, "mean_rollouts": 0.0}
            continue
        dec_n, used_n = {}, []
        for k in range(resamples):
            rng = random.Random(f"{seed}|{cand}|{k}")
            cl = [rng.sample(P0[cand][t], len(P0[cand][t])) for t in tids]
            pl = [rng.sample(P0[par][t], len(P0[par][t])) for t in tids]
            dec, used, _, _ = _run_pair(cl, pl, [[] for _ in tids], rng, m, cap)
            dec_n[dec] = dec_n.get(dec, 0) + 1; used_n.append(used)
        rows[cand] = {**row, "decisions": dec_n, "p_accept": dec_n.get("accept", 0) / resamples,
                      "mean_rollouts": round(sum(used_n) / resamples, 1)}
    return rows


def replay_report(fx: dict, pregate_rejects=(), n_splits: int = 10, seed: int = 0, m: int = 150) -> dict:
    cands = replay_candidates(fx, pregate_rejects, seed, m)
    new = 90 + round(sum(r["mean_rollouts"] for r in cands.values()))      # +90 = seed baseline; 0 controls
    return {"label": LABEL, "identical_bytes_pairs": replay_identical_pairs(fx, seed, m),
            "identical_bytes_resplits": replay_resplits(fx, n_splits, seed, m),
            "candidates": cands, "new_engine_rollouts": new, "control_rollouts": 0,
            "recorded_spent": fx["spent"],
            "note": "new_engine_rollouts = 9 replayable candidates (mean over resamples) + 90 seed baseline; the "
                    "recorded 2270 also include screens, cand_9, null controls (900) and test (120)."}


# ---- simulator -------------------------------------------------------------------------------------

def _clip(x): return min(1.0, max(0.0, x))


class Sim:
    def __init__(self, cfg: dict, seed: int, p0, c0, params: dict, m: int):
        self.cfg, self.seed, self.P, self.m = cfg, seed, params, m
        self.T = len(p0); self.c0 = c0
        self.champ = {"id": "seed", "rates": list(p0), "factor": 1.0}
        self.rollouts = 0; self.usd = 0.0; self.time = 0; self.n_prop = 0
        self.cnt = {}; self.false_acc = self.regress = 0
        self.led = {"seed": ([0.0] * self.T, [0.0] * self.T)}      # active_eval: pooled per-task (s, n)
        self.cache = None                                            # legacy: parent's last per-task means
        self.traj = []
        self.rng = random.Random(f"{seed}|eval")
        self.true0 = sum(p0) / self.T

    # -- bookkeeping
    def _n(self, k, n=1): self.cnt[k] = self.cnt.get(k, 0) + n

    def _spend(self, tasks, factor, waves):
        self.rollouts += len(tasks); self.time += waves
        self.usd += sum(self.c0[t] for t in tasks) * factor

    def _true(self, rates=None): return sum(rates or self.champ["rates"]) / self.T

    def _snap(self):
        self.traj.append((self.rollouts, round(self.usd, 5), round(self._true(), 5)))

    def _bern(self, rate, shift=0.0): return float(self.rng.random() < _clip(rate + shift))

    # -- proposals
    def _propose(self):
        self.n_prop += 1; self.usd += self.P["optimizer_usd"]
        r = random.Random(f"{self.seed}|prop|{self.n_prop}"); P = self.P
        base = self.champ["rates"]
        defect = r.random() < P["p_defect"]
        lo, hi = P["cluster_tasks"] if self.cfg["failure_clustering"] else P["single_tasks"]
        weak = [i for i in range(self.T) if base[i] < 0.85] or list(range(self.T))
        tgt = r.sample(weak, min(len(weak), r.randint(lo, hi)))
        kind = r.random()
        mu, sd = ((P["shift_mu"], P["shift_sd"]) if kind < P["p_help"] else
                  (0.0, P["null_sd"]) if kind < P["p_help"] + P["p_null"] else (P["harm_mu"], P["shift_sd"]))
        new = list(base)
        if defect:
            for i in r.sample(range(self.T), int(self.T * 0.4)): new[i] = _clip(base[i] * 0.5)
        else:
            for i in tgt: new[i] = _clip(base[i] + r.gauss(mu, sd))
            for i in range(self.T):
                if i not in tgt and r.random() < P["p_side"]: new[i] = _clip(base[i] + r.gauss(0, P["side_sd"]))
        f = 1.0 + (P["cost_bloat"] if r.random() < P["p_cost_bloat"] else 0.0)
        return {"id": f"p{self.n_prop}", "rates": new, "factor": self.champ["factor"] * f, "defect": defect,
                "tasks": set(tgt), "obs": None, "decision": None,
                "blocks": set(r.sample(range(P["blocks"]), r.randint(*P["edit_blocks"])))}

    # -- evaluators; each returns decision in accept|prune|inconclusive|skipped, sets cand["obs"]
    def _cost_ok(self, cand):
        if not self.cfg["cost_gating"]:
            return True
        est = cand["factor"] / self.champ["factor"] * (1 + self.rng.gauss(0, self.P["cost_noise"]))
        return est <= self.P["cost_tol"]

    def _eval_active(self, cand, slots):
        P = self.P; cid = self.champ["id"]
        sp, np_ = (list(x) for x in self.led[cid])
        base = self.champ["rates"]
        Pr = posterior.Pair(posterior.k_vector([(s + .5) / (n + 1) for s, n in zip(sp, np_)]), sp, np_)
        calls = [0]; eta = [0.0]

        def draw(arm, t):                                    # interleaved: one common drift per round
            if calls[0] % sched.ROUND == 0: eta[0] = self.rng.gauss(0, P["tau"])
            calls[0] += 1
            r = (cand["rates"] if arm == 0 else base)[t]
            self._spend([t], cand["factor"] if arm == 0 else self.champ["factor"], 0)
            return self._bern(r, eta[0])
        before = self.rollouts
        dec, used, v = sched.run(Pr, draw, [60] * self.T, [60] * self.T, self.rng, slots=slots, m=self.m)
        self.time += math.ceil(used / sched.ROUND) * math.ceil(sched.ROUND / P["par"])
        self.led[cid] = (Pr.sp, Pr.np_)
        cand["ledger"] = (Pr.sc, Pr.nc)
        cand["obs"] = v["d_mean"]
        if dec == "accept" and not self._cost_ok(cand):
            self._n("cost_reject"); return "prune"
        return dec

    def _legacy_screen_and_gate(self, cand, remaining, control_shared=None):
        """8-task x 1 screen then 3-trial full-val gate vs a (shared) fresh control. Returns decision."""
        P, base, fac = self.P, self.champ["rates"], self.champ["factor"]
        order = sorted(range(self.T), key=lambda i: base[i])
        tasks = order[:5] + self.rng.sample(order[5:], 3)
        if remaining < 98:
            return "skipped"
        self._spend(tasks, cand["factor"], math.ceil(8 / P["par"]))
        ref = self.cache
        d = sum(self._bern(cand["rates"][t]) - ref[t] for t in tasks) / 8
        if d < 0:
            return "prune"
        eta_c = self.rng.gauss(0, P["tau"])
        c = [[self._bern(cand["rates"][t], eta_c) for _ in range(3)] for t in range(self.T)]
        self._spend([t for t in range(self.T) for _ in range(3)], cand["factor"], math.ceil(90 / P["par"]))
        if control_shared is None:
            control_shared = self._control()
        cand["cache"] = [sum(x) / 3 for x in c]
        cand["obs"] = sum(sum(x) / 3 for x in c) / self.T - sum(sum(x) / 3 for x in control_shared) / self.T
        if not legacy_gate_accepts(c, control_shared):
            return "prune"
        return "accept" if self._cost_ok(cand) else (self._n("cost_reject") or "prune")

    def _control(self):
        eta = self.rng.gauss(0, self.P["tau"])
        ctl = [[self._bern(self.champ["rates"][t], eta) for _ in range(3)] for t in range(self.T)]
        self._spend([t for t in range(self.T) for _ in range(3)], self.champ["factor"],
                    math.ceil(90 / self.P["par"]))
        self.cache = [sum(x) / 3 for x in ctl]
        return ctl

    # -- accept / merge
    def _adopt(self, cand):
        old = self.champ
        D = self._true(cand["rates"]) - self._true(old["rates"])
        if D <= 0: self.false_acc += 1
        if any(old["rates"][i] >= 0.85 and cand["rates"][i] < old["rates"][i] - 0.25 for i in range(self.T)):
            self.regress += 1
        self._n("accept")
        self.champ = {"id": cand["id"], "rates": cand["rates"], "factor": cand["factor"]}
        if self.cfg["active_eval"]:
            self.led[cand["id"]] = cand.get("ledger") or ([0.0] * self.T, [0.0] * self.T)
        else:
            self.cache = cand.get("cache") or self.cache

    def _merge(self, pool):
        """Fold the promising siblings into one candidate (additive shifts); None if nothing merged."""
        smart, base = self.cfg["smart_merge"], self.champ["rates"]
        got = [pool[0]]
        for c in pool[1:]:
            disjoint = not (set().union(*(g["blocks"] for g in got)) & c["blocks"])
            if disjoint and (smart or self.rng.random() < self.P["p_pair_merge_ok"]):
                got.append(c); self._n("merge_ok")
            else:
                self._n("merge_conflict")
        if len(got) < 2:
            return None
        rates = [_clip(base[i] + sum(g["rates"][i] - base[i] for g in got)) for i in range(self.T)]
        return {"id": "m" + "+".join(g["id"] for g in got), "rates": rates, "defect": False,
                "factor": self.champ["factor"] * math.prod(g["factor"] / self.champ["factor"] for g in got),
                "tasks": set().union(*(g["tasks"] for g in got)),
                "blocks": set().union(*(g["blocks"] for g in got)), "obs": None}

    # -- main loop
    def run(self):
        P, cfg = self.P, self.cfg
        slots = [P["budget"]]
        if cfg["active_eval"]:
            sp = [0.0] * self.T; np_ = [3.0] * self.T
            for t in range(self.T):
                sp[t] = float(sum(self._bern(self.champ["rates"][t]) for _ in range(3)))
            self.led["seed"] = (sp, np_)
        self._spend(list(range(self.T)) * 3, 1.0, math.ceil(90 / P["par"]))     # seed baseline, both modes
        if not cfg["active_eval"]:
            self.cache = [sum(self._bern(self.champ["rates"][t]) for _ in range(3)) / 3 for t in range(self.T)]
        slots[0] -= self.rollouts
        self._snap()
        n_sib = P["siblings"] if cfg["dag_parallel"] else 1
        while self.rollouts < P["budget"] and self.n_prop < 400:
            self.time += P["prop_waves"]
            remaining = P["budget"] - self.rollouts
            sibs = [self._propose() for _ in range(n_sib)]
            ctl = None
            if not cfg["active_eval"] and remaining >= 98 * n_sib + 90:
                ctl = self._control()                               # mandatory null control per round
            elif not cfg["active_eval"]:
                break
            for c in sibs:
                if c["defect"] and cfg["pregate"]:
                    c["decision"] = "pregate_reject"; self._n("pregate_reject"); continue
                if cfg["active_eval"]:
                    if slots[0] <= 0 and self.rollouts >= P["budget"]: break
                    slots[0] = P["budget"] - self.rollouts
                    c["decision"] = self._eval_active(c, slots)
                else:
                    c["decision"] = self._legacy_screen_and_gate(c, P["budget"] - self.rollouts, ctl)
                self._n(c["decision"])
            acc = sorted((c for c in sibs if c["decision"] == "accept"), key=lambda c: -(c["obs"] or 0))
            if cfg["dag_parallel"]:
                pool = [c for c in sibs if (c["obs"] or 0) > 0 and c["decision"] in ("accept", "inconclusive")]
                pool.sort(key=lambda c: -(c["obs"] or 0))
                if len(pool) >= 2 and self.rollouts < P["budget"]:
                    mc = self._merge(pool[:3])
                    if mc is not None:
                        if cfg["active_eval"]:
                            slots[0] = P["budget"] - self.rollouts
                            mc["decision"] = self._eval_active(mc, slots)
                        elif P["budget"] - self.rollouts >= 98:
                            mc["decision"] = self._legacy_screen_and_gate(mc, P["budget"] - self.rollouts)
                        else:
                            mc["decision"] = "skipped"
                        self._n("merged_" + mc["decision"])
                        if mc["decision"] == "accept":
                            acc.insert(0, mc)
            if acc:
                self._adopt(acc[0])
            self._snap()
        return self


def run_one(args) -> dict:
    name, seed, p0, c0, params, m = args
    cfg = resolve_arm(name)
    s = Sim(cfg, seed, p0, c0, params, m).run()
    return {"arm": name, "seed": seed, "final_true": s._true(), "gain": s._true() - s.true0,
            "rollouts": s.rollouts, "usd": round(s.usd, 4), "time": s.time,
            "false_accepts": s.false_acc, "regressions": s.regress, "decisions": s.cnt,
            "final_cost_factor": s.champ["factor"], "traj": s.traj}


# ---- aggregation ------------------------------------------------------------------------------------

def ci(xs: list[float], seed: int = 0, B: int = 1000) -> tuple[float, float, float]:
    """mean and 95% percentile-bootstrap interval over seeds."""
    n = len(xs); mean = sum(xs) / n
    if n < 2:
        return mean, mean, mean
    r = random.Random(seed)
    bs = sorted(sum(xs[r.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return mean, bs[int(.025 * B)], bs[int(.975 * B) - 1]


def _at(traj, x, col):
    """Champion true mean once ``x`` of column ``col`` (0 rollouts, 1 usd) is spent (step function)."""
    v = traj[0][2]
    for pt in traj:
        if pt[col] <= x: v = pt[2]
    return v


def curves(runs: list[dict], col: int, xmax: float, pts: int = 16) -> list[dict]:
    grid = [round(xmax * i / (pts - 1), 4) for i in range(pts)]
    out = []
    for x in grid:
        m, lo, hi = ci([_at(r["traj"], x, col) for r in runs])
        out.append({"x": x, "mean": round(m, 4), "lo": round(lo, 4), "hi": round(hi, 4)})
    return out


def summarize(runs: list[dict]) -> dict:
    out = {}
    for k in ("final_true", "gain", "rollouts", "usd", "time", "false_accepts", "regressions",
              "final_cost_factor"):
        m, lo, hi = ci([r[k] for r in runs]); out[k] = {"mean": round(m, 4), "lo": round(lo, 4), "hi": round(hi, 4)}
    dec: dict[str, float] = {}
    for r in runs:
        for k, v in r["decisions"].items(): dec[k] = dec.get(k, 0) + v / len(runs)
    out["decisions_per_run"] = {k: round(v, 2) for k, v in sorted(dec.items())}
    g = out["gain"]["mean"]
    out["rollouts_per_real_gain_point"] = round(out["rollouts"]["mean"] / (g * 100), 1) if g > 0 else None
    return out


def simulate(arms=None, n_seeds: int = 20, budget: int | None = None, m: int = 150, jobs: int = 1,
             fx: dict | None = None, params: dict | None = None) -> dict:
    fx = fx or load_fixture()
    tids = task_ids(fx)
    p0 = [sum(pools(fx)["seed"][t]) / len(pools(fx)["seed"][t]) for t in tids]
    c0 = [fx["tags"]["seed"]["cost"][t] for t in tids]
    P = {**PARAMS, **(params or {})}
    if budget: P["budget"] = budget
    arms = list(arms or ARMS)
    jobs_l = [(a, s, p0, c0, P, m) for a in arms for s in range(n_seeds)]
    if jobs > 1:
        import multiprocessing as mp
        with mp.Pool(jobs) as pool:
            res = pool.map(run_one, jobs_l, chunksize=4)
    else:
        res = [run_one(j) for j in jobs_l]
    by = {a: [r for r in res if r["arm"] == a] for a in arms}
    xmax_usd = max(r["usd"] for r in res)
    out = {"label": LABEL, "mode": "simulated", "n_seeds": n_seeds, "params": {**P, "m_draws": m},
           "switch_model": SWITCH_MODEL, "seed_true_mean": round(sum(p0) / len(p0), 4), "arms": {}}
    for a in arms:
        out["arms"][a] = {"config": arm_config(a), "summary": summarize(by[a]),
                          "curve_reward_vs_rollouts": curves(by[a], 0, P["budget"]),
                          "curve_reward_vs_usd": curves(by[a], 1, xmax_usd),
                          "runs": [{k: r[k] for k in r if k != "traj"} for r in by[a]]}
    return out


def markdown(res: dict) -> str:
    f = lambda d, p=3: f"{d['mean']:.{p}f} [{d['lo']:.{p}f}, {d['hi']:.{p}f}]"
    L = [f"# Ablation matrix ({res['mode']})", "", f"**{res['label']}**", "",
         f"{res['n_seeds']} seeds/arm, budget {res['params']['budget']} rollouts, seed-capability true mean "
         f"{res['seed_true_mean']}. Cells: mean [95% bootstrap CI over seeds]. `gain` = champion true mean "
         "minus the seed's (the simulator knows the truth). False accept = adopted edit with true delta <= 0; "
         "regression = adopted edit that drops a parent-stable task by > 0.25.", "",
         "| arm | gain | rollouts | $ (proxy) | time (proxy) | false accepts | regressions | cost factor |",
         "|---|---|---|---|---|---|---|---|"]
    for a, r in res["arms"].items():
        s = r["summary"]
        L.append(f"| {a} | {f(s['gain'])} | {s['rollouts']['mean']:.0f} | {f(s['usd'], 2)} | "
                 f"{s['time']['mean']:.0f} | {f(s['false_accepts'], 2)} | {f(s['regressions'], 2)} | "
                 f"{s['final_cost_factor']['mean']:.3f} |")
    L += ["", "Decisions per run (mean count):", "", "| arm | decisions |", "|---|---|"]
    L += [f"| {a} | {r['summary']['decisions_per_run']} |" for a, r in res["arms"].items()]
    L += ["", "Reward-vs-rollouts and reward-vs-$ curves are in the JSON (`curve_reward_vs_*`).",
          "", "Switch model: " + "; ".join(f"`{k}`: {v}" for k, v in res["switch_model"].items())]
    return "\n".join(L) + "\n"


# ---- real mode (dry run) ---------------------------------------------------------------------------

def real_plan(base_spec: Path, out_dir: Path, arms=None, seeds=(0, 1, 2), max_iterations: int = 6) -> list[str]:
    """Write one spec per arm = base spec + an ``optimizer.ablation`` block, return the commands.
    Nothing is executed. The base spec must not already define a top-level ``optimizer:`` key."""
    text = Path(base_spec).read_text(encoding="utf-8")
    if any(l.startswith("optimizer:") for l in text.splitlines()):
        raise SystemExit("base spec already has a top-level `optimizer:` block; merge by hand")
    (out_dir / "specs").mkdir(parents=True, exist_ok=True)
    cmds = []
    for a in arms or ARMS:
        block = "\noptimizer:\n  ablation:\n" + "".join(f"    {k}: {str(v).lower()}\n"
                                                         for k, v in arm_config(a).items())
        spec = out_dir / "specs" / f"{a}.yaml"
        spec.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
        for s in seeds:
            cmds.append(f"cap-evolve run --spec {spec} --run-ts ablate_{a}_s{s} --max-iterations {max_iterations}"
                        "  # real agent: costs money; run by a human/agent, see docs/HOLDOUT_PROTOCOL.md")
    return cmds


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ablate", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay"); r.add_argument("--splits", type=int, default=10)
    r.add_argument("--pregate-reject", action="append", default=["cand_10"],
                   help="candidates the pre-gate rejects (default cand_10, see test_replay_ablation_harness)")
    s = sub.add_parser("sim"); s.add_argument("--out", default="ablation_out")
    s.add_argument("--seeds", type=int, default=20); s.add_argument("--budget", type=int)
    s.add_argument("--arm", action="append"); s.add_argument("--jobs", type=int, default=1)
    s.add_argument("--m", type=int, default=150)
    d = sub.add_parser("real"); d.add_argument("--spec", required=True); d.add_argument("--out", default="ablation_out")
    d.add_argument("--seeds", type=int, default=3); d.add_argument("--arm", action="append")
    a = p.parse_args(argv)
    print(f"# {LABEL}", file=sys.stderr)
    if a.cmd == "replay":
        print(json.dumps(replay_report(load_fixture(), set(a.pregate_reject), a.splits), indent=1))
    elif a.cmd == "sim":
        res = simulate(a.arm, a.seeds, a.budget, a.m, a.jobs)
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        (out / "ablation_sim.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        (out / "ablation_sim.md").write_text(markdown(res), encoding="utf-8")
        print(markdown(res))
    else:
        print("\n".join(real_plan(Path(a.spec), Path(a.out), a.arm, range(a.seeds))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
