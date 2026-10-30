"""Ablation switch ``abl_gate`` (none | disjoint): GATE-NONE and GATE-DISJOINT."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

FB = ["f1", "f2", "f3"]
GT = ["g17", "g18", "g19"]
ALL = FB + GT


class _Adapter:
    """A task passes iff its id is listed in the candidate's cfg.txt."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in ALL]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        cfg = [x[::-1] for x in (Path(ctx) / "cfg.txt").read_text().split()]   # ids stored reversed
        return Rollout(task_id=task.id, output="pass" if task.id in cfg else "fail")

    def score(self, task, rollout):
        from cap_evolve import Score
        ok = rollout.output == "pass"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, trial_rewards=[1.0 if ok else 0.0],
                     feedback=f"{task.id} {'ok' if ok else 'failed'}")

    def apply(self, candidate_dir, edits=None):
        return None


def _setup(tmp_path, spec: dict, seed_cfg):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    adapter = _Adapter()
    seed = tmp_path / "seed"
    seed.mkdir(parents=True)
    (seed / "cfg.txt").write_text(" ".join(x[::-1] for x in seed_cfg))
    rd = RunDir.create(tmp_path / ".capevolve", ts="ag")
    rd.write_splits(Splits(train=[], val=list(ALL), test=[], seed=0))
    rd.snapshot("seed", seed)
    rd.set_best("seed")
    specp = tmp_path / "capevolve.yaml"
    specp.write_text("\n".join(f"{k}: {json.dumps(v)}" for k, v in spec.items()) + "\n")
    rd.log_event("spec_resolved", spec=str(specp))
    base = harness.evaluate_candidate(adapter, rd.candidate_dir("seed"), run_dir=rd, split="val", tag="seed")
    return adapter, rd, base


def _opt(cfg):
    from cap_evolve import harness
    return harness.optimizer_from_command(
        ["python3", "-c", "import sys,pathlib; pathlib.Path(sys.argv[1], 'cfg.txt').write_text(sys.argv[2])",
         "{workdir}", " ".join(x[::-1] for x in cfg)])


def _step(adapter, rd, base, cfg, **kw):
    from cap_evolve import harness
    from cap_evolve.memory import History, RejectedMemory
    rej, hist = RejectedMemory(rd.rejected_path), History(rd.history_path)
    return harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir(rd.best_id), optimizer=_opt(cfg),
                            instructions="x", current_val=base, gate_kwargs={"mode": "strict"},
                            rejected=rej, history=hist, **kw)


def _events(rd, kind):
    return [json.loads(l) for l in rd.events_path.read_text().splitlines() if json.loads(l).get("kind") == kind]


# ---------------------------------------------------------------- validation
def test_settings_validation(tmp_path):
    from cap_evolve import abl_gate
    bad = [({"abl_gate": "bogus"}, "must be one of"),
           ({"abl_gate": "disjoint", "abl_feedback_ids": FB, "abl_gate_ids": []}, "non-empty"),
           ({"abl_gate": "disjoint", "abl_feedback_ids": FB, "abl_gate_ids": FB + ["g17"]}, "overlap"),
           ({"abl_gate": "disjoint", "abl_feedback_ids": FB, "abl_gate_ids": ["g17"]}, "partition")]
    for i, (spec, msg) in enumerate(bad):
        _, rd, _ = _setup(tmp_path / str(i), spec, ALL)
        with pytest.raises(ValueError, match=msg):
            abl_gate.settings(rd)
    _, rd, _ = _setup(tmp_path / "ok", {"abl_gate": "disjoint", "abl_feedback_ids": FB, "abl_gate_ids": GT}, ALL)
    assert abl_gate.settings(rd) == ("disjoint", FB, GT)
    _, rd, _ = _setup(tmp_path / "stock", {"gate_k_se": 1.0}, ALL)
    assert abl_gate.settings(rd) == (None, [], [])


# ---------------------------------------------------------------- GATE-NONE
def test_gate_none_accepts_what_stock_rejects_and_records_shadow(tmp_path):
    a, rd, base = _setup(tmp_path / "n", {"abl_gate": "none"}, ALL)
    step = _step(a, rd, base, FB + GT[:1])          # strictly worse
    assert step["accepted"] is True
    assert step["decision"]["reason"].startswith("GATE-NONE: accepted without test; stock gate would have said accept=False")
    assert rd.best_id == step["candidate_id"]
    ev = _events(rd, "step")[-1]
    assert ev["accept"] is True and ev["abl_gate_shadow"]["accept"] is False
    # stock arm: the same candidate is rejected
    a, rd2, base2 = _setup(tmp_path / "s", {"gate_k_se": 1.0}, ALL)
    st = _step(a, rd2, base2, FB + GT[:1])
    assert st["accepted"] is False and "abl_gate_shadow" not in _events(rd2, "step")[-1]


