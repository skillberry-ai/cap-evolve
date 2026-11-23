"""Hill-climb's next prompt never showed what the rejected candidate's edit did to the judges.

The prompt's feedback is built from the CURRENT BEST's results, and the best does not change
on a reject — so on the rfe-creator full-v2 run, iterations 1 and 2 got byte-identical
prompts (53,658 chars). The rejected candidate's own judge feedback reached the next
optimizer only as raw trial JSON under ``./prior_iterations/<id>/trajectories/``, which it had
to find and diff by hand. ``_last_reject_block`` puts that feedback in the prompt, task by
task, for every task the reject measurably moved — worse first — inside the same feedback
budget as the failure index.
"""

from __future__ import annotations

from cap_evolve import Budget, RunDir, feedback_digest, harness
from cap_evolve.loop import SplitResult


def _pt(task_id, reward, feedback="", stderr=0.02):
    return {"task_id": task_id, "reward": reward, "stderr": stderr, "n": 3, "feedback": feedback,
            "raw": {"n_trials": 3, "valid_trials": 3}}


BEST = SplitResult.from_dict({"split": "val", "reward": 0.66, "stderr": 0.02, "per_task": [
    _pt("rfe-005", 0.70, "best: WHY 1, calibration slightly generous"),
    _pt("rfe-014", 0.70, "best: ok"),
    _pt("rfe-021", 0.55, "best: no customers named"),
    _pt("init-001", 0.70, "best: fine"),
]})


def _reject_step(cid="cand_0001", accepted=False):
    cand = SplitResult.from_dict({"split": "val", "reward": 0.57, "stderr": 0.03, "per_task": [
        _pt("rfe-005", 0.32, "cand: no run report — the split fan-out timed out"),
        _pt("rfe-014", 0.48, "cand: review re-scored WHY to 0, inconsistent with its notes"),
        _pt("rfe-021", 0.70, "cand: revision restated the gap without fabricating"),
        _pt("init-001", 0.69, "cand: unchanged"),
    ]})
    return {"candidate_id": cid, "accepted": accepted, "candidate_val": cand.to_dict()}


def test_the_block_lists_the_rejects_own_feedback_worse_first():
    text = harness._last_reject_block([_reject_step()], BEST)
    assert "Last rejected candidate `cand_0001`" in text
    worse = text.index("Measurably WORSE")
    better = text.index("Measurably BETTER")
    assert worse < text.index("rfe-005 (best 0.70 → cand_0001 0.32)") < text.index(
        "rfe-014 (best 0.70 → cand_0001 0.48)") < better, text      # worst drop first
    assert "split fan-out timed out" in text and "re-scored WHY to 0" in text
    assert better < text.index("rfe-021 (best 0.55 → cand_0001 0.70)"), text
    assert "revision restated the gap" in text
    assert "no claim either way): init-001" in text                 # 0.01 < 2·SE: named, no text
    assert "cand: unchanged" not in text
    assert "./prior_iterations/cand_0001/" in text


def test_no_block_after_an_accept_or_before_any_step():
    assert harness._last_reject_block([], BEST) == ""
    assert harness._last_reject_block([_reject_step(accepted=True)], BEST) == ""
    assert harness._last_reject_block([{"candidate_id": "c", "accepted": False}], BEST) == ""


def test_the_block_takes_at_most_half_of_the_shared_budget():
    budget = feedback_digest.Budget(total=4000)
    text = harness._last_reject_block([_reject_step()], BEST, budget=budget)
    assert text and 0 < budget.used <= 2000
    tiny = feedback_digest.Budget(total=feedback_digest.MIN_BUDGET)
    harness._last_reject_block([_reject_step()], BEST, budget=tiny)
    assert tiny.used <= feedback_digest.MIN_BUDGET // 2 + 1


class _Splits:
    pooled = True

    def ids(self, split):
        assert split == "feedback"
        return ["rfe-005", "rfe-021", "init-001"]       # rfe-014 is in the sealed confirm stratum


class _PooledRun:
    def read_splits(self):
        return _Splits()


def test_a_pooled_runs_confirm_tasks_never_reach_the_prompt():
    text = harness._last_reject_block([_reject_step()], BEST, run_dir=_PooledRun())
    assert "rfe-005" in text and "rfe-021" in text
    assert "rfe-014" not in text and "re-scored WHY to 0" not in text


