"""replay_gates.py on a synthetic artifact tree: rules, masking inference, champion-path/test linkage."""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("replay_gates", REPO / "research/capevolve-paper/analysis/scripts/replay_gates.py")
rg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rg)

IDS = [f"t{i:02d}" for i in range(20)]


def _tree(tmp_path):
    art = tmp_path / "111" / "bench"
    (art / "ui" / "data").mkdir(parents=True)
    (art / "runmeta.json").write_text(json.dumps({"bench": "b", "tier": "x", "algorithm": "hill-climb-all", "gate_k_se": 0.2}))
    seed = {t: 0.0 for t in IDS}
    c1 = {t: (1.0 if i < 8 else 0.0) for i, t in enumerate(IDS)}           # clear gain
    c2 = dict(c1); c2["t10"] = 1.0; c2["t13"] = 1.0; c2["t00"] = 0.0         # +2 -1: passes k=0.2, not k=1
    c3 = dict(c2); c3["t11"] = 1.0; c3["t01"] = 0.0                         # net 0 vs c2, yet recorded as a masked accept
    nodes = [{"id": "seed", "parent": None, "per_task": seed, "status": "seed"},
             {"id": "c1", "parent": "seed", "per_task": c1, "status": "accepted", "iteration": 1},
             {"id": "c2", "parent": "c1", "per_task": c2, "status": "accepted", "iteration": 2},
             {"id": "c3", "parent": "c2", "per_task": c3, "status": "accepted", "iteration": 3}]
    gd = [{"candidate": "c3", "delta": 0.05, "stderr": 0.03, "n": 20, "k_se": 0.2, "verdict": "accept"}]
    summ = {"algorithm": "hill-climb", "gate_decisions": gd, "splits": {"val": 20}, "test_reward": 0.7,
            "test_baseline_reward": 0.5, "test_delta": 0.2}
    (art / "ui" / "data" / "runs_run_suite.json").write_text(json.dumps({"summary": summ, "graph": {"nodes": nodes, "best_id": "c3"}}))
    (art / "metrics.jsonl").write_text("".join(json.dumps({"reward_baseline": 0.0, "reward_opt": float(i % 2)}) + "\n" for i in range(10)))
    return tmp_path


def test_replay_rules_masking_and_champion_path(tmp_path):
    runs = rg.load_runs(_tree(tmp_path))
    r = rg.replay_run(runs[0])
    by = {c["candidate"]: c for c in r["candidates"]}
    assert by["c1"]["outcomes"]["unmasked_k1"] is True
    assert by["c2"]["outcomes"]["k0.2"] is True and by["c2"]["outcomes"]["unmasked_k1"] is False
    assert "unmasked_k1" in by["c3"]["flips"] and by["c3"]["recorded_accept"] is True
    m = by["c3"]["masking"]
    assert m["applicable"] and m["masked_or_floored_inferred"] and m["excluded_net_delta_mass"] < 0
    assert by["c1"]["rules"]["rule_P"]["confirmation"].startswith("not replayable")
    agg = rg.aggregate([r])
    assert agg["path"]["unmasked_k1"]["champion_path_blocked"]["runs"] == 1
    assert agg["path"]["unmasked_k1"]["champion_path_blocked"]["test_deltas"] == [0.2]
    assert agg["masking"]["accepted_masked_unmasked_would_reject"] == 1
    assert "[INFERRED]" in rg.render([r], agg, "x")


def test_main_writes_outputs(tmp_path):
    hist = _tree(tmp_path / "h")
    rg.main(["--history", str(hist), "--out", str(tmp_path / "out")])
    d = json.loads((tmp_path / "out" / "replay_gates.json").read_text())
    assert d["aggregate"]["candidates"] == 3 and (tmp_path / "out" / "replay_gates.md").exists()


def test_fewer_recorded_tasks_is_a_dropped_task_not_masking(tmp_path):
    hist = _tree(tmp_path)
    f = hist / "111" / "bench" / "ui" / "data" / "runs_run_suite.json"
    d = json.loads(f.read_text())
    d["summary"]["gate_decisions"][0]["n"] = 19
    f.write_text(json.dumps(d))
    r = rg.replay_run(rg.load_runs(hist)[0])
    m = {c["candidate"]: c for c in r["candidates"]}["c3"]["masking"]
    assert m["dropped_task_inferred"] is True and m["masked_or_floored_inferred"] is False
    assert m["mismatch"].startswith("n_differs")