# ------------------------------------------------------------ GATE-DISJOINT
DIS = {"abl_gate": "disjoint", "abl_feedback_ids": FB, "abl_gate_ids": GT}


def test_disjoint_better_on_F_worse_on_G_is_rejected(tmp_path):
    a, rd, base = _setup(tmp_path, DIS, ["f1", "g17", "g18", "g19"])   # F: 1/3, G: 3/3
    step = _step(a, rd, base, ["f1", "f2", "f3", "g17"])               # F up, G down
    assert step["accepted"] is False
    ev = _events(rd, "step")[-1]
    assert ev["abl_gate_disjoint"]["gate_reward"] < ev["abl_gate_disjoint"]["gate_parent_reward"]


def test_disjoint_worse_on_F_better_on_G_is_accepted(tmp_path):
    a, rd, base = _setup(tmp_path, DIS, ["f1", "f2", "f3", "g17"])     # F: 3/3, G: 1/3
    step = _step(a, rd, base, ["f1", "g17", "g18", "g19"])             # F down, G up
    assert step["accepted"] is True
    assert rd.best_id == step["candidate_id"]
    # the incumbent the loop carries over is the FULL val
    assert len(step["candidate_val"]["per_task"]) == 6


def test_restrict_recomputes_with_harness_aggregation(tmp_path):
    from cap_evolve import abl_gate
    _, rd, base = _setup(tmp_path, DIS, ["f1", "g17", "g18"])
    r = abl_gate.restrict(base, GT)
    assert [p["task_id"] for p in r.per_task] == GT and r.n_scored == 3
    assert abs(r.reward - 2 / 3) < 1e-9 and abs(base.reward - 0.5) < 1e-9


def test_scrub_reason():
    from cap_evolve import abl_gate
    t = "paired Δ̄=+0.1 > 1.0·SE; REJECTED by no-regression gate (broke ['g17', 'g18']); broke {g19} f1"
    out = abl_gate.scrub_reason(t, GT)
    assert not any(g in out for g in GT) and "f1" in out and "+0.1" in out


def test_disjoint_proposer_artifacts_never_name_a_gate_task(tmp_path):
    from cap_evolve import harness
    a, rd, base = _setup(tmp_path, DIS, ["f1", "f2", "g17", "g18", "g19"])
    # candidate 1: breaks f2 and g17 (rejected); candidate 2: fixes f3, breaks g19 (rejected on G)
    s1 = _step(a, rd, base, ["f1", "g18", "g19"])
    s2 = _step(a, rd, base, ["f1", "f2", "f3", "g17", "g18"])
    assert not s1["accepted"] and not s2["accepted"]
    # proposer-facing: a fresh workdir via the real context assembly
    wd = rd.root / "work" / "probe"
    wd.mkdir(parents=True)
    ctx = harness.OptimizerContext()
    ctx.inject(a, rd, wd, split="val")
    text = ctx.augment_instructions(ctx.instructions(
        __import__("cap_evolve").abl_gate.for_proposer(rd, base), None, "x", algorithm="hill_climb"), wd, rd)
    blobs = [text]
    for p in list(wd.rglob("*")) + [rd.rejected_path, rd.history_path, rd.root / "JOURNAL.md"]:
        if Path(p).is_file():
            blobs.append(Path(p).read_text(errors="ignore"))
            blobs.append(Path(p).name)
    all_text = "\n".join(blobs)
    assert "f1" in all_text                                   # F is visible
    for g in GT:
        assert g not in all_text, g
    traj = sorted(p.name.split("__")[0] for p in (wd / "trajectories").glob("*.json"))
    assert traj and set(traj) <= set(FB)
    ledger = (wd / "LEDGER.md").read_text()
    assert "cand_0001" in ledger


def test_hill_climb_loop_disjoint_carries_full_val(tmp_path):
    from cap_evolve import harness
    a, rd, base = _setup(tmp_path, DIS, ["f1", "f2", "f3", "g17"])
    seen = []

    def opt(workdir, instructions):
        seen.append(instructions)
        Path(workdir, "cfg.txt").write_text(" ".join(x[::-1] for x in ["f1", "g17", "g18", "g19"]))
        return None

    out = harness.hill_climb_loop(a, run_dir=rd, optimizer=opt, current_val=base, max_iterations=1,
                                  gate_kwargs={"mode": "strict"})
    assert out["accepts"] == 1 and out["best_val"] == pytest.approx(4 / 6)
    assert not any(g in seen[0] for g in GT)
