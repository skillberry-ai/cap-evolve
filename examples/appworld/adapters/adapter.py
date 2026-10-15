"""Project adapter — AppWorld (official simplified ReAct code agent, gpt-oss-120b on RITS).

Wires cap-evolve to AppWorld for the example in examples/appworld/README.md:

  * ``tasks``      -> train and val are BOTH the union of the official ``train`` and ``dev`` ids
                      (147, rule S2), read from AppWorld's split files; ``test`` is ``[]``.
  * ``run_trials`` -> one subprocess per episode (``aw_agent.py``; AppWorld allows one live world
                      per process), ``AW_WORKERS`` at a time. A candidate that fails the lints
                      (README: Lints) is rejected (``lint_reject``) without running any episode.
  * ``run_target`` -> ``run_trials`` on one task.
  * ``score``      -> 1.0 iff AppWorld's evaluation passes every requirement; feedback tier F1
                      (failed requirement texts, collateral damage, complete_task called, steps,
                      API errors, termination). Never the gold answer or the failure ``trace``.

Seal: an id outside train ∪ dev runs only with ``AW_ALLOW_SEALED=final-eval-only`` (the final
window sets it, together with ``AW_APPWORLD_ROOT`` = root_full).
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

import lints  # noqa: E402

HERE = Path(__file__).resolve().parent
EVAL = Path(os.environ.get("AW_EVAL", "/tmp/aw_eval"))
ROOT_OPT = EVAL / "root_opt"
SEAL_VALUE = "final-eval-only"
EPISODE_TIMEOUT_S = int(os.environ.get("AW_EPISODE_TIMEOUT", "1800"))
MAX_STEPS = 50


def _appworld_root() -> Path:
    return Path(os.environ.get("AW_APPWORLD_ROOT", str(ROOT_OPT)))


def _wait_readable(path: Path, timeout_s: float = 60.0) -> None:
    """The cape-hc run locks root_opt while its optimizer runs (README: Isolation); wait it out."""
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


class _Progress:
    """Appends ``UTC | trial | phase | detail`` lines to AW_PROGRESS_LOG every few episodes."""

    def __init__(self, total: int):
        self.path = os.environ.get("AW_PROGRESS_LOG")
        self.trial = os.environ.get("AW_TRIAL", "cape-hc")
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


class Adapter(CapabilityAdapter):
    # ---- data ------------------------------------------------------------------------------
    def tasks(self, split: str) -> list[Task]:
        if split == "test":
            return []
        if split not in ("train", "val", "all"):
            raise ValueError(f"unknown split {split!r}")
        return [_task_cached(t, str(ROOT_OPT)) for t in _search_ids()]

    def runner_model(self) -> str | None:
        return "openai/gpt-oss-120b-a100"

    def trajectories(self, split, ctx=None):
        return None  # cap-evolve's per-rollout JSON is the (gold-free) trajectory store

    # ---- running ---------------------------------------------------------------------------
    def _check_seal(self, ids: list[str]) -> None:
        allowed = set(_search_ids())
        outside = [t for t in ids if t not in allowed]
        if outside and os.environ.get("AW_ALLOW_SEALED") != SEAL_VALUE:
            raise PermissionError(f"{len(outside)} task id(s) outside train ∪ dev are sealed; "
                                  f"only the final window may run them (AW_ALLOW_SEALED={SEAL_VALUE})")

    def _memory_block(self, cdir: Path, tid: str) -> str:
        pb = cdir / "memory" / "playbook.md"
        if pb.is_file() and pb.read_text(encoding="utf-8").strip():
            return pb.read_text(encoding="utf-8")
        rj = cdir / "memory" / "retrieval.json"
        if rj.is_file():
            return json.loads(rj.read_text(encoding="utf-8")).get(tid, "")
        return ""

    def _episode(self, task: Task, cdir: Path, seed: int, root: Path, workdir: Path,
                 random_seed: int | None = None) -> Rollout:
        retries = int(os.environ.get("AW_INFRA_RETRIES", "1"))
        last_err = ""
        for attempt in range(retries + 1):
            ep = f"{task.id}__s{seed}__a{attempt}__{uuid.uuid4().hex[:8]}"
            spec = {
                "task_id": task.id,
                "experiment_name": f"{os.environ.get('AW_EXPERIMENT', 'capevolve')}/{ep}",
                "candidate_dir": str(cdir),
                "appworld_root": str(root),
                "random_seed": int(random_seed) if random_seed is not None else 100 + int(seed),
                "memory_block": self._memory_block(cdir, task.id),
                "secrets_file": os.environ.get("AW_SECRETS_FILE", ""),
                "log_lm_calls": os.environ.get("AW_LOG_LM_CALLS") == "1",
            }
            spec_path, out_path = workdir / f"{ep}.spec.json", workdir / f"{ep}.out.json"
            spec_path.write_text(json.dumps(spec))
            env = {k: v for k, v in os.environ.items() if k != os.environ.get("AW_KEY_ENV", "RITS_API_KEY")}
            env["APPWORLD_ROOT"] = str(root)
            t0 = time.time()
            try:
                proc = subprocess.run([sys.executable, str(HERE / "aw_agent.py"), str(spec_path), str(out_path)],
                                      env=env, capture_output=True, text=True, timeout=EPISODE_TIMEOUT_S,
                                      cwd=str(workdir))
                rec = json.loads(out_path.read_text()) if out_path.is_file() else {
                    "infra_error": f"worker exited {proc.returncode} without output: {proc.stderr[-800:]}"}
            except subprocess.TimeoutExpired:
                rec = {"infra_error": f"episode wall cap {EPISODE_TIMEOUT_S}s exceeded"}
            finally:
                spec_path.unlink(missing_ok=True)
                out_path.unlink(missing_ok=True)
                # AppWorld's native output dir holds the evaluation report (gold traces) and the
                # full lm_calls log; the gold-free record above is all that is kept.
                if os.environ.get("AW_KEEP_OUTPUTS") != "1":
                    shutil.rmtree(root / "experiments" / "outputs" / spec["experiment_name"], ignore_errors=True)
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
        cdir = Path(ctx).resolve()  # workers run with cwd = a scratch dir
        tasks = list(tasks)
        self._check_seal([t.id for t in tasks])
        violations = lints.lint_candidate(cdir)
        if violations:
            # Rejected before any rollout: no episode runs, every task scores 0 with the reason.
            meta = {"lint_reject": violations, "success": False, "cost_source": "unpriced"}
            return {t.id: [Rollout(task_id=t.id, output="lint_reject", trace=[], metadata=dict(meta))
                           for _ in range(n_trials)] for t in tasks}
        root = _appworld_root()
        _wait_readable(root)
        workers = int(os.environ.get("AW_WORKERS", "24"))
        scratch = Path(os.environ.get("AW_SCRATCH", str(EVAL / "scratch")))
        scratch.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix="aw_eps_", dir=scratch))
        jobs = [(t, k) for k in range(n_trials) for t in tasks]
        progress = _Progress(len(jobs))
        out: dict[str, list] = {t.id: [None] * n_trials for t in tasks}

        def one(job):
            t, k = job
            r = self._episode(t, cdir, base_seed + k, root, workdir)
            progress.bump(r)
            return t.id, k, r

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for tid, k, r in pool.map(one, jobs):
                out[tid][k] = r
        try:
            workdir.rmdir()
        except OSError:
            pass
        return out

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        return self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]

    # ---- scoring ---------------------------------------------------------------------------
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
