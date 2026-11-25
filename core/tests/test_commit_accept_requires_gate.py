"""#763: commit.py --decision accept needs a passing gate record, or --accept-without-gate."""

from __future__ import annotations

import copy
import json

import test_inconclusive_requires_growth as base


def _staged(tmp_path, verdict=None):
    run_dir, work = base._staged(tmp_path)
    t = copy.deepcopy(base.UNSTABLE_TABLE)
    if verdict is None:
        t["candidates"] = []
    else:
        t["candidates"][0]["verdict"] = verdict
    (run_dir.root / "work" / "round_i0.json").write_text(json.dumps(t), encoding="utf-8")
    return run_dir, work


def _best(run_dir):
    from cap_evolve import RunDir
    return RunDir.open(run_dir.root).best_id


def _events(run_dir):
    return [json.loads(x) for x in run_dir.events_path.read_text().splitlines() if x.strip()]


def test_accept_without_gate_row_exits_2_and_keeps_best(tmp_path):
    run_dir, work = _staged(tmp_path)
    before = _best(run_dir)
    p = base._commit(run_dir, work, decision="accept")
    assert p.returncode == 2, p.stdout + p.stderr
    assert "no passing gate record" in p.stdout
    assert _best(run_dir) == before


def test_accept_with_passing_gate_row_accepts(tmp_path):
    run_dir, work = _staged(tmp_path, verdict="accept")
    p = base._commit(run_dir, work, decision="accept")
    assert p.returncode == 0, p.stdout + p.stderr
    assert _best(run_dir) == "cand_2"


def test_accept_with_promote_gate_event_accepts(tmp_path):
    run_dir, work = _staged(tmp_path)
    run_dir.log_event("promote_gate", candidate="cand_2", verdict="accept", reference="seed")
    p = base._commit(run_dir, work, decision="accept")
    assert p.returncode == 0, p.stdout + p.stderr


def test_accept_without_gate_escape_records_reason(tmp_path):
    run_dir, work = _staged(tmp_path)
    p = base._commit(run_dir, work, "--accept-without-gate", "gate infra down", decision="accept")
    assert p.returncode == 0, p.stdout + p.stderr
    assert _best(run_dir) == "cand_2"
    evs = [e for e in _events(run_dir) if e["kind"] == "accept_without_gate"]
    assert evs and evs[0]["reason"] == "gate infra down"
    acc = [e for e in _events(run_dir) if e["kind"] == "accept"]
    assert acc[-1]["accepted_without_gate"] == "gate infra down"


# --- the REAL gate_check.py, run as a subprocess -------------------------------------------

import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_S = _ROOT / "skills" / "algorithms" / "agent-optimize" / "scripts"
_J = ["--missing-handover-justification", "x", "--missing-ranked-issues-justification", "x",
      "--missing-diagnosis-justification", "x"]


class _Real:
    def __init__(self, tmp_path):
        from cap_evolve import Budget, RunDir, harness
        from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir
        self.harness = harness
        self.ad = SyntheticAdapter(n=12)
        seed = seed_capability_dir(tmp_path, level=3)
        self.rd = RunDir.create(tmp_path / ".capevolve", ts="t81", budget=Budget(max_iterations=9, stall=9))
        harness.ensure_splits(self.ad, self.rd, seed=0)
        harness.baseline(self.ad, seed, run_dir=self.rd)
        self.env = {**os.environ, "CAPEVOLVE_CORE": str(_ROOT / "core"), "PYTHONPATH": str(_ROOT / "core")}

    def mk(self, tag, lvl):
        w = self.rd.root / "work" / tag
        w.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.rd.root / "candidates" / "seed", w)
        (w / "level.txt").write_text(str(lvl))
        self.harness.evaluate_candidate(self.ad, w, run_dir=self.rd, split="val", n_trials=1, tag=tag)
        return w

    def run(self, script, *a):
        p = subprocess.run([sys.executable, str(_S / script), "--run-dir", str(self.rd.root), *a],
                           capture_output=True, text=True, env=self.env)
        return p

    def gate(self, tag, *extra):
        p = self.run("gate_check.py", "--candidate", tag, "--k-se", "1.0", *extra)
        return json.loads(p.stdout)["verdict"]

    def commit(self, tag, w, *extra):
        m = self.harness.split_result_from_rollouts(self.rd, tag, "val").reward
        return self.run("commit.py", "--candidate-id", tag, "--from-dir", str(w), "--decision",
                        "accept", "--val", str(m), "--note", "n", *_J, *extra)

    def best(self):
        from cap_evolve import RunDir
        return RunDir.open(self.rd.root).best_id


