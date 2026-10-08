"""plan_round.py's branch-count logic (issue #665, workstream 2).

Forensic finding this exists for: every round of run_20261003_184253 forked exactly
one candidate with no stated reason N was 1, not more. These tests assert the branch
count is a FUNCTION of cluster count/overlap/score_lost -- never a fixed constant (the
anti-pattern issue #665 names explicitly: "Fixed 3-candidate loops").
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plan_round  # noqa: E402  (sys.path must be seeded first)

from cap_evolve import Budget, RunDir, graph, harness, task_ownership  # noqa: E402
from cap_evolve.candidate_graph import CandidateGraph  # noqa: E402
from cap_evolve.types import Rollout, Score, Task  # noqa: E402


def _cluster(sig: str, tasks: list[str], score_lost: float, tag: str | None = None) -> dict:
    return {"signature": sig, "tasks": tasks, "score_lost": score_lost, "tag": tag}


def test_single_root_cause_yields_one_slot_and_one_ish_branch():
    clusters = [_cluster("wrong write action", ["1", "2"], 0.2)]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 1
    assert plan_round.estimate_branches(groups[0], groups) == 1


def test_several_unrelated_root_causes_scale_total_branches_up():
    # Four clusters with disjoint vocabularies -> no signature overlap -> 4 slots.
    clusters = [
        _cluster("payment method count violation", ["1"], 0.1),
        _cluster("basic economy change never attempted", ["2"], 0.1),
        _cluster("cancel already flown unenforced", ["3"], 0.1),
        _cluster("origin destination change unenforced", ["4"], 0.1),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 4  # one slot per unrelated cause, not merged

    single_total = plan_round.estimate_branches(
        plan_round.group_clusters([clusters[0]])[0], plan_round.group_clusters([clusters[0]]))
    unrelated_total = sum(plan_round.estimate_branches(g, groups) for g in groups)
    assert unrelated_total > single_total  # proportionally more than the single-cluster case
    assert unrelated_total == 4  # one branch per independent, low-stakes slot


def test_overlapping_root_causes_group_into_fewer_slots_than_unrelated():
    # Four clusters that all share vocabulary ("write action" surface) -> overlap merges
    # them into ONE slot, unlike the unrelated case above which stays at 4 slots.
    clusters = [
        _cluster("wrong write action flight", ["1"], 0.1),
        _cluster("wrong write action payment", ["2"], 0.1),
        _cluster("wrong write action seat", ["3"], 0.1),
        _cluster("wrong write action baggage", ["4"], 0.1),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 1
    assert len(groups[0]) == 4

    unrelated_groups = plan_round.group_clusters([
        _cluster("payment method count violation", ["1"], 0.1),
        _cluster("basic economy change never attempted", ["2"], 0.1),
        _cluster("cancel already flown unenforced", ["3"], 0.1),
        _cluster("origin destination change unenforced", ["4"], 0.1),
    ])
    assert len(groups) < len(unrelated_groups)  # grouped case: fewer candidate SLOTS


def test_branch_count_is_not_a_fixed_constant():
    """No scenario here may land on a hardcoded "always 3" (or any other fixed N) --
    the count must visibly track the input, both up and down, even against a generous cap.
    """
    one = plan_round.group_clusters([_cluster("a b c", ["1"], 0.1)])
    many_unrelated = plan_round.group_clusters([
        _cluster("alpha", ["1"], 0.1), _cluster("beta", ["2"], 0.1),
        _cluster("gamma", ["3"], 0.1), _cluster("delta", ["4"], 0.1),
        _cluster("epsilon", ["5"], 0.1),
    ])
    high_cap = 100  # a generous ceiling: if the result still came out "3" it would be hardcoded
    n_one = plan_round.estimate_branches(one[0], one, max_cap=high_cap)
    totals_unrelated = sum(plan_round.estimate_branches(g, many_unrelated, max_cap=high_cap)
                          for g in many_unrelated)
    assert n_one == 1
    assert totals_unrelated == 5
    assert n_one != 3 and totals_unrelated != 3  # the exact anti-pattern issue #665 names


def test_high_stakes_single_cluster_slot_gets_a_second_branch():
    """A lone cluster that carries most of the round's score_lost is worth a second
    implementation attempt -- the uncertainty bump, not the cluster-count term."""
    clusters = [
        _cluster("alpha", ["1"], 0.9),   # dominates score_lost
        _cluster("beta", ["2"], 0.05),
        _cluster("gamma", ["3"], 0.05),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 3  # unrelated signatures: no merging
    alpha_group = next(g for g in groups if g[0]["signature"] == "alpha")
    assert plan_round.estimate_branches(alpha_group, groups) == 2  # 1 (count) + 1 (stakes)


def test_two_unrelated_clusters_with_equal_score_lost_do_not_both_get_bumped():
    """Regression for the double-bump bug: two unrelated clusters each independently
    clearing HIGH_STAKES_SHARE (here, tied at 50/50) must NOT both get the stakes bump --
    that gave 2+2=4 total branches, more than even the 5-overlapping-capped-at-3 case, and
    is not "the ONE cluster carrying most of the damage" the bump is meant to reward."""
    clusters = [
        _cluster("alpha", ["1"], 0.5),
        _cluster("beta", ["2"], 0.5),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 2
    totals = sum(plan_round.estimate_branches(g, groups) for g in groups)
    assert totals == 2  # 1 + 1, no bump on either side of the tie


# -- alternative_parents (issue #684 item 3: ownership-driven branch diversity) ------------

def test_alternative_parents_surfaces_non_champion_owning_distinct_tasks():
    ownership = {
        "owners": {
            "t1": ["champ"],
            "t2": ["champ"],
            "t3": ["rival"],       # rival cleanly wins a task the champion doesn't
            "t4": ["rival"],
        },
    }
    out = plan_round.alternative_parents(ownership, champion_id="champ")
    assert len(out) == 1
    assert out[0]["candidate"] == "rival"
    assert out[0]["tasks_uniquely_owned"] == ["t3", "t4"]
    assert "rival" in out[0]["rationale"] and "champ" in out[0]["rationale"]


def test_alternative_parents_empty_when_champion_dominates_every_task():
    ownership = {
        "owners": {"t1": ["champ"], "t2": ["champ"], "t3": ["champ"]},
    }
    assert plan_round.alternative_parents(ownership, champion_id="champ") == []


def test_alternative_parents_ignores_ties_with_champion():
    # rival ties the champion on t1 (champion still in the owner set there) -- not a
    # diversity signal; only t2, where champion is absent entirely, counts.
    ownership = {
        "owners": {"t1": ["champ", "rival"], "t2": ["rival"]},
    }
    out = plan_round.alternative_parents(ownership, champion_id="champ")
    assert len(out) == 1
    assert out[0]["tasks_uniquely_owned"] == ["t2"]


def test_alternative_parents_empty_without_champion_or_ownership():
    ownership = {"owners": {"t1": ["rival"]}}
    assert plan_round.alternative_parents(ownership, champion_id=None) == []
    assert plan_round.alternative_parents(None, champion_id="champ") == []


def test_alternative_parents_sorted_by_tasks_owned_descending():
    ownership = {
        "owners": {
            "t1": ["rival_small"],
            "t2": ["rival_big"], "t3": ["rival_big"], "t4": ["rival_big"],
        },
    }
    out = plan_round.alternative_parents(ownership, champion_id="champ")
    assert [row["candidate"] for row in out] == ["rival_big", "rival_small"]


def test_plan_round_output_includes_alternative_parents_field():
    clusters = [_cluster("wrong write action", ["1", "2"], 0.2)]
    ownership = {"owners": {"t1": ["rival"], "t2": ["champ"]}}
    out = plan_round.plan_round(clusters, None, None, ownership=ownership, champion_id="champ")
    assert out["alternative_parents"] == [
        {"candidate": "rival", "tasks_uniquely_owned": ["t1"],
         "rationale": "rival currently best-scores 1 task(s) (t1) that the champion (champ) does not"},
    ]


def test_high_stakes_bump_requires_a_clear_margin_over_the_runner_up():
    """A unique leader that only narrowly beats the runner-up (no clear margin) should
    not get the bump either -- it's not clearly "the one cluster carrying most of the
    damage", just a slightly bigger slice."""
    clusters = [
        _cluster("alpha", ["1"], 0.50),
        _cluster("beta", ["2"], 0.45),
        _cluster("gamma", ["3"], 0.05),
    ]
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 3
    alpha_group = next(g for g in groups if g[0]["signature"] == "alpha")
    assert plan_round.estimate_branches(alpha_group, groups) == 1  # no bump: too close to beta


