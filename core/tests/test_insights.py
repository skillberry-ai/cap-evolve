"""Durable synthesized priors — INSIGHTS.md (issue #128).

The durable signal is: what HELPED (gate-accepted edits + the tasks they fixed), what
HURT (gate-rejected edits + the tasks they broke, with the reject reason), and what is
still OPEN (the val tasks the current best still fails). It is re-synthesized from
``events.jsonl`` + persisted rollouts every iteration — pure Python, zero LLM calls —
so it survives across iterations independent of the transcript.

The tests here pin the four properties that can silently break:
  1. it reaches the prompt via ``_augment_instructions`` (the ONE function whose output
     the optimizer actually reads, and which all three algorithms route through);
  2. it is built from ``RunDir.iteration_events()``, so it is NON-EMPTY for GEPA — whose
     ``gepa_val_gate`` events a ``kind == "step"`` filter would drop entirely (#199);
  3. it is BOUNDED and evicts by |Δ| on val, so a long run cannot balloon the prompt;
  4. it leaks no ground truth — only val rewards and val task ids, never the sealed test
     split's ids or any gold answer.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _rollout(run_dir, tag, task_id, reward, split="val"):
    d = run_dir.rollouts / split
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{task_id}__{tag}__t0.json").write_text(json.dumps({
        "input": {}, "rollout": {"task_id": task_id},
        "score": {"task_id": task_id, "reward": reward, "feedback": "", "raw": {}},
    }), encoding="utf-8")


def _run(kind, *, n=3):
    """A run dir with n iterations logged under ``kind``, alternating accept/reject.

    ``kind`` is the iteration-event kind an algorithm emits: "step" (hill-climb /
    SkillOpt via run_step) or "gepa_val_gate" (GEPA).
    """
    from cap_evolve import RunDir
    rd = RunDir.create(Path(tempfile.mkdtemp()) / ".capevolve", ts=f"ins_{kind}")
    for tid, r in (("t1", 1.0), ("t2", 0.0), ("t3", 0.0)):
        _rollout(rd, "seed", tid, r)
    prev, prev_val = "seed", 1 / 3
    for i in range(n):
        cid = f"c{i}"
        accept = (i % 2 == 0)
        # Accepted candidates fix t2; rejected ones break t1 (and fix nothing).
        rows = (("t1", 1.0), ("t2", 1.0), ("t3", 0.0)) if accept else \
               (("t1", 0.0), ("t2", 0.0), ("t3", 0.0))
        for tid, r in rows:
            _rollout(rd, cid, tid, r)
        val = sum(r for _, r in rows) / 3
        rd.log_event(kind, candidate=cid, parent=prev, accept=accept, val=val,
                     parent_val=prev_val, reason="ok" if accept else "Δ<=0 on val")
        if accept:
            rd.set_best(cid)
            prev, prev_val = cid, val
    return rd


def test_insights_reach_the_prompt_and_persist_in_the_run_dir():
    """The durable priors must (a) be written to the run dir, (b) be written into the
    optimizer's workdir, and (c) be POINTED AT from the assembled instructions.

    (c) is the part that matters: a file nobody is told to read is not a signal.
    """
    from cap_evolve import harness

    rd = _run("step")
    wd = Path(tempfile.mkdtemp())
    out = harness._augment_instructions("BASE", wd, rd, None, None)

    assert (rd.root / "INSIGHTS.md").exists(), "no durable copy in the run dir"
    body = (wd / "INSIGHTS.md").read_text(encoding="utf-8")
    assert "INSIGHTS.md" in out, "the prompt never points the optimizer at the priors"
    assert "What HELPED" in body and "What HURT" in body and "Still OPEN" in body
    # Honesty: priors are hypotheses, never asserted truth.
    assert "CANDIDATE PRIORS" in body and "gate" in body
    # The synthesized content: the accepted edit's fixed task and the rejected edit's
    # broken task, with the reject reason.
    # c0 (accepted, parent seed) fixed t2; c1 (rejected, parent c0) broke t1 AND t2.
    assert "fixed {t2}" in body and "broke {t1, t2}" in body
    assert "Δ<=0 on val" in body
    # Still-open = the val task the current best does not pass (t3), not t2 (now fixed).
    open_block = body.split("Still OPEN")[1]
    assert "`t3`" in open_block and "`t2`" not in open_block


def test_insights_are_non_empty_for_gepa():
    """GEPA emits ``gepa_val_gate``, not ``step``. Filtering ``kind == "step"`` by hand
    is the bug #199 fixed in three other consumers — this pins that the priors block is
    built from ``RunDir.iteration_events()`` and is therefore populated for GEPA too."""
    from cap_evolve import harness

    for kind in ("step", "gepa_val_gate", "skillopt_step"):
        rd = _run(kind)
        body = harness._build_insights(Path(tempfile.mkdtemp()), rd)
        assert "fixed {t2}" in body, f"priors empty for {kind}"
        assert "nothing accepted yet" not in body, f"priors empty for {kind}"


def test_insights_are_bounded_and_evict_the_smallest_movers():
    """A 60-iteration run must not balloon the prompt. The block stays under its cap and
    keeps the LARGEST |Δ| movers — the ones actually worth re-testing."""
    from cap_evolve import RunDir, harness

    rd = RunDir.create(Path(tempfile.mkdtemp()) / ".capevolve", ts="ins_long")
    _rollout(rd, "seed", "t1", 0.0)
    for i in range(60):
        # Δ grows with i, so the LAST accepted iterations are the big movers and the
        # first ones (Δ ≈ 0.001) are the noise that must be evicted.
        rd.log_event("step", candidate=f"c{i}", parent="seed", accept=(i % 2 == 0),
                     val=0.5 + i * 0.001, parent_val=0.5, reason="r")
    body = harness._build_insights(Path(tempfile.mkdtemp()), rd)

    assert len(body) <= harness.MAX_INSIGHT_CHARS
    assert "`c58`" in body and "`c59`" in body, "biggest movers evicted"
    assert "`c0`" not in body and "`c1`" not in body, "noise-level movers kept"
    # And it must fit comfortably inside one iteration's whole prompt budget.
    from cap_evolve.optimizer_context import MAX_INSTRUCTIONS_CHARS
    assert len(body) < MAX_INSTRUCTIONS_CHARS // 4


def test_insights_never_name_a_test_split_task():
    """The priors are synthesized from VAL rollouts only. A test-split task id (or any
    gold answer) appearing here would leak the sealed split into the optimizer prompt."""
    from cap_evolve import harness

    rd = _run("step")
    # Persist a TEST-split rollout with a distinctive id + a gold answer in its feedback.
    _rollout(rd, "c0", "TESTONLY_task", 1.0, split="test")
    d = rd.rollouts / "test"
    (d / "TESTONLY_task__c0__t0.json").write_text(json.dumps({
        "input": {}, "rollout": {"task_id": "TESTONLY_task"},
        "score": {"task_id": "TESTONLY_task", "reward": 1.0,
                  "feedback": "GOLD_ANSWER_42", "raw": {}},
    }), encoding="utf-8")

    body = harness._build_insights(Path(tempfile.mkdtemp()), rd)
    assert "TESTONLY_task" not in body
    assert "GOLD_ANSWER_42" not in body


def test_insights_first_iteration_is_valid_and_empty():
    """Reduced case: no iterations yet. The block must render (no crash) and say so."""
    from cap_evolve import RunDir, harness

    rd = RunDir.create(Path(tempfile.mkdtemp()) / ".capevolve", ts="ins_empty")
    body = harness._build_insights(Path(tempfile.mkdtemp()), rd)
    assert "nothing accepted yet" in body and "nothing rejected yet" in body


def test_insights_are_not_capability_bytes():
    """INSIGHTS.md is framework read-context, so it must be excluded everywhere a
    candidate is treated as "the capability": the snapshot, GEPA's editable components,
    the eval-cache content hash, and SkillOpt's applied-edit count. Leaving it in any
    one of those makes the priors block look like an optimizer edit."""
    from cap_evolve import harness, skillopt
    from cap_evolve.cache import _IGNORE_NAMES, hash_candidate_dir
    from cap_evolve.gepa import _NON_COMPONENT

    assert "INSIGHTS.md" in harness._SNAPSHOT_IGNORE
    assert "INSIGHTS.md" in _IGNORE_NAMES
    assert "INSIGHTS.md" in _NON_COMPONENT
    assert "INSIGHTS.md" in skillopt._SCAFFOLD

    # The content hash must be blind to it, or every iteration misses the eval cache.
    d = Path(tempfile.mkdtemp())
    (d / "prompt.txt").write_text("hello", encoding="utf-8")
    before = hash_candidate_dir(d)
    (d / "INSIGHTS.md").write_text("priors change every iteration", encoding="utf-8")
    assert hash_candidate_dir(d) == before

    # And SkillOpt must not count it as an applied edit.
    parent = Path(tempfile.mkdtemp())
    (parent / "prompt.txt").write_text("hello", encoding="utf-8")
    assert skillopt._changed_components(parent, d) == 0


def test_iteration_events_dedupe_skillopt_double_logging():
    """SkillOpt logs BOTH ``step`` (via harness.run_step) and its own ``skillopt_step``
    for the SAME candidate, so a raw kind filter yields two rows per iteration — which
    double-counted every SkillOpt iteration in LEDGER.md, RUNMAP.md and the priors, the
    second copy lacking parent/parent_val (blank Δ). Fixed in RunDir.iteration_events,
    so all four consumers get it at once."""
    from cap_evolve import RunDir, harness

    rd = RunDir.create(Path(tempfile.mkdtemp()) / ".capevolve", ts="ins_dedupe")
    rd.log_event("step", candidate="so_1", parent="seed", accept=True, val=1.0,
                 parent_val=0.0, reason="paired Δ̄>0")
    rd.log_event("skillopt_step", candidate="so_1", accept=True, val=1.0,
                 epoch=1, edit_budget=4)

    evs = rd.iteration_events()
    assert len(evs) == 1, f"double-counted: {evs}"
    # First occurrence wins (it has the parent edge + gate reason)…
    assert evs[0]["parent"] == "seed" and evs[0]["reason"] == "paired Δ̄>0"
    # …but the later record's algorithm-specific metadata is merged in, not lost.
    assert evs[0]["epoch"] == 1 and evs[0]["edit_budget"] == 4

    body = harness._build_insights(Path(tempfile.mkdtemp()), rd)
    assert body.count("`so_1`") == 1
