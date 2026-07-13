import importlib
from pathlib import Path


def _reload_asgi_with_static_dir(monkeypatch, *, static_dir):
    if static_dir is None:
        monkeypatch.delenv("CAPEVOLVE_STATIC_DIR", raising=False)
    else:
        monkeypatch.setenv("CAPEVOLVE_STATIC_DIR", static_dir)
    module = importlib.import_module("capevolve_dashboard.asgi")
    return importlib.reload(module)


def _find_static_route(app):
    return next((route for route in app.routes if getattr(route, "name", None) == "static"), None)


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


def test_asgi_auto_detects_static_dir_when_env_unset(monkeypatch):
    module = _reload_asgi_with_static_dir(monkeypatch, static_dir=None)
    route = _find_static_route(module.app)
    expected = Path(module.__file__).resolve().parents[2] / "frontend" / "dist"
    assert route is not None
    assert Path(route.app.directory) == expected


def test_asgi_empty_static_dir_disables_static_mount(monkeypatch):
    module = _reload_asgi_with_static_dir(monkeypatch, static_dir="")
    assert _find_static_route(module.app) is None
