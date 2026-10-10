"""#707: offline replay of the recorded run_20261008_150326 through the new engine + the ablation
harness (skills/algorithms/agent-optimize/scripts/ablate.py). Fixture: fixtures/replay_run_20261008.json
(per-rollout rewards only). Simulator numbers are NOT evidence of real performance; these tests check the
decision machinery and that every switch is actually plumbed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

import ablate  # noqa: E402
import merge_n  # noqa: E402
import pytest  # noqa: E402
import pregate  # noqa: E402
from cap_evolve.candidate_graph import CandidateGraph  # noqa: E402

FX = Path(__file__).parent / "fixtures"
FIX = ablate.load_fixture(FX / "replay_run_20261008.json")


def test_fixture_is_the_recorded_run():
    assert FIX["spent"]["total"] == 2270 and sum(v["n"] for v in FIX["tags"].values()) == FIX["spent"]["val"]
    assert ablate.FIXTURE == FX / "replay_run_20261008.json"
    assert len(ablate.task_ids(FIX)) == 30


def test_cand10_is_caught_by_pregate_before_any_val_rollout():
    r = pregate.hidden_writes_dirs(FX / "pregate" / "cand_10", FX / "pregate" / "seed")
    assert not r["ok"] and "update_reservation_cabin -> update_reservation_flights" in r["detail"]
    rows = ablate.replay_candidates(FIX, pregate_rejects={"cand_10"}, resamples=2, m=60)
    assert rows["cand_10"]["mean_rollouts"] == 0 and rows["cand_10"]["decisions"] == {"pregate_reject": 2}


def test_cand345_policy_collisions_are_real_conflicts_for_merge_n(tmp_path):
    md = FX / "md_blocks"
    tags = ["cand_3", "cand_4", "cand_5"]
    g = CandidateGraph({k: {"id": k, "parents": v, "children": []}
                        for k, v in {"seed": [], **{t: ["seed"] for t in tags}}.items()})
    r = merge_n.merge_n(tags, lambda t: md / t, g, tmp_path / "out")
    assert not r["built"] and r["unmerged"] and r["conflicts"]
    assert all(c["proposal"] for c in r["conflicts"])


@pytest.fixture(scope="module")
def report():
    return ablate.replay_report(FIX, {"cand_10"}, n_splits=3, m=100)


def test_no_accept_among_identical_bytes_pairs_except_the_known_drift_hash(report):
    per = report["identical_bytes_pairs"]["per_capability"]
    tot = report["identical_bytes_pairs"]["total"]
    assert tot["pairs"] == 38
    assert all(per[g]["new_engine_accepts"] == 0 for g in ("seed", "cand_1", "cand_4"))
    # cand_7's evals differ by drift (.567/.689/.700); the replay cannot interleave, so <=1 pair may
    # be fooled -- reported, not hidden. The original gate false-accepts ~40% of the same pairs.
    assert tot["new_engine_accepts"] <= 1 and tot["legacy_gate_false_accepts"] >= 0.25 * tot["pairs"]
    assert all(v["new_engine_accepts"] == 0 for v in report["identical_bytes_resplits"].values())


def test_new_engine_requests_fewer_rollouts_than_were_spent_and_no_controls(report):
    assert report["control_rollouts"] == 0
    assert 0 < report["new_engine_rollouts"] < report["recorded_spent"]["total"]
    c = report["candidates"]
    assert set(c["cand_2"]["decisions"]) == {"prune"}
    assert c["cand_10"]["mean_rollouts"] == 0
    assert "cand_9" not in c


def test_every_arm_resolves_to_its_explicit_config_and_ignores_env(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_DAG_PARALLEL", "0")
    for a in ablate.ARMS:
        assert ablate.resolve_arm(a) == ablate.arm_config(a)
    assert ablate.arm_config("baseline_original") == dict.fromkeys(ablate.KEYS, False)
    assert all(ablate.arm_config("full").values())
    assert ablate.arm_config("full_no_pregate")["pregate"] is False
    assert ablate.arm_config("shipped_default") == ablate.optimizer_config.DEFAULTS


def _sim(arm, seeds=4, budget=600):
    res = ablate.simulate([arm], n_seeds=seeds, budget=budget, m=60, fx=FIX)
    return res, [r["decisions"] for r in res["arms"][arm]["runs"]]


def test_switches_change_behaviour():
    _, on = _sim("full")
    _, off = _sim("full_no_pregate")
    assert sum(d.get("pregate_reject", 0) for d in on) > 0 and not any("pregate_reject" in d for d in off)
    _, nog = _sim("full_no_cost_gating")
    assert not any("cost_reject" in d for d in nog)
    r_old, _ = _sim("baseline_original")
    r_new, _ = _sim("adaptive_only")
    assert r_new["arms"]["adaptive_only"]["summary"]["false_accepts"]["mean"] <= \
        r_old["arms"]["baseline_original"]["summary"]["false_accepts"]["mean"]


def test_output_is_labelled_deterministic_and_has_curves_and_cis():
    a = ablate.simulate(["baseline_original", "full"], n_seeds=20, budget=300, m=40, fx=FIX)
    b = ablate.simulate(["baseline_original", "full"], n_seeds=20, budget=300, m=40, fx=FIX)
    assert a == b
    assert "NOT EVIDENCE" in a["label"] and "NOT EVIDENCE" in ablate.markdown(a)
    arm = a["arms"]["full"]
    assert len(arm["runs"]) == 20 and len(arm["curve_reward_vs_rollouts"]) == 16 == len(arm["curve_reward_vs_usd"])
    g = arm["summary"]["gain"]
    assert g["lo"] <= g["mean"] <= g["hi"]
    assert arm["curve_reward_vs_rollouts"][0]["mean"] == a["seed_true_mean"]
    json.dumps(a)


def test_real_mode_only_writes_specs_with_ablation_block(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text("capabilities: [system-prompt]\n", encoding="utf-8")
    cmds = ablate.real_plan(base, tmp_path, ["baseline_original", "full"], range(2))
    assert len(cmds) == 4 and all(c.startswith("cap-evolve run --spec ") for c in cmds)
    from cap_evolve.specfile import read_yaml
    spec = read_yaml((tmp_path / "specs" / "full.yaml").read_text(encoding="utf-8"))
    assert set(spec["optimizer"]["ablation"]) == set(ablate.KEYS)
    base.write_text("optimizer:\n  x: 1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        ablate.real_plan(base, tmp_path, ["full"])
