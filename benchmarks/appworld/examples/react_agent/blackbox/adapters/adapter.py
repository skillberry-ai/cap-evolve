"""Project adapter — AppWorld through the Skillberry Store + Proxy-Agent (blackbox approach).

Wires cap-evolve to AppWorld for benchmarks/appworld/examples/react_agent/blackbox/README.md. Data,
the seal and scoring are the direct approach's (direct/adapters/adapter.py); what differs is how a
candidate reaches the agent.

``run_trials``, once per candidate:
  1. lints the candidate (``bb_lints``): a violation rejects it before any episode runs;
  2. deploys it (``appworld_tailoring.deploy``): its ``my_skill/SKILL.md``, plus the
     generated helper sentence, becomes the Skillberry Store's only skill, and the Proxy-Agent is
     restarted bound to it;
  3. builds the candidate's tools (``tools/helpers.py`` + ``tools/api_notes.json``) into the
     (remote) REPL code (``appworld_tailoring.repl_code``);
  4. runs the episodes, ``AW_WORKERS`` at a time.

``_episode``, once per trial:
  * starts the trial's own AppWorld environment server, the remote REPL
    (``appworld_tailoring.start_env_server``;
  * runs AppWorld's STOCK ReAct agent in a subprocess (``aw_bb_agent.py``), with a spec holding the
    task, the skillberry-context headers (a per-episode ``env_id``, the history-start marker and the
    task's supervisor), the server's URL and the remote REPL code, which the worker runs before step runs;
  * stops the server and disconnects the episode from the proxy, however the trial ended; an
    infrastructure failure (the server, the worker, the time cap) is retried ``AW_INFRA_RETRIES``
    times;
  * keeps the gold-free record as the rollout, and writes the agent's own messages to
    ``<run>/native_sims/<candidate>/<split>/`` (never into the rollout).

``score`` is the direct approach's: 1.0 iff AppWorld's evaluation passes every requirement, feedback
tier F1, never the gold answer or the failure ``trace``.

Seal: an id outside train ∪ dev runs only with ``AW_ALLOW_SEALED=final-eval-only``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import appworld_tailoring as tailoring  # noqa: E402
import aw_agent  # noqa: E402  (the direct approach's harness; stdlib-only at import)
import bb_lints  # noqa: E402

HERE = Path(__file__).resolve().parent
EVAL = Path(os.environ.get("AW_EVAL", "/tmp/aw_eval"))
ROOT_OPT = EVAL / "root_opt"
SEAL_VALUE = "final-eval-only"
EPISODE_TIMEOUT_S = int(os.environ.get("AW_EPISODE_TIMEOUT", "1800"))
MAX_STEPS = 50


def _appworld_root() -> Path:
    return Path(os.environ.get("AW_APPWORLD_ROOT", str(ROOT_OPT)))


def _client_prompt() -> Path:
    """AppWorld's own stock ReAct prompt: the benchmark's file, sent unchanged by the client."""
    return Path(os.environ.get("AW_CLIENT_PROMPT")
                or EVAL / "appworld" / "experiments" / "prompts" / "react_code_agent" / "instructions.txt")


def _wait_readable(path: Path, timeout_s: float = 60.0) -> None:
    t0 = time.time()
    while not os.access(path, os.R_OK | os.X_OK) and time.time() - t0 < timeout_s:
        time.sleep(1)


def _split_ids(name: str, root: Path | None = None) -> list[str]:
    root = root or ROOT_OPT
    _wait_readable(root)
    return [x for x in (root / "data" / "datasets" / f"{name}.txt").read_text().split() if x]


@lru_cache(maxsize=1)
def _search_ids_cached() -> tuple[str, ...]:
    return tuple(_split_ids("train") + _split_ids("dev"))


def _search_ids() -> list[str]:
    return list(_search_ids_cached())


@lru_cache(maxsize=None)
def _task_cached(tid: str, root: str) -> Task:
    return _task(tid, Path(root))


def _task(tid: str, root: Path) -> Task:
    spec = json.loads((root / "data" / "tasks" / tid / "specs.json").read_text())
    sup = spec.get("supervisor") or {}
    return Task(id=tid, input={"instruction": spec["instruction"],
                               "supervisor": f"{sup.get('first_name', '')} {sup.get('last_name', '')}".strip()})


def _supervisor(tid: str, root: Path) -> dict:
    """The task's supervisor (name, email, phone): the template values the proxy renders SKILL.md with."""
    return json.loads((root / "data" / "tasks" / tid / "specs.json").read_text()).get("supervisor") or {}


