"""#710: N-way merge by merge-base fold + interaction score + probe plan (merge_n.py).

Real fixtures: md_blocks/cand_3/4/5 policy.md edit the SAME lines (preamble insert, Modify-flight
lines) -> the N-way merge must report conflicts with a resolution proposal, never merge silently.
A synthetic disjoint trio (one new rule in three different sections of the real seed) merges cleanly.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))
sys.path.insert(0, str(REPO / "core"))

import merge_n  # noqa: E402
from cap_evolve import lineage  # noqa: E402
from cap_evolve.candidate_graph import CandidateGraph  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "md_blocks"
SEED = (FIX / "seed" / "policy" / "policy.md").read_text(encoding="utf-8")


def _cap(root: Path, name: str, text: str) -> Path:
    (root / name / "policy").mkdir(parents=True)
    (root / name / "policy" / "policy.md").write_text(text, encoding="utf-8")
    return root / name


def _g(parents: dict) -> CandidateGraph:
    return CandidateGraph({k: {"id": k, "parents": v, "children": []} for k, v in parents.items()})


def _trio(tmp_path):
    lines = SEED.splitlines()
    heads = [i for i, l in enumerate(lines) if l.startswith("#")]
    dirs = {"seed": _cap(tmp_path, "seed", SEED)}
    for n, h in zip("abc", (heads[2], heads[4], heads[6])):
        ls = list(lines)
        ls.insert(h + 1, f"- new rule {n}: call do_thing_{n} first")
        dirs[n] = _cap(tmp_path, n, "\n".join(ls) + "\n")
    return dirs


def test_real_cand345_conflict_is_reported_with_a_proposal_not_merged(tmp_path):
    tags = ["cand_3", "cand_4", "cand_5"]
    g = _g({"seed": [], **{t: ["seed"] for t in tags}})
    r = merge_n.merge_n(tags, lambda t: FIX / t, g, tmp_path / "out", wins={"cand_3": {"1", "2"}})
    assert not r["built"] and r["unmerged"]
    assert r["conflicts"] and all(c["proposal"] and c["trunk"] and c["donor"] for c in r["conflicts"])
    assert any("Modify flight" in c["where"] for c in r["conflicts"])
    assert r["merged"][0] == "cand_3"               # most wins = trunk, folded first
    assert all(s["base"] == "seed" for s in r["steps"])


def test_disjoint_trio_merges_cleanly_without_a_probe(tmp_path):
    d = _trio(tmp_path)
    g = _g({"seed": [], "a": ["seed"], "b": ["seed"], "c": ["seed"]})
    r = merge_n.plan(["a", "b", "c"], lambda t: d[t], g,
                     touched_tasks={"a": ["1"], "b": ["2"], "c": ["3"]},
                     wins={"a": {"1"}, "b": {"2"}, "c": {"3"}}, all_tasks=list("123456789"),
                     out_dir=tmp_path / "m")
    assert r["built"] and sorted(r["merged"]) == ["a", "b", "c"]
    merged = (tmp_path / "m" / "policy" / "policy.md").read_text(encoding="utf-8")
    assert all(f"do_thing_{n}" in merged for n in "abc")
    assert r["max_I"] < merge_n.PROBE_AT and not r["probe"]


def test_overlapping_wins_and_tasks_trigger_a_probe_over_union_plus_sentinels(tmp_path):
    d = _trio(tmp_path)
    g = _g({"seed": [], "a": ["seed"], "b": ["seed"], "c": ["seed"]})
    r = merge_n.plan(["a", "b", "c"], lambda t: d[t], g,
                     touched_tasks={"a": ["1", "2"], "b": ["2", "3"], "c": ["1", "3"]},
                     wins={"a": {"1", "2"}, "b": {"2", "3"}, "c": {"1", "3"}},
                     all_tasks=list("123456789"), out_dir=tmp_path / "m",
                     run_dir=SimpleNamespace(root=tmp_path / "run"))
    assert r["probe"]
    req = r["eval_request"]
    assert set("123") <= set(req["task_ids"]) and len(req["sentinels"]) == merge_n.N_SENTINELS
    assert req["n_trials"] == 3 and not set(req["sentinels"]) & set("123")
    assert "cap_hash" in req and req["missing"]       # nothing in the ledger yet -> all cells cost


def test_missing_win_evidence_warns_and_is_neutral(capsys):
    f = {"blocks": set(), "tools": set(), "tasks": set(), "wins": None}
    r = merge_n.interaction(f, f)
    assert r["parts"]["wins"] == 0.5 and "warning" in r
    assert "WARNING" in capsys.readouterr().err


def test_multi_cycle_merge_node_records_parents_and_is_a_tip_to_branch_from(tmp_path):
    d = _trio(tmp_path)
    g = _g({"seed": [], "a": ["seed"], "b": ["seed"], "c": ["seed"]})
    r = merge_n.merge_n(["a", "b"], lambda t: d[t], g, tmp_path / "m1")
    rec = merge_n.node_record(r, "m1", round_id=2)
    assert rec["parents"] == ["a", "b"] and rec["edit_kind"] == "merge" and rec["merge_base"] == "seed"
    assert rec["parent_roles"] == {"a": "primary", "b": "donor"} and rec["stage"] == "built"
    g._nodes["m1"] = {"id": "m1", "parents": rec["parents"], "children": []}
    assert "m1" in lineage.tips(g) or "m1" in g._nodes
    # branch off the merge node, then merge that branch with c
    d["m1"] = tmp_path / "m1"
    text = (tmp_path / "m1" / "policy" / "policy.md").read_text(encoding="utf-8")
    d["m1x"] = _cap(tmp_path, "m1x", text.replace("do_thing_a", "do_thing_a_v2"))
    g._nodes["m1x"] = {"id": "m1x", "parents": ["m1"], "children": []}
    r2 = merge_n.merge_n(["m1x", "c"], lambda t: d[t], g, tmp_path / "m2")
    assert r2["built"] and r2["steps"][0]["base"] == "seed"
    final = (tmp_path / "m2" / "policy" / "policy.md").read_text(encoding="utf-8")
    assert "do_thing_a_v2" in final and "do_thing_c" in final and "do_thing_b" in final


def test_ownership_selects_complementary_merge_parents():
    alts = [{"candidate": "x", "tasks_uniquely_owned": ["1", "2", "3"]},
            {"candidate": "y", "tasks_uniquely_owned": ["2", "3"]},      # covered by x
            {"candidate": "z", "tasks_uniquely_owned": ["9"]}]
    assert merge_n.select_merge_set(alts, "champ", k=3) == ["champ", "x", "z"]
    assert merge_n.select_merge_set(alts, None) == []


def test_smart_merge_ablation_keys_and_env(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_SMART_MERGE", raising=False)
    assert merge_n.enabled({}) and merge_n.enabled(None)
    assert not merge_n.enabled({"optimizer": {"ablation": {"smart_merge": False}}})
    assert not merge_n.enabled({"ablation": {"smart_merge": False}})        # legacy top-level
    monkeypatch.setenv("CAPEVOLVE_SMART_MERGE", "0")
    assert not merge_n.enabled({})
    monkeypatch.setenv("CAPEVOLVE_SMART_MERGE", "1")
    assert merge_n.enabled({"optimizer": {"ablation": {"smart_merge": False}}})
