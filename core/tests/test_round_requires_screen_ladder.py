"""issue #420 item 4: full-val evaluation must go through the screen ladder by default.

Run 33492876620 paid a full 100-rollout sweep for every one of 7 candidates, including
``cand_scope`` (clearly harmful) and ``cand_e2_verifytype`` (flat) — exactly the cases
``screen.py`` exists to kill for a quarter of the price. It was never used because using it
was optional. ``round.py`` now refuses a candidate with no ``$R/screens/<tag>__screen*.json``
record unless the driver passes ``--skip-screen-ladder``.

Also covers issue #420 item 9: ``round.py`` records ``measurement_max_parallel`` alongside
``measurement_concurrency``, and warns when either drifts from the previous round.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(SCRIPTS))


def _project(tmp: Path, *, n: int, num_trials: int = 1, extra: str = "") -> Path:
    project = tmp / "project"
    (project / "adapters").mkdir(parents=True, exist_ok=True)
    (project / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter\n\n\n"
        "class Adapter(SyntheticAdapter):\n"
        f"    def __init__(self):\n        super().__init__(n={n})\n",
        encoding="utf-8")
    (project / "capevolve.yaml").write_text(
        f"num_trials: {num_trials}\ngate_mode: paired\ngate_k_se: 1.0\n"
        'stop_condition: "reach val mean >= 0.9, or stop after $5 or 30 minutes"\n' + extra,
        encoding="utf-8")
    return project


def _run(argv, env=None):
    e = dict(os.environ, CAPEVOLVE_CORE=str(CORE))
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=e)


def _staged_run_dir(tmp_path, *, n=24, num_trials=1, extra=""):
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=n)
    project = _project(tmp_path, n=n, num_trials=num_trials, extra=extra)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="chk")
    harness.ensure_splits(adapter, run_dir, seed=0)

    for i, tid in enumerate(run_dir.read_splits().ids("val")):
        from cap_evolve.skillcheck import write_val_rollout
        write_val_rollout(run_dir, tid, tag="cur", reward=float(i % 2), feedback="fb")
    run_dir.set_best("cur")
    run_dir.snapshot("cur", seed_capability_dir(tmp_path / "roundcap", level=12))

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copytree(seed_capability_dir(tmp_path / "_src", level=24), work / "cand_1")
    return run_dir, project, work


# N<3 sibling candidates now needs a recorded reason (round.py's own MIN_SIBLINGS guard) — a
# fixed constant here so every single-candidate call in this file states the SAME reason, kept
# out of the way of the screen-ladder guard these tests actually exercise.
_JUSTIFY = ["--single-candidate-justification", "screen-ladder test: single candidate by design"]


def test_round_screens_an_unscreened_candidate_itself_before_full_val(tmp_path):
    """#437: screening is round.py's DEFAULT step, not something the driver must remember —
    an unscreened candidate is screened by round.py before any full-val rollout is offered."""
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1", *_JUSTIFY])
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert (run_dir.root / "screens" / "cand_1__screen1.json").exists()
    assert out["screen_stage"]["cand_1"]["auto"] is True
    assert out["screen_stage"]["cand_1"]["rationale"], "subset.rationale must be recorded"

    events = [json.loads(ln) for ln in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    kinds = [(e["kind"], e.get("tag")) for e in events]
    # The screen event lands BEFORE the compliance record that admits it to full val.
    assert kinds.index(("screen", "cand_1")) < kinds.index(("agent_optimize_compliance", "cand_1"))
    compliance = [e for e in events if e.get("kind") == "agent_optimize_compliance"]
    assert compliance[0]["screened_before_fullval"] is True
    assert compliance[0]["auto_screened"] is True

    from cap_evolve import graph
    statuses = [(n["id"], n["status"]) for n in graph.read_nodes(run_dir)]
    assert statuses == [("cand_1", "screened"), ("cand_1", "gated")] or \
        statuses == [("cand_1", "screened")], statuses  # killed ⇒ never gated
    if out["candidates"]:
        gated = graph.read_nodes(run_dir)[-1]
        assert gated["subset"]["rationale"] and gated["parents"] == ["cur"]


def test_skip_screen_ladder_records_the_deliberate_override(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
              "--skip-screen-ladder", *_JUSTIFY])
    assert p.returncode == 0, f"--skip-screen-ladder did not override the guard: {p.stdout}"
    out = json.loads(p.stdout)
    assert [x["tag"] for x in out.get("candidates") or []] == ["cand_1"]


def test_skip_screen_justification_records_the_reason_on_the_compliance_event(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
              "--skip-screen-justification", "break-even unreachable on this split size",
              *_JUSTIFY])
    assert p.returncode == 0, f"--skip-screen-justification did not override the guard: {p.stdout}"
    out = json.loads(p.stdout)
    assert [x["tag"] for x in out.get("candidates") or []] == ["cand_1"]

    events = [json.loads(ln) for ln in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    compliance = [e for e in events if e.get("kind") == "agent_optimize_compliance"]
    assert compliance and compliance[0]["screened_before_fullval"] is False
    assert compliance[0]["skip_justification"] == "break-even unreachable on this split size"


def test_round_proceeds_once_the_candidate_has_a_screen_record(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_1__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_1", "--n-trials", "1", *_JUSTIFY])
    assert p.returncode == 0, f"round.py refused a screened candidate: {p.stdout}"


# --- #631: the screen-skip budget is a COUNT against frozen arithmetic, not a text check ------

def _round(run_dir, project, tag, *extra):
    return _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                 "--project", str(project), "--candidates", tag, "--n-trials", "1",
                 *_JUSTIFY, *extra])


def _new_cand(tmp_path, work, tag):
    import shutil
    from cap_evolve.skillcheck import seed_capability_dir
    shutil.copytree(seed_capability_dir(tmp_path / f"_src_{tag}", level=24), work / tag)


def _compliance(run_dir):
    return [e for e in (json.loads(ln) for ln in
                        run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip())
            if e.get("kind") == "agent_optimize_compliance"]


def test_screening_economics_is_screen_py_breakeven_arithmetic():
    from cap_evolve.subsample import screening_economics

    # The issue's own run: val 30 x 10 trials — tier 1 fires max(6, 8) = 8 of 300.
    e = screening_economics(30, 10)
    assert (e["tier1_fired"], e["full_val_rollouts"], e["breakeven_kill_rate"]) == (8, 300, 0.0267)
    assert e["screening_structurally_uneconomical"] is False
    # docs/RESULTS.md's val 12 x 1: the 6-task floor is half the split, break-even 0.5.
    assert screening_economics(12, 1)["screening_structurally_uneconomical"] is True
    # A 6-task val: tier 1 IS the whole split at 1 trial; at 10 trials it is a tenth of it.
    assert screening_economics(6, 1)["breakeven_kill_rate"] == 1.0
    assert screening_economics(6, 10)["screening_structurally_uneconomical"] is False


def test_baseline_freezes_screening_economics_once(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=24)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="eco")
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed_capability_dir(tmp_path / "seed", level=3), run_dir=run_dir,
                     n_trials=10)
    state = json.loads(run_dir.state_path.read_text(encoding="utf-8"))
    assert state["screening_structurally_uneconomical"] is False
    assert state["screening_economics"]["n_trials"] == 10
    # A later caller with a lower trial count (e.g. a round's own --n-trials 1, which the
    # optimizer controls) gets the FROZEN answer back, never a recomputed one.
    again = harness.freeze_screening_economics(run_dir, 1)
    assert again["screening_structurally_uneconomical"] is False and again["n_trials"] == 10


def test_screen_skip_budget_hard_blocks_with_no_override(tmp_path):
    # 6-task val at num_trials 10: tier 1 fires 6 of 60, break-even 0.1 — screening pays, so it
    # is mandatory and max_screen_skips (default 1) is enforced. The round itself runs at
    # --n-trials 1, which must NOT flip the frozen verdict.
    run_dir, project, work = _staged_run_dir(tmp_path, num_trials=10)
    p1 = _round(run_dir, project, "cand_1", "--skip-screen-justification", "pure additive tool")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    state = json.loads(run_dir.state_path.read_text(encoding="utf-8"))
    assert state["screening_structurally_uneconomical"] is False
    assert state["screening_economics"]["breakeven_kill_rate"] == 0.1
    # Re-gating the SAME already-charged candidate does not spend the budget a second time.
    assert _round(run_dir, project, "cand_1", "--skip-screen-ladder").returncode == 0

    _new_cand(tmp_path, work, "cand_2")
    n_before = len(_compliance(run_dir))
    # A fresh, specific, never-seen-before reason is refused all the same: it is a count.
    fresh = ("cand_2 bundles a 4-way diff touching retrieval, prompt template, and two tool "
             "schemas; a tier-1 subset cannot resolve interactions across that many surfaces.")
    refused = _round(run_dir, project, "cand_2", "--skip-screen-justification", fresh)
    assert refused.returncode == 2, refused.stdout
    err = json.loads(refused.stdout)
    assert "max_screen_skips=1" in err["error"] and "cand_1" in err["error"]
    assert "no override flag" in err["why"]
    assert err["screening_economics"]["screening_structurally_uneconomical"] is False
    assert _round(run_dir, project, "cand_2", "--skip-screen-ladder").returncode == 2
    assert len(_compliance(run_dir)) == n_before, "a refused skip must not log (or count) itself"
    # The #613 override is gone: there is nothing to argue with.
    gone = _round(run_dir, project, "cand_2", "--skip-screen-ladder",
                  "--duplicate-skip-justification", "please")
    assert gone.returncode == 2 and "unrecognized arguments" in gone.stderr
    # The only way through is the screen itself — which round.py runs on its own.
    ok = _round(run_dir, project, "cand_2")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    last = _compliance(run_dir)[-1]
    assert last["tag"] == "cand_2" and last["screened_before_fullval"] is True
    assert last["screen_skips_used"] == 1 and last["max_screen_skips"] == 1


def test_max_screen_skips_is_configurable_per_benchmark(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path, num_trials=10, extra="max_screen_skips: 2\n")
    assert _round(run_dir, project, "cand_1", "--skip-screen-ladder").returncode == 0
    _new_cand(tmp_path, work, "cand_2")
    assert _round(run_dir, project, "cand_2", "--skip-screen-ladder").returncode == 0
    _new_cand(tmp_path, work, "cand_3")
    refused = _round(run_dir, project, "cand_3", "--skip-screen-ladder")
    assert refused.returncode == 2 and "max_screen_skips=2" in json.loads(refused.stdout)["error"]


def test_structurally_uneconomical_benchmark_skips_stay_unrestricted(tmp_path):
    # 6-task val at 1 trial: tier 1 would screen the whole split (break-even 1.0). The arithmetic
    # settled it once, so skipping is unrestricted — bare, reworded or copy-pasted alike.
    run_dir, project, work = _staged_run_dir(tmp_path)
    reasons = [["--skip-screen-justification",
                "30-task val makes the tier-1 screen floor unreachable; consistent with cand_1."],
               ["--skip-screen-justification",
                "30-task val makes the tier-1 screen floor unreachable, per prior rounds cand_1."],
               ["--skip-screen-ladder"]]
    for i, flags in enumerate(reasons, start=1):
        tag = f"cand_{i}"
        if i > 1:
            _new_cand(tmp_path, work, tag)
        p = _round(run_dir, project, tag, *flags)
        assert p.returncode == 0, f"{tag}: {p.stdout} {p.stderr}"
    events = _compliance(run_dir)
    assert [e["screening_structurally_uneconomical"] for e in events] == [True, True, True]
    assert [e["screen_skips_used"] for e in events] == [1, 2, 3]
    # Similarity is still RECORDED (audit evidence), just never enforced.
    assert events[1]["justification_near_duplicate_of"] == "cand_1"
    state = json.loads(run_dir.state_path.read_text(encoding="utf-8"))
    assert state["screening_structurally_uneconomical"] is True


def test_round_records_max_parallel_and_warns_on_drift(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_1__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    p1 = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
               "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
               "--max-parallel", "2", *_JUSTIFY])
    assert p1.returncode == 0, p1.stdout
    out1 = json.loads(p1.stdout)
    assert out1["measurement_max_parallel"] == 2
    assert out1["parallel_warning"] is None, "the first round has nothing to drift from"

    # Advance to a fresh iteration and re-run with a different --max-parallel.
    from cap_evolve import RunDir, harness
    harness.record_iteration(run_dir, work / "cand_1", "cand_1", parent_id="cur",
                             accepted=False, reason="test", val=0.5, parent_val=0.5)

    import shutil
    from cap_evolve.skillcheck import seed_capability_dir
    shutil.copytree(seed_capability_dir(tmp_path / "_src2", level=24), work / "cand_2")
    (screens / "cand_2__screen1.json").write_text(json.dumps({"decision": "promote"}),
                                                  encoding="utf-8")
    p2 = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
               "--project", str(project), "--candidates", "cand_2", "--n-trials", "1",
               "--max-parallel", "4", *_JUSTIFY])
    assert p2.returncode == 0, p2.stdout
    out2 = json.loads(p2.stdout)
    assert out2["measurement_max_parallel"] == 4
    assert out2["parallel_warning"] is not None, (
        "round 2 silently doubled --max-parallel from round 1's 2 and nothing warned about it")
    assert "2" in out2["parallel_warning"] and "4" in out2["parallel_warning"]
