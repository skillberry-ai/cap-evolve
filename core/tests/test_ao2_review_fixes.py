"""PR-2b: review fixes for the AO-2 conductor. Fakes only; the real-backend end-to-end is test_ao2_e2e.py."""

from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402

import conductor  # noqa: E402
import conductor_backend  # noqa: E402
import proposer  # noqa: E402
from cap_evolve import conductor_state as cs  # noqa: E402

SPEC = {"max_metric_calls": 5000, "ao_plateau_n": 99}


def _until(c, pred, ticks=400):
    for _ in range(ticks):
        if pred():
            return
        c.tick()
    raise AssertionError("condition never reached")


def _events(w, name):
    return [e[1] for e in w.events if e[0] == name]


# HIGH 1 -----------------------------------------------------------------------------------------
def test_a_runaway_proposer_is_killed_at_the_job_token_cap(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={**SPEC, "max_optimizer_tokens": 100_000, "ao_job_token_cap": 3_000})
    w.hang_tokens = 5_000
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    _until(c, lambda: _events(w, "job_token_cap"))
    ev = _events(w, "job_token_cap")[0]
    assert ev["tokens"] == 5_000 and ev["cap"] == 3_000
    assert not [j for j in w.jobs.values() if j["id"] == ev["job"]], "the process was killed"
    j = c.st["jobs"][ev["job"]]
    assert j["state"] == "failed" and j["result"]["error"] == "token_cap"
    assert c.st["tokens_committed"] >= 5_000, "what the job burned is booked"
    assert j["reserved_tokens"] == 0


def test_transcript_tokens_count_each_message_once_and_prefer_the_result_record(tmp_path):
    t = tmp_path / "t.jsonl"
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 9999}
    rows = [{"type": "assistant", "message": {"id": "m1", "usage": usage}},
            {"type": "assistant", "message": {"id": "m1", "usage": usage}},
            {"type": "assistant", "message": {"id": "m2", "usage": usage}}, "not json"]
    t.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows))
    assert proposer.transcript_tokens(t) == 2 * 115
    t.write_text(t.read_text() + "\n" + json.dumps({"type": "result", "usage": {"input_tokens": 1, "output_tokens": 2}}))
    assert proposer.transcript_tokens(t) == 3
    assert proposer.transcript_tokens(tmp_path / "missing") == 0


def test_the_real_backend_hands_every_one_shot_job_a_hard_usd_limit_and_a_transcript(tmp_path):
    spent = SimpleNamespace(optimizer_usd=1.5)
    fake = SimpleNamespace(spec={"max_optimizer_usd": 4.0}, root=tmp_path)
    import unittest.mock as m
    with m.patch.object(conductor_backend.RunDir, "open", return_value=SimpleNamespace(spent=spent)):
        assert conductor_backend.RealBackend.job_usd_cap(fake) == 2.5          # what the run may still spend
        fake.spec["ao_job_usd_cap"] = 1.0
        assert conductor_backend.RealBackend.job_usd_cap(fake) == 1.0          # an explicit per-job cap wins when lower
        fake.spec = {}
        assert conductor_backend.RealBackend.job_usd_cap(fake) == 0


# HIGH 2 -----------------------------------------------------------------------------------------
def test_a_started_job_is_on_disk_with_its_pid_before_anything_else_can_crash(tmp_path):
    w, be, cfg = F.make(tmp_path, spec=SPEC)
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    j = c.new_job("eval", tag="seed", ids=["t00"], window=(0, 1)) if hasattr(c, "new_job") else None
    if j is None:
        _until(c, lambda: any(x["state"] == "running" for x in c.st["jobs"].values()))
        # the live state on disk right after a tick must already carry pids for every running job
    disk = json.loads((w.root / "conductor.json").read_text())
    running = [x for x in disk["jobs"].values() if x["state"] == "running"]
    assert running and all(x.get("pid") for x in running)
    # and specifically: save() is called straight after start, not only at the end of the tick
    saves, orig = [], c.store.save
    c.store.save = lambda st: (saves.append([x["state"] for x in st["jobs"].values()]), orig(st))[1]
    job = {"id": "j_probe", "kind": "eval", "tag": "seed", "ids": ["t00"], "window": [0, 1], "state": "queued",
           "reserved_rollouts": 0, "reserved_tokens": 0}
    c.st["jobs"]["j_probe"] = job
    c._start(job)
    assert len(saves) == 2 and saves[-1].count("running") > saves[0].count("running"), saves


