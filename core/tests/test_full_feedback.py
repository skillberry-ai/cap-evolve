"""The scorer's feedback reaches every optimizer prompt: whole when it fits, else within ONE budget.

LLM-judge feedback (each judge's full rationale) runs to thousands of characters,
and the actionable part is often at the END (the verdict after the analysis). Each
prompt builder below once sliced it to a few hundred characters. Now all feedback in one
optimizer prompt shares one budget (``feedback_digest``): shown in full when it fits,
otherwise only the longest entries are condensed, and only as much as needed.
"""

import contextlib
import importlib.util
import json
import re
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import feedback_digest as fd  # noqa: E402
from cap_evolve import gepa, harness, hc2, skillopt  # noqa: E402
from cap_evolve.loop import SplitResult  # noqa: E402

TAIL = "FINAL-VERDICT: the revision dropped the named customer"
LONG = ("quality judge: " + "analysis of the WHAT/WHY criteria. " * 150
        + "; revision judge: " + "content fidelity notes. " * 150 + TAIL)
join = fd.join_trial_feedback


def _pt(tid, reward, **kw):
    return {"task_id": tid, "reward": reward, "feedback": LONG, **kw}


def _rd(tmp_path, **budget):
    from cap_evolve import Budget, RunDir
    return RunDir.create(tmp_path / ".capevolve", ts="t", **({"budget": Budget(**budget)} if budget else {}))


def _size(s: str) -> int:
    return len(s.encode("utf-8"))


def test_long_feedback_is_longer_than_any_former_cap():
    assert len(LONG) > 5000


# ---- the budget: full when it fits, condensed only when needed (review round 5, item 2) ----

def _fake_optimizer(reply=None, calls=None, cost=None, fail=None, delay=0.0):
    """An OptimizerFn that 'summarizes' by writing ./summaries.json, as the real CLI is told to."""
    def opt(workdir, prompt):
        files = {f.name: f.read_text(encoding="utf-8") for f in sorted(Path(workdir).glob("tasks/*.md"))}
        if calls is not None:
            calls.append((files, prompt))
        if delay:
            time.sleep(delay)
        if fail:
            raise fail
        ids = re.findall(r"^- tasks/\S+ -> (\S+)$", prompt, re.M)
        (Path(workdir) / "summaries.json").write_text(
            json.dumps({i: (reply(i) if callable(reply) else reply) for i in ids}), encoding="utf-8")
        return cost
    opt.command = "fake-optimizer --model m1"
    return opt


def test_few_failing_tasks_with_long_feedback_are_shown_in_full_with_no_summary(tmp_path):
    """3 tasks x 9 KB fit the budget: every word inline, no summarizer call, no link."""
    rd = _rd(tmp_path)
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": f"task {i}: " + "x" * 9000 + f" VERDICT-{i}"}
            for i in range(3)]
    calls = []
    block = harness._failures_block(rows, [], [], run_dir=rd, optimizer=_fake_optimizer("s", calls))
    assert calls == []
    assert all(r["feedback"] in block for r in rows)
    assert fd.DIR not in block and "condensed" not in block


def test_hill_climb_failure_index_condenses_to_the_budget_and_keeps_the_verdict(tmp_path, monkeypatch):
    """Over the budget, each long rationale is condensed, its END (the verdict) kept, and the
    whole text is one link away under the run dir."""
    monkeypatch.setenv(fd.ENV_BUDGET, "4000")
    assert LONG in harness._fmt(_pt("a", 0.0))          # _fmt alone does not cut
    rd = _rd(tmp_path)
    budget = fd.Budget()
    block = harness._failures_block([_pt("a", 0.0)], [_pt("b", 0.5)], [], run_dir=rd, budget=budget)
    assert 0 < budget.used <= 4000
    entries = [e for e in block.split("\n- ") if e.startswith(("a (", "b ("))]
    assert len(entries) == 2 and all(TAIL in e for e in entries)
    assert _size(block) < 4000 + 1000                  # the budget plus the section headers
    links = fd.LINK_RE.findall(block)
    assert len(links) == 2
    assert all((rd.root / fd.DIR / n).read_text(encoding="utf-8").count(LONG) == 1 for n in links)


def test_many_failing_tasks_stay_within_the_budget_and_keep_each_lowest_trial(tmp_path):
    """200 tasks x 3 trials x 4 KB: the listed entries fit the budget, each one's lowest trial is
    there, and the tasks the budget cannot list are named."""
    rows = [{"task_id": f"t{i:03d}", "reward": 0.3, "feedback": join(
        [(k, 0.1 * k, f"task {i} trial {k} LOW-{i}-{k} " + "z" * 4000) for k in range(3)])}
        for i in range(200)]
    got = fd.fit(rows, 48_000, head=harness._fmt_head)
    assert got.used <= 48_000
    assert sum(_size(e) for e in got.entries.values()) + _size(got.rest_line) == got.used
    assert len(got.shown) + len(got.rest) == 200 and got.rest
    for pt in got.shown:
        i = int(pt["task_id"][1:])
        e = got.entries[pt["task_id"]]
        assert "trial 0 0.000 (lowest)" in e and f"LOW-{i}-0" in e, e[:300]
    assert "more failing task(s) not listed" in got.rest_line
    # a smaller budget lists fewer tasks: the listing comes from the budget, not a fixed cap
    assert len(fd.fit(rows, 12_000, head=harness._fmt_head).shown) < len(got.shown)


