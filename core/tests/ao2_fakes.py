"""Fakes for the AO-2 conductor tests: a deterministic world, no model calls, no subprocess.

``FakeWorld`` is the part that survives a conductor "crash" (the filesystem and the processes it
started): the evidence ledger, the candidates, the running jobs. ``FakeBackend`` is the conductor's
view of it. A candidate is a set of GENES; a gene raises the pass probability of the tasks it fixes
and may lower others, so effects are real, repeatable and different per candidate. A rollout's
outcome is a seeded Bernoulli of (content hash, task, trial index) -- the same as the adapter in
test_promotion_rule_p.py, so the hill-climb reference run and the conductor see the same world.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

import conductor  # noqa: E402
import conductor_backend  # noqa: E402
from cap_evolve import RunDir, graph  # noqa: E402

TASKS = [f"t{i:02d}" for i in range(24)]


def u(*parts) -> float:
    return random.Random(":".join(map(str, parts))).random()


def p_of(genes: frozenset, task: str, base: float = 0.5) -> float:
    p = base
    for g in genes:
        kind, tasks, delta = g
        if task in tasks:
            p += delta
    return min(max(p, 0.02), 0.98)


def gene_for(tag: str, parent_genes: frozenset, quality: float | None = None):
    """Deterministic gene for a proposal tag: fixes ~6 tasks by +0.4 on average ``quality``."""
    r = random.Random(f"gene:{tag}")
    k = r.randint(9, 15)
    tasks = frozenset(r.sample(TASKS, k))
    q = r.choice([-0.3, 0.0, 0.45, 0.45]) if quality is None else quality
    return (tag, tasks, q)


class FakeWorld:
    def __init__(self, root: Path, *, base: float = 0.5, seed_trials: int = 1, delay=(1, 1), rng_seed=0,
                 quality=None, tokens_per_propose=1000, dup_every=0, salt=0, reward_fn=None):
        self.root = Path(root)
        self.base, self.delay, self.quality, self.salt = base, delay, quality, salt
        self.reward_fn = reward_fn          # (cands[tag], task, trial) -> reward; default = the gene model
        self.tokens_per_propose, self.dup_every = tokens_per_propose, dup_every
        self.rows: dict[tuple, float] = {}
        self.runs: dict[tuple, int] = {}          # how many times each cell was actually executed
        self.cands: dict[str, dict] = {"seed": {"genes": frozenset(), "parents": []}}
        self.jobs: dict[str, dict] = {}
        self.decisions: list[tuple] = []
        self.events: list[tuple] = []
        self.finalize_calls = 0
        self.rng = random.Random(rng_seed)
        self.n_proposed = 0
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_dir = RunDir.create(self.root / ".capevolve", ts="ao2")
        for t in TASKS:                                   # the host's baseline phase
            for k in range(seed_trials):
                self._row("seed", t, k)

    # ---- world mechanics
    def content(self, tag: str) -> str:
        if "cfg" in self.cands[tag]:
            return json.dumps(self.cands[tag]["cfg"], sort_keys=True)
        return json.dumps(sorted((g[0], sorted(g[1]), g[2]) for g in self.cands[tag]["genes"]))

    def hash(self, tag: str) -> str:
        return hashlib.sha256(self.content(tag).encode()).hexdigest()[:16]

    def _row(self, tag, task, trial):
        h = self.hash(tag)
        key = (h, task, trial)
        self.runs[key] = self.runs.get(key, 0) + 1
        if self.reward_fn:
            self.rows[key] = self.reward_fn(self.cands[tag], task, trial)
        else:
            self.rows[key] = 1.0 if u(self.salt, h, task, trial) < p_of(self.cands[tag]["genes"], task, self.base) else 0.0

    def crash(self):
        """SIGKILL of the conductor and every job it started: running chunks may have written
        part of their cells; a proposer is gone before it registered anything."""
        for j in list(self.jobs.values()):
            if j["kind"] == "eval":
                cells = [(t, k) for t in j["ids"] for k in range(*j["window"])]
                for t, k in cells[: self.rng.randint(0, len(cells))]:
                    if (self.hash(j["tag"]), t, k) not in self.rows:
                        self._row(j["tag"], t, k)
        self.jobs.clear()


class FakeBackend(conductor.Backend):
    def __init__(self, world: FakeWorld, ids=None, confirm=None):
        self.w = world
        self._ids = list(ids or TASKS)
        self._confirm = list(confirm or self._ids)
        self.started: list[dict] = []

    # ---- data
    def screen_ids(self): return self._ids
    def confirm_ids(self): return self._confirm
    def cap_hash(self, tag): return self.w.hash(tag) if tag in self.w.cands else None

    def missing(self, tag, ids, window):
        h, lo, hi = self.w.hash(tag), *window
        out = {}
        for t in map(str, ids):
            have = sum(1 for k in range(lo, hi) if (h, t, k) in self.w.rows)
            if have < hi - lo:
                out[t] = hi - lo - have
        return out

    def rewards(self, tag, ids, window):
        h, out = self.w.hash(tag), {}
        for (hh, t, k), r in sorted(self.w.rows.items()):
            if hh == h and t in set(ids) and (window is None or window[0] <= k < window[1]):
                out.setdefault(t, []).append(r)
        return out

    def spent_rollouts(self): return len(self.w.rows)
    def best_reward(self, tag):
        r = self.rewards(tag, self._ids, (0, 1000))
        return sum(sum(v) / len(v) for v in r.values()) / max(len(r), 1)

    # ---- jobs
    def start(self, job):
        self.started.append(dict(job))
        lo, hi = self.w.delay
        self.w.jobs[job["id"]] = {**job, "left": self.w.rng.randint(lo, hi)}
        if job["kind"] == "propose" and getattr(self.w, "hang_tokens", 0):
            self.w.jobs[job["id"]]["left"] = 10 ** 9           # a runaway proposer: never finishes, keeps burning
        return {"pid": 1000 + len(self.started)}

    def alive(self, job): return job["id"] in self.w.jobs

    def poll(self, job):
        rec = self.w.jobs.get(job["id"])
        if rec is None:
            return None
        rec["left"] -= 1
        if rec["left"] > 0:
            return None
        del self.w.jobs[job["id"]]
        if job["kind"] == "eval":
            n = 0
            for t in job["ids"]:
                for k in range(*job["window"]):
                    if (self.w.hash(job["tag"]), t, k) not in self.w.rows:
                        self.w._row(job["tag"], t, k)
                        n += 1
            return {"ok": True, "rollouts": n}
        if job["kind"] == "propose":
            tag, parent = job["tag"], job["parent"]
            self.w.n_proposed += 1
            if getattr(self.w, "script", None):              # recorded fixture: the n-th proposal is a fixed cfg
                self.w.cands[tag] = {"cfg": self.w.script[int(tag.split("_")[1]) - 1], "genes": frozenset(), "parents": [parent]}
                return {"ok": True, "tokens": self.w.tokens_per_propose}
            if self.w.dup_every and self.w.n_proposed % self.w.dup_every == 0:
                genes = self.w.cands[parent]["genes"]          # byte-identical to the parent
            else:
                genes = self.w.cands[parent]["genes"] | {gene_for(tag, self.w.cands[parent]["genes"], self.w.quality)}
            self.w.cands[tag] = {"genes": genes, "parents": [parent]}
            return {"ok": True, "tokens": self.w.tokens_per_propose}
        if job["kind"] == "merge":
            a, b = job["parents"]
            self.w.cands[job["tag"]] = {"genes": self.w.cands[a]["genes"] | self.w.cands[b]["genes"], "parents": [a, b]}
            return {"ok": True, "tokens": self.w.tokens_per_propose}
        return {"ok": True}

    def kill(self, job):
        if getattr(self.w, "unkillable", False):
            return False
        self.w.jobs.pop(job["id"], None)

    def running_tokens(self, job):
        return int(getattr(self.w, "hang_tokens", 0)) if job["id"] in self.w.jobs else 0

    # ---- graph
    def register(self, job, result):
        tag = job["tag"]
        if tag not in self.w.cands:
            return {"ok": False, "refused": "no_candidate"}
        return {"ok": True, "hash": self.w.hash(tag), "parents": self.w.cands[tag]["parents"]}

    def node_event(self, tag, status, **kw):
        parents = kw.pop("parents", None)
        self.w.events.append((tag, status, kw.get("stage")))
        graph.append_node(self.w.run_dir, node_id=tag, parents=parents, status=status, **{k: v for k, v in kw.items()})

    def commit_accept(self, tag, evidence): self.w.decisions.append((tag, "accept"))
    def commit_reject(self, tag, reason, evidence): self.w.decisions.append((tag, "reject"))

    def discard(self, tag): self.w.cands.pop(tag, None)

    def merge_build(self, a, b, tag, kind):
        ga, gb = self.w.cands[a]["genes"], self.w.cands[b]["genes"]
        if getattr(self.w, "merge_conflicts", False):
            return {"built": False, "conflicts": ["f.md"]}
        self.w.cands[tag] = {"genes": ga | gb, "parents": [a, b]}
        return {"built": True}

    def wins(self, tags, base):
        gb = self.w.cands[base]["genes"]
        out = {}
        for t in tags:
            g = self.w.cands[t]["genes"]
            out[t] = {x for x in TASKS if p_of(g, x, self.w.base) > p_of(gb, x, self.w.base) + 1e-9}
        return out

    def related(self, a, b):
        def anc(x, seen=None):
            seen = seen if seen is not None else set()
            for p in self.w.cands.get(x, {}).get("parents", []):
                if p not in seen:
                    seen.add(p)
                    anc(p, seen)
            return seen
        return a in anc(b) or b in anc(a)

    def finalize(self, champion):
        self.w.finalize_calls += 1
        (self.w.root / "final.json").write_text(json.dumps({"champion": champion}))
        return {"champion": champion}

    def finalized(self): return (self.w.root / "final.json").exists()
    def log(self, event, **kw): self.w.events.append((event, kw))


def make(tmp_path, *, spec=None, world_kw=None, ids=None, **cfg_kw):
    """(world, backend, cfg) with a deterministic spec; ``cfg_kw`` overrides Cfg fields."""
    w = FakeWorld(tmp_path, **(world_kw or {}))
    spec = {"promotion_n_conf": 4, "promotion_dmin": 0.02, "promotion_z_conf": 2.0, **(spec or {})}
    cfg = conductor.Cfg.from_spec(spec)
    for k, v in cfg_kw.items():
        setattr(cfg, k, v)
    cfg.tick_s = 0
    return w, FakeBackend(w, ids=ids), cfg


def run_to_done(w, be, cfg, *, crash_at=(), max_ticks=4000, clock=None):
    """Run a conductor to completion; at each tick number in ``crash_at`` the process 'dies' (world.crash,
    all in-memory conductor state dropped) and a new Conductor resumes from the files."""
    kw = {"clock": clock} if clock else {}
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None, **kw)
    for i in range(max_ticks):
        if i in crash_at:
            w.crash()
            c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None, **kw)
        if c.tick():
            return c
    raise AssertionError("conductor did not finish")


# ---- P2 mode: the REAL P2Evaluator on the seeded Bernoulli adapter (tests/p2_fakes.py) -------------

class P2Backend(conductor_backend.P2Port, conductor.Backend):
    """Conductor backend over a real run dir + cap_evolve.evaluator. Jobs run on a thread pool, so
    several candidates really evaluate in parallel; proposals are instant, scripted by effect size."""

    def __init__(self, tmp_path, effects, *, n=48, default=0.4, max_metric_calls=0, workers=4, params=None):
        from concurrent.futures import ThreadPoolExecutor
        from cap_evolve import evaluator, promotion
        from p2_fakes import make_run
        self.tmp, self.effects, self.default = Path(tmp_path), list(effects), default
        self.adapter, self.run_dir = make_run(self.tmp, n_train=n // 2, n_val=n // 2, default=default,
                                              max_metric_calls=max_metric_calls)
        self.params = params or promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 48, "p2_ctrl_m": 2})
        self.ev = evaluator.P2Evaluator(self.adapter, self.run_dir, self.params)
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.futs: dict = {}
        self._rounds: dict = {}
        self.dirs: dict = {"seed": self.run_dir.candidate_dir("seed")}
        self.decisions: list = []
        self.max_parallel = 0
        self.running = 0
        import threading
        self.lock = threading.Lock()

    def attach(self, other):
        """A 'restarted process': the same run dir and candidate dirs, no threads, no cached rounds."""
        import copy
        self.pool.shutdown(wait=True)
        n = P2Backend.__new__(P2Backend)
        n.__dict__.update(self.__dict__)
        from concurrent.futures import ThreadPoolExecutor
        n.pool, n.futs, n._rounds = ThreadPoolExecutor(max_workers=4), {}, {}
        return n

    def dir_of(self, tag): return self.dirs[tag]
    def _dir(self, tag): return self.dirs[tag]
    def _workdir(self, tag): return self.dirs[tag]
    def cap_hash(self, tag):
        from cap_evolve import eval_index
        return eval_index.cap_hash(self.dirs[tag]) if tag in self.dirs else None

    def screen_ids(self): return self.ev.feedback_ids()
    def confirm_ids(self): return self.ev.confirm_ids()
    def spent_rollouts(self): return self.run_dir.spent.metric_calls
    def reserved_rollouts(self): return self.run_dir.reserved_metric_calls()
    def remaining_rollouts(self): return self.run_dir.remaining_metric_calls()

    def _remember_round(self, rnd):
        self._rounds[rnd.round_id] = rnd

    def _round(self, rid):
        if rid not in self._rounds:
            self._rounds[rid] = self.ev.resume_round(rid)
        return self._rounds[rid]

    def _job(self, x):
        from cap_evolve.evaluator import Job
        return Job(**{**x, "ids": tuple(x["ids"])})

    # ---- jobs
    def start(self, job):
        if job["kind"] == "propose":
            i = int(job["tag"].split("_")[1]) - 1
            eff = self.effects[i % len(self.effects)]
            d = self.tmp / job["tag"]
            d.mkdir(exist_ok=True)
            (d / "cfg.json").write_text(json.dumps({"default": min(1.0, self.default + eff), "p": {}, "salt": i + 1}))
            self.dirs[job["tag"]] = d
            self.futs[job["id"]] = {"ok": True, "tokens": 1000}
            return {"pid": 1}
        rnd = self._round(job["round"])

        def work():
            from cap_evolve.rundir import BudgetExhausted
            with self.lock:
                self.running += 1
                self.max_parallel = max(self.max_parallel, self.running)
            try:
                if job.get("p2seq"):
                    v = rnd.sequential(job["p2seq"]["cid"])
                    return {"ok": True, "verdict": {"cid": v.cid, "status": v.status, "mean": v.mean, "z": v.z}}
                rnd.run_job(self._job(job["p2"]))
                return {"ok": True}
            except BudgetExhausted:
                return {"ok": True, "unfunded": True}
            finally:
                with self.lock:
                    self.running -= 1
        self.futs[job["id"]] = self.pool.submit(work)
        return {"pid": 1}

    def alive(self, job): return job["id"] in self.futs

    def poll(self, job):
        f = self.futs.get(job["id"])
        if f is None:
            return None
        if isinstance(f, dict):
            return f
        return f.result() if f.done() else None

    def kill(self, job): self.futs.pop(job["id"], None)

    # ---- graph
    def register(self, job, result):
        return {"ok": True, "hash": self.cap_hash(job["tag"]), "parents": [job["parent"]]}

    def node_event(self, tag, status, **kw):
        parents = kw.pop("parents", None)
        graph.append_node(self.run_dir, node_id=tag, parents=parents, status=status, **kw)

    def commit_accept(self, tag, evidence):
        self.decisions.append((tag, "accept"))
        self.run_dir.snapshot(tag, self.dirs[tag])
        self.run_dir.set_best(tag)

    def commit_reject(self, tag, reason, evidence): self.decisions.append((tag, "reject"))
    def finalize(self, champion):
        (self.run_dir.root / "final.json").write_text(json.dumps({"champion": champion}))
        return {"champion": champion}
    def finalized(self): return (self.run_dir.root / "final.json").exists()
    def log(self, event, **kw): self.run_dir.log_event(event, **kw)
    def best_reward(self, tag): return None
