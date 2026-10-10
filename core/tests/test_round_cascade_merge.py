"""#435/#437/#438: round.py's DEFAULT per-round cascade, end to end, zero-API.

Three siblings off the seed: cand_1 fixes fn_a (t0,t1), cand_2 fixes fn_b (t2,t3) — disjoint —
and cand_3 breaks everything. With NO screen/merge flags, one ``round.py`` call must:

  1. screen all three itself (the driver never calls screen.py);
  2. drop cand_3 on its screen kill — no full-val rollout for it;
  3. build merge_cand_1_cand_2 (2 parents), screen it, and see it keep both parents' gains;
  4. gate ONLY the merge on full val (its parents are inside it, never gated twice);
  5. record it all in graph.jsonl, so a later commit with no --parents keeps both parents.

This is exactly run v18's waste (unscreened full-val gates + hand-built unions paying a second
full gate), fixed by the default path rather than by a flag the driver must remember.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(SCRIPTS))

BASE = "def fn_a(x):\n    return x\n\n\ndef fn_b(x):\n    return x\n"
FIX_A = BASE.replace("def fn_a(x):\n    return x", 'def fn_a(x):\n    return x + "MARK_A"')
FIX_B = BASE.replace("def fn_b(x):\n    return x", 'def fn_b(x):\n    return x + "MARK_B"')
# Also rewrites fn_a, but DIFFERENTLY from FIX_A — a real edit collision on the same module,
# used to prove a genuinely non-mergeable pair (as opposed to merely same-cluster) is still
# free to --no-merge.
FIX_A_OTHER = BASE.replace("def fn_a(x):\n    return x",
                          'def fn_a(x):\n    return x + "OTHER_MARK_A"')
BROKEN = BASE + "\n\nBROKEN = True\n"

ADAPTER = '''
from pathlib import Path
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.trials import run_trials_pool
from cap_evolve.types import Task, Rollout, Score

NEEDS = {"t0": "MARK_A", "t1": "MARK_A", "t2": "MARK_B", "t3": "MARK_B"}

class Adapter(CapabilityAdapter):
    def tasks(self, split):
        return [Task(id=f"t{i}") for i in range(8)]

    def run_target(self, task, ctx, *, seed=0):
        return Rollout(task_id=task.id,
                       output=(Path(ctx) / "tools" / "tools.py").read_text(encoding="utf-8"))

    def run_trials(self, tasks, ctx, *, n_trials, base_seed):
        return run_trials_pool(lambda t, s: self.run_target(t, ctx, seed=s), tasks,
                               n_trials=n_trials, base_seed=base_seed)

    def score(self, task, rollout):
        src = rollout.output or ""
        need = NEEDS.get(task.id)
        ok = "BROKEN" not in src and (need is None or need in src)
        r = 1.0 if ok else 0.0
        return Score(task_id=task.id, reward=r, feedback="ok" if ok else f"needs {need}",
                     trial_rewards=[r])
'''


def _env():
    return dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"),
                CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


def _cap(root: Path, name: str, tools: str) -> Path:
    d = root / name
    (d / "tools").mkdir(parents=True, exist_ok=True)
    (d / "tools" / "tools.py").write_text(tools, encoding="utf-8")
    (d / "policy").mkdir(parents=True, exist_ok=True)
    (d / "policy" / "policy.md").write_text("base policy\n", encoding="utf-8")
    return d


def _setup(tmp_path: Path):
    import importlib.util

    from cap_evolve import Budget, RunDir, harness

    project = tmp_path / "project"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(ADAPTER, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("cascade_adapter",
                                                  project / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=10))
    harness.ensure_splits(mod.Adapter(), run_dir, seed=0,
                          split_ids={"val": [f"t{i}" for i in range(8)], "train": [], "test": []})
    harness.baseline(mod.Adapter(), _cap(tmp_path, "seed_cap", BASE), run_dir=run_dir)
    # The round parent's snapshot carries its OWN (stale) diagnosis — a merge must not inherit it.
    (run_dir.candidate_dir("seed") / "DIAGNOSIS.json").write_text(json.dumps(
        {"clusters": [{"id": "OLD", "tasks": ["t7"]}], "edits": []}), encoding="utf-8")
    work = run_dir.root / "work"
    for tag, src, cl, tasks in (("cand_1", FIX_A, "A", ["t0", "t1"]),
                                ("cand_2", FIX_B, "B", ["t2", "t3"]),
                                ("cand_3", BROKEN, "C", ["t4"])):
        d = _cap(work, tag, src)
        # #611: every candidate carries its own diagnosis — which differs per sibling, so a
        # naive 3-way merge of this file would collide on EVERY pair.
        (d / "DIAGNOSIS.json").write_text(json.dumps(
            {"candidate": tag, "clusters": [{"id": cl, "tasks": tasks}],
             "edits": [{"id": f"E_{tag}", "clusters": [cl]}]}), encoding="utf-8")
    return run_dir, project


def _full_val_tags(run_dir) -> set[str]:
    tags = set()
    for f in (run_dir.root / "rollouts" / "val").glob("*.json"):
        parts = f.name.split("__")
        if len(parts) >= 3 and not any(p.startswith("screen") for p in parts[1:-1]):
            tags.add("__".join(parts[1:-1]))
    return tags - {"seed"}


def test_default_round_screens_kills_merges_and_gates_the_merge_once(tmp_path):
    from cap_evolve import graph

    run_dir, project = _setup(tmp_path)
    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1,cand_2,cand_3",
                        "--n-trials", "1", "--concurrency", "1"],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)

    # 1-2. every sibling screened by round.py itself; the harmful one killed, never gated.
    assert {t: s["auto"] for t, s in out["screen_stage"].items()} == \
        {"cand_1": True, "cand_2": True, "cand_3": True}
    assert out["screen_killed"] == ["cand_3"]
    assert out["dominated"] == {}, "disjoint siblings are never subsets of each other (#633)"

    # 3. the disjoint survivors were merged, and the merge screened before any gate.
    merge = "merge_cand_1_cand_2"
    m = next(x for x in out["merge_stage"]["merges"] if x["tag"] == merge)
    assert m["parents"] == ["cand_1", "cand_2"] and m["qualifies"] is True
    assert m["screen"]["decision"] == "promote" and m["screen"]["auto"] is True
    assert out["merge_stage"]["subsumed"] == {"cand_1": merge, "cand_2": merge}

    # 4. full val paid for exactly one candidate: the merge (plus the null controls).
    assert [r["tag"] for r in out["candidates"]] == [merge]
    assert out["candidates"][0]["reward"] == 1.0
    assert {t for t in _full_val_tags(run_dir) if not t.startswith("ctl_")} == {merge}

    events = [json.loads(ln) for ln in run_dir.events_path.read_text().splitlines() if ln.strip()]
    kinds = [(e["kind"], e.get("tag")) for e in events]
    batch = next(i for i, e in enumerate(events) if e["kind"] == "agent_optimize_round_batch")
    assert kinds.index(("screen", merge)) < batch, "the merge must be screened before gating"
    assert events[batch]["gated"] == [merge] and events[batch]["screen_killed"] == ["cand_3"]

    # 5. graph.jsonl: real DAG structure, one transition per state change.
    dag = graph.build_dag(run_dir)
    assert dag[merge]["parents"] == ["cand_1", "cand_2"]
    assert dag[merge]["edit_kind"] == "merge" and dag[merge]["status"] == "gated"
    assert dag[merge]["subset"]["rationale"].startswith("pairwise merge of screen survivors")
    assert [n["status"] for n in graph.read_nodes(run_dir) if n["id"] == merge] == \
        ["proposed", "screened", "gated"]
    for parent in ("cand_1", "cand_2"):
        assert dag[parent]["status"] == "superseded" and dag[parent]["merged_into"] == merge
        assert dag[parent]["parents"] == ["seed"]
    assert dag["cand_3"]["status"] == "screened" and dag["cand_3"]["screen"]["decision"] == "kill"
    # No --plan: cluster_ids came from each candidate's own DIAGNOSIS.json (#611's parser).
    assert dag["cand_1"]["cluster_ids"] == ["A"] and dag[merge]["cluster_ids"] == ["A", "B"]
    assert set(dag["cand_1"]["children"]) >= {merge}

    # #611 interaction: the merge's DIAGNOSIS.json is its parents' diagnoses combined, never
    # the round parent's stale one and never a 3-way-merge collision.
    diag = json.loads((run_dir.root / "work" / merge / "DIAGNOSIS.json").read_text())
    assert [c["id"] for c in diag["clusters"]] == ["A", "B"]
    assert [e["id"] for e in diag["edits"]] == ["E_cand_1", "E_cand_2"]

    # The terminal commit needs no --parents (the node round.py built already has both) and NO
    # --missing-diagnosis-justification: the auto-merge satisfies #611's precondition itself.
    c = subprocess.run([sys.executable, str(SCRIPTS / "commit.py"), "--run-dir", str(run_dir.root),
                        "--candidate-id", merge, "--from-dir", str(run_dir.root / "work" / merge),
                        "--decision", "accept", "--val", "1.0", "--val-unverified", "fixture: val not under test", "--note", "merge accepted",
                        "--missing-handover-justification", "fixture: handover not under test"],
                       capture_output=True, text=True, env=_env())
    assert c.returncode == 0, c.stdout + c.stderr
    assert json.loads(c.stdout)["diagnosis_recorded"] is True
    final = graph.latest_node(run_dir, merge)
    assert final["status"] == "accepted" and final["parents"] == ["cand_1", "cand_2"]
    assert final["edit_kind"] == "merge" and final["cluster_ids"] == ["A", "B"]
    step = [json.loads(ln) for ln in run_dir.events_path.read_text().splitlines()
            if ln.strip() and json.loads(ln).get("kind") == "step"][-1]
    assert step["merge_of"] == ["cand_1", "cand_2"], "dashboard multi-parent edge"


def test_no_merge_gates_every_survivor_alone(tmp_path):
    run_dir, project = _setup(tmp_path)
    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1,cand_2,cand_3",
                        "--n-trials", "1", "--concurrency", "1", "--no-merge"],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["merge_stage"] is None
    assert sorted(r["tag"] for r in out["candidates"]) == ["cand_1", "cand_2"]


def _sibling(run_dir, tag, src, cluster, tasks):
    d = _cap(run_dir.root / "work", tag, src)
    (d / "DIAGNOSIS.json").write_text(json.dumps(
        {"candidate": tag, "clusters": [{"id": cluster, "tasks": tasks}],
         "edits": [{"id": f"E_{tag}", "clusters": [cluster]}]}), encoding="utf-8")


def test_repeated_no_merge_with_eligible_pairs_is_hard_blocked(tmp_path):
    """#630: 7/9 rounds of a real run passed --no-merge with disjoint, screened survivors, so
    merge_stage never ran once. The first such decline is allowed but announced IN REAL TIME;
    past max_merge_skips (default 1) it is refused, with no override flag."""
    run_dir, project = _setup(tmp_path)

    def rnd(cands, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
             "--project", str(project), "--candidates", cands, "--n-trials", "1",
             "--concurrency", "1", "--single-candidate-justification", "merge-budget test",
             *extra], capture_output=True, text=True, env=_env())

    def events(kind):
        return [e for e in (json.loads(ln) for ln in run_dir.events_path.read_text().splitlines()
                            if ln.strip()) if e.get("kind") == kind]

    p1 = rnd("cand_1,cand_2", "--no-merge")
    assert p1.returncode == 0, p1.stdout + p1.stderr
    assert "WARNING: --no-merge declined merging [['cand_1', 'cand_2']]" in p1.stderr
    warn = events("merge_compliance_warning")
    assert len(warn) == 1 and warn[0]["realtime"] is True and warn[0]["refused"] is False
    assert warn[0]["reason"] == "no_merge_with_eligible_pairs"
    assert warn[0]["disjoint_pairs"] == [["cand_1", "cand_2"]]
    assert json.loads(p1.stdout)["merge_skip"]["merge_skips_used"] == 1
    # Re-running the SAME round (a re-gate) does not spend the budget a second time.
    assert rnd("cand_1,cand_2", "--no-merge").returncode == 0

    _sibling(run_dir, "cand_4", FIX_A, "D", ["t0", "t1"])
    _sibling(run_dir, "cand_5", FIX_B, "E", ["t2", "t3"])
    n_batches = len(events("agent_optimize_round_batch"))
    n_compliance = len(events("agent_optimize_compliance"))
    refused = rnd("cand_4,cand_5", "--no-merge")
    assert refused.returncode == 2, refused.stdout + refused.stderr
    err = json.loads(refused.stdout)
    assert "max_merge_skips=1" in err["error"] and "no override flag" in err["why"]
    assert events("merge_compliance_warning")[-1]["refused"] is True
    # Refused before any compliance event or round batch, so it is never itself counted.
    assert len(events("agent_optimize_round_batch")) == n_batches
    assert len(events("agent_optimize_compliance")) == n_compliance

    # Obeying is free: the screens are on disk, and the default path merges them.
    ok = rnd("cand_4,cand_5")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["merge_stage"]["chosen"] == ["merge_cand_4_cand_5"]

    # A round where no merge APPLIED (both siblings independently diverged on the SAME module,
    # fn_a — #684's is_mergeable, not mere cluster labels, decides this now) spends nothing and
    # is not refused even with the budget gone. Same cluster label ("F") on purpose: #684 item 4
    # requires that two same-cluster siblings on DISJOINT files/functions now be attempted (see
    # cand_4/cand_5 above, which share no cluster but prove the same point) — only a genuine
    # same-module collision, not a shared cluster id, is a free skip.
    _sibling(run_dir, "cand_6", FIX_A, "F", ["t0", "t1"])
    _sibling(run_dir, "cand_7", FIX_A_OTHER, "F", ["t0", "t1"])
    same = rnd("cand_6,cand_7", "--no-merge")
    assert same.returncode == 0, same.stdout + same.stderr
    assert json.loads(same.stdout)["merge_skip"] is None


def test_merge_that_loses_a_parents_gain_is_not_gated_and_parents_are():
    """integrate.py's rule (gains do not compose), applied with the screens already paid."""
    import round as rnd

    a = {"paired": {"ids": ["t0", "t1"], "deltas": [1.0, 1.0]}}
    b = {"paired": {"ids": ["t2"], "deltas": [1.0]}}
    lost_a = {"paired": {"ids": ["t0", "t1", "t2"], "deltas": [1.0, 0.0, 1.0]}}
    assert rnd.keeps_parent_gain(lost_a, b) and not rnd.keeps_parent_gain(lost_a, a)
    assert not rnd.keeps_parent_gain(lost_a, {"paired": {"ids": ["t9"], "deltas": [0.0]}})

    merges = [
        {"tag": "m_ab", "parents": ["a", "b"], "qualifies": False, "screen": {"mean_delta": .9}},
        {"tag": "m_ac", "parents": ["a", "c"], "qualifies": True, "screen": {"mean_delta": .5}},
        {"tag": "m_bc", "parents": ["b", "c"], "qualifies": True, "screen": {"mean_delta": .4}},
    ]
    chosen, covered = rnd.choose_merges(merges)
    assert chosen == ["m_ac"] and covered == {"a": "m_ac", "c": "m_ac"}  # b gated alone


