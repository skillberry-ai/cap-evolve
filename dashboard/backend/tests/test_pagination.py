"""Pagination on /api/runs and /api/runs/{id}/rollouts, and the empty SSE snapshot
frame (issue #119).

Contract: both endpoints are UNPAGINATED by default (back-compat with the SPA, which
expects a plain array). ``?limit=N`` returns at most N rows; ``?offset=K`` skips the
first K. Order is deterministic — runs newest-first by dir mtime, rollouts by
(split, file name) — so consecutive pages tile the full list without gaps or repeats.
"""

import json

from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def _write_rollout(rd, split, task, cand, trial, reward=1.0):
    d = rd.root / "rollouts" / split
    d.mkdir(parents=True, exist_ok=True)
    name = f"{task}__{cand}__t{trial}.json"
    (d / name).write_text(json.dumps({
        "rollout": {"task_id": task, "output": "out"},
        "score": {"task_id": task, "reward": reward, "feedback": ""},
    }), encoding="utf-8")
    return name


# ---- /api/runs -------------------------------------------------------------

def test_runs_unpaginated_by_default(tmp_base, make_run):
    from capevolve_dashboard import runs
    for i in range(5):
        make_run(f"run_{i}", events=BASE_EVENTS)
    assert len(runs.list_runs(tmp_base)) == 5
    r = _client(tmp_base).get("/api/runs")
    assert r.status_code == 200 and len(r.json()) == 5


def test_runs_pages_tile_the_full_list(tmp_base, make_run):
    from capevolve_dashboard import runs
    for i in range(5):
        make_run(f"run_{i}", events=BASE_EVENTS)
    full = [r["run_id"] for r in runs.list_runs(tmp_base)]
    paged = []
    for off in (0, 2, 4):
        page = runs.list_runs(tmp_base, limit=2, offset=off)
        assert len(page) <= 2
        paged += [r["run_id"] for r in page]
    assert paged == full                                  # no gaps, no repeats
    assert runs.list_runs(tmp_base, limit=2, offset=99) == []  # past the end


def test_runs_endpoint_limit_and_offset(tmp_base, make_run):
    for i in range(4):
        make_run(f"run_{i}", events=BASE_EVENTS)
    c = _client(tmp_base)
    first = c.get("/api/runs?limit=2").json()
    second = c.get("/api/runs?limit=2&offset=2").json()
    assert len(first) == 2 and len(second) == 2
    assert {r["run_id"] for r in first}.isdisjoint({r["run_id"] for r in second})
    assert c.get("/api/runs?limit=0").status_code == 422   # bounds are validated
    assert c.get("/api/runs?offset=-1").status_code == 422


# ---- /api/runs/{id}/rollouts ----------------------------------------------

def test_rollouts_pages_tile_the_full_list(tmp_base, make_run):
    from capevolve_dashboard import trajectories
    rd = make_run("run_a", events=BASE_EVENTS)
    for i in range(6):
        _write_rollout(rd, "val", f"t{i}", "cand_0001", 0)
    full = [r["file"] for r in trajectories.list_rollouts(rd.root)]
    assert len(full) == 6
    paged = []
    for off in (0, 3, 6):
        page = trajectories.list_rollouts(rd.root, limit=3, offset=off)
        assert len(page) <= 3
        paged += [r["file"] for r in page]
    assert paged == full
    assert trajectories.list_rollouts(rd.root, limit=3, offset=99) == []


def test_rollouts_paging_only_opens_the_page(tmp_base, make_run, monkeypatch):
    """The point of the change: a page costs one parse per row ON the page."""
    from capevolve_dashboard import trajectories
    rd = make_run("run_a", events=BASE_EVENTS)
    for i in range(20):
        _write_rollout(rd, "val", f"t{i:02d}", "cand_0001", 0)
    reads = []
    real = trajectories.json.loads
    monkeypatch.setattr(trajectories.json, "loads",
                        lambda s, *a, **k: (reads.append(1), real(s, *a, **k))[1])
    rows = trajectories.list_rollouts(rd.root, limit=5)
    assert len(rows) == 5
    assert len(reads) == 5, f"paged read parsed {len(reads)} files, want 5"


