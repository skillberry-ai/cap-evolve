"""Tests for the generic directory browser (/tree, /file) and git diff endpoints."""
import subprocess

import pytest
from conftest import BASE_EVENTS
from fastapi.testclient import TestClient

from capevolve_dashboard.app import create_app


@pytest.fixture
def client(make_run, tmp_base):
    rd = make_run(events=BASE_EVENTS)
    # seed a memory directory + a candidate scratch tree
    (rd.root / "memory").mkdir()
    (rd.root / "memory" / "notes.md").write_text("# learned\n- prefer X\n", encoding="utf-8")
    (rd.root / "memory" / "blob.bin").write_bytes(b"\x00\x01\x02\x03data")
    return TestClient(create_app(tmp_base))


def test_tree_lists_memory_dir(client):
    r = client.get("/api/runs/run_t/tree", params={"path": "memory"})
    assert r.status_code == 200
    names = {e["name"] for e in r.json()["entries"]}
    assert {"notes.md", "blob.bin"} <= names


def test_file_reads_text(client):
    r = client.get("/api/runs/run_t/file", params={"path": "memory/notes.md"})
    assert r.status_code == 200 and "prefer X" in r.json()["text"]


def test_file_detects_binary(client):
    r = client.get("/api/runs/run_t/file", params={"path": "memory/blob.bin"})
    assert r.status_code == 200 and r.json()["binary"] is True and r.json()["text"] is None


def test_tree_rejects_traversal(client):
    r = client.get("/api/runs/run_t/file", params={"path": "../../etc/passwd"})
    assert r.status_code == 400


def test_git_log_and_diff(client, tmp_base):
    rd_root = tmp_base / "run_t"
    # build a tiny git history in the run dir
    subprocess.run(["git", "-C", str(rd_root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(rd_root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(rd_root), "config", "user.name", "t"], check=True)
    (rd_root / "art.txt").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(rd_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(rd_root), "commit", "-q", "-m", "iter 1"], check=True)
    (rd_root / "art.txt").write_text("v2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(rd_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(rd_root), "commit", "-q", "-m", "iter 2"], check=True)

    log = client.get("/api/runs/run_t/git/log").json()
    assert len(log) == 2 and log[0]["subject"] == "iter 1"
    d = client.get("/api/runs/run_t/git/diff", params={"from": "HEAD~1", "to": "HEAD"}).json()
    assert d["available"] is True
    rows = [r for f in d["files"] for r in f["rows"]]
    assert any(r["t"] == "add" and r["l"] == "v2" for r in rows)
    assert any(r["t"] == "del" and r["l"] == "v1" for r in rows)


def test_git_diff_bad_ref(client):
    d = client.get("/api/runs/run_t/git/diff", params={"from": "x;rm", "to": "HEAD"}).json()
    assert d.get("error") == "bad ref" or d.get("available") is False