def test_build_merge_dir_refuses_a_same_lines_collision(tmp_path):
    import merge

    base = _cap(tmp_path, "base", BASE)
    a = _cap(tmp_path, "a", FIX_A)
    b = _cap(tmp_path, "b", FIX_A.replace("MARK_A", "OTHER"))
    res = merge.build_merge_dir(base, a, b, tmp_path / "out")
    assert res["built"] is False and res["conflicts"][0]["file"] == "tools/tools.py"
    assert not (tmp_path / "out").exists()

    (a / "policy" / "policy.md").write_text("base policy\nrule A\n", encoding="utf-8")
    res = merge.build_merge_dir(base, a, _cap(tmp_path, "b2", FIX_B), tmp_path / "out")
    assert res["built"], res
    merged = (tmp_path / "out" / "tools" / "tools.py").read_text()
    assert "MARK_A" in merged and "MARK_B" in merged
    assert "rule A" in (tmp_path / "out" / "policy" / "policy.md").read_text()


FIX_AB = FIX_A.replace("def fn_b(x):\n    return x", 'def fn_b(x):\n    return x + "MARK_B"')


def test_diff_contained_is_strict_literal_containment(tmp_path):
    """#633: subset -> True; related-but-different, disjoint, identical -> False."""
    import merge

    base = _cap(tmp_path, "base", BASE)
    a, ab = _cap(tmp_path, "a", FIX_A), _cap(tmp_path, "ab", FIX_AB)
    assert merge.diff_contained(base, a, ab)
    assert not merge.diff_contained(base, ab, a)                        # superset, not subset
    # Same function, different edit, plus more: related, NOT contained.
    other = _cap(tmp_path, "other", FIX_AB.replace("MARK_A", "OTHER_A"))
    assert not merge.diff_contained(base, a, other)
    b = _cap(tmp_path, "b", FIX_B)
    assert not merge.diff_contained(base, a, b) and not merge.diff_contained(base, b, a)
    assert not merge.diff_contained(base, a, _cap(tmp_path, "a2", FIX_A))  # identical
    # Containment across files: A edits only the policy, B edits the policy the same way + code.
    (a / "tools" / "tools.py").write_text(BASE, encoding="utf-8")
    (a / "policy" / "policy.md").write_text("base policy\nrule A\n", encoding="utf-8")
    (ab / "policy" / "policy.md").write_text("base policy\nrule A\n", encoding="utf-8")
    assert merge.diff_contained(base, a, ab)