def test_budget_left_by_short_entries_goes_to_the_long_ones():
    short = [{"task_id": f"s{i}", "reward": 0.0, "feedback": f"short {i}"} for i in range(6)]
    long_ = [{"task_id": f"l{i}", "reward": 0.0, "feedback": f"long {i} " + "y" * 20_000} for i in range(3)]
    limit = 10_000
    got = fd.fit(short + long_, limit, head=harness._fmt_head)
    assert all(got.entries[f"s{i}"].endswith(f"short {i}") for i in range(6))     # shown in full
    assert got.condensed == 3 and got.used <= limit
    # each long entry got far more than an equal split of the budget over all nine tasks
    assert all(_size(got.entries[f"l{i}"]) > 2 * limit // 9 for i in range(3))
    assert all(_size(got.entries[f"l{i}"]) > 3000 for i in range(3))


def test_the_failure_index_names_the_tasks_the_budget_cannot_list(monkeypatch):
    af = [{"task_id": f"a{i}", "reward": 0.0, "feedback": "x" * 5000} for i in range(30)]
    fl = [{"task_id": f"f{i}", "reward": 0.1 + i / 100, "feedback": "y" * 5000} for i in range(30)]
    monkeypatch.setenv(fd.ENV_BUDGET, "8000")
    block = harness._failures_block(af, fl, [])
    listed = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert 0 < len(listed) < 60 and listed[0].startswith("- a0 ")
    m = re.search(r"\+(\d+) more failing task\(s\) not listed", block)
    assert m and int(m.group(1)) == 60 - len(listed) and "f29" in block
    assert fd.ENV_BUDGET in block


def test_a_large_run_keeps_the_whole_prompt_inside_the_inline_limit():
    """200 failing tasks x 3 trials x 4 KB: the size review round 3 measured at 3.75 MB."""
    per = []
    for i in range(200):
        per.append({"task_id": f"t{i}", "reward": 0.3, "feedback": join(
            [(k, 0.1 * k, f"task {i} trial {k} " + "z" * 4000) for k in range(3)])})
    cur = SplitResult(split="val", reward=0.3, stderr=0.02, per_task=per, n_tasks=200, n_scored=200)
    text = harness._focus_instructions(cur, None, "all", capabilities=["skill-package"], seed_empty=False)
    sys.path.insert(0, str(REPO / "skills" / "optimizers" / "run-optimizer" / "scripts"))
    import run as run_optimizer  # noqa: E402
    assert len(text.encode("utf-8")) <= run_optimizer.MAX_INLINE_PROMPT_BYTES, len(text.encode("utf-8"))
    # the budget is what fills it: the rest of the prompt leaves room for the whole default budget
    assert len(text.encode("utf-8")) > fd.DEFAULT_BUDGET * 0.9


# ---- the blocks that share one prompt's budget ---------------------------------------

def test_gepa_reflection_keeps_full_feedback(tmp_path):
    mb = SplitResult(split="train", reward=0.0, stderr=0.0,
                     per_task=[_pt("a", 0.0, raw={"output": "out"})])
    gepa._write_reflection(tmp_path, mb)
    assert f"- Feedback: {LONG}" in (tmp_path / "REFLECTION.md").read_text(encoding="utf-8")


def test_gepa_reflection_takes_half_the_budget_and_brings_its_linked_files(tmp_path):
    rd = _rd(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    mb = SplitResult(split="train", reward=0.0, stderr=0.0,
                     per_task=[_pt(f"a{i}", 0.0, raw={"output": "out"}) for i in range(20)])
    budget = fd.Budget()
    gepa._write_reflection(wd, mb, run_dir=rd, budget=budget)
    text = (wd / "REFLECTION.md").read_text(encoding="utf-8")
    assert 0 < budget.used <= fd.budget_bytes() // 2
    assert text.count(TAIL) == len(fd.LINK_RE.findall(text)) > 0
    assert all((wd / fd.DIR / n).is_file() for n in fd.LINK_RE.findall(text))


def test_skillopt_slow_update_keeps_each_tasks_verdict():
    text = skillopt._slow_update_instructions(
        2, {"regressed": [_pt("a", 0.0)], "persistent_fail": [_pt("b", 0.0)],
            "stable_success": []})
    assert text.count(LONG) == 2                       # within the budget: shown in full


def test_the_slow_update_prompt_is_bounded_too(tmp_path):
    """Round 4: SkillOpt's slow/meta update listed up to 20 tasks' full feedback (243 KB)."""
    rd = _rd(tmp_path)
    rows = [{"task_id": f"t{i}", "reward": 0.3, "feedback": join(
        [(k, 0.1 * k, f"task {i} trial {k} " + "z" * 4000 + f" VERDICT-{i}") for k in range(3)])}
        for i in range(20)]
    cats = {"regressed": rows[:10], "persistent_fail": rows[10:], "stable_success": []}
    budget = fd.Budget()
    text = skillopt._slow_update_instructions(2, cats, rd, budget=budget)
    assert budget.used <= fd.budget_bytes() // 2 and _size(text) < fd.budget_bytes() // 2 + 2000
    assert all(f"VERDICT-{i}" in text for i in range(20))          # the end of each text survives
    assert len(fd.LINK_RE.findall(text)) == 20
    assert "trials: trial 0 0.000 (lowest)" in text


def test_the_slow_update_and_failure_index_share_one_budget(tmp_path):
    """SkillOpt's whole slow-update prompt: both blocks together stay inside ONE budget."""
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": f"t{i} " + "q" * 6000} for i in range(30)]
    budget = fd.Budget()
    skillopt._slow_update_instructions(2, {"regressed": rows, "persistent_fail": [], "stable_success": []},
                                       budget=budget)
    first = budget.used
    harness._failures_block(rows, [], [], budget=budget)
    assert first > 0 and budget.used > first and budget.used <= budget.total


# ---- the trial-label grammar (items 4, 6 and 10) -------------------------------------

def test_join_trial_feedback_keeps_every_trial_once():
    assert join([(0, 1.0, "same"), (1, 0.5, "same")]) == "same"
    out = join([(1, 0.2, "B " + LONG), (0, 0.9, "A"), (2, 0.4, "A")])
    assert out.index("[trial 0 reward 0.900, trial 2 reward 0.400]\nA") < out.index("[trial 1 reward 0.200]")
    assert ("B " + LONG) in out


def test_trials_are_ordered_numerically_not_as_text():
    out = join([(10, 0.1, "late"), (2, 0.9, "early")])
    assert out.index("[trial 2 ") < out.index("[trial 10 ")


def test_an_errored_trial_is_labelled_errored():
    out = join([(0, None, "Rollout timed out (infra)"), (1, 0.5, "judge: missed WHY")])
    assert out.startswith("[trial 0 errored]\nRollout timed out (infra)")
    assert "[trial 1 reward 0.500]" in out
    assert fd.strip_labels(out).split() == "Rollout timed out (infra) judge: missed WHY".split()


def test_the_only_text_keeps_its_label_when_other_trials_are_empty_or_errored():
    """Review round 5: the single-text shortcut dropped the labels in exactly these cases."""
    out = join([(0, None, "docker pull 429"), (1, 0.0, ""), (2, 0.0, "")])
    assert "[trial 0 errored]\ndocker pull 429" in out
    assert f"[trial 1 reward 0.000, trial 2 reward 0.000]\n{fd.NO_FEEDBACK}" in out
    out = join([(0, 0.0, ""), (1, 0.0, ""), (2, 1.0, "All checks passed")])
    assert "[trial 2 reward 1.000]\nAll checks passed" in out and "trial 0 reward 0.000" in out
    assert fd.header({"task_id": "x", "reward": 1 / 3, "feedback": out}).startswith(
        "trials: trial 0 0.000 (lowest)")
    assert join([(0, None, "same"), (1, 0.5, "same")]).startswith("[trial 0 errored, trial 1 reward 0.500]")
    assert join([(0, 0.0, ""), (1, 0.0, "")]) == ""


def test_pooled_evaluations_keep_an_evaluation_every_trial_agreed_on(tmp_path):
    """Review round 5: text before the first trial label was dropped, so a reward-0 evaluation
    whose trials agreed vanished, and trial names from two evaluations collided."""
    from cap_evolve.loop import pool_split_results

    def res(fb, rewards):
        return SplitResult(split="val", reward=sum(rewards) / len(rewards), stderr=0.0, n_tasks=1, n_scored=1,
                           per_task=[{"task_id": "t0", "reward": sum(rewards) / len(rewards),
                                      "trial_rewards": rewards, "feedback": fb}])
    first = res(join([(0, 0.0, "BAD: wrong tool"), (1, 0.0, "BAD: wrong tool")]), [0.0, 0.0])
    second = res(join([(0, 1.0, "fine"), (1, 0.5, "missed one step")]), [1.0, 0.5])
    pt = pool_split_results(first, second).per_task[0]
    trials = fd.trials_of(pt)
    assert [(n, r) for n, r, _ in trials] == [("e1 trial 0", 0.0), ("e1 trial 1", 0.0),
                                              ("e2 trial 0", 1.0), ("e2 trial 1", 0.5)]
    assert fd.header(pt).startswith("trials: e1 trial 0 0.000 (lowest), e1 trial 1 0.000,")
    assert "BAD: wrong tool" in fd.fallback(pt, 400)
    # text with no label at all is never dropped either
    assert fd.trials_of({"task_id": "x", "reward": 0.2, "feedback": "lead text\n\n[trial 1 reward 0.000]\nB"})[0] \
        == ("unlabelled", 0.2, "lead text")


def test_skillopt_clusters_ignore_the_multi_trial_labels():
    """The label carries per-trial rewards; it must not split one failure into two clusters."""
    p = "Wrong tool: called cancel_reservation before the user confirmed the change"
    x = join([(0, 0.0, p + " (a)"), (1, 0.0, p + " (b)")])
    y = join([(0, 1.0, p + " (c)"), (1, 0.0, p + " (d)")])
    pats = skillopt._failure_patterns([{"task_id": "x", "reward": 0.0, "feedback": x},
                                       {"task_id": "y", "reward": 0.5, "feedback": y}])
    assert len(pats) == 1 and pats[0]["n"] == 2, pats
    assert not pats[0]["pattern"].startswith("[")


def test_one_label_grammar_for_every_reader():
    """Review round 5: the join, the parser and SkillOpt's stripper are one module's API."""
    import inspect
    assert not hasattr(harness, "_join_trial_feedback") and not hasattr(skillopt, "_TRIAL_LABEL_RE")
    for mod in (harness, hc2, skillopt):
        assert "feedback_digest" in inspect.getsource(mod)
    src = (REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "taskeval.py").read_text(encoding="utf-8")
    assert "feedback_digest.join_trial_feedback" in src and "distinct_feedback" not in src


# ---- evaluation and pooling -----------------------------------------------------------

def test_evaluate_and_resume_render_identical_multi_trial_feedback(tmp_path):
    from cap_evolve import Rollout, Score, Task

    class A:
        def tasks(self, split):
            return [Task(id="t0", input="x")]

        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, output=str(seed))

        def score(self, task, rollout):
            r = 0.25 if int(rollout.output) % 2 else 0.75
            return Score(task_id=task.id, reward=r, feedback=f"judge says {r} {LONG}")

    rd = _rd(tmp_path)
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


def test_pooled_tags_name_the_tag_in_each_trial_label(tmp_path):
    """Pooled control replicates each number their trials from 0; the label must still be unique."""
    from cap_evolve.splits import Splits

    rd = _rd(tmp_path)
    rd.write_splits(Splits(train=["t0"], val=["t0"], test=["t0"], seed=0))
    vdir = rd.rollout_dir("val")
    vdir.mkdir(parents=True, exist_ok=True)
    for tag, r in (("c", 0.25), ("c_rep1", 0.75)):
        (vdir / f"t0__{tag}__t0.json").write_text(json.dumps(
            {"score": {"task_id": "t0", "reward": r, "feedback": f"judge on {tag}"}}), encoding="utf-8")
    fb = harness.split_result_from_rollouts(rd, ["c", "c_rep1"], "val").per_task[0]["feedback"]
    assert "[c trial 0 reward 0.250]" in fb and "[c_rep1 trial 0 reward 0.750]" in fb


def test_pooled_round_tags_keep_their_full_tag_in_the_label(tmp_path):
    """Round tags hold "__" themselves; two rounds of one stage must not share a label."""
    from cap_evolve.splits import Splits

    rd = _rd(tmp_path)
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


def test_pooling_two_results_keeps_both_sides_feedback_once():
    from cap_evolve.loop import pool_split_results

    pooled = pool_split_results(_one_task("run A: " + LONG), _one_task("run B: " + TAIL))
    fb = pooled.per_task[0]["feedback"]
    assert fb.count(LONG) == 1 and fb.count("run B: " + TAIL) == 1
    assert pool_split_results(_one_task("same"), _one_task("same")).per_task[0]["feedback"] == "same"


def test_pooling_keeps_a_side_whose_text_is_inside_the_other():
    """The dedup is an exact match: a shorter rationale contained in a longer one is kept."""
    from cap_evolve.loop import pool_split_results

    a, b = "wrong tool: book_flight; wrong cabin", "wrong cabin"
    fb = pool_split_results(_one_task(a), _one_task(b)).per_task[0]["feedback"]
    assert f"[evaluation 1 of 2]\n[trial 0 reward 0.500]\n{a}" in fb
    assert f"[evaluation 2 of 2]\n[trial 0 reward 0.500]\n{b}" in fb


def test_pooling_the_same_words_follows_the_join_rule():
    """The same UNLABELLED words from every evaluation: every trial gave them, so the text alone
    (join_trial_feedback's rule). Labelled ones keep every evaluation and its rewards."""
    from cap_evolve.loop import pool_split_results

    assert pool_split_results(_one_task("same", 0.0), _one_task("same", 1.0)).per_task[0]["feedback"] == "same"
    a, b = join([(0, 0.0, "same"), (1, 0.0, "other")]), join([(0, 1.0, "same"), (1, 1.0, "other")])
    fb = pool_split_results(_one_task(a, 0.0), _one_task(b, 1.0)).per_task[0]["feedback"]
    assert "[trial 0 reward 0.000]\nsame" in fb and "[trial 0 reward 1.000]\nsame" in fb


def test_pooling_names_each_evaluation_and_does_not_nest_on_repeat():
    """Each evaluation numbers its trials from 0; the header says which evaluation a label is in."""
    from cap_evolve.loop import pool_split_results

    side = lambda r: join([(0, r, f"judge {r}"), (1, r, "same")])
    once = pool_split_results(_one_task(side(0.5)), _one_task(side(0.9)))
    twice = pool_split_results(once, _one_task(side(0.1)))   # the missing-retry loop pools again
    fb = twice.per_task[0]["feedback"]
    assert [ln for ln in fb.splitlines() if ln.startswith("[evaluation")] == [
        "[evaluation 1 of 3]", "[evaluation 2 of 3]", "[evaluation 3 of 3]"]
    assert fb.count("[trial 0 reward") == 3


def test_skillopt_clusters_ignore_the_pooled_evaluation_headers():
    from cap_evolve.loop import pool_split_results

    p = "Wrong tool: called cancel_reservation before the user confirmed the change"
    x = pool_split_results(_one_task(p + " (a)", 0.0), _one_task(p + " (b)", 0.0)).per_task[0]["feedback"]
    pats = skillopt._failure_patterns([{"task_id": "x", "reward": 0.0, "feedback": x},
                                       {"task_id": "y", "reward": 0.0, "feedback": p + " (c)"}])
    assert len(pats) == 1 and pats[0]["n"] == 2, pats


def test_hc2_pooled_feedback_keeps_full_signature():
    tr = hc2.Trace("a", "c1", 0, 0.0, Path("a__c1__t0.json"), signature=LONG)
    sr = hc2._pooled_split_result([tr], ["a"])
    assert sr.per_task[0]["feedback"] == LONG


def test_hc2_joins_every_failing_draw_not_only_the_first():
    ts = [hc2.Trace("a", "c1", k, r, Path(f"a__c1__t{k}.json"), signature=f"sig {k}")
          for k, r in ((0, 0.0), (1, 1.0), (2, 0.5))]
    fb = hc2._pooled_split_result(ts, ["a"]).per_task[0]["feedback"]
    assert "[trial 0 reward 0.000]\nsig 0" in fb and "[trial 2 reward 0.500]\nsig 2" in fb
    assert "sig 1" not in fb      # a passing draw is not failure feedback


def test_a_rollout_tag_with_a_path_in_it_is_refused(tmp_path):
    rd = _rd(tmp_path)
    for bad in ("../x", "a/b", "c*", "x[1]"):
        with pytest.raises(ValueError):
            harness.split_result_from_rollouts(rd, ["ok", bad], "val")


# ---- a condensed entry: lowest trial, bounded header, layout (items 5 and 9) ------------

def test_a_later_good_trial_never_hides_an_earlier_failure(tmp_path):
    """The lowest-scoring trial is in the entry the optimizer reads, summary or fallback."""
    fail = "FAIL-SIGNAL: the review missed the misfiled initiative. " + "detail " * 300
    good = "the review flagged the item correctly. " + "detail " * 300
    pt = {"task_id": "t0", "reward": 0.5, "feedback": join([(0, 0.0, fail), (1, 1.0, good), (2, 1.0, good)])}
    # 1) no optimizer: the deterministic fallback leads with the lowest trial
    body = fd.fit([pt], 1500).entries["t0"]
    assert body.startswith("trials: trial 0 0.000 (lowest), trial 1 1.000, trial 2 1.000")
    assert "lowest (trial 0): FAIL-SIGNAL" in body and _size(body) <= 1500
    # 2) the run's optimizer summarizes; it sees the failing trial with its reward, and even a
    #    summary that only talks about the good trials still gets the code-written header
    rd = _rd(tmp_path)
    calls = []
    body = fd.fit([pt], 1500, run_dir=rd, optimizer=_fake_optimizer("The review is good.", calls)).entries["t0"]
    task_file = calls[0][0]["00.md"]
    assert "## trial 0 - reward 0.000" in task_file and "FAIL-SIGNAL" in task_file
    assert "LOWEST-scoring trial" in calls[0][1]
    assert body.splitlines()[0] == "trials: trial 0 0.000 (lowest), trial 1 1.000, trial 2 1.000"
    assert body.splitlines()[1] == "  The review is good."


def test_the_header_is_bounded_with_many_pooled_trials():
    """Review round 5: 6 pooled round tags x 5 trials gave a header longer than the entry."""
    tags = [f"r00{i}__cand3__rung1_0" for i in range(6)]
    pt = {"task_id": "t0", "reward": 0.4, "feedback": join(
        [(f"{t} {k}", 0.1 * k + (0.0 if t != tags[3] or k else -0.0), f"{t} trial {k} " + "w" * 600)
         for t in tags for k in range(5)])}
    assert _size(fd.header(pt)) > 1000                 # the full line, unbounded
    for limit in (300, 600, 1200):
        got = fd.fit([pt], limit, head=harness._fmt_head)
        e = got.entries["t0"]
        assert _size(e) <= limit, (limit, _size(e))
        assert "lowest" in e.split("\n", 1)[0]
    assert _size(fd.fallback(pt, 400)) <= 400 and fd.fallback(pt, 400).startswith("trials: 30, rewards")


def test_every_entry_is_indented_the_same_way(tmp_path, monkeypatch):
    """Review round 5: a short multi-trial entry put its label lines at column 0, and the link line
    of a condensed one was indented twice."""
    short = {"task_id": "s", "reward": 0.5, "feedback": join([(0, 0.0, "bad"), (1, 1.0, "good")])}
    block = harness._failures_block([], [short], [])
    assert "- s (reward 0.50): [trial 0 reward 0.000]\n  bad\n  \n  [trial 1 reward 1.000]\n  good" in block
    monkeypatch.setenv(fd.ENV_BUDGET, "4000")
    rd = _rd(tmp_path)
    block = harness._failures_block([_pt("a", 0.0), _pt("b", 0.0)], [], [], run_dir=rd)
    links = [ln for ln in block.splitlines() if "(full feedback, every trial:" in ln]
    assert len(links) == 2 and all(ln.startswith("  (full feedback") for ln in links)


def test_short_feedback_is_shown_unchanged(tmp_path):
    rd = _rd(tmp_path)
    pt = {"task_id": "s", "reward": 0.0, "feedback": "expected 42, got 41"}
    block = harness._failures_block([pt], [], [], run_dir=rd)
    assert "- s (reward 0.00): expected 42, got 41" in block and fd.DIR not in block


# ---- the summarizer: the run's optimizer, batched by size, budgeted, concurrent-safe ----

def test_the_summary_uses_the_runs_optimizer_and_counts_its_spend(tmp_path):
    """Same optimizer (its command keys the cache), batches filled by size, spend recorded."""
    rd = _rd(tmp_path)
    rows = [_pt(f"t{i}", 0.0) for i in range(23)]
    calls = []
    opt = _fake_optimizer(lambda i: f"summary of {i}", calls, cost={"cost_usd": 0.25, "tokens": 1000})
    got = fd.fit(rows, fd.budget_bytes(), run_dir=rd, optimizer=opt)
    expected = fd.batches(rows, fd.budget_bytes())
    assert len(expected) > 1 and len(calls) == len(expected)
    assert sorted(len(files) for files, _ in calls) == sorted(len(b) for b in expected)
    assert all(sum(_size(r["feedback"]) for r in b) <= fd.budget_bytes() for b in expected)
    assert got.condensed == 23 and all(got.entries[f"t{i}"].startswith(f"summary of t{i}\n") for i in range(23))
    spent = rd.spent
    assert spent.optimizer_usd == pytest.approx(0.25 * len(expected))
    assert spent.optimizer_tokens == 1000 * len(expected)
    ev = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    s = [e for e in ev if e["kind"] == "feedback_summary"][-1]
    assert s["optimizer"] == "fake-optimizer --model m1" and s["summarized"] == 23
    assert s["calls"] == len(expected)
    # the cache is keyed by the optimizer command: same command = no new call, another = new calls
    fd.fit(rows, fd.budget_bytes(), run_dir=rd, optimizer=opt)
    assert len(calls) == len(expected)
    other = _fake_optimizer("x", calls)
    other.command = "fake-optimizer --model m2"
    fd.fit(rows, fd.budget_bytes(), run_dir=rd, optimizer=other)
    assert len(calls) == 2 * len(expected)
    assert not list((rd.root / "work").glob("feedback_summary_*"))   # scratch removed


def test_summarizer_failure_falls_back_and_is_logged(tmp_path):
    rd = _rd(tmp_path)
    rows = [_pt(f"t{i}", 0.0) for i in range(23)]
    calls = []
    err = RuntimeError("optimizer failed (1): rate limited")
    err.cost = {"cost_usd": 0.1, "tokens": 50}
    got = fd.fit(rows, fd.budget_bytes(), run_dir=rd, optimizer=_fake_optimizer(calls=calls, fail=err))
    n = len(fd.batches(rows, fd.budget_bytes()))
    assert len(calls) == n
    assert got.condensed == 23 and all(TAIL in v for v in got.entries.values())
    assert rd.spent.optimizer_usd == pytest.approx(0.1 * n)   # a failed call is still paid
    ev = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    s = [e for e in ev if e["kind"] == "feedback_summary"][-1]
    assert s["fallback"] == 23 and s["summarized"] == 0 and "rate limited" in s["errors"][0]
    # an optimizer that writes no summaries.json is a fallback too, not a crash
    lazy = lambda wd, p: None
    lazy.command = "lazy"
    assert all(TAIL in v for v in fd.fit(rows[:12], 8000, run_dir=rd, optimizer=lazy).entries.values())


def test_the_summary_can_be_switched_off(tmp_path, monkeypatch):
    rd = _rd(tmp_path)
    calls = []
    monkeypatch.setenv("CAPEVOLVE_FEEDBACK_SUMMARY", "off")
    got = fd.fit([_pt("a", 0.0)], 1000, run_dir=rd, optimizer=_fake_optimizer("s", calls))
    assert calls == [] and TAIL in got.entries["a"]


def test_summary_calls_use_the_runs_workers_setting(tmp_path, monkeypatch):
    rd = _rd(tmp_path)
    live, peak, lock = [0], [0], threading.Lock()

    def opt(workdir, prompt):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
    opt.command = "slow"
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": "v" * 30_000} for i in range(8)]  # 1 per batch
    monkeypatch.setenv("CAPEVOLVE_WORKERS", "3")
    fd.fit(rows, 8000, run_dir=rd, optimizer=opt)
    assert peak[0] == 3
    monkeypatch.setenv("CAPEVOLVE_WORKERS", "1")
    peak[0] = 0
    fd.fit([dict(r, feedback=r["feedback"] + "!") for r in rows], 8000, run_dir=rd, optimizer=opt)
    assert peak[0] == 1


def test_no_summary_call_without_room_in_the_usd_budget(tmp_path, monkeypatch):
    """Review round 5: summaries started even when the optimizer USD cap had no room for them."""
    monkeypatch.setenv("CAPEVOLVE_WORKERS", "4")
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": f"t{i} " + "v" * 30_000} for i in range(8)]
    # no room at all: no call, the fallback for every entry
    rd = _rd(tmp_path / "a", max_optimizer_usd=1.0)
    rd.update_spent(optimizer_usd=1.0)
    calls = []
    got = fd.fit(rows, 8000, run_dir=rd, optimizer=_fake_optimizer("s", calls, cost={"cost_usd": 0.3}))
    assert calls == [] and got.condensed == 8
    s = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()
         if json.loads(ln)["kind"] == "feedback_summary"][-1]
    assert s["skipped_for_budget"] == 8 and s["calls"] == 0
    # room for about 3 calls at $0.30: one probe call, then only as many as the headroom pays for
    rd = _rd(tmp_path / "b", max_optimizer_usd=1.0)
    calls = []
    fd.fit(rows, 8000, run_dir=rd, optimizer=_fake_optimizer("s", calls, cost={"cost_usd": 0.3}))
    assert len(calls) == 3 and rd.spent.optimizer_usd <= 1.0
    # no USD cap: every batch is summarized
    rd = _rd(tmp_path / "c")
    calls = []
    fd.fit(rows, 8000, run_dir=rd, optimizer=_fake_optimizer("s", calls, cost={"cost_usd": 0.3}))
    assert len(calls) == 8


