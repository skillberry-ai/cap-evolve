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
        assert len(e.split("\n  (full feedback")[0]) <= fd.entry_chars() + 40
    links = fd._LINK_RE.findall(block)
    assert len(links) == 2
    assert all((rd.root / fd.DIR / n).read_text(encoding="utf-8").count(LONG) == 1 for n in links)


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


# ---- bounded entries, the lowest trial, errored trials, HC2 (review round 3) ----------

def test_a_later_good_trial_never_hides_an_earlier_failure(monkeypatch):
    """The lowest-scoring trial is in the entry the optimizer reads, summary or fallback."""
    from cap_evolve import feedback_digest as fd

    fail = "FAIL-SIGNAL: the review missed the misfiled initiative. " + "detail " * 300
    good = "the review flagged the item correctly. " + "detail " * 300
    pt = {"task_id": "t0", "reward": 0.5,
          "feedback": harness._join_trial_feedback([(0, 0.0, fail), (1, 1.0, good), (2, 1.0, good)])}
    # 1) no summarizer: the deterministic fallback leads with the lowest trial
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY", "off")
    body = fd.condense([pt])["t0"]
    assert body.startswith("trials: trial 0 0.000 (lowest), trial 1 1.000, trial 2 1.000")
    assert "lowest (trial 0): FAIL-SIGNAL" in body and len(body) <= fd.entry_chars()
    # 2) a summarizer that only talks about the good trials still gets the code-written header
    monkeypatch.delenv("CAPEVOLVE_FEEDBACK_SUMMARY")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    class RD:
        root = None
        events = []

        def log_event(self, kind, **kw):
            self.events.append((kind, kw))

    import tempfile
    rd = RD()
    rd.root = Path(tempfile.mkdtemp())
    seen = {}

    def call(cfg, prompt):
        seen["prompt"] = prompt
        return json.dumps({"t0": "The review is good."})

    body = fd.condense([pt], rd, call=call)["t0"]
    assert "FAIL-SIGNAL" in seen["prompt"] and '"reward": 0.0' in seen["prompt"]
    assert body.splitlines()[0] == "trials: trial 0 0.000 (lowest), trial 1 1.000, trial 2 1.000"
    assert rd.events[0][0] == "feedback_summary" and rd.events[0][1]["summarized"] == 1


def test_summarizer_failure_falls_back_and_is_logged(tmp_path, monkeypatch):
    from cap_evolve import RunDir, feedback_digest as fd

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    rows = [_pt(f"t{i}", 0.0) for i in range(23)]   # 3 batches of at most 10

    calls = []

    def boom(cfg, prompt):
        calls.append(prompt)
        raise TimeoutError("gateway down")

    out = fd.condense(rows, rd, call=boom)
    assert len(calls) == 3
    assert set(out) == {f"t{i}" for i in range(23)} and all(TAIL in v for v in out.values())
    ev = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    s = [e for e in ev if e["kind"] == "feedback_summary"][-1]
    assert s["fallback"] == 23 and s["summarized"] == 0 and "gateway down" in s["errors"][0]


def test_summaries_are_cached_by_content(tmp_path, monkeypatch):
    from cap_evolve import RunDir, feedback_digest as fd

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    n = []
    call = lambda cfg, p: (n.append(1), json.dumps({"a": "short summary"}))[1]
    fd.condense([_pt("a", 0.0)], rd, call=call)
    fd.condense([_pt("a", 0.0)], rd, call=call)
    assert len(n) == 1


def test_summarizer_model_and_gateway_come_from_the_environment_only(monkeypatch):
    from cap_evolve import feedback_digest as fd

    for k in ("CAPEVOLVE_FEEDBACK_SUMMARY", "CAPEVOLVE_FEEDBACK_SUMMARY_MODEL",
              "CAPEVOLVE_FEEDBACK_SUMMARY_BASE_URL", "CAPEVOLVE_FEEDBACK_SUMMARY_API_KEY",
              "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert fd.summarizer_config() is None                      # no credentials: fallback only
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    assert fd.summarizer_config()["model"] == "claude-haiku-4-5"
    monkeypatch.setenv("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude/ibm/claude-haiku-4-5")
    assert fd.summarizer_config()["model"] == "claude/ibm/claude-haiku-4-5"
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY_MODEL", "rits/zai-org/glm-5-3")
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY_BASE_URL", "https://gw.example/")
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY_API_KEY", "k2")
    cfg = fd.summarizer_config()
    assert (cfg["model"], cfg["base_url"], cfg["bearer"]) == ("rits/zai-org/glm-5-3", "https://gw.example", "k2")
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY", "off")
    assert fd.summarizer_config() is None


def test_short_feedback_is_shown_unchanged(tmp_path):
    from cap_evolve import RunDir, feedback_digest as fd

    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    pt = {"task_id": "s", "reward": 0.0, "feedback": "expected 42, got 41"}
    block = harness._failures_block([pt], [], [], run_dir=rd)
    assert "- s (reward 0.00): expected 42, got 41" in block and fd.DIR not in block


def test_the_failure_index_lists_at_most_40_tasks_and_names_the_rest(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY", "off")
    af = [{"task_id": f"a{i}", "reward": 0.0, "feedback": "x" * 5000} for i in range(30)]
    fl = [{"task_id": f"f{i}", "reward": 0.1 + i / 100, "feedback": "y" * 5000} for i in range(30)]
    block = harness._failures_block(af, fl, [])
    listed = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert len(listed) == 40 and listed[30].startswith("- f0 ")
    assert "+20 more failing task(s) not listed" in block and "f29" in block
    monkeypatch.setenv("CAPEVOLVE_MAX_LISTED_FAILURES", "5")
    assert len([ln for ln in harness._failures_block(af, fl, []).splitlines() if ln.startswith("- ")]) == 5


def test_a_large_run_keeps_the_whole_prompt_inside_the_inline_limit(monkeypatch):
    """200 failing tasks x 3 trials x 4 KB: the size review round 3 measured at 3.75 MB."""
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY", "off")
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
