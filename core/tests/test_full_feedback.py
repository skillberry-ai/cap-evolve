"""The scorer's feedback reaches every optimizer prompt whole.

LLM-judge feedback (each judge's full rationale) runs to thousands of characters,
and the actionable part is often at the END (the verdict after the analysis). Each
prompt builder below once sliced it to a few hundred characters; this pins that none
does.
"""

import json
import re
import sys
from pathlib import Path

import pytest

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


def test_hill_climb_failure_index_bounds_each_entry_and_keeps_the_verdict(tmp_path):
    """A long rationale is condensed to the entry bound, its END (the verdict) kept, and the
    whole text is one link away under the run dir."""
    from cap_evolve import RunDir, feedback_digest as fd

    assert LONG in harness._fmt(_pt("a", 0.0))          # _fmt alone does not cut
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    block = harness._failures_block([_pt("a", 0.0)], [_pt("b", 0.5)], [], run_dir=rd)
    entries = [e for e in block.split("\n- ") if e.startswith(("a (", "b ("))]
    assert len(entries) == 2
    for e in entries:
        assert TAIL in e
        body = e.split("\n    (full feedback")[0]
        assert len(body) < len(e) and len(body) <= fd.entry_chars() + 40, len(body)
    links = fd._LINK_RE.findall(block)
    assert len(links) == 2
    assert all((rd.root / fd.DIR / n).read_text(encoding="utf-8").count(LONG) == 1 for n in links)


def test_gepa_reflection_keeps_full_feedback(tmp_path):
    mb = SplitResult(split="train", reward=0.0, stderr=0.0,
                     per_task=[_pt("a", 0.0, raw={"output": "out"})])
    gepa._write_reflection(tmp_path, mb)
    assert f"- Feedback: {LONG}" in (tmp_path / "REFLECTION.md").read_text(encoding="utf-8")


def test_skillopt_slow_update_keeps_each_tasks_verdict():
    text = skillopt._slow_update_instructions(
        2, {"regressed": [_pt("a", 0.0)], "persistent_fail": [_pt("b", 0.0)],
            "stable_success": []})
    assert text.count(TAIL) == 2 and LONG not in text      # bounded, the end of each kept


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


# ---- bounded entries, the lowest trial, errored trials, HC2 (review round 3) ----------

def _fake_optimizer(reply=None, calls=None, cost=None, fail=None):
    """An OptimizerFn that 'summarizes' by writing ./summaries.json, as the real CLI is told to."""
    def opt(workdir, prompt):
        files = {f.name: f.read_text(encoding="utf-8") for f in sorted(Path(workdir).glob("tasks/*.md"))}
        if calls is not None:
            calls.append((files, prompt))
        if fail:
            raise fail
        ids = re.findall(r"^- tasks/\S+ -> (\S+)$", prompt, re.M)
        (Path(workdir) / "summaries.json").write_text(
            json.dumps({i: (reply(i) if callable(reply) else reply) for i in ids}), encoding="utf-8")
        return cost
    opt.command = "fake-optimizer --model m1"
    return opt


def test_a_later_good_trial_never_hides_an_earlier_failure(tmp_path):
    """The lowest-scoring trial is in the entry the optimizer reads, summary or fallback."""
    from cap_evolve import RunDir, feedback_digest as fd

    fail = "FAIL-SIGNAL: the review missed the misfiled initiative. " + "detail " * 300
    good = "the review flagged the item correctly. " + "detail " * 300
    pt = {"task_id": "t0", "reward": 0.5,
          "feedback": harness._join_trial_feedback([(0, 0.0, fail), (1, 1.0, good), (2, 1.0, good)])}
    # 1) no optimizer: the deterministic fallback leads with the lowest trial
    body = fd.condense([pt])["t0"]
    assert body.startswith("trials: trial 0 0.000 (lowest), trial 1 1.000, trial 2 1.000")
    assert "lowest (trial 0): FAIL-SIGNAL" in body and len(body) <= fd.entry_chars()
    # 2) the run's optimizer summarizes; it sees the failing trial with its reward, and even a
    #    summary that only talks about the good trials still gets the code-written header
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    calls = []
    body = fd.condense([pt], rd, _fake_optimizer("The review is good.", calls))["t0"]
    task_file = calls[0][0]["00.md"]
    assert "## trial 0 - reward 0.000" in task_file and "FAIL-SIGNAL" in task_file
    assert "LOWEST-scoring trial" in calls[0][1]
    assert body.splitlines()[0] == "trials: trial 0 0.000 (lowest), trial 1 1.000, trial 2 1.000"
    assert body.splitlines()[1] == "The review is good."