def test_overlap_min_lowered_bundles_related_but_not_near_identical_clusters():
    """Issue #676: round 1 of the first real multi-objective run produced 3 small,
    single-lever candidates because 3 related clusters each fell short of the old
    OVERLAP_MIN=0.5 and so each got its own slot. These three pairwise share exactly
    1 of 3 tokens each (overlap 0.333) -- genuinely related (same "write" mechanism),
    but nowhere near half-overlapping -- so they must bundle into one slot at the
    lowered default while still NOT bundling at the old 0.5 bar."""
    clusters = [
        _cluster("write payment flow", ["1"], 0.1),
        _cluster("write seat error", ["2"], 0.1),
        _cluster("write baggage check", ["3"], 0.1),
    ]
    assert plan_round.OVERLAP_MIN < 0.5  # the lowering this test is for

    groups = plan_round.group_clusters(clusters)  # default (lowered) OVERLAP_MIN
    assert len(groups) == 1
    assert len(groups[0]) == 3

    old_threshold_groups = plan_round.group_clusters(clusters, overlap_min=0.5)
    assert len(old_threshold_groups) == 3  # the old bar kept them apart -- this is the bug

    unrelated = plan_round.group_clusters([
        _cluster("payment method count violation", ["1"], 0.1),
        _cluster("basic economy change never attempted", ["2"], 0.1),
    ])
    assert len(unrelated) == 2  # genuinely disjoint vocabularies still don't bundle


