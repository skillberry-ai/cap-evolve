from pathlib import Path

from conftest import BASE_EVENTS


def test_discover_finds_run_dirs(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS)
    make_run("run_b", events=BASE_EVENTS)
    (tmp_base / "not_a_run").mkdir()
    found = runs.discover(tmp_base)
    names = sorted(p.name for p in found)
    assert names == ["run_a", "run_b"]


def test_list_runs_projects_light_summary(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    rows = runs.list_runs(tmp_base)
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "run_a"
    assert row["baseline_val"] == 0.25
    assert row["best_val"] == 0.75
    assert row["iterations"] == 2
    assert row["status"] in {"live", "done", "failed"}


def test_plateau_is_surfaced_and_is_not_liveness(tmp_base, make_run):
    """Plateau state must reach the REACT dashboard, not only the static HTML.

    A stop decision the user cannot see is half a feature. It is a field separate from
    ``status`` on purpose: ``status`` is liveness (is the process running), plateau is
    progress (is anything it does helping) — a plateaued run is BOTH ``live`` and ``stop``.
    """
    from capevolve_dashboard import runs
    events = BASE_EVENTS + [
        {"kind": "plateau", "level": "stop", "run_length": 7, "accepts_in_streak": 0,
         "algorithm": "gepa", "reason": "plateau: 7 consecutive iterations bought no best val"},
        {"kind": "lineage_exhausted", "parent": "cand_0001", "window": 4,
         "plateau_level": "stop"},
    ]
    make_run("run_a", events=events, baseline={"val": {"reward": 0.25}, "best_id": "seed"})

    row = runs.list_runs(tmp_base)[0]
    assert row["plateau_level"] == "stop"
    assert row["status"] == "live", "liveness and plateau answer different questions"

    s = runs.load_run(tmp_base, "run_a")["summary"]
    assert s["plateau"]["level"] == "stop" and s["plateau"]["run_length"] == 7
    assert s["exhausted_lineages"] == ["cand_0001"]


def test_plateau_level_defaults_to_ok(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS)
    assert runs.list_runs(tmp_base)[0]["plateau_level"] == "ok"


def test_load_run_returns_graph_and_summary(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    data = runs.load_run(tmp_base, "run_a")
    assert data["run_id"] == "run_a"
    assert "graph" in data and "summary" in data
    assert data["graph"]["best_id"] == "cand_0001"


def test_load_run_missing_raises(tmp_base):
    import pytest
    from capevolve_dashboard import runs
    with pytest.raises(runs.RunNotFound):
        runs.load_run(tmp_base, "run_nope")


def test_resolve_run_accepts_valid_child(tmp_base, make_run):
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS)
    p = runs.resolve_run(tmp_base, "run_a")
    assert p.name == "run_a"
    assert p.parent == tmp_base.resolve()


def test_resolve_run_rejects_traversal(tmp_base, make_run):
    import pytest
    from capevolve_dashboard import runs
    make_run("run_a", events=BASE_EVENTS)
    # A run dir one level up must not be reachable via traversal.
    (tmp_base.parent / "run_evil").mkdir(exist_ok=True)
    (tmp_base.parent / "run_evil" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    for evil in ("..", "../run_evil", "run_a/../../run_evil"):
        with pytest.raises(runs.RunNotFound):
            runs.resolve_run(tmp_base, evil)


def test_resolve_run_rejects_non_run_prefix(tmp_base):
    import pytest
    from capevolve_dashboard import runs
    (tmp_base / "notarun").mkdir()
    (tmp_base / "notarun" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(runs.RunNotFound):
        runs.resolve_run(tmp_base, "notarun")