def test_real_gate_check_accept_then_commit_accepts(tmp_path):
    r = _Real(tmp_path)
    w = r.mk("candA", 12)
    assert r.commit("candA", w).returncode == 2  # no gate yet
    assert r.gate("candA") == "accept"
    p = r.commit("candA", w)
    assert p.returncode == 0, p.stdout + p.stderr
    assert r.best() == "candA"
    acc = [e for e in _events(r.rd) if e["kind"] == "accept"][-1]
    assert acc["gate_verdict"] == "accept" and acc["gate_reference"] == "seed"


def test_stale_reference_gate_does_not_let_a_loser_replace_champion(tmp_path):
    r = _Real(tmp_path)
    wa = r.mk("candA", 12)
    assert r.gate("candA") == "accept"
    assert r.commit("candA", wa).returncode == 0
    wb = r.mk("candB", 6)
    assert r.gate("candB") == "reject"  # vs champion candA
    assert r.commit("candB", wb).returncode == 2
    assert r.gate("candB", "--current", "seed") == "accept"  # weaker reference
    p = r.commit("candB", wb)
    assert p.returncode == 2, p.stdout + p.stderr
    assert r.best() == "candA"


def test_pooled_reference_containing_champion_counts(tmp_path):
    r = _Real(tmp_path)
    r.mk("seed_rep", 3)
    w = r.mk("candA", 12)
    assert r.gate("candA", "--current", "seed,seed_rep") == "accept"
    p = r.commit("candA", w)
    assert p.returncode == 0, p.stdout + p.stderr
    assert r.best() == "candA"


def test_pooled_reference_of_identical_copies_of_champion_counts(tmp_path):
    r = _Real(tmp_path)
    r.mk("ctl_a", 3)  # same bytes as seed
    r.mk("ctl_b", 3)
    w = r.mk("candA", 12)
    assert r.gate("candA", "--current", "ctl_a,ctl_b") == "accept"
    assert r.commit("candA", w).returncode == 0
    assert r.best() == "candA"


def test_pooled_reference_with_different_bytes_refused(tmp_path):
    r = _Real(tmp_path)
    r.mk("ctl_a", 3)
    r.mk("ctl_b", 4)  # not a copy of the champion
    w = r.mk("candA", 12)
    assert r.gate("candA", "--current", "ctl_a,ctl_b") == "accept"
    assert r.commit("candA", w).returncode == 2
    assert r.best() == "seed"


def test_pooling_champion_with_weaker_candidate_does_not_let_loser_in(tmp_path):
    r = _Real(tmp_path)
    wa = r.mk("candA", 12)
    assert r.gate("candA") == "accept"
    assert r.commit("candA", wa).returncode == 0
    wb = r.mk("candB", 9)
    assert r.gate("candB") == "reject"
    r.gate("candB", "--current", "candA,seed")
    assert r.commit("candB", wb).returncode == 2
    assert r.best() == "candA"


def test_pooled_reference_with_unknown_hash_refused(tmp_path):
    r = _Real(tmp_path)
    w = r.mk("candA", 12)
    r.run("gate_check.py", "--candidate", "candA", "--k-se", "1.0", "--current", "seed,ghost")
    assert r.commit("candA", w).returncode == 2
    assert r.best() == "seed"


def test_real_gate_check_reject_then_commit_accept_refused(tmp_path):
    r = _Real(tmp_path)
    w = r.mk("candC", 1)
    assert r.gate("candC") == "reject"
    assert r.commit("candC", w).returncode == 2
    assert r.best() == "seed"


