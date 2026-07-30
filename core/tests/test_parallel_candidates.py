"""Worktree-isolated parallel candidate evaluation (#131).

The hazard list this file is written against — every item is one test:

  * ``parallel=N>1`` changes the SEARCH (breadth from one champion, not depth per
    accept) — proved with a non-idempotent optimizer against a monotone objective, and
    the old idempotent probe is pinned as a fixture artifact so the false "identical
    results" claim cannot come back;
  * every score a parallel run BANKS is still honestly gated — a sibling forked from a
    champion its peer superseded is rejected, never recorded as progress;
  * two concurrent candidates are hermetically isolated (neither sees the other's
    files) and get independent, correct scores;
  * ``events.jsonl`` never contains an interleaved or partial line under concurrent
    append load — every line parses strictly;
  * cost/token accounting is exact: ``Spent`` == sum of per-candidate spend;
  * the eval cache doesn't collide across candidates and doesn't lose writes;
  * the sealed test split is never touched by a worker, and one worker consuming the
    seal doesn't let another;
  * workspaces are cleaned up on normal exit, on exception, and on SIGINT;
  * a concurrency-unsafe adapter is downgraded to sequential, audibly.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cap_evolve import Budget, CapabilityAdapter, EvalCache, RunDir, Rollout, Score, Task, parallel
from cap_evolve import harness
from cap_evolve.splits import Splits, TestSealError

TASKS = [Task(id=f"t{i}", input=f"{i}+{i}", target=str(i + i)) for i in range(8)]


class CalcAdapter(CapabilityAdapter):
    """Deterministic toy adapter: the candidate's prompt.txt decides correctness.

    Hermetic by construction — ``run_target`` reads ONLY ``ctx`` (the candidate dir),
    so it uses the base class's pure ``live()``/``apply()`` and is parallel-safe.
    """

    def __init__(self, cost: float = 0.01, tokens: int = 7, sleep: float = 0.0):
        self.cost, self.tokens, self.sleep = cost, tokens, sleep

    def tasks(self, split: str) -> list[Task]:
        return list(TASKS)

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        if self.sleep:
            time.sleep(self.sleep)
        prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
        a, b = str(task.input).split("+")
        out = str(int(a) + int(b)) if "[CALC]" in prompt else "dunno"
        return Rollout(task_id=task.id, output=out, cost_usd=self.cost, tokens=self.tokens)

    def score(self, task: Task, rollout: Rollout) -> Score:
        ok = (rollout.output or "").strip() == str(task.target)
        return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                     feedback="correct" if ok else "wrong", trial_rewards=[1.0 if ok else 0.0])


class GlobalInjectAdapter(CalcAdapter):
    """Not concurrency-safe: overrides ``apply`` as a global inject."""

    LIVE = None

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        GlobalInjectAdapter.LIVE = Path(candidate_dir)


def _fresh_run(tmp_path: Path, name: str = "r", *, max_iterations: int = 4) -> tuple[RunDir, Path]:
    base = tmp_path / name
    rd = RunDir.create(base, ts="t", budget=Budget(max_iterations=max_iterations))
    ids = [t.id for t in TASKS]
    rd.write_splits(Splits(train=ids[:4], val=ids[4:7], test=ids[7:], seed=0))
    seed_dir = base / "seed_capability"
    seed_dir.mkdir(parents=True)
    (seed_dir / "prompt.txt").write_text("answer the question\n", encoding="utf-8")
    rd.snapshot("seed", seed_dir)
    rd.set_best("seed")
    return rd, seed_dir


def _optimizer(marker: str = "\n[CALC] compute exactly\n"):
    """A mock optimizer: appends the winning marker, idempotently."""
    def _run(workdir: Path, instructions: str) -> dict:
        p = Path(workdir) / "prompt.txt"
        cur = p.read_text(encoding="utf-8")
        if marker not in cur:
            p.write_text(cur + marker, encoding="utf-8")
        return {"cost_usd": 0.02, "tokens": 3}
    return _run


# ---- 1. what parallel DOES and DOES NOT preserve ---------------------------

class MonotoneAdapter(CapabilityAdapter):
    """Reward = fraction of val tasks whose index is below the ``[X]`` count.

    Strictly monotone in the number of ``[X]`` markers, so every real improvement is
    gate-visible and each accept unlocks exactly one more task. Paired with
    ``_nonidempotent_optimizer`` this makes DEPTH (serial) and BREADTH (parallel)
    measurably different searches rather than two schedules of the same one.
    """

    parallel_safe = True

    def tasks(self, split: str) -> list[Task]:
        return list(TASKS)

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        n = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8").count("[X]")
        return Rollout(task_id=task.id, output=str(n), cost_usd=0.01, tokens=1)

    def score(self, task: Task, rollout: Rollout) -> Score:
        idx = int(task.id[1:])
        ok = idx < int(rollout.output or 0)
        return Score(task_id=task.id, reward=1.0 if ok else 0.0,
                     feedback="", trial_rewards=[1.0 if ok else 0.0])


def _nonidempotent_optimizer():
    """Append ONE ``[X]`` to whatever parent it is handed — output depends on the parent.

    This is the fixture the equivalence claim needed and did not have. ``_optimizer``
    above is idempotent (it appends its marker only if absent), so every candidate
    converges to identical content no matter which parent it forked and a stale-parent
    fork is structurally undetectable. Here candidate content is a direct function of
    the parent, so a round of siblings forked from ONE champion produces N
    byte-identical candidates and the divergence is visible.
    """
    def _run(workdir: Path, instructions: str) -> dict:
        p = Path(workdir) / "prompt.txt"
        p.write_text(p.read_text(encoding="utf-8") + "[X]", encoding="utf-8")
        return {"cost_usd": 0.02, "tokens": 3}
    return _run


def _monotone_run(tmp_path: Path, name: str, workers: int, *, iters: int = 6):
    rd = RunDir.create(tmp_path / name, ts="t", budget=Budget(max_iterations=iters))
    ids = [t.id for t in TASKS]
    rd.write_splits(Splits(train=ids[6:7], val=ids[0:6], test=ids[7:], seed=0))
    seed_dir = tmp_path / name / "seed_capability"
    seed_dir.mkdir(parents=True)
    (seed_dir / "prompt.txt").write_text("", encoding="utf-8")
    rd.snapshot("seed", seed_dir)
    rd.set_best("seed")
    adapter = MonotoneAdapter()
    baseline = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                          split="val", tag="seed")
    res = harness.hill_climb_loop(
        adapter, run_dir=rd, optimizer=_nonidempotent_optimizer(), current_val=baseline,
        max_iterations=iters, store=None, parallel=workers, gate_kwargs={"k_se": 0.0})
    trace = [(s["candidate_id"], s["accepted"], round(s["candidate_val"]["reward"], 4))
             for s in res["steps"]]
    nx = {s["candidate_id"]: (rd.candidate_dir(s["candidate_id"]) / "prompt.txt")
          .read_text(encoding="utf-8").count("[X]") for s in res["steps"]}
    return res, rd, trace, nx


def test_parallel_changes_the_search_and_is_not_score_equivalent(tmp_path):
    """THE honest statement of what ``--parallel N>1`` does. Deterministic, no RNG.

    Serial forks each step from the previous ACCEPT (depth), so ``[X]`` accumulates
    1,2,3,… and every iteration accepts. A parallel round forks all N siblings from the
    START-OF-ROUND champion (breadth), so they are byte-identical at ``[X]``=k+1 and only
    the first can beat the champion — the rest are correctly REJECTED (which is the
    honesty property that does hold) but the budget is spent.

    Asserting the accept sequence and ``best_id`` progression, not just ``final.json``:
    a run comparison that looks only at the final score can pass by luck.
    """
    ser, rd_s, ser_trace, ser_nx = _monotone_run(tmp_path, "mono_ser", 1)
    par, rd_p, par_trace, par_nx = _monotone_run(tmp_path, "mono_par", 6)

    # Serial: depth. Every step accepts, [X] climbs 1..6, val climbs to 1.0.
    assert [a for _, a, _ in ser_trace] == [True] * 6, ser_trace
    assert [ser_nx[c] for c, _, _ in ser_trace] == [1, 2, 3, 4, 5, 6], ser_nx
    assert ser["best_val"] == 1.0
    assert ser["best_id"] == "cand_0006"

    # Parallel at N=6: breadth. ONE round, all six siblings forked from `seed`, so all
    # six are byte-identical and only the first clears the gate.
    assert [ser_nx[c] for c, _, _ in ser_trace] != [par_nx[c] for c, _, _ in par_trace]
    assert set(par_nx.values()) == {1}, par_nx
    assert [a for _, a, _ in par_trace] == [True] + [False] * 5, par_trace
    assert par["best_id"] == "cand_0001"

    # The headline: same iteration budget, parallel lands on a strictly WORSE score.
    assert par["best_val"] < ser["best_val"]
    # …and the accept sequence and best_id progression differ, which is exactly the
    # claim the deleted `test_serial_and_parallel_are_identical` used to assert.
    assert ser_trace != par_trace
    assert ser["best_id"] != par["best_id"]


def test_every_banked_score_is_still_honestly_gated(tmp_path):
    """What parallelism DOES preserve: a sibling forked from a superseded champion loses.

    The stale-parent fork is a search-quality problem, never an honesty problem — the
    serialized commit point re-gates each sibling against the champion as of ITS commit,
    so a redundant sibling is recorded as a reject and never banked as progress. Every
    accepted step must strictly beat the best val seen before it.
    """
    _, _, trace, nx = _monotone_run(tmp_path, "mono_gate", 4, iters=8)
    best = 0.0
    for cid, accepted, val in trace:
        if accepted:
            assert val > best, f"{cid} accepted without beating {best}: {trace}"
            best = val
        else:
            assert val <= best, f"{cid} rejected despite beating {best}: {trace}"
    # And best_val only ever came from an accepted step.
    assert best == max([v for _, a, v in trace if a] or [0.0])


def test_the_idempotent_probe_cannot_detect_a_stale_parent_fork(tmp_path):
    """Guard the test METHODOLOGY, so the false equivalence claim can't come back.

    With the idempotent ``_optimizer`` every candidate converges to the same content
    regardless of parent, so serial and parallel agree — and that agreement is an
    artifact of the fixture, not a property of the code. Assert both facts in one place:
    idempotent → looks identical; non-idempotent → provably differs.
    """
    ser, rd_s = _run_loop(tmp_path, "idem_ser", 1)
    par, rd_p = _run_loop(tmp_path, "idem_par", 4)
    assert _fingerprint(ser, rd_s) == _fingerprint(par, rd_p)  # a fixture artifact...
    for s in ser["steps"]:
        assert ((rd_s.candidate_dir(s["candidate_id"]) / "prompt.txt").read_bytes()
                == (rd_p.candidate_dir(s["candidate_id"]) / "prompt.txt").read_bytes())
    # ...and NOT a general guarantee — see the non-idempotent test above.
    _, _, t1, _ = _monotone_run(tmp_path, "idem_mono1", 1)
    _, _, t4, _ = _monotone_run(tmp_path, "idem_mono4", 4)
    assert t1 != t4


def _run_loop(tmp_path: Path, name: str, workers: int) -> dict:
    rd, seed_dir = _fresh_run(tmp_path, name)
    adapter = CalcAdapter()
    baseline = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                         split="val", tag="seed")
    return harness.hill_climb_loop(
        adapter, run_dir=rd, optimizer=_optimizer(), current_val=baseline,
        max_iterations=4, store=None, parallel=workers), rd


def _fingerprint(result: dict, rd: RunDir) -> dict:
    return {
        "best_id": result["best_id"],
        "best_val": round(result["best_val"], 9),
        "accepts": result["accepts"],
        "iterations": result["iterations"],
        "steps": [{"id": s["candidate_id"], "accepted": s["accepted"],
                   "val": round(s["candidate_val"]["reward"], 9),
                   "parent_val": round(s["parent_val"]["reward"], 9)} for s in result["steps"]],
        "spent_metric_calls": rd.spent.metric_calls,
        "spent_usd": round(rd.spent.usd, 9),
        "spent_iterations": rd.spent.iterations,
        "test_used": rd.read_splits().test_used,
    }


# NOTE: `test_serial_and_parallel_are_identical` used to live here and asserted something
# FALSE — it only passed because `_optimizer` is idempotent. Replaced by
# `test_parallel_changes_the_search_and_is_not_score_equivalent` (the real behaviour),
# `test_every_banked_score_is_still_honestly_gated` (what parallelism does preserve), and
# `test_the_idempotent_probe_cannot_detect_a_stale_parent_fork` (which pins the old probe
# as a fixture artifact so the claim cannot be reintroduced).


def test_parallel_default_is_one_and_serial(tmp_path):
    """The default must be serial: no threads, no behaviour change."""
    assert parallel.resolve_workers(None) == 1
    assert parallel.resolve_workers(0) == 1
    assert parallel.resolve_workers(-5) == 1
    assert parallel.resolve_workers("nonsense") == 1
    assert parallel.resolve_workers(4) == 4
    assert parallel.resolve_workers(9999) == 16

    seen: list[str] = []

    def fn(x):
        seen.append(threading.current_thread().name)
        return x * 2

    assert parallel.map_ordered(fn, [1, 2, 3], workers=1) == [2, 4, 6]
    assert set(seen) == {threading.current_thread().name}  # inline, no worker threads


def test_map_ordered_preserves_input_order(tmp_path):
    """Completion order must not leak into result order (determinism of the commit loop)."""
    def fn(x):
        time.sleep(0.05 if x == 0 else 0.0)  # first job finishes LAST
        return x
    assert parallel.map_ordered(fn, list(range(6)), workers=4) == list(range(6))


# ---- 2. hermetic isolation -------------------------------------------------

def test_concurrent_candidates_are_isolated_and_scored_independently(tmp_path):
    """Two candidates evaluated at once: neither sees the other's files; scores differ."""
    rd, _ = _fresh_run(tmp_path, "iso")
    adapter = CalcAdapter(sleep=0.01)
    # Candidate A gets the winning marker; candidate B gets a useless edit.
    plans = [{"candidate_id": "cand_0001", "parent_dir": rd.candidate_dir("seed"),
              "instructions": "A"},
             {"candidate_id": "cand_0002", "parent_dir": rd.candidate_dir("seed"),
              "instructions": "B"}]

    def optimizer(workdir: Path, instructions: str) -> dict:
        # `instructions` arrives augmented by the harness; the plan's own marker is the
        # first character (the raw text this test passed in).
        which = "A" if instructions.startswith("A") else "B"
        p = Path(workdir) / "prompt.txt"
        p.write_text(p.read_text(encoding="utf-8") +
                     ("\n[CALC] go\n" if which == "A" else "\nplease try harder\n"),
                     encoding="utf-8")
        # Leave a private file; the sibling must never see it.
        (Path(workdir) / f"private_{which}.txt").write_text(which, encoding="utf-8")
        siblings = sorted(q.name for q in Path(workdir).glob("private_*"))
        assert siblings == [f"private_{which}.txt"], f"leak: {siblings}"
        return {"cost_usd": 0.0, "tokens": 0}

    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")
    steps = harness.parallel_steps(adapter, plans, run_dir=rd, optimizer=optimizer,
                                   current_val=base, workers=2, store=None)
    by_id = {s["candidate_id"]: s for s in steps}
    assert by_id["cand_0001"]["candidate_val"]["reward"] == 1.0   # [CALC] → all correct
    assert by_id["cand_0002"]["candidate_val"]["reward"] == 0.0   # no marker → all wrong
    assert by_id["cand_0001"]["accepted"] is True
    assert by_id["cand_0002"]["accepted"] is False
    # The workspaces really are separate directories with separate contents.
    wa = Path(by_id["cand_0001"]["workdir"])
    wb = Path(by_id["cand_0002"]["workdir"])
    assert wa != wb
    assert (wa / "private_A.txt").exists() and not (wa / "private_B.txt").exists()
    assert (wb / "private_B.txt").exists() and not (wb / "private_A.txt").exists()


