"""Security regressions for the evograph read-only backend.

Covers the path-traversal hardening on the user-controlled route params
(slug / weakness / sol_id / SPA fallback) and the parse_rejected heading filter.
Skipped where FastAPI isn't installed (the backend's own runtime dep).
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    (tmp_path / "wiki" / "weaknesses").mkdir(parents=True)
    (tmp_path / "wiki" / "weaknesses" / "good-slug.md").write_text(
        "---\nslug: good-slug\n---\nbody\n", encoding="utf-8"
    )
    monkeypatch.setenv("EVOGRAPH_BASE", str(tmp_path))
    for m in [m for m in list(sys.modules) if m == "app"]:
        del sys.modules[m]
    import app  # re-import so EVOGRAPH_BASE takes effect
    return TestClient(app.app)


def test_valid_weakness_ok(client):
    assert client.get("/api/weakness/good-slug").status_code == 200


@pytest.mark.parametrize("evil", [
    "..%2f..%2fetc%2fpasswd",
    "foo%2fbar",
    "..",
    ".",
])
def test_weakness_traversal_rejected(client, evil):
    assert client.get(f"/api/weakness/{evil}").status_code == 404


def test_solution_traversal_rejected(client):
    assert client.get("/api/solution/..%2f..%2f/x").status_code == 404


def test_parse_rejected_ignores_format_heading():
    import app
    body = (
        "## Rejected Store Memory\n\n"
        "### RSM entry format\nsome docs\n\n"
        "### Round 2 · raise-temperature\nResult: reward 0.48\n"
    )
    entries = app.parse_rejected(body)
    assert [e["round"] for e in entries] == [2]
    assert "raise-temperature" in entries[0]["label"]