def test_strict_subset_sibling_is_not_gated(tmp_path):
    """#633: cand_1 (fn_a) is a literal subset of cand_2 (fn_a + fn_b) — only cand_2 is gated."""
    from cap_evolve import graph

    run_dir, project = _setup(tmp_path)
    (run_dir.root / "work" / "cand_2" / "tools" / "tools.py").write_text(FIX_AB, encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1,cand_2,cand_3",
                        "--n-trials", "1", "--concurrency", "1"],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["dominated"] == {"cand_1": "cand_2"}
    assert [r["tag"] for r in out["candidates"]] == ["cand_2"]
    assert {t for t in _full_val_tags(run_dir) if not t.startswith("ctl_")} == {"cand_2"}
    assert graph.build_dag(run_dir)["cand_1"]["dominated_by"] == "cand_2"
    assert graph.latest_node(run_dir, "cand_1")["status"] == "superseded"


def test_subset_pair_is_not_charged_to_the_no_merge_budget(tmp_path):
    """#633 x #630: once cand_1 is dominated, --no-merge declines no eligible pair."""
    run_dir, project = _setup(tmp_path)
    (run_dir.root / "work" / "cand_2" / "tools" / "tools.py").write_text(FIX_AB, encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1,cand_2,cand_3",
                        "--n-trials", "1", "--concurrency", "1", "--no-merge"],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["dominated"] == {"cand_1": "cand_2"} and out["merge_skip"] is None
    assert [r["tag"] for r in out["candidates"]] == ["cand_2"]


def test_related_but_not_subset_sibling_is_still_gated(tmp_path):
    """Same function as a sibling, but a DIFFERENT edit to it: not a subset, gated normally."""
    run_dir, project = _setup(tmp_path)
    (run_dir.root / "work" / "cand_2" / "tools" / "tools.py").write_text(
        FIX_AB.replace("MARK_A", "OTHER_A"), encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
                        "--project", str(project), "--candidates", "cand_1,cand_2,cand_3",
                        "--n-trials", "1", "--concurrency", "1", "--no-merge"],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["dominated"] == {}
    assert sorted(r["tag"] for r in out["candidates"]) == ["cand_1", "cand_2"]