def test_concurrent_prompt_builders_never_share_scratch_or_lose_cached_summaries(tmp_path):
    """Review round 5: a millisecond scratch name and an unlocked cache write."""
    rd = _rd(tmp_path)
    dirs = []

    def opt(workdir, prompt):
        dirs.append(Path(workdir).parent)
        time.sleep(0.05)
        ids = re.findall(r"^- tasks/\S+ -> (\S+)$", prompt, re.M)
        (Path(workdir) / "summaries.json").write_text(json.dumps({i: f"s {i}" for i in ids}))
    opt.command = "c"
    groups = [[{"task_id": f"g{g}_{i}", "reward": 0.0, "feedback": f"g{g} {i} " + "u" * 9000}
               for i in range(3)] for g in range(4)]
    ts = [threading.Thread(target=fd.fit, args=(rows, 2000), kwargs={"run_dir": rd, "optimizer": opt})
          for rows in groups]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(set(dirs)) == 4                       # one scratch dir per prompt builder
    cache = json.loads((rd.root / "feedback_summaries.json").read_text())
    assert len([k for k in cache if k != "__meta__"]) == 12   # nobody's paid-for summaries were lost


# ---- the full text reaches every optimizer (item 12) --------------------------------------

def test_full_feedback_files_reach_the_optimizer_workdir(tmp_path, monkeypatch):
    monkeypatch.setenv(fd.ENV_BUDGET, "4000")
    rd = _rd(tmp_path)
    block = harness._failures_block([_pt("a", 0.0), _pt("b", 0.0)], [], [], run_dir=rd)
    wd = tmp_path / "anywhere" / "wd"            # not under <run>/work/
    wd.mkdir(parents=True)
    assert fd.provide_linked(block, wd, rd) == 2
    for name in fd.LINK_RE.findall(block):
        assert (wd / fd.DIR / name).read_text(encoding="utf-8").count(LONG) == 1
    assert fd.DIR in harness._SNAPSHOT_IGNORE        # never part of a candidate
    assert not hasattr(fd, "copy_linked") and not hasattr(fd, "copy_linked_from")


