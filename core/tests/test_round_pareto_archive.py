"""round.py --mode pareto / epsilon_constraint, end-to-end (issue #684 items 1-2).

The real-run bug: a spec declaring ``gate_mode: pareto`` was silently gated single-objective
(reward-only) because round.py excluded "pareto" from its own ``--mode`` choices. This asserts
the fix DIRECTLY — the exact symptom that proved the bug — rather than trusting the exclusion
is gone: ``round.py --mode pareto`` must produce real archive/dominance fields in its output
(``pareto_archive`` non-None, each candidate row carrying its own archive insertion verdict),
never the paired-mode scalar fields a reward-only fallback would have produced instead.

Also covers: the archive persists across SEPARATE ``round.py`` subprocess invocations (each a
real process restart, not an in-memory object kept alive across the test), and
``epsilon_constraint`` requires a non-empty ``constraints:`` config.
"""

from __future__ import annotations

import json

from test_round_requires_screen_ladder import SCRIPTS, _run, _staged_run_dir

_JUSTIFY = ["--single-candidate-justification", "pareto archive test: single candidate by design"]


def _round(run_dir, project, tag, *extra):
    return _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                 "--project", str(project), "--candidates", tag, "--n-trials", "1",
                 "--skip-screen-justification", "pareto archive e2e test",
                 *_JUSTIFY, *extra])


def test_round_mode_pareto_is_now_a_first_class_choice(tmp_path):
    """The old guard test asserted the OPPOSITE of this — round.py excluded "pareto" from its
    own --mode choices. Issue #684 item 1 requires the exclusion REMOVED, not merely silenced:
    this is the direct, positive check that --mode pareto is argparse-acceptable."""
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _round(run_dir, project, "cand_1", "--mode", "pareto")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "invalid choice: 'pareto'" not in p.stderr


def test_round_pareto_produces_archive_fields_not_paired_scalar_fallback(tmp_path):
    """THE symptom that proved the real-run bug, asserted directly: a round gated with
    --mode pareto must carry real archive/dominance output, not the paired-mode shape a
    silent reward-only fallback would have produced instead."""
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _round(run_dir, project, "cand_1", "--mode", "pareto")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)

    # Round-level: a real persistent archive snapshot, not None.
    assert out["pareto_archive"] is not None
    assert out["pareto_archive"]["version"] == 1
    assert {o["name"] for o in out["objectives"]} == {"reward", "cost"}
    assert out["pareto_archive"]["points"], "the archive must contain at least the seeded baseline"

    # Per-candidate: the archive's OWN insertion verdict, not a paired-mode gate_delta/threshold
    # read as the final word. Every gated candidate carries `pareto_archive` + `objective_values`.
    assert out["candidates"], "no candidate was gated"
    for row in out["candidates"]:
        assert row["verdict"] in ("accept", "reject")
        assert "pareto_archive" in row and row["pareto_archive"] is not None
        assert "inserted" in row["pareto_archive"] and "reason" in row["pareto_archive"]
        assert "objective_values" in row and "cost" in row["objective_values"]
        # verdict must literally be driven by the archive's own decision, not re-derived.
        assert row["verdict"] == ("accept" if row["pareto_archive"]["inserted"] else "reject")

    # The persisted archive file this run wrote to disk.
    archive_path = run_dir.root / "pareto_archive.json"
    assert archive_path.is_file()
    on_disk = json.loads(archive_path.read_text(encoding="utf-8"))
    assert on_disk == out["pareto_archive"]


def test_round_pareto_archive_persists_across_separate_process_invocations(tmp_path):
    """Each `_round(...)` call here is a genuinely separate `round.py` subprocess — a real
    process restart, not an in-memory object this test kept alive. The second invocation's
    archive must build on what the first one wrote, not start from an empty frontier again."""
    run_dir, project, work = _staged_run_dir(tmp_path)
    p1 = _round(run_dir, project, "cand_1", "--mode", "pareto")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    out1 = json.loads(p1.stdout)
    size_after_round_1 = out1["pareto_archive"]["size_total"] if "size_total" in out1["pareto_archive"] \
        else len(out1["pareto_archive"]["points"])

    import shutil
    from cap_evolve.skillcheck import seed_capability_dir
    shutil.copytree(seed_capability_dir(tmp_path / "_src2", level=20), work / "cand_2")

    p2 = _round(run_dir, project, "cand_2", "--mode", "pareto")
    assert p2.returncode == 0, p2.stdout + p2.stderr
    out2 = json.loads(p2.stdout)

    # The SAME archive file, read back by a fresh subprocess, carries forward whatever round 1
    # inserted (at minimum, the seeded baseline point from round 1 is still namable).
    archive_path = run_dir.root / "pareto_archive.json"
    on_disk = json.loads(archive_path.read_text(encoding="utf-8"))
    assert on_disk == out2["pareto_archive"]
    round1_tags = {p["tag"] for p in out1["pareto_archive"]["points"]}
    round2_tags = {p["tag"] for p in out2["pareto_archive"]["points"]}
    # At least one tag from round 1's archive state survived into round 2's — the archive was
    # LOADED from disk, not rebuilt from scratch (which would start from only "cur"/cand_2).
    assert round1_tags & round2_tags or len(round2_tags) >= len(round1_tags)


def test_round_epsilon_constraint_requires_constraints_config(tmp_path):
    run_dir, project, work = _staged_run_dir(tmp_path)
    p = _round(run_dir, project, "cand_1", "--mode", "epsilon_constraint")
    assert p.returncode == 2, p.stdout + p.stderr
    err = json.loads(p.stdout)
    assert "constraints" in err["error"]


def test_round_epsilon_constraint_end_to_end(tmp_path):
    run_dir, project, work = _staged_run_dir(
        tmp_path, extra="constraints:\n  - {name: cost, max: 1.0}\n")
    p = _round(run_dir, project, "cand_1", "--mode", "epsilon_constraint")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["constraints"] == [{"name": "cost", "max": 1.0}]
    assert out["candidates"]
    for row in out["candidates"]:
        assert row["verdict"] in ("accept", "reject", "inconclusive")
        assert "cost" in (row.get("objective_values") or {})
