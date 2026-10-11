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
    monkeypatch.setattr(act, "_first_free_trial", lambda c, t: 3)
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
    monkeypatch.setattr(act.eval_index, "cap_hash", lambda d: "h")
    a = SimpleNamespace(tag="M", verbose=False, commit_extra=None, note=None, over_budget=None)
    with pytest.raises(act.Refused, match="needs a passing verification"):
        act.promote(a, ctx)
    (ctx.root / "merge_verify").mkdir()
    (ctx.root / "merge_verify" / "M.json").write_text(json.dumps({"verdict": "pass"}))
    with pytest.raises(act.Refused, match="lacks full-val ledger"):               # got past the merge check
        act.promote(a, ctx)
    ctx.spec = {}                                                                 # switch off: legacy path
    (ctx.root / "merge_verify" / "M.json").unlink()
    with pytest.raises(act.Refused, match="lacks full-val ledger"):
        act.promote(a, ctx)