def _toy():
    example = REPO / "benchmarks" / "toy" / "examples" / "skill"
    spec = importlib.util.spec_from_file_location("toy_skill_adapter_ff", example / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return example, mod.Adapter()


def test_an_in_process_optimizer_gets_the_linked_files_too(tmp_path, monkeypatch):
    """run_step copies the linked files for EVERY OptimizerFn, not only a command-based one."""
    example, adapter = _toy()
    monkeypatch.setenv("CAPEVOLVE_CORE", str(REPO / "core"))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(example))
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(REPO / "skills"))
    from cap_evolve import Budget, RunDir
    seed = tmp_path / "seed_capability"
    shutil.copytree(example / "seed_capability", seed)
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, rd, seed=0, ratios=(0.2, 0.4, 0.4))
    base = harness.baseline(adapter, seed, run_dir=rd)
    monkeypatch.setenv(fd.ENV_BUDGET, "4000")
    instructions = harness._failures_block([_pt("a", 0.0), _pt("b", 0.0)], [], [], run_dir=rd)
    want = sorted(fd.LINK_RE.findall(instructions))
    seen = {}

    def opt(workdir, prompt):                   # an in-process OptimizerFn: no .command
        seen["files"] = sorted(p.name for p in (Path(workdir) / fd.DIR).glob("*.md"))
    harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"), optimizer=opt,
                     instructions=instructions, current_val=base)
    assert len(want) == 2 and seen["files"] == want