def test_generic_shared_token_alone_does_not_bundle_short_signatures():
    """Review on #681: lowering OVERLAP_MIN to 0.3 means a single shared token now
    clears the bar for 3-token signatures (1/3 = 0.333 >= 0.3) even when it is a
    generic failure-handling word, not a shared implementation surface. Concrete
    repro: "retry seat lock" and "retry refund amount" are unrelated failure
    mechanisms (seat locking vs refund amount) that merely both involved a retry --
    the raw ratio clears OVERLAP_MIN, but they must NOT bundle."""
    a, b = frozenset("retry seat lock".split()), frozenset("retry refund amount".split())
    assert len(a & b) / min(len(a), len(b)) >= plan_round.OVERLAP_MIN  # raw ratio clears it

    groups = plan_round.group_clusters([
        _cluster("retry seat lock", ["1"], 0.1),
        _cluster("retry refund amount", ["2"], 0.1),
    ])
    assert len(groups) == 2  # must stay separate: "retry" alone isn't shared root cause

    # The legitimate case this PR's lowered threshold exists for must still bundle --
    # same 1/3 raw overlap, but "write" is a shared implementation surface, not a
    # generic strategy word, so it is NOT filtered and the bundle still happens.
    legit = plan_round.group_clusters([
        _cluster("write payment flow", ["1"], 0.1),
        _cluster("write seat error", ["2"], 0.1),
    ])
    assert len(legit) == 1


def test_max_branches_per_slot_only_clamps_down_never_up():
    clusters = [_cluster(f"shared surface {i}", ["t"], 0.1) for i in range(6)]
    # Make them all overlap (shared "shared surface" tokens) -> one big group of 6.
    groups = plan_round.group_clusters(clusters)
    assert len(groups) == 1
    assert plan_round.estimate_branches(groups[0], groups, max_cap=2) == 2  # clamped down
    assert plan_round.estimate_branches(groups[0], groups, max_cap=100) == 6  # not clamped up to 100


# -- end-to-end: real RunDir rollouts -> task_ownership.from_run -> plan_round -------------