def test_hill_climb_puts_the_last_reject_in_the_next_prompt(tmp_path, monkeypatch):
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=6)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=2, stall=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    tid = str(base.per_task[0]["task_id"])
    before = float(base.per_task[0]["reward"])
    after = 0.0 if before > 0.5 else 1.0
    cand = SplitResult.from_dict({**base.to_dict(), "per_task": [
        {**pt, "reward": after, "stderr": 0.0,
         "feedback": "REJECT-ONLY FEEDBACK: the edit removed the worked example"}
        if str(pt["task_id"]) == tid else pt for pt in base.to_dict()["per_task"]]})

    prompts = []

    def fake_step(adapter, *, instructions, **kw):
        prompts.append(instructions)
        return {"candidate_id": f"cand_{len(prompts):04d}", "accepted": False,
                "candidate_val": cand.to_dict()}

    monkeypatch.setattr(harness, "run_step", fake_step)
    harness.hill_climb_loop(adapter, run_dir=run_dir, optimizer=lambda *a, **k: None,
                            current_val=base, focus="all", max_iterations=2,
                            algorithm="hill-climb", capabilities=["system-prompt"])
    assert len(prompts) == 2
    assert "Last rejected candidate" not in prompts[0]
    assert "Last rejected candidate `cand_0001`" in prompts[1], prompts[1][-2000:]
    assert "REJECT-ONLY FEEDBACK: the edit removed the worked example" in prompts[1]


# --- review round 1 (PR #1010): the block obeys the same rules as LEDGER.md ------------------


def test_no_block_when_the_history_ablation_is_off(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_HISTORY", "0")
    assert harness._last_reject_block([_reject_step()], BEST) == ""


class _ValSplits:
    pooled = False

    def ids(self, split):
        return ["rfe-005", "rfe-014", "rfe-021", "init-001"]


class _ValRun:
    def read_splits(self):
        return _ValSplits()


def _one_trial(rows):
    return [{**pt, "n": 1, "stderr": 0.0, "raw": {"n_trials": 1, "valid_trials": 1}} for pt in rows]


def test_under_the_noise_guard_few_trials_make_no_worse_or_better_claim(monkeypatch):
    from cap_evolve import gatecfg

    monkeypatch.setattr(gatecfg.GateConfig, "for_run",
                        classmethod(lambda cls, rd: cls(ledger_noise_guard=True, ledger_min_trials=3)))
    best = SplitResult.from_dict({**BEST.to_dict(), "per_task": _one_trial(BEST.to_dict()["per_task"])})
    step = _reject_step()
    step["candidate_val"]["per_task"] = _one_trial(step["candidate_val"]["per_task"])
    text = harness._last_reject_block([step], best, run_dir=_ValRun())
    assert "Measurably WORSE" not in text and "Measurably BETTER" not in text
    assert "find what the edit broke" not in text
    assert "NO causal claim" in text and "n=1 trial(s) per task" in text
    assert "split fan-out timed out" in text and "init-001 (best 0.70" in text   # still context


def test_the_guard_is_off_by_default_so_three_trials_keep_the_claims(monkeypatch):
    text = harness._last_reject_block([_reject_step()], BEST, run_dir=_ValRun())
    assert "Measurably WORSE than the best (2" in text


def test_an_indecisive_step_is_not_called_rejected():
    step = {**_reject_step(), "decision": {"indecisive": True}}
    text = harness._last_reject_block([step], BEST)
    assert "Last unresolved candidate `cand_0001`" in text
    assert "was not accepted (the measurement could not decide" in text
    assert "was rejected" not in text


class _BrokenRun:
    def read_splits(self):
        raise OSError("splits.json unreadable")


def test_unreadable_splits_drop_the_block_instead_of_showing_every_row():
    assert harness._last_reject_block([_reject_step()], BEST, run_dir=_BrokenRun()) == ""


def test_rows_over_the_budget_point_at_the_rejects_own_trials_and_the_header_is_charged():
    budget = feedback_digest.Budget(total=feedback_digest.MIN_BUDGET)
    text = harness._last_reject_block([_reject_step()], BEST, budget=budget)
    assert budget.used == feedback_digest._size(text)          # every byte of the block charged
    if "more moved task(s) not listed" in text:
        assert "./prior_iterations/cand_0001/trajectories/" in text
        assert "failing task(s)" not in text


def test_skillopt_does_not_call_missing_data_a_regression():
    from cap_evolve import skillopt

    prev = [_pt("a", 0.70, stderr=0.02)]
    errored = {**_pt("a", 0.0, stderr=0.0), "raw": {"n_trials": 3, "valid_trials": 0}}
    cats = skillopt._categorize(prev, [errored])
    assert cats["regressed"] == []