def test_commit_point_is_serialized(tmp_path):
    """Only one commit runs at a time, so the honesty core stays single-threaded."""
    rd, _ = _fresh_run(tmp_path, "serialcommit", max_iterations=8)
    adapter = CalcAdapter()
    concurrent = {"max": 0, "now": 0}
    lock = threading.Lock()
    real = harness.commit_candidate

    def spy(proposal, **kw):
        with lock:
            concurrent["now"] += 1
            concurrent["max"] = max(concurrent["max"], concurrent["now"])
        try:
            time.sleep(0.01)
            return real(proposal, **kw)
        finally:
            with lock:
                concurrent["now"] -= 1

    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")
    plans = [{"candidate_id": f"cand_{i:04d}", "parent_dir": rd.candidate_dir("seed"),
              "instructions": ""} for i in range(1, 5)]
    orig = harness.commit_candidate
    harness.commit_candidate = spy
    try:
        harness.parallel_steps(adapter, plans, run_dir=rd, optimizer=_optimizer(),
                               current_val=base, workers=4, store=None)
    finally:
        harness.commit_candidate = orig
    assert concurrent["max"] == 1, f"commits overlapped ({concurrent['max']} at once)"


# ---- 3. events.jsonl integrity under concurrent append ---------------------

def test_events_jsonl_has_no_partial_or_interleaved_lines(tmp_path):
    """N threads append fat records at once; EVERY line must parse strictly."""
    rd = RunDir.create(tmp_path / "ev", ts="t")
    n_threads, per_thread = 8, 60
    # Payloads far larger than Python's 8 KiB text buffer, so a buffered write would
    # have to split them across syscalls (the interleaving bug this guards).
    def writer(w: int) -> None:
        for i in range(per_thread):
            rd.log_event("load", worker=w, i=i, blob="x" * (4000 + 900 * (i % 9)))

    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        list(ex.map(writer, range(n_threads)))

    raw = rd.events_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    lines = raw.splitlines()
    assert len(lines) == n_threads * per_thread
    seen = set()
    for ln in lines:
        rec = json.loads(ln)  # strict: a spliced line raises here
        assert rec["kind"] == "load"
        assert set(rec["blob"]) == {"x"}
        seen.add((rec["worker"], rec["i"]))
    assert len(seen) == n_threads * per_thread  # nothing lost, nothing duplicated


