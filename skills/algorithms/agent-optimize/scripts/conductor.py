"""conductor -- AO-2: a code-driven graph conductor for agent-optimize (opt-in: ``ao_engine: conductor``).

The old engine hands the loop to a conversational agent that has to poll, sleep and wait on
evaluations; it burned most of its tokens waiting, stopped on prose it read as caps, and never
reached a promotion verdict. Here CODE runs the loop and the LLM does only bounded one-shot jobs:

    python conductor.py run --run-dir R --project P         # one conductor; exit 0 only when DONE
    python conductor.py supervise --run-dir R --project P   # relaunch `run` until exit 0 (crash safe)

One tick is a pure function of files (``conductor.json``, ``graph.jsonl``, the evidence ledger):

  1 reap     finished jobs -> ledger rows, graph nodes, token/rollout books
  2 promote  screen (rule P stage 1) on full coverage; confirm (stage 2) on FRESH trials of the
             candidate AND the incumbent; accept moves the champion
  3 merge    complementary tips -> one merge node (merge_n/funcmerge, or an LLM merge-resolve job);
             champion change -> rebase merge of every alive tip parented on the old champion
  4 rungs    cells for each node's next evaluation stage, chunked (<= ``chunk`` rollouts) and run in
             a shared slot pool so several candidates evaluate in parallel
  5 propose  start one-shot proposer jobs while slots, token budget and rollout budget allow
  6 stop     structured: rollouts, tokens, wall deadline, stop_at_reward, plateau with a floor;
             then drain, finalize (idempotent) and exit 0

Prose is never parsed into a cap. AO refuses multi-objective specs (single scalar objective; cost
is reported only). With K=1, no rungs and no merge the conductor makes the same promotion
decisions as hill-climb (tested): it calls the same ``promotion.screen`` / ``promotion.confirm``.

The conductor talks to the world only through a ``Backend`` (see conductor_backend.py for the real
one); tests drive it with a fake. State: ``conductor.json`` (jobs, reservations, node stages),
``graph.jsonl`` (the candidate DAG, one record per transition).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

import policy
from cap_evolve import conductor_state as cs
from cap_evolve import gatecfg, promotion

FRESH_BASE = 1000          # first fresh-trial index (hill-climb: ``1000 + iterations * n_conf``)
FILL_BASE, FILL_N = 3000, 2   # focus rule: a new champion's fresh reference fill (trial indices, trials per task)
TERMINAL = ("champion", "rejected", "pruned", "superseded", "refused")
PRE_CONFIRM = ("proposed", "rung", "full", "screened", "stale", "racing")
EXIT_REFUSED = 2


class Refused(Exception):
    """The spec asks for something AO-2 will not do (e.g. multi-objective). Exit 2: never relaunched."""


# ---- configuration (structured keys only) -----------------------------------------------------

@dataclasses.dataclass
class Cfg:
    slots: int = 4                      # shared evaluation slots (spec gateway_max_concurrency)
    k_prop: int = 1                     # concurrent proposer jobs / branches
    chunk: int = policy.CHUNK
    rungs: tuple = ()                   # subset sizes of the kill-only rungs; () = off (full-val screen)
    screen_n: int = 1                   # trials per cell in the screen
    max_confirm: int = 1                # simultaneous confirmations
    target_alive: int | None = None     # nodes in flight before confirm; default K (K=1 => serial = hill-climb)
    merge: bool = False
    merge_bar: float = policy.COMPLEMENTARY   # complementarity a pair of tips needs to be merged
    focus: bool = False                 # ao_focus: judge on the champion's failing tasks + canaries, promote directly
    focus_n: int = 1                    # first look: trials per focus cell
    focus_max: int = 3                  # last look; undecided after it = pruned (no resolvable gain)
    focus_canary: int = 6               # sample of the champion's passing tasks (regression stratum)
    focus_accept_min: int = 2           # trials per focus cell before an ACCEPT (one trial is enough to kill)
    job_token_cap: int = 150_000
    chunk_timeout: float = 3 * 3600.0
    eval_retries: int = 3
    propose_retries: int = 2
    tick_s: float = 5.0
    seed: int = 0
    ref_pooled: bool = False            # screen reference = all of the champion's draws (pooled splits)
    params: promotion.PromotionParams = dataclasses.field(default_factory=promotion.PromotionParams)
    p2: object | None = None            # promotion.P2Params when promotion_rule is P2 (round mode)
    cost_eps: float | None = None       # second objective (a ``cost`` objective in the spec): cost per success
    finalize: bool = True               # spec ``finalize: false``: record the champion, score nothing
    pipeline: int = 1                   # P2: proposals may run this many rounds ahead of the evaluating round
    caps: policy.Caps = dataclasses.field(default_factory=policy.Caps)

    @property
    def alive_cap(self) -> int:
        return self.target_alive or self.k_prop * (self.pipeline if self.p2 else 1)

    @classmethod
    def from_spec(cls, spec: dict, budget: dict | None = None) -> "Cfg":
        spec, budget = spec or {}, budget or {}
        cost_eps = refuse_multi_objective(spec)
        params = promotion.PromotionParams.from_spec({"promotion_rule": "P", **spec}) or promotion.PromotionParams()
        deadline = spec.get("deadline_utc")
        if deadline:
            from datetime import datetime, timezone
            d = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
            deadline = (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
        elif spec.get("max_wallclock_seconds"):
            deadline = time.time() + float(spec["max_wallclock_seconds"])

        def num(*keys, cast=int, default=None):
            for k in keys:
                for src in (spec, budget):
                    if src.get(k) not in (None, "", 0, False):
                        return cast(src[k])
            return default
        job_cap = num("ao_job_token_cap", default=cls.job_token_cap)
        caps = policy.Caps(
            max_metric_calls=num("max_metric_calls"), max_tokens=num("max_optimizer_tokens", "ao_max_tokens"),
            deadline=deadline, stop_at_reward=num("stop_at_reward", cast=float),
            max_candidates=num("max_candidates"), plateau_n=num("ao_plateau_n"),
            plateau_floor=num("ao_plateau_floor", cast=float, default=0.4),
            max_idle=num("ao_max_idle_proposals", default=policy.MAX_IDLE),
            chunk=num("ao_chunk", default=policy.CHUNK), proposer_cap=job_cap,
            finalize_rollouts=num("ao_finalize_reserve", default=0),
            finalize_tokens=num("ao_finalize_tokens", default=0))
        k = num("ao_k_prop", default=1)
        p2 = promotion.P2Params.from_spec(spec) if hasattr(promotion, "P2Params") else None
        if p2 and cost_eps is not None:
            raise Refused("a `cost` objective is supported with promotion_rule P only, not P2")
        return cls(slots=num("ao_slots", "gateway_max_concurrency", default=cls.slots), k_prop=k,
                   chunk=caps.chunk, rungs=tuple(int(x) for x in (spec.get("ao_rungs") or ())),
                   screen_n=num("ao_screen_n", default=1), max_confirm=num("ao_max_confirm", default=1),
                   target_alive=num("ao_target_alive"), merge=bool(spec.get("ao_merge")),
                   job_token_cap=job_cap, chunk_timeout=num("ao_chunk_timeout", cast=float, default=cls.chunk_timeout),
                   seed=num("ao_seed", default=0), tick_s=num("ao_tick_s", cast=float, default=cls.tick_s), ref_pooled=spec.get("split_mode") == "pooled", finalize=gatecfg.finalize_enabled(spec),
                   params=params, caps=caps, p2=p2, pipeline=num("ao_pipeline", default=2 if p2 and k > 1 else 1),
                   cost_eps=cost_eps, merge_bar=num("ao_merge_bar", cast=float, default=policy.COMPLEMENTARY),
                   focus=bool(spec.get("ao_focus")), focus_n=num("ao_focus_n", default=1),
                   focus_max=num("ao_focus_max", default=3), focus_canary=num("ao_focus_canary", default=6),
                   focus_accept_min=num("ao_focus_accept_min", default=2))


def refuse_multi_objective(spec: dict) -> float | None:
    """AO optimizes reward, plus at most ONE second objective: ``cost`` (minimize), read as cost per
    success (see ``policy.mo_verdict``). Returns its tolerance ``eps`` (objective ``eps``, else spec
    ``ao_cost_eps``, default 0.10), None when there is no cost objective. Any other objective declared
    with a role other than ``display`` (gate / pareto / epsilon-constraint): refuse, loudly, before spending."""
    objs = [o for o in (spec.get("objectives") or []) if isinstance(o, dict)]
    cost = [o for o in objs if o.get("role") != "display" and o.get("name") == "cost"
            and o.get("direction", "minimize") in ("minimize", "min")]
    active = [o for o in objs if o.get("role") != "display" and o.get("name") not in (None, "reward")
              and o not in cost]
    if len(active) > 0 or spec.get("pareto") or spec.get("objective_mode") in ("pareto", "multi"):
        names = [o.get("name") for o in active] or ["pareto"]
        raise Refused("agent-optimize (AO-2) optimizes a single scalar objective, plus optionally `cost` "
                      f"(cost per success); this spec declares additional gating objectives {names}. Mark "
                      "them `role: display` (reported only), or use hill-climb for other multi-objective search.")
    if cost:
        return float(cost[0].get("eps", spec.get("ao_cost_eps", 0.10)))
    return None


# ---- backend contract -------------------------------------------------------------------------

class Backend:
    """What the conductor needs from the world. All reads are cheap; ``start`` never blocks."""

    # data
    def screen_ids(self) -> list[str]: raise NotImplementedError
    def confirm_ids(self) -> list[str]: return self.screen_ids()
    def cap_hash(self, tag: str) -> str | None: raise NotImplementedError
    def missing(self, tag: str, ids, window: tuple[int, int]) -> dict[str, int]: raise NotImplementedError
    def rewards(self, tag: str, ids, window: tuple[int, int] | None) -> dict[str, list[float]]: raise NotImplementedError
    def costs(self, tag: str, ids, window: tuple[int, int] | None) -> dict[str, list]: return {}   # aligned with rewards
    def spent_rollouts(self) -> int: raise NotImplementedError
    def spent_tokens(self) -> int: return 0
    def best_reward(self, tag: str) -> float | None: return None
    # jobs
    def start(self, job: dict) -> dict: raise NotImplementedError
    def poll(self, job: dict) -> dict | None: raise NotImplementedError
    def alive(self, job: dict) -> bool: raise NotImplementedError
    def kill(self, job: dict) -> bool | None:
        """Stop the job. False = it cannot be stopped yet (a P2 worker thread mid-rollout): the conductor keeps its
        slot and reservation until ``poll`` reports it finished. None/True = stopped."""
        raise NotImplementedError
    def running_tokens(self, job: dict) -> int: return 0        # optimizer tokens a RUNNING one-shot job has used so far
    # graph
    def register(self, job: dict, result: dict) -> dict: raise NotImplementedError
    def node_event(self, tag: str, status: str, **kw) -> None: raise NotImplementedError
    def commit_accept(self, tag: str, evidence: dict) -> None: raise NotImplementedError
    def restore_champion(self, tag: str) -> None: pass             # a reverted promotion: the run's best is ``tag`` again
    def commit_reject(self, tag: str, reason: str, evidence: dict) -> None: raise NotImplementedError
    def discard(self, tag: str) -> None: pass
    def merge_build(self, a: str, b: str, tag: str, kind: str) -> dict: raise NotImplementedError
    def wins(self, tags: list[str], base: str) -> dict[str, set]: return {}
    def related(self, a: str, b: str) -> bool: return False
    def recover(self) -> None: pass
    def finalize(self, champion: str) -> dict: raise NotImplementedError
    def finalized(self) -> bool: raise NotImplementedError
    def skip_finalize(self, champion: str) -> dict:
        """``finalize: false``: record the champion, score nothing."""
        self.log("finalize_skipped", reason="spec", champion=champion)
        return {"champion": champion, "finalized": False, "reason": "spec"}
    def log(self, event: str, **kw) -> None: pass
    def initial_champion(self) -> str: return "seed"
    def remaining_rollouts(self) -> int | None: return None      # P2: what the run dir has left after reservations
    def reserved_rollouts(self) -> int: return 0
    # ---- P2 rounds (promotion_rule: P2). Jobs are plain dicts; run_job is idempotent (done markers).
    def p2_plan(self, k_wanted: int, incumbent: str) -> tuple[int, bool]: raise NotImplementedError
    def p2_open(self, tags: list[str], incumbent: str) -> str: raise NotImplementedError
    def p2_stage_jobs(self, rid: str, stage: str) -> list[dict]: raise NotImplementedError
    def p2_job_done(self, rid: str, job: dict) -> bool: raise NotImplementedError
    def p2_close(self, rid: str, stage: str, unfunded: bool) -> dict: raise NotImplementedError


def window_key(w) -> tuple[int, int]:
    return int(w[0]), int(w[1])


# ---- the conductor ----------------------------------------------------------------------------

class Conductor:
    def __init__(self, root, backend: Backend, cfg: Cfg, *, clock=time.time, sleep=time.sleep):
        self.root, self.b, self.cfg = Path(root), backend, cfg
        self.store = cs.Store(self.root)
        self.clock, self.sleep = clock, sleep
        self.st = self.store.load()
        self.tick_no = 0
        self.recovered = False
        self.ids = None

    # ---- bookkeeping --------------------------------------------------------------------
    def save(self) -> None:
        self.store.save(self.st)

    @property
    def champion(self) -> str:
        return self.st["champion"]

    def node(self, tag) -> dict:
        return self.st["nodes"][tag]

    def screen_ids(self) -> list[str]:
        if self.ids is None:
            self.ids = sorted(map(str, self.b.screen_ids()))
        return self.ids

    def committed(self) -> int:
        return int(self.b.spent_rollouts())

    def fits(self, need: int) -> bool:
        return cs.rollouts_fit(self.st, self.committed() + self.b.reserved_rollouts(), need,
                               self.cfg.caps.max_metric_calls, self.cfg.caps.finalize_rollouts)

    def tokens_used(self) -> int:
        return int(self.st.get("tokens_base", 0)) + int(self.st.get("tokens_committed", 0))

    def ref_window(self, tag) -> tuple[int, int] | None:
        """The trials of ``tag`` the screen READS as its reference: the seed's selection-era trials,
        or - after a promotion under rule P - the incumbent's own FRESH confirmation trials (the
        screen that picked it is biased upward). None = every draw (pooled splits)."""
        if self.cfg.ref_pooled:
            return None
        w = self.st["nodes"].get(tag, {}).get("ref_window")
        return window_key(w) if w else (0, FRESH_BASE)

    def ref_want(self, tag) -> tuple[int, int]:
        """The trial block the reference must HAVE: its fresh block, else the first ``screen_n`` trials."""
        w = None if self.cfg.ref_pooled else self.st["nodes"].get(tag, {}).get("ref_window")
        return window_key(w) if w else (0, self.cfg.screen_n)

    def _is_base(self, tag) -> bool:
        """The run's starting incumbent: a node with no edit, never a candidate to evaluate or merge."""
        return self.st["nodes"].get(tag, {}).get("edit_kind") == "seed"

    def n_decided(self) -> int:
        return sum(1 for n in self.st["nodes"].values() if n["status"] in TERMINAL and n.get("decided"))

    def new_tag(self) -> str:
        return f"cand_{self.st['n_proposals'] + 1}"

    # ---- main loop ----------------------------------------------------------------------
    def run(self, max_ticks: int | None = None) -> int:
        """Tick until DONE (returns 0). ``max_ticks`` is a test seam: returns 1 when it runs out."""
        n = 0
        while True:
            if self.tick():
                return 0
            n += 1
            if max_ticks is not None and n >= max_ticks:
                return 1
            self.sleep(self.cfg.tick_s)

    def tick(self) -> bool:
        if not self.recovered:
            self.recover()
        self.tick_no += 1
        if "tokens_base" not in self.st:
            self.st["tokens_base"] = int(self.b.spent_tokens())
        if "champion_seeded" not in self.st:
            base = self.b.initial_champion()
            self.st["champion"] = base
            self.st["nodes"].setdefault(base, {"tag": base, "status": "champion", "parents": [],
                                               "edit_kind": "seed", "hash": self.b.cap_hash(base),
                                               "decided": False, "rung": 0, "epoch": 0})
            self.st["champion_seeded"] = True
        self.reap()
        self.promote()
        reason = self.stop_check()
        if reason and not self.st.get("stopped"):
            self.st["stopped"] = self.st["stop_reason"] = reason
            self.b.log("conductor_stop", reason=reason)
        if not self.st.get("stopped"):
            self.merge()
            self.propose()
        elif self.drain():
            self.finish()
            self.save()
            return True
        self.launch_evals()
        self.save()
        return False

    # ---- recovery -----------------------------------------------------------------------
    def recover(self) -> None:
        """At start: jobs recorded as live whose process is gone become ``lost`` (their reservation
        is refunded; the ledger decides which cells are still missing, so nothing is double-run).
        Open ``eval_start`` events are closed by the backend. A lost proposer retries its tag."""
        self.recovered = True
        for j in list(self.st["jobs"].values()):
            if j["state"] in cs.LIVE and not self.b.alive(j):
                res = self.b.poll(j)
                if res is not None:                  # finished while we were down: reap it normally
                    continue
                j["state"] = "lost"
                j["reserved_rollouts"] = j["reserved_tokens"] = 0
                self.b.log("job_lost", job=j["id"], job_kind=j["kind"], tag=j.get("tag"))
                if j["kind"] in ("propose", "merge"):
                    self._lost_proposal(j)
        self.b.recover()
        self.save()

    def _lost_proposal(self, j) -> None:
        j["retry_of_lost"] = True
        att = self.st.setdefault("attempts", {})
        att[j["tag"]] = att.get(j["tag"], 0) + 1

    # ---- 1. reap ------------------------------------------------------------------------
    def reap(self) -> None:
        for j in sorted(self.st["jobs"].values(), key=lambda j: j["id"]):
            if j["state"] != "running":
                continue
            res = self.b.poll(j)
            if res is not None and j.get("cancelling"):      # a cancelled worker finally ended: now free its slot
                self._lose(j, "job_cancelled")
                continue
            if res is None:
                if j.get("cancelling"):
                    continue
                if not self.b.alive(j):                 # gone without leaving an exit record: free the slot now
                    self._lose(j, "job_vanished")
                elif self.clock() - float(j.get("started") or self.clock()) > self.cfg.chunk_timeout:
                    if self._stop(j):
                        self._lose(j, "job_timeout")
                elif j["kind"] in ("propose", "merge", "diagnose") and \
                        self.b.running_tokens(j) > self.cfg.job_token_cap:
                    used = int(self.b.running_tokens(j))     # the per-job cap is enforced here, not trusted to the CLI
                    self.b.kill(j)                           # a proposer is a process: kill() always stops it
                    self.b.log("job_token_cap", job=j["id"], job_kind=j["kind"], tokens=used, cap=self.cfg.job_token_cap)
                    res = {"ok": False, "error": "token_cap", "tokens": used}
                if res is None:
                    continue
            j["result"] = {k: v for k, v in res.items() if k != "stdout"}
            j["state"] = "done" if res.get("ok", True) else "failed"
            j["reserved_rollouts"] = 0
            tok = int(res.get("tokens") or 0)                  # non-cache-read: input + output + cache creation
            if j["kind"] in ("propose", "merge", "diagnose"):
                self.st["tokens_committed"] = int(self.st.get("tokens_committed", 0)) + tok
                self.st["cache_read_committed"] = int(self.st.get("cache_read_committed", 0)) + int(res.get("cache_read_tokens") or 0)
                j["reserved_tokens"] = 0
            getattr(self, f"_reaped_{j['kind']}", lambda *_: None)(j, res)

    def _stop(self, j) -> bool:
        """Ask the backend to stop ``j``. False (and ``cancelling``) when it cannot stop yet; reap frees it later."""
        if self.b.kill(j) is False:
            j["cancelling"] = True
            return False
        return True

    def _lose(self, j, why) -> None:
        """A running job that is gone or hung: refund its reservations; the ledger decides what is missing."""
        j["state"] = "lost"
        j["reserved_rollouts"] = j["reserved_tokens"] = 0
        self.b.log(why, job=j["id"], job_kind=j["kind"], tag=j.get("tag"))
        if j["kind"] in ("propose", "merge"):
            self._lost_proposal(j)

    def _missing(self, tag, ids, window) -> dict:
        """``b.missing`` minus cells dropped after ``eval_retries`` runs that never landed (a rollout that
        always errors): missing data, which ``paired_deltas`` already drops, never a wait forever."""
        drop = self.st.get("dropped_cells", {})
        lo, hi = window_key(window)
        return {t: k for t, k in self.b.missing(tag, ids, window).items() if f"{tag}|{t}|{lo}|{hi}" not in drop}

    def _reaped_eval(self, j, res) -> None:
        if j.get("p2seq") or j.get("p2"):
            return self._p2_reaped(j, res)
        if res.get("ok", True):
            lo, hi = window_key(j["window"])
            tries, drop = self.st.setdefault("cell_tries", {}), self.st.setdefault("dropped_cells", {})
            for t in self.b.missing(j["tag"], j["ids"], j["window"]):
                key = f"{j['tag']}|{t}|{lo}|{hi}"
                tries[key] = tries.get(key, 0) + 1
                if tries[key] >= self.cfg.eval_retries and key not in drop:
                    drop[key] = tries[key]
                    self.b.log("cell_dropped", tag=j["tag"], task=t, window=[lo, hi], tries=tries[key])
        n = self.st["nodes"].get(j.get("owner"))
        if not res.get("ok", True) and n is not None:
            n["eval_failures"] = int(n.get("eval_failures", 0)) + 1
            if n["eval_failures"] >= self.cfg.eval_retries and n["status"] in PRE_CONFIRM + ("confirming",):
                self._finish_node(j["owner"], "pruned", "eval_failed", {"stage": "eval_failed"})

    def _reaped_propose(self, j, res) -> None:
        tag = j["tag"]
        out = self.b.register(j, res) if res.get("ok", True) else {"ok": False, "refused": "job_failed"}
        if not out.get("ok"):
            att = self.st.setdefault("attempts", {})
            att[tag] = att.get(tag, 0) + 1
            detail = str(out.get("detail") or res.get("tail") or "")[:300] if not res.get("ok", True) or out.get("detail") else ""
            self.b.log("proposal_failed", tag=tag, why=out.get("refused"), attempt=att[tag], detail=detail)
            self.st.setdefault("refusals", {})[tag] = {"why": out.get("refused"), "detail": detail, "attempt": att[tag]}
            self.st["idle_proposals"] = int(self.st.get("idle_proposals", 0)) + 1      # refused / duplicate / failed
            if out.get("refused") == "duplicate":
                self.st["dup_refused"] = int(self.st.get("dup_refused", 0)) + 1
            if att[tag] > self.cfg.propose_retries or out.get("refused") == "duplicate":
                self._give_up(tag, j)
            else:
                j["retry"] = True            # same tag, relaunched with a stricter prompt next propose()
            return
        self._add_node(tag, out, j)

    _reaped_merge = _reaped_propose

    def _give_up(self, tag, j) -> None:
        self.st["proposals_since_improve"] += 1
        self.b.discard(tag)
        self.st.get("attempts", {}).pop(tag, None)
        parent = self.st["nodes"].get(j.get("parent"))
        if parent is not None:
            parent["stuck"] = int(parent.get("stuck", 0)) + 1

    def _add_node(self, tag, out, j) -> None:
        h = out.get("hash") or self.b.cap_hash(tag)
        for t, n in self.st["nodes"].items():                        # content-hash dedup guard
            if t != tag and n.get("hash") == h and n["status"] != "refused":
                self.b.discard(tag)
                self.st["dup_refused"] = int(self.st.get("dup_refused", 0)) + 1
                self.b.log("duplicate_refused", tag=tag, same_as=t)
                self.st["idle_proposals"] = int(self.st.get("idle_proposals", 0)) + 1
                self.st["proposals_since_improve"] += 1
                return
        self.st["idle_proposals"] = 0                                # a new evaluable candidate ends the idle streak
        parents = out.get("parents") or [j.get("parent") or self.champion]
        self.st["nodes"][tag] = {
            "tag": tag, "parents": parents, "parent": parents[0], "edit_kind": j.get("edit_kind", "edit"),
            "hash": h, "status": "proposed", "rung": 0, "epoch": self.st["epoch"], "branch_id": self._branch(tag, parents),
            "hypothesis_id": out.get("hypothesis_id"), "created_by": j["id"], "stuck": 0, "decided": False,
            "eval_failures": 0}
        self.st["proposals_since_improve"] += 1
        self.b.node_event(tag, "proposed", parents=parents, edit_kind=j.get("edit_kind", "edit"),
                          branch_id=self.node(tag)["branch_id"], stage="checked", created_by=j["id"])

    def _branch(self, tag, parents) -> str:
        """Lineage root: a child of a non-champion tip stays on that tip's branch; a child of the
        champion (or seed) starts one; a merge takes the lower branch id of its parents."""
        ids = []
        for p in parents:
            n = self.st["nodes"].get(p)
            if n and n["status"] not in ("champion", "superseded") and n.get("branch_id"):
                ids.append(n["branch_id"])
        return min(ids) if ids else f"b_{tag}"

    # ---- 2. promote ---------------------------------------------------------------------
    def _finish_node(self, tag, status, why, evidence) -> None:
        n = self.node(tag)
        n.update(status=status, why=why, decided=True)
        if n.get("reserved"):
            n["reserved"] = 0
        gstat = {"champion": "accepted", "rejected": "rejected", "pruned": "rejected"}.get(status, status)
        self.b.node_event(tag, gstat, **{"stage": status, "why": why, **evidence})
        if status in ("rejected", "pruned"):
            self.b.commit_reject(tag, why, evidence)

    def promote(self) -> None:
        if self.cfg.p2:
            self._p2_step()
            return
        if self.cfg.focus:
            self._check_fill()
        for tag in sorted(self.st["nodes"]):
            n = self.st["nodes"][tag]
            if n["status"] in ("proposed", "rung", "full", "stale") and not self._is_base(tag):
                (self._advance_focus if self.cfg.focus else self._advance)(tag, n)
        for tag in sorted(self.st["nodes"]):
            n = self.st["nodes"][tag]
            if n["status"] == "confirming":
                self._decide_confirm(tag, n)
        self._start_confirms()
        if self.st["epoch"] != self.st.get("rebased_epoch", 0):
            self._rebase_all()

    def _cps(self, tag, ids, w, ref, ref_w) -> dict:
        """Paired cost per success of ``tag`` (window ``w``) vs ``ref`` (window ``ref_w``) on ``ids``."""
        return policy.cost_per_success(self.b.rewards(tag, ids, w), self.b.costs(tag, ids, w),
                                       self.b.rewards(ref, ids, ref_w), self.b.costs(ref, ids, ref_w))

    def _ref(self) -> dict:
        w = self.ref_window(self.champion)
        return self.b.rewards(self.champion, self.screen_ids(), w)

    def _cand_rewards(self, tag, ids) -> dict:
        return self.b.rewards(tag, ids, (0, FRESH_BASE))

    def _stage_ids(self, n) -> list[str]:
        ids = self.screen_ids()
        r = n.get("rung", 0)
        if self.cfg.rungs and r < len(self.cfg.rungs):
            return policy.rung_ids(ids, self.cfg.rungs[r], self.cfg.seed)
        return ids

    def _advance(self, tag, n) -> None:
        """Move a node through its rungs and the full screen as its cells arrive."""
        for _ in range(len(self.cfg.rungs) + 2):
            ids = self._stage_ids(n)
            full = ids == self.screen_ids()
            if self._missing(tag, ids, (0, self.cfg.screen_n)) or self._missing(self.champion, ids, self.ref_want(self.champion)):
                n["status"] = "rung" if not full else "full"
                return
            deltas = policy.paired_deltas(self._cand_rewards(tag, ids), self._ref(), ids)
            if not full:
                if policy.rung_kill(deltas):
                    m, se, k = policy.mean_se(deltas, policy.SD_FLOOR)
                    self._finish_node(tag, "pruned", "rung_kill", {"stage": f"rung{n['rung']}", "mean_delta": round(m, 6)})
                    return
                n["rung"] += 1
                n["status"] = "rung"
                n["p_beat"] = policy.p_beat(deltas)
                continue
            s = promotion.screen(deltas, self.cfg.params.k_se)
            n["screen"] = {k: (None if isinstance(v, float) and v != v else v) for k, v in s.items() if k != "z"}
            n["screen_n"] = s["n"]
            n["p_beat"] = policy.p_beat(deltas)
            route = "reward"
            if self.cfg.cost_eps is not None:
                cps = self._cps(tag, ids, (0, FRESH_BASE), self.champion, self.ref_window(self.champion))
                s["pass"], route = policy.mo_verdict(s["pass"], s["mean"], s["se"], s["n"], cps, self.cfg.cost_eps, self.cfg.params.k_se)
                n["screen"]["cost_rel"], n["screen"]["route"] = round(cps.get("rel", 0.0), 4), route
            if not s["pass"]:
                self._finish_node(tag, "pruned", "screen_reject", {"stage": "screen", "mean_delta": round(s["mean"], 6), "route": route})
            else:
                n["status"] = "screened"
                self.b.node_event(tag, "gated", stage="screened", mean_delta=round(s["mean"], 6), se=round(s["se"], 6))
            return

    # ---- focus rule (ao_focus) -------------------------------------------------------------
    def _check_fill(self, unfunded: bool = False) -> None:
        """A focus promotion is tentative until the new champion's fresh fill (all tasks, unselected trials)
        beats the previous champion's reference on every task: paired mean - FILL_Z*se > 0. Catches a lucky
        look and regressions outside the canary sample at no extra cost (the fill runs anyway); else revert."""
        champ = self.champion
        n = self.node(champ)
        prev = n.get("fill_check")
        ids = self.screen_ids()
        if not prev or (self._missing(champ, ids, self.ref_want(champ)) and not unfunded):
            return
        d = policy.paired_deltas(self.b.rewards(champ, ids, self.ref_window(champ)),
                                 self.b.rewards(prev, ids, self.ref_window(prev)), ids)
        m, se, k = policy.mean_se(d, policy.FOCUS_SD_FLOOR)
        ev = {"stage": "fill_check", "fill_mean_delta": round(m, 4), "se": round(se, 4), "n": k}
        n.pop("fill_check")
        if k and m - policy.FILL_Z * se > 0 and not unfunded:
            n["fill"] = ev
            self.b.node_event(champ, "gated", **ev, kept=True)
            return
        self._finish_node(champ, "rejected", "fill_unfunded" if unfunded else "fill_reject", ev)
        self.node(prev)["status"] = "champion"
        self.st.update(champion=prev, epoch=self.st["epoch"] + 1)
        self.b.restore_champion(prev)          # commit.py moved the run's best_id on the accept; undo it
        self.b.log("promotion_reverted", tag=champ, back_to=prev, **ev)

    def _focus_ids(self, n) -> tuple[list[str], list[str]]:
        """(focus, canaries) against the CURRENT champion, frozen per node per epoch: focus = tasks the
        champion does not always pass (all its draws), canaries = ``focus_canary`` of its passing tasks."""
        if n.get("focus_epoch") != self.st["epoch"]:
            ref = self.b.rewards(self.champion, self.screen_ids(), self.ref_window(self.champion))
            mean = {t: sum(v) / len(v) for t, v in ref.items() if v}
            focus = sorted(t for t, m in mean.items() if m < 1.0)
            passing = sorted(t for t, m in mean.items() if m >= 1.0)
            canary = sorted(random.Random(f"{self.cfg.seed}:{n.get('tag', '')}:{self.st['epoch']}").sample(
                passing, min(self.cfg.focus_canary, len(passing))))
            n.update(focus_ids=focus, canary_ids=canary, focus_epoch=self.st["epoch"], n_pass=len(passing),
                     trials=self.cfg.focus_n, rung=0)
        return n["focus_ids"], n["canary_ids"]

    def _advance_focus(self, tag, n) -> None:
        """Judge ``tag`` on the champion's failing tasks (+ canaries) only, and promote directly: a real
        fix is a large per-task jump there, invisible in a 30-task mean. Looks at ``focus_n`` ..
        ``focus_max`` trials per cell; the champion's reference is all of its draws."""
        n.setdefault("tag", tag)
        if self._missing(self.champion, self.screen_ids(), self.ref_want(self.champion)):   # a new champion's fresh fill first
            n["status"] = "rung"
            return
        focus, canary = self._focus_ids(n)
        ids = focus + canary
        if not focus:                     # the champion passes every task: nothing left this rule can promote on
            self._finish_node(tag, "pruned", "no_focus_targets", {"stage": "focus"})
            return
        if self._missing(tag, ids, (0, n["trials"])):
            n["status"] = "rung"
            return
        ref = self.b.rewards(self.champion, ids, self.ref_window(self.champion))
        cand = self.b.rewards(tag, ids, (0, n["trials"]))
        v = policy.focus_verdict(policy.paired_deltas(cand, ref, focus), policy.paired_deltas(cand, ref, canary),
                                 len(self.screen_ids()), n["n_pass"])
        n["p_beat"], n["focus"] = v["p_beat"], {k: v[k] for k in ("gain", "mean", "se", "canary", "n")}
        route = "reward"
        if v["verdict"] == "accept" and n["trials"] < self.cfg.focus_accept_min:
            v["verdict"] = "more"                 # one trial per cell kills, never accepts: too noisy (seen live)
        if v["verdict"] == "accept" and self.cfg.cost_eps is not None:
            cps = self._cps(tag, ids, (0, n["trials"]), self.champion, self.ref_window(self.champion))
            ok, route = policy.mo_verdict(True, v["mean"], v["se"], v["n"], cps, self.cfg.cost_eps, 1.0)
            n["focus"]["cost_rel"] = round(cps.get("rel", 0.0), 4)
            if not ok:
                v["verdict"] = "kill"
        ev = {"stage": f"focus@{n['trials']}", "gain": round(v["gain"], 4), "route": route, **n["focus"]}
        if v["verdict"] == "accept":
            self.b.commit_accept(tag, ev)
            old = self.champion
            self._finish_node(tag, "champion", "promoted", ev)
            self.node(old)["status"] = "superseded"
            # its reference is a FRESH unselected fill, never the trials that won it the promotion (those
            # are selected upward: reusing them inflated the champion by ~0.1 per promotion in simulation)
            k = FILL_BASE + 10 * (self.st["epoch"] + 1)
            n["ref_window"] = [k, k + FILL_N]
            n["fill_check"] = old                 # the fill must confirm the gain on EVERY task, else revert
            self.st.update(champion=tag, epoch=self.st["epoch"] + 1, proposals_since_improve=0)
        elif v["verdict"] == "kill" or n["trials"] >= self.cfg.focus_max:
            self._finish_node(tag, "pruned", "focus_" + (route if route != "reward" else v["why"]), ev)
        else:
            n["trials"] += 1
            n["rung"] += 1
            n["status"] = "rung"

    def _start_confirms(self) -> None:
        busy = [t for t, n in self.st["nodes"].items() if n["status"] == "confirming"]
        free = self.cfg.max_confirm - len(busy)
        if free <= 0 or self.st.get("stopped"):
            return
        ready = {t: n["screen"]["mean"] for t, n in self.st["nodes"].items() if n["status"] == "screened"}
        for tag in policy.rank_survivors(ready, free):
            ids = self.b.confirm_ids()
            need = 2 * self.cfg.params.n_conf * len(ids)
            if not self.fits(need):
                self.node(tag)["status"] = "unconfirmed"       # pending, never a reject
                self.b.node_event(tag, "gated", stage="unconfirmed", why="confirmation does not fit the budget")
                continue
            n = self.node(tag)
            k0 = FRESH_BASE + (self.n_decided() + len(busy)) * self.cfg.params.n_conf
            n.update(status="confirming", k0=k0, ref=self.champion, ref_epoch=self.st["epoch"], reserved=need)
            busy.append(tag)
            self.b.node_event(tag, "gated", stage="confirming", k0=k0)

    def _decide_confirm(self, tag, n) -> None:
        ids = self.b.confirm_ids()
        w = (n["k0"], n["k0"] + self.cfg.params.n_conf)
        ref = n["ref"]
        if self._missing(tag, ids, w) or self._missing(ref, ids, w):
            return
        deltas = policy.paired_deltas(self.b.rewards(tag, ids, w), self.b.rewards(ref, ids, w), ids)
        p = self.cfg.params
        c = promotion.confirm(deltas, p.dmin, p.z_conf, n.get("screen_n"), p.min_coverage)
        ev = {"stage": "confirm", "confirm_mean": round(c["mean"], 6), "z": None if c["z"] in (float("inf"), float("-inf")) else round(c["z"], 4)}
        if self.cfg.cost_eps is not None:
            cps = self._cps(tag, ids, w, ref, w)
            ok, route = policy.mo_verdict(c["pass"], c["mean"], c["se"], c["n"], cps, self.cfg.cost_eps, p.z_conf)
            c["pass"] = ok and c["n"] >= 2 and c["coverage"] >= p.min_coverage
            ev.update(route=route, cost_per_success_rel=round(cps.get("rel", 0.0), 4),
                      cost_z=None if abs(cps.get("z", 0.0)) == float("inf") else round(cps.get("z", 0.0), 4))
        if not c["pass"]:
            self._finish_node(tag, "rejected", "confirm_reject", ev)
            return
        if n["ref_epoch"] != self.st["epoch"]:
            # another candidate was promoted while this one confirmed: it beat the OLD incumbent;
            # it must clear the new one, so re-screen against the new champion's measurement.
            n.update(status="stale", rung=len(self.cfg.rungs), reserved=0)
            self.b.node_event(tag, "gated", stage="stale", why="incumbent changed during confirmation")
            return
        self.b.commit_accept(tag, {**ev, "k0": n["k0"]})
        old = self.champion
        self._finish_node(tag, "champion", "promoted", ev)
        self.node(old)["status"] = "superseded"
        n["ref_window"] = [n["k0"], n["k0"] + p.n_conf]
        self.st.update(champion=tag, epoch=self.st["epoch"] + 1, proposals_since_improve=0)

    # ---- 3. merge -----------------------------------------------------------------------
    def alive_tips(self) -> list[str]:
        return sorted(t for t, n in self.st["nodes"].items()
                      if not self._is_base(t) and t != self.champion and n["status"] in PRE_CONFIRM + ("confirming", "unconfirmed"))

    def _merge_jobs(self) -> int:
        return len(cs.live(self.st, "merge"))

    def _rebase_all(self) -> None:
        """Champion changed: every alive tip still parented on an older champion is rebased onto it
        (the same merge operator), so stale branches continue instead of dying."""
        if not self.cfg.merge:
            self.st["rebased_epoch"] = self.st["epoch"]
            return
        done = self.st.setdefault("rebased", [])
        for tip in self.alive_tips():
            n = self.node(tip)
            key = f"{tip}>{self.champion}"
            if n.get("edit_kind") in ("rebase", "merge") or key in done or n["status"] in ("confirming", "racing"):
                continue
            if self._merge_jobs() >= 1 or not self._merge_room():
                return
            done.append(key)
            if self.b.related(tip, self.champion):      # the champion is already in its lineage (e.g. a revert)
                continue
            self._do_merge(tip, self.champion, "rebase")
        self.st["rebased_epoch"] = self.st["epoch"]

    def _merge_room(self) -> bool:
        """Merges and rebases are candidates too: they count toward ``max_candidates`` and may add at most
        one node beyond the alive cap (seen live: unbounded near-miss merging queued ~40 nodes)."""
        cap = self.cfg.caps.max_candidates
        return not (cap and self.st["n_proposals"] >= cap) and self.in_flight_nodes() < self.cfg.alive_cap + 1

    def merge(self) -> None:
        if not self.cfg.merge or self._merge_jobs() >= 1 or not self._merge_room():
            return
        tips = self.alive_tips()
        wins = self.b.wins(tips, self.champion)
        merged = {frozenset(p) for p in self.st.get("merged_pairs", [])}
        nm = sum(1 for n in self.st["nodes"].values() if n.get("edit_kind") in ("merge", "rebase"))
        won = any(n.get("edit_kind") == "merge" and n["status"] in ("champion", "rejected", "pruned")
                  for n in self.st["nodes"].values())
        if not policy.merge_allowed(nm, self.st["n_proposals"], won):
            return
        if self.cfg.focus:    # near misses: candidates that fixed failing tasks of THIS champion but not enough alone
            tips = sorted(t for t, n in self.st["nodes"].items() if not self._is_base(t) and t != self.champion
                          and n.get("focus_epoch") == self.st["epoch"] and (n.get("focus") or {}).get("gain", 0) > 0
                          and n["status"] in ("pruned", "rung") and n.get("edit_kind", "edit") == "edit")
            wins = self.b.wins(tips, self.champion)
            eligible = tips
        elif self.cfg.p2:     # a P2 node has been through its rungs when it is pending after a round
            eligible = [t for t in tips if self.node(t)["status"] == "unconfirmed" or self.node(t).get("unconfirmed")]
        else:
            eligible = [t for t in tips if self.node(t)["status"] == "screened"
                        or (self.node(t)["status"] in ("full", "rung") and self.node(t).get("rung", 0) >= 1)]
        pairs = policy.merge_pairs(eligible, wins, self.b.related, merged, bar=self.cfg.merge_bar, limit=10)
        if self.cfg.focus:    # only a pair whose gains TOGETHER could clear the accept bar is worth an evaluation
            g = lambda t: (self.node(t).get("focus") or {}).get("gain", 0.0)  # noqa: E731
            pairs = [p for p in pairs if g(p[0]) + g(p[1]) >= policy.FOCUS_MIN_GAIN]
        if pairs:
            a, b, _ = pairs[0]
            self.st.setdefault("merged_pairs", []).append(sorted((a, b)))
            self._do_merge(a, b, "merge")

    def _do_merge(self, a, b, kind) -> None:
        tag = self.new_tag()
        self.st["n_proposals"] += 1
        out = self.b.merge_build(a, b, tag, kind)
        if out.get("built"):
            j = cs.new_job(self.st, "merge", tag=tag, state="done", parent=a, edit_kind=kind, reserved_tokens=0)
            self._add_node(tag, {"hash": self.b.cap_hash(tag), "parents": [a, b]}, j)
            return
        if out.get("conflicts") and self.cfg.caps.proposer_cap and cs.tokens_fit(
                self.st, self.cfg.job_token_cap, self.cfg.caps.max_tokens, self.cfg.caps.finalize_tokens):
            j = cs.new_job(self.st, "merge", tag=tag, parent=a, parents=[a, b], edit_kind=kind,
                           conflicts=out["conflicts"], reserved_tokens=self.cfg.job_token_cap, reserved_rollouts=0)
            self._start(j)
            return
        self.b.log("merge_skipped", a=a, b=b, why="conflicts, no token budget" if out.get("conflicts") else "nothing merged")
        self.b.discard(tag)

    # ---- 4. evaluation chunks -----------------------------------------------------------
    def _inflight(self, tag, w) -> set[str]:
        out = set()
        for j in cs.live(self.st, "eval"):
            if j["tag"] == tag and window_key(j["window"]) == tuple(w):
                out.update(j["ids"])
        return out

    def _wants(self) -> list[tuple]:
        """(priority, sort key, tag, ids, window, owner, purpose) for every cell block we want run."""
        out = []
        ids = self.screen_ids()
        champ = self.champion
        out.append((0, "", champ, ids, self.ref_want(champ), champ, "baseline"))
        for tag in sorted(self.st["nodes"]):
            n = self.st["nodes"][tag]
            if n["status"] == "confirming":
                w = (n["k0"], n["k0"] + self.cfg.params.n_conf)
                cids = self.b.confirm_ids()
                out.append((1, tag, tag, cids, w, tag, "confirm"))
                out.append((1, tag, n["ref"], cids, w, tag, "confirm"))
            elif n["status"] in ("proposed", "rung", "full", "stale") and not self._is_base(tag):
                if self.cfg.focus:
                    if self._missing(champ, ids, self.ref_want(champ)):
                        continue                                  # wait for the champion's fill (priority 0)
                    n.setdefault("tag", tag)
                    f, c = self._focus_ids(n)
                    sids, w = f + c, (0, n["trials"])
                else:
                    sids, w = self._stage_ids(n), (0, self.cfg.screen_n)
                out.append((2, f"{-n.get('p_beat', 0.5):+.6f}:{tag}", tag, sids, w, tag, "rung"))
        return sorted(out, key=lambda w: (w[0], w[1]))

    def launch_evals(self) -> None:
        if self.cfg.p2:
            self._p2_launch()
            return
        if self.st.get("stopped"):           # finish confirmations, and a pending focus fill check
            fill = bool(self.cfg.focus and self.node(self.champion).get("fill_check"))
            wants = [w for w in self._wants() if w[6] == "confirm" or (fill and w[6] == "baseline")]
        else:
            wants = self._wants()
        for prio, _k, tag, ids, window, owner, purpose in wants:
            miss = self._missing(tag, ids, window)
            for t in self._inflight(tag, window):
                miss.pop(t, None)
            for ch in policy.chunks(miss, self.cfg.chunk):
                if len(cs.live(self.st, "eval")) >= self.cfg.slots:
                    return
                if not self._reserve_for(owner, purpose, ch["rollouts"]):
                    continue
                j = cs.new_job(self.st, "eval", tag=tag, ids=ch["ids"], window=list(window), owner=owner,
                               purpose=purpose, fixed=window[0] > 0, reserved_rollouts=ch["rollouts"],
                               reserved_tokens=0)
                self._start(j)

    def _reserve_for(self, owner, purpose, need) -> bool:
        """Reserve ``need`` rollouts for a chunk. A confirmation's rollouts were reserved when it
        started, so its chunks draw on that node reservation; everything else must fit the budget."""
        n = self.st["nodes"].get(owner)
        if purpose == "confirm" and n is not None and n.get("reserved", 0) >= need:
            n["reserved"] -= need
            return True
        return self.fits(need)

    def _start(self, j) -> None:
        j["started"] = self.clock()
        self.save()                  # the job is on disk BEFORE its process exists: no orphan we cannot see
        try:
            j.update(self.b.start(j))
            j["state"] = "running"
            self.save()              # the pid is on disk before anything else can crash: no double run on resume
        except Exception as e:      # noqa: BLE001 - a job that cannot start is a failed job, not a crash
            j["state"] = "failed"
            j["reserved_rollouts"] = j["reserved_tokens"] = 0
            j["error"] = f"{type(e).__name__}: {e}"
            self.b.log("job_start_failed", job=j["id"], job_kind=j["kind"], error=j["error"])

    # ---- P2 rounds ------------------------------------------------------------------------
    def _p2_pool(self) -> list[str]:
        return sorted(t for t, n in self.st["nodes"].items()
                      if not self._is_base(t) and n["status"] == "proposed" and not n.get("round"))

    def _p2_step(self) -> None:
        r = self.st.get("round")
        if r is None:
            return self._p2_maybe_open()
        if r["stage"] == "seq":
            return                                   # one worker job runs the group-sequential test
        stage = r["stage"]
        if stage not in r["jobs"]:
            r["jobs"][stage] = self.b.p2_stage_jobs(r["id"], stage)     # created ONCE, then stored
        pend = [x for x in r["jobs"][stage] if not self.b.p2_job_done(r["id"], x)]
        live = [j for j in cs.live(self.st, "eval") if j.get("round") == r["id"]]
        if r.get("unfunded") or any(v >= self.cfg.eval_retries for v in r.get("fails", {}).values()):
            if not live:
                self._p2_close_stage(r, unfunded=True)
        elif not pend and not live:
            self._p2_close_stage(r, unfunded=False)

    def _p2_maybe_open(self) -> None:
        pool = self._p2_pool()
        if not pool:
            return
        stopped = bool(self.st.get("stopped"))
        proposing = len(cs.live(self.st, "propose")) + len(cs.live(self.st, "merge"))
        if len(pool) < self.cfg.k_prop and proposing and not stopped:
            return                                   # keep collecting the batch
        if stopped:
            return
        k, funded = self.b.p2_plan(min(len(pool), self.cfg.k_prop), self.champion)
        if not funded:
            self.st["round_unfunded"] = True
            return
        chosen = pool[:k]
        rid = self.b.p2_open(chosen, self.champion)
        self.st["round"] = {"id": rid, "stage": "rung1" if len(chosen) > 1 else "seq", "tags": chosen,
                            "jobs": {}, "fails": {}, "unfunded": False}
        for t in chosen:
            self.node(t).update(status="racing", round=rid)
            self.b.node_event(t, "proposed", stage="racing", round=rid)
        self.b.log("p2_round", round=rid, tags=chosen, stage=self.st["round"]["stage"])

    def _p2_launch(self) -> None:
        r = self.st.get("round")
        if r is None:
            return
        live = cs.live(self.st, "eval")
        if r["stage"] == "seq":
            if not any(j.get("p2seq") for j in live) and len(live) < self.cfg.slots and "seq_done" not in r:
                j = cs.new_job(self.st, "eval", tag=r["tags"][0], owner=r["tags"][0], round=r["id"],
                               p2seq={"round": r["id"], "cid": r["tags"][0]}, purpose="seq",
                               reserved_rollouts=0, reserved_tokens=0, ids=[], window=[0, 0])
                self._start(j)
            return
        if self.st.get("stopped") and r["stage"] not in ("confirm", "seq"):
            return
        busy = {j["p2"]["job_id"] for j in live if j.get("p2")}
        for x in r["jobs"].get(r["stage"], []):
            if len(cs.live(self.st, "eval")) >= self.cfg.slots:
                return
            if x["job_id"] in busy or self.b.p2_job_done(r["id"], x) or r.get("unfunded"):
                continue
            if r.get("fails", {}).get(x["job_id"], 0) >= self.cfg.eval_retries:
                continue
            j = cs.new_job(self.st, "eval", tag=x["cid"], owner=x["cid"], round=r["id"], p2=x, purpose=x["stage"],
                           ids=list(x["ids"]), window=[0, 0], reserved_rollouts=0, reserved_tokens=0)
            self._start(j)

    def _p2_reaped(self, j, res) -> None:
        r = self.st.get("round")
        if r is None or j.get("round") != r["id"]:
            return
        if j.get("p2seq"):
            if res.get("ok", True) and res.get("verdict"):
                r["seq_done"] = True
                self._p2_apply_confirm({res["verdict"]["cid"]: res["verdict"]}, champion=res["verdict"]["cid"]
                                       if res["verdict"]["status"] == "accept" else None)
                self._p2_end_round(r)
            elif not res.get("ok", True):
                r.setdefault("fails", {})["seq"] = r.get("fails", {}).get("seq", 0) + 1
                if r["fails"]["seq"] >= self.cfg.eval_retries:
                    self._p2_abandon_round(r, "sequential test failed")
                else:
                    r.pop("seq_done", None)
            return
        if res.get("unfunded"):
            r["unfunded"] = True
        elif not res.get("ok", True):
            jid = j["p2"]["job_id"]
            r.setdefault("fails", {})[jid] = r.get("fails", {}).get(jid, 0) + 1

    def _p2_close_stage(self, r, unfunded: bool) -> None:
        out = self.b.p2_close(r["id"], r["stage"], unfunded)
        verdicts = out.get("verdicts", {})
        if r["stage"] == "confirm":
            self._p2_apply_confirm(verdicts, out.get("champion"))
            return self._p2_end_round(r)
        for tag, v in verdicts.items():
            if v["status"] == "kill":
                self._finish_node(tag, "pruned", "rung_kill", {"stage": r["stage"]})
            elif v["status"] == "unfunded":
                self.node(tag).update(status="proposed", round=None)
        nxt = out.get("next")
        if not nxt or unfunded:
            for tag in r["tags"]:
                if self.node(tag)["status"] == "racing":
                    self.node(tag).update(status="proposed", round=None, why="round unfunded")
            return self._p2_end_round(r)
        r["stage"] = nxt
        r["jobs"].pop(nxt, None)

    def _p2_apply_confirm(self, verdicts, champion) -> None:
        for tag in sorted(verdicts):
            v = verdicts[tag]
            n = self.node(tag)
            if v["status"] == "accept" and tag == champion:
                ev = {"stage": "confirm", "confirmation": "accept"}
                self.b.commit_accept(tag, {**ev, "mean": v.get("mean"), "z": v.get("z")})
                old = self.champion
                self._finish_node(tag, "champion", "promoted", ev)
                self.node(old)["status"] = "superseded"
                self.st.update(champion=tag, epoch=self.st["epoch"] + 1, proposals_since_improve=0)
            elif v["status"] == "unconfirmed" or (v["status"] == "accept"):
                # survived but could not be funded (or lost to a better accept): pending, never a reject
                n["unconfirmed"] = int(n.get("unconfirmed", 0)) + 1
                if n["unconfirmed"] > 1 or v["status"] == "accept":
                    n.update(status="unconfirmed", round=None)
                    self.b.node_event(tag, "gated", stage="unconfirmed", confirmation="pending")
                else:
                    n.update(status="proposed", round=None)
            else:
                self._finish_node(tag, "rejected", "confirm_reject", {"stage": "confirm", "confirmation": "reject"})

    def _p2_end_round(self, r) -> None:
        for tag in r["tags"]:
            n = self.st["nodes"].get(tag)
            if n and n["status"] == "racing":          # survived to a verdict-less end: back to the pool
                n.update(status="proposed", round=None)
        self.st["rounds_done"] = int(self.st.get("rounds_done", 0)) + 1
        self.st["round"] = None

    def _p2_abandon_round(self, r, why) -> None:
        for j in cs.live(self.st, "eval"):
            if j.get("round") == r["id"] and self._stop(j):
                j["state"] = "lost"
                j["reserved_rollouts"] = j["reserved_tokens"] = 0
        for tag in r["tags"]:
            n = self.st["nodes"].get(tag)
            if n and n["status"] == "racing":
                n.update(status="unconfirmed", round=None, why=why)
                self.b.node_event(tag, "gated", stage="unconfirmed", why=why)
        self.b.log("p2_round_abandoned", round=r["id"], why=why)
        self.st["round"] = None

    # ---- 5. propose ---------------------------------------------------------------------
    def in_flight_nodes(self) -> int:
        return sum(1 for t, n in self.st["nodes"].items() if not self._is_base(t) and n["status"] in PRE_CONFIRM + ("confirming",))

    def propose(self) -> None:
        cap = self.cfg.caps
        # retries of proposals that failed first (same tag, stricter prompt)
        for j in sorted(self.st["jobs"].values(), key=lambda j: j["id"]):
            if j["kind"] == "propose" and (j.get("retry") or j.get("retry_of_lost")) and j["state"] in ("failed", "done", "lost") and not j.get("relaunched"):
                if len(cs.live(self.st, "propose")) >= self.cfg.k_prop or not self._token_room():
                    return
                j["relaunched"] = True
                if self.st.get("attempts", {}).get(j["tag"], 0) > self.cfg.propose_retries:
                    self._give_up(j["tag"], j)
                    continue
                self._launch_propose(j["tag"], j["parent"], j.get("slot", 0), retry=True, edit_kind=j.get("edit_kind", "edit"),
                                     refusal=(self.st.get("refusals", {}).get(j["tag"]) or {}).get("detail", ""))
        while True:
            live = cs.live(self.st, "propose") + cs.live(self.st, "merge")
            if len(live) >= self.cfg.k_prop or self.in_flight_nodes() + len(live) >= self.cfg.alive_cap:
                return
            if not self._token_room() or not self.fits(self.cfg.caps.chunk):
                return
            if cap.max_candidates and self.st["n_proposals"] >= cap.max_candidates:
                return
            if cap.max_idle and int(self.st.get("idle_proposals", 0)) >= cap.max_idle:
                return                      # exhausted: stop proposing; the run ends once in-flight nodes are decided
            used = {j.get("slot") for j in cs.live(self.st, "propose")}
            slot = next(i for i in range(self.cfg.k_prop) if i not in used)
            tag = self.new_tag()
            self.st["n_proposals"] += 1
            rng = random.Random(f"{self.cfg.seed}:{self.st['n_proposals']}:{slot}")
            tips = {t: self.node(t).get("p_beat", 0.0) for t in self.alive_tips()}
            stuck = {t: n.get("stuck", 0) for t, n in self.st["nodes"].items()}
            parent = policy.pick_parent(slot, self.champion, tips, rng, stuck)
            self._launch_propose(tag, parent, slot)

    def _token_room(self) -> bool:
        c = self.cfg.caps
        return cs.tokens_fit({"tokens_committed": self.tokens_used(), "jobs": self.st["jobs"]}, self.cfg.job_token_cap,
                             c.max_tokens, c.finalize_tokens)

    def _launch_propose(self, tag, parent, slot, retry=False, edit_kind="edit", refusal="") -> None:
        j = cs.new_job(self.st, "propose", tag=tag, parent=parent, slot=slot, retry=False, edit_kind=edit_kind,
                       strict=retry, refusal=refusal, reserved_tokens=self.cfg.job_token_cap, reserved_rollouts=0)
        self._start(j)

    # ---- 6. stop / drain / finish -------------------------------------------------------
    def stop_check(self) -> str | None:
        if self.st.get("stopped"):
            return self.st["stopped"]
        if self.st.get("round_unfunded") and not self.st.get("round"):
            return "budget: no round fits the remaining rollouts"
        alive_p = [self.node(t).get("p_beat", 0.0) for t in self.alive_tips()]
        champ_reward = self.b.best_reward(self.champion)
        return policy.stop_reason(
            caps=self.cfg.caps, committed=self.committed(),
            reserved=cs.reserved(self.st) + self.b.reserved_rollouts(),
            tokens=self.tokens_used(), tokens_reserved=cs.reserved(self.st, "reserved_tokens"), now=self.clock(),
            best_reward=champ_reward, n_proposals=self.st["n_proposals"], since_improve=self.st["proposals_since_improve"],
            alive_p=alive_p, idle=int(self.st.get("idle_proposals", 0)), in_flight=self.in_flight_nodes() + len(cs.live(self.st, "propose")) + len(cs.live(self.st, "merge")))

    def drain(self) -> bool:
        """After a stop: cancel proposer/merge jobs and evals that do not serve a running
        confirmation; let confirmations finish if their cells fit (already reserved); a node whose
        confirmation can no longer run is ``unconfirmed``. True when nothing is in flight."""
        for j in cs.live(self.st):
            keep = self._keep_on_drain(j)
            if not keep and not j.get("cancelling") and self._stop(j):
                j["state"] = "lost"
                j["reserved_rollouts"] = j["reserved_tokens"] = 0
        confirming = [t for t, n in self.st["nodes"].items() if n["status"] == "confirming"]
        for t in confirming:
            n = self.node(t)
            if not cs.live(self.st, "eval") and (self._missing(t, self.b.confirm_ids(), (n["k0"], n["k0"] + self.cfg.params.n_conf))
                                                or self._missing(n["ref"], self.b.confirm_ids(), (n["k0"], n["k0"] + self.cfg.params.n_conf))):
                if not self._confirm_launchable(t, n):
                    n["status"] = "unconfirmed"
                    n["reserved"] = 0
                    self.b.node_event(t, "gated", stage="unconfirmed", why="stopped before the confirmation finished")
        if self.cfg.p2:
            r = self.st.get("round")
            if r and r["stage"] not in ("confirm", "seq"):
                self._p2_abandon_round(r, "stopped before the round reached its confirmation")
            return not cs.live(self.st) and not self.st.get("round")
        if self.cfg.focus:
            self._check_fill()
            if self.node(self.champion).get("fill_check"):
                need = sum(self._missing(self.champion, self.screen_ids(), self.ref_want(self.champion)).values())
                if cs.live(self.st, "eval") or self.fits(need):
                    return False                     # running, or launches next tick
                self._check_fill(unfunded=True)      # the fill cannot be funded: an unverified promotion reverts
        return not cs.live(self.st) and not any(n["status"] == "confirming" for n in self.st["nodes"].values())

    def _keep_on_drain(self, j) -> bool:
        if j["kind"] != "eval":
            return False
        if self.cfg.focus and j.get("purpose") == "baseline" and self.node(self.champion).get("fill_check"):
            return True                    # the new champion's fill decides whether its promotion stands
        if self.cfg.p2:
            r = self.st.get("round")
            return bool(r) and r["stage"] in ("confirm", "seq") and j.get("round") == r["id"]
        return j.get("purpose") == "confirm" and self.node(j["owner"])["status"] == "confirming"

    def _confirm_launchable(self, tag, n) -> bool:
        return bool(n.get("reserved")) and len(cs.live(self.st, "eval")) < self.cfg.slots

    def finish(self) -> None:
        for t, n in self.st["nodes"].items():
            if n["status"] in PRE_CONFIRM and not self._is_base(t):
                self.b.node_event(t, "gated" if n["status"] == "screened" else "proposed", stage="pending_at_stop")
        if not self.cfg.finalize:
            if not self.st.get("final_skipped"):
                self.st["final_skipped"] = self.b.skip_finalize(self.champion)
        elif not self.b.finalized():
            try:
                self.st["final"] = self.b.finalize(self.champion)
            except Refused as e:                 # retrying cannot help: stop the supervisor instead of looping it
                self.st["finalize_blocked"] = str(e)[:400]
                self.b.log("finalize_blocked", reason=self.st["finalize_blocked"])
                self.save()
                raise
        self.st["finalized"] = True
        self.b.log("conductor_done", champion=self.champion, reason=self.st.get("stopped"))


