"""#702: dashboard_views node states on the slim recorded-run fixture."""
from pathlib import Path

from cap_evolve import RunDir, dashboard

FIX = Path(__file__).parents[2] / "dashboard/backend/tests/fixtures/base/run_20261008_150326"


def test_recorded_run_cand9_screened_8_of_30():
    nodes = {n["id"]: n for n in dashboard.reduce_run(RunDir.open(FIX))["graph"]["nodes"]}
    assert nodes["cand_9"]["eval_state"] == "screened"
    assert (nodes["cand_9"]["coverage"]["n_tasks"], nodes["cand_9"]["coverage"]["n_val_tasks"]) == (8, 30)
    assert nodes["cand_7"]["eval_state"] == "full"


def test_malformed_node_does_not_break_reducer(monkeypatch):
    from cap_evolve import dashboard_views, schema_v2
    monkeypatch.setattr(schema_v2, "normalize_node", lambda *a, **k: 1 / 0)
    r = dashboard.reduce_run(RunDir.open(FIX))
    assert all("schema_warning" in n for n in r["graph"]["nodes"])


def test_no_node_is_its_own_parent_and_cand4_resolves_to_cand1():
    nodes = {n["id"]: n for n in dashboard.reduce_run(RunDir.open(FIX))["graph"]["nodes"]}
    assert [i for i, n in nodes.items() if n.get("parent") == i] == []
    assert nodes["cand_4"]["parent"] == "cand_1"