class _FixedTasksAdapter:
    """Minimal adapter whose reward per task is read straight off ``solves``, so two
    candidates can be given deliberately NON-overlapping solved-task sets -- unlike
    ``SyntheticAdapter``'s monotonic level ladder, this can produce a genuine
    champion-doesn't-dominate-everything scenario for the ownership signal to catch."""

    def __init__(self, task_ids: list[str], solves: dict[str, set[str]]):
        self.task_ids = task_ids
        self.solves = solves  # {tag: {task_ids this tag scores 1.0 on}}

    def tasks(self, split: str):
        return [Task(id=t, input=t, target="1") for t in self.task_ids]

    def run_target(self, task, ctx, *, seed: int = 0):
        return Rollout(task_id=task.id, output=str(ctx), trace="")

    def score(self, task, rollout):
        tag = Path(str(rollout.output)).name  # ctx dir name doubles as the tag here
        ok = task.id in self.solves.get(tag, set())
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback="",
                     trial_rewards=[1.0 if ok else 0.0])


def test_plan_round_end_to_end_surfaces_a_real_non_champion_owner(tmp_path):
    """Real RunDir, real persisted rollouts, real graph.jsonl nodes: champion ("champ")
    wins t1/t2 but NOT t3/t4; rival ("rival") was rejected on aggregate (it loses t1/t2)
    yet cleanly owns t3/t4 the champion never solves. plan_round's alternative_parents
    must surface rival with exactly those two tasks -- including picking up a REJECTED
    candidate's evidence, per issue #684 item 3's explicit example."""
    task_ids = ["t1", "t2", "t3", "t4"]
    solves = {"champ": {"t1", "t2"}, "rival": {"t3", "t4"}}
    adapter = _FixedTasksAdapter(task_ids, solves)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget())
    # Pin every task to val -- a ratio-based split with only 4 tasks could otherwise
    # leave t3/t4 out of the val split entirely, which would hide the signal this
    # test exists to check rather than exercising it.
    harness.ensure_splits(adapter, run_dir, seed=0,
                          split_ids={"train": task_ids, "val": task_ids, "test": task_ids})

    for tag in ("champ", "rival"):
        cdir = tmp_path / tag
        cdir.mkdir()
        harness.evaluate_candidate(adapter, cdir, run_dir=run_dir, split="val",
                                   n_trials=1, tag=tag)

    graph.append_node(run_dir, node_id="champ", parents=["seed"], status="accepted",
                      val_mean=0.5)
    graph.append_node(run_dir, node_id="rival", parents=["seed"], status="rejected",
                      val_mean=0.0)
    run_dir.set_best("champ")

    cg = CandidateGraph.load(run_dir)
    ownership = task_ownership.from_run(run_dir, cg)
    out = plan_round.plan_round([], cg, None, ownership=ownership, champion_id=run_dir.best_id)

    assert out["alternative_parents"] == [
        {"candidate": "rival", "tasks_uniquely_owned": ["t3", "t4"],
         "rationale": "rival currently best-scores 2 task(s) (t3, t4) that the champion "
                      "(champ) does not"},
    ]


def test_plan_round_end_to_end_no_alternative_when_champion_dominates(tmp_path):
    """Same wiring, but champion wins every task outright -- no non-champion owner
    exists, so alternative_parents must be empty (no false positives)."""
    task_ids = ["t1", "t2"]
    solves = {"champ": {"t1", "t2"}, "rival": set()}
    adapter = _FixedTasksAdapter(task_ids, solves)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget())
    harness.ensure_splits(adapter, run_dir, seed=0,
                          split_ids={"train": task_ids, "val": task_ids, "test": task_ids})

    for tag in ("champ", "rival"):
        cdir = tmp_path / tag
        cdir.mkdir()
        harness.evaluate_candidate(adapter, cdir, run_dir=run_dir, split="val",
                                   n_trials=1, tag=tag)

    graph.append_node(run_dir, node_id="champ", parents=["seed"], status="accepted",
                      val_mean=1.0)
    graph.append_node(run_dir, node_id="rival", parents=["seed"], status="rejected",
                      val_mean=0.0)
    run_dir.set_best("champ")

    cg = CandidateGraph.load(run_dir)
    ownership = task_ownership.from_run(run_dir, cg)
    out = plan_round.plan_round([], cg, None, ownership=ownership, champion_id=run_dir.best_id)

    assert out["alternative_parents"] == []
