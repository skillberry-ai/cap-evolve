"""The v6 lane queue and the dispatching adapter, with an in-process worker standing in for LSF."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

V6 = Path(__file__).resolve().parents[1] / "v6"
CORE = Path(__file__).resolve().parents[3] / "core"
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(V6))

from lane_queue import LaneQueue  # noqa: E402


def _load_dispatcher(tree: Path):
    """Import v6/adapters/adapter.py fresh against a throwaway v5 tree (both modules read env at import)."""
    env = {"PARSEC_BENCH": "v5", "PARSEC_V5N": str(tree), "PARSEC_JOBS_SUITE": "v6_test"}
    with patch.dict(os.environ, env):
        spec = importlib.util.spec_from_file_location(f"v6_dispatch_{id(tree)}", V6 / "adapters" / "adapter.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _bundle(root: Path, text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "orchestrator.md").write_text(text * 600)
    (root / "shared_context.md").write_text("ctx")
    return root


class FakeWorkers:
    """ensure() starts one in-process worker that scores trials with ``outcome(item) -> (reward, error)``."""

    def __init__(self, queue: LaneQueue, outcome):
        self.queue, self.outcome, self.started = queue, outcome, 0
        self.thread = None
        self.stop = threading.Event()

    def ensure(self, want: int) -> int:
        if self.thread is not None:
            return 0
        self.queue.heartbeat("w1", state="idle")

        def loop():
            while not self.stop.is_set():
                self.queue.heartbeat("w1", state="idle")
                item = self.queue.claim("w1")
                if item is None:
                    time.sleep(0.01)
                    continue
                reward, error = self.outcome(item)
                self.queue.complete(item, {"task_id": item["task_id"], "error": error,
                                           "metadata": {"trial_result": {"reward": reward},
                                                        "seed": item["seed"], "jobs_root": item["jobs_root"]}})

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()
        self.started += 1
        return 1


class TestLaneQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.q = LaneQueue(Path(self.tmp.name) / "q")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_trial_is_claimed_by_exactly_one_worker(self):
        for i in range(20):
            self.q.enqueue({"item": f"i{i}", "task_id": "t"})
        got: list = []
        lock = threading.Lock()

        crashed: list = []

        def drain(w):
            try:
                while (it := self.q.claim(w)) is not None:
                    with lock:
                        got.append(it["item"])
            except Exception as e:  # noqa: BLE001 — a crashing claimer is the failure under test
                crashed.append(e)

        threads = [threading.Thread(target=drain, args=(f"w{n}",)) for n in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(crashed, [])
        self.assertEqual(sorted(got), sorted(f"i{i}" for i in range(20)))

    def test_a_dead_workers_trials_go_back_to_pending_and_a_live_ones_do_not(self):
        self.q.enqueue({"item": "a", "task_id": "t"})
        self.q.enqueue({"item": "b", "task_id": "t"})
        self.q.heartbeat("live", state="running")
        self.q.claim("live")
        self.q.claim("dead")                      # never heartbeats
        moved = self.q.requeue_stale(stale_sec=60)
        self.assertEqual(len(moved), 1)
        self.assertEqual(self.q.counts(), {"pending": 1, "claimed": 1, "done": 0})

    def test_release_returns_the_trial_unchanged(self):
        self.q.enqueue({"item": "a", "task_id": "t", "seed": 3})
        it = self.q.claim("w")
        self.q.release(it)
        again = self.q.claim("w2")
        self.assertEqual((again["item"], again["seed"], again["worker"]), ("a", 3, "w2"))

    def test_cancel_only_withdraws_unclaimed_trials(self):
        self.q.enqueue({"item": "a", "task_id": "t"})
        self.q.enqueue({"item": "b", "task_id": "t"})
        claimed = self.q.claim("w")["item"]
        other = "b" if claimed == "a" else "a"
        self.assertFalse(self.q.cancel(claimed))
        self.assertTrue(self.q.cancel(other))

    def test_bundles_are_content_addressed(self):
        a = self.q.snapshot_bundle(_bundle(Path(self.tmp.name) / "c1", "x"))
        b = self.q.snapshot_bundle(_bundle(Path(self.tmp.name) / "c2", "x"))
        c = self.q.snapshot_bundle(_bundle(Path(self.tmp.name) / "c3", "y"))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue((a / "orchestrator.md").is_file())

    def test_worker_ids_may_not_contain_the_separator(self):
        with self.assertRaises(ValueError):
            self.q.claim("bad__id")


class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.tree = root / "v5tree"
        for t in ("a", "b"):
            (self.tree / "_run" / "tasks" / f"bench-v5-{t}").mkdir(parents=True)
        self.mod = _load_dispatcher(self.tree)
        self.queue = LaneQueue(root / "queue")
        self.cand = _bundle(root / "cand", "prompt")
        self.patches = [patch.object(self.mod, "POLL_SEC", 0.01)]
        [p.start() for p in self.patches]

    def tearDown(self):
        [p.stop() for p in self.patches]
        self.tmp.cleanup()

    def _adapter(self, outcome, env=None):
        workers = FakeWorkers(self.queue, outcome)
        self.addCleanup(workers.stop.set)
        with patch.dict(os.environ, {"V6_MAX_ATTEMPTS": "3", **(env or {})}):
            a = self.mod.Adapter(queue=self.queue, workers=workers)
        return a, workers

    def _tasks(self, a):
        return {t.id: t for t in a.tasks("all")}

    def test_returns_every_trial_in_order_with_its_seed(self):
        a, _ = self._adapter(lambda it: (0.5, None))
        t = self._tasks(a)
        out = a.run_trials([t["a"], t["b"]], self.cand, n_trials=3, base_seed=10)
        self.assertEqual(sorted(out), ["a", "b"])
        self.assertEqual([r.metadata["seed"] for r in out["a"]], [10, 11, 12])
        self.assertTrue(all(r.error is None for rs in out.values() for r in rs))
        self.assertEqual(a.score(t["a"], out["a"][0]).reward, 0.5)

    def test_a_dead_trial_is_retried_and_the_retry_is_what_is_returned(self):
        seen: dict = {}

        def outcome(it):
            n = seen[it["trial"]] = seen.get(it["trial"], 0) + 1
            return (0.0, "agent did not finish: AgentTimeoutError") if n == 1 else (0.8, None)

        a, _ = self._adapter(outcome)
        out = a.run_trials([self._tasks(a)["a"]], self.cand, n_trials=2)
        self.assertTrue(all(r.error is None for r in out["a"]))
        self.assertTrue(all(r.metadata["dispatch"]["attempt"] == 2 for r in out["a"]))

    def test_a_trial_dead_on_every_attempt_comes_back_as_an_error_not_a_score(self):
        a, _ = self._adapter(lambda it: (0.0, "agent did not finish: AgentTimeoutError"))
        out = a.run_trials([self._tasks(a)["a"]], self.cand, n_trials=1)
        r = out["a"][0]
        self.assertIn("did not finish", r.error)
        self.assertEqual(r.metadata["dispatch"]["attempt"], 3)

    def test_hidden_tasks_transcripts_go_to_the_sealed_tree(self):
        public = Path(self.tmp.name) / "public.txt"
        public.write_text("a\n")
        sealed = Path(self.tmp.name) / "sealed-jobs"
        a, _ = self._adapter(lambda it: (1.0, None),
                             env={"V6_PUBLIC_TASKS": str(public), "V6_SEALED_JOBS_ROOT": str(sealed)})
        t = self._tasks(a)
        out = a.run_trials([t["a"], t["b"]], self.cand, n_trials=1)
        self.assertEqual(out["a"][0].metadata["jobs_root"], str(self.mod.shared.JOBS_ROOT))
        self.assertEqual(out["b"][0].metadata["jobs_root"], str(sealed))

    def test_public_tasks_without_a_sealed_root_is_refused(self):
        public = Path(self.tmp.name) / "public.txt"
        public.write_text("a\n")
        with patch.dict(os.environ, {"V6_PUBLIC_TASKS": str(public)}):
            with self.assertRaises(RuntimeError):
                self.mod.Adapter(queue=self.queue, workers=object())

    def test_a_batch_that_times_out_returns_errors_and_withdraws_its_trials(self):
        class NoWorkers:
            def ensure(self, want):
                return 0
        with patch.dict(os.environ, {"V6_BATCH_TIMEOUT_SEC": "0.2"}):
            a = self.mod.Adapter(queue=self.queue, workers=NoWorkers())
        out = a.run_trials([self._tasks(a)["a"]], self.cand, n_trials=2)
        self.assertTrue(all("dispatch: no result" in r.error for r in out["a"]))
        self.assertEqual(self.queue.counts()["pending"], 0)


if __name__ == "__main__":
    unittest.main()
