"""issue #634: late rounds tunnel-visioned on 1-2 stubborn tasks. Two commit.py preconditions,
same escape-hatch shape as #588 (JOURNAL.md) and #611 (DIAGNOSIS.json):

1. PROCESS.md's "Ranked issue list" must have data rows (it was header-only on most nodes);
   ``--missing-ranked-issues-justification`` is the override.
2. A candidate whose DIAGNOSIS.json targets (nearly) the same tasks as an earlier REJECTED
   candidate needs ``--retry-justification`` saying what is different this time.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

HEADER_ONLY = (
    "## Ranked issue list (clusters by # failing tasks × trials, biggest first)\n"
    "| rank | cluster | tasks | shared root cause | tag | planned change class |\n"
    "| --- | --- | --- | --- | --- | --- |\n\n"
    # A filled table BELOW must not make the blank ranked list count as filled.
    "## Changes made this iteration\n"
    "| cluster | edit class | file / tool | what & why it generalizes | protects passing? |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| A | guard | policy.md | refund math | yes |\n")
FILLED = (
    "## Ranked issue list (clusters by # failing tasks × trials, biggest first)\n"
    "| rank | cluster | tasks | shared root cause | tag | planned change class |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
    "| 1 | A | t1, t3 | cancel reason not checked | BEHAVIORAL | guard |\n"
    "| 2 | B | t9 | wrong fare class | KNOWLEDGE | doc |\n\n"
    "## Changes made this iteration\n")


def _diag(cid, tasks):
    return {"candidate": cid, "clusters": [{"id": "A", "name": "cancel", "tasks": tasks}],
            "edits": [{"id": "E1", "clusters": ["A"]}]}


def _run_dir(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=10, stall=10))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    return run_dir


def _work(run_dir, cid, *, process=FILLED, tasks=("t1", "t3")):
    work = run_dir.root / "work" / cid
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.candidate_dir("seed"), work)
    (work / "PROCESS.md").write_text(process, encoding="utf-8")
    (work / "DIAGNOSIS.json").write_text(json.dumps(_diag(cid, list(tasks))))
    return work


def _commit(run_dir, cid, work, *extra, decision="reject"):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", cid, "--from-dir", str(work), "--decision", decision,
         "--val", "0.4", "--val-unverified", "fixture: val not under test", "--note", f"test {cid}",
         "--missing-handover-justification", "fixture: journal handover not under test",
         *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})
    return p.returncode, json.loads(p.stdout)


# --- 1. ranked issue list ---------------------------------------------------------------

def test_header_only_ranked_list_is_refused(tmp_path):
    run_dir = _run_dir(tmp_path)
    rc, out = _commit(run_dir, "cand_1", _work(run_dir, "cand_1", process=HEADER_ONLY))
    assert rc == 2, out
    assert "Ranked issue list" in out["error"]
    assert "--missing-ranked-issues-justification" in out["fix"]
    assert not (run_dir.root / "graph.jsonl").exists(), "a refused commit must book nothing"


def test_seeded_template_is_refused(tmp_path):
    """No PROCESS.md at all: commit.py seeds the blank template, which is still blank."""
    run_dir = _run_dir(tmp_path)
    work = _work(run_dir, "cand_1")
    (work / "PROCESS.md").unlink()
    rc, _ = _commit(run_dir, "cand_1", work)
    assert rc == 2


def test_header_only_passes_with_override_and_warns(tmp_path):
    run_dir = _run_dir(tmp_path)
    rc, out = _commit(run_dir, "cand_1", _work(run_dir, "cand_1", process=HEADER_ONLY),
                      "--missing-ranked-issues-justification", "infra died mid-survey")
    assert rc == 0, out
    assert out["ranked_issue_rows"] == 0
    assert any("missing ranked issues" in w and "infra died" in w for w in out["warnings"])


def test_filled_ranked_list_passes(tmp_path):
    run_dir = _run_dir(tmp_path)
    rc, out = _commit(run_dir, "cand_1", _work(run_dir, "cand_1"))
    assert rc == 0, out
    assert out["ranked_issue_rows"] == 2
    assert not [w for w in out["warnings"] if "ranked" in w]


# --- 2. retry of a refuted component ----------------------------------------------------

def test_retry_of_a_rejected_component_is_refused_then_passes_with_justification(tmp_path):
    run_dir = _run_dir(tmp_path)
    assert _commit(run_dir, "cand_1", _work(run_dir, "cand_1"))[0] == 0  # v1: rejected

    work = _work(run_dir, "cand_2", tasks=("t1", "t3", "t4"))  # v2: near-identical targets
    rc, out = _commit(run_dir, "cand_2", work)
    assert rc == 2, out
    assert [h["candidate"] for h in out["refuted_priors"]] == ["cand_1"]
    assert "--retry-justification" in out["fix"]

    rc, out = _commit(run_dir, "cand_2", work, "--retry-justification",
                      "v1 guarded the prompt; v2 adds a tool that computes the reason")
    assert rc == 0, out
    assert any("refuted retry" in w and "cand_1" in w for w in out["warnings"])
    ev = [json.loads(ln) for ln in run_dir.events_path.read_text().splitlines()
          if ln.strip() and json.loads(ln).get("kind") == "reject"][-1]
    assert ev["retry_of"] == ["cand_1"] and "computes the reason" in ev["retry_justification"]


def test_disjoint_targets_and_non_refutations_need_no_justification(tmp_path):
    run_dir = _run_dir(tmp_path)
    assert _commit(run_dir, "cand_1", _work(run_dir, "cand_1"))[0] == 0
    # Different tasks: a fresh cluster, not a retry.
    assert _commit(run_dir, "cand_2", _work(run_dir, "cand_2", tasks=("t9",)))[0] == 0
    # An ACCEPTED prior on the same tasks is no refutation either.
    assert _commit(run_dir, "cand_3", _work(run_dir, "cand_3", tasks=("t7",)),
                   decision="accept")[0] == 0
    assert _commit(run_dir, "cand_4", _work(run_dir, "cand_4", tasks=("t7",)))[0] == 0
    # An infra reject is missing data, not a judgement.
    assert _commit(run_dir, "cand_5", _work(run_dir, "cand_5", tasks=("t5",)),
                   "--reject-basis", "infra")[0] == 0
    assert _commit(run_dir, "cand_6", _work(run_dir, "cand_6", tasks=("t5",)))[0] == 0
