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


def _project(tmp: Path, *, n: int) -> Path:
    project = tmp / "project"
    (project / "adapters").mkdir(parents=True, exist_ok=True)
    (project / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter\n\n\n"
        "class Adapter(SyntheticAdapter):\n"
        f"    def __init__(self):\n        super().__init__(n={n})\n",
        encoding="utf-8")
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        'stop_condition: "reach val mean >= 0.9, or stop after $5 or 30 minutes"\n',
        encoding="utf-8")
    return project


def _run(argv, env=None):
    e = dict(os.environ, CAPEVOLVE_CORE=str(CORE))
    if env:
        e.update(env)
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=e)


def _staged_run_dir(tmp_path, *, n=24):
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=n)
    project = _project(tmp_path, n=n)
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


def test_near_duplicate_skip_justification_is_refused_without_override(tmp_path):
    """issue #585 (reopened): boilerplate skip_justification text copy-pasted round after round
    ("consistent with cand_1/2/...", "...consistent with prior rounds", "...per prior rounds
    cand_2-...") is refused on an unscreened candidate unless --duplicate-skip-justification
    records why; a first-time or genuinely fresh justification still passes on its own.
    """
    run_dir, project, work = _staged_run_dir(tmp_path)

    p1 = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
               "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
               "--skip-screen-justification",
               "30-task val makes the tier-1 screen floor unreachable; consistent with cand_1.",
               *_JUSTIFY])
    assert p1.returncode == 0, p1.stdout

    from cap_evolve import harness
    harness.record_iteration(run_dir, work / "cand_1", "cand_1", parent_id="cur",
                             accepted=False, reason="test", val=0.5, parent_val=0.5)
    import shutil
    from cap_evolve.skillcheck import seed_capability_dir
    shutil.copytree(seed_capability_dir(tmp_path / "_src2", level=24), work / "cand_2")

    # Round 2: near-identical boilerplate, same template with the candidate list tacked on.
    round2 = [str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
              "--project", str(project), "--candidates", "cand_2", "--n-trials", "1",
              "--skip-screen-justification",
              "30-task val makes the tier-1 screen floor unreachable, per prior rounds cand_1.",
              *_JUSTIFY]
    refused = _run(round2)
    assert refused.returncode == 2, f"near-duplicate skip was not refused: {refused.stdout}"
    err = json.loads(refused.stdout)
    assert "near-duplicate of cand_1" in err["error"]
    assert "--duplicate-skip-justification" in err["fix"]
    events = [json.loads(ln) for ln in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [e["tag"] for e in events if e.get("kind") == "agent_optimize_compliance"] == [
        "cand_1"], "a refused round must not log a compliance event"

    override = "cand_2 is a one-line wording tweak of cand_1's prompt; same split-size fact holds"
    p2 = _run([*round2, "--duplicate-skip-justification", override])
    assert p2.returncode == 0, p2.stdout
    assert "repeats cand_1" in p2.stderr, f"no near-duplicate note on stderr: {p2.stderr}"

    events = [json.loads(ln) for ln in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    compliance = [e for e in events if e.get("kind") == "agent_optimize_compliance"]
    assert compliance[0]["justification_near_duplicate_of"] is None, (
        "the first round's justification has nothing prior to duplicate")
    assert compliance[-1]["justification_near_duplicate_of"] == "cand_1", (
        f"round 2's boilerplate justification was not flagged as a near-duplicate: {compliance}")
    assert compliance[-1]["duplicate_skip_justification"] == override

    harness.record_iteration(run_dir, work / "cand_2", "cand_2", parent_id="cur",
                             accepted=False, reason="test", val=0.5, parent_val=0.5)
    shutil.copytree(seed_capability_dir(tmp_path / "_src3", level=24), work / "cand_3")

    # Round 3: a genuinely fresh justification describing THIS candidate's own edit surface —
    # must NOT be flagged as a near-duplicate of the boilerplate above.
    p3 = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
               "--project", str(project), "--candidates", "cand_3", "--n-trials", "1",
               "--skip-screen-justification",
               "cand_3 bundles a 4-way diff touching retrieval, prompt template, and two tool "
               "schemas; screen.py's tier-1 subset is too small to resolve interaction effects "
               "across that many changed surfaces, so going straight to full-val is deliberate "
               "here, not rote.",
               *_JUSTIFY])
    assert p3.returncode == 0, p3.stdout
    assert "near-duplicate" not in p3.stderr, f"fresh justification wrongly flagged: {p3.stderr}"

    events = [json.loads(ln) for ln in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    compliance = [e for e in events if e.get("kind") == "agent_optimize_compliance"]
    assert compliance[-1]["justification_near_duplicate_of"] is None, (
        f"fresh justification wrongly flagged as a near-duplicate: {compliance[-1]}")


def test_repeated_bare_skip_screen_ladder_is_refused_without_override(tmp_path):
    """issue #585 loophole: a bare --skip-screen-ladder has no text to near-duplicate, so a
    driver refused for a boilerplate reason could just drop the reason. The first bare skip in a
    run passes; the 2nd+ is refused unless --duplicate-skip-justification records why.
    """
    run_dir, project, work = _staged_run_dir(tmp_path)

    def rnd(tag, *extra):
        return _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                     "--project", str(project), "--candidates", tag, "--n-trials", "1",
                     *_JUSTIFY, *extra])

    # A round with NO skip flag at all (auto-screened since #437) still logs a compliance event;
    # it must not count as the run's first bare skip.
    import shutil
    from cap_evolve.skillcheck import seed_capability_dir
    shutil.copytree(seed_capability_dir(tmp_path / "_src0", level=24), work / "cand_0")
    assert rnd("cand_0").returncode == 0
    p1 = rnd("cand_1", "--skip-screen-ladder")
    assert p1.returncode == 0, f"the first bare skip in a run must pass: {p1.stdout}"

    from cap_evolve import harness
    harness.record_iteration(run_dir, work / "cand_1", "cand_1", parent_id="cur",
                             accepted=False, reason="test", val=0.5, parent_val=0.5)
    shutil.copytree(seed_capability_dir(tmp_path / "_src2", level=24), work / "cand_2")

    refused = rnd("cand_2", "--skip-screen-ladder")
    assert refused.returncode == 2, f"a repeated bare skip was not refused: {refused.stdout}"
    err = json.loads(refused.stdout)
    assert "bare --skip-screen-ladder" in err["error"] and "cand_1" in err["error"]
    assert "--duplicate-skip-justification" in err["fix"]

    override = "cand_2 only renames a tool argument; nothing a subset could discriminate"
    p2 = rnd("cand_2", "--skip-screen-ladder", "--duplicate-skip-justification", override)
    assert p2.returncode == 0, p2.stdout
    events = [json.loads(ln) for ln in
              run_dir.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    last = [e for e in events if e.get("kind") == "agent_optimize_compliance"][-1]
    assert last["tag"] == "cand_2" and last["skip_screen_ladder"] is True
    assert last["justification_near_duplicate_of"] == "cand_1"
    assert last["duplicate_skip_justification"] == override


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