def test_the_summary_uses_the_runs_optimizer_and_counts_its_spend(tmp_path):
    """Same optimizer (its command keys the cache), 10 tasks per call, spend recorded."""
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rows = [_pt(f"t{i}", 0.0) for i in range(23)]
    calls = []
    opt = _fake_optimizer(lambda i: f"summary of {i}", calls, cost={"cost_usd": 0.25, "tokens": 1000})
    out = fd.condense(rows, rd, opt)
    assert len(calls) == 3 and sorted(len(files) for files, _ in calls) == [3, 10, 10]
    assert all(out[f"t{i}"] == f"summary of t{i}" for i in range(23))
    spent = rd.spent
    assert spent.optimizer_usd == pytest.approx(0.75) and spent.optimizer_tokens == 3000
    ev = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    s = [e for e in ev if e["kind"] == "feedback_summary"][-1]
    assert s["optimizer"] == "fake-optimizer --model m1" and s["summarized"] == 23 and s["calls"] == 3
    # the cache is keyed by the optimizer command: same command = no new call, another = new calls
    fd.condense(rows, rd, opt)
    assert len(calls) == 3
    other = _fake_optimizer("x", calls)
    other.command = "fake-optimizer --model m2"
    fd.condense(rows, rd, other)
    assert len(calls) == 6
    assert not list((rd.root / "work").glob("feedback_summary_*"))   # scratch removed


def test_summarizer_failure_falls_back_and_is_logged(tmp_path):
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rows = [_pt(f"t{i}", 0.0) for i in range(23)]
    calls = []
    err = RuntimeError("optimizer failed (1): rate limited")
    err.cost = {"cost_usd": 0.1, "tokens": 50}
    out = fd.condense(rows, rd, _fake_optimizer(calls=calls, fail=err))
    assert len(calls) == 3
    assert set(out) == {f"t{i}" for i in range(23)} and all(TAIL in v for v in out.values())
    assert rd.spent.optimizer_usd == pytest.approx(0.3)   # a failed call is still paid
    ev = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    s = [e for e in ev if e["kind"] == "feedback_summary"][-1]
    assert s["fallback"] == 23 and s["summarized"] == 0 and "rate limited" in s["errors"][0]
    # an optimizer that writes no summaries.json is a fallback too, not a crash
    lazy = lambda wd, p: None
    lazy.command = "lazy"
    assert all(TAIL in v for v in fd.condense(rows[:2], rd, lazy).values())


def test_the_summary_can_be_switched_off(tmp_path, monkeypatch):
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    calls = []
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY", "off")
    out = fd.condense([_pt("a", 0.0)], rd, _fake_optimizer("s", calls))
    assert calls == [] and TAIL in out["a"]


def test_the_slow_update_prompt_is_bounded_too(tmp_path):
    """Round 4: SkillOpt's slow/meta update listed up to 20 tasks' full feedback (243 KB)."""
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rows = [{"task_id": f"t{i}", "reward": 0.3, "feedback": harness._join_trial_feedback(
        [(k, 0.1 * k, f"task {i} trial {k} " + "z" * 4000 + f" VERDICT-{i}") for k in range(3)])}
        for i in range(20)]
    cats = {"regressed": rows[:10], "persistent_fail": rows[10:], "stable_success": []}
    text = skillopt._slow_update_instructions(2, cats, rd)
    assert len(text.encode("utf-8")) < 30_000, len(text.encode("utf-8"))
    assert all(f"VERDICT-{i}" in text for i in range(20))          # the end of each text survives
    assert len(fd._LINK_RE.findall(text)) == 20
    assert "trials: trial 0 0.000 (lowest)" in text


