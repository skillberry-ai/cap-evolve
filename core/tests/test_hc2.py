"""HC-2: K parallel proposals per round on the shared P2 evaluator (opt-in; defaults unchanged).

No model calls: a fake evaluator stands in for ``P2Evaluator`` (whose interface it mirrors) and a fake
optimizer writes deterministic edits.
"""

import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import RunDir, harness, hc2  # noqa: E402
from cap_evolve.evaluator import ConfirmVerdict, RoundPlan, RungVerdict  # noqa: E402

F_IDS = [f"f{i}" for i in range(8)]
C_IDS = ["c0", "c1", "c2"]
FEEDBACK = {"f0": "timeout calling search tool", "f1": "timeout calling search tool again",
            "f2": "timeout in search tool", "f3": "wrong date format output",
            "f4": "date format wrong in output", "f5": "missing currency symbol",
            "f6": "currency symbol missing", "f7": "refused unsupported request"}


def _write(run_dir, split, task, tag, k, reward, fb="", split_dir=None):
    d = run_dir.rollouts / (split_dir or split)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{task}__{tag}__t{k}.json").write_text(json.dumps(
        {"input": "x", "rollout": {"task_id": task, "output": "o", "error": None},
         "score": {"reward": reward, "feedback": fb}}))


@pytest.fixture
def run_dir(tmp_path):
    from cap_evolve import Budget
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(max_iterations=5))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "SKILL.md").write_text("base rule one\nbase rule two\n")
    rd.snapshot("seed", seed)
    rd.set_best("seed")
    for t in F_IDS:
        _write(rd, "feedback", t, "seed", 0, 0.0, FEEDBACK[t])
    _write(rd, "feedback", "f0", "seed", 1, 1.0)          # f0 is flaky: a passing draw too
    for t in C_IDS:                                        # C traces leaked into the same directory
        _write(rd, "feedback", t, "seed", 0, 0.0, "secret c failure")
    return rd


class FakeRound:
    @property
    def champion(self):
        return self.state.get("champion")

    @champion.setter
    def champion(self, v):
        self.state["champion"] = v

    def __init__(self, ev, cands, round_id):
        self.ev, self.cands, self.round_id = ev, dict(cands), round_id
        self.state = {"stage": "open"}
        ev.opened.append(sorted(self.cands))

    def run_rung(self, rung, map_fn=None):
        return {c: RungVerdict(c, "advance", 0.1, 2.0, 12) for c in self.cands}

    def confirm_jobs(self):
        return [SimpleNamespace(cid=c) for c in self.cands]

    def run_job(self, job):
        pass

    def confirm(self, map_fn=None):
        return self.close_confirm()

    def _save(self):
        pass

    def close_confirm(self):
        first = sorted(self.cands)[0]
        self.champion = first if self.ev.accept else None
        return {c: ConfirmVerdict(c, "accept" if c == self.champion else "reject", 0.1, 2.0, 147)
                for c in self.cands}


class FakeEvaluator:
    proposer_split = "feedback"

    def __init__(self, accept=True, k=4):
        self.opened, self.accept, self.k = [], accept, k
        self.run_dir = None
        self.params = SimpleNamespace(dmin=0.02)
        self.validated = []

    def validate_chain(self, chain, seed_dir, *, n_trials=3, z_min=0.0):
        self.validated.append([c for c, _ in chain])
        return {"chosen": chain[0][0], "tested": [], "skipped": None}

    def final_estimate(self, champion_dir, seed_dir, *, n_trials=4):
        return {"mean": 0.1, "se": 0.05, "n": 3}

    def feedback_ids(self):
        return list(F_IDS)

    def confirm_ids(self):
        return list(C_IDS)

    def plan_round(self, k_wanted, incumbent_dir=None, *, allow_direct=False):
        return RoundPlan(min(k_wanted, self.k), 100, True)

    def _round_dir(self):
        d = self.run_dir.root / "private" / "p2"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def open_round(self, candidates, incumbent):
        d = self._round_dir()
        rid = f"r{len(list(d.glob('r*.json'))):03d}"
        (d / f"{rid}.json").write_text(json.dumps({"round_id": rid, "candidates": {c: str(p) for c, p in candidates.items()}}))
        return FakeRound(self, candidates, rid)

    def resume_round(self, round_id):
        raise AssertionError("fake never resumes")


