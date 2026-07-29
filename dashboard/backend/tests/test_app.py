from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def test_health(tmp_base):
    r = _client(tmp_base).get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_list_runs_endpoint(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    r = _client(tmp_base).get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["run_id"] == "run_a"


def test_get_run_endpoint(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    r = _client(tmp_base).get("/api/runs/run_a")
    assert r.status_code == 200
    assert r.json()["graph"]["best_id"] == "cand_0001"


def test_get_missing_run_404(tmp_base):
    r = _client(tmp_base).get("/api/runs/run_nope")
    assert r.status_code == 404


def test_serves_static_index(tmp_path):
    from capevolve_dashboard.app import create_app
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>cap-evolve</title>", encoding="utf-8")
    base = tmp_path / "runs"
    base.mkdir()
    c = TestClient(create_app(base, static_dir=static))
    r = c.get("/")
    assert r.status_code == 200
    assert "cap-evolve" in r.text
    # API still wins
    assert c.get("/api/health").json()["ok"] is True


def test_stream_replays_the_whole_log_for_a_finished_run(tmp_base, make_run):
    """The SSE route starts at offset 0, not EOF. At EOF the Events tab was
    permanently empty on every FINISHED run even though events.jsonl was full."""
    make_run("run_a", events=BASE_EVENTS + [{"kind": "finalize", "test": 0.8}],
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    with _client(tmp_base).stream("GET", "/api/runs/run_a/stream") as r:
        body = "".join(r.iter_text())
    # every historical event replayed, then `done` (finalize closes the stream)
    assert body.count("\nevent: event\n") == len(BASE_EVENTS) + 1
    assert "event: done" in body
    assert '"cand_0001"' in body
