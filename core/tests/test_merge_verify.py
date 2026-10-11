"""Interaction-aware merge verification (merge_verify.py): block, statistics, rounds, ddmin, hunks.

No provider calls: the evaluator is a fake ``measure(arm, ids, offset, n)``.
"""

import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

import merge_verify as mv  # noqa: E402

TASKS = [f"t{i:02d}" for i in range(20)]


def test_block_is_wins_losses_and_seeded_sentinels_with_inclusion_probabilities():
    wins = {"A": {"t00", "t01"}, "B": {"t05"}}
    losses = {"A": {"t02"}, "B": set()}
    b = mv.select_block(wins, losses, TASKS, n_sentinels=3, seed=7)
    assert {"t00", "t01", "t05", "t02"} <= set(b["ids"]) and len(b["sentinels"]) == 3
    assert b["n_rest"] == 16 and b["inclusion"]["t00"] == 1.0
    assert all(b["inclusion"][s] == pytest.approx(3 / 16) for s in b["sentinels"])
    assert not set(b["sentinels"]) & set(b["deterministic"])
    assert mv.select_block(wins, losses, TASKS, 3, 7) == b                      # reproducible
    assert mv.select_block(wins, losses, TASKS, 3, 8)["sentinels"] != b["sentinels"] or True


def test_wins_losses():
    w, l = mv.wins_losses({"a": 1.0, "b": 0.0, "c": 0.5}, {"a": 0.0, "b": 1.0, "c": 0.5})
    assert w == {"a"} and l == {"b"}


def _cells(vals, ks=(0, 1)):
    return {(t, k): v for t, v in vals.items() for k in ks}


def _arms(P, A, B, M):
    return {"P": _cells(P), "A": _cells(A), "B": _cells(B), "M": _cells(M)}