def _optimizer(seen):
    lock = threading.Lock()

    def opt(workdir, instructions):
        with lock:
            seen.append((Path(workdir), instructions))
        n = Path(workdir).name
        (Path(workdir) / "SKILL.md").write_text(f"base rule one\nunique edit for {n} " + "x" * len(n) + "\n")
        return {"cost_usd": 0.0, "tokens": 1}
    return opt


def _loop(run_dir, ev, opt, params=None, rounds=1):
    ev.run_dir = run_dir
    ctx = harness.OptimizerContext()
    return hc2.hc2_loop(None, run_dir=run_dir, optimizer=opt, evaluator=ev,
                        params=params or hc2.HC2Params(k=3, per_cluster=2), ctx=ctx,
                        max_iterations=rounds, workers=3)


def test_k_candidates_submitted_per_round(run_dir):
    ev, seen = FakeEvaluator(), []
    out = _loop(run_dir, ev, _optimizer(seen))
    assert len(ev.opened) == 1 and len(ev.opened[0]) == 3          # K=3 candidates in ONE round
    assert out["accepts"] == 1 and run_dir.best_id == ev.opened[0][0]
    assert len({i for _, i in seen}) == 3                           # distinct clusters, distinct prompts


def test_k_shrinks_to_plan(run_dir):
    ev = FakeEvaluator(k=2)
    _loop(run_dir, ev, _optimizer([]))
    assert len(ev.opened[0]) == 2


def test_c_traces_never_reach_the_proposer(run_dir):
    seen = []
    _loop(run_dir, FakeEvaluator(), _optimizer(seen))
    for wd, instr in seen:
        for sub in ("trajectories", "contrast"):
            for f in (wd / sub).rglob("*") if (wd / sub).exists() else []:
                assert not any(f.name.startswith(c + "__") for c in C_IDS), f
        assert "secret c failure" not in instr
    # and the scrub removes a C file placed there by anything else
    wd = run_dir.root / "work" / "x" / "trajectories"
    wd.mkdir(parents=True)
    (wd / "c1__seed__t0.json").write_text("{}")
    (wd / "f1__seed__t0.json").write_text("{}")
    assert hc2.scrub_confirm_traces(wd.parent, C_IDS) == 1 and (wd / "f1__seed__t0.json").exists()


def test_read_traces_filters_to_feedback_ids(run_dir):
    tr = hc2.read_traces(run_dir, ("feedback",), F_IDS, hc2.incumbent_tag_ok("seed"))
    assert {t.task_id for t in tr} <= set(F_IDS)


def test_contrastive_pair_for_flaky_task(run_dir):
    tr = hc2.read_traces(run_dir, ("feedback",), F_IDS, hc2.incumbent_tag_ok("seed"))
    pairs = hc2.contrastive_pairs(tr, set(F_IDS), 3)
    assert [(g.task_id, g.reward, b.reward) for g, b in pairs] == [("f0", 1.0, 0.0)]


def test_clusters_group_similar_failures(run_dir):
    tr = hc2.read_traces(run_dir, ("feedback",), F_IDS, hc2.incumbent_tag_ok("seed"))
    cl = hc2.cluster_failures(hc2.failing_tasks(tr), F_IDS, 0.3)
    assert len(cl) >= 3
    assert any({"f3", "f4"} <= set(c) for c in cl)


def test_diversity_gate_rejects_near_duplicate(tmp_path):
    parent = tmp_path / "p"
    parent.mkdir()
    (parent / "SKILL.md").write_text("a\nb\nc\n")
    c1, c2, c3 = (tmp_path / n for n in ("c1", "c2", "c3"))
    for c, body in ((c1, "a\nb\nc\nuse the guard on country\nvalidate exchange items\n"),
                    (c2, "a\nb\nc\nuse the guard on country\nvalidate exchange items now\n"),
                    (c3, "a\nb\nc\nformat dates as iso\n")):
        c.mkdir()
        (c / "SKILL.md").write_text(body)
    d1, d2, d3 = (hc2.diff_lines(parent, c) for c in (c1, c2, c3))
    assert hc2.near_duplicate(d2, [d1], 0.3) == 0
    assert hc2.near_duplicate(d3, [d1], 0.3) is None
    assert hc2.near_duplicate(d1, [d1], 0.99) == 0


