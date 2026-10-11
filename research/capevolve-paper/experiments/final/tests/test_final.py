"""stdlib unittest for the final-evaluation machinery.  Run:  python3 -I -m unittest discover -s experiments/final/tests   (from research/capevolve-paper)"""
import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import fe_common as C  # noqa: E402
import reconstruct as R  # noqa: E402
import run_final as RF  # noqa: E402
import order as O  # noqa: E402
import bstar as B  # noqa: E402


def ev(event, cid, idx, val=None, split="val", **kw):
    d = {"event": event, "candidate_id": cid, "rollout_index": idx, "artifact_dir": "/x/" + cid, "sha256": "h" + cid}
    if val is not None:
        d["score"] = {"value": val, "split": split}
    d.update(kw)
    return d


PINNED = 1556853023238011366
CTX = {"full_n": 40, "limit_is_finite": True, "suite": "A"}


class TestRng(unittest.TestCase):
    def test_stable_vector(self):
        # pinned: the order permutation must not change across Python versions or edits
        self.assertEqual(O.HashRng(20261013, "A|order|primary").u32(), PINNED)


class TestBstar(unittest.TestCase):
    def test_floor(self):
        self.assertEqual(B.floor_step(199), 200)
        self.assertEqual(B.floor_step(36), 200)
        self.assertEqual(B.floor_step(263), 250)
        self.assertEqual(B.floor_step(600), 600)


class TestRules(unittest.TestCase):
    def test_gepa_argmax_tie_earliest_and_limit(self):
        evs = [ev("created", "c0", 0), ev("evaluated", "c0", 40, 0.5, n_tasks=40), ev("evaluated", "c1", 100, 0.7, n_tasks=40),
               ev("evaluated", "c2", 150, 0.7, n_tasks=40), ev("evaluated", "m", 120, 0.99, split="train-minibatch", n_tasks=3)]
        s = R.rule_gepa("/nonexistent", evs, 120, CTX)
        self.assertEqual(s["candidate_id"], "c1")
        s = R.rule_gepa("/nonexistent", evs, 99, CTX)
        self.assertEqual(s["candidate_id"], "c0")
        s = R.rule_gepa("/nonexistent", evs, R.INF, dict(CTX, limit_is_finite=False))
        self.assertEqual(s["candidate_id"], "c1")          # tie -> earliest

    def test_gepa_straddle_excluded(self):
        e = ev("evaluated", "c1", 130, 0.9, n_tasks=40, start_rollout_index=110)
        s = R.rule_gepa("/n", [ev("created", "c0", 0), ev("evaluated", "c0", 40, 0.5, n_tasks=40), e], 120, CTX)
        self.assertEqual(s["candidate_id"], "c0")

    def test_capevolve_last_accepted(self):
        evs = [ev("created", "seed", 0), ev("accepted", "cand_1", 100, 0.6), ev("rejected", "cand_2", 130, 0.5), ev("accepted", "cand_3", 260, 0.7)]
        self.assertEqual(R.rule_capevolve("/n", evs, 250, CTX)["candidate_id"], "cand_1")
        self.assertEqual(R.rule_capevolve("/n", evs, 50, CTX)["candidate_id"], "seed")
        self.assertTrue(R.rule_capevolve("/n", evs, 50, CTX)["fallback_seed"])

    def test_mipro_ignores_minibatch(self):
        evs = [ev("created", "d", 0), ev("evaluated", "d", 40, split="val", score={"split": "val", "kind": "full", "value_pct": 50.0}),
               ev("evaluated", "m", 60, split="val", score={"split": "val", "kind": "minibatch", "value_pct": 99.0}),
               ev("evaluated", "f", 90, split="val", score={"split": "val", "kind": "full", "value_pct": 60.0})]
        self.assertEqual(R.rule_mipro("/n", evs, 100, CTX)["candidate_id"], "f")
        self.assertEqual(R.rule_mipro("/n", evs, 70, CTX)["candidate_id"], "d")

    def test_evoskill_frontier_best(self):
        evs = [ev("created", "base", 0), ev("evaluated", "base", 40, 0.5), ev("evaluated", "b", 80, 0.6), ev("evaluated", "c", 120, 0.6)]
        s = R.rule_evoskill("/n", evs, 200, CTX)
        self.assertEqual(s["candidate_id"], "c")         # tie -> larger tag index (alphabetical), flagged partial
        self.assertEqual(s["status"], "partial")
        self.assertEqual(R.rule_evoskill("/n", evs, 100, CTX)["candidate_id"], "b")

    def test_wikiskill_strict(self):
        evs = [ev("created", "S0", 40), ev("evaluated", "S0", 40, 0.5), ev("evaluated", "S1", 90, 0.5), ev("evaluated", "S2", 140, 0.6)]
        self.assertEqual(R.rule_wikiskill("/n", evs, 100, CTX)["candidate_id"], "S0")
        self.assertEqual(R.rule_wikiskill("/n", evs, 200, CTX)["candidate_id"], "S2")

    def test_metaharness_skips_incomplete(self):
        evs = [ev("created", "seed", 0), ev("evaluated", "seed", 120, 0.6, incomplete=False), ev("evaluated", "x", 150, 0.9, incomplete=True)]
        self.assertEqual(R.rule_metaharness("/n", evs, 200, CTX)["candidate_id"], "seed")

    def test_ace_impossible_without_eval(self):
        s = R.rule_ace("/n", [ev("created", "e1", 10)], 50, CTX)
        self.assertEqual(s["status"], "impossible")