def _table(r, tag_verdicts, parent, name, mtime=None):
    t = {"parent": {"tag": parent}, "candidates": [{"tag": t, "verdict": v} for t, v in tag_verdicts]}
    path = r.rd.root / "work" / name
    path.write_text(json.dumps(t), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_round_reject_not_overruled_by_advisory_side_check(tmp_path):
    import time
    r = _Real(tmp_path)
    w = r.mk("candX", 12)
    _table(r, [("candX", "reject")], "seed", "round_i0.json", time.time() - 100)
    assert r.gate("candX", "--current", "seed", "--advisory", "raw_vs_parent") == "accept"
    assert r.commit("candX", w).returncode == 2
    assert r.best() == "seed"


def test_round_table_accept_loses_to_newer_gate_reject_vs_champion(tmp_path):
    import time
    r = _Real(tmp_path)
    wa, wb = r.mk("candA", 12), r.mk("candB", 6)
    _table(r, [("candA", "accept"), ("candB", "accept")], "seed", "round_i0.json", time.time() - 100)
    assert r.commit("candA", wa).returncode == 0
    assert r.gate("candB") == "reject"  # vs champion candA, newer than the table
    p = r.commit("candB", wb)
    assert p.returncode == 2, p.stdout + p.stderr
    assert r.best() == "candA"


def test_round_table_accept_vs_old_parent_refused_after_champion_change(tmp_path):
    import time
    r = _Real(tmp_path)
    wa, wb = r.mk("candA", 12), r.mk("candB", 6)
    _table(r, [("candA", "accept"), ("candB", "accept")], "seed", "round_i0.json", time.time() - 100)
    assert r.commit("candA", wa).returncode == 0
    assert r.commit("candB", wb).returncode == 2  # table's reference (seed) is no longer the champion
    assert r.best() == "candA"


def test_leftover_promote_gate_cannot_be_reused(tmp_path):
    r = _Real(tmp_path)
    wa, wb = r.mk("candA", 12), r.mk("candB", 6)
    r.rd.log_event("promote_gate", candidate="candB", verdict="accept", reference="seed")
    r.rd.log_event("promote_gate", candidate="candB", verdict="cancelled", reference="seed")
    assert r.gate("candA") == "accept"
    assert r.commit("candA", wa).returncode == 0
    assert r.commit("candB", wb).returncode == 2
    assert r.best() == "candA"
    # even an uncancelled one is tied to its reference
    r.rd.log_event("promote_gate", candidate="candB", verdict="accept", reference="seed")
    assert r.commit("candB", wb).returncode == 2
    assert r.best() == "candA"


def test_act_commit_cancels_promote_gate_on_refusal(tmp_path):
    if str(_S) not in sys.path:
        sys.path.insert(0, str(_S))
    import act
    r = _Real(tmp_path)
    proj = tmp_path / "proj"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text("class Adapter: pass\n", encoding="utf-8")

    class Ctx:
        root = str(r.rd.root)
        run_dir = r.rd
        project = str(proj)

        def work(self, tag):
            return str(r.rd.root / "work" / tag)

    orig = act.sh
    act.sh = lambda cmd: (2, "{}", "")
    try:
        rc, _ = act.commit(Ctx(), "candB", "accept", "n", [], verdict="accept", reference="seed")
    finally:
        act.sh = orig
    assert rc == 2
    gates = [e for e in _events(r.rd) if e["kind"] == "promote_gate"]
    assert [g["verdict"] for g in gates] == ["accept", "cancelled"]
    assert gates[0]["reference"] == "seed"


def test_provisional_then_real_grow_accept_then_commit_accepts(tmp_path):
    """grow.py's pooled row records its reference, so its `promote` -> commit accept works."""
    r = _Real(tmp_path)
    proj = tmp_path / "proj"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter as _S\n"
        "class Adapter(_S):\n    def __init__(self):\n        super().__init__(n=12)\n",
        encoding="utf-8")
    w = r.mk("candA", 12)
    val = str(r.harness.split_result_from_rollouts(r.rd, "candA", "val").reward)
    pv = r.run("commit.py", "--candidate-id", "candA", "--from-dir", str(w), "--decision",
               "provisional", "--val", val, "--note", "n", *_J)
    assert pv.returncode == 0, pv.stdout + pv.stderr
    g = r.run("grow.py", "--project", str(proj), "--candidate", "candA", "--add-trials", "1",
              "--growth-round", "1", "--k-se", "1.0")
    assert g.returncode == 0, g.stdout + g.stderr
    assert json.loads(g.stdout)["recommendation"] == "promote"
    p = r.commit("candA", w)
    assert p.returncode == 0, p.stdout + p.stderr
    assert r.best() == "candA"


# --- gate strictness is recorded and enforced (#1011 review) -------------------------------

def _write_spec(r, text):
    d = r.rd.root.parent / "project"
    d.mkdir(parents=True, exist_ok=True)
    (d / "capevolve.yaml").write_text(text, encoding="utf-8")