def test_loop_drops_duplicate_of_rejected_diff_at_no_rollout_cost(run_dir):
    ev = FakeEvaluator(accept=False)

    def same_edit(workdir, instructions):
        (Path(workdir) / "SKILL.md").write_text("base rule one\nthe same edit everywhere\n")

    _loop(run_dir, ev, same_edit, rounds=1)      # round 1: siblings duplicate each other -> one live
    assert len(ev.opened[0]) == 1
    n_before = len(ev.opened)
    _loop(run_dir, ev, same_edit, rounds=2)      # round 2: now a near-duplicate of a rejected diff
    assert len(ev.opened) == n_before            # nothing sent to the evaluator


def test_consolidation_mode_is_opt_in(run_dir):
    seen = []
    _loop(run_dir, FakeEvaluator(), _optimizer(seen), hc2.HC2Params(k=2, consolidate=True))
    assert all((wd / "cross_trace_summary.md").exists() and "Consolidation mode" in i for wd, i in seen)
    seen.clear()
    _loop(run_dir, FakeEvaluator(), _optimizer(seen), hc2.HC2Params(k=2))
    assert not any((wd / "cross_trace_summary.md").exists() or "Consolidation mode" in i for wd, i in seen)


def test_defaults_unchanged():
    assert hc2.HC2Params.from_spec({}) is None
    assert hc2.HC2Params.from_spec({"hc2_k": 3}) is None          # off unless hc2: true
    with pytest.raises(ValueError):
        hc2.HC2Params.from_spec({"hc2": True})                    # needs P2 + pooled
    p = hc2.HC2Params.from_spec({"hc2": True, "promotion_rule": "P2", "split_mode": "pooled",
                                 "hc2_k": 5, "hc2_consolidate": True})
    assert p.k == 5 and p.consolidate and p.retries == 1


def test_hill_climb_cli_has_hc2_off_by_default():
    import importlib.util
    path = REPO / "skills/algorithms/hill-climb/scripts/run.py"
    src = path.read_text()
    assert '"--hc2", default=None' in src and "if args.hc2:" in src


def test_workers_forwarded_to_baseline_and_algorithm(monkeypatch, tmp_path):
    src = (REPO / "core/cap_evolve/cli.py").read_text()
    assert 'base_cmd += ["--workers"' in src and 'alg_cmd += ["--workers"' in src
    assert 'spec.get("workers")' in src
    bsrc = (REPO / "skills/phases/baseline/scripts/run.py").read_text()
    assert "workers=args.workers" in bsrc


def test_baseline_passes_workers_to_evaluations(tmp_path, monkeypatch):
    from cap_evolve import Budget
    rd = RunDir.create(tmp_path, ts="b", budget=Budget(max_iterations=1))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "f.txt").write_text("x")
    seen = []

    def fake_eval(adapter, cdir, **kw):
        seen.append((kw["split"], kw.get("workers")))
        from cap_evolve.loop import SplitResult
        return SplitResult(split=kw["split"], reward=0.5, stderr=0.0, n_tasks=1, n_scored=1)

    monkeypatch.setattr(harness, "evaluate_candidate", fake_eval)
    monkeypatch.setattr(RunDir, "read_splits", lambda self: SimpleNamespace(train=["a"], val=["b"], test=["c"]))
    harness.baseline(None, seed, run_dir=rd, workers=4)
    assert seen == [("val", 4), ("train", 4)]


# ---- against the real P2 evaluator --------------------------------------------------------------