# ---- one list of read-context dirs (item 11) ---------------------------------------------

def test_every_skip_list_derives_from_the_one_list_of_read_context_dirs(tmp_path, monkeypatch):
    from cap_evolve import dashboard, types
    assert set(types.NON_CAPABILITY_DIRS) - {".git", "__pycache__"} <= set(harness._SNAPSHOT_IGNORE)
    assert set(types.NON_CAPABILITY_DIRS) <= hc2._SKIP_DIRS
    d = tmp_path / "cand"
    for rel in ("policy/a.md", "feedback_full/x.md", "trajectories/t.json", "prior_iterations/p.md"):
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text("x\n", encoding="utf-8")
    assert set(harness._capability_files(d)) == {"policy/a.md"}
    assert set(dashboard._read_dir_files(d)) == {"policy/a.md"}
    sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))
    import proposer  # noqa: E402
    e = tmp_path / "parent"
    (e / "policy").mkdir(parents=True)
    (e / "policy" / "a.md").write_text("x\n", encoding="utf-8")
    assert proposer.capability_diff_lines(e, d) == 0
    # a new read-context dir needs ONE edit: every site above follows types.NON_CAPABILITY_DIRS
    f = tmp_path / "edited"
    (f / "policy").mkdir(parents=True)
    (f / "policy" / "a.md").write_text("y\n", encoding="utf-8")
    assert proposer.capability_diff_lines(e, f) == 2
    monkeypatch.setattr(types, "NON_CAPABILITY_DIRS", types.NON_CAPABILITY_DIRS | {"policy"})
    monkeypatch.setattr(harness, "NON_CAPABILITY_DIRS", types.NON_CAPABILITY_DIRS)
    monkeypatch.setattr(dashboard, "NON_CAPABILITY_DIRS", types.NON_CAPABILITY_DIRS)
    assert harness._capability_files(d) == {} and dashboard._read_dir_files(d) == {}
    assert proposer.capability_diff_lines(e, f) == 0


