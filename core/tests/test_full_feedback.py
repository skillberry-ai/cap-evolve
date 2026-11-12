"""The scorer's feedback reaches every optimizer prompt whole.

LLM-judge feedback (each judge's full rationale) runs to thousands of characters,
and the actionable part is often at the END (the verdict after the analysis). Each
prompt builder below once sliced it to a few hundred characters; this pins that none
does.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import gepa, harness, hc2, skillopt  # noqa: E402
from cap_evolve.loop import SplitResult  # noqa: E402

TAIL = "FINAL-VERDICT: the revision dropped the named customer"
LONG = ("quality judge: " + "analysis of the WHAT/WHY criteria. " * 150
        + "; revision judge: " + "content fidelity notes. " * 150 + TAIL)


def _pt(tid, reward, **kw):
    return {"task_id": tid, "reward": reward, "feedback": LONG, **kw}


def test_long_feedback_is_longer_than_any_former_cap():
    assert len(LONG) > 5000


def test_hill_climb_failure_index_keeps_full_feedback():
    line = harness._fmt(_pt("a", 0.0))
    assert LONG in line and line.endswith(TAIL)
    block = harness._failures_block([_pt("a", 0.0)], [_pt("b", 0.5)], [])
    assert block.count(LONG) == 2


def test_gepa_reflection_keeps_full_feedback(tmp_path):
    mb = SplitResult(split="train", reward=0.0, stderr=0.0,
                     per_task=[_pt("a", 0.0, raw={"output": "out"})])
    gepa._write_reflection(tmp_path, mb)
    assert f"- Feedback: {LONG}" in (tmp_path / "REFLECTION.md").read_text(encoding="utf-8")


def test_skillopt_slow_update_keeps_full_feedback():
    text = skillopt._slow_update_instructions(
        2, {"regressed": [_pt("a", 0.0)], "persistent_fail": [_pt("b", 0.0)],
            "stable_success": []})
    assert text.count(LONG) == 2


def test_hc2_pooled_feedback_keeps_full_signature():
    tr = hc2.Trace("a", "c1", 0, 0.0, Path("a__c1__t0.json"), signature=LONG)
    sr = hc2._pooled_split_result([tr], ["a"])
    assert sr.per_task[0]["feedback"] == LONG


def test_join_trial_feedback_keeps_every_trial_once():
    assert harness._join_trial_feedback([(0, 1.0, "same"), (1, 0.5, "same")]) == "same"
    out = harness._join_trial_feedback([(1, 0.2, "B " + LONG), (0, 0.9, "A"), (2, 0.4, "A")])
    assert out.index("[trial 0 reward 0.900, trial 2 reward 0.400]\nA") < out.index("[trial 1 reward 0.200]")
    assert ("B " + LONG) in out


def test_evaluate_and_resume_render_identical_multi_trial_feedback(tmp_path):
    from cap_evolve import RunDir, Score, Task, Rollout

    class A:
        def tasks(self, split):
            return [Task(id="t0", input="x")]

        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output=str(seed))

        def score(self, task, rollout):
            r = 0.25 if int(rollout.output) % 2 else 0.75
            return Score(task_id=task.id, reward=r, feedback=f"judge says {r} {LONG}")

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    from cap_evolve.splits import Splits
    rd.write_splits(Splits(train=["t0"], val=["t0"], test=["t0"], seed=0))
    cand = tmp_path / "cand"
    cand.mkdir()
    live = harness.evaluate_candidate(A(), cand, run_dir=rd, split="val", tag="c", n_trials=3)
    fb = live.per_task[0]["feedback"]
    assert fb.count(LONG) == 2 and "trial 0" in fb and "trial 1" in fb and "trial 2" in fb
    resumed = harness.split_result_from_rollouts(rd, "c", "val")
    assert resumed.per_task[0]["feedback"] == fb


def test_failure_index_lists_every_flaky_task_worst_first():
    flaky = [{"task_id": f"t{i}", "reward": 0.1 + i / 40, "feedback": "f"} for i in range(25)][::-1]
    block = harness._failures_block([], flaky, [])
    assert all(f"- t{i} " in block for i in range(25))
    assert block.index("- t0 ") < block.index("- t24 ")


def test_trials_are_ordered_numerically_not_as_text():
    out = harness._join_trial_feedback([(10, 0.1, "late"), (2, 0.9, "early")])
    assert out.index("[trial 2 ") < out.index("[trial 10 ")


def test_pooled_tags_name_the_tag_in_each_trial_label(tmp_path):
    """Pooled control replicates each number their trials from 0; the label must still be unique."""
    from cap_evolve import RunDir
    from cap_evolve.splits import Splits

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rd.write_splits(Splits(train=["t0"], val=["t0"], test=["t0"], seed=0))
    vdir = rd.rollout_dir("val")
    vdir.mkdir(parents=True, exist_ok=True)
    for tag, r in (("c", 0.25), ("c_rep1", 0.75)):
        (vdir / f"t0__{tag}__t0.json").write_text(json.dumps(
            {"score": {"task_id": "t0", "reward": r, "feedback": f"judge on {tag}"}}), encoding="utf-8")
    fb = harness.split_result_from_rollouts(rd, ["c", "c_rep1"], "val").per_task[0]["feedback"]
    assert "[c trial 0 reward 0.250]" in fb and "[c_rep1 trial 0 reward 0.750]" in fb


def test_pooling_two_results_keeps_both_sides_feedback_once():
    from cap_evolve.loop import pool_split_results

    def res(fb):
        return SplitResult(split="val", reward=0.5, stderr=0.0, n_tasks=1, n_scored=1,
                           per_task=[{"task_id": "t0", "reward": 0.5, "trial_rewards": [0.5],
                                      "feedback": fb}])
    pooled = pool_split_results(res("run A: " + LONG), res("run B: " + TAIL))
    fb = pooled.per_task[0]["feedback"]
    assert fb.count(LONG) == 1 and fb.count("run B: " + TAIL) == 1
    assert pool_split_results(res("same"), res("same")).per_task[0]["feedback"] == "same"


def test_skillopt_clusters_ignore_the_multi_trial_labels():
    """The label carries per-trial rewards; it must not split one failure into two clusters."""
    p = "Wrong tool: called cancel_reservation before the user confirmed the change"
    x = harness._join_trial_feedback([(0, 0.0, p + " (a)"), (1, 0.0, p + " (b)")])
    y = harness._join_trial_feedback([(0, 1.0, p + " (c)"), (1, 0.0, p + " (d)")])
    pats = skillopt._failure_patterns([{"task_id": "x", "reward": 0.0, "feedback": x},
                                       {"task_id": "y", "reward": 0.5, "feedback": y}])
    assert len(pats) == 1 and pats[0]["n"] == 2, pats
    assert not pats[0]["pattern"].startswith("[")


def test_pooled_round_tags_keep_their_full_tag_in_the_label(tmp_path):
    """Round tags hold "__" themselves; two rounds of one stage must not share a label."""
    from cap_evolve import RunDir
    from cap_evolve.splits import Splits

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rd.write_splits(Splits(train=["t0"], val=["t0"], test=["t0"], seed=0))
    vdir = rd.rollout_dir("val")
    vdir.mkdir(parents=True, exist_ok=True)
    tags = ["r000__cand_0003__rung1_0", "r001__cand_0003__rung1_0"]
    for tag, r in zip(tags, (0.0, 1.0)):
        (vdir / f"t0__{tag}__t1000.json").write_text(json.dumps(
            {"score": {"task_id": "t0", "reward": r, "feedback": f"judge on {tag}"}}), encoding="utf-8")
    fb = harness.split_result_from_rollouts(rd, tags, "val").per_task[0]["feedback"]
    assert "[r000__cand_0003__rung1_0 trial 1000 reward 0.000]" in fb
    assert "[r001__cand_0003__rung1_0 trial 1000 reward 1.000]" in fb


def _one_task(fb, reward=0.5):
    return SplitResult(split="val", reward=reward, stderr=0.0, n_tasks=1, n_scored=1,
                       per_task=[{"task_id": "t0", "reward": reward, "trial_rewards": [reward],
                                  "feedback": fb}])


def test_pooling_keeps_a_side_whose_text_is_inside_the_other():
    """The dedup is an exact match: a shorter rationale contained in a longer one is kept."""
    from cap_evolve.loop import pool_split_results

    a, b = "wrong tool: book_flight; wrong cabin", "wrong cabin"
    fb = pool_split_results(_one_task(a), _one_task(b)).per_task[0]["feedback"]
    assert f"[evaluation 1 of 2]\n{a}" in fb and f"[evaluation 2 of 2]\n{b}" in fb


def test_pooling_names_each_evaluation_and_does_not_nest_on_repeat():
    """Each evaluation numbers its trials from 0; the header says which evaluation a label is in."""
    from cap_evolve.loop import pool_split_results

    side = lambda r: harness._join_trial_feedback([(0, r, f"judge {r}"), (1, r, "same")])
    once = pool_split_results(_one_task(side(0.5)), _one_task(side(0.9)))
    twice = pool_split_results(once, _one_task(side(0.1)))   # the missing-retry loop pools again
    fb = twice.per_task[0]["feedback"]
    assert [ln for ln in fb.splitlines() if ln.startswith("[evaluation")] == [
        "[evaluation 1 of 3]", "[evaluation 2 of 3]", "[evaluation 3 of 3]"]
    assert fb.count("[trial 0 reward") == 3
    assert pool_split_results(_one_task("same"), _one_task("same")).per_task[0]["feedback"] == "same"


def test_skillopt_clusters_ignore_the_pooled_evaluation_headers():
    from cap_evolve.loop import pool_split_results

    p = "Wrong tool: called cancel_reservation before the user confirmed the change"
    x = pool_split_results(_one_task(p + " (a)", 0.0), _one_task(p + " (b)", 0.0)).per_task[0]["feedback"]
    pats = skillopt._failure_patterns([{"task_id": "x", "reward": 0.0, "feedback": x},
                                       {"task_id": "y", "reward": 0.0, "feedback": p + " (c)"}])
    assert len(pats) == 1 and pats[0]["n"] == 2, pats