def test_hc2_round_on_the_real_evaluator(tmp_path):
    from p2_fakes import make_run
    from cap_evolve import evaluator, harness as h, promotion
    adapter, rd = make_run(tmp_path, n_train=24, n_val=24, default=0.4, max_metric_calls=3000)
    h.baseline_pooled(adapter, tmp_path / "seed", run_dir=rd, n_trials=2)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})
    ev = evaluator.P2Evaluator(adapter, rd, params)
    seen = []

    def opt(workdir, instructions):
        seen.append(Path(workdir))
        i = len(seen)
        cfg = json.loads((Path(workdir) / "cfg.json").read_text())
        cfg.update(default=0.85 if i == 1 else 0.4, salt=i)        # only the first proposal helps
        (Path(workdir) / "cfg.json").write_text(json.dumps(cfg, indent=1))

    out = hc2.hc2_loop(adapter, run_dir=rd, optimizer=opt, evaluator=ev,
                       params=hc2.HC2Params(k=3, per_cluster=2), ctx=harness.OptimizerContext(),
                       max_iterations=1, workers=2)
    assert len(seen) >= 3 and out["iterations"] >= 3
    assert out["accepts"] == 1 and rd.best_id != "seed"
    # FINAL phase: champion vs seed on C, written to summary.json, inside max_metric_calls, paid once
    est = out["internal_estimate"]
    assert est["n"] and json.loads((rd.root / "summary.json").read_text())["internal_estimate"] == est
    assert rd.spent.metric_calls <= 3000
    paid = rd.spent.metric_calls
    assert hc2.final_estimate(ev, rd) == est and rd.spent.metric_calls == paid
    c_ids = set(ev.confirm_ids())
    for wd in seen:
        for f in (wd / "trajectories").glob("*.json"):
            assert f.name.split("__")[0] not in c_ids


def test_split_to_k_gives_distinct_slices_when_clusters_are_few():
    out = hc2.split_to_k([["a", "b", "c", "d"]], 3)
    assert len(out) == 3 and sorted(sum(out, [])) == ["a", "b", "c", "d"]
    assert hc2.split_to_k([["a"]], 3) == [["a"]]


def test_final_estimate_skipped_when_unfunded_and_never_over_budget(tmp_path):
    from p2_fakes import make_run
    from cap_evolve import evaluator, harness as h, promotion
    adapter, rd = make_run(tmp_path, n_train=24, n_val=24, default=0.4, max_metric_calls=100)
    h.baseline_pooled(adapter, tmp_path / "seed", run_dir=rd, n_trials=2)
    ev = evaluator.P2Evaluator(adapter, rd, promotion.P2Params.from_spec({"promotion_rule": "P2"}))
    assert hc2.final_estimate(ev, rd) is None                    # champion is the seed: nothing to estimate
    rd.snapshot("cand_0001", tmp_path / "seed")
    rd.set_best("cand_0001")
    out = hc2.final_estimate(ev, rd)
    assert out["skipped"] == "budget" and rd.spent.metric_calls <= 100


# ---- review fixes (PR-4b) -----------------------------------------------------------------------

def _capped_fake(run_dir, **kw):
    ev = FakeEvaluator(**kw)
    ev.remaining_at_plan = []
    orig = ev.plan_round

    def plan(k_wanted, incumbent_dir=None, **kw):
        ev.remaining_at_plan.append(run_dir.remaining_metric_calls())
        return orig(k_wanted, incumbent_dir, **kw)
    ev.plan_round = plan
    return ev


def test_one_round_is_one_iteration_and_one_stall_step(run_dir):
    _loop(run_dir, FakeEvaluator(accept=False), _optimizer([]))
    assert run_dir.spent.iterations == 1 and run_dir.spent.stall == 1       # 3 candidates, one round
    _loop(run_dir, FakeEvaluator(accept=True), _optimizer([]), rounds=2)
    assert run_dir.spent.iterations == 2 and run_dir.spent.stall == 0       # an accepted round resets it


def test_candidate_ids_do_not_collide_across_rounds(run_dir):
    ev = FakeEvaluator(accept=False)
    _loop(run_dir, ev, _optimizer([]), rounds=2)
    flat = [c for o in ev.opened for c in o]
    assert len(flat) == len(set(flat)) >= 2


def test_final_estimate_cost_is_held_while_planning(run_dir):
    run_dir.update_budget(max_metric_calls=1000)
    ev = _capped_fake(run_dir)
    _loop(run_dir, ev, _optimizer([]))
    assert ev.remaining_at_plan[0] == 1000 - run_dir.spent.metric_calls - hc2.final_estimate_cost(ev) \
        or ev.remaining_at_plan[0] == 1000 - hc2.final_estimate_cost(ev)
    assert run_dir.reserved_metric_calls() == 0                              # released afterwards


