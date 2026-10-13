"""conductor_backend -- the real world behind conductor.py: run dir, evidence ledger, subprocess jobs.

    open_backend(run_dir, project, optimizer) -> (RealBackend, Cfg)     # refuses multi-objective specs

Jobs are conductor-owned subprocesses (their own session, a pid file and an exit-code file), so a
conductor that is killed leaves them running and finds their exit codes on restart:

  eval     evaluate/run.py for one chunk of cells (``--topup-to`` for the selection trials, an explicit
           ``--trial-offset`` + ``--fixed-seeds`` for fresh confirmation trials). The ledger is the checkpoint.
  propose  run-optimizer on a fresh copy of the parent, with the small proposer prompt (proposer.py).
  merge    run-optimizer resolving the conflicts of a merge that merge_n could not fold on its own.

P2 jobs (``promotion_rule: P2``) run ``Round.run_job`` on worker threads of this process instead; the
evaluator's done-markers make them idempotent across a restart. Verbs that mutate the run (propose
registration, commit, prune, merge, finalize) are the existing ``act.py`` functions called in-process, so
there is one code path for them in both engines.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

import act
import conductor
import digest
import proposer
from cap_evolve import RunDir, eval_index, graph, harness, optimizer_config
from cap_evolve.candidate_graph import CandidateGraph
from cap_evolve.specfile import spec_for_run

HERE = Path(__file__).resolve().parent
SKILLS = act.SKILLS
RUN_OPTIMIZER = SKILLS / "optimizers" / "run-optimizer" / "scripts" / "run.py"
SELF = "conductor"


def open_backend(run_dir: str, project: str, optimizer: str | None = None):
    rd = RunDir.open(Path(run_dir).resolve())
    spec = spec_for_run(rd, Path(project))
    cfg = conductor.Cfg.from_spec(spec, rd.budget.to_dict())           # raises conductor.Refused
    return RealBackend(rd, Path(project), spec, cfg, optimizer), cfg


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError, TypeError):
        return True
    return True


def helper_refusal(spec: dict, cand: Path, parent: Path | None):
    """PR-3 helper checks (static lint, then the smoke run) on a proposed candidate, or None.

    Optional: ``cap_evolve.helpers`` / ``helper_smoke`` are imported only if they exist and
    ``helpers.enabled`` is set, so without PR-3 this is a no-op. A failure costs 0 rollouts."""
    try:
        from cap_evolve import helper_smoke, helpers
    except ImportError:
        return None
    if not helpers.enabled(spec):
        return None
    cfg = helpers.resolve(spec)
    if cfg.get("lint", True):
        r = helpers.lint_candidate(cand, cfg, parent)
        if not r.get("ok", True):
            return "helper_lint", "; ".join(map(str, r.get("findings") or []))[:300]
    if cfg.get("smoke", True):
        r = helper_smoke.run_smoke(cand, cfg, parent=parent)
        if not r.get("ok", True):
            return "helper_smoke", str(r.get("detail"))[:300]
    return None


class P2Port:
    """The conductor's P2 methods over ``cap_evolve.evaluator``. A backend supplies ``ev`` (a P2Evaluator),
    ``_round(rid)``, ``_job(dict)``, ``_dir(tag)`` (a candidate's directory) and ``_workdir(tag)``."""

    def p2_plan(self, k_wanted, incumbent):
        plan = self.ev.plan_round(k_wanted, self._dir(incumbent))
        return plan.k, plan.funded

    def p2_open(self, tags, incumbent):
        rnd = self.ev.open_round({t: self._workdir(t) for t in tags}, (incumbent, self._dir(incumbent)))
        self._remember_round(rnd)
        return rnd.round_id

    def _remember_round(self, rnd):
        self._rounds[rnd.round_id] = rnd

    def p2_stage_jobs(self, rid, stage):
        rnd = self._round(rid)
        jobs = {"rung1": lambda: rnd.incumbent_jobs() + rnd.rung_jobs(1), "rung2": lambda: rnd.rung_jobs(2),
                "confirm": rnd.confirm_jobs}[stage]()
        return [j.to_dict() for j in jobs]

    def p2_job_done(self, rid, x):
        return self._round(rid)._marker(self._job(x)).exists()

    def p2_close(self, rid, stage, unfunded):
        rnd = self._round(rid)
        live = rnd.state["live"]
        if stage == "confirm":
            if unfunded:
                rnd.state["confirm_unfunded"] = list(rnd.state.get("confirm_unfunded", [])) + list(rnd.state.get("confirm_funded", []))
                rnd.state["confirm_funded"] = []
            out = rnd.close_confirm()
            return {"verdicts": {c: {"status": v.status, "mean": v.mean, "z": v.z} for c, v in out.items()},
                    "champion": rnd.champion}
        n = int(stage[-1])
        if unfunded:
            return {"verdicts": {c: {"status": "unfunded"} for c in live[str(n)]}, "next": None}
        out = rnd.close_rung(n)
        nxt = "rung2" if n == 1 and live["2"] else ("confirm" if n == 2 and live.get("confirm") else None)
        return {"verdicts": {c: {"status": v.status, "mean": v.mean, "z": v.z} for c, v in out.items()}, "next": nxt}


class RealBackend(P2Port, conductor.Backend):
    def __init__(self, run_dir: RunDir, project: Path, spec: dict, cfg: conductor.Cfg, optimizer: str | None):
        self.run_dir, self.root, self.project, self.spec, self.cfg = run_dir, Path(run_dir.root), project, spec, cfg
        self.optimizer = optimizer or str(spec.get("optimizer_skill") or "mock")
        self.jobs_dir = self.root / "conductor_jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.ns = argparse.Namespace(run_dir=str(self.root), project=str(project), strict=False)
        self.ctx = act.Ctx(self.ns)
        self._rows: tuple = (None, [])
        self._hash: dict = {}
        self._threads: dict = {}
        self._pool = None
        self._ev = None
        self._rounds: dict = {}
        self._lock = threading.Lock()

    # ---- process lifetime
    @contextlib.contextmanager
    def run_lock(self):
        """One conductor per run dir. flock, held for the life of the process and released by the OS even on a
        crash; a second conductor fails fast with the holder's pid."""
        self.run_dir.run_lock("conductor")
        yield

    # ---- data: the evidence ledger
    def _ledger(self) -> list[dict]:
        path = self.root / eval_index.LEDGER
        try:
            m = path.stat().st_mtime_ns
        except OSError:
            return []
        if self._rows[0] != m:
            self._rows = (m, eval_index.rows(self.run_dir))
        return self._rows[1]

    def screen_ids(self):
        return [str(t) for t in (self.ev.feedback_ids() if self.cfg.p2 else self.ctx.val_ids())]

    def confirm_ids(self):
        return [str(t) for t in (self.ev.confirm_ids() if self.cfg.p2 else self.ctx.val_ids())]

    def cap_hash(self, tag):
        d = digest.cand_dir(self.run_dir, tag)
        if not d.is_dir():
            return None
        key = (tag, d.stat().st_mtime_ns)
        if key not in self._hash:
            self._hash[key] = eval_index.cap_hash(d)
        return self._hash[key]

    def _cells(self, tag, ids, window, field="reward"):
        h, fp, lo, hi = self.cap_hash(tag), eval_index.env_fp(), *window
        want = set(map(str, ids))
        out: dict[str, dict[int, float]] = {}
        for r in self._ledger():
            if (r["cap_hash"] == h and r["split"] == "val" and r["env_fp"] == fp and r["task"] in want
                    and lo <= int(r["trial_idx"]) < hi):
                v = r[field] if field == "reward" else r.get(field)
                out.setdefault(r["task"], {})[int(r["trial_idx"])] = None if v is None else float(v)
        return out

    def missing(self, tag, ids, window):
        have, lo, hi = self._cells(tag, ids, window), window[0], window[1]
        out = {t: (hi - lo) - len(have.get(str(t), {})) for t in map(str, ids)}
        return {t: n for t, n in out.items() if n > 0}

    def rewards(self, tag, ids, window):
        cells = self._cells(tag, ids, window if window is not None else (0, 10 ** 12))
        return {t: [c[k] for k in sorted(c)] for t, c in cells.items()}

    def costs(self, tag, ids, window):
        """Per-cell agent cost (USD), aligned with ``rewards``; None where the row has none."""
        cells = self._cells(tag, ids, window if window is not None else (0, 10 ** 12), "cost")
        return {t: [c[k] for k in sorted(c)] for t, c in cells.items()}

    def initial_champion(self):
        return RunDir.open(self.root).best_id or "seed"

    def spent_rollouts(self):
        return int(RunDir.open(self.root).spent.metric_calls)

    def spent_tokens(self):
        return int(RunDir.open(self.root).spent.optimizer_tokens)

    def remaining_rollouts(self):
        return RunDir.open(self.root).remaining_metric_calls()

    def reserved_rollouts(self):
        return RunDir.open(self.root).reserved_metric_calls()

    def best_reward(self, tag):
        try:
            sr = harness.split_result_from_rollouts(self.run_dir, tag, "val")
            return sr.reward if sr.per_task else None
        except Exception:  # noqa: BLE001
            return None

    # ---- jobs
    def _paths(self, job):
        stem = self.jobs_dir / job["id"]
        return stem.with_suffix(".log"), stem.with_suffix(".rc"), stem.with_suffix(".prompt.md")

    def _spawn(self, job, cmd, env=None):
        log, rc, _ = self._paths(job)
        rc.unlink(missing_ok=True)
        wrapped = ["sh", "-c", f'"$@"; echo $? > {rc}', "sh", *map(str, cmd)]
        with log.open("ab") as f:
            p = subprocess.Popen(wrapped, stdout=f, stderr=subprocess.STDOUT, env={**os.environ, **(env or {})},
                                 start_new_session=True, cwd=str(self.root))
        return {"pid": p.pid}

    def eval_cmd(self, job) -> list[str]:
        tag, ids, (lo, hi) = job["tag"], job["ids"], job["window"]
        # ponytail: always the exact trial window, never --topup-to (that numbers refills after the tag's
        # highest k, so an errored trial 1 came back as trial 2 and the window [0, 2) waited forever).
        # A partial refill re-runs the cells it already has; dedupe per cell if that waste ever matters.
        cmd = eval_index.eval_cmd(self.root, self.project, tag, "val", hi - lo, ids=ids, trial_offset=lo,
                                  fixed_seeds=True, skills_dir=SKILLS)
        cmd[cmd.index("--candidate") + 1] = str(digest.cand_dir(self.run_dir, tag))
        return cmd

    def start(self, job):
        kind = job["kind"]
        if job.get("p2") or job.get("p2seq"):
            return self._start_p2(job)
        if kind == "eval":
            workers = max(1, int(self.spec.get("gateway_max_concurrency") or self.cfg.slots) // max(1, self.cfg.slots))
            env = {} if os.environ.get("CAPEVOLVE_WORKERS") else {"CAPEVOLVE_WORKERS": str(workers)}
            return self._spawn(job, self.eval_cmd(job), env)
        if kind in ("propose", "merge"):
            return self._start_llm(job)
        return {}                                   # diagnose: nothing to run yet

    def _start_llm(self, job):
        tag, parent, kind = job["tag"], job["parent"], job["kind"]
        work = self.ctx.work(tag)
        if kind == "propose":
            if work.exists():
                shutil.rmtree(work)                 # a retry starts from a clean copy of the parent
            rc, out, err = act.sh([act.PY, HERE / "prepare_candidate.py", "-r", self.root, "-t", tag, "--parent", parent])
            if rc != 0:
                raise RuntimeError(f"prepare_candidate failed: {(err or out)[-300:]}")
            (work.parent / f".parent_{tag}").write_text(parent)
        try:
            dg, text = digest.fit(digest.build(self.run_dir, self.project, self.spec))
        except Exception:  # noqa: BLE001 - a digest failure must not stop a proposal
            dg, text = {}, ""
        if self.cfg.cost_eps is not None:
            text = ("Objectives: reward first, then cost per success (agent USD per unit reward); an edit that "
                    "adds cost per success beyond " f"{self.cfg.cost_eps:.0%} is rejected even when reward rises.\n" + text)
        taken = {j.get("cluster") for j in conductor_jobs(self.root) if j.get("state") in ("queued", "running")}
        cluster = proposer.pick_cluster(dg, int(job.get("slot") or 0), taken)
        job["cluster"] = (cluster or {}).get("id")
        log, rcf, prompt = self._paths(job)
        prompt.write_text(proposer.build_prompt(workdir=work, parent=parent, cluster=cluster, digest_text=text,
                                                strict=bool(job.get("strict")), kind=kind,
                                                conflicts=job.get("conflicts")), encoding="utf-8")
        cmd = [act.PY, RUN_OPTIMIZER, "--name", self.optimizer, "--workdir", work, "--prompt", prompt, "--json",
               "--transcript", str(self.transcript(job))]
        turns = int(self.spec.get("optimizer_max_turns") or 40)
        cmd += ["--budget", str(turns)]
        usd = self.job_usd_cap()
        if usd:
            cmd += ["--usd-budget", f"{usd:g}"]         # the CLI's own hard stop; the conductor's token kill is the backstop
        if self.spec.get("optimizer_model"):
            cmd += ["--model", str(self.spec["optimizer_model"])]
        return self._spawn(job, cmd)

    def transcript(self, job) -> Path:
        return self.jobs_dir / f"{job['id']}.transcript.jsonl"

    def job_usd_cap(self) -> float:
        """Hard $ limit for ONE one-shot job: ``ao_job_usd_cap``, else what is left of ``max_optimizer_usd``
        (never more than the run may still spend). 0 = no dollar cap configured."""
        cap = float(self.spec.get("ao_job_usd_cap") or 0)
        total = float(self.spec.get("max_optimizer_usd") or 0)
        if total:
            left = max(total - float(RunDir.open(self.root).spent.optimizer_usd), 0.01)
            cap = min(cap, left) if cap else left
        return cap

    def running_tokens(self, job):
        return proposer.transcript_tokens(self.transcript(job))

    def alive(self, job):
        if job.get("p2") or job.get("p2seq"):
            return job["id"] in self._threads
        pid = job.get("pid")
        return bool(pid) and _pid_alive(pid)

    def poll(self, job):
        if job.get("p2") or job.get("p2seq"):
            return self._poll_p2(job)
        log, rcf, _ = self._paths(job)
        if not rcf.exists():
            return None
        try:
            rc = int(rcf.read_text().strip() or 1)
        except ValueError:
            rc = 1
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        res = {"ok": rc == 0, "rc": rc, "tail": text[-400:]}
        if job["kind"] in ("propose", "merge"):
            res["tokens"] = proposer.tokens_from_result(text)
        return res

    def kill(self, job):
        if job.get("p2") or job.get("p2seq"):
            f = self._threads.get(job["id"])
            if f is not None and not f.done() and not f.cancel():
                return False             # mid-rollout: a thread cannot be interrupted; keep its slot and reservation
            self._threads.pop(job["id"], None)
            return True
        pid = job.get("pid")
        if pid and _pid_alive(pid):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(int(pid), signal.SIGTERM)

    # ---- graph and verbs (act.py, in-process)
    def register(self, job, result):
        tag, parent = job["tag"], job["parent"]
        work = self.ctx.work(tag)
        if not work.is_dir():
            return {"ok": False, "refused": "no_candidate"}
        bad = helper_refusal(self.spec, work, digest.cand_dir(self.run_dir, parent))
        if bad:
            return {"ok": False, "refused": bad[0], "detail": bad[1]}
        h = proposer.read_hypothesis(work)
        hyp = work / proposer.HYPOTHESIS_FILE
        a = argparse.Namespace(**vars(self.ns), tag=tag, parent=parent, hypothesis_file=str(hyp) if h else None,
                               small_edit_justification=None, over_budget=None, verb="propose")
        try:
            rc, out = act.propose(a, self.ctx)
        except act.Refused as e:
            msg = str(e)
            why = "duplicate" if "duplicate candidate" in msg else ("pregate" if "pregate" in msg else "hypothesis")
            return {"ok": False, "refused": why, "detail": msg[:300]}
        parents = [parent] if job["kind"] == "propose" else list(job.get("parents") or [parent])
        return {"ok": True, "hash": self.cap_hash(tag), "parents": parents, "hypothesis_id": out.get("hypothesis_id")}

    def node_event(self, tag, status, **kw):
        parents = kw.pop("parents", None)
        graph.append_node(self.run_dir, node_id=tag, parents=parents, status=status, **kw)

    def commit_accept(self, tag, evidence):
        sr = harness.split_result_from_rollouts(self.run_dir, tag, "val")
        why = "the conductor's one-shot proposer writes hypothesis.json only; no agent session keeps a journal or ranked list"
        extra = ["--val", str(sr.reward if sr.per_task else 0.0), "--missing-handover-justification", why,
                 "--missing-ranked-issues-justification", why, "--missing-diagnosis-justification", why]
        rc, res = act.commit(self.ctx, tag, "accept", "conductor: " + json.dumps(evidence, default=str)[:200], extra)
        if rc != 0:
            raise RuntimeError(f"commit.py refused the accept of {tag}: {res}")

    def commit_reject(self, tag, reason, evidence):
        a = argparse.Namespace(tag=tag, reason=str(reason), commit_extra=None)
        try:
            act.prune(a, self.ctx)
        except act.Refused as e:
            self.log("prune_refused", tag=tag, why=str(e)[:200])

    def discard(self, tag):
        shutil.rmtree(self.ctx.work(tag), ignore_errors=True)
        (self.root / "work" / f".parent_{tag}").unlink(missing_ok=True)

    def merge_build(self, a, b, tag, kind):
        ns = argparse.Namespace(tags=[a, b], tag=tag)
        try:
            rc, out = act.merge(ns, self.ctx)
        except act.Refused as e:
            return {"built": False, "error": str(e)}
        if out.get("stage") == "built":
            return {"built": True}
        return {"built": False, "conflicts": out.get("conflicts") or []}

    def wins(self, tags, base):
        import merge_n
        try:
            return merge_n.wins_from_run(self.run_dir, tags, base) or {}
        except Exception:  # noqa: BLE001
            return {}

    def related(self, a, b):
        g = CandidateGraph.load(self.run_dir)
        return g.is_descendant(a, b) or g.is_descendant(b, a)

    def recover(self):
        """Close dangling ``eval_start`` events now (the old engine noticed only after the host exited)."""
        import host
        d = host._dangling_eval(self.root)
        if d is not None:
            host._log_eval_abandoned(self.root, d)

    def finalize(self, champion):
        if self.cfg.p2 and champion != "seed" and not (self.root / "final_estimate.json").exists():
            est = self.ev.final_estimate(digest.cand_dir(self.run_dir, champion), digest.cand_dir(self.run_dir, "seed"))
            (self.root / "final_estimate.json").write_text(json.dumps(est, indent=1, default=str), encoding="utf-8")
        a = argparse.Namespace(**vars(self.ns), n_confirm=0, n_trials=0, seal_anyway=None, over_budget=None, verb="finalize")
        try:
            rc, out = act.finalize(a, self.ctx)
        except act.Refused as e:
            raise conductor.Refused(f"finalize blocked: {e}") from e
        return out

    def finalized(self):
        return (self.root / "final.json").exists() and RunDir.open(self.root).read_splits().test_used

    def log(self, event, **kw):
        kw.pop("kind", None)
        self.run_dir.log_event(event, **kw)

    # ---- P2
    @property
    def ev(self):
        if self._ev is None:
            from cap_evolve import evaluator
            from cap_evolve.check import load_adapter
            self._adapter = load_adapter(self.project)
            self._ev = evaluator.P2Evaluator(self._adapter, self.run_dir, self.cfg.p2,
                                             workers=int(self.spec.get("gateway_max_concurrency") or 0) or None)
        return self._ev

    def _round(self, rid):
        if rid not in self._rounds:
            self._rounds[rid] = self.ev.resume_round(rid)
        return self._rounds[rid]

    def _job(self, x):
        from cap_evolve.evaluator import Job
        return Job(**{**x, "ids": tuple(x["ids"])})

    def _dir(self, tag):
        return digest.cand_dir(self.run_dir, tag)

    def _workdir(self, tag):
        return self.ctx.work(tag)

    def _start_p2(self, job):
        from concurrent.futures import ThreadPoolExecutor
        from cap_evolve.rundir import BudgetExhausted
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=max(1, self.cfg.slots))
        rnd = self._round(job["round"])

        def work():
            try:
                if job.get("p2seq"):
                    v = rnd.sequential(job["p2seq"]["cid"])
                    return {"ok": True, "verdict": {"cid": v.cid, "status": v.status, "mean": v.mean, "z": v.z}}
                rnd.run_job(self._job(job["p2"]))
                return {"ok": True}
            except BudgetExhausted:
                return {"ok": True, "unfunded": True}
            except Exception as e:  # noqa: BLE001 - a failed job is retried by the conductor, bounded
                return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        self._threads[job["id"]] = self._pool.submit(work)
        return {"pid": os.getpid()}

    def _poll_p2(self, job):
        f = self._threads.get(job["id"])
        if f is None:
            return None
        return f.result() if f.done() else None


def conductor_jobs(root) -> list[dict]:
    try:
        return list(json.loads((Path(root) / "conductor.json").read_text(encoding="utf-8")).get("jobs", {}).values())
    except (OSError, ValueError):
        return []
