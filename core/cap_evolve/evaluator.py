"""The P2 evaluator (policy "SH-C"): ONE scheduler shared by hill-climb rounds and the agent-optimize
conductor.

A *round* takes K candidates built from one incumbent and returns at most one champion:

  1. rung 1   kill-only, ``rung_sizes[0]`` rollouts per candidate on a seeded random subset of the
              feedback stratum F (same subset for every candidate and for the incumbent's F draws)
  2. rung 2   survivors only, up to ``rung_sizes[1]`` cumulative rollouts, ranked on pooled F draws
  3. control  once per round, if a survivor exists: the incumbent re-measured on the confirm stratum C
              (``ctrl_m`` trials per task), concurrently with the confirmations
  4. confirm  at most ``max_survivors`` survivors, ``conf_n`` FRESH rollouts each on C, none of the rung
              data reused; accept the best paired mean among those with z >= ``z_conf`` and mean >= dmin

Rungs never accept. A confirmation that does not fit the budget returns ``unconfirmed`` (the candidate
stays pending); it is never a reject and never an accept. With a single pending candidate
(``Round.sequential``) a group-sequential test on C replaces rungs + confirmation.

Information barrier. F is what the proposer may see (traces, per-task rewards). C is used only here;
every value this module returns about C is an aggregate (mean, z, n) or a verdict bit, never a task id,
a trace, or a per-task score.

The unit of work is a ``Job`` (at most ``chunk`` rollouts of one candidate on one stage). Jobs are plain
data: a caller may run them inline (``Round.run``), on a thread pool, or in a caller's shared slot
pool, in any order and across processes, because ``Round.collect`` rebuilds every statistic from the
rollouts on disk. Every job reserves its rollouts before dispatch (``RunDir.reserve_metric_calls``).

Public surface (stable; the agent-optimize conductor and the hill-climb rounds share exactly this):

    ev = P2Evaluator(adapter, run_dir, params)
    ev.feedback_ids() / ev.confirm_ids()        split accessors (C ids are for the evaluator only)
    ev.plan_round(k_wanted, fits=...)           -> RoundPlan (K shrunk until the worst case fits)
    rnd = ev.open_round(candidates, incumbent)  -> Round, persisted, resumable
    rnd.rung_jobs(1) / rnd.run_job(job) / rnd.close_rung(1)  -> {cid: RungVerdict}
    rnd.run_rung(1, map_fn=...)                 jobs + close in one call (map_fn = parallel executor)
    rnd.confirm_jobs() / rnd.close_confirm()    -> {cid: ConfirmVerdict}, plus Round.champion
    rnd.sequential(cid)                         K = 1 group-sequential on C
    ev.final_estimate(champion_dir, seed_dir)   champion vs seed on C, fresh seeds
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from . import costaware, eval_index, harness, racing
from .promotion import P2Params
from .rundir import BudgetExhausted, _atomic_write

#: Verdict statuses. ``kill``/``advance`` come from rungs, ``accept``/``reject`` from a confirmation,
#: ``unconfirmed`` = survived but the budget could not fund its confirmation (pending, not a reject),
#: ``unfunded`` = a rung could not be funded (the round ends).
STATUSES = ("kill", "advance", "accept", "reject", "unconfirmed", "unfunded", "extend")

#: Stage names a Job can carry.
STAGES = ("rung1", "rung2", "control", "confirm", "seq", "incumbent")

#: Fresh-seed ranges (``trial_offset``) per use. Disjoint by construction: a confirmation never reuses
#: a rung seed, a control never reuses a confirmation seed, and rounds step within their block.
SEED_BASE = {"incumbent": 100_000, "rung": 200_000, "control": 300_000, "confirm": 400_000,
             "seq": 500_000, "final": 600_000}
SEED_BLOCK = 10_000     # per round, within a base


@dataclass(frozen=True)
class Job:
    """A bounded unit of evaluation: <= ``chunk`` rollouts of ONE candidate on ONE stage."""
    job_id: str                 # stable: f"{round_id}:{cid}:{stage}:{index}"
    round_id: str
    cid: str                    # candidate id; the control/incumbent jobs use the incumbent's id
    stage: str                  # one of STAGES
    role: str                   # "feedback" (F) | "confirm" (C)
    tag: str                    # rollout tag the job writes under (disjoint per job)
    ids: tuple                  # task ids of this chunk (never shown to a proposer when role == "confirm")
    n_trials: int
    trial_offset: int           # fresh-seed range; confirm ranges never overlap rung ranges
    rollouts: int               # len(ids) * n_trials, the amount reserved against max_metric_calls

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RungVerdict:
    cid: str
    status: str                 # kill | advance | unfunded
    mean: float                 # paired mean vs the incumbent's pooled F draws
    z: float
    n: int                      # candidate rollouts counted so far
    reason: str = ""


@dataclass
class ConfirmVerdict:
    cid: str
    status: str                 # accept | reject | unconfirmed
    mean: float | None = None   # aggregates on C only; None when unconfirmed
    z: float | None = None
    n: int = 0
    reason: str = ""
    rel_cost: float | None = None   # candidate cost per rollout relative to the incumbent's (cost-aware gate)
    path: str = ""                  # reward | cost | cost_adjusted | ... (see ``costaware.Judgement``)

    def bit(self) -> str:
        """What the proposer is told about C: ``accept`` | ``reject`` | ``pending``. Nothing else."""
        return {"accept": "accept", "reject": "reject"}.get(self.status, "pending")

    def proposer_view(self) -> dict:
        """The only form of this verdict that may reach a proposer's context."""
        return {"candidate": self.cid, "confirmation": self.bit()}


@dataclass
class RoundPlan:
    k: int                      # candidates the round can afford (<= k_wanted)
    worst_case: int             # rollouts: rung 1 + rung 2 + control + survivors * conf_n
    funded: bool                # False: even K=1 does not fit; run no round
    direct: bool = False        # shrunk final round: one candidate, no rungs, straight to control + confirmation