def test_final_estimate_needs_both_arms_funded(run_dir):
    run_dir.update_budget(max_metric_calls=1000)
    run_dir.update_spent(metric_calls=1000 - hc2.final_estimate_cost(FakeEvaluator()) + 1)
    run_dir.snapshot("cand_0009", run_dir.candidate_dir("seed"))
    run_dir.set_best("cand_0009")
    ev = FakeEvaluator()
    ev.final_estimate = lambda *a, **k: pytest.fail("must not start one arm")
    out = hc2.final_estimate(ev, run_dir)
    assert out["skipped"] == "budget"


def test_retry_accumulates_every_attempts_cost_and_keeps_full_context(run_dir):
    seen = []
    calls = []

    def opt(workdir, instructions):
        calls.append(instructions)
        seen.append(Path(workdir))
        dup = "duplicated an edit" not in instructions
        (Path(workdir) / "SKILL.md").write_text("base rule one\n" + ("the common edit\n" if dup else "a fresh idea\n"))
        return {"cost_usd": 0.5, "tokens": 10}

    ref = run_dir.root / "ref"
    ref.mkdir()
    (ref / "SKILL.md").write_text("base rule one\nthe common edit\n")
    hc2.RejectedDiffs(run_dir).add("cand_old", hc2.diff_lines(run_dir.candidate_dir("seed"), ref))
    before = run_dir.spent.optimizer_tokens
    _loop(run_dir, FakeEvaluator(), opt, hc2.HC2Params(k=1, consolidate=True))
    assert len(calls) == 2 and run_dir.spent.optimizer_tokens - before == 20       # both attempts paid
    assert "Consolidation mode" in calls[1] and (seen[-1] / "cross_trace_summary.md").exists()
    assert "fresh idea" in (seen[-1] / "SKILL.md").read_text()


def test_k1_round(run_dir):
    ev = FakeEvaluator()
    out = _loop(run_dir, ev, _optimizer([]), hc2.HC2Params(k=1))
    assert [len(o) for o in ev.opened] == [1] and out["accepts"] == 1


def test_an_unconfirmed_candidate_can_be_reproposed(run_dir):
    class Pending(FakeRound):
        def close_confirm(self):
            self.champion = None
            return {c: ConfirmVerdict(c, "unconfirmed") for c in self.cands}

    class Ev(FakeEvaluator):
        def open_round(self, candidates, incumbent):
            r = super().open_round(candidates, incumbent)
            r.__class__ = Pending
            return r

    def same(workdir, instructions):
        (Path(workdir) / "SKILL.md").write_text("base rule one\nthe edit that could not be confirmed\n")

    ev = Ev()
    _loop(run_dir, ev, same, hc2.HC2Params(k=1), rounds=2)
    assert len(ev.opened) == 2                           # round 2 was not blocked by the diversity gate


def test_inject_never_lets_a_c_trace_in_from_any_rollout_dir(run_dir):
    for sd in ("train", "val", "feedback"):
        for c in C_IDS:
            _write(run_dir, sd, c, "seed", 0, 0.0, "secret c failure")
    seen = []
    _loop(run_dir, FakeEvaluator(), _optimizer(seen))
    for wd, instr in seen:
        for f in wd.rglob("*"):
            if f.is_file():
                assert not any(f.name.startswith(c + "__") for c in C_IDS), f
                try:
                    assert "secret c failure" not in f.read_text()
                except UnicodeDecodeError:
                    pass


def test_workers_bound_total_concurrency(run_dir):
    ev = FakeEvaluator()
    ev.workers = 8
    _loop(run_dir, ev, _optimizer([]))
    assert ev.workers == 1                               # jobs fan out once, in the loop's own map


def test_shingle_overlap_catches_a_reworded_copy(tmp_path):
    p = tmp_path / "p"
    p.mkdir()
    (p / "S.md").write_text("a\n")
    a, b = tmp_path / "a", tmp_path / "b"
    for d, t in ((a, "always validate the country code before shipping any exchange order"),
                 (b, "always validate the country code before shipping any exchange order today")):
        d.mkdir()
        (d / "S.md").write_text("a\n" + t + "\n")
    da, db = hc2.diff_lines(p, a), hc2.diff_lines(p, b)
    assert len(da & db) < len(da | db)                   # the lines differ ...
    assert hc2.diff_overlap(da, db) >= 0.6               # ... the shingles still match