def test_events_jsonl_survives_a_dribbling_reader(tmp_path):
    """A reader that consumes 7 bytes at a time still reassembles whole lines."""
    rd = RunDir.create(tmp_path / "ev2", ts="t")
    for i in range(30):
        rd.log_event("dribble", i=i, blob="y" * 9000)
    data = rd.events_path.read_bytes()
    buf, out = b"", []
    for off in range(0, len(data), 7):
        buf += data[off:off + 7]
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            out.append(json.loads(line))
    assert buf == b""
    assert [r["i"] for r in out] == list(range(30))


def test_parallel_run_events_all_parse(tmp_path):
    """The real loop at parallel=4: every emitted event line parses."""
    _, rd = _run_loop(tmp_path, "evrun", 4)
    lines = rd.events_path.read_text(encoding="utf-8").splitlines()
    recs = [json.loads(ln) for ln in lines]
    assert recs, "no events written"
    assert any(r["kind"] == "parallel_round" for r in recs)
    assert sum(1 for r in recs if r["kind"] == "step") == 4


# ---- 4. cost / token accounting is exact -----------------------------------

def test_cost_and_tokens_are_exact_under_parallelism(tmp_path):
    """Spent == sum of per-candidate spend, with concurrent read-modify-write."""
    rd, _ = _fresh_run(tmp_path, "cost", max_iterations=8)
    adapter = CalcAdapter(cost=0.005, tokens=11)
    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")
    before = rd.spent
    plans = [{"candidate_id": f"cand_{i:04d}", "parent_dir": rd.candidate_dir("seed"),
              "instructions": ""} for i in range(1, 7)]
    steps = harness.parallel_steps(adapter, plans, run_dir=rd, optimizer=_optimizer(),
                                   current_val=base, workers=6, store=None)
    after = rd.spent
    runner_usd = sum(s["candidate_val"]["cost_usd"] for s in steps)
    runner_tok = sum(s["candidate_val"]["tokens"] for s in steps)
    opt_usd = sum(s["optimizer_usd"] for s in steps)
    opt_tok = sum(s["optimizer_tokens"] for s in steps)
    assert after.usd - before.usd == pytest.approx(runner_usd, abs=1e-12)
    assert after.runner_tokens - before.runner_tokens == runner_tok
    assert after.optimizer_usd - before.optimizer_usd == pytest.approx(opt_usd, abs=1e-12)
    assert after.optimizer_tokens - before.optimizer_tokens == opt_tok
    assert after.iterations - before.iterations == len(plans)
    # Nothing lost: every rollout counted (6 candidates x 3 val tasks x 1 trial).
    assert after.metric_calls - before.metric_calls == len(plans) * 3