def thread_map(max_workers: int) -> Callable:
    """A ``map_fn`` for ``Round.run_rung`` / ``confirm`` that runs jobs on a thread pool."""
    def _map(fn, jobs):
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
            return list(ex.map(fn, jobs))
    return _map


def interleave(*job_lists) -> list:
    """Round-robin merge, so a control and its candidates are measured in the same time window
    (drift between them cancels instead of landing on the candidate)."""
    out, lists = [], [list(x) for x in job_lists]
    while any(lists):
        for lst in lists:
            if lst:
                out.append(lst.pop(0))
    return out


def _serial_map(fn, jobs):
    return [fn(j) for j in jobs]


def _passes(draws: list) -> list:
    """Occurrence index of each draw: ``[(task, pass_idx)]``; the j-th time a task is drawn is pass j."""
    seen: dict = {}
    out = []
    for t in draws:
        out.append((t, seen.get(t, 0)))
        seen[t] = seen.get(t, 0) + 1
    return out


class P2Evaluator:
    """Owns the F/C split, the incumbent's pooled F draws, and budget reservations for P2 rounds."""

    def __init__(self, adapter, run_dir, params, *, workers: int | None = None,
                 errored_policy: str | None = None, cost: "costaware.CostParams | None" = None):
        """``params`` = ``promotion.P2Params``. Requires ``split_mode: pooled`` splits (``Splits.pooled``)
        (the partition is created on first use, see ``harness.ensure_pooled``)."""
        if not eval_index.enabled():
            raise RuntimeError("rule P2 pools incumbent draws through the evidence ledger; "
                               "CAPEVOLVE_EVAL_LEDGER=0 disables it")
        self.adapter, self.run_dir, self.params = adapter, run_dir, params
        self.workers = workers
        self._inc_trials = None          # set by ``plan_round`` when the incumbent top-up had to be degraded
        self.splits = harness.ensure_pooled(run_dir)
        if not self.splits.feedback or not self.splits.confirm:
            raise ValueError("rule P2 needs a non-empty feedback and confirm stratum "
                             f"(got {len(self.splits.feedback)} / {len(self.splits.confirm)})")
        self.errored_policy = errored_policy or self._default_policy()
        self.cost = cost if cost is not None else self._default_cost()
        self._lock = threading.Lock()
        self._round_dir().mkdir(parents=True, exist_ok=True)

    def _default_policy(self) -> str:
        from .specfile import spec_for_run
        raw = os.environ.get(harness.ERRORED_POLICY_ENV) or (spec_for_run(self.run_dir) or {}).get(
            "errored_trial_policy")
        if raw:
            return harness.resolve_errored_policy(raw, self.run_dir)
        return "fail" if getattr(self.adapter, "supports_error_kind", False) else "drop"

    def _default_cost(self) -> "costaware.CostParams":
        """Cost-aware acceptance from the run's spec (``cost_lambda`` ... , see ``costaware``); off by default."""
        from .specfile import spec_for_run
        return costaware.CostParams.from_spec(spec_for_run(self.run_dir) or {})

    # -- split accessors ------------------------------------------------------------------------
    def feedback_ids(self) -> list:
        """Task ids of F: what the proposer and the rungs may use."""
        return list(self.splits.feedback)

    def confirm_ids(self) -> list:
        """Task ids of C. For the evaluator only: never write them where a proposer can read."""
        return list(self.splits.confirm)

    @property
    def proposer_split(self) -> str:
        """The split name to hand ``OptimizerContext.inject`` / trajectory writers: ``"feedback"``."""
        return "feedback"

    # -- budget -----------------------------------------------------------------------------------
    @contextmanager
    def reserve(self, n: int, label: str):
        """Reserve ``n`` rollouts for the ``with`` body; refund what the body did not spend.
        Raises ``BudgetExhausted`` on entry when it does not fit (nothing is dispatched)."""
        token = self.run_dir.reserve_metric_calls(n, label=label)
        try:
            yield token
        finally:
            self.run_dir.release_metric_calls(token)

    def _incumbent_shortfall(self, inc_dir: Path, trials: int | None = None) -> dict:
        h = eval_index.cap_hash(inc_dir)
        want = trials or getattr(self, "_inc_trials", None) or self.params.incumbent_trials
        return eval_index.missing(self.run_dir, h, self.splits.feedback, want, split="feedback")

    def plan_round(self, k_wanted: int, incumbent_dir: Path | None = None, *,
                   allow_direct: bool = False) -> RoundPlan:
        """Shrink K until the worst-case cost fits the remaining ``max_metric_calls``.

        ``incumbent_dir`` (optional) adds the cost of topping the incumbent's F draws up to
        ``incumbent_trials`` per task. ``allow_direct`` (hill-climb): when not even K = 1 with rungs fits, the
        last round SHRINKS instead of ending the search with budget unspent: one candidate, no rungs, straight
        to the control + confirmation on C (the rungs are kill-only filters; the confirmation is the test).
        That top-up only sharpens the rung ranking, so when no K >= 1 fits
        with the full top-up the plan degrades it (down to one draw per task) before it gives up: after
        a promotion the new incumbent has almost no F draws, and the full top-up used to end the search
        with up to 40% of the budget unspent (campaign erratum 29). The chosen level is remembered for
        ``Round.incumbent_jobs``."""
        p = self.params
        cap = self.run_dir.budget.max_metric_calls
        k0 = max(1, min(int(k_wanted), p.k_for_budget(cap)))
        left = self.run_dir.remaining_metric_calls()
        n_c = len(self.splits.confirm)
        prep = 0
        for want in range(p.incumbent_trials, 0, -1):
            prep = sum(self._incumbent_shortfall(incumbent_dir, want).values()) if incumbent_dir else 0
            k = k0
            while k >= 1:
                cost = p.worst_case_cost(k, n_c) + prep
                if left is None or cost <= left:
                    self._inc_trials = want
                    return RoundPlan(k=k, worst_case=cost, funded=True)
                k -= 1
            if not incumbent_dir:
                break
        direct_cost = self.params.ctrl_m * n_c + self.params.conf_n_for(n_c)
        if allow_direct and (left is None or direct_cost <= left):
            return RoundPlan(k=1, worst_case=direct_cost, funded=True, direct=True)
        return RoundPlan(k=0, worst_case=p.worst_case_cost(1, n_c) + prep, funded=False)

    # -- rounds -----------------------------------------------------------------------------------
    def _round_dir(self) -> Path:
        """Round state: job dicts carry C task ids, so it lives in the sealed dir (outside every proposer-readable tree)."""
        return self.run_dir.private_dir / "p2"

    def _private(self, kind: str, **fields) -> None:
        """Append C-derived numbers (means, z, n) to ``private/p2_confirm.jsonl``; events get the bit only."""
        path = self.run_dir.private_dir / "p2_confirm.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in fields.items()}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": kind, "ts": time.time(), **clean}) + "\n")

    def open_round(self, candidates: Mapping[str, Path], incumbent: tuple, *, direct: bool = False) -> "Round":
        """``candidates = {cid: workdir}``, ``incumbent = (cid, dir)``. Persists the round. ``direct`` = a shrunk
        final round: the candidates skip the rungs and go straight to the confirmation."""
        with self._lock:
            no = len(list(self._round_dir().glob("r*.json")))
            round_id = f"r{no:03d}"
            state = {"round_id": round_id, "no": no, "incumbent": [str(incumbent[0]), str(incumbent[1])],
                     "candidates": {str(c): str(d) for c, d in candidates.items()},
                     "live": {"1": list(map(str, candidates)), "2": []}, "stage": "open",
                     "jobs": {}, "rungs": {}, "confirms": {}, "champion": None, "opened": time.time()}
            if direct:
                state.update(direct=True, stage="rung2_closed")
                state["live"]["confirm"] = list(map(str, candidates))
            _atomic_write(self._round_dir() / f"{round_id}.json", json.dumps(state, indent=1))
        self.run_dir.log_event("p2_round_open", round=round_id, k=len(candidates),
                               incumbent=str(incumbent[0]), n_feedback=len(self.splits.feedback),
                               n_confirm=len(self.splits.confirm))
        return Round(self, state)

    def resume_round(self, round_id: str) -> "Round":
        return Round(self, json.loads((self._round_dir() / f"{round_id}.json").read_text(encoding="utf-8")))

    def final_estimate(self, champion_dir: Path, seed_dir: Path, *, n_trials: int = 4) -> dict:
        """Fresh-trial estimate of champion minus seed on C: ``{mean, se, n, scope}``.

        Selection touched C only through accept/reject bits, so the winner's curse of the selection data
        is gone; but the estimate is CONDITIONAL ON THE C TASKS (``scope``): ``se`` is rollout noise
        plus the spread of the per-task deltas, and it is not an unbiased estimate for new tasks (the
        |C| tasks were chosen by the partition, and the search stopped on what the bits said about
        them). The sealed test split is the estimate for unseen tasks."""
        need = 2 * int(n_trials) * len(self.splits.confirm)
        if not self.run_dir.can_afford(need):       # both arms fit, or neither runs
            raise BudgetExhausted(f"final estimate needs {need} rollouts, "
                                  f"{self.run_dir.remaining_metric_calls()} remain")
        res = {}
        base = SEED_BASE["final"]
        for name, d in (("champion", champion_dir), ("seed", seed_dir)):
            res[name] = harness.evaluate_candidate(
                self.adapter, Path(d), run_dir=self.run_dir, split="confirm", ids=self.splits.confirm,
                n_trials=n_trials, tag=f"final__{name}", trial_offset=base, fixed_seeds=True,
                errored_policy=self.errored_policy, workers=self.workers, budget_reserve=True)
        c = {pt["task_id"]: pt.get("trial_rewards") or [] for pt in res["champion"].per_task}
        s = {pt["task_id"]: pt.get("trial_rewards") or [] for pt in res["seed"].per_task}
        r = racing.confirm_with_control(c, s, z_conf=0.0, dmin=-1.0, n_planned=len(self.splits.confirm))
        out = {"mean": r["mean"], "se": r["se"], "z": r["z"], "n": r["n"], "coverage": r["coverage"],
               "scope": "fresh trials, conditional on the C tasks",
               "n_trials": n_trials, "champion_reward": res["champion"].reward,
               "seed_reward": res["seed"].reward}
        self._private("final_estimate", **out)
        self.run_dir.log_event("p2_final_estimate", n=out["n"])
        return out


    def validate_chain(self, chain, seed_dir: Path, *, n_trials: int = 3, z_min: float = 0.0) -> dict:
        """End-of-search validation for ``hc2_cheap_accept``: ``chain`` = ``[(cid, dir)]`` accepted in order,
        latest last. The seed is measured on C once; the latest accepted candidate is measured against it
        and kept when its paired delta is > 0 with z >= ``z_min``, otherwise the previous one is tried, down
        to the seed. Each arm is ``n_trials`` fresh draws per C task and is paid for (or skipped) as a whole.

        Returns ``{"chosen": cid or "seed", "tested": [{cid, mean, z, n}], "skipped": reason or None}``."""
        C = self.splits.confirm
        arm = int(n_trials) * len(C)
        tested, skipped = [], None
        if not self.run_dir.can_afford(2 * arm):
            return {"chosen": chain[-1][0] if chain else "seed", "tested": [], "skipped": "budget"}
        base = SEED_BASE["final"]

        def measure(name, d):
            res = harness.evaluate_candidate(
                self.adapter, Path(d), run_dir=self.run_dir, split="confirm", ids=C, n_trials=n_trials,
                tag=f"final__{name}", trial_offset=base, fixed_seeds=True, errored_policy=self.errored_policy,
                workers=self.workers, budget_reserve=True)
            return {pt["task_id"]: pt.get("trial_rewards") or [] for pt in res.per_task}
        seed = measure("seed", seed_dir)
        chosen = "seed"
        for cid, d in reversed(list(chain)):
            if tested and not self.run_dir.can_afford(arm):
                skipped = "budget"
                chosen = cid          # an earlier prefix cannot be measured: keep the one that was last accepted
                break
            r = racing.confirm_with_control(measure(cid, d), seed, z_conf=0.0, dmin=-1.0, n_planned=len(C))
            tested.append({"cid": cid, "mean": r["mean"], "z": r["z"], "n": r["n"]})
            if r["mean"] > 0 and r["z"] >= z_min:
                chosen = cid
                break
        self._private("validate_chain", chosen=chosen, tested=tested)
        self.run_dir.log_event("p2_validate_chain", chosen=chosen, tested=[t["cid"] for t in tested], skipped=skipped)
        return {"chosen": chosen, "tested": tested, "skipped": skipped}