# MEDIUM 4 ---------------------------------------------------------------------------------------
def test_a_vanished_job_frees_its_slot_at_once_not_after_the_timeout(tmp_path):
    w, be, cfg = F.make(tmp_path, spec=SPEC, world_kw={"delay": (50, 50)})
    cfg.chunk_timeout = 10 ** 9
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    _until(c, lambda: cs.live(c.st, "eval"))
    gone = cs.live(c.st, "eval")[0]
    w.jobs.pop(gone["id"])                                  # killed from outside: no exit record
    c.reap()
    assert c.st["jobs"][gone["id"]]["state"] == "lost"
    assert c.st["jobs"][gone["id"]]["reserved_rollouts"] == 0
    assert _events(w, "job_vanished")


def test_a_vanished_proposer_counts_an_attempt_so_it_is_not_retried_forever(tmp_path):
    w, be, cfg = F.make(tmp_path, spec=SPEC, world_kw={"delay": (50, 50)})
    cfg.chunk_timeout = 10 ** 9
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    _until(c, lambda: cs.live(c.st, "propose"))
    j = cs.live(c.st, "propose")[0]
    w.jobs.pop(j["id"])
    c.reap()
    assert c.st["attempts"][j["tag"]] == 1


# MEDIUM 5 ---------------------------------------------------------------------------------------
def test_a_blocked_finalize_exits_2_so_the_supervisor_stops(tmp_path, monkeypatch, capsys):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 80, "ao_plateau_n": 99})

    def blocked(champion):
        raise conductor.Refused("finalize blocked: the seed's test rollouts are missing")
    be.finalize = blocked
    monkeypatch.setattr(conductor_backend, "open_backend", lambda *a, **k: (be, cfg))
    be.run_lock = lambda: __import__("contextlib").nullcontext()
    cfg.tick_s = 0
    rc = conductor.main(["run", "--run-dir", str(w.root), "--project", str(tmp_path)])
    assert rc == conductor.EXIT_REFUSED
    assert "finalize blocked" in capsys.readouterr().out
    assert _events(w, "finalize_blocked")
    assert "finalize_blocked" in json.loads((w.root / "conductor.json").read_text())
    assert conductor.supervise(["x"], spawn=lambda a: rc, sleep=lambda s: None) == conductor.EXIT_REFUSED


# MEDIUM 6 ---------------------------------------------------------------------------------------
def test_an_uninterruptible_job_keeps_its_slot_and_reservation_until_it_really_ends(tmp_path):
    w, be, cfg = F.make(tmp_path, spec=SPEC, world_kw={"delay": (50, 50)})
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    _until(c, lambda: cs.live(c.st, "eval"))
    j = cs.live(c.st, "eval")[0]
    held = j["reserved_rollouts"]
    w.unkillable = True
    assert c._stop(j) is False and j["cancelling"]
    c.reap()
    assert j["state"] == "running" and j["reserved_rollouts"] == held, "slot and reservation are still held"
    w.jobs[j["id"]]["left"] = 1                              # the worker finally finishes
    c.reap()
    assert j["state"] == "lost" and j["reserved_rollouts"] == 0 and _events(w, "job_cancelled")