def test_update_spent_loses_nothing_under_heavy_concurrency(tmp_path):
    """The locked RMW must not drop a single increment."""
    rd = RunDir.create(tmp_path / "spend", ts="t")
    n, per = 8, 40

    def bump(_w):
        for _ in range(per):
            rd.update_spent(metric_calls=1, usd=0.01, runner_tokens=3)

    with ThreadPoolExecutor(max_workers=n) as ex:
        list(ex.map(bump, range(n)))
    sp = rd.spent
    assert sp.metric_calls == n * per
    assert sp.runner_tokens == n * per * 3
    assert sp.usd == pytest.approx(n * per * 0.01, abs=1e-9)


# ---- 5. eval cache under concurrency --------------------------------------

def test_eval_cache_no_collision_and_no_lost_writes(tmp_path):
    """Distinct candidate hashes never collide; concurrent puts all persist."""
    cache = EvalCache(tmp_path / "cache.json")
    hashes = [f"h{i:02d}" for i in range(8)]

    def put(h):
        for t in range(20):
            cache.put(h, f"t{t}", reward=float(t) / 20.0, feedback=f"{h}:{t}")

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(put, hashes))
    for h in hashes:
        for t in range(20):
            got = cache.get(h, f"t{t}")
            assert got is not None and got["feedback"] == f"{h}:{t}"
    # And the persisted file is valid JSON holding every entry (no torn write).
    on_disk = json.loads((tmp_path / "cache.json").read_text(encoding="utf-8"))
    assert len(on_disk) == len(hashes) * 20
    assert len(EvalCache(tmp_path / "cache.json")) == len(hashes) * 20


