def test_is_up_false_when_nothing_listening():
    from capevolve_dashboard import server
    # Port 1 is never an http health endpoint; should be quick-false.
    assert server.is_up(1) is False


def test_resolve_static_dir_points_at_frontend_dist():
    from capevolve_dashboard import server
    out = server.resolve_static_dir()
    # Whether or not it's been built, the resolved location must be the real
    # dashboard/frontend/dist — guards the parents[] off-by-one regression.
    from pathlib import Path
    expected = Path(server.__file__).resolve().parents[2] / "frontend" / "dist"
    if out is not None:
        assert out == expected
        assert out.parent.name == "frontend" and out.parent.parent.name == "dashboard"


def test_url_for():
    from capevolve_dashboard import server
    assert server.url_for(7878) == "http://127.0.0.1:7878"