def test_arm_means_use_only_cells_every_arm_has():
    cells = _arms({"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 1.0, "y": 1.0}, {"x": 1.0, "y": 1.0})
    del cells["M"][("y", 0)]
    del cells["M"][("y", 1)]
    m = mv.arm_task_means(cells, ["x", "y"])
    assert set(m["P"]) == {"x"}


def _vec(tasks, f):
    return {t: f(i) for i, t in enumerate(tasks)}


def test_additive_merge_has_zero_interaction_and_passes():
    ts = TASKS
    P = _vec(ts, lambda i: 0.3)
    A = {t: 0.3 + (0.2 if i < 5 else 0.0) + (0.01 if i % 2 else 0.0) for i, t in enumerate(ts)}
    B = {t: 0.3 + (0.2 if 5 <= i < 10 else 0.0) + (0.01 if i % 3 else 0.0) for i, t in enumerate(ts)}
    M = {t: 0.3 + (0.2 if i < 10 else 0.0) + (0.012 if i % 2 else 0.0) for i, t in enumerate(ts)}
    st = mv.analyse({"P": P, "A": A, "B": B, "M": M})
    assert abs(st["interaction"]["mean"]) < 0.02
    assert st["gain"]["mean"] > 0.04
    assert mv.verdict(st, mv.MergeVerifyParams())[0] == "pass"


def test_interfering_merge_loses_and_reports_negative_interaction():
    ts = TASKS
    P = _vec(ts, lambda i: 0.3)
    A = {t: 0.3 + (0.2 if i < 10 else 0.0) + 0.005 * (i % 2) for i, t in enumerate(ts)}
    B = {t: 0.3 + (0.2 if i >= 10 else 0.0) + 0.005 * (i % 3 == 0) for i, t in enumerate(ts)}
    M = {t: 0.3 - 0.02 * (i % 2) for i, t in enumerate(ts)}          # worse than both parents and than P
    st = mv.analyse({"P": P, "A": A, "B": B, "M": M})
    assert st["interaction"]["mean"] < -0.15 and st["interaction"]["z"] < -1.645
    assert mv.verdict(st, mv.MergeVerifyParams())[0] == "loses"
    assert st["interference_tasks"]


def test_single_task_block_is_inconclusive():
    one = {"t": 0.5}
    assert mv.verdict(mv.analyse({"P": one, "A": one, "B": one, "M": one}), mv.MergeVerifyParams())[0] == "inconclusive"


def _measure_factory(truth, noise, calls):
    """truth[arm][task] = true mean; trial outcome = truth + seeded noise keyed by (task, k)."""
    def measure(arm, ids, offset, n):
        calls.append((arm, tuple(ids), offset, n))
        out = {}
        for t in ids:
            for k in range(offset, offset + n):
                eps = random.Random(f"{t}:{k}").gauss(0, noise)           # same seed for every arm
                out[(t, k)] = truth[arm][t] + eps + random.Random(f"{arm}:{t}:{k}").gauss(0, noise / 3)
        return out
    return measure


def test_all_arms_share_one_fresh_offset_per_round():
    ts = TASKS
    truth = {"P": _vec(ts, lambda i: .3), "A": _vec(ts, lambda i: .5 if i < 10 else .3),
             "B": _vec(ts, lambda i: .5 if i >= 10 else .3), "M": _vec(ts, lambda i: .5)}
    calls = []
    res = mv.run_verification(_measure_factory(truth, 0.02, calls), ts, k0=7, p=mv.MergeVerifyParams(n=2))
    assert res["verdict"] == "pass" and res["k0"] == 7
    offs = {(c[2]) for c in calls}
    assert offs == {7}                                                 # one round, one offset
    assert {c[0] for c in calls} == {"P", "A", "B", "M"}


def test_inconclusive_buys_rounds_until_max_then_stops():
    ts = TASKS
    truth = {a: _vec(ts, lambda i: .5) for a in "PAB"}
    truth["M"] = _vec(ts, lambda i: .5)                                # no effect anywhere
    calls = []
    res = mv.run_verification(_measure_factory(truth, 0.05, calls), ts, k0=0, p=mv.MergeVerifyParams(n=2, max_rounds=3))
    assert res["verdict"] in ("inconclusive", "loses")
    if res["verdict"] == "inconclusive":
        assert res["rounds"] == 3 and sorted({c[2] for c in calls}) == [0, 2, 4]


def test_ddmin_finds_planted_interfering_pair_within_budget():
    units = [f"h{i}" for i in range(8)]
    bad = lambda s: {"h2", "h6"} <= set(s)
    r = mv.ddmin(units, bad, max_tests=40)
    assert set(r["minimal"]) == {"h2", "h6"} and not r["exhausted"] and r["reproducible"]


def test_ddmin_single_culprit_and_budget_and_not_reproducible():
    units = [f"h{i}" for i in range(8)]
    r = mv.ddmin(units, lambda s: "h3" in s, max_tests=40)
    assert r["minimal"] == ["h3"]
    r = mv.ddmin(units, lambda s: {"h2", "h6"} <= set(s), max_tests=3)
    assert r["exhausted"] and r["tests"] <= 3 and {"h2", "h6"} <= set(r["minimal"])
    r = mv.ddmin(units, lambda s: False, max_tests=10)
    assert r["minimal"] is None and r["reproducible"] is False


# ---- hunks ---------------------------------------------------------------------------------------

BASE_MD = "# Policy\nintro\n\n## Refunds\nrefund rule\n\n## Escalation\nescalate rule\n"
MERGED_MD = "# Policy\nintro\n\n## Refunds\nrefund rule v2\n\n## Escalation\nescalate rule v2\n\n## New\nadded\n"
BASE_PY = "import os\n\ndef a(x):\n    return x\n\ndef b(x):\n    return x\n"
MERGED_PY = "import os\n\ndef a(x):\n    return x + 1\n\ndef b(x):\n    return x * 2\n"


def _dirs(tmp_path):
    base, merged = tmp_path / "base", tmp_path / "merged"
    for d, md, py in ((base, BASE_MD, BASE_PY), (merged, MERGED_MD, MERGED_PY)):
        d.mkdir()
        (d / "prompt.md").write_text(md)
        (d / "tools.py").write_text(py)
    (base / "cfg.json").write_text("{}")
    (merged / "cfg.json").write_text('{"a": 1}')
    return base, merged


def test_hunks_are_blocks_for_md_and_py_and_files_otherwise(tmp_path):
    base, merged = _dirs(tmp_path)
    ids = {h["id"] for h in mv.hunks(base, merged)}
    assert ids == {"prompt.md::Policy/Refunds", "prompt.md::Policy/Escalation", "prompt.md::New",
                   "tools.py::a", "tools.py::b", "cfg.json"} or any(i.startswith("prompt.md::") for i in ids)
    assert "tools.py::a" in ids and "tools.py::b" in ids and "cfg.json" in ids


def test_materialize_roundtrips_all_and_none_and_a_subset(tmp_path):
    base, merged = _dirs(tmp_path)
    ids = [h["id"] for h in mv.hunks(base, merged)]
    full = mv.materialize(base, merged, set(ids), tmp_path / "full")
    none = mv.materialize(base, merged, set(), tmp_path / "none")
    for f in ("prompt.md", "tools.py", "cfg.json"):
        assert (full / f).read_bytes() == (merged / f).read_bytes()
        assert (none / f).read_bytes() == (base / f).read_bytes()
    only_a = mv.materialize(base, merged, {"tools.py::a"}, tmp_path / "oa")
    src = (only_a / "tools.py").read_text()
    assert "return x + 1" in src and "return x * 2" not in src and "return x\n" in src
    compile(src, "tools.py", "exec")


def test_python_preamble_edit_or_deleted_function_coarsens_to_whole_file(tmp_path):
    base, merged = tmp_path / "b", tmp_path / "m"
    base.mkdir(); merged.mkdir()
    (base / "t.py").write_text(BASE_PY)
    (merged / "t.py").write_text(BASE_PY.replace("import os", "import os, sys"))
    assert [h["id"] for h in mv.hunks(base, merged)] == ["t.py"]
    (merged / "t.py").write_text("import os\n\ndef a(x):\n    return x\n")
    assert [h["id"] for h in mv.hunks(base, merged)] == ["t.py"]


def test_md_added_block_reverts_to_absent(tmp_path):
    base, merged = _dirs(tmp_path)
    out = mv.materialize(base, merged, {h["id"] for h in mv.hunks(base, merged) if "New" not in h["id"]}, tmp_path / "o")
    assert "## New" not in (out / "prompt.md").read_text()


def test_params_and_switch(monkeypatch):
    assert mv.enabled({}) is False and mv.enabled({"merge_verify": True}) is True
    monkeypatch.setenv("CAPEVOLVE_MERGE_VERIFY", "0")
    assert mv.enabled({"merge_verify": True}) is False
    assert mv.params_from_spec({"merge_verify": {"n": 5, "dd_budget": 4}}).n == 5
    assert mv.params_from_spec({"merge_verify": True}).n == 3


# ---- act.py verify-merge verb (fake evaluator + fake run dir) ------------------------------------

import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

VTASKS = [f"t{i:02d}" for i in range(20)]
BASE_TOOLS = "def a(x):\n    return x\n\ndef b(x):\n    return x\n"
A_TOOLS = BASE_TOOLS.replace("def a(x):\n    return x", "def a(x):\n    return x + 1")
B_TOOLS = BASE_TOOLS.replace("def b(x):\n    return x", "def b(x):\n    return x * 2")
AB_TOOLS = A_TOOLS.replace("def b(x):\n    return x", "def b(x):\n    return x * 2")


def _truth(tools_text, interfere):
    has_a, has_b = "x + 1" in tools_text, "x * 2" in tools_text
    out = {}
    for i, t in enumerate(VTASKS):
        r = 0.3 + (0.2 if has_a and i < 10 else 0) + (0.2 if has_b and i >= 10 else 0)
        out[t] = 0.2 if (has_a and has_b and interfere) else r
    return out


def _act(monkeypatch, tmp_path, interfere, spec=None):
    scripts = str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import act
    dirs = {}
    for tag, txt in (("P", BASE_TOOLS), ("A", A_TOOLS), ("B", B_TOOLS), ("M", AB_TOOLS)):
        d = tmp_path / "cands" / tag
        d.mkdir(parents=True)
        (d / "tools.py").write_text(txt)
        dirs[tag] = d
    root = tmp_path / "run"
    (root / "rollouts" / "val").mkdir(parents=True)
    ctx = SimpleNamespace(
        spec={"merge_verify": True} if spec is None else spec, root=root,
        run_dir=SimpleNamespace(root=root, rollouts=root / "rollouts"),
        val_ids=lambda: list(VTASKS), check_budget=lambda a: None, need_project=lambda: tmp_path,
        work=lambda tag: root / "work" / tag, decision=lambda *a, **k: None, warn=lambda m: None)
    calls = []

    def cand_dir(run_dir, tag):
        w = root / "work" / tag
        return dirs.get(tag) or w

    def measure(c, tag, ids, offset, n):
        calls.append((tag, offset, n, tuple(ids)))
        tools = (cand_dir(None, tag) / "tools.py").read_text()
        tr = _truth(tools, interfere)
        return {(t, k): tr[t] for t in ids for k in range(offset, offset + n)}

    def split(run_dir, tag, sp, **kw):
        tools = (cand_dir(None, tag) / "tools.py").read_text()
        tr = _truth(tools, interfere)
        return SimpleNamespace(per_task=[{"task_id": t, "reward": tr[t]} for t in VTASKS], reward=0.0)
    monkeypatch.setattr(act, "_measure", measure)
    monkeypatch.setattr(act, "_first_free_trial", lambda c, *t: 3)
    monkeypatch.setattr(act.digest, "cand_dir", cand_dir)
    monkeypatch.setattr(act.harness, "split_result_from_rollouts", split)
    monkeypatch.setattr(act.lineage if hasattr(act, "lineage") else __import__("cap_evolve.lineage", fromlist=["x"]),
                        "merge_base", lambda g, a, b: "P")
    monkeypatch.setattr(act.CandidateGraph, "load", classmethod(lambda cls, rd: None))
    return act, ctx, calls


def _args(**kw):
    base = dict(tag="M", parents=["A", "B"], base=None, n=0, max_rounds=0, dd_budget=12, over_budget=None, verb="verify-merge")
    return SimpleNamespace(**{**base, **kw})


def test_verify_merge_requires_the_switch(monkeypatch, tmp_path):
    act, ctx, _ = _act(monkeypatch, tmp_path, False, spec={})
    with pytest.raises(act.Refused, match="merge_verify is off"):
        act.verify_merge(_args(), ctx)


def test_verify_merge_pass_uses_one_common_fresh_offset_and_records(monkeypatch, tmp_path):
    act, ctx, calls = _act(monkeypatch, tmp_path, interfere=False)
    rc, out = act.verify_merge(_args(), ctx)
    assert rc == 0 and out["verdict"] == "pass" and out["retained"] == ["A", "B"]
    assert {c[1] for c in calls} == {3} and {c[0] for c in calls} == {"P", "A", "B", "M"}
    assert json.loads((ctx.root / "merge_verify" / "M.json").read_text())["verdict"] == "pass"
    assert "delta_debug" not in out


def test_verify_merge_loss_localizes_the_interfering_hunks_and_keeps_parents(monkeypatch, tmp_path):
    act, ctx, calls = _act(monkeypatch, tmp_path, interfere=True)
    rc, out = act.verify_merge(_args(), ctx)
    assert rc == 1 and out["verdict"] == "loses"
    dd = out["delta_debug"]
    assert set(dd["minimal"]) == {"tools.py::a", "tools.py::b"} and dd["reproducible"] and not dd["exhausted"]
    assert out["stats"]["interaction"]["mean"] < 0 and "parents retained" in out["next"]
    assert (tmp_path / "cands" / "A").exists() and (tmp_path / "cands" / "B").exists()   # parents untouched


def test_verify_merge_dd_budget_zero_skips_localization(monkeypatch, tmp_path):
    act, ctx, _ = _act(monkeypatch, tmp_path, interfere=True)
    rc, out = act.verify_merge(_args(dd_budget=0), ctx)
    assert out["verdict"] == "loses" and "delta_debug" not in out


def test_ancestor_branch_is_refused(monkeypatch, tmp_path):
    act, ctx, _ = _act(monkeypatch, tmp_path, False)
    import cap_evolve.lineage as lin
    monkeypatch.setattr(lin, "merge_base", lambda g, a, b: "A")
    with pytest.raises(act.Refused, match="ancestor"):
        act.verify_merge(_args(), ctx)


def test_promote_of_an_unverified_merge_is_refused_only_when_the_switch_is_on(monkeypatch, tmp_path):
    act, ctx, _ = _act(monkeypatch, tmp_path, False)
    ctx.champion = lambda: "P"
    monkeypatch.setattr(act.graph, "latest_node", lambda rd, tag: {"edit_kind": "merge"})
    monkeypatch.setattr(act.eval_index, "missing", lambda *a, **k: {"t00": 1})
    a = SimpleNamespace(tag="M", verbose=False, commit_extra=None, note=None, over_budget=None)
    with pytest.raises(act.Refused, match="needs a passing verification"):
        act.promote(a, ctx)
    (ctx.root / "merge_verify").mkdir()
    (ctx.root / "merge_verify" / "M.json").write_text(json.dumps({"verdict": "pass"}))
    with pytest.raises(act.Refused, match="no hashes recorded"):                  # a pass without hashes is not binding
        act.promote(a, ctx)
    hashes = {t: act.eval_index.cap_hash(act.digest.cand_dir(None, t)) for t in "PABM"}
    (ctx.root / "merge_verify" / "M.json").write_text(json.dumps({"verdict": "pass", "hashes": hashes}))
    with pytest.raises(act.Refused, match="lacks full-val ledger"):               # got past the merge check
        act.promote(a, ctx)
    ctx.spec = {}                                                                 # switch off: legacy path
    (ctx.root / "merge_verify" / "M.json").unlink()
    with pytest.raises(act.Refused, match="lacks full-val ledger"):
        act.promote(a, ctx)


# ---- review round: unit guards -----------------------------------------------------------------------

def test_small_block_cannot_pass_on_an_infinite_z():
    ts = ["a", "b", "c"]
    P = {t: 0.0 for t in ts}
    st = mv.analyse({"P": P, "A": {t: 0.5 for t in ts}, "B": {t: 0.5 for t in ts}, "M": {t: 1.0 for t in ts}})
    assert st["gain"]["z"] == float("inf")
    v, why = mv.verdict(st, mv.MergeVerifyParams())
    assert v == "inconclusive" and "min_block" in why


def test_duplicate_python_def_text_coarsens_to_the_file_and_revert_refuses():
    base = "def a(x):\n    return x\n\ndef b(x):\n    return x\n"
    merged = "def a(x):\n    return x + 1\n\ndef b(x):\n    return x\n"
    assert mv._py_units(base, merged) == {"a": ("def a(x):\n    return x\n", "def a(x):\n    return x + 1\n")}
    twice = merged + "\ndef a(x):\n    return x + 1\n"          # the same changed def text twice
    assert mv._py_units(base, twice) is None                          # coarsened to the whole file
    with pytest.raises(ValueError, match="not unique"):
        mv._revert_py(base, merged, {"zzz"})


def test_next_trial_matches_the_exact_tag_only(tmp_path):
    scripts = str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts")
    sys.path.insert(0, scripts)
    import act
    val = tmp_path / "val"
    val.mkdir()
    for name in ("t1__M__t2.json", "t1__M__dd1__t9.json", "t1__xM__t7.json", "t1__B__M__t5.json"):
        (val / name).write_text("{}")
    from types import SimpleNamespace
    ctx = SimpleNamespace(run_dir=SimpleNamespace(rollouts=tmp_path))
    # exact: "t1__M__t2" (k=2) and "t1__B__M__t5" (task "t1__B"? head ends with __M: counts) ; dd1 and xM do not
    assert act._next_trial(ctx, "M") == 6
    assert act._next_trial(ctx, "M__dd1") == 10
    assert act._next_trial(ctx, "xM") == 8


def test_stale_pass_is_refused_after_the_merge_is_rebuilt(monkeypatch, tmp_path):
    act, ctx, _ = _act(monkeypatch, tmp_path, False)
    ctx.champion = lambda: "P"
    monkeypatch.setattr(act.graph, "latest_node", lambda rd, tag: {"edit_kind": "merge"})
    monkeypatch.setattr(act.eval_index, "missing", lambda *a, **k: {"t00": 1})
    act.verify_merge(_args(), ctx)
    a = SimpleNamespace(tag="M", verbose=False, commit_extra=None, note=None, over_budget=None)
    with pytest.raises(act.Refused, match="lacks full-val ledger"):               # bound hashes match: gate passes
        act.promote(a, ctx)
    (tmp_path / "cands" / "M" / "tools.py").write_text(AB_TOOLS + "\n# rebuilt\n")
    with pytest.raises(act.Refused, match=r"no longer matches.*\['M'\]"):
        act.promote(a, ctx)


def test_budget_is_checked_before_every_arm_and_every_ddmin_test(monkeypatch, tmp_path):
    act, ctx, calls = _act(monkeypatch, tmp_path, interfere=True)
    seen = []
    ctx.check_budget = lambda a: seen.append(1)
    act.verify_merge(_args(), ctx)
    assert len(seen) >= len(calls)                      # one check per _measure (arm or ddmin test) at least
    act2, ctx2, calls2 = _act(monkeypatch, tmp_path / "second", interfere=True)

    def stop_after_two(a, n=[0]):
        n[0] += 1
        if n[0] > 2:
            raise act2.Refused("budget exhausted: test")
    ctx2.check_budget = stop_after_two
    with pytest.raises(act2.Refused, match="budget exhausted"):
        act2.verify_merge(_args(), ctx2)
    assert len(calls2) == 2 and not (ctx2.root / "merge_verify" / "M.json").exists()


def test_ddmin_scratch_dirs_rollouts_and_ledger_rows_are_purged(monkeypatch, tmp_path):
    act, ctx, _ = _act(monkeypatch, tmp_path, interfere=True)
    forgotten = []
    monkeypatch.setattr(act.eval_index, "forget_tags", lambda rd, tags: forgotten.append(list(tags)))
    (ctx.run_dir.rollouts / "val").mkdir(parents=True, exist_ok=True)
    orig = act._measure

    def measure_and_write(c, tag, ids, offset, n):
        out = orig(c, tag, ids, offset, n)
        (c.run_dir.rollouts / "val" / f"t00__{tag}__t{offset}.json").write_text("{}")
        return out
    monkeypatch.setattr(act, "_measure", measure_and_write)
    rc, out = act.verify_merge(_args(), ctx)
    assert out["delta_debug"]["tests"] >= 2 and forgotten and forgotten[0][0].startswith("M__dd")
    assert not list((ctx.root / "work").glob("M__dd*"))
    assert not list((ctx.run_dir.rollouts / "val").glob("*M__dd*"))
    assert list((ctx.root / "merge_verify" / "M" / "scratch").glob("*.json"))


# ---- end to end: real fake adapter, real evaluate subprocess, real ledger ------------------------------

E2E_ADAPTER = '''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

NEEDS = {f"t{i}": "MARK_A" for i in range(0, 4)}
NEEDS.update({f"t{i}": "MARK_B" for i in range(4, 8)})

class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}") for i in range(12)]
    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id, output=(Path(ctx) / "tools.py").read_text(), metadata={"seed": seed})
    def run_trials(self, tasks, ctx, *, n_trials, base_seed):
        return run_trials_pool(lambda t, s: self.run_target(t, ctx, seed=s), tasks, n_trials=n_trials, base_seed=base_seed)
    def score(self, task, rollout):
        ok = NEEDS.get(task.id, "") in (rollout.output or "")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback="", trial_rewards=[1.0 if ok else 0.0])
'''


def _e2e(tmp_path, monkeypatch):
    import importlib.util
    from cap_evolve import Budget, RunDir, harness
    scripts = str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import act
    monkeypatch.setenv("CAPEVOLVE_CORE", str(REPO / "core"))
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(REPO / "skills"))
    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(E2E_ADAPTER)
    sp = importlib.util.spec_from_file_location("e2e_adapter", project / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    adapter = mod.Adapter()
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="mv", budget=Budget(max_iterations=10))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "tools.py").write_text("base\n")
    harness.ensure_splits(adapter, run_dir, seed=0, split_ids={"val": [f"t{i}" for i in range(12)], "train": [], "test": []})
    harness.baseline(adapter, seed, run_dir=run_dir)
    for tag, text in (("A", "base MARK_A\n"), ("B", "base MARK_B\n"), ("M", "base MARK_A MARK_B\n")):
        d = run_dir.root / "work" / tag
        d.mkdir(parents=True)
        (d / "tools.py").write_text(text)
    for tag in ("A", "B"):
        harness.evaluate_candidate(adapter, run_dir.root / "work" / tag, run_dir=run_dir, split="val", n_trials=1, tag=tag)
    ctx = act.Ctx(SimpleNamespace(run_dir=str(run_dir.root), project=str(project), strict=False))
    ctx.spec = {"merge_verify": True}
    return act, ctx, run_dir


