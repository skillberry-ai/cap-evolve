#!/usr/bin/env python3
"""Dispatching adapter: cap-evolve's evaluations run in parallel on LSF lanes, everything else is stock.

cap-evolve asks an adapter with a ``run_trials`` hook for a whole batch at once
(``harness._evaluate_candidate``). This adapter answers by putting every
(task, trial) of the batch on a shared queue (``lane_queue.py``), keeping enough
lane workers alive (``lane_worker.sh``, one per node), and collecting their
results. A trial that comes back dead (the agent never finished) or broken (the
lane failed) is re-queued up to ``V6_MAX_ATTEMPTS`` times; whatever is still not a
real measurement after that returns as an error, which the gate drops rather
than scoring. The loop, gate, budgets and dashboard are cap-evolve's own.

Each trial itself runs inside a lane through the shared parsec adapter
(``examples/parsec/adapters/adapter.py``, ``PARSEC_BENCH=v6``), whose v6 profile has v5's
runtime and timeouts, so a v6 trial is measured exactly as a v5 one was.

Transcripts of tasks the optimizer may not see (the hidden stratum C, and test)
are written under ``V6_SEALED_JOBS_ROOT`` instead of the shared jobs tree, the same
convention cap-evolve uses for C's rollouts. ``V6_PUBLIC_TASKS`` names the tasks
whose transcripts may go to the shared tree (the feedback stratum F).

Environment:
  V6_QUEUE_ROOT          queue directory on GPFS (required)
  V6_PUBLIC_TASKS        file of task ids whose transcripts are public (unset = all public)
  V6_SEALED_JOBS_ROOT    where every other task's transcripts go (required with V6_PUBLIC_TASKS)
  V6_MAX_WORKERS         lane workers kept alive while a batch has work (default 15)
  V6_MAX_ATTEMPTS        tries per trial before it is returned as an error (default 3)
  V6_BATCH_TIMEOUT_SEC   give up on a batch's stragglers after this long (default 21600)
  V6_WORKER_IDLE_EXIT    a worker exits after this long with nothing to do (default 600)
  V6_LSF_QUEUE / V6_LSF_MEM / CCC_LOGS   bsub queue, memory and log dir
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("PARSEC_BENCH", "v6")

_V6_DIR = Path(__file__).resolve().parents[1]
_SHARED = _V6_DIR.parent / "adapters" / "adapter.py"
if str(_V6_DIR) not in sys.path:
    sys.path.insert(0, str(_V6_DIR))


def _load_shared():
    spec = importlib.util.spec_from_file_location("parsec_shared_adapter", _SHARED)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["parsec_shared_adapter"] = mod
    spec.loader.exec_module(mod)
    return mod


shared = _load_shared()

from cap_evolve import CapabilityAdapter, Rollout, Task  # noqa: E402
from lane_queue import LaneQueue  # noqa: E402

HEARTBEAT_STALE_SEC = 180.0
POLL_SEC = 10.0
ENSURE_EVERY_SEC = 60.0


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


class LsfWorkers:
    """Keeps lane workers alive on LSF: one node per worker, never a node already running our jobs."""

    # Hosts held by the `infusion` reservation, which `bhosts` does not show (same list as fan_out.sh).
    EXTRA_RESERVED = {"cccxc701", "cccxc702", "cccxc704", "cccxc707", "cccxc710", "cccxc711",
                      "cccxc535", "cccxc575"}

    def __init__(self, queue_root: Path):
        self.queue_root = queue_root
        self.lsf_queue = os.environ.get("V6_LSF_QUEUE", "normal")
        self.memory = os.environ.get("V6_LSF_MEM", "64G")
        self.logs = Path(os.environ.get("CCC_LOGS") or Path.home() / "ccc_logs")
        self.idle_exit = os.environ.get("V6_WORKER_IDLE_EXIT", "600")
        self.job_name = f"v6w_{queue_root.name}"
        self.script = _V6_DIR / "lane_worker.sh"

    def _run(self, *cmd) -> str:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout

    def active(self) -> list[tuple[str, str, str]]:
        """``(jobid, state, host)`` of this queue's workers that are pending or running."""
        out = []
        for line in self._run("bjobs", "-w", "-J", self.job_name, "-noheader").splitlines():
            f = line.split()
            if len(f) >= 3 and f[2] in ("PEND", "RUN"):
                host = f[5].split("*")[-1] if f[2] == "RUN" and len(f) > 5 else ""
                out.append((f[0], f[2], host))
        return out

    def _free_hosts(self, pinned: set) -> list[str]:
        ok = [ln.split()[0] for ln in self._run("bhosts").splitlines()[1:] if len(ln.split()) > 1
              and ln.split()[1] == "ok"]
        busy = {ln.split()[5].split("*")[-1] for ln in self._run("bjobs", "-u", os.environ.get("USER", ""),
                                                                    "-r", "-w").splitlines()[1:]
                if len(ln.split()) > 5}
        reserved_blob = self._run("brsvs", "-w")

        def reserved(h):
            m = re.fullmatch(r"cccxc(\d{3})", h)
            return ((m and 600 <= int(m.group(1)) <= 630) or h in self.EXTRA_RESERVED
                    or re.search(rf"\b{re.escape(h)}\b", reserved_blob) is not None)

        return [h for h in ok if h not in busy and h not in pinned and not reserved(h)]

    def ensure(self, want: int) -> int:
        """Submit workers until ``want`` are pending or running; returns how many were submitted."""
        have = self.active()
        need = want - len(have)
        if need <= 0:
            return 0
        pinned = set(self._pinned_hosts())
        hosts = self._free_hosts(pinned)[:need]
        self.logs.mkdir(parents=True, exist_ok=True)
        submitted = 0
        for h in hosts:
            out = self._run("bsub", "-q", self.lsf_queue, "-M", self.memory, "-n", "1", "-m", h,
                            "-J", self.job_name, "-oo", str(self.logs / "%J.stdout"),
                            "-eo", str(self.logs / "%J.stderr"),
                            "bash", str(self.script), "--queue", str(self.queue_root),
                            "--idle-exit", str(self.idle_exit))
            m = re.search(r"Job <(\d+)>", out)
            if m:
                self._record_pin(m.group(1), h)
                submitted += 1
        return submitted

    # Pending workers are pinned with -m but do not show a host in bjobs yet; remember the pins so the
    # next ensure() does not pick the same node for a second worker.
    def _pins_file(self) -> Path:
        return self.queue_root / "worker_pins.tsv"

    def _record_pin(self, jobid: str, host: str) -> None:
        with self._pins_file().open("a", encoding="utf-8") as f:
            f.write(f"{jobid}\t{host}\n")

    def _pinned_hosts(self) -> list[str]:
        try:
            pins = dict(ln.split("\t") for ln in self._pins_file().read_text().splitlines() if "\t" in ln)
        except OSError:
            return []
        live = {j for j, _, _ in self.active()}
        return [h for j, h in pins.items() if j in live]