class _Progress:
    """Appends ``UTC | trial | phase | detail`` lines to AW_PROGRESS_LOG every few episodes."""

    def __init__(self, total: int):
        self.path = os.environ.get("AW_PROGRESS_LOG")
        self.trial = os.environ.get("AW_TRIAL", "blackbox")
        self.phase = os.environ.get("AW_PHASE", "eval")
        self.total, self.done, self.passed, self.errors = total, 0, 0, 0
        self.lock = threading.Lock()
        self.every = max(1, total // 10)
        self.log(f"start {total} episodes")

    def log(self, detail: str) -> None:
        if not self.path:
            return
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(self.path, "a") as f:
            f.write(f"{ts} | {self.trial} | {self.phase} | {detail}\n")

    def bump(self, rollout: Rollout) -> None:
        with self.lock:
            self.done += 1
            if rollout.error:
                self.errors += 1
            elif rollout.metadata.get("success"):
                self.passed += 1
            if self.done % self.every == 0 or self.done == self.total:
                self.log(f"{self.done}/{self.total} episodes, passed {self.passed}, infra errors {self.errors}")


def _native_sims_enabled() -> bool:
    """Whether to keep each episode's own ReAct message list (default: yes).
    Opt out with CAPEVOLVE_NATIVE_SIMS=0, as CI does."""
    return str(os.environ.get("CAPEVOLVE_NATIVE_SIMS", "")).strip().lower() not in {"0", "false", "no", "off"}


def _split_of(ctx: Path, task_ids: list[str]) -> str:
    """Which split this batch is, from the run's own splits.json (run_trials is not told).
    Ties resolve to val, the split the optimizer reads."""
    try:
        splits = json.loads((ctx.parent.parent / "splits.json").read_text(encoding="utf-8"))
        want = set(task_ids)
        for name in ("val", "train", "test"):
            ids = {str(i) for i in (splits.get(name) or [])}
            if ids and want <= ids:
                return name
    except Exception:  # noqa: BLE001 — an unreadable splits.json must not break the eval
        pass
    return "eval"


def _native_dir(ctx: Path, task_ids: list[str]) -> Path | None:
    """``<run_dir>/native_sims/<tag>/<split>/``, or None when off or when
    ctx is not ``candidates/<tag>`` / ``work/<tag>``. Each episode writes ``<task>__t<trial>.json``
    there: AppWorld's ReAct agent's own message list (the stock prompt messages + every turn)."""
    if not _native_sims_enabled() or ctx.parent.name not in ("candidates", "work"):
        return None
    return ctx.parent.parent / "native_sims" / ctx.name / _split_of(ctx, task_ids)


def _write_native(path: Path, record: dict) -> Path | None:
    """Write one episode's record, never over an earlier one; returns the file written.

    The same ``<tag>/<split>/<task>__t<trial>`` can be scored twice in one run: when a task is in
    both val and test, the final test resolves to the same split as the baseline (ties go to val).
    The second record then gets ``__2``, the third ``__3``, and so on. Native traces are a
    convenience: never let writing one break the eval.
    """
    text = json.dumps(record, indent=1, ensure_ascii=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        for n in range(1, 1000):
            p = path if n == 1 else path.with_name(f"{path.stem}__{n}{path.suffix}")
            try:
                with open(p, "x", encoding="utf-8") as f:   # "x": fails if it exists, so nothing is replaced
                    f.write(text)
                return p
            except FileExistsError:
                continue
    except OSError:
        pass
    return None


class Adapter(CapabilityAdapter):
    # ---- data ------------------------------------------------------------------------------
    def tasks(self, split: str) -> list[Task]:
        if split == "test":
            return []
        if split not in ("train", "val", "all"):
            raise ValueError(f"unknown split {split!r}")
        return [_task_cached(t, str(ROOT_OPT)) for t in _search_ids()]

    def runner_model(self) -> str | None:
        return os.environ.get("AW_MODEL_NAME", tailoring.DEFAULT_MODEL_NAME)

    def trajectories(self, split, ctx=None):
        return None  # cap-evolve's per-rollout JSON is the (gold-free) trajectory store

    # ---- running ---------------------------------------------------------------------------
    def _check_seal(self, ids: list[str]) -> None:
        allowed = set(_search_ids())
        outside = [t for t in ids if t not in allowed]
        if outside and os.environ.get("AW_ALLOW_SEALED") != SEAL_VALUE:
            raise PermissionError(f"{len(outside)} task id(s) outside train ∪ dev are sealed; "
                                  f"only the final window may run them (AW_ALLOW_SEALED={SEAL_VALUE})")

    def _episode(self, task: Task, seed: int, root: Path, workdir: Path,
                 native_path: Path | None = None, repl_code: str = "") -> Rollout:
        retries = int(os.environ.get("AW_INFRA_RETRIES", "1"))
        supervisor = _supervisor(task.id, root)
        last_err = ""
        for attempt in range(retries + 1):
            ep = f"{task.id}__s{seed}__a{attempt}__{uuid.uuid4().hex[:8]}"
            env = aw_agent.worker_env(dict(os.environ), str(root))
            # The worker needs no model key (the proxy holds it). The allowlist passes OPENAI_API_KEY
            # through, and blackbox_env.load_env() may have put the repo's real key in this process.
            env["OPENAI_API_KEY"] = "unused"
            # The remote REPL: this trial's own AppWorld environment server (one world per server).
            port = None
            if tailoring.remote_repl_enabled():
                try:
                    port = tailoring.start_env_server(str(root), env)
                except Exception as e:  # noqa: BLE001 — infrastructure, retried like a crashed worker
                    last_err = f"remote REPL did not start: {type(e).__name__}: {e}"[:1500]
                    continue
            spec = {
                "task_id": task.id,
                "experiment_name": f"{os.environ.get('AW_EXPERIMENT', 'capevolve-blackbox')}/{ep}",
                "appworld_root": str(root),
                "random_seed": 100 + int(seed),
                "client_prompt": str(_client_prompt()),
                "spa_url": tailoring.spa_base_url(),
                "headers": tailoring.context_headers(env_id=f"aw-{ep}", task_id=task.id, supervisor=supervisor),
                "log_lm_calls": False,  # unpatched AppWorld logs request arguments; never enable here
                "remote_environment_url": tailoring.env_server_url(port) if port else None,
                # The candidate's tools as the direct approach's REPL code: the worker runs it with
                # world.execute before step 1, as direct does ("" when there is nothing to load).
                "repl_code": repl_code,
            }
            spec_path, out_path = workdir / f"{ep}.spec.json", workdir / f"{ep}.out.json"
            spec_path.write_text(json.dumps(spec))
            t0 = time.time()
            try:
                proc = subprocess.run([sys.executable, str(HERE / "aw_bb_agent.py"), str(spec_path), str(out_path)],
                                      env=env, capture_output=True, text=True, timeout=EPISODE_TIMEOUT_S,
                                      cwd=str(workdir))
                # stderr is never passed on: a crash during evaluate could print gold values.
                exc = aw_agent.redact_stderr(proc.stderr)
                rec = json.loads(out_path.read_text()) if out_path.is_file() else {
                    "infra_error": f"worker exited {proc.returncode} without output" + (f" ({exc})" if exc else "")}
            except subprocess.TimeoutExpired:
                rec = {"infra_error": f"episode wall cap {EPISODE_TIMEOUT_S}s exceeded"}
            finally:
                spec_path.unlink(missing_ok=True)
                out_path.unlink(missing_ok=True)
                # Trial end, whatever ended it: stop the remote REPL and free its memory and port.
                if port is not None:
                    tailoring.stop_env_server(port)
                if os.environ.get("AW_KEEP_OUTPUTS") != "1":
                    shutil.rmtree(root / "experiments" / "outputs" / spec["experiment_name"], ignore_errors=True)
            # Disconnect upon trial end, whatever ended it: the worker does it in its own finally, but a
            # worker killed at the wall cap or crashed never gets there, and the proxy would keep this
            # env_id's vMCP server and trajectory. Idempotent, so a second call is harmless.
            if not rec.get("disconnected"):
                rec["disconnected"] = tailoring.disconnect(spec["headers"], spa_url=spec["spa_url"])
                rec["disconnected_by"] = "adapter"
            native = rec.pop("native", None)    # never part of the rollout: it goes to native_sims/
            if native is not None and native_path is not None:
                _write_native(native_path, dict(native, seed=seed, attempt=attempt,
                                                termination=rec.get("termination")))
            if not rec.get("infra_error"):
                steps = rec.pop("steps", [])
                meta = dict(rec, seed=seed, attempt=attempt, cost_source="unpriced",
                            episode_seconds=round(time.time() - t0, 1))
                return Rollout(task_id=task.id, output=rec.get("termination"), trace=steps,
                               tokens=int(rec.get("prompt_tokens", 0)) + int(rec.get("completion_tokens", 0)),
                               cost_usd=0.0, metadata=meta)
            last_err = str(rec["infra_error"])[:1500]
        return Rollout(task_id=task.id, error=f"infrastructure: {last_err}",
                       metadata={"seed": seed, "cost_source": "unpriced", "infra_error": last_err})

    def run_trials(self, tasks, ctx, *, n_trials: int, base_seed: int):
        # The candidate is the seed folder (capability_path: seed_capability): my_skill/ + tools/.
        cdir = Path(ctx).resolve()
        tasks = list(tasks)
        self._check_seal([t.id for t in tasks])
        root = _appworld_root()
        _wait_readable(root)
        violations = bb_lints.lint_candidate(cdir)
        if violations:
            # Rejected before any rollout: no episode runs, every task scores 0 with the reason.
            meta = {"lint_reject": violations, "success": False, "cost_source": "unpriced"}
            return {t.id: [Rollout(task_id=t.id, output="lint_reject", trace=[], metadata=dict(meta))
                           for _ in range(n_trials)] for t in tasks}
        try:
            tailoring.deploy(cdir)
        except Exception as e:  # noqa: BLE001 — the store or proxy is down: infra, not the candidate
            err = f"infrastructure: could not deploy the candidate to the store/proxy: {type(e).__name__}: {e}"[:1500]
            return {t.id: [Rollout(task_id=t.id, error=err, metadata={"cost_source": "unpriced", "infra_error": err})
                           for _ in range(n_trials)] for t in tasks}
        repl_code = tailoring.repl_code(cdir)   # the same for every episode of this candidate
        workers = int(os.environ.get("AW_WORKERS", "24"))
        scratch = Path(os.environ.get("AW_SCRATCH", str(EVAL / "scratch")))
        scratch.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix="aw_bb_eps_", dir=scratch))
        jobs = [(t, k) for k in range(n_trials) for t in tasks]
        progress = _Progress(len(jobs))
        out: dict[str, list] = {t.id: [None] * n_trials for t in tasks}

        native = _native_dir(cdir, [t.id for t in tasks])

        def one(job):
            t, k = job
            r = self._episode(t, base_seed + k, root, workdir,
                              native / f"{t.id}__t{k}.json" if native else None, repl_code=repl_code)
            progress.bump(r)
            return t.id, k, r

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for tid, k, r in pool.map(one, jobs):
                    out[tid][k] = r
        finally:
            # The batch-end sweep: no remote REPL outlives its batch, even if a trial's own stop failed.
            tailoring.stop_all_env_servers()
        try:
            workdir.rmdir()
        except OSError:
            pass
        return out

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        return self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]

    # ---- scoring (the direct approach's) ----------------------------------------------------
    def score(self, task: Task, rollout: Rollout) -> Score:
        m = rollout.metadata or {}
        if rollout.error:
            return Score(task_id=task.id, reward=0.0, feedback=f"not measured ({rollout.error[:200]})",
                         raw={"errored": True})
        if m.get("lint_reject"):
            return Score(task_id=task.id, reward=0.0,
                         feedback="LINT_REJECT (candidate not run): " + "; ".join(m["lint_reject"]),
                         raw={"lint_reject": True})
        reward = 1.0 if m.get("success") else 0.0
        n, passed = int(m.get("num_tests", 0)), int(m.get("pass_count", 0))
        facts = (f"steps used {m.get('n_steps', 0)}/{MAX_STEPS}; complete_task called: "
                 f"{'yes' if m.get('complete_task_called') else 'no'}; API/execution errors: {m.get('api_errors', 0)}; "
                 f"termination: {m.get('termination')}")
        if reward == 1.0:
            fb = f"PASSED all {n} requirement checks. {facts}."
        else:
            reqs = m.get("failed_requirements") or []
            fb = (f"FAILED: {passed}/{n} requirement checks passed. Failed requirements: "
                  + " | ".join(r.strip() for r in reqs[:12])
                  + (f" | (+{len(reqs) - 12} more)" if len(reqs) > 12 else "")
                  + f". Collateral damage (changed state the task did not ask for): "
                  f"{'yes' if m.get('collateral_damage') else 'no'}. {facts}.")
        metrics = [
            {"name": "reward", "value": reward, "primary": True, "direction": "higher"},
            {"name": "steps", "value": float(m.get("n_steps", 0)), "primary": False, "direction": "lower"},
            {"name": "prompt_tokens", "value": float(m.get("prompt_tokens", 0)), "primary": False, "direction": "lower"},
            {"name": "completion_tokens", "value": float(m.get("completion_tokens", 0)), "primary": False,
             "direction": "lower"},
        ]
        return Score(task_id=task.id, reward=reward, feedback=fb, metrics=metrics,
                     raw={"pass_count": passed, "num_tests": n, "termination": m.get("termination")})