def test_looser_gate_k_se_than_spec_is_refused(tmp_path):
    r = _Real(tmp_path)
    _write_spec(r, "gate_k_se: 1.0\n")
    w = r.mk("candA", 12)
    p = r.run("gate_check.py", "--candidate", "candA", "--k-se", "0")
    assert json.loads(p.stdout)["verdict"] == "accept"
    p = r.commit("candA", w)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "looser" in p.stdout
    assert r.best() == "seed"


def test_normal_gate_accept_commits_and_event_carries_settings(tmp_path):
    r = _Real(tmp_path)
    _write_spec(r, "gate_k_se: 1.0\n")
    w = r.mk("candA", 12)
    assert r.gate("candA") == "accept"
    p = r.commit("candA", w)
    assert p.returncode == 0, p.stdout + p.stderr
    g = [e for e in _events(r.rd) if e["kind"] == "gate_check"][-1]
    assert g["k_se"] == 1.0 and "threshold" in g and "candidate_min_trial" in g
    acc = [e for e in _events(r.rd) if e["kind"] == "accept"][-1]
    assert acc["gate_settings"]["k_se"] == 1.0


def test_act_commit_without_measured_verdict_does_not_pass(tmp_path):
    if str(_S) not in sys.path:
        sys.path.insert(0, str(_S))
    import act
    r = _Real(tmp_path)
    w = r.mk("candA", 12)
    proj = tmp_path / "proj"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text("class Adapter: pass\n", encoding="utf-8")

    class Ctx:
        root = str(r.rd.root)
        run_dir = r.rd
        project = str(proj)

        def work(self, tag):
            return str(w)

    rc, _ = act.commit(Ctx(), "candA", "accept", "n", ["--val", "1.0", *_J])
    assert rc == 2
    assert not [e for e in _events(r.rd) if e["kind"] == "promote_gate" and e["verdict"] == "accept"]
    assert r.best() == "seed"


def test_looser_gate_checked_against_the_runs_own_spec_file(tmp_path):
    r = _Real(tmp_path)
    d = r.rd.root.parent / "project"
    d.mkdir(parents=True, exist_ok=True)
    (d / "capevolve.agentopt.yaml").write_text("gate_k_se: 1.0\n", encoding="utf-8")
    r.rd.log_event("run_config", spec=str(d / "capevolve.agentopt.yaml"))
    w = r.mk("candA", 12)
    r.run("gate_check.py", "--candidate", "candA", "--k-se", "0")
    p = r.commit("candA", w)
    assert p.returncode == 2, p.stdout + p.stderr
    assert r.best() == "seed"


def test_round_table_k_se_is_checked(tmp_path):
    r = _Real(tmp_path)
    _write_spec(r, "gate_k_se: 1.0\n")
    w = r.mk("candA", 12)
    (r.rd.root / "work").mkdir(exist_ok=True)
    (r.rd.root / "work" / "round_i0.json").write_text(json.dumps(
        {"parent": {"tag": "seed"},
         "candidates": [{"tag": "candA", "verdict": "accept", "k_se": 0.0}]}), encoding="utf-8")
    p = r.commit("candA", w)
    assert p.returncode == 2, p.stdout + p.stderr
    assert r.best() == "seed"


def test_strict_mode_against_paired_spec_is_refused(tmp_path):
    r = _Real(tmp_path)
    _write_spec(r, "gate_mode: paired\ngate_k_se: 1.0\n")
    w = r.mk("candA", 12)
    r.run("gate_check.py", "--candidate", "candA", "--mode", "strict", "--k-se", "1.0")
    p = r.commit("candA", w)
    assert p.returncode == 2, p.stdout + p.stderr
    assert r.best() == "seed"


def test_round_table_strict_mode_against_paired_spec_is_refused(tmp_path):
    r = _Real(tmp_path)
    _write_spec(r, "gate_mode: paired\ngate_k_se: 1.0\n")
    w = r.mk("candA", 12)
    r.run("gate_check.py", "--candidate", "candA", "--mode", "strict", "--k-se", "1.0")
    (r.rd.root / "work").mkdir(exist_ok=True)
    (r.rd.root / "work" / "round_i0.json").write_text(json.dumps(
        {"parent": {"tag": "seed"},
         "candidates": [{"tag": "candA", "verdict": "accept", "k_se": 1.0,
                         "mode": "strict"}]}), encoding="utf-8")
    p = r.commit("candA", w)
    assert p.returncode == 2, p.stdout + p.stderr
    assert r.best() == "seed"