# ---- agent-optimize's taskeval (item 1) --------------------------------------------------

_ADAPTER = '''
from contextlib import contextmanager
from cap_evolve import Rollout, Score, Task

class Adapter:
    def tasks(self, split):
        return [Task(id=t, input=t) for t in ("flaky", "solid", "broken")]

    @contextmanager
    def live(self, cand):
        yield cand

    def run_trials(self, tasks, ctx, *, n_trials, base_seed=0):
        out = {}
        for t in tasks:
            rolls = []
            for k in range(n_trials):
                err = "docker pull 429" if (t.id == "broken" and k == 0) else None
                rolls.append(Rollout(task_id=t.id, output=str(k), error=err))
            out[t.id] = rolls
        return out

    def score(self, task, rollout):
        k = int(rollout.output)
        if task.id == "solid":
            return Score(task_id=task.id, reward=1.0, feedback="all good")
        if task.id == "flaky":
            r = 1.0 if k == 2 else 0.0
            return Score(task_id=task.id, reward=r, feedback="JUDGE: passed" if r else f"JUDGE: missed step {k}")
        return Score(task_id=task.id, reward=0.0, feedback="LONG " + "b" * 200000 + " BROKEN-VERDICT")
'''


def test_taskeval_uses_the_cores_feedback_code(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text(_ADAPTER, encoding="utf-8")
    cand = tmp_path / "cand"
    cand.mkdir()
    out = tmp_path / "out.json"
    scripts = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("taskeval_ff", scripts / "taskeval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(sys, "argv", ["taskeval.py", str(cand), "flaky,solid,broken", "--project", str(proj),
                                      "--n", "3", "--json", str(out)])
    with contextlib.redirect_stdout(open(tmp_path / "stdout", "w")):
        assert mod.main() == 0
    per = json.loads(out.read_text())["per_task"]
    flaky = per["flaky"]["feedback"]
    assert "[trial 0 reward 0.000]\n  JUDGE: missed step 0" in flaky
    assert "[trial 2 reward 1.000]\n  JUDGE: passed" in flaky       # labelled, every trial
    assert per["solid"]["feedback"] == ""                            # a task with no failure
    broken = per["broken"]["feedback"]
    assert "BROKEN-VERDICT" in broken and len(broken.encode()) <= fd.budget_bytes()
    assert "trial 0 errored" in broken and "lowest" in broken.split("\n", 1)[0]


# ---- local review of 2f9b6805d -------------------------------------------------------