def test_atomic_write_is_thread_safe(tmp_path):
    """Concurrent _atomic_write to ONE path yields one of the inputs, never a splice."""
    from cap_evolve.rundir import _atomic_write
    target = tmp_path / "x.json"
    payloads = [json.dumps({"who": i, "pad": "z" * 20000}) for i in range(8)]

    def w(p):
        for _ in range(15):
            _atomic_write(target, p)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(w, payloads))
    assert target.read_text(encoding="utf-8") in payloads
    # No temp files left behind.
    assert not [p.name for p in tmp_path.iterdir() if p.name.startswith(".x.json.tmp")]


def test_rollout_files_are_not_truncate_written(tmp_path):
    """A hardlinked archive of a rollout must NOT be mutated by a re-evaluation."""
    rd, _ = _fresh_run(tmp_path, "hardlink")
    adapter = CalcAdapter()
    harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                              split="val", tag="seed")
    src = sorted((rd.rollouts / "val").glob("*__seed__t0.json"))[0]
    archive = tmp_path / "archived.json"
    os.link(src, archive)  # shared inode, exactly the PR #210 scenario
    original = archive.read_bytes()
    # Re-evaluate the same tag with a DIFFERENT candidate so the content changes.
    cand = rd.candidate_dir("seed")
    (cand / "prompt.txt").write_text("[CALC] now correct\n", encoding="utf-8")
    harness.evaluate_candidate(adapter, cand, run_dir=rd, split="val", tag="seed")
    assert src.read_bytes() != original       # the live file changed
    assert archive.read_bytes() == original   # the archive did NOT


# ---- 6. sealed test split --------------------------------------------------

def test_no_worker_touches_the_test_split(tmp_path):
    """Parallel candidate evaluation reads val only; the seal stays unused and no
    test task id appears in any worker dir or val rollout."""
    result, rd = _run_loop(tmp_path, "seal", 4)
    splits = rd.read_splits()
    assert splits.test == ["t7"]
    assert splits.test_used is False
    assert not (rd.rollouts / "test").exists()
    # Grep every worker dir + val rollout for the sealed task id: must be zero hits.
    hits = []
    for root in [rd.root / "work", rd.rollouts / "val"]:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if "t7" in p.name:
                hits.append(str(p))
                continue
            try:
                if "t7" in p.read_text(encoding="utf-8"):
                    hits.append(str(p))
            except (UnicodeDecodeError, OSError):
                pass
    assert hits == [], f"sealed test id leaked into worker/val artifacts: {hits}"


def test_seal_can_be_consumed_only_once_even_from_many_threads(tmp_path):
    """Concurrent commit_test: exactly one wins, the rest raise TestSealError."""
    rd, _ = _fresh_run(tmp_path, "seal2")
    ok, failed = [], []

    def burn(_i):
        try:
            rd.commit_test()
            ok.append(1)
        except TestSealError:
            failed.append(1)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(burn, range(8)))
    assert len(ok) == 1, f"seal burned {len(ok)} times"
    assert len(failed) == 7
    assert rd.read_splits().test_used is True


# ---- 7. workspace cleanup: normal, exception, SIGINT ----------------------

def test_workspace_cleans_up_on_normal_exit_and_on_exception(tmp_path):
    root = tmp_path / "work"
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "f.txt").write_text("hi", encoding="utf-8")

    with parallel.workspace(root, "c1", parent, keep=False) as wd:
        assert (wd / "f.txt").read_text(encoding="utf-8") == "hi"
        assert wd in parallel.live_workspaces()
    assert not wd.exists()
    assert parallel.live_workspaces() == []

    with pytest.raises(RuntimeError):
        with parallel.workspace(root, "c2", parent, keep=False) as wd2:
            raise RuntimeError("boom")
    assert not wd2.exists()
    assert parallel.live_workspaces() == []


def test_workspace_cleans_up_on_sigint(tmp_path):
    """A real SIGINT to a child process must leave no workspace behind."""
    script = tmp_path / "sig.py"
    marker = tmp_path / "started"
    script.write_text(
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "from cap_evolve import parallel\n"
        "root = Path(sys.argv[1]) / 'work'\n"
        "parent = Path(sys.argv[1]) / 'parent'\n"
        "parent.mkdir(parents=True, exist_ok=True)\n"
        "(parent / 'f.txt').write_text('x')\n"
        "try:\n"
        "    with parallel.workspace(root, 'cX', parent, keep=False) as wd:\n"
        "        Path(sys.argv[2]).write_text(str(wd))\n"
        "        time.sleep(30)\n"
        "except KeyboardInterrupt:\n"
        "    pass\n",
        encoding="utf-8")
    core_dir = Path(harness.__file__).resolve().parents[1]  # .../core (holds cap_evolve/)
    env = dict(os.environ, PYTHONPATH=str(core_dir))
    proc = subprocess.Popen([sys.executable, str(script), str(tmp_path), str(marker)], env=env)
    try:
        for _ in range(200):
            if marker.exists():
                break
            time.sleep(0.05)
        assert marker.exists(), "child never entered the workspace"
        wd = Path(marker.read_text(encoding="utf-8"))
        assert wd.exists()
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert not wd.exists(), "SIGINT left an orphan workspace"