class TestOrder(unittest.TestCase):
    def test_deterministic_permutation(self):
        a = O.HashRng(1, "x").shuffle(list(range(50)))
        b = O.HashRng(1, "x").shuffle(list(range(50)))
        c = O.HashRng(1, "y").shuffle(list(range(50)))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(sorted(a), list(range(50)))

    def test_trial_seed_common_random_numbers(self):
        self.assertEqual(O.trial_seed("A", "t1", 0), O.trial_seed("A", "t1", 0))
        self.assertNotEqual(O.trial_seed("A", "t1", 0), O.trial_seed("A", "t1", 1))


def job(i, arm="hc", seed=0, task="t1", trial=0, mode="B", also_end=False):
    return {"type": "job", "job_id": "A|%s|s%d|%s|%s|t%d" % (arm, seed, task, mode, trial), "suite": "A", "arm": arm, "arm_label": arm, "seed": seed, "task": task,
            "family": "f" + task, "trial": trial, "mode": mode, "trial_seed": 100 + i, "tag": "tag:x", "also_end": also_end}


class TestFinalTaskLoading(unittest.TestCase):
    def test_final_b_reads_sealed_test_from_splits_file(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "protocol").mkdir()
        (tmp / "protocol" / "tau_retail_splits.json").write_text(json.dumps({"opt": ["1"], "sel": ["2"], "sealed_test": ["90", "91", "92"]}))
        old = O.WT_TAU
        try:
            O.WT_TAU = tmp
            tasks, kind, sha = O.load_tasks("B", "final", 2, O.HashRng(1, "x"))
        finally:
            O.WT_TAU = old
        self.assertEqual((kind, [t["id"] for t in tasks]), ("final", ["90", "91", "92"]))

    def test_final_a_needs_the_draw(self):
        old = O.FINAL_A_TASKS
        try:
            O.FINAL_A_TASKS = Path(tempfile.mkdtemp()) / "missing.json"
            with self.assertRaises(SystemExit):
                O.load_tasks("A", "final", 2, O.HashRng(1, "x"))
        finally:
            O.FINAL_A_TASKS = old


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cm = C.collect_metrics()

    def fake_attempts(self, results):
        it = iter(results)

        def fake(job, attempt, root, cm, py, hang_s):
            res = next(it)
            cls, rule = RF.classify(res, cm)
            return {"type": "attempt", "job_id": job["job_id"], "attempt": attempt, "suite": "A", "arm": job["arm_label"], "seed": job["seed"], "task": job["task"],
                    "family": job["family"], "trial": job["trial"], "mode": job["mode"], "trial_seed": 1, "t_spawn": 1.0, "t_start": 1.0, "t_end": 2.0,
                    "reward": res.get("reward"), "reward_as_saved": res.get("reward"), "error_class": cls, "error_rule": rule, "error_text": res.get("error") or "",
                    "hang": bool(res.get("hang")), "worker_ok": res.get("worker_ok"), "tag": "tag:x", "attempt_dir": "/n"}
        return fake

    def test_infra_retry_then_done_and_missing(self):
        infra = {"worker_ok": True, "error": "Connection reset by peer 502", "error_kind_adapter": "infra", "reward": 0.0}
        ok = {"worker_ok": True, "error": None, "reward": 1.0}
        orig = RF.run_attempt
        try:
            RF.run_attempt = self.fake_attempts([infra, infra, ok])
            st = RF.Store(self.tmp)
            RF.execute_job(job(0), st, self.cm, "py", log=lambda s: None)
            t = st.terminal("A|hc|s0|t1|B|t0")
            self.assertEqual(t["final_status"], "done")
            self.assertEqual(len(st.records("A|hc|s0|t1|B|t0")), 3)
            RF.run_attempt = self.fake_attempts([infra] * 4)
            RF.execute_job(job(1, task="t2"), st, self.cm, "py", log=lambda s: None)
            self.assertEqual(st.terminal("A|hc|s0|t2|B|t0")["final_status"], "missing")
            hang = {"worker_ok": True, "error": "watchdog", "error_kind_adapter": "infra", "reward": 0.0, "hang": True}
            RF.run_attempt = self.fake_attempts([hang, hang])
            RF.execute_job(job(2, task="t3"), st, self.cm, "py", log=lambda s: None)
            self.assertEqual(st.terminal("A|hc|s0|t3|B|t0")["final_status"], "missing")
            self.assertEqual(len(st.records("A|hc|s0|t3|B|t0")), 2)
            cand = {"worker_ok": True, "error": "task_template.md broke the placeholder contract", "error_kind_adapter": "infra", "reward": 0.0}
            RF.run_attempt = self.fake_attempts([cand])
            RF.execute_job(job(3, task="t4"), st, self.cm, "py", log=lambda s: None)
            t = st.terminal("A|hc|s0|t4|B|t0")
            self.assertEqual((t["final_status"], t["error_class"], t["reward"]), ("done", "candidate", 0.0))
        finally:
            RF.run_attempt = orig

    def test_idempotent_resume_and_contract_csv(self):
        orig = RF.run_attempt
        try:
            jobs = [job(i, arm=a, seed=s, task=t, trial=k) for i, (a, s, t, k) in enumerate(
                [(a, s, t, k) for a in ("hc", "seed") for s in ((0, 1) if a == "hc" else (0,)) for t in ("t1", "t2") for k in (0, 1)])]
            RF.run_attempt = self.fake_attempts([{"worker_ok": True, "error": None, "reward": float(i % 2)} for i in range(len(jobs))])
            st = RF.Store(self.tmp)
            for j in jobs:
                RF.execute_job(j, st, self.cm, "py", log=lambda s: None)
            RF.run_attempt = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not rerun finished jobs"))
            st2 = RF.Store(self.tmp)                       # fresh process view of the same file
            for j in jobs:
                RF.execute_job(j, st2, self.cm, "py", log=lambda s: None)
            out, rep = RF.aggregate("A", self.tmp, {}, jobs)
            rows = list(csv.DictReader(open(Path(self.tmp) / "results_long.csv")))
            self.assertEqual({(r["arm"], r["seed"], r["task"]) for r in rows}, {(a, str(s), t) for a in ("hc", "seed") for s in ((0, 1) if a == "hc" else (0,)) for t in ("t1", "t2")})
            for col in ("arm", "seed", "task", "reward", "family", "n_trials", "t_start", "t_end", "error_class", "error_text"):
                self.assertIn(col, rows[0])
            # the campaign's reader must parse it
            import importlib.util
            sp = importlib.util.spec_from_file_location("pcb", C.PAPER / "analysis/scripts/paired_cluster_bootstrap.py")
            pcb = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(pcb)
            Ya, Yb, cl, tasks = pcb.load_long(str(Path(self.tmp) / "results_long.csv"), "hc", "seed", "family")
            self.assertEqual((len(Ya), len(Ya[0]), len(Yb)), (2, 2, 1))
            self.assertEqual(cl, ["ft1", "ft2"])
        finally:
            RF.run_attempt = orig


if __name__ == "__main__":
    unittest.main()