def test_cli_forwards_workers_to_baseline_and_algorithm(tmp_path, monkeypatch):
    """Behavioural: run the real CLI on the toy project with ``workers: 3``; the eval and the
    algorithm both report 3."""
    import shutil
    from cap_evolve import cli
    ex = REPO / "examples" / "toy_calc"
    monkeypatch.setenv("CAPEVOLVE_CORE", str(REPO / "core"))
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(REPO / "skills"))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(ex))
    monkeypatch.setenv("CAPEVOLVE_MOCK_SCRIPT", str(ex / "mock_script.json"))
    monkeypatch.delenv("CAPEVOLVE_WORKERS", raising=False)
    project = tmp_path / ".capevolve" / "project"
    (project / "adapters").mkdir(parents=True)
    shutil.copy(ex / "adapter.py", project / "adapters" / "adapter.py")
    shutil.copytree(ex / "capability", tmp_path / "seed_capability")
    spec = project / "capevolve.yaml"
    spec.write_text((REPO / "templates/project/capevolve.yaml").read_text() + "\nworkers: 3\n")
    assert cli.main(["run", "--spec", str(spec), "--project", str(project), "--dashboard", "off",
                     "--run-ts", "w3"]) == 0
    ev = [json.loads(l) for l in (tmp_path / ".capevolve/run_w3/events.jsonl").read_text().splitlines()]
    starts = [e for e in ev if e.get("kind") == "eval_start" and (e.get("tag") == "seed" or e.get("split") == "val")]   # baseline + search, not finalize
    assert starts and {e["workers"] for e in starts} == {3}          # baseline AND candidate evals
    assert any(e.get("kind") == "parallel" and e.get("workers") == 3 for e in ev)


def test_hc2_resumes_an_interrupted_round_without_reproposing(tmp_path, monkeypatch):
    from p2_fakes import make_run
    from cap_evolve import evaluator, harness as h, promotion

    class Boom(Exception):
        pass

    adapter, rd = make_run(tmp_path, n_train=24, n_val=24, default=0.4, max_metric_calls=4000)
    h.baseline_pooled(adapter, tmp_path / "seed", run_dir=rd, n_trials=2)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})
    calls = []

    def opt(workdir, instructions):
        calls.append(Path(workdir).name)
        i = len(calls)
        cfg = json.loads((Path(workdir) / "cfg.json").read_text())
        cfg.update(default=0.85 if i == 1 else 0.4, salt=i)
        (Path(workdir) / "cfg.json").write_text(json.dumps(cfg, indent=1))

    state = {"crash": True}
    orig = evaluator.Round.run_job

    def flaky(self, job):
        if state["crash"] and job.stage == "confirm":
            raise Boom("killed mid-confirmation")
        return orig(self, job)

    monkeypatch.setattr(evaluator.Round, "run_job", flaky)
    kw = dict(optimizer=opt, params=hc2.HC2Params(k=3, per_cluster=2), ctx=harness.OptimizerContext(),
              max_iterations=1, workers=2)
    with pytest.raises(Boom):
        hc2.hc2_loop(adapter, run_dir=rd, evaluator=evaluator.P2Evaluator(adapter, rd, params), **kw)
    assert (rd.root / "hc2_pending.json").exists() and rd.best_id == "seed"
    n_proposed, spent = len(calls), rd.spent.metric_calls

    state["crash"] = False
    out = hc2.hc2_loop(adapter, run_dir=rd, evaluator=evaluator.P2Evaluator(adapter, rd, params), **kw)
    assert len(calls) == n_proposed                                   # nothing re-proposed
    assert len(list(evaluator.P2Evaluator(adapter, rd, params)._round_dir().glob("r*.json"))) == 1   # same round
    assert not (rd.root / "hc2_pending.json").exists()
    assert out["accepts"] == 1 and rd.best_id != "seed"
    assert rd.spent.iterations == 1
    assert rd.spent.metric_calls >= spent


# ---- configurable final-estimate reserve --------------------------------------------------------