def test_short_feedback_is_shown_unchanged(tmp_path):
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    pt = {"task_id": "s", "reward": 0.0, "feedback": "expected 42, got 41"}
    block = harness._failures_block([pt], [], [], run_dir=rd)
    assert "- s (reward 0.00): expected 42, got 41" in block and fd.DIR not in block


def test_the_failure_index_lists_at_most_40_tasks_and_names_the_rest(monkeypatch):
    af = [{"task_id": f"a{i}", "reward": 0.0, "feedback": "x" * 5000} for i in range(30)]
    fl = [{"task_id": f"f{i}", "reward": 0.1 + i / 100, "feedback": "y" * 5000} for i in range(30)]
    block = harness._failures_block(af, fl, [])
    listed = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert len(listed) == 40 and listed[30].startswith("- f0 ")
    assert "+20 more failing task(s) not listed" in block and "f29" in block
    monkeypatch.setenv("CAPEVOLVE_MAX_LISTED_FAILURES", "5")
    assert len([ln for ln in harness._failures_block(af, fl, []).splitlines() if ln.startswith("- ")]) == 5


def test_a_large_run_keeps_the_whole_prompt_inside_the_inline_limit():
    """200 failing tasks x 3 trials x 4 KB: the size review round 3 measured at 3.75 MB."""
    per = []
    for i in range(200):
        per.append({"task_id": f"t{i}", "reward": 0.3, "feedback": harness._join_trial_feedback(
            [(k, 0.1 * k, f"task {i} trial {k} " + "z" * 4000) for k in range(3)])})
    cur = SplitResult(split="val", reward=0.3, stderr=0.02, per_task=per, n_tasks=200, n_scored=200)
    text = harness._focus_instructions(cur, None, "all", capabilities=["skill-package"], seed_empty=False)
    sys.path.insert(0, str(REPO / "skills" / "optimizers" / "run-optimizer" / "scripts"))
    import run as run_optimizer  # noqa: E402
    assert len(text.encode("utf-8")) <= run_optimizer.MAX_INLINE_PROMPT_BYTES, len(text.encode("utf-8"))


def test_an_errored_trial_is_labelled_errored():
    out = harness._join_trial_feedback([(0, None, "Rollout timed out (infra)"), (1, 0.5, "judge: missed WHY")])
    assert out.startswith("[trial 0 errored]\nRollout timed out (infra)")
    assert "[trial 1 reward 0.500]" in out
    assert skillopt._TRIAL_LABEL_RE.sub("", out).split() == "Rollout timed out (infra) judge: missed WHY".split()


def test_hc2_joins_every_failing_draw_not_only_the_first():
    ts = [hc2.Trace("a", "c1", k, r, Path(f"a__c1__t{k}.json"), signature=f"sig {k}")
          for k, r in ((0, 0.0), (1, 1.0), (2, 0.5))]
    fb = hc2._pooled_split_result(ts, ["a"]).per_task[0]["feedback"]
    assert "[trial 0 reward 0.000]\nsig 0" in fb and "[trial 2 reward 0.500]\nsig 2" in fb
    assert "sig 1" not in fb      # a passing draw is not failure feedback


def test_a_rollout_tag_with_a_path_in_it_is_refused(tmp_path):
    import pytest
    from cap_evolve import RunDir

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    for bad in ("../x", "a/b", "c*", "x[1]"):
        with pytest.raises(ValueError):
            harness.split_result_from_rollouts(rd, ["ok", bad], "val")


def test_full_feedback_files_reach_the_optimizer_workdir(tmp_path):
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    block = harness._failures_block([_pt("a", 0.0)], [], [], run_dir=rd)
    wd = rd.root / "work" / "cand_0001"
    wd.mkdir(parents=True)
    assert fd.copy_linked_from(block, wd) == 1
    (name,) = fd._LINK_RE.findall(block)
    assert (wd / fd.DIR / name).read_text(encoding="utf-8").count(LONG) == 1
    assert fd.DIR in harness._SNAPSHOT_IGNORE        # never part of a candidate