def test_rollouts_endpoint_limit_offset_and_split(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    for i in range(4):
        _write_rollout(rd, "val", f"t{i}", "cand_0001", 0)
    _write_rollout(rd, "train", "tx", "cand_0001", 0)
    c = _client(tmp_base)
    page = c.get("/api/runs/run_a/rollouts?split=val&limit=2").json()
    assert len(page) == 2 and all(r["split"] == "val" for r in page)
    rest = c.get("/api/runs/run_a/rollouts?split=val&limit=2&offset=2").json()
    assert {r["file"] for r in page}.isdisjoint({r["file"] for r in rest})
    assert len(c.get("/api/runs/run_a/rollouts").json()) == 5  # default: everything


# ---- SSE snapshot frame ---------------------------------------------------

def test_sse_snapshot_frame_carries_no_reduced_run(tmp_base, make_run, monkeypatch):
    """The client ignored the payload; it must no longer be serialized.

    A ``finalize`` event is injected on the first poll so the generator returns at
    once instead of holding the connection for the 5-minute idle timeout.
    """
    from capevolve_dashboard import stream as _stream
    make_run("run_a", events=BASE_EVENTS,
             baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    monkeypatch.setattr(_stream, "read_new_events",
                        lambda p, off: ([{"kind": "finalize"}], off))
    with _client(tmp_base).stream("GET", "/api/runs/run_a/stream") as r:
        assert r.status_code == 200
        frames = [ln for ln in r.iter_lines() if ln.startswith(("event:", "data:"))]
    assert frames[0] == "event: snapshot"
    # Payload is the open marker only — NOT {"graph": ..., "summary": ...}.
    assert json.loads(frames[1][len("data:"):]) == {"run_id": "run_a"}


# ---- page-size bounds (N5) and short pages (N6) ---------------------------

def test_page_size_is_capped(tmp_base, make_run):
    """``le=1000`` makes the contract self-documenting; a huge limit is a 422, not a 200."""
    make_run("run_a", events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    c = _client(tmp_base)
    for url in ("/api/runs", "/api/runs/run_a/rollouts"):
        assert c.get(f"{url}?limit=1000").status_code == 200
        assert c.get(f"{url}?limit=1001").status_code == 422
        assert c.get(f"{url}?limit=99999999999999999999").status_code == 422
        assert c.get(f"{url}?limit=0").status_code == 422
        assert c.get(f"{url}?offset=-1").status_code == 422


def test_a_short_page_is_not_the_end_of_the_list(tmp_base, make_run):
    """N6: a corrupt file is skipped AFTER windowing, so a page can be short mid-list.

    Pins the documented contract: page until you get an EMPTY page, not a short one.
    """
    rd = make_run("run_a", events=BASE_EVENTS,
                  baseline={"val": {"reward": 0.25}, "best_id": "seed"})
    for i in range(6):
        _write_rollout(rd, "val", f"t{i}", "cand_0001", 0)
    (rd.root / "rollouts" / "val" / "t1__cand_0001__t0.json").write_text("{ not json",
                                                                        encoding="utf-8")
    c = _client(tmp_base)
    first = c.get("/api/runs/run_a/rollouts?limit=3").json()
    assert len(first) == 2, "short page mid-list (the corrupt row was skipped)"
    second = c.get("/api/runs/run_a/rollouts?limit=3&offset=3").json()
    assert len(second) == 3, "a short page did NOT mean the list was exhausted"
    assert c.get("/api/runs/run_a/rollouts?limit=3&offset=6").json() == []  # empty = end
    # and paging still tiles the unpaged list exactly
    full = c.get("/api/runs/run_a/rollouts").json()
    assert [r["file"] for r in first + second] == [r["file"] for r in full]


def test_run_order_is_total_even_at_identical_mtimes(tmp_base, make_run):
    """N4: name tiebreaks the mtime sort, so pagination has a total order to tile."""
    import os
    from capevolve_dashboard import runs as R
    for n in ("run_c", "run_a", "run_b"):
        make_run(n, events=BASE_EVENTS, baseline={"val": {"reward": 0.25}, "best_id": "seed"})
        os.utime(tmp_base / n, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    order = [r["run_id"] for r in R.list_runs(tmp_base)]
    assert order == ["run_a", "run_b", "run_c"], order
    assert all([r["run_id"] for r in R.list_runs(tmp_base)] == order for _ in range(5))
    pages = R.list_runs(tmp_base, limit=2) + R.list_runs(tmp_base, limit=2, offset=2)
    assert [r["run_id"] for r in pages] == order  # pages tile the total order
