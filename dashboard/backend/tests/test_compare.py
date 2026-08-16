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


def test_compare_counts_every_judged_candidate_and_exposes_the_split(tmp_base, make_run):
    """The comparison must agree with the hub on how many candidates a run had, and it
    must publish each run's val task ids.

    ``iterations`` summed only accepted+rejected while the hub summed all four verdicts,
    so the same run reported a different candidate count in the two views and indecisive
    steps vanished. And with no task ids the UI could not tell that two selected runs
    were scored on DIFFERENT splits — a 2-task toy run and a 12-task benchmark run went
    into one table and one chart with nothing saying the numbers are not comparable.
    """
    from capevolve_dashboard import compare, runs
    events = BASE_EVENTS + [
        {"kind": "step", "candidate": "cand_0003", "accept": False, "reason": "no coverage",
         "val": None, "parent": "cand_0001"},
        {"kind": "step_indecisive", "candidate": "cand_0003"},
    ]
    baseline = {"val": {"reward": 0.25,
                        "per_task": [{"task_id": "t1", "reward": 0.0},
                                     {"task_id": "t2", "reward": 0.5}]}}
    make_run("run_a", events=events, baseline=baseline)
    out = compare.compare_runs(tmp_base, ["run_a"])
    row = out["runs"][0]
    hub = next(r for r in runs.list_runs(tmp_base) if r["run_id"] == "run_a")
    assert row["iterations"] == hub["iterations"] == 3
    assert sorted(row["tasks"]) == ["t1", "t2"]
    assert row["splits"]["val"] == 2
    assert row["status"] == hub["status"]