def test_real_backend_kill_waits_for_a_running_p2_thread_but_cancels_a_queued_one():
    gate = threading.Event()
    pool = ThreadPoolExecutor(max_workers=1)
    running = pool.submit(gate.wait)
    queued = pool.submit(lambda: 1)
    fake = SimpleNamespace(_threads={"a": running, "b": queued})
    kill = conductor_backend.RealBackend.kill
    import time
    time.sleep(0.05)
    try:
        assert kill(fake, {"id": "a", "p2": {"x": 1}}) is False and "a" in fake._threads
        assert kill(fake, {"id": "b", "p2": {"x": 1}}) is True and "b" not in fake._threads
    finally:
        gate.set()
    running.result(timeout=5)
    assert kill(fake, {"id": "a", "p2": {"x": 1}}) is True
    pool.shutdown()


# LOW 7 ------------------------------------------------------------------------------------------
def test_run_lock_is_a_context_manager_that_holds_the_lock_inside_it(tmp_path):
    held = []
    rd = SimpleNamespace(run_lock=lambda name: held.append(name))
    fake = SimpleNamespace(run_dir=rd)
    with conductor_backend.RealBackend.run_lock(fake):
        assert held == ["conductor"]


# gap (c): a proposer that cannot produce anything new must not spin -------------------------------
def test_a_duplicate_only_proposer_stops_the_run_as_proposer_exhausted(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 100_000, "max_optimizer_tokens": 10_000_000,
                                        "ao_plateau_n": 10_000, "ao_max_idle_proposals": 4},
                        world_kw={"dup_every": 1})
    c = F.run_to_done(w, be, cfg)
    assert c.st["stop_reason"] == "proposer_exhausted" and c.st["stopped"] == "proposer_exhausted"
    assert c.st["idle_proposals"] == 4 and c.st["n_proposals"] <= 6, "stopped at the cap, not after dozens"
    assert c.st["tokens_committed"] > 0, "the idle proposals' tokens are booked against the token cap"
    assert w.finalize_calls == 1 and c.st["finalized"], "and the run was finalized"


def test_an_idle_streak_resets_when_a_real_candidate_arrives(tmp_path):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 3000, "ao_plateau_n": 10_000, "ao_max_idle_proposals": 3},
                        world_kw={"dup_every": 3, "salt": 2})
    c = F.run_to_done(w, be, cfg)
    assert c.st["n_proposals"] > 3, "a duplicate now and then does not stop the run"
    assert c.st["stop_reason"] != "proposer_exhausted"


def test_the_idle_cap_is_configurable_and_defaults_to_six():
    from conductor import Cfg
    assert Cfg.from_spec({"ao_max_idle_proposals": 0}).caps.max_idle == 6, "0 means unset: the default holds"
    assert Cfg.from_spec({"ao_max_idle_proposals": 9}).caps.max_idle == 9


def test_the_final_estimate_is_configurable_and_never_exceeds_what_is_left(tmp_path):
    for spec, left, c, want in (({}, None, 58, 4), ({"ao_final_estimate_trials": 0}, None, 58, 0),
                                ({"ao_final_estimate_trials": 2}, None, 58, 2),
                                ({}, 100, 58, 0), ({}, 300, 58, 2), ({}, 5000, 58, 4)):
        fake = SimpleNamespace(spec=spec, root=tmp_path, ev=SimpleNamespace(confirm_ids=lambda c=c: list(range(c))))
        import unittest.mock as m
        with m.patch.object(conductor_backend.RunDir, "open",
                            return_value=SimpleNamespace(remaining_metric_calls=lambda left=left: left)):
            assert conductor_backend.RealBackend.final_estimate_trials(fake) == want, (spec, left)