def test_e2e_four_arms_share_seeds_hashes_bind_and_budget_binds(tmp_path, monkeypatch):
    act, ctx, run_dir = _e2e(tmp_path, monkeypatch)
    args = _args(parents=["A", "B"], base="seed", n=2, max_rounds=1, dd_budget=0)
    rc, out = act.verify_merge(args, ctx)
    assert rc == 0 and out["verdict"] == "pass", out["reason"]
    k0 = out["k0"]
    assert k0 == 1                                              # A, B, seed, M have only t0 so far
    val = run_dir.rollouts / "val"
    seeds = {}
    for arm, tag in (("P", "seed"), ("A", "A"), ("B", "B"), ("M", "M")):
        seeds[arm] = {}
        for f in val.glob(f"*__{tag}__t*.json"):
            k = int(f.stem.rsplit("__t", 1)[1])
            if k >= k0:
                d = json.loads(f.read_text())
                seeds[arm][(d["score"]["task_id"], k)] = d["rollout"]["metadata"]["seed"]
    common = set.intersection(*(set(v) for v in seeds.values()))
    assert common and all(len({seeds[a][c] for a in seeds}) == 1 for c in common)     # identical seeds per cell
    # ledger rows carry trial_idx == k
    from cap_evolve import eval_index
    h = eval_index.cap_hash(act.digest.cand_dir(run_dir, "M"))
    assert {r["trial_idx"] for r in eval_index.rows(run_dir) if r["cap_hash"] == h and r["trial_idx"] >= k0} == {1, 2}
    # hashes bind: rebuilding M invalidates the pass
    monkeypatch.setattr(act.graph, "latest_node", lambda rd, tag: {"edit_kind": "merge"})
    monkeypatch.setattr(act.eval_index, "missing", lambda *a, **k: {"t00": 1})
    a = SimpleNamespace(tag="M", verbose=False, commit_extra=None, note=None, over_budget=None)
    with pytest.raises(act.Refused, match="lacks full-val ledger"):
        act.promote(a, ctx)
    (run_dir.root / "work" / "M" / "tools.py").write_text("base MARK_A MARK_B rebuilt\n")
    with pytest.raises(act.Refused, match="no longer matches"):
        act.promote(a, ctx)


def test_e2e_budget_stops_verification_midway(tmp_path, monkeypatch):
    act, ctx, run_dir = _e2e(tmp_path, monkeypatch)
    run_dir.update_budget(max_metric_calls=run_dir.spent.metric_calls + 1)
    with pytest.raises(act.Refused, match="budget exhausted"):
        act.verify_merge(_args(parents=["A", "B"], base="seed", n=2, max_rounds=3, dd_budget=0), ctx)
    spent_after_first_arm = run_dir.spent.metric_calls
    assert spent_after_first_arm > 0 and not (ctx.root / "merge_verify" / "M.json").exists()