def test_real_run_sigint_cleans_up_the_workspace(tmp_path):
    """The PRODUCTION path, not the helper: a real SIGINT to a real ``propose_candidate``.

    Regression for a defect this PR's own SIGINT test could not see: it called
    ``parallel.workspace()`` directly, but ``propose_candidate`` did its own raw
    ``copytree`` and never registered anything, so ``_install_handlers`` never ran in a
    real run and a Ctrl-C mid-round orphaned every live workspace. The child below builds
    a run dir and calls ``harness.propose_candidate`` with an optimizer that blocks, so
    the interrupt lands while the workspace is genuinely uncommitted.
    """
    script = tmp_path / "realsig.py"
    marker = tmp_path / "wd_path"
    script.write_text(
        "import sys, time\n"
        "from pathlib import Path\n"
        "from cap_evolve import Budget, RunDir\n"
        "from cap_evolve import harness\n"
        "from cap_evolve.splits import Splits\n"
        "sys.path.insert(0, str(Path(sys.argv[3])))\n"
        "from test_parallel_candidates import CalcAdapter, TASKS\n"
        "base = Path(sys.argv[1]) / 'run'\n"
        "rd = RunDir.create(base, ts='t', budget=Budget(max_iterations=2))\n"
        "ids = [t.id for t in TASKS]\n"
        "rd.write_splits(Splits(train=ids[:4], val=ids[4:7], test=ids[7:], seed=0))\n"
        "seed = base / 'seed_capability'; seed.mkdir(parents=True)\n"
        "(seed / 'prompt.txt').write_text('x')\n"
        "rd.snapshot('seed', seed); rd.set_best('seed')\n"
        "def blocking_optimizer(workdir, instructions):\n"
        "    Path(sys.argv[2]).write_text(str(workdir))\n"   # workspace now EXISTS + is live
        "    time.sleep(60)\n"
        "    return {}\n"
        "try:\n"
        "    harness.propose_candidate(CalcAdapter(), run_dir=rd,\n"
        "        parent_dir=rd.candidate_dir('seed'), optimizer=blocking_optimizer,\n"
        "        instructions='go', candidate_id='cand_0001')\n"
        "except BaseException:\n"
        "    pass\n",
        encoding="utf-8")
    core_dir = Path(harness.__file__).resolve().parents[1]
    tests_dir = Path(__file__).resolve().parent
    env = dict(os.environ, PYTHONPATH=str(core_dir))
    proc = subprocess.Popen(
        [sys.executable, str(script), str(tmp_path), str(marker), str(tests_dir)], env=env)
    try:
        for _ in range(400):
            if marker.exists() and marker.read_text(encoding="utf-8").strip():
                break
            time.sleep(0.05)
        raw = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
        assert raw, "child never reached the optimizer with a live workspace"
        wd = Path(raw)
        assert wd.exists(), "workspace should exist while the optimizer is running"
        assert (wd / "prompt.txt").exists(), "workspace should be a copy of the parent"
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    assert not wd.exists(), f"SIGINT left an orphan workspace at {wd} (real run path)"


def test_committed_workspace_is_released_from_the_interrupt_registry(tmp_path):
    """Once snapshotted into ``candidates/``, a workspace is scratch — not interrupt work.

    Complements the SIGINT test: the registry must be empty after a normal round, or a
    later interrupt would delete inspectable scratch belonging to committed candidates
    (and ``_LIVE`` would grow without bound across a long run).
    """
    rd, _ = _fresh_run(tmp_path, "release")
    adapter = CalcAdapter()
    baseline = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                          split="val", tag="seed")
    harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_optimizer(),
                            current_val=baseline, max_iterations=2, store=None, parallel=2)
    assert parallel.live_workspaces() == []
    # The directories themselves are deliberately kept for post-hoc inspection.
    assert (rd.root / "work" / "cand_0001").exists()


def test_no_git_worktree_orphans(tmp_path):
    """We never create git worktrees, so `git worktree list` can't accumulate orphans.

    Guards the design decision: the isolation unit is a plain hermetic directory, so
    a crashed candidate cannot leave a stale entry in .git/worktrees. Prove no
    parallel run registers one in the run's own git store.
    """
    if not shutil.which("git"):
        pytest.skip("git unavailable")
    _, rd = _run_loop(tmp_path, "wt", 4)
    from cap_evolve.store import VersionStore
    store = VersionStore(kind="git", root=rd.root)
    store.init()
    out = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=str(rd.root),
                         capture_output=True, text=True)
    worktrees = [ln for ln in out.stdout.splitlines() if ln.startswith("worktree ")]
    assert len(worktrees) <= 1, f"unexpected worktrees: {worktrees}"
    assert not (rd.root / ".git" / "worktrees").exists()


# ---- 8. concurrency-unsafe adapter falls back to sequential ---------------

def test_unsafe_adapter_is_downgraded_to_sequential(tmp_path):
    rd, _ = _fresh_run(tmp_path, "unsafe")
    unsafe = GlobalInjectAdapter()
    safe, reason = parallel.adapter_is_parallel_safe(unsafe)
    assert safe is False and "apply" in reason
    assert parallel.resolve_workers_for(unsafe, 4, run_dir=rd) == 1
    recs = [json.loads(ln) for ln in rd.events_path.read_text(encoding="utf-8").splitlines()]
    downgrades = [r for r in recs if r["kind"] == "parallel_downgraded"]
    assert downgrades and downgrades[-1]["requested"] == 4 and downgrades[-1]["workers"] == 1


def test_safe_adapter_is_allowed_and_declaration_wins(tmp_path):
    safe, reason = parallel.adapter_is_parallel_safe(CalcAdapter())
    assert safe is True and "default" in reason

    class Declared(GlobalInjectAdapter):
        parallel_safe = True

    safe2, reason2 = parallel.adapter_is_parallel_safe(Declared())
    assert safe2 is True and "declares" in reason2

    class OptedOut(CalcAdapter):
        parallel_safe = False

    safe3, _ = parallel.adapter_is_parallel_safe(OptedOut())
    assert safe3 is False


def test_unsafe_adapter_still_produces_correct_results(tmp_path):
    """The sequential fallback must be correct, not just slower."""
    rd, _ = _fresh_run(tmp_path, "unsafe2")
    adapter = GlobalInjectAdapter()
    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")
    result = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_optimizer(),
                                     current_val=base, max_iterations=2, store=None,
                                     parallel=4)
    assert result["accepts"] == 1
    assert result["best_val"] == 1.0


# ---- 9. a parallel round must not overshoot the budget --------------------