def test_linked_files_are_written_before_the_integrity_seal(tmp_path, monkeypatch):
    """The framework's own ./feedback_full/ copy must never read as tampering, even when a task
    id matches a protected pattern (``*gold*``)."""
    from cap_evolve import Budget, RunDir, integrity
    example, adapter = _toy()
    monkeypatch.setenv("CAPEVOLVE_CORE", str(REPO / "core"))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(example))
    monkeypatch.setenv("CAPEVOLVE_SKILLS_DIR", str(REPO / "skills"))
    seed = tmp_path / "seed_capability"
    shutil.copytree(example / "seed_capability", seed)
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, rd, seed=0, ratios=(0.2, 0.4, 0.4))
    base = harness.baseline(adapter, seed, run_dir=rd)
    monkeypatch.setenv(fd.ENV_BUDGET, "4000")
    instructions = harness._failures_block([_pt("gold_answer_17", 0.0), _pt("b", 0.0)], [], [], run_dir=rd)
    assert any(n.startswith("gold_answer_17") for n in fd.LINK_RE.findall(instructions))
    harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"), optimizer=lambda wd, p: None,
                     instructions=instructions, current_val=base,
                     protected_patterns=integrity.DEFAULT_PATTERNS)
    kinds = [json.loads(ln)["kind"] for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    assert "tamper_detected" not in kinds


def test_pooling_with_one_side_silent_keeps_every_trials_reward(tmp_path):
    """A side with no text still lists its rewards, so the other side's text is never read as
    every trial's, pooled once or twice."""
    from cap_evolve.loop import pool_split_results

    def res(fb, rewards):
        return SplitResult(split="val", reward=sum(rewards) / len(rewards), stderr=0.0, n_tasks=1, n_scored=1,
                           per_task=[{"task_id": "t0", "reward": sum(rewards) / len(rewards),
                                      "trial_rewards": rewards, "feedback": fb}])
    bad = res(join([(0, 0.0, "BAD: wrong tool"), (1, 0.0, "BAD: wrong tool")]), [0.0, 0.0])
    silent = res("", [1.0, 1.0])
    once = pool_split_results(bad, silent)
    fb = once.per_task[0]["feedback"]
    assert "[trial 0 reward 0.000, trial 1 reward 0.000]\nBAD: wrong tool" in fb
    assert f"[trial 0 reward 1.000, trial 1 reward 1.000]\n{fd.NO_FEEDBACK}" in fb
    twice = pool_split_results(once, res(join([(0, 0.0, "OTHER: timeout")]), [0.0])).per_task[0]["feedback"]
    sections = re.split(r"^\[evaluation \d+ of 3\]\n", twice, flags=re.M)[1:]
    assert len(sections) == 3
    (bad_sec,) = [x for x in sections if "BAD: wrong tool" in x]
    assert bad_sec.startswith("[trial 0 reward 0.000, trial 1 reward 0.000]\nBAD")   # not the 1.000 trials
    # no evaluation gave any text: no placeholder text either
    assert pool_split_results(res("", [0.0]), res("", [1.0])).per_task[0]["feedback"] == ""


def test_the_no_feedback_placeholder_never_splits_a_skillopt_cluster():
    p = "timeout calling search tool after retry loop exhausted"
    rows = [{"task_id": "a", "reward": 0.0, "feedback": join([(0, 0.0, ""), (1, 0.0, p)])},
            {"task_id": "b", "reward": 0.0, "feedback": join([(0, 0.0, p), (1, 0.0, "")])},
            {"task_id": "c", "reward": 0.0, "feedback": p}]
    pats = skillopt._failure_patterns(rows)
    assert len(pats) == 1 and pats[0]["n"] == 3, pats


@pytest.mark.parametrize("ch", ["判", "é", "щ", "ש"])
def test_non_ascii_feedback_is_cut_to_its_room_not_to_nothing(ch):
    text = "start " + ch * 3000 + " VERDICT-" + ch * 5
    assert 590 <= fd._size(fd._clip(text, 600)) <= 600
    rows = [{"task_id": f"t{i}", "reward": 0.3, "feedback": join(
        [(k, 0.1 * k, f"{ch * 4000} LOW-{i}-{k}") for k in range(3)])} for i in range(200)]
    got = fd.fit(rows, 48_000, head=harness._fmt_head)
    assert got.used > 0.95 * 48_000                  # the budget is used, not lost
    for pt in got.shown:
        body = got.entries[pt["task_id"]].split("lowest (trial 0): ", 1)[1]
        assert ch in body and f"LOW-{pt['task_id'][1:]}-0" in body


def test_a_cached_summary_is_never_paid_for_twice(tmp_path):
    """A summary longer than its room (bullet lines, over the asked size, non-ASCII) is cut on
    reuse, not requested again."""
    rd = _rd(tmp_path)
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": f"t{i} " + "q" * 20_000} for i in range(10)]
    calls = []
    long_reply = lambda i: "- issue line\n" * 400 + "判" * 300
    for _ in range(3):
        harness._failures_block(rows, [], [], run_dir=rd,
                                optimizer=_fake_optimizer(long_reply, calls, cost={"cost_usd": 0.5}))
    assert len(calls) == len(fd.batches(rows, fd.budget_bytes()))
    assert rd.spent.optimizer_usd == pytest.approx(0.5 * len(calls))


def test_a_judge_line_that_looks_like_a_label_is_kept_as_text():
    fb = "Judge notes:\n[trial 2 of the protocol was cited]\nThe answer FAILED: wrong dosage VERDICT"
    pt = {"task_id": "x", "reward": 0.0, "feedback": fb}
    assert fd.trials_of(pt) == [("", 0.0, fb)]
    assert "VERDICT" in fd.fallback(pt, 300)
    assert fd.label_unlabelled(fb, [0.0, 0.0]).startswith("[trial 0 reward 0.000, trial 1 reward 0.000]\n")
    assert fd.strip_labels(fb) == fb


def test_the_budget_setting_is_clamped_below_the_inline_limit(monkeypatch):
    monkeypatch.setenv(fd.ENV_BUDGET, "200000")
    assert fd.budget_bytes() == fd.MAX_BUDGET
    monkeypatch.setenv(fd.ENV_BUDGET, "10")
    assert fd.budget_bytes() == fd.MIN_BUDGET


def test_the_rest_line_never_takes_the_whole_budget():
    rows = [{"task_id": "task_with_a_long_identifier_" + "x" * 80 + str(i), "reward": 0.0,
             "feedback": "f" * 5000} for i in range(100)]
    got = fd.fit(rows, 2000)
    assert got.used <= 2000 and got.rest and _size(got.rest_line) <= 500
    assert "more failing task(s) not listed" in got.rest_line


def test_fit_is_fast_with_many_rows():
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": "g" * 3000} for i in range(10_000)]
    t0 = time.time()
    fd.fit(rows, 48_000)
    assert time.time() - t0 < 2.0


def test_usd_headroom_counts_what_in_flight_evaluations_reserved(tmp_path):
    rd = _rd(tmp_path, max_usd=1.0)
    rd.reserve_metric_calls(1, label="eval", est_usd=0.75)
    assert fd.usd_headroom(rd) == pytest.approx(0.25)


def test_taskeval_links_name_the_files_where_they_are(tmp_path, monkeypatch):
    from cap_evolve import RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="t")
    proj = tmp_path / "proj"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text(_ADAPTER, encoding="utf-8")
    cand = tmp_path / "cand"
    cand.mkdir()
    out = tmp_path / "out.json"
    scripts = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("taskeval_ff2", scripts / "taskeval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(sys, "argv", ["taskeval.py", str(cand), "broken", "--project", str(proj), "--n", "3",
                                      "--json", str(out), "--run-dir", str(rd.root)])
    monkeypatch.chdir(tmp_path)                       # a cwd with no feedback_full/ in it
    with contextlib.redirect_stdout(open(tmp_path / "stdout", "w")), \
            contextlib.redirect_stderr(open(tmp_path / "stderr", "w")):
        assert mod.main() == 0
    fb = json.loads(out.read_text())["per_task"]["broken"]["feedback"]
    links = re.findall(r"\(full feedback, every trial: (.+)\)", fb)
    assert len(links) == 1 and Path(links[0]).is_absolute() and Path(links[0]).is_file()
    assert "BROKEN-VERDICT" in Path(links[0]).read_text(encoding="utf-8")