class Adapter(CapabilityAdapter):
    def __init__(self, *, queue: LaneQueue | None = None, workers=None) -> None:
        root = os.environ.get("V6_QUEUE_ROOT")
        if queue is None and not root:
            raise RuntimeError("V6_QUEUE_ROOT is required: the queue directory the lane workers read")
        self.queue = queue or LaneQueue(Path(root))
        self.workers = workers or LsfWorkers(self.queue.root)
        self.max_workers = _env_int("V6_MAX_WORKERS", 15)
        self.max_attempts = _env_int("V6_MAX_ATTEMPTS", 3)
        self.batch_timeout = float(os.environ.get("V6_BATCH_TIMEOUT_SEC") or 6 * 3600)
        public = os.environ.get("V6_PUBLIC_TASKS")
        self.public = (None if not public else
                       {ln.strip() for ln in Path(public).read_text().splitlines() if ln.strip()})
        sealed = os.environ.get("V6_SEALED_JOBS_ROOT")
        if self.public is not None and not sealed:
            raise RuntimeError("V6_SEALED_JOBS_ROOT is required when V6_PUBLIC_TASKS is set")
        self.sealed_jobs = Path(sealed) if sealed else None
        self._shared = None

    def _shared_adapter(self):
        if self._shared is None:
            self._shared = shared.Adapter()
        return self._shared

    # ---- the contract cap-evolve calls -------------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        return self._shared_adapter().tasks(split)

    def score(self, task: Task, rollout: Rollout):
        return self._shared_adapter().score(task, rollout)

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        orch = Path(candidate_dir) / "orchestrator.md"
        if orch.exists() and orch.stat().st_size < shared.MIN_ORCHESTRATOR_BYTES:
            raise ValueError(f"refusing to evaluate candidate: {orch} is truncated/placeholder content")

    @contextmanager
    def live(self, candidate_dir: Path):
        # Nothing shared is mutated here: each lane installs the bundle into its own prompts dir.
        self.apply(candidate_dir)
        yield candidate_dir

    def trajectories(self, split: str, ctx=None):
        return None             # the per-tag rollout copy is what the optimizer should read

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        return self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]

    def run_trials(self, tasks, ctx, *, n_trials: int = 1, base_seed: int = 0) -> dict:
        bundle = self.queue.snapshot_bundle(Path(ctx))
        batch = uuid.uuid4().hex[:10]
        planned = {}
        for t in tasks:
            for k in range(n_trials):
                planned[(t.id, k)] = {"batch": batch, "task_id": t.id, "task_dir": t.metadata["task_dir"],
                                      "bundle": str(bundle), "seed": base_seed + k, "trial": k,
                                      "jobs_root": str(self._jobs_root(t.id))}
        results = self._dispatch(planned)
        return {t.id: [results[(t.id, k)] for k in range(n_trials)] for t in tasks}

    # ---- internals -----------------------------------------------------------------------------------

    def _jobs_root(self, task_id: str) -> Path:
        if self.public is None or task_id in self.public:
            return shared.JOBS_ROOT
        return self.sealed_jobs

    @staticmethod
    def _item_id(base: dict, attempt: int) -> str:
        return f"{base['batch']}.{base['task_id']}.t{base['trial']}.a{attempt}"

    def _dispatch(self, planned: dict) -> dict:
        outstanding = {}
        for key, base in planned.items():
            iid = self._item_id(base, 1)
            self.queue.enqueue({**base, "item": iid, "attempt": 1})
            outstanding[iid] = (key, base, 1)
        self.queue.clear_stop()
        results: dict = {}
        deadline = time.monotonic() + self.batch_timeout
        next_ensure = 0.0
        while outstanding and time.monotonic() < deadline:
            for iid, (key, base, attempt) in list(outstanding.items()):
                rec = self.queue.result(iid)
                if rec is None:
                    continue
                del outstanding[iid]
                rollout = Rollout.from_dict(rec["rollout"])
                rollout.metadata = {**(rollout.metadata or {}), "dispatch": {
                    "attempt": attempt, "worker": rec["item"].get("worker"), "item": iid}}
                if rollout.error and attempt < self.max_attempts:
                    nid = self._item_id(base, attempt + 1)
                    self.queue.enqueue({**base, "item": nid, "attempt": attempt + 1})
                    outstanding[nid] = (key, base, attempt + 1)
                else:
                    results[key] = rollout
            self.queue.requeue_stale(HEARTBEAT_STALE_SEC)
            if outstanding and time.monotonic() >= next_ensure:
                self.workers.ensure(min(self.max_workers, len(outstanding)))
                next_ensure = time.monotonic() + ENSURE_EVERY_SEC
            if outstanding:
                time.sleep(POLL_SEC)
        for iid, (key, _, attempt) in outstanding.items():
            self.queue.cancel(iid)
            results[key] = Rollout(task_id=key[0], error=f"dispatch: no result within {self.batch_timeout:.0f}s",
                                   metadata={"dispatch": {"attempt": attempt, "item": iid}})
        return results