class Round:
    """State of one round; persisted under the run dir so a scheduler can crash and resume."""

    def __init__(self, ev: P2Evaluator, state: dict):
        self.ev, self.state = ev, state
        self.round_id = state["round_id"]
        self._lock = threading.Lock()

    # ---- plumbing --------------------------------------------------------------------------------
    @property
    def champion(self) -> str | None:
        """Best accepted confirmation; None until ``close_confirm`` (or when nothing was accepted)."""
        return self.state.get("champion")

    @property
    def candidates(self) -> list:
        return list(self.state["candidates"])

    def _path(self) -> Path:
        return self.ev._round_dir() / f"{self.round_id}.json"

    def _save(self) -> None:
        with self._lock:
            _atomic_write(self._path(), json.dumps(self.state, indent=1))

    def _dir_of(self, cid: str) -> Path:
        if cid == self.state["incumbent"][0]:
            return Path(self.state["incumbent"][1])
        return Path(self.state["candidates"][cid])

    def _seed_off(self, kind: str, extra: int = 0) -> int:
        return SEED_BASE[kind] + self.state["no"] * SEED_BLOCK + extra

    def _draw_key(self, role: str) -> str:
        return f"{self.ev.splits.pool_seed}:{self.state['no']}:{role}"

    def _existing_jobs(self, cid: str, stage: str, tag_prefix: str) -> list:
        """Jobs already created for (cid, stage, tag prefix): a restarted caller gets the same jobs back."""
        mark = f"__{tag_prefix}"
        return [Job(**{**j, "ids": tuple(j["ids"])}) for j in self.state["jobs"].values()
                if j["cid"] == cid and j["stage"] == stage and mark in j["tag"]]

    def _make_jobs(self, cid: str, stage: str, role: str, draws: list, passes: list, kind: str,
                   tag_prefix: str, seed_shift: int = 0) -> list:
        """Chunk ``draws`` of one candidate into jobs (grouped by pass so a job never repeats a task).
        Idempotent per (cid, stage, tag_prefix): called again after a restart it returns the jobs it made before.

        ``passes`` = ``[(task, pass_idx)]`` parallel to ``draws``; the pass index is part of the seed
        (``trial_offset = SEED_BASE[kind] + round block + seed_shift + pass``)."""
        p = self.ev.params
        done = self._existing_jobs(cid, stage, tag_prefix)
        if done:
            return done
        by_pass: dict = {}
        for t, k in passes:
            by_pass.setdefault(k, []).append(t)
        idx = sum(1 for j in self.state["jobs"].values() if j["cid"] == cid and j["stage"] == stage)
        jobs = []
        for k in sorted(by_pass):
            tasks = by_pass[k]
            for lo in range(0, len(tasks), p.chunk):
                ids = tuple(tasks[lo:lo + p.chunk])
                job = Job(job_id=f"{self.round_id}:{cid}:{stage}:{idx}", round_id=self.round_id, cid=cid,
                          stage=stage, role=role, tag=f"{self.round_id}__{cid}__{tag_prefix}_{idx}",
                          ids=ids, n_trials=1, trial_offset=self._seed_off(kind, seed_shift + k),
                          rollouts=len(ids))
                jobs.append(job)
                self.state["jobs"][job.job_id] = job.to_dict()
                idx += 1
        self._save()
        return jobs

    def _tags(self, cid: str, stage_prefix: str) -> list:
        return [j["tag"] for j in self.state["jobs"].values()
                if j["cid"] == cid and j["stage"].startswith(stage_prefix)]

    def _marker(self, job: Job) -> Path:
        return self.ev._round_dir() / "done" / f"{job.job_id.replace(':', '_')}.ok"

    # ---- jobs ------------------------------------------------------------------------------------
    def run_job(self, job: Job):
        """Execute one job: reserve -> ``evaluate_candidate`` -> convert reservation. Idempotent
        (a finished job is skipped, so a restarted caller re-runs nothing). Raises
        ``BudgetExhausted`` before dispatching a rollout when the job does not fit."""
        mk = self._marker(job)
        if mk.exists():
            return None
        mk.parent.mkdir(parents=True, exist_ok=True)
        res = harness.evaluate_candidate(
            self.ev.adapter, self._dir_of(job.cid), run_dir=self.ev.run_dir, split=job.role,
            ids=list(job.ids), n_trials=job.n_trials, tag=job.tag, trial_offset=job.trial_offset,
            fixed_seeds=True, errored_policy=self.ev.errored_policy, workers=self.ev.workers,
            budget_reserve=True)
        mk.write_text(str(time.time()), encoding="utf-8")
        return res

    def _run_jobs(self, jobs: list, map_fn) -> bool:
        """Run ``jobs`` through ``map_fn``; True when every one completed, False if one was unfunded."""
        unfunded = []

        def _one(job):
            try:
                self.run_job(job)
            except BudgetExhausted as e:
                unfunded.append(str(e))
        (map_fn or _serial_map)(_one, jobs)
        if unfunded:
            self.ev.run_dir.log_event("p2_unfunded", round=self.round_id, jobs=len(unfunded),
                                      first=unfunded[0][:200])
        return not unfunded

    # ---- incumbent -------------------------------------------------------------------------------
    def incumbent_jobs(self) -> list:
        """Top-up jobs bringing the incumbent's F draws to ``incumbent_trials`` per task (pooled over
        every earlier draw of the same capability hash). Empty when it is already measured."""
        inc_cid, inc_dir = self.state["incumbent"]
        done = self._existing_jobs(inc_cid, "incumbent", "inc_p")
        if done:
            return done
        need = self.ev._incumbent_shortfall(Path(inc_dir))
        jobs, idx = [], 0
        for k in range(max(need.values(), default=0)):
            ids = [t for t, n in need.items() if n > k]
            for lo in range(0, len(ids), self.ev.params.chunk):
                chunk = tuple(ids[lo:lo + self.ev.params.chunk])
                job = Job(job_id=f"{self.round_id}:{inc_cid}:incumbent:{idx}", round_id=self.round_id,
                          cid=inc_cid, stage="incumbent", role="feedback",
                          tag=f"{self.round_id}__{inc_cid}__inc_p{k}_{idx}", ids=chunk, n_trials=1,
                          trial_offset=self._seed_off("incumbent", k), rollouts=len(chunk))
                jobs.append(job)
                self.state["jobs"][job.job_id] = job.to_dict()
                idx += 1
        self._save()
        return jobs

    def _inc_rates(self) -> dict:
        h = eval_index.cap_hash(Path(self.state["incumbent"][1]))
        return eval_index.counts(self.ev.run_dir, h, "feedback")

    # ---- cost-aware acceptance (opt-in, see ``costaware``) -----------------------------------------
    def _rel_cost(self, cid: str, stage_prefix: str, split: str, ref_tags=None) -> float | None:
        """Candidate cost per rollout relative to the incumbent's, over the tasks both were measured on.
        ``ref_tags`` = the incumbent's control tags (confirmation); None = every ledger row of its hash (rungs)."""
        cp = self.ev.cost
        if not cp.enabled:
            return None
        tags = set(self._tags(cid, stage_prefix))
        rows = [r for r in eval_index.rows(self.ev.run_dir) if r.get("split") == split and r.get("env_fp", "") == eval_index.env_fp()]
        cand = [r for r in rows if r.get("tag") in tags]
        if ref_tags is None:
            h = eval_index.cap_hash(Path(self.state["incumbent"][1]))
            ref = [r for r in rows if r.get("cap_hash") == h]
        else:
            ref = [r for r in rows if r.get("tag") in set(ref_tags)]
        shared = {r["task"] for r in cand} & {r["task"] for r in ref}
        return costaware.relative_cost([r for r in cand if r["task"] in shared],
                                       [r for r in ref if r["task"] in shared], cp)

    # ---- rungs -----------------------------------------------------------------------------------
    def _f_draws(self) -> tuple:
        r1, r2 = self.ev.params.rung_sizes
        draws = racing.draw_order(self.ev.splits.feedback, min(r2, len(self.ev.splits.feedback)), self._draw_key("F"))
        return draws, _passes(draws), r1, r2

    def rung_jobs(self, rung: int) -> list:
        """Chunked ``Job``s for rung 1 or 2 over the live candidates (rung 2: survivors only)."""
        if rung not in (1, 2):
            raise ValueError("rung must be 1 or 2")
        draws, passes, r1, r2 = self._f_draws()
        lo, hi = (0, r1) if rung == 1 else (r1, r2)
        # rung sizes count TASKS; each task is evaluated ``trials`` times (pass k = trial k), so
        # ``num_trials`` lowers the per-task noise of the kill decision instead of being ignored
        t = self.ev.params.trials
        rd = [x for _ in range(t) for x in draws[lo:hi]]
        rp = [(x, k) for k in range(t) for x in draws[lo:hi]]
        live = self.state["live"][str(rung)]
        jobs = []
        for cid in live:
            jobs += self._make_jobs(cid, f"rung{rung}", "feedback", rd, rp, "rung", f"rung{rung}")
        return jobs

    def _rung_stat(self, cid: str) -> dict:
        tags = self._tags(cid, "rung")
        rates = self._inc_rates()
        if not tags:
            return {"mean": 0.0, "z": 0.0, "n": 0}
        sr = harness.split_result_from_rollouts(self.ev.run_dir, tags, "feedback",
                                                errored_policy=self.ev.errored_policy)
        n, tot, counts, rows, vsum, vn = 0, 0.0, [], [], 0.0, 0
        m_acc = []
        for pt in sr.per_task:
            t = str(pt.get("task_id"))
            ys = [float(y) for y in (pt.get("trial_rewards") or [])]
            if not ys or t not in rates or rates[t][1] <= 0:
                continue
            s, mt = rates[t]
            phat = s / mt
            tot += sum(y - phat for y in ys)
            n += len(ys)
            counts.append(len(ys))
            m_acc.append(mt)
            rows.append(ys)
            vsum += phat * (1 - phat) * (mt / (mt - 1) if mt > 1 else 1.0)
            vn += 1
        if n == 0:
            return {"mean": 0.0, "z": 0.0, "n": 0}
        v_c = racing.within_task_variance({str(i): ys for i, ys in enumerate(rows)})
        v = 0.5 * (v_c + vsum / vn)
        m = max(1, int(round(sum(m_acc) / len(m_acc))))
        se = racing.pooled_se(n, counts, v, m)
        mean = tot / n
        return {"mean": mean, "z": (mean / se if se > 0 else 0.0), "n": n, "se": se}

    def close_rung(self, rung: int) -> dict:
        """``{cid: RungVerdict}``; kill-only halving on the pooled F draws. Never accepts."""
        p = self.ev.params
        live = self.state["live"][str(rung)]
        stats = {cid: self._rung_stat(cid) for cid in live}
        k = len(self.state["candidates"])
        keep_n = max(1, k // 2) if rung == 1 else min(p.max_survivors, max(1, k // 4))
        # cost path (``cost_accept``): a clearly cheaper candidate whose reward is not clearly worse stays alive
        # for the confirmation even with a non-positive screen mean (it cannot win a screen on reward)
        cp = self.ev.cost
        rels = {cid: self._rel_cost(cid, "rung", "feedback") for cid in stats} if cp.accept else {}
        cheap = {cid for cid, r in rels.items() if r is not None and r <= -cp.min_saving
                 and stats[cid]["mean"] - cp.noninf_z * stats[cid].get("se", 0.0) >= -cp.margin}
        ranked = {cid: ({**st, "mean": max(st["mean"], 1e-9)} if cid in cheap else st) for cid, st in stats.items()}
        keep = set(racing.halve(ranked, keep_n))
        out = {}
        for cid, st in stats.items():
            status = "advance" if cid in keep else "kill"
            why = ("kept: top %d by paired z with mean > 0" % keep_n if status == "advance" and cid not in cheap
                   else ("kept: cheaper at non-inferior reward (cost path)" if status == "advance"
                         else ("mean <= 0" if st["mean"] <= 0 else "outside the top %d by paired z" % keep_n)))
            out[cid] = RungVerdict(cid, status, st["mean"], st["z"], st["n"], why)
        self.state["rungs"][str(rung)] = {c: asdict(v) for c, v in out.items()}
        if rung == 1:
            self.state["live"]["2"] = sorted(keep, key=lambda c: -stats[c]["z"])
        else:
            self.state["live"]["confirm"] = sorted(keep, key=lambda c: -stats[c]["z"])
        self.state["stage"] = f"rung{rung}_closed"
        self._save()
        self.ev.run_dir.log_event("p2_rung", round=self.round_id, rung=rung,
                                  kept=sorted(keep), killed=sorted(set(stats) - keep),
                                  stats={c: {"mean": round(s["mean"], 4), "z": round(s["z"], 3), "n": s["n"]}
                                         for c, s in stats.items()})
        return out

    def run_rung(self, rung: int, map_fn: Callable | None = None) -> dict:
        """``rung_jobs`` + ``run_job`` over ``map_fn(fn, jobs)`` (a parallel executor) + ``close_rung``.

        Rung 1 first tops up the incumbent's F draws. If any job does not fit the budget the rung is
        ``unfunded``: every live candidate gets that status and the round ends."""
        jobs = (self.incumbent_jobs() if rung == 1 else []) + self.rung_jobs(rung)
        if not self._run_jobs(jobs, map_fn):
            live = self.state["live"][str(rung)]
            out = {c: RungVerdict(c, "unfunded", 0.0, 0.0, 0, "budget") for c in live}
            self.state["stage"] = "unfunded"
            self.state["live"]["2"] = []
            self.state["live"]["confirm"] = []
            self._save()
            return out
        return self.close_rung(rung)

    # ---- confirmation ----------------------------------------------------------------------------
    def _n_conf_draws(self) -> int:
        return self.ev.params.conf_n_for(len(self.ev.splits.confirm))

    def _cost_conf(self) -> int:
        return self._n_conf_draws()

    def _prior_control(self) -> tuple:
        """``(tags, per_task_draws)``: control rollouts of this round's incumbent from EARLIER rounds (``p2_reuse_control``).
        Only complete controls count (every C task has at least one draw); the reusable depth is the minimum
        draws per task. A promoted incumbent has a new id, so nothing is reused across a champion change."""
        if not self.ev.params.reuse_control:
            return [], 0
        inc_cid = self.state["incumbent"][0]
        tags = []
        for f in sorted(self.ev._round_dir().glob("r*.json")):
            if f.stem == self.round_id:
                continue
            try:
                st = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if st.get("incumbent", [None])[0] != inc_cid:
                continue
            for j in st.get("jobs", {}).values():
                if j["cid"] == inc_cid and j["stage"] == "control" and \
                        (self.ev._round_dir() / "done" / f"{j['job_id'].replace(':', '_')}.ok").exists():
                    tags.append(j["tag"])
        if not tags:
            return [], 0
        sr = harness.split_result_from_rollouts(self.ev.run_dir, tags, "confirm", errored_policy=self.ev.errored_policy)
        have = {str(pt["task_id"]): len(pt.get("trial_rewards") or []) for pt in sr.per_task}
        depth = min((have.get(str(t), 0) for t in self.ev.splits.confirm), default=0)
        return (tags, depth) if depth > 0 else ([], 0)

    def _ctrl_passes(self) -> int:
        """Control passes over C this round still has to run."""
        return max(0, self.ev.params.ctrl_m - self._prior_control()[1])

    def _cost_ctrl(self) -> int:
        return self._ctrl_passes() * len(self.ev.splits.confirm)

    def confirm_plan(self) -> tuple:
        """``(funded, unfunded)`` survivor lists: as many survivors (best rung z first) as fit the
        budget together with the control. Survivors that do not fit are ``unconfirmed`` (pending)."""
        surv = list(self.state["live"].get("confirm") or [])
        left = self.ev.run_dir.remaining_metric_calls()
        if left is None:
            return surv, []
        funded = []
        cost = self._cost_ctrl()
        for cid in surv:
            if cost + self._cost_conf() <= left:
                funded.append(cid)
                cost += self._cost_conf()
        return funded, [c for c in surv if c not in funded]

    def confirm_jobs(self) -> list:
        """Control jobs (incumbent on C, ``ctrl_m`` trials) and fresh confirmation jobs per funded survivor."""
        p = self.ev.params
        if self.state.get("extending"):
            return self._extension_jobs()
        funded, unfunded = self.confirm_plan()
        self.state["confirm_funded"], self.state["confirm_unfunded"] = funded, unfunded
        if not funded:
            self._save()
            return []
        C = self.ev.splits.confirm
        inc_cid = self.state["incumbent"][0]
        reuse_tags, _ = self._prior_control()
        self.state["control_reuse"] = reuse_tags
        ctrl_draws = [t for _ in range(self._ctrl_passes()) for t in C]
        ctrl_jobs = (self._make_jobs(inc_cid, "control", "confirm", ctrl_draws, _passes(ctrl_draws),
                                     "control", "ctrl") if ctrl_draws else [])
        cand_jobs = []
        for i, cid in enumerate(funded):
            draws = racing.draw_order(C, p.conf_n_for(len(C)), self._draw_key(f"C:{cid}"))
            # each survivor gets its own seed block, so confirmations are independent of each other
            cand_jobs.append(self._make_jobs(cid, "confirm", "confirm", draws, _passes(draws), "confirm",
                                             "conf", seed_shift=100 * i))
        self._save()
        return interleave(ctrl_jobs, *cand_jobs)

    def _extension_jobs(self) -> list:
        """The one extra block of fresh C draws for the near-miss candidates (``p2_extend_z``). The control is
        not re-run: the extension is judged against the same control draws. Idempotent per candidate."""
        p = self.ev.params
        C = self.ev.splits.confirm
        left = self.ev.run_dir.remaining_metric_calls()
        jobs, cost = [], 0
        for i, cid in enumerate(self.state["extending"]):
            if left is not None and cost + self._cost_conf() > left:
                self.state.setdefault("extend_unfunded", []).append(cid)
                continue
            cost += self._cost_conf()
            draws = racing.draw_order(C, p.conf_n_for(len(C)), self._draw_key(f"C2:{cid}"))
            jobs += self._make_jobs(cid, "confirm", "confirm", draws, _passes(draws), "confirm", "cx",
                                    seed_shift=1000 + 100 * i)
        self._save()
        return jobs

    def _trials_on_c(self, cid: str, stage: str) -> dict:
        tags = self._tags(cid, stage) + (list(self.state.get("control_reuse") or []) if stage == "control" else [])
        if not tags:
            return {}
        sr = harness.split_result_from_rollouts(self.ev.run_dir, tags, "confirm",
                                                errored_policy=self.ev.errored_policy)
        return {str(pt["task_id"]): [float(y) for y in (pt.get("trial_rewards") or [])]
                for pt in sr.per_task if pt.get("trial_rewards")}

    def close_confirm(self) -> dict:
        """``{cid: ConfirmVerdict}``; sets ``champion``. A confirmation that did not fit is
        ``unconfirmed``, never a reject."""
        p = self.ev.params
        inc_cid = self.state["incumbent"][0]
        self.state["extending"] = None            # the extension block (if any) has been run by now
        ctrl = self._trials_on_c(inc_cid, "control")
        out: dict = {}
        n_c = len(self.ev.splits.confirm)
        accepted, near_miss = [], []
        for cid in self.state.get("confirm_funded", []):
            cand = self._trials_on_c(cid, "confirm")
            second = cid in self.state.get("extended", [])      # pooled second look: a stricter bar
            r = racing.confirm_with_control(cand, ctrl, z_conf=p.z_conf + (p.extend_margin if second else 0.0),
                                            dmin=p.dmin, min_coverage=p.min_coverage, n_planned=n_c)
            reason = (f"mean {r['mean']:+.4f}, z {r['z']:.2f} on {r['n']} paired C tasks "
                      f"(need mean >= {p.dmin:g}, z >= {p.z_conf + (p.extend_margin if second else 0.0):g})")
            ok, rel, path = r["pass"], None, "reward"
            if p.extend_z and not r["pass"] and cid not in self.state.get("extended", []) \
                    and r["mean"] > 0 and r["z"] >= p.extend_z:
                near_miss.append(cid)
                continue
            if self.ev.cost.enabled and r["n"] >= 2 and r["coverage"] >= p.min_coverage:
                rel = self._rel_cost(cid, "confirm", "confirm", ref_tags=self._tags(inc_cid, "control")
                                    + list(self.state.get("control_reuse") or []))
                j = costaware.judge(self.ev.cost, passed=r["pass"], mean=r["mean"], se=r["se"], z=r["z"],
                                    dmin=p.dmin, rel=rel)
                ok, path = j.accept, j.path
                if j.reason:
                    reason += "; " + j.reason
                if rel is not None:
                    reason += f"; relative cost {rel:+.1%}"
            v = ConfirmVerdict(cid, "accept" if ok else "reject", r["mean"], r["z"], r["n"], reason,
                               rel_cost=rel, path=path)
            out[cid] = v
            if ok:
                accepted.append(v)
        if near_miss and self.ev.run_dir.can_afford(self._cost_conf() * len(near_miss)):
            # Nothing is decided yet: the caller runs ``confirm_jobs`` (now the extension block) and calls
            # ``close_confirm`` again, which recomputes every verdict from the pooled draws.
            self.state["extending"] = near_miss
            self.state["extended"] = list(self.state.get("extended", [])) + near_miss
            self.state["stage"] = "confirm_extend"
            self._save()
            self.ev.run_dir.log_event("p2_confirm_extend", round=self.round_id, n=len(near_miss))
            return {c: ConfirmVerdict(c, "extend", reason="near-miss: one more block of fresh C draws")
                    for c in near_miss}
        for cid in near_miss:                    # the extension does not fit the budget: a plain reject of the near-miss
            out[cid] = ConfirmVerdict(cid, "reject", reason="near-miss; the extension did not fit the budget")
        for cid in self.state.get("confirm_unfunded", []):
            out[cid] = ConfirmVerdict(cid, "unconfirmed", reason="the budget could not fund its confirmation")
        for cid, rv in (self.state["rungs"].get("2") or self.state["rungs"].get("1") or {}).items():
            if cid not in out and rv["status"] == "unfunded":
                out[cid] = ConfirmVerdict(cid, "unconfirmed", reason="rung unfunded")
        lam = self.ev.cost.lam
        champ = (max(accepted, key=lambda v: v.mean - lam * (v.rel_cost or 0.0)).cid) if accepted else None
        self.state["confirms"] = {c: asdict(v) for c, v in out.items()}
        self.state["champion"], self.state["stage"] = champ, "closed"
        self._save()
        self.ev._private("confirm", round=self.round_id, champion=champ,
                         verdicts={c: {"status": v.status, "mean": v.mean, "z": v.z, "n": v.n}
                                   for c, v in out.items()})
        self.ev.run_dir.log_event("p2_confirm", round=self.round_id, champion=champ,
                                  bits={c: v.bit() for c, v in out.items()})
        return out

    def confirm(self, map_fn: Callable | None = None) -> dict:
        """``confirm_jobs`` + run + ``close_confirm`` in one call (plus the near-miss extension, once)."""
        jobs = self.confirm_jobs()
        if jobs and not self._run_jobs(jobs, map_fn):
            funded = self.state.get("confirm_funded", [])
            self.state["confirm_unfunded"] = list(self.state.get("confirm_unfunded", [])) + funded
            self.state["confirm_funded"] = []
        out = self.close_confirm()
        if any(v.status == "extend" for v in out.values()):
            self._run_jobs(self.confirm_jobs(), map_fn)     # a block that does not fit just leaves fewer draws
            out = self.close_confirm()
        return out

    # ---- K = 1 -----------------------------------------------------------------------------------
    def sequential(self, cid: str, map_fn: Callable | None = None) -> ConfirmVerdict:
        """K = 1: group-sequential test on C with looks ``gs_looks`` and a concurrent control.

        The incumbent is re-measured on C first (``ctrl_m`` trials per task); the candidate then draws
        passes over C and is judged at each look with ``racing.gs_decide``. An early kill/accept saves the
        remaining rollouts; running out of budget returns ``unconfirmed``."""
        p = self.ev.params
        C = self.ev.splits.confirm
        inc_cid = self.state["incumbent"][0]
        n_max = p.gs_looks[-1]
        left = self.ev.run_dir.remaining_metric_calls()
        if left is not None and p.ctrl_m * len(C) + p.gs_looks[0] > left:     # sequential() never reuses control draws
            return self._seq_done(cid, ConfirmVerdict(cid, "unconfirmed", reason="budget"))
        ctrl_draws = [t for _ in range(p.ctrl_m) for t in C]
        ctrl_jobs = self._make_jobs(inc_cid, "control", "confirm", ctrl_draws, _passes(ctrl_draws),
                                    "control", "ctrl")
        draws = racing.draw_order(C, n_max, self._draw_key(f"S:{cid}"))
        passes = _passes(draws)
        prev, cost_note = 0, ""
        for i, n in enumerate(p.gs_looks):
            jobs = self._make_jobs(cid, "seq", "confirm", draws[prev:n], passes[prev:n], "seq", f"seq{i}")
            if i == 0:      # the control is measured in the same window as the first look
                if not self._run_jobs(interleave(ctrl_jobs, jobs), map_fn):
                    return self._seq_done(cid, ConfirmVerdict(cid, "unconfirmed", n=prev, reason="budget"))
                ctrl = self._trials_on_c(inc_cid, "control")
                phat = {t: sum(ys) / len(ys) for t, ys in ctrl.items() if ys}
            elif not self._run_jobs(jobs, map_fn):
                return self._seq_done(cid, ConfirmVerdict(cid, "unconfirmed", n=prev, reason="budget"))
            prev = n
            cand = self._trials_on_c(cid, "seq")
            mean, z, nn = self._seq_stat(cand, phat, len(ctrl_draws) // max(1, len(C)))
            act = racing.gs_decide(i, nn, z, looks=p.gs_looks, c=p.gs_c, futility=p.gs_futility)
            if act == "accept" and mean < p.dmin:
                act = "continue" if i < len(p.gs_looks) - 1 else "kill"
            if act == "accept" and self.ev.cost.enabled:      # reward win: the cost term can only veto a marginal one
                j = costaware.judge(self.ev.cost, passed=True, mean=mean, se=math.inf, z=z, dmin=p.dmin,
                                    rel=self._rel_cost(cid, "seq", "confirm",
                                                       ref_tags=self._tags(inc_cid, "control")))
                if not j.accept:
                    act = "kill"
                    cost_note = f"; {j.reason}"
            if act == "kill" and self.ev.cost.accept and i == len(p.gs_looks) - 1 and nn >= 2:
                # the last look found no reward win; a clearly cheaper, non-inferior candidate may still land (cost path)
                se = abs(mean / z) if z else 0.0
                j = costaware.judge(self.ev.cost, passed=False, mean=mean, se=se, z=z, dmin=p.dmin,
                                    rel=self._rel_cost(cid, "seq", "confirm", ref_tags=self._tags(inc_cid, "control")))
                if j.accept:
                    act, cost_note = "accept", f"; {j.reason}"
            if act != "continue":
                status = "accept" if act == "accept" else "reject"
                return self._seq_done(cid, ConfirmVerdict(
                    cid, status, mean, z, nn, f"look {i + 1}/{len(p.gs_looks)}: mean {mean:+.4f}, z {z:.2f} "
                    f"on {nn} rollouts{cost_note}"))
        return self._seq_done(cid, ConfirmVerdict(cid, "reject", n=prev, reason="no decision"))

    def _seq_stat(self, cand: dict, phat: dict, m: int) -> tuple:
        n, tot, counts, rows, task_d = 0, 0.0, [], [], []
        for t, ys in cand.items():
            if t not in phat:
                continue
            tot += sum(y - phat[t] for y in ys)
            n += len(ys)
            counts.append(len(ys))
            rows.append(ys)
            task_d.append(sum(ys) / len(ys) - phat[t])
        if n == 0:
            return 0.0, 0.0, 0
        v = racing.within_task_variance({str(i): ys for i, ys in enumerate(rows)})
        se = max(racing.pooled_se(n, counts, v, max(1, m)), racing.heterogeneity_se(task_d))
        mean = tot / n
        return mean, (mean / se if se > 0 else 0.0), n

    def _seq_done(self, cid: str, v: ConfirmVerdict) -> ConfirmVerdict:
        self.state["confirms"][cid] = asdict(v)
        self.state["champion"] = cid if v.status == "accept" else None
        self.state["stage"] = "closed"
        self._save()
        self.ev._private("sequential", round=self.round_id, candidate=cid, status=v.status, n=v.n,
                         mean=v.mean, z=v.z, reason=v.reason)
        self.ev.run_dir.log_event("p2_sequential", round=self.round_id, candidate=cid, bit=v.bit())
        return v
