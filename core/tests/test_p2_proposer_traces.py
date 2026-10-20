"""What the P2 proposer reads after an accept or a reject: the current champion's own F trials, and each
prior candidate's own F trials, never the seed's alone and never a C trial."""

import json
import tempfile
from pathlib import Path

from p2_fakes import make_run

from cap_evolve import harness, promotion  # noqa: E402


def _opt(cfg):
    f = Path(tempfile.mkdtemp()) / "c.json"
    f.write_text(json.dumps(cfg))
    code = ("import sys,pathlib; w=pathlib.Path(sys.argv[1]); "
            "(w/'cfg.json').write_text(pathlib.Path(sys.argv[2]).read_text())")
    return harness.optimizer_from_command(["python3", "-c", code, "{workdir}", str(f)])


def _setup(tmp_path):
    adapter, run_dir = make_run(tmp_path, n_train=24, n_val=24, default=0.4)
    base = harness.baseline_pooled(adapter, tmp_path / "seed", run_dir=run_dir, n_trials=4)
    return adapter, run_dir, base


def _step(adapter, run_dir, current, cfg, **gk):
    return harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir(run_dir.best_id),
                            optimizer=_opt(cfg), instructions="x", current_val=current, n_trials=1,
                            gate_kwargs={"promotion_rule": "P2", "p2_conf_n": 96, **gk})


def _tags_in(d: Path) -> set:
    return {f.stem.rsplit("__t", 1)[0].split("__", 1)[1] for f in d.glob("*.json")}


def test_after_an_accept_the_next_proposer_reads_the_champions_own_f_trials(tmp_path):
    adapter, run_dir, base = _setup(tmp_path)
    s1 = _step(adapter, run_dir, base, {"default": 0.9, "p": {}})
    assert s1["accepted"] and run_dir.best_id == "cand_0001"
    nxt = harness.SplitResult.from_dict(s1["baseline_val"])
    f_ids = set(run_dir.read_splits().feedback)
    assert {pt["task_id"] for pt in nxt.per_task} == f_ids
    assert all(pt["n"] >= promotion.P2Params().champion_trials for pt in nxt.per_task)
    assert nxt.reward > base.reward

    _step(adapter, run_dir, nxt, {"default": 0.05, "p": {}})
    traj = run_dir.root / "work" / "cand_0002" / "trajectories"
    tags = _tags_in(traj)
    assert tags and all("cand_0001" in t for t in tags) and "seed" not in tags
    assert {f.name.split("__")[0] for f in traj.glob("*.json")} == f_ids


def test_each_prior_candidate_folder_holds_its_own_f_trials_and_no_c_trial(tmp_path):
    adapter, run_dir, base = _setup(tmp_path)
    _step(adapter, run_dir, base, {"default": 0.05, "p": {}})      # killed at rung 1
    _step(adapter, run_dir, base, {"default": 0.06, "p": {}, "salt": 1})
    prior = run_dir.root / "work" / "cand_0002" / "prior_iterations" / "cand_0001" / "trajectories"
    assert prior.is_dir()
    assert _tags_in(prior) == {"r000__cand_0001__rung1_0"}
    sp = run_dir.read_splits()
    assert {f.name.split("__")[0] for f in prior.glob("*.json")} <= set(sp.feedback)
    runmap = (run_dir.root / "work" / "cand_0002" / "RUNMAP.md").read_text()
    assert "trajectories/ (" in runmap


def test_champion_trials_zero_keeps_only_the_rung_trials(tmp_path):
    adapter, run_dir, base = _setup(tmp_path)
    s1 = _step(adapter, run_dir, base, {"default": 0.9, "p": {}}, p2_champion_trials=0)
    assert s1["accepted"]
    nxt = harness.SplitResult.from_dict(s1["baseline_val"])
    assert len(nxt.per_task) == promotion.P2Params().rung_sizes[0]


def test_candidate_rollout_tags_finds_round_tags_and_never_reads_confirm(tmp_path):
    _, run_dir = make_run(tmp_path)
    d = run_dir.rollout_dir("feedback")
    d.mkdir(parents=True)
    for name in ("a__seed__t0", "a__r001__cand_0002__rung1_0__t1", "a__r002__cand_0002__inc_p0_0__t2",
                 "a__cand_0002__champ_p0__t3", "a__r002__cand_0020__rung1_0__t4", "a__cand_0002__t5"):
        (d / f"{name}.json").write_text("{}")
    assert harness.candidate_rollout_tags(run_dir, "cand_0002", "feedback") == [
        "cand_0002", "cand_0002__champ_p0", "r001__cand_0002__rung1_0", "r002__cand_0002__inc_p0_0"]
    assert harness.candidate_rollout_tags(run_dir, "seed", "feedback") == ["seed"]
    assert harness.candidate_rollout_tags(run_dir, "cand_0002", "confirm") == []