def test_parallel_round_respects_budget_headroom(tmp_path):
    """A round is clamped to remaining headroom, so N=4 spends the same as N=1.

    Regression for a real divergence found during verification: the round launched
    `workers` candidates without looking at the caps, so a parallel run overshot
    max_iterations / kept proposing past `stall` and produced MORE steps than a serial
    run with the same budget.
    """
    def run(workers: int, **budget) -> dict:
        base = tmp_path / f"b{workers}{sorted(budget.items())}"
        rd = RunDir.create(base, ts="t", budget=Budget(**budget))
        ids = [t.id for t in TASKS]
        rd.write_splits(Splits(train=ids[:4], val=ids[4:7], test=ids[7:], seed=0))
        seed_dir = base / "seed"
        seed_dir.mkdir(parents=True)
        (seed_dir / "prompt.txt").write_text("answer\n", encoding="utf-8")
        rd.snapshot("seed", seed_dir)
        rd.set_best("seed")
        adapter = CalcAdapter()
        base_val = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                              split="val", tag="seed")
        res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=_optimizer(),
                                      current_val=base_val, max_iterations=20,
                                      store=None, parallel=workers)
        return {"ids": [s["candidate_id"] for s in res["steps"]],
                "accepts": res["accepts"], "iterations": rd.spent.iterations,
                "metric_calls": rd.spent.metric_calls, "stop": res["stop_reason"]}

    # stall cap: the optimizer wins once then plateaus, so stall trips.
    assert run(1, max_iterations=20, stall=2) == run(4, max_iterations=20, stall=2)
    # iteration cap that is NOT a multiple of the worker count.
    assert run(1, max_iterations=3) == run(4, max_iterations=3)
    # metric-call cap: 3 val tasks per candidate, cap of 7 → 2 candidates then stop.
    assert run(1, max_iterations=20, max_metric_calls=10) == \
           run(4, max_iterations=20, max_metric_calls=10)


def test_budget_headroom(tmp_path):
    rd = RunDir.create(tmp_path / "hr", ts="t", budget=Budget(max_iterations=5, stall=2))
    assert rd.budget_headroom() == 2                      # stall is tighter
    rd.update_spent(accepted=False)                       # stall -> 1
    assert rd.budget_headroom() == 1
    rd.update_spent(accepted=True)                        # stall -> 0
    assert rd.budget_headroom() == 2
    rd.update_spent(iterations=4)
    assert rd.budget_headroom() == 1                      # iterations now tighter
    rd.update_spent(iterations=1)
    assert rd.budget_headroom() == 0
    # max_metric_calls converts to candidates only when the per-candidate cost is known.
    mc = RunDir.create(tmp_path / "mc", ts="t",
                       budget=Budget(max_iterations=99, max_metric_calls=10))
    assert mc.budget_headroom() == 99                       # unknown cost → cap not applied
    assert mc.budget_headroom(metric_calls_per_candidate=3) == 4   # ceil(10/3)
    mc.update_spent(metric_calls=9)
    assert mc.budget_headroom(metric_calls_per_candidate=3) == 1   # ceil(1/3)
    mc.update_spent(metric_calls=1)
    assert mc.budget_headroom(metric_calls_per_candidate=3) == 0


def test_budget_headroom_includes_the_money_caps(tmp_path):
    """The two cost caps must constrain a round, or N>1 overshoots a HARD spend ceiling.

    Regression: ``budget_headroom`` omitted ``max_usd`` and ``max_optimizer_usd``
    entirely, so a round of N committed N candidates before the next
    ``budget_exhausted()`` check — measured 2x ``max_optimizer_usd`` at N=8.
    """
    rd = RunDir.create(tmp_path / "usd", ts="t", budget=Budget(max_iterations=99, max_usd=1.0))
    # No observed average yet → the first money-capped round is limited to ONE candidate,
    # after which the real per-iteration rate is known. Guessing here is what let N=8
    # blow the cap on round 1.
    assert rd.budget_headroom() == 1
    rd.update_spent(iterations=1, usd=0.10)    # $0.10/iteration, $0.90 left → 8 more
    assert rd.budget_headroom() == 8   # 0.9//0.1 floors to 8 in binary float: conservative
    rd.update_spent(iterations=1, usd=0.40)    # $0.25/iteration avg, $0.50 left → 2 more
    assert rd.budget_headroom() == 2
    rd.update_spent(iterations=1, usd=0.45)    # $0.95 spent, $0.05 left at $0.316/iter
    assert rd.budget_headroom() == 1           # floored at 1: same as serial's in-flight candidate

    # optimizer_usd is projected off optimizer spend alone, not total.
    od = RunDir.create(tmp_path / "ousd", ts="t",
                       budget=Budget(max_iterations=99, max_optimizer_usd=2.0))
    od.update_spent(iterations=1, optimizer_usd=0.50, usd=5.0)  # runner spend must not count
    assert od.budget_headroom() == 3           # (2.0-0.5)//0.5
    # A cap that isn't set never constrains.
    free = RunDir.create(tmp_path / "free", ts="t", budget=Budget(max_iterations=99))
    free.update_spent(iterations=1, usd=100.0, optimizer_usd=100.0)
    assert free.budget_headroom() == 98   # only max_iterations constrains (99 - 1 spent)