# ---- supervisor -------------------------------------------------------------------------------

def supervise(argv: list[str], *, max_restarts: int = 50, sleep_s: float = 5.0, spawn=None, sleep=time.sleep) -> int:
    """Run ``conductor.py run`` until it exits 0 (done) or 2 (refused: never retried). Any other exit
    - a crash, OOM kill, SIGKILL - is relaunched against the same run dir; the conductor resumes."""
    spawn = spawn or (lambda a: subprocess.call([sys.executable, str(Path(__file__).resolve()), "run", *a]))
    for i in range(max_restarts + 1):
        rc = spawn(argv)
        if rc in (0, EXIT_REFUSED):
            return rc
        sleep(sleep_s)
    return 1


# ---- cli --------------------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="conductor", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "supervise"):
        s = sub.add_parser(name)
        s.add_argument("--run-dir", required=True)
        s.add_argument("--project", required=True)
        s.add_argument("--optimizer", default=None, help="run-optimizer row for proposer jobs (default: spec optimizer)")
        s.add_argument("--max-ticks", type=int, default=None)
        if name == "supervise":
            s.add_argument("--max-restarts", type=int, default=50)
            s.add_argument("--sleep", type=float, default=5.0)
    return p


def main(argv=None) -> int:
    a = _parser().parse_args(argv)
    if a.cmd == "supervise":
        rest = ["--run-dir", a.run_dir, "--project", a.project] + (["--optimizer", a.optimizer] if a.optimizer else [])
        return supervise(rest, max_restarts=a.max_restarts, sleep_s=a.sleep)
    import conductor_backend
    try:
        be, cfg = conductor_backend.open_backend(a.run_dir, a.project, a.optimizer)
    except Refused as e:
        print(json.dumps({"ok": False, "refused": str(e)}, indent=2))
        return EXIT_REFUSED
    with be.run_lock():
        c = Conductor(Path(a.run_dir).resolve(), be, cfg)
        try:
            rc = c.run(a.max_ticks)
        except Refused as e:             # e.g. finalize blocked: a relaunch would hit the same wall
            print(json.dumps({"ok": False, "refused": str(e)}, indent=2))
            return EXIT_REFUSED
    print(json.dumps({"ok": rc == 0, "champion": c.champion, "stopped": c.st.get("stopped"),
                      "n_proposals": c.st["n_proposals"]}, indent=2))
    return rc


if __name__ == "__main__":
    # run the importable module, not __main__: conductor_backend does `import conductor`, and its Refused must
    # be the very class main() catches (two copies of this file would make the exit-2 path a crash the supervisor retries)
    import conductor as _conductor
    sys.exit(_conductor.main())