def test_final_estimate_trials_default_and_spec():
    base = {"hc2": True, "promotion_rule": "P2", "split_mode": "pooled"}
    assert hc2.HC2Params.from_spec(base).final_estimate_trials == 4
    assert hc2.HC2Params.from_spec({**base, "hc2_final_estimate_trials": 0}).final_estimate_trials == 0
    with pytest.raises(ValueError):
        hc2.HC2Params.from_spec({**base, "hc2_final_estimate_trials": -1})


def test_default_still_holds_the_reserve_while_planning(run_dir):
    run_dir.update_budget(max_metric_calls=1000)
    ev = _capped_fake(run_dir)
    _loop(run_dir, ev, _optimizer([]))
    assert ev.remaining_at_plan[0] == 1000 - hc2.final_estimate_cost(ev)


def test_zero_trials_reserves_nothing_and_skips_the_estimate(run_dir):
    run_dir.update_budget(max_metric_calls=1000)
    ev = _capped_fake(run_dir)
    ev.final_estimate = lambda *a, **k: pytest.fail("final_estimate must not be called")
    out = _loop(run_dir, ev, _optimizer([]), hc2.HC2Params(k=3, per_cluster=2, final_estimate_trials=0))
    assert ev.remaining_at_plan[0] == 1000                       # plan_round sees the full budget
    assert out["internal_estimate"] == {"skipped": "disabled"}
    assert not (run_dir.root / "internal_estimate.json").exists()
    events = [json.loads(l) for l in run_dir.events_path.read_text().splitlines()]
    assert any(e["kind"] == "p2_final_estimate" and e.get("skipped") == "disabled" for e in events)


def test_non_default_trials_are_passed_through(run_dir):
    seen = []
    ev = FakeEvaluator()
    ev.final_estimate = lambda c, s, *, n_trials=4: seen.append(n_trials) or {"mean": 0.1, "se": 0.0, "n": 1}
    _loop(run_dir, ev, _optimizer([]), hc2.HC2Params(k=2, final_estimate_trials=2))
    assert seen == [2]


def test_cli_forwards_the_key_in_the_hc2_json():
    src = (REPO / "core/cap_evolve/cli.py").read_text()
    assert 'k.startswith(("hc2_", "p2_"))' in src             # every hc2_* key travels in --hc2


# ---- broad slot, cross-cluster traces, merged survivors -------------------------------------------

def _recording_optimizer(seen, files=False):
    lock = threading.Lock()

    def opt(workdir, instructions):
        wd = Path(workdir)
        with lock:
            seen.append({"name": wd.name, "instr": instructions,
                         "traj": sorted(p.name.split("__")[0] for p in (wd / "trajectories").glob("*.json"))})
        if files:
            (wd / f"{wd.name}.md").write_text(f"edit from {wd.name}\n")
        else:
            (wd / "SKILL.md").write_text(f"base rule one\nunique edit for {wd.name} " + "x" * len(wd.name) + "\n")
        return {"cost_usd": 0.0, "tokens": 1}
    return opt


def test_proposals_see_every_failure_type_and_the_broad_slot_sees_all(run_dir):
    seen = []
    params = hc2.HC2Params(k=3, per_cluster=1, broad_slot=True, cross_traces=1, minibatch=8)
    _loop(run_dir, FakeEvaluator(), _recording_optimizer(seen), params=params)
    assert len(seen) == 3
    broad = [s for s in seen if "ALL failure types" in s["instr"] and "no single primary cluster" in s["instr"]]
    assert len(broad) == 1
    assert set(broad[0]["traj"]) == set(F_IDS)                   # every failing F task, one trace each
    for s in seen:
        assert not set(s["traj"]) & set(C_IDS)                   # C never leaks
        assert "address only the cluster below" not in s["instr"]
        assert "largest expected reward gain" in s["instr"]
    cluster = [s for s in seen if s not in broad]
    assert len(cluster) == 2
    for s in cluster:
        assert len(s["traj"]) > 1                                # primary cluster plus other clusters' traces


def test_cross_traces_zero_restores_the_single_cluster_view(run_dir):
    seen = []
    params = hc2.HC2Params(k=2, per_cluster=2, cross_traces=0, minibatch=8)
    _loop(run_dir, FakeEvaluator(), _recording_optimizer(seen), params=params)
    assert all(len(s["traj"]) <= 2 for s in seen)


