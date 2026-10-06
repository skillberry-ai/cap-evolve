"""merge_search.check_merge_compliance — an audit signal, not an enforcement.

SKILL.md requires the agent-mode optimizer to run merge_search.py on its accepted
candidates before any end-of-run measurement whenever 2+ of them target disjoint task
clusters, but nothing in the framework can force that (host.py owns no algorithm
decisions). This is the code-level compliance CHECK measure.py runs at finalize time —
same idiom as round.py's existing agent_optimize_compliance event for the screen ladder:
it never blocks, it only makes an ignored requirement visible in events.jsonl.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _load_merge_search():
    spec = importlib.util.spec_from_file_location("merge_search", SCRIPTS / "merge_search.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _run_dir(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=8)
    seed = seed_capability_dir(tmp_path, level=0)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci",
                            budget=Budget(max_iterations=10, stall=10))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    return run_dir


def _accept_node(run_dir, tag, *, parents=("seed",), edit_kind="code"):
    from cap_evolve import graph
    graph.append_node(run_dir, node_id=tag, parents=list(parents), status="accepted",
                      val_mean=0.6, edit_kind=edit_kind)


def _record_targets(run_dir, tag, task_ids):
    line = json.dumps({"owner": tag, "status": "proposed", "tasks": list(task_ids)})
    with (run_dir.root / "mechanisms.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def test_flags_two_accepted_disjoint_clusters_with_no_merge_attempt(tmp_path):
    ms = _load_merge_search()
    run_dir = _run_dir(tmp_path)

    _accept_node(run_dir, "cand_a")
    _record_targets(run_dir, "cand_a", ["t0", "t1"])
    _accept_node(run_dir, "cand_b")
    _record_targets(run_dir, "cand_b", ["t2", "t3"])

    warning = ms.check_merge_compliance(run_dir)
    assert warning is not None
    assert warning["reason"] == "merge_skipped_with_multiple_clusters"
    assert warning["accepted_candidates"] == ["cand_a", "cand_b"]
    assert warning["disjoint_pairs"] == [["cand_a", "cand_b"]]


def test_no_warning_when_a_merge_was_already_attempted(tmp_path):
    ms = _load_merge_search()
    run_dir = _run_dir(tmp_path)

    _accept_node(run_dir, "cand_a")
    _record_targets(run_dir, "cand_a", ["t0", "t1"])
    _accept_node(run_dir, "cand_b")
    _record_targets(run_dir, "cand_b", ["t2", "t3"])
    # A merge node exists (built by merge_search.py, committed via commit.py --parents) —
    # rejected or accepted, it still proves a merge was ATTEMPTED between these clusters.
    _accept_node(run_dir, "merge_a_b", parents=("cand_a", "cand_b"), edit_kind="merge")

    assert ms.check_merge_compliance(run_dir) is None


def test_no_warning_with_fewer_than_two_accepted_candidates(tmp_path):
    ms = _load_merge_search()
    run_dir = _run_dir(tmp_path)

    _accept_node(run_dir, "cand_a")
    _record_targets(run_dir, "cand_a", ["t0", "t1"])

    assert ms.check_merge_compliance(run_dir) is None


def test_no_warning_when_accepted_clusters_are_not_disjoint(tmp_path):
    ms = _load_merge_search()
    run_dir = _run_dir(tmp_path)

    _accept_node(run_dir, "cand_a")
    _record_targets(run_dir, "cand_a", ["t0", "t1"])
    _accept_node(run_dir, "cand_b")
    _record_targets(run_dir, "cand_b", ["t1", "t2"])  # shares t1 with cand_a

    assert ms.check_merge_compliance(run_dir) is None


def test_no_warning_when_accepted_candidates_have_no_recorded_targets(tmp_path):
    """A candidate with no mechanisms.jsonl row and no cluster_ids is unknowable, not
    assumed disjoint — the check must never manufacture a cluster out of missing data."""
    ms = _load_merge_search()
    run_dir = _run_dir(tmp_path)

    _accept_node(run_dir, "cand_a")
    _accept_node(run_dir, "cand_b")

    assert ms.check_merge_compliance(run_dir) is None
