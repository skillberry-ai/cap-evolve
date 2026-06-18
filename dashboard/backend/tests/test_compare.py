from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def test_compare_runs(tmp_base, make_run):
    from capevolve_dashboard import compare
    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    make_run("run_b", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    out = compare.compare_runs(tmp_base, ["run_a", "run_b"])
    assert [r["run_id"] for r in out["runs"]] == ["run_a", "run_b"]
    assert out["runs"][0]["best_val"] == 0.75
    assert isinstance(out["runs"][0]["series"], list)


def test_compare_endpoint_skips_unknown(tmp_base, make_run):
    from capevolve_dashboard.app import create_app
    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    r = TestClient(create_app(tmp_base)).get("/api/compare?ids=run_a,run_ghost")
    assert r.status_code == 200
    assert [x["run_id"] for x in r.json()["runs"]] == ["run_a"]
