#!/usr/bin/env python3
"""One lane's worker: claim trials from the shared queue and run each through the parsec adapter.

Run by lane_worker.sh after it has built the lane and brought the stack up, so the
lane's environment (PARSEC_BENCH, PARSEC_LIVE_PROMPTS_DIR, PARSEC_LIVE_LOG,
PARSEC_SIM_TRACE, ...) is already exported and the shared adapter reads it exactly
as it does inside a `cap-evolve run`.

Exits when the queue has been empty for ``--idle-exit`` seconds (so a worker frees
its node while the optimizer thinks), when ``stop`` is requested, or after
``--max-infra-errors`` consecutive trials fail for a reason that is not the agent's
(a broken lane must not chew through the queue; the trial goes back to pending).
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "adapters"))

import adapter as parsec_adapter  # noqa: E402
from cap_evolve import Task  # noqa: E402
from lane_queue import LaneQueue  # noqa: E402

AGENT_FAILURE_PREFIX = "agent did not finish"


def is_infra_error(error: str | None) -> bool:
    """An error that says the lane, not the agent, failed (seeding, harbor, simulators)."""
    return bool(error) and not str(error).startswith(AGENT_FAILURE_PREFIX)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue", required=True, type=Path)
    ap.add_argument("--worker", default=os.environ.get("LSB_JOBID") or f"{socket.gethostname()}-{os.getpid()}")
    ap.add_argument("--idle-exit", type=float, default=600.0)
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--heartbeat", type=float, default=30.0)
    ap.add_argument("--max-infra-errors", type=int, default=3)
    args = ap.parse_args()

    q = LaneQueue(args.queue)
    state = {"state": "idle", "item": None, "done": 0}
    common = {"host": socket.gethostname(), "jobid": os.environ.get("LSB_JOBID"), "pid": os.getpid()}
    stop_beat = threading.Event()

    def beat():
        while not stop_beat.is_set():
            q.heartbeat(args.worker, **common, **state)
            stop_beat.wait(args.heartbeat)

    q.heartbeat(args.worker, **common, **state)          # live before the first claim
    threading.Thread(target=beat, daemon=True).start()

    adapter = parsec_adapter.Adapter()
    idle_since = time.monotonic()
    infra_errors = 0
    rc = 0
    try:
        while not q.stop_requested():
            item = q.claim(args.worker)
            if item is None:
                if time.monotonic() - idle_since >= args.idle_exit:
                    print(f"idle for {args.idle_exit:.0f}s; exiting", flush=True)
                    break
                time.sleep(args.poll)
                continue
            state.update(state="running", item=item["item"])
            print(f"[{time.strftime('%H:%M:%S')}] {item['item']} task={item['task_id']} seed={item['seed']}",
                  flush=True)
            # Module-level JOBS_ROOT is read at call time; the dispatcher picks it per trial so the
            # hidden stratum's transcripts land in the sealed tree.
            parsec_adapter.JOBS_ROOT = Path(item["jobs_root"])
            bundle = Path(item["bundle"])
            adapter.apply(bundle)
            task = Task(id=item["task_id"], metadata={"task_dir": item["task_dir"]})
            rollout = adapter.run_target(task, bundle, seed=int(item["seed"]))
            if is_infra_error(rollout.error):
                infra_errors += 1
                print(f"  infra error ({infra_errors}/{args.max_infra_errors}): {rollout.error}", flush=True)
                if infra_errors >= args.max_infra_errors:
                    q.release(item)
                    print("  too many infra errors in a row; giving this lane up", flush=True)
                    rc = 3
                    break
            else:
                infra_errors = 0
            q.complete(item, rollout.to_dict())
            state.update(state="idle", item=None, done=state["done"] + 1)
            idle_since = time.monotonic()
    finally:
        stop_beat.set()
        q.heartbeat(args.worker, **common, **{**state, "state": "exited"})
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
