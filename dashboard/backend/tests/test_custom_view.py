import json

from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def test_no_custom_view_returns_empty(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS)
    r = _client(tmp_base).get("/api/runs/run_a/custom-view")
    assert r.status_code == 200
    assert r.json() == {}


def test_custom_view_declared(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    (rd.root / "custom_view.json").write_text(
        json.dumps({"title": "Weakness graph", "url": "http://127.0.0.1:7878/"}),
        encoding="utf-8",
    )
    r = _client(tmp_base).get("/api/runs/run_a/custom-view")
    assert r.status_code == 200
    assert r.json() == {"title": "Weakness graph", "url": "http://127.0.0.1:7878/"}


def test_custom_view_defaults_title(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    (rd.root / "custom_view.json").write_text(
        json.dumps({"url": "http://localhost:9000/"}), encoding="utf-8"
    )
    assert _client(tmp_base).get("/api/runs/run_a/custom-view").json() == {
        "title": "Custom view",
        "url": "http://localhost:9000/",
    }


def test_custom_view_invalid_ignored(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    # missing url -> ignored
    (rd.root / "custom_view.json").write_text(json.dumps({"title": "x"}), encoding="utf-8")
    assert _client(tmp_base).get("/api/runs/run_a/custom-view").json() == {}
    # malformed JSON -> ignored (never 500)
    (rd.root / "custom_view.json").write_text("{not json", encoding="utf-8")
    assert _client(tmp_base).get("/api/runs/run_a/custom-view").json() == {}


def test_custom_view_rejects_dangerous_schemes(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    # javascript:/data:/scheme-relative/relative URLs are never used as an iframe src.
    for bad in (
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//evil.example.com/",
        "/relative/path",
        "ftp://host/file",
    ):
        (rd.root / "custom_view.json").write_text(
            json.dumps({"url": bad}), encoding="utf-8"
        )
        assert _client(tmp_base).get("/api/runs/run_a/custom-view").json() == {}


def test_custom_view_missing_run_404(tmp_base):
    r = _client(tmp_base).get("/api/runs/run_nope/custom-view")
    assert r.status_code == 404
