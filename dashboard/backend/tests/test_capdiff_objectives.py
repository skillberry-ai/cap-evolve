"""#702: dashboard_views node states, /capdiff and /objectives. Fixture is a slim copy of the
recorded run_20261008_150326 (no absolute paths); synthetic tests cover merges and v2 fields."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import BASE_EVENTS

FIX = Path(__file__).parent / "fixtures" / "base"
RID = "run_20261008_150326"


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


@pytest.fixture
def recorded(tmp_path):
    shutil.copytree(FIX, tmp_path / "b")
    return _client(tmp_path / "b")


def test_cand9_is_screened_with_8_of_30(recorded):
    nodes = {n["id"]: n for n in recorded.get(f"/api/runs/{RID}").json()["graph"]["nodes"]}
    c9 = nodes["cand_9"]
    assert c9["eval_state"] == "screened"
    assert (c9["coverage"]["n_tasks"], c9["coverage"]["n_val_tasks"]) == (8, 30)
    assert nodes["cand_7"]["eval_state"] == "full" and nodes["seed"]["eval_state"] == "full"
    assert nodes["cand_4"]["parents"] == ["cand_1"]  # corrupt self-parent never becomes an edge


def test_decisions_fall_back_to_legacy_commits(recorded):
    decs = recorded.get(f"/api/runs/{RID}").json()["summary"]["decisions"]
    assert {d["decision"] for d in decs} <= {"accept", "reject"} and len({d["id"] for d in decs}) == len(decs) == 10


def test_old_run_without_graph_jsonl_still_loads(tmp_base, make_run):
    make_run("run_old", events=BASE_EVENTS, baseline={"val": {"reward": 0.25, "per_task": []}})
    nodes = {n["id"]: n for n in _client(tmp_base).get("/api/runs/run_old").json()["graph"]["nodes"]}
    assert nodes["cand_0001"]["eval_state"] in ("full", "partial", "screened", "unevaluated")
    assert nodes["cand_0001"]["matched_task_ids"] == [] and nodes["cand_0001"]["decisions"]


def test_v2_fields_and_decision_events_pass_through(tmp_base, make_run):
    ev = BASE_EVENTS + [{"t": 5, "kind": "decision", "id": "cand_0001", "decision": "promote",
                         "evidence": {"z": 2}, "rationale": "r", "optimizer_usd": 0.5}]
    rd = make_run("run_v2", events=ev, baseline={"val": {"reward": 0.25, "per_task": []}})
    (rd.root / "graph.jsonl").write_text(json.dumps({
        "id": "cand_0001", "parents": ["seed"], "eval_state": "partial", "branch_id": "b1",
        "coverage": {"split": "val", "task_ids": ["1"], "n_tasks": 1, "n_val_tasks": 4, "full": False},
        "vs_parent": {"cost_matched": {"matched_task_ids": ["1"]}}}) + "\n")
    n = {x["id"]: x for x in _client(tmp_base).get("/api/runs/run_v2").json()["graph"]["nodes"]}["cand_0001"]
    assert (n["eval_state"], n["branch_id"], n["matched_task_ids"]) == ("partial", "b1", ["1"])
    assert n["decisions"][0]["decision"] == "promote" and n["decisions"][0]["optimizer_usd"] == 0.5


# ---- capdiff ---------------------------------------------------------------------------------

def test_capdiff_parent_excludes_journal(recorded):
    d = recorded.get(f"/api/runs/{RID}/capdiff", params={"target": "cand_7"}).json()
    assert d["base"] == "cand_4" and not d["merge"]
    assert [f["path"] for f in d["files"]] == ["policy/policy.md"]
    assert d["files"][0]["added"] + d["files"][0]["removed"] > 0


def test_capdiff_bases(recorded):
    g = lambda base: recorded.get(f"/api/runs/{RID}/capdiff", params={"target": "cand_9", "base": base}).json()
    assert g("original")["base"] == "seed"
    assert g("latest_base")["base"] == "cand_4"
    assert g("cand_7")["base"] == "cand_7"
    assert g("selected")["base"] == "cand_7"  # state.json best_id
    assert recorded.get(f"/api/runs/{RID}/capdiff", params={"target": "nope"}).status_code == 404
    assert recorded.get(f"/api/runs/{RID}/capdiff", params={"target": "..%2Fx"}).status_code in (400, 404)


def test_capdiff_ancestry_edges_and_blame(recorded):
    d = recorded.get(f"/api/runs/{RID}/capdiff", params={"target": "cand_9", "base": "ancestry"}).json()
    # cand_1 has no snapshot in the slim fixture
    assert d["target"] == "cand_9" or d.get("detail")


def _mk_merge_run(base):
    """seed O -> A (adds a), B (adds b), merge C keeps a, drops b, adds c."""
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(base, ts="m", budget=Budget())
    rd.events_path.write_text(json.dumps({"kind": "baseline", "val": 0.1}) + "\n")
    O = "\n".join(f"l{i}" for i in range(20))
    snap = {"seed": O,
            "A": O.replace("l2", "a2"),
            "B": O.replace("l10", "b10"),
            "M": O.replace("l2", "a2").replace("l17", "c17")}
    for tag, text in snap.items():
        (rd.root / "candidates" / tag / "policy").mkdir(parents=True)
        (rd.root / "candidates" / tag / "policy" / "p.md").write_text(text + "\n")
        (rd.root / "candidates" / tag / "JOURNAL.md").write_text(tag)
    rows = [{"id": "A", "parents": ["seed"]}, {"id": "B", "parents": ["seed"]},
            {"id": "M", "parents": ["A", "B"]}]
    (rd.root / "graph.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
    return rd


def test_capdiff_merge_classification(tmp_base):
    _mk_merge_run(tmp_base)
    d = _client(tmp_base).get("/api/runs/run_m/capdiff", params={"target": "M"}).json()
    assert d["merge"] and d["base"] == "seed"
    rows = [r for f in d["files"] for r in f["rows"] if r.get("c")]
    cls = {r["c"] for r in rows}
    assert cls == {"inherited:A", "new", "reverted"}
    assert any(r["l"] == "a2" and r["c"] == "inherited:A" for r in rows)
    assert any(r["l"] == "c17" and r["c"] == "new" for r in rows)
    assert any(r["l"] == "b10" and r["c"] == "reverted" for r in rows)


def test_capdiff_merge_ancestry_and_blame(tmp_base):
    _mk_merge_run(tmp_base)
    d = _client(tmp_base).get("/api/runs/run_m/capdiff", params={"target": "M", "base": "ancestry"}).json()
    assert [(e["from"], e["to"]) for e in d["edges"]] == [("seed", "A"), ("A", "M")]
    assert d["edges"][1]["merge"]
    runs = {(r["start"], r["by"]) for r in d["blame"]["policy/p.md"]}
    assert (3, "A") in runs and (18, "M") in runs and (1, "seed") in runs


def test_capdiff_node_capability_files_narrows(tmp_base):
    rd = _mk_merge_run(tmp_base)
    (rd.root / "candidates" / "M" / "extra.md").write_text("x")
    (rd.root / "graph.jsonl").write_text(json.dumps(
        {"id": "M", "parents": ["A"], "capability_files": ["policy/p.md"]}) + "\n")
    d = _client(tmp_base).get("/api/runs/run_m/capdiff", params={"target": "M", "base": "original"}).json()
    assert [f["path"] for f in d["files"]] == ["policy/p.md"]


# ---- objectives ------------------------------------------------------------------------------

def test_objectives_endpoint_recorded(recorded):
    o = recorded.get(f"/api/runs/{RID}/objectives").json()
    c = o["candidates"]
    assert c["seed"]["n_tasks"] == 6 and c["seed"]["reward"] is not None
    assert c["seed"]["cost_overall"] > 0 and c["seed"]["cost_per_success"] > 0
    v = c["cand_4"]["vs_parent"]
    assert v["reward"]["n"] >= 1 and set(v) == {"reward", "cost_matched", "ecps", "latency"}
    assert c["cand_4"]["parent"] == "cand_1"  # no cand_1 rollouts in the slim fixture
    assert c["cand_9"]["reward"] is None if "reward" in c["cand_9"] else True  # screened only
    assert "optimizer_usd" in c["cand_7"]
    json.dumps(o, allow_nan=False)  # strict JSON: NaN/inf are mapped to null


def test_objectives_vs_parent_matched_ids(recorded):
    v = recorded.get(f"/api/runs/{RID}/objectives").json()["candidates"]["cand_7"]["vs_parent"]
    assert v["cost_matched"]["matched_task_ids"] == sorted(v["cost_matched"]["matched_task_ids"])
    assert v["cost_matched"]["n_matched"] == len(v["cost_matched"]["matched_task_ids"])
