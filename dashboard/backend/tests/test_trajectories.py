import json

from fastapi.testclient import TestClient

from conftest import BASE_EVENTS


def _client(base):
    from capevolve_dashboard.app import create_app
    return TestClient(create_app(base))


def _write_rollout(rd, split, task, cand, trial, reward, feedback):
    d = rd.root / "rollouts" / split
    d.mkdir(parents=True, exist_ok=True)
    name = f"{task}__{cand}__t{trial}.json"
    (d / name).write_text(json.dumps({
        "input": f"in-{task}",
        "rollout": {"task_id": task, "output": "out", "trace": "...",
                    "tool_calls": [{"name": "calc"}], "cost_usd": 0.0,
                    "tokens": 0, "error": None, "metadata": {}},
        "score": {"task_id": task, "reward": reward, "feedback": feedback,
                  "n": 1, "stderr": 0.0, "trial_rewards": [reward], "raw": {}},
    }), encoding="utf-8")
    return name


def test_list_rollouts(tmp_base, make_run):
    from capevolve_dashboard import trajectories
    rd = make_run("run_a", events=BASE_EVENTS)
    _write_rollout(rd, "val", "t1", "cand_0001", 0, 1.0, "correct")
    _write_rollout(rd, "val", "t2", "cand_0001", 0, 0.0, "wrong")
    rows = trajectories.list_rollouts(rd.root)
    assert {r["task_id"] for r in rows} == {"t1", "t2"}
    assert all(r["candidate"] == "cand_0001" for r in rows)


def test_rollouts_endpoint(tmp_base, make_run):
    rd = make_run("run_a", events=BASE_EVENTS)
    _write_rollout(rd, "val", "t1", "cand_0001", 0, 1.0, "correct")
    r = _client(tmp_base).get("/api/runs/run_a/rollouts?split=val")
    assert r.status_code == 200
    assert r.json()[0]["task_id"] == "t1"


def test_diff_endpoint_no_git_is_empty(tmp_base, make_run):
    make_run("run_a", events=BASE_EVENTS)
    r = _client(tmp_base).get("/api/runs/run_a/diff/cand_0001")
    assert r.status_code == 200
    assert r.json()["files"] == []
