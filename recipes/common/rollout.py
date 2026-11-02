"""The ONE rollout every exp895 competitor arm uses (issue #895 §7: "replace only the agent rollout with the
common CapEvolve SpreadsheetBench rollout").

It wraps the SAME adapter the CapEvolve arm runs. That means the same agent loop, scorer, LibreOffice
recalculation, container fix and pre-rollout helper gate, on the same v2-seed surfaces. On top it adds what
every arm needs and must not re-implement:

  * k trials inside one evaluation call (a cache keyed by task id cannot collapse them);
  * the shared R counter: `BudgetStop` is raised BEFORE an evaluation that would overshoot R. Infra-errored
    rollouts are refunded and retried with a fresh trial seed, never scored 0 (issue §0.3);
  * the trial-seed convention: trial_seed = 10_000*search_seed + 100*eval_call + trial;
  * rollouts.jsonl rows in the issue's §8 schema.

Usage (inside an arm's port):

    from rollout import CommonRollout, BudgetStop
    ro = CommonRollout(run_dir, arm="gepa", search_seed=0, R=2160)
    res = ro.evaluate(candidate_dir, task_ids, k=3)   # -> EvalResult (raises BudgetStop if it would overshoot)
    res.mean, res.per_task[tid].mean, res.per_task[tid].trials, res.per_task[tid].feedback
    res.per_task[tid].worst_trace    # the lowest-scoring trial's transcript, for reflective datasets

A candidate is a DIRECTORY holding prompt.md, task_template.md and skills/ (the v2 seed layout).
Gold-safe: feedback is the scorer's argument-level message (range checked, cases passed), never gold values.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import adapter as _sb  # templates/adapters/spreadsheetbench/adapter.py, on PYTHONPATH via node_env.sh

MAX_INFRA_RETRIES = 3  # issue §9: up to 3 further attempts with a fresh seed


class BudgetStop(Exception):
    """Raised before an evaluation that would take counted rollouts past R."""


@dataclass
class TaskResult:
    task_id: str
    trials: list = field(default_factory=list)       # rewards (hard_restriction, after recalc), one per trial
    trial_seeds: list = field(default_factory=list)
    feedback: list = field(default_factory=list)     # gold-safe scorer feedback per trial
    errors: list = field(default_factory=list)       # candidate-caused errors per trial (None if clean)
    worst_trace: object = None                       # transcript of the lowest-scoring trial
    infra: list = field(default_factory=list)        # True where the trial was STILL infra-errored after all retries
                                                     # (its entry in `trials` is a placeholder 0.0, NOT a measured failure)
    traces: list = field(default_factory=list)       # transcript of EVERY trial, in trial order

    @property
    def valid(self) -> list:
        """Rewards of the trials that were actually measured (infra-missing trials excluded)."""
        return [x for x, bad in zip(self.trials, self.infra or [False] * len(self.trials)) if not bad]

    @property
    def missing(self) -> bool:
        """No trial of this task was measured: the task is missing data, not a failure (issue §0.3)."""
        return not self.valid

    @property
    def mean(self) -> float:
        """Mean over MEASURED trials only. An infra-missing trial is never counted as 0 (issue §0.3).
        A task with no measured trial returns 0.0 here; check `.missing` and drop it instead of using it."""
        v = self.valid
        return sum(v) / len(v) if v else 0.0


@dataclass
class EvalResult:
    eval_call: int
    candidate_dir: str
    per_task: dict
    counted: int
    infra_retries: int

    @property
    def missing_tasks(self) -> list:
        return [t for t, r in self.per_task.items() if r.missing]

    @property
    def mean(self) -> float:
        """Mean per-task score over tasks with at least one measured trial (missing tasks are dropped, not zeroed)."""
        ok = [r.mean for r in self.per_task.values() if not r.missing]
        return sum(ok) / len(ok) if ok else 0.0


class CommonRollout:
    def __init__(self, run_dir, *, arm: str, search_seed: int, R: int, phase: str = "search"):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.arm, self.search_seed, self.R, self.phase = arm, int(search_seed), int(R), phase
        self._adapter = _sb.Adapter()
        self._tasks = {t.id: t for t in self._adapter.tasks("train")}
        self._lock = threading.Lock()
        self._ledger = self.run_dir / "rollouts.jsonl"
        self._state = self.run_dir / "budget_state.json"
        st = json.loads(self._state.read_text()) if self._state.exists() else {"spent": 0, "eval_calls": 0}
        self.spent, self._eval_calls = st["spent"], st["eval_calls"]

    # ---- budget -------------------------------------------------------------------------------------
    def remaining(self) -> int:
        return self.R - self.spent

    def would_fit(self, n_tasks: int, k: int) -> bool:
        return self.spent + n_tasks * k <= self.R

    def _save(self):
        self._state.write_text(json.dumps({"spent": self.spent, "eval_calls": self._eval_calls, "R": self.R}))

    # ---- evaluation --------------------------------------------------------------------------------
    def evaluate(self, candidate_dir, task_ids, *, k: int = 3, candidate_id: str = "", split: str = "train") -> EvalResult:
        ids = [str(t) for t in task_ids]
        unknown = [t for t in ids if t not in self._tasks]
        if unknown:
            raise KeyError(f"not a train/val task: {unknown[:3]}")
        with self._lock:
            n = len(ids) * k
            if self.spent + n > self.R:
                raise BudgetStop(f"{self.arm}: evaluation of {len(ids)}x{k}={n} would exceed R ({self.spent}/{self.R})")
            self.spent += n                          # reserve up front; infra retries are refunded below
            call = self._eval_calls
            self._eval_calls += 1
            self._save()
        cand = Path(candidate_dir)
        per_task = {t: TaskResult(task_id=t) for t in ids}
        jobs = [(t, j) for t in ids for j in range(k)]
        infra_retries = 0
        from concurrent.futures import ThreadPoolExecutor

        def run_one(job):
            t, j = job
            for attempt in range(MAX_INFRA_RETRIES + 1):
                # Issue §5 convention widened so it stays unique (decisions.md): 10_000*seed + 100*call + trial
                # collides once an arm makes >= 100 evaluation calls (GEPA minibatches) and with retries.
                # Here: trial < 100, attempt <= 3, eval_call < 1000 (R=2160) -> unique per (seed, call, trial, attempt).
                seed = 1_000_000 * self.search_seed + 1000 * call + 100 * attempt + j
                t0 = time.time()
                r = self._adapter.run_target(self._tasks[t], cand, seed=seed)
                s = self._adapter.score(self._tasks[t], r)
                meta = r.metadata or {}
                kind = "none" if not r.error else ("candidate" if meta.get("error_kind") == "candidate" else "infra")
                m = {x["name"]: x["value"] for x in (s.metrics or [])}
                self._log({"suite": "spreadsheetbench_verified_400", "arm": self.arm, "seed": self.search_seed,
                           "phase": self.phase, "task_id": t, "split": split, "trial": j, "trial_seed": seed,
                           "candidate_id": candidate_id or cand.name, "eval_call": call, "t_start": t0, "t_end": time.time(),
                           "wall_s": round(time.time() - t0, 1), "reward": s.reward,
                           "reward_as_saved": m.get("hard_no_recalc"), "error_kind": kind,
                           "error_text": (r.error or "")[:500], "retried": attempt > 0, "counted": kind != "infra"})
                if kind != "infra":
                    return t, j, seed, s, r, kind, attempt
            return t, j, seed, s, r, "infra", attempt

        with ThreadPoolExecutor(max_workers=_sb.CONCURRENCY) as ex:
            out = list(ex.map(run_one, jobs))
        for t, j, seed, s, r, kind, attempts in out:
            infra_retries += attempts
            tr = per_task[t]
            tr.trials.append(0.0 if kind == "infra" else float(s.reward))
            tr.trial_seeds.append(seed)
            tr.feedback.append(s.feedback)
            tr.errors.append(r.error if kind == "candidate" else None)
            tr.infra.append(kind == "infra")
            tr.traces.append(r.trace)
            if kind != "infra" and (tr.worst_trace is None or s.reward <= min(tr.valid)):
                tr.worst_trace = r.trace
        stuck = sum(1 for o in out if o[5] == "infra")
        if stuck:  # still infra after all retries: refund, and say so; the arm must treat these as missing
            with self._lock:
                self.spent -= stuck
                self._save()
        return EvalResult(eval_call=call, candidate_dir=str(cand), per_task=per_task, counted=n - stuck,
                          infra_retries=infra_retries)

    def _log(self, row: dict):
        with self._lock, open(self._ledger, "a") as f:
            f.write(json.dumps(row) + "\n")