def _spendy_run(tmp_path: Path, name: str, workers: int, **caps):
    """Hill-climb with a $0.10/rollout adapter and a $0.50/candidate optimizer."""
    rd = RunDir.create(tmp_path / name, ts="t", budget=Budget(**caps))
    ids = [t.id for t in TASKS]
    rd.write_splits(Splits(train=ids[:4], val=ids[4:7], test=ids[7:], seed=0))
    seed_dir = tmp_path / name / "seed_capability"
    seed_dir.mkdir(parents=True)
    (seed_dir / "prompt.txt").write_text("", encoding="utf-8")
    rd.snapshot("seed", seed_dir)
    rd.set_best("seed")
    adapter = CalcAdapter(cost=0.10, tokens=1)

    def opt(workdir, instructions):
        return {"cost_usd": 0.50, "tokens": 1}

    baseline = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                          split="val", tag="seed")
    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=opt, current_val=baseline,
                                  max_iterations=caps.get("max_iterations") or 99,
                                  store=None, parallel=workers)
    return res, rd


@pytest.mark.parametrize("workers", [1, 4, 8])
def test_all_four_caps_hold_at_every_worker_count(tmp_path, workers):
    """max_iterations, stall, max_usd and max_optimizer_usd must all hold at N=8.

    "Hold" = overshot by at most the ONE candidate already in flight, which is exactly
    what the serial loop does (it checks the cap before a candidate, then runs it to
    completion). The N x overshoot is the defect; one candidate is pre-existing N=1
    behaviour.
    """
    per_iter_usd = 0.30 + 0.50   # 3 val tasks x $0.10 + $0.50 optimizer
    res, rd = _spendy_run(tmp_path, f"usd{workers}", workers,
                          max_iterations=20, max_usd=2.0)
    assert rd.spent.iterations <= 20
    assert rd.spent.total_usd <= 2.0 + per_iter_usd, (
        f"max_usd overshot at N={workers}: {rd.spent.total_usd}")

    res, rd = _spendy_run(tmp_path, f"opt{workers}", workers,
                          max_iterations=20, max_optimizer_usd=2.0)
    assert rd.spent.optimizer_usd <= 2.0 + 0.50, (
        f"max_optimizer_usd overshot at N={workers}: {rd.spent.optimizer_usd}")

    # max_iterations exactly, and stall (this optimizer never improves, so every step
    # after the first rejects).
    res, rd = _spendy_run(tmp_path, f"it{workers}", workers, max_iterations=6)
    assert rd.spent.iterations == 6, f"iterations at N={workers}: {rd.spent.iterations}"
    res, rd = _spendy_run(tmp_path, f"st{workers}", workers, max_iterations=20, stall=3)
    assert rd.spent.stall <= 3, f"stall overshot at N={workers}: {rd.spent.stall}"
    assert rd.spent.iterations <= 20


# ---- 10. honesty failures must ABORT, not become a rejected candidate -----

def test_seal_violation_aborts_the_round(tmp_path):
    """A TestSealError from a worker propagates; nothing is scored or banked.

    Regression for a defect found during this issue's own verification: both the
    optimizer-call ``except Exception`` and the round's ``except Exception`` swallowed
    honesty errors and recorded them as "a rejected candidate", so a tamper detection
    or a seal violation was downgraded to a wasted iteration instead of aborting.
    """
    rd, _ = _fresh_run(tmp_path, "fatal")
    adapter = CalcAdapter()
    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")

    def evil_optimizer(workdir: Path, instructions: str) -> dict:
        raise TestSealError("simulated seal violation from inside a worker")

    plans = [{"candidate_id": f"cand_{i:04d}", "parent_dir": rd.candidate_dir("seed"),
              "instructions": ""} for i in (1, 2)]
    with pytest.raises(TestSealError):
        harness.parallel_steps(adapter, plans, run_dir=rd, optimizer=evil_optimizer,
                               current_val=base, workers=2, store=None)
    recs = [json.loads(ln) for ln in rd.events_path.read_text(encoding="utf-8").splitlines()]
    assert not [r for r in recs if r["kind"] == "step"], "a score was banked despite the abort"
    assert rd.best_id == "seed"
    assert rd.read_splits().test_used is False


def test_seal_violation_also_aborts_a_serial_step(tmp_path):
    """Same guarantee on the serial path — the fix is in shared code, not the fork."""
    rd, _ = _fresh_run(tmp_path, "fatal2")
    adapter = CalcAdapter()
    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")

    def evil_optimizer(workdir: Path, instructions: str) -> dict:
        raise TestSealError("simulated seal violation")

    with pytest.raises(TestSealError):
        harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                         optimizer=evil_optimizer, instructions="", current_val=base,
                         candidate_id="cand_0001", store=None)
    assert rd.best_id == "seed"


def test_honesty_errors_includes_tamper_when_available():
    """``TamperError`` (#142) joins the fatal set as soon as ``protect`` exists."""
    fatal = harness._honesty_errors()
    assert TestSealError in fatal
    try:
        from cap_evolve.protect import TamperError
    except ImportError:
        pytest.skip("protected-paths guard (#142) not merged yet")
    assert TamperError in fatal


# ---- 11. a failed proposal doesn't sink the round -------------------------

def test_failed_proposal_becomes_a_rejected_step(tmp_path):
    rd, _ = _fresh_run(tmp_path, "fail")
    adapter = CalcAdapter()
    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd,
                                      split="val", tag="seed")
    plans = [{"candidate_id": "cand_0001", "parent_dir": rd.candidate_dir("seed"),
              "instructions": "ok"},
             {"candidate_id": "cand_0002", "parent_dir": tmp_path / "does-not-exist",
              "instructions": "broken"}]
    steps = harness.parallel_steps(adapter, plans, run_dir=rd, optimizer=_optimizer(),
                                   current_val=base, workers=2, store=None)
    by_id = {s["candidate_id"]: s for s in steps}
    assert by_id["cand_0001"]["accepted"] is True
    assert by_id["cand_0002"]["accepted"] is False
    assert "proposal failed" in (by_id["cand_0002"]["optimizer_error"] or "")
    recs = [json.loads(ln) for ln in rd.events_path.read_text(encoding="utf-8").splitlines()]
    assert any(r["kind"] == "proposal_error" for r in recs)