# merge-resolve jobs (seen live on run_20261013_131033) ------------------------------------------
def test_proposer_metadata_never_makes_two_branches_conflict(tmp_path):
    import merge
    dirs = {}
    for name, hyp in (("base", None), ("a", '{"id": "a"}'), ("b", '{"id": "b"}')):
        d = dirs[name] = tmp_path / name
        (d / "policy").mkdir(parents=True)
        (d / "policy" / "policy.md").write_text("# P\n\nrule\n")
        if hyp:
            (d / "hypothesis.json").write_text(hyp)
    (dirs["b"] / "tools.py").write_text("x = 1\n")
    r = merge.build_merge_dir(dirs["base"], dirs["a"], dirs["b"], tmp_path / "out")
    assert r["built"], r


def test_a_merge_resolve_job_gets_a_copy_of_the_trunk_and_the_donor_path(tmp_path):
    import unittest.mock as m
    work = tmp_path / "work" / "cand_9"
    calls = []

    def sh(argv):
        calls.append([str(x) for x in argv])
        work.mkdir(parents=True)
        return 0, "", ""
    fake = SimpleNamespace(
        ctx=SimpleNamespace(work=lambda t: work), run_dir=tmp_path, root=tmp_path, project=tmp_path, spec={},
        cfg=SimpleNamespace(cost_eps=None), optimizer="mock",
        _paths=lambda j: (tmp_path / "j.log", tmp_path / "j.rc", tmp_path / "j.prompt.md"),
        _spawn=lambda j, cmd, env=None: {"pid": 1}, transcript=lambda j: tmp_path / "t.jsonl", job_usd_cap=lambda: 0,
        _inject_context=lambda work, parent: None)
    job = {"id": "j1", "kind": "merge", "tag": "cand_9", "parent": "cand_1", "parents": ["cand_1", "cand_2"],
           "conflicts": [{"where": "policy/policy.md::Rules", "trunk": ["cand_2"], "donor": ["cand_1"]}]}
    with m.patch.object(conductor_backend.act, "sh", sh), \
            m.patch.object(conductor_backend, "conductor_jobs", lambda root: []), \
            m.patch.object(conductor_backend.digest, "build", lambda *a: {}), \
            m.patch.object(conductor_backend.digest, "fit", lambda d: ({}, "")), \
            m.patch.object(conductor_backend.digest, "cand_dir", lambda rd, t: tmp_path / "candidates" / t):
        conductor_backend.RealBackend._start_llm(fake, job)
    argv = calls[0]
    assert argv[argv.index("--parent") + 1] == "cand_2", "the work dir is a copy of the conflict's trunk"
    assert argv[argv.index("--source") + 1] == str(tmp_path / "candidates" / "cand_2"), "read where the tip lives"
    assert job["parent"] == "cand_2", "register() diffs the result against the trunk it was built from"
    prompt = (tmp_path / "j.prompt.md").read_text()
    assert "policy/policy.md::Rules" in prompt and str(tmp_path / "candidates" / "cand_1") in prompt


def test_a_proposer_reads_its_parents_val_traces_and_guidance(tmp_path):
    """Seen live: conductor proposers had no ./trajectories, so every edit was written blind."""
    import unittest.mock as m
    seen = {}
    fake = SimpleNamespace(project=tmp_path, run_dir=SimpleNamespace(log_event=lambda *a, **k: seen.setdefault("warn", k)),
                           optimizer="claude-code", spec={"capabilities": ["system-prompt", "tools"],
                                                          "capability_sources": ["seed/data_model.py"]})
    with m.patch("cap_evolve.check.load_adapter", lambda p: "ADAPTER"), \
            m.patch.object(conductor_backend.harness, "_inject_optimizer_context",
                           lambda adapter, rd, work, **kw: seen.update(adapter=adapter, work=work, **kw)):
        conductor_backend.RealBackend._inject_context(fake, tmp_path / "work" / "cand_5", "cand_3")
    assert seen["split"] == "val" and seen["tag"] == "cand_3", "the PARENT's feedback-split traces, never test"
    assert seen["work"] == tmp_path / "work" / "cand_5" and seen["capabilities"] == ["system-prompt", "tools"]
    assert "warn" not in seen
