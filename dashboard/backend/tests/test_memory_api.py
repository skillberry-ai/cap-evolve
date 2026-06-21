import json

from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def _seed_memory(rd):
    (rd.root / "history.jsonl").write_text(
        json.dumps({"candidate_id": "cand_0001", "summary": "up", "val": 1.0}) + "\n",
        encoding="utf-8",
    )
    (rd.root / "rejected.jsonl").write_text(
        json.dumps({"candidate_id": "cand_0002", "summary": "flat", "reason": "Δ<=SE", "val": 1.0}) + "\n",
        encoding="utf-8",
    )
    cdir = rd.root / "candidates" / "cand_0001"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "MEMORY.md").write_text("# notes\nlearned X", encoding="utf-8")
    (cdir / "prompt.txt").write_text("you are helpful", encoding="utf-8")


def test_read_memory(tmp_base, make_run):
    from capevolve_dashboard import memory
    rd = make_run("run_a", events=BASE_EVENTS)
    _seed_memory(rd)
    out = memory.read_memory(rd.root)
    assert out["history"][0]["candidate_id"] == "cand_0001"
    assert out["rejected"][0]["reason"] == "Δ<=SE"


def test_memory_endpoint(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    _seed_memory(rd)
    r = _client(tmp_base).get("/api/runs/run_a/memory")
    assert r.status_code == 200
    body = r.json()
    assert len(body["history"]) == 1 and len(body["rejected"]) == 1


def test_candidate_files_endpoint(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    _seed_memory(rd)
    r = _client(tmp_base).get("/api/runs/run_a/candidate/cand_0001/files")
    assert r.status_code == 200
    names = {f["name"] for f in r.json()}
    assert names == {"MEMORY.md", "prompt.txt"}


def test_memory_missing_run_404(tmp_base):
    r = _client(tmp_base).get("/api/runs/run_nope/memory")
    assert r.status_code == 404


def test_candidate_files_traversal_is_contained(tmp_base, make_run):
    from capevolve_dashboard import memory
    rd = make_run("run_a", events=BASE_EVENTS)
    _seed_memory(rd)
    # A traversal candidate id is reduced to a basename, so it can't escape.
    assert memory.list_candidate_files(rd.root, "../../etc") == []