# ---- second local review of 509110801 --------------------------------------------------

def test_identical_pooled_evaluations_name_every_trial():
    """Two evaluations with the same words AND rewards are still two evaluations."""
    from cap_evolve.loop import pool_split_results

    def res(rewards):
        fb = join([(k, r, "expected X got Y" if r < 1 else "") for k, r in enumerate(rewards)])
        return SplitResult(split="val", reward=sum(rewards) / len(rewards), stderr=0.0, n_tasks=1, n_scored=1,
                           per_task=[{"task_id": "t0", "reward": sum(rewards) / len(rewards),
                                      "trial_rewards": rewards, "feedback": fb}])
    pt = pool_split_results(res([0.0, 1.0]), res([0.0, 1.0])).per_task[0]
    assert len(fd.trials_of(pt)) == len(pt["trial_rewards"]) == 4
    again = pool_split_results(pool_split_results(res([0.0, 1.0]), res([0.0, 1.0])), res([0.0, 1.0])).per_task[0]
    assert len(fd.trials_of(again)) == len(again["trial_rewards"]) == 6
    assert pool_split_results(_one_task("same"), _one_task("same")).per_task[0]["feedback"] == "same"


def test_a_summary_made_for_a_small_room_is_made_again_for_a_much_larger_one(tmp_path):
    rd = _rd(tmp_path)
    calls = []
    sized = lambda i: None   # replaced below: reply exactly the size the prompt asks for

    def opt(workdir, prompt):
        n = int(re.search(r"at most (\d+) characters", prompt).group(1))
        ids = re.findall(r"^- tasks/\S+ -> (\S+)$", prompt, re.M)
        calls.append(n)
        (Path(workdir) / "summaries.json").write_text(json.dumps({i: f"{i} " + "s" * (n - 10) for i in ids}))
    opt.command = "sized"
    rows = [{"task_id": f"t{i}", "reward": 0.0, "feedback": f"t{i} " + "q" * 20_000} for i in range(150)]
    fd.fit(rows, 48_000, run_dir=rd, optimizer=opt)              # a small room per task
    n_small = len(calls)
    big = fd.fit(rows[:4], 24_000, run_dir=rd, optimizer=opt)    # 4 of them, a large room each
    assert len(calls) > n_small                                  # made again, for the larger room
    assert all(_size(e) > 0.8 * big.cut for e in big.entries.values()), [_size(e) for e in big.entries.values()]
    n_big = len(calls)
    fd.fit(rows[:4], 24_000, run_dir=rd, optimizer=opt)          # the same room again: reused
    assert len(calls) == n_big


@pytest.mark.parametrize("reply", [None, 5, ["a"], "", "   "])
def test_a_summary_that_is_not_text_falls_back_and_is_not_cached(tmp_path, reply):
    rd = _rd(tmp_path)
    pt = {"task_id": "t0", "reward": 0.5, "feedback": join([(0, 0.0, "FAIL: " + "x" * 5000 + " LOW-VERDICT"),
                                                            (1, 1.0, "good " + "y" * 5000)])}
    got = fd.fit([pt], 1500, run_dir=rd, optimizer=_fake_optimizer(reply))
    assert "LOW-VERDICT" in got.entries["t0"] and "None" not in got.entries["t0"]
    cache = json.loads((rd.root / "feedback_summaries.json").read_text()) \
        if (rd.root / "feedback_summaries.json").exists() else {}
    assert [k for k in cache if k != "__meta__"] == []


def test_a_corrupt_cache_never_breaks_a_prompt_build(tmp_path):
    rd = _rd(tmp_path)
    pt = _pt("t0", 0.0)
    calls = []
    opt = _fake_optimizer("ok summary", calls)
    fd.fit([pt], 1500, run_dir=rd, optimizer=opt)
    cache = json.loads((rd.root / "feedback_summaries.json").read_text())
    for k in [k for k in cache if k != "__meta__"]:
        cache[k] = {"text": {"not": "text"}}
    cache["__meta__"] = "garbage"
    (rd.root / "feedback_summaries.json").write_text(json.dumps(cache))
    got = fd.fit([pt], 1500, run_dir=rd, optimizer=opt)           # no crash; made again
    assert got.entries["t0"].startswith("ok summary") and len(calls) == 2


def test_a_summarizer_that_keeps_failing_is_stopped(tmp_path):
    rd = _rd(tmp_path)
    calls = []
    opt = _fake_optimizer(calls=calls, fail=RuntimeError("down"))
    for i in range(fd.FAILED_BUILDS_LIMIT + 3):
        rows = [{"task_id": f"b{i}", "reward": 0.0, "feedback": f"b{i} " + "x" * 5000 + " VERDICT"}]
        got = fd.fit(rows, 1000, run_dir=rd, optimizer=opt)
        assert "VERDICT" in got.entries[f"b{i}"]                  # the cut, every time
    assert len(calls) == fd.FAILED_BUILDS_LIMIT
    ev = [json.loads(ln) for ln in (rd.root / "events.jsonl").read_text().splitlines()]
    assert any(e.get("summarizer_disabled") for e in ev if e["kind"] == "feedback_summary")


def test_the_known_call_cost_stops_a_probe_call_the_budget_cannot_pay_for(tmp_path):
    """Build 1 learns that a call costs $0.40; build 2, with $0.20 left, makes no call."""
    rd = _rd(tmp_path, max_usd=1.0)
    calls = []
    opt = _fake_optimizer("s", calls, cost={"cost_usd": 0.4})
    rows = lambda g: [{"task_id": f"{g}{i}", "reward": 0.0, "feedback": f"{g}{i} " + "v" * 30_000} for i in range(4)]
    fd.fit(rows("a"), 8000, run_dir=rd, optimizer=opt)
    assert len(calls) == 2 and rd.spent.optimizer_usd == pytest.approx(0.8)
    fd.fit(rows("b"), 8000, run_dir=rd, optimizer=opt)
    assert len(calls) == 2 and rd.spent.optimizer_usd <= 1.0


def test_the_fallback_gives_the_best_trial_what_the_lowest_does_not_use():
    pt = {"task_id": "t0", "reward": 0.5,
          "feedback": join([(0, 0.0, "short low VERDICT"), (1, 1.0, "best " + "b" * 5000 + " BEST-END")])}
    body = fd.fallback(pt, 2000)
    assert "short low VERDICT" in body and "BEST-END" in body and _rendered_size_ok(body, 2000)


def _rendered_size_ok(body, n):
    return 0.9 * n <= fd._rendered_size(body) <= n
