"""#676: real DIAGNOSIS.json files (see `.capevolve/archive/run_20261003_184253_single-
objective-v1/candidates/*/DIAGNOSIS.json`) write ``clusters: [{id, signature, tasks,
score_lost}]`` and ``edits: [{clusters, file, change}]`` -- missing the ``name``/``id``/
``title``/``files`` fields SKILL.md documents and the dashboard's optimizer-diagnosis
flow view renders. reduce_run() must fill those from what's actually on disk (never
fabricate), compute ``latent`` from the parent's own per_task, and read PROCESS.md's
``## Deliberately skipped`` section when DIAGNOSIS.json carries no ``skipped`` of its own.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _mk_run(tmp: Path):
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = [
        {"kind": "splits", "train": 2, "val": 4, "test": 2, "seed": 0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5, "cost_usd": 0.0},
        {"kind": "baseline", "val": 0.5, "stderr": 0.0},
        {"kind": "step", "candidate": "cand_1", "accept": True, "reason": "bugfix",
         "val": 0.75, "parent": "seed", "parent_val": 0.5},
    ]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (rd.root / "baseline.json").write_text(
        json.dumps({"val": {"reward": 0.5, "per_task": [
            {"task_id": "29", "reward": 0.0}, {"task_id": "18", "reward": 0.0},
            {"task_id": "99", "reward": 1.0}, {"task_id": "7", "reward": 1.0},
        ]}, "best_id": "seed"}), encoding="utf-8")
    cand_dir = rd.root / "candidates" / "cand_1"
    cand_dir.mkdir(parents=True, exist_ok=True)
    # Real on-disk shape: `signature`/`score_lost` on clusters, `file`/`change` on edits,
    # no top-level `skipped`.
    (cand_dir / "DIAGNOSIS.json").write_text(json.dumps({
        "split": "val", "parent": "seed",
        "clusters": [{
            "id": "origin_destination_change_unenforced",
            "signature": "update_reservation_flights allows an illegal origin/destination "
                          "change (trace: task 29, LGA->JFK)",
            "tasks": ["29", "18"], "score_lost": 4.0,
        }],
        "edits": [{
            "clusters": ["origin_destination_change_unenforced"], "file": "tools/tools.py",
            "change": "corrected origin/destination-preserved guard",
        }],
    }), encoding="utf-8")
    (cand_dir / "PROCESS.md").write_text(
        "# PROCESS\n\n"
        "## Deliberately skipped\n"
        "- wrong_write_action (rank 2): deferred -- needs a separate lever\n"
        "- N/A -- nothing else considered\n\n"
        "## RESULT\n- val 0.75\n",
        encoding="utf-8")
    return rd


def _node(reduced, nid):
    return next(n for n in reduced["graph"]["nodes"] if n["id"] == nid)


def test_cluster_name_and_detail_derived_from_signature():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    reduced = dashboard.reduce_run(_mk_run(tmp))
    cluster = _node(reduced, "cand_1")["diagnosis"]["clusters"][0]
    assert cluster["name"] == cluster["signature"]
    assert cluster["detail"] == cluster["signature"]


def test_latent_computed_from_parent_per_task_not_fabricated():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    reduced = dashboard.reduce_run(_mk_run(tmp))
    cluster = _node(reduced, "cand_1")["diagnosis"]["clusters"][0]
    # tasks 29/18 were both failing (reward 0.0) on the parent (seed) -> not latent.
    assert cluster["latent"] is False


def test_edit_id_title_files_derived_from_change_and_file():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    reduced = dashboard.reduce_run(_mk_run(tmp))
    edit = _node(reduced, "cand_1")["diagnosis"]["edits"][0]
    assert edit["id"] == "e1"
    assert edit["title"] == "corrected origin/destination-preserved guard"
    assert edit["files"] == ["tools/tools.py"]


def test_skipped_filled_from_process_md_section_na_entries_dropped():
    from cap_evolve import dashboard
    tmp = Path(tempfile.mkdtemp())
    reduced = dashboard.reduce_run(_mk_run(tmp))
    skipped = _node(reduced, "cand_1")["diagnosis"]["skipped"]
    assert len(skipped) == 1
    assert skipped[0]["title"] == "wrong_write_action (rank 2)"
    assert "needs a separate lever" in skipped[0]["reason"]


def test_parse_process_md_skipped_duplicate_header_keeps_both_bullets():
    """A real archived PROCESS.md (run_20261003_184253_single-objective-v1/cand_3) has
    the exact ``## Deliberately skipped`` header twice in sequence (template artifact),
    each followed by its own bullet. The second occurrence of the SAME header must not
    be treated as the start of "the next section" and truncate the first bullet away.
    """
    from cap_evolve.dashboard import _parse_process_md_skipped
    text = (
        "## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)\n"
        "- wrong_write_action — already banked via cand_2; not re-targeted this round.\n"
        "\n"
        "## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)\n"
        "- Teaching the agent the CORRECT write arguments (vs. just stopping blind "
        "repetition) — deferred; needs per-task trace analysis of what argument was "
        "actually wrong, a bigger and riskier lever than this round's prohibition.\n"
        "\n"
        "---\n"
    )
    skipped = _parse_process_md_skipped(text)
    assert len(skipped) == 2
    assert "wrong_write_action" in skipped[0]["reason"]
    assert "CORRECT write arguments" in skipped[1]["reason"]
