"""issue #435: ``graph.jsonl`` is a candidate DAG log — a VIEW over the accept/reject
mechanics ``commit.py``/``round.py``/``screen.py`` already enforce, not a new source of
truth. This covers a multi-round, multi-sibling, one-merge scenario and checks the
written nodes against ``events.jsonl`` (the pre-existing audit log) and ``screens/*.json``
(the pre-existing screen record) independently, so a passing test proves the graph is
reconstructible from data that already existed before #435 — it adds nothing a reader
could not already piece together by hand.
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


def _stage(run_dir, cid, from_id="seed"):
    work = run_dir.root / "work" / cid
    if work.exists():
        shutil.rmtree(work)
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.candidate_dir(from_id), work)
    return work


def _commit(run_dir, work, cid, decision, val, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
         "--candidate-id", cid, "--from-dir", str(work),
         "--decision", decision, "--val", str(val), "--note", f"test commit {cid}", *extra],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})


def _ok(p):
    assert p.returncode == 0, f"commit.py failed: {p.stdout}\n{p.stderr}"
    return json.loads(p.stdout)


def _graph_nodes(run_dir):
    from cap_evolve import graph
    return graph.read_nodes(run_dir)


def _step_events(run_dir):
    """Independently rebuild {candidate: {parent, accept}} from events.jsonl, the
    audit log that existed before #435 — used to cross-check graph.jsonl, never to
    build it."""
    out = {}
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("kind") == "step" and rec.get("candidate"):
            out[str(rec["candidate"])] = {"parent": rec.get("parent"), "accept": rec.get("accept")}
    return out


def test_multi_round_multi_sibling_dag_matches_events_and_screens(tmp_path):
    from cap_evolve import graph

    run_dir = _run_dir(tmp_path)

    # Round 1: two siblings forked from seed — one rejected, one accepted (new best).
    work_a = _stage(run_dir, "cand_a", "seed")
    _ok(_commit(run_dir, work_a, "cand_a", "reject", 0.40))

    work_b = _stage(run_dir, "cand_b", "seed")
    _ok(_commit(run_dir, work_b, "cand_b", "accept", 0.70))
    assert run_dir.best_id == "cand_b"

    # Round 2: cand_c forks from the NEW best (cand_b), with a screen record on disk
    # BEFORE it is committed — proving graph.jsonl picks up screen.py's own artifact
    # rather than requiring a new input.
    work_c = _stage(run_dir, "cand_c", "cand_b")
    screens = run_dir.root / "screens"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / "cand_c__screen1.json").write_text(json.dumps({
        "tag": "cand_c", "screen_tag": "cand_c__screen1", "tier": 1,
        "subset": {"ids": ["1", "2", "3"]}, "decision": "promote",
        "mean_delta": 0.05, "se": 0.02,
    }), encoding="utf-8")
    _ok(_commit(run_dir, work_c, "cand_c", "accept", 0.80))
    assert run_dir.best_id == "cand_c"

    # A MERGE candidate combining cand_a and cand_c (2 parents) — the data model #434
    # asks Phase 1 to support even though #438 owns the merge LOGIC. --parents is the
    # only thing commit.py cannot infer on its own.
    work_m = _stage(run_dir, "cand_merge", "cand_c")
    _ok(_commit(run_dir, work_m, "cand_merge", "accept", 0.85,
                "--parents", "cand_a,cand_c"))

    nodes = {n["id"]: n for n in _graph_nodes(run_dir)}
    assert set(nodes) == {"cand_a", "cand_b", "cand_c", "cand_merge"}

    # --- cross-check against events.jsonl (pre-existing, independent of graph.jsonl) ---
    steps = _step_events(run_dir)
    for cid, node in nodes.items():
        assert cid in steps, f"{cid} has a graph node but no step event — not a view"
        expected_accept = steps[cid]["accept"]
        assert node["status"] == ("accepted" if expected_accept else "rejected")
        if cid != "cand_merge":  # single-parent nodes: parent must match the step event
            assert node["parents"] == [steps[cid]["parent"]]

    # --- edit_kind / parents shape ---
    assert nodes["cand_a"]["parents"] == ["seed"]
    assert nodes["cand_a"]["edit_kind"] == "code"
    assert nodes["cand_b"]["parents"] == ["seed"]
    assert nodes["cand_c"]["parents"] == ["cand_b"]
    assert nodes["cand_merge"]["parents"] == ["cand_a", "cand_c"]
    assert nodes["cand_merge"]["edit_kind"] == "merge"

    # --- cross-check the screen/subset fields against the screen file written above ---
    assert nodes["cand_c"]["screen"] is not None
    assert nodes["cand_c"]["screen"]["subset_ids"] == ["1", "2", "3"]
    assert nodes["cand_c"]["screen"]["decision"] == "promote"
    assert nodes["cand_c"]["subset"]["task_ids"] == ["1", "2", "3"]
    # cand_a/cand_b/cand_merge never went through screen.py — no screen artifact exists.
    assert nodes["cand_a"]["screen"] is None
    assert nodes["cand_b"]["screen"] is None

    # --- val_mean matches what was committed ---
    assert nodes["cand_a"]["val_mean"] == 0.40
    assert nodes["cand_c"]["val_mean"] == 0.80

    # --- build_dag reconstructs the correct children edges ---
    dag = graph.build_dag(run_dir)
    assert set(dag["cand_b"]["children"]) == {"cand_c"}
    assert set(dag["cand_a"]["children"]) == {"cand_merge"}
    assert set(dag["cand_c"]["children"]) == {"cand_merge"}
    assert dag["cand_merge"]["children"] == []


def test_graph_jsonl_absent_when_never_committed(tmp_path):
    """No commit -> no graph.jsonl. It is written lazily by the same step that would
    otherwise write nothing at all — never pre-created, never required to exist."""
    from cap_evolve import graph

    run_dir = _run_dir(tmp_path)
    assert not (run_dir.root / graph.GRAPH_FILENAME).exists()
    assert graph.read_nodes(run_dir) == []