def test_merge_trees_three_way(tmp_path):
    def tree(name, files):
        d = tmp_path / name
        for rel, body in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(body)
        return d
    base = tree("base", {"a.md": "l1\nl2\nl3\nl4\nl5\nl6\n", "b.md": "b\n"})
    ours = tree("ours", {"a.md": "l1\nl2\nl3\nl4\nl5\nl6\n", "b.md": "b\n"})
    v1 = tree("v1", {"a.md": "L1\nl2\nl3\nl4\nl5\nl6\n", "b.md": "b\n", "new1.md": "n1\n"})
    v2 = tree("v2", {"a.md": "l1\nl2\nl3\nl4\nl5\nL6\n", "b.md": "b\n"})
    v3 = tree("v3", {"a.md": "X\nl2\nl3\nl4\nl5\nl6\n", "b.md": "b2\n"})       # conflicts with v1 on line 1
    out = tmp_path / "out"
    res = hc2.merge_trees(base, ours, [("v1", v1), ("v2", v2), ("v3", v3)], out)
    assert (out / "a.md").read_text() == "L1\nl2\nl3\nl4\nl5\nL6\n"            # clean line-level merge
    assert (out / "new1.md").read_text() == "n1\n"
    assert (out / "b.md").read_text() == "b2\n"                                   # only v3 touched b.md
    assert res["merged"] == ["v1", "v2", "v3"] and res["skipped"] == ["v3:a.md"]  # v3's conflicting hunk is not applied


def test_survivors_of_a_round_are_merged_into_one_candidate_of_the_next(run_dir):
    seen = []
    params = hc2.HC2Params(k=3, per_cluster=1, merge_survivors=True, minibatch=8, final_estimate_trials=0)
    ev = FakeEvaluator(accept=False)
    out = _loop(run_dir, ev, _recording_optimizer(seen, files=True), params=params, rounds=2)
    assert len(ev.opened) == 2 and len(ev.opened[0]) == 3
    r2 = ev.opened[1]
    assert len(r2) == 3                                           # K stays 3: the merge takes one slot
    merged = [c for c in r2 if c not in {s["name"] for s in seen[3:]}]
    assert len(merged) == 1 and len(seen) == 3 + 2                # only K-1 proposer calls in round 2
    tree = run_dir.root / "work" / merged[0]
    assert len(list(tree.glob("cand_*.md"))) >= 2                 # edits of >= 2 round-1 candidates combined
    events = [json.loads(l) for l in run_dir.events_path.read_text().splitlines()]
    assert any(e["kind"] == "hc2_merge" and len(e["sources"]) >= 2 for e in events)
    assert out["iterations"] == 6                                 # 3 + 3 candidates recorded


def test_merge_is_off_by_default(run_dir):
    seen = []
    ev = FakeEvaluator(accept=False)
    _loop(run_dir, ev, _recording_optimizer(seen, files=True), params=hc2.HC2Params(k=3, per_cluster=1, minibatch=8),
          rounds=2)
    assert len(seen) == 6 and not (run_dir.root / "hc2_merge_pool.json").exists()


def test_cheap_accept_skips_the_round_confirmation_and_validates_the_chain_once(run_dir):
    ev, seen = FakeEvaluator(accept=False), []
    params = hc2.HC2Params(k=2, per_cluster=2, minibatch=8, cheap_accept=True, cheap_z=1.0)
    out = _loop(run_dir, ev, _recording_optimizer(seen), params=params, rounds=1)
    assert out["accepts"] == 1                                   # cheap accept, the fake never ran a C confirmation
    assert run_dir.best_id != "seed"
    assert ev.validated == [[run_dir.best_id]]                    # the accepted chain is validated once, at the end
    assert out["chain_validation"]["chosen"] == run_dir.best_id
    assert "internal_estimate" not in out


def test_cheap_accept_is_off_by_default(run_dir):
    ev = FakeEvaluator(accept=False)
    out = _loop(run_dir, ev, _recording_optimizer([]), rounds=1)
    assert out["accepts"] == 0 and not ev.validated and "chain_validation" not in out
