"""Coverage for the dashboard's surfacing of 4 agent-optimize mechanisms that landed as
separate PRs (#557-#560): screen+gate bypass, sibling-count enforcement, background-task
mass-kill, and merge-of-rejects. Each case checks ``reduce_run``'s output JSON only — the
frontend reads these same fields, but rendering itself has no test harness here.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _make_run(events=None):
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = events if events is not None else [{"t": 1.0, "kind": "splits",
                                                  "train": 1, "val": 1, "test": 1, "seed": 0}]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return rd, dashboard


# ---- PR #557: screen+gate bypass -------------------------------------------------

def test_bypassed_screen_and_gate_surfaces_on_the_candidate_node():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "reject", "candidate": "cand_1", "note": "override",
         "reject_basis": "driver_judgement", "bypassed_screen_and_gate": True,
         "bypassed_gate_justification": "infra failure before any rollout could be scored"},
    ])
    reduced = dashboard.reduce_run(rd)
    node = next(n for n in reduced["graph"]["nodes"] if n["id"] == "cand_1")
    assert node["bypassed_screen_and_gate"] is True
    assert node["bypassed_gate_justification"] == (
        "infra failure before any rollout could be scored")
    assert reduced["summary"]["capabilities"]["screen_gate_bypass"] is True


def test_no_bypass_field_means_no_screen_gate_bypass_capability():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "reject", "candidate": "cand_1", "note": "normal reject",
         "reject_basis": "gate"},
    ])
    reduced = dashboard.reduce_run(rd)
    node = next(n for n in reduced["graph"]["nodes"] if n["id"] == "cand_1")
    assert node.get("bypassed_screen_and_gate") is None
    assert reduced["summary"]["capabilities"]["screen_gate_bypass"] is False


def test_skip_justification_surfaces_on_the_compliance_row():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "agent_optimize_compliance", "tag": "cand_1", "iteration": 1,
         "screened_before_fullval": False,
         "skip_justification": "break-even unreachable on this split size"},
    ])
    reduced = dashboard.reduce_run(rd)
    rows = reduced["summary"]["algo_extra"]["compliance"]
    assert rows[0]["skip_justification"] == "break-even unreachable on this split size"


# ---- PR #559: sibling-count enforcement ------------------------------------------

def test_round_batch_below_min_siblings_surfaces_justification_and_source():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "agent_optimize_round_batch", "batch_id": "b1",
         "candidates": ["cand_1"], "n_candidates": 1,
         "single_candidate_justification": "diagnose surfaced only one cluster this round",
         "single_candidate_justification_source": "explicit"},
    ])
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["capabilities"]["round_batches"] is True
    batch = reduced["summary"]["algo_extra"]["round_batches"][0]
    assert batch["n_candidates"] == 1
    assert batch["single_candidate_justification"] == (
        "diagnose surfaced only one cluster this round")
    assert batch["single_candidate_justification_source"] == "explicit"


def test_round_batch_with_three_siblings_needs_no_justification():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "agent_optimize_round_batch", "batch_id": "b1",
         "candidates": ["cand_1", "cand_2", "cand_3"], "n_candidates": 3,
         "single_candidate_justification": None,
         "single_candidate_justification_source": None},
    ])
    reduced = dashboard.reduce_run(rd)
    batch = reduced["summary"]["algo_extra"]["round_batches"][0]
    assert batch["n_candidates"] == 3
    assert batch["single_candidate_justification"] is None


# ---- PR #558: background task mass-kill ------------------------------------------

def test_background_mass_kill_detected_from_host_transcript():
    rd, dashboard = _make_run()
    hdir = rd.root / "host"
    hdir.mkdir()
    transcript = [
        {"type": "task_updated", "task_id": f"t{i}", "status": "killed",
         "timestamp": 1700000000123}
        for i in range(4)
    ] + [{"type": "task_notification", "task_id": "t4", "status": "stopped",
          "timestamp": 1700000000123}]
    (hdir / "transcript.jsonl").write_text(
        "\n".join(json.dumps(e) for e in transcript) + "\n", encoding="utf-8")

    reduced = dashboard.reduce_run(rd)
    kills = reduced["summary"]["background_mass_kills"]
    assert kills and kills[0]["count"] == 5
    assert kills[0]["timestamp"] == 1700000000123
    assert reduced["summary"]["capabilities"]["background_mass_kills"] is True


def test_tasks_within_the_cap_or_at_different_times_are_not_flagged():
    rd, dashboard = _make_run()
    hdir = rd.root / "host"
    hdir.mkdir()
    transcript = [
        {"type": "task_updated", "task_id": "t1", "status": "killed", "timestamp": 1000},
        {"type": "task_updated", "task_id": "t2", "status": "killed", "timestamp": 1000},
        {"type": "task_updated", "task_id": "t3", "status": "killed", "timestamp": 1001},
        {"type": "task_updated", "task_id": "t4", "status": "completed", "timestamp": 1000},
    ]
    (hdir / "transcript.jsonl").write_text(
        "\n".join(json.dumps(e) for e in transcript) + "\n", encoding="utf-8")

    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["background_mass_kills"] == []
    assert reduced["summary"]["capabilities"]["background_mass_kills"] is False


def test_no_host_dir_means_no_mass_kills():
    rd, dashboard = _make_run()
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["background_mass_kills"] == []


# ---- PR #560: merge-of-rejects ---------------------------------------------------

def test_merge_rejects_warning_surfaces_with_no_proposal_yet():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "merge_rejects_compliance_warning",
         "reason": "safe_rejects_not_merged",
         "safe_reject_candidates": ["cand_4", "cand_5", "cand_7"],
         "evidence": {"cand_4": {"gate_delta": 0.02, "broke": []}},
         "targets": {"cand_4": ["t0", "t1"]}},
    ])
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["capabilities"]["merge_rejects"] is True
    w = reduced["summary"]["algo_extra"]["merge_rejects_warning"]
    assert w["safe_reject_candidates"] == ["cand_4", "cand_5", "cand_7"]
    assert w["acted_on"] is False


def test_merge_rejects_warning_is_marked_acted_on_after_a_propose_event():
    rd, dashboard = _make_run([
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "merge_rejects_compliance_warning",
         "reason": "safe_rejects_not_merged",
         "safe_reject_candidates": ["cand_4", "cand_5", "cand_7"],
         "evidence": {}, "targets": {}},
        {"t": 3.0, "kind": "merge_rejects_propose", "rejects": ["cand_4", "cand_5"],
         "tag": "mergereject_cand_4_cand_5", "built": True, "targets": ["t0", "t1", "t2", "t3"]},
    ])
    reduced = dashboard.reduce_run(rd)
    w = reduced["summary"]["algo_extra"]["merge_rejects_warning"]
    assert w["acted_on"] is True
    proposals = reduced["summary"]["algo_extra"]["merge_rejects_proposals"]
    assert proposals[0]["tag"] == "mergereject_cand_4_cand_5"
    assert proposals[0]["built"] is True


def test_no_merge_rejects_warning_means_no_capability():
    rd, dashboard = _make_run()
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["capabilities"]["merge_rejects"] is False
    assert "merge_rejects_warning" not in reduced["summary"]["algo_extra"]
