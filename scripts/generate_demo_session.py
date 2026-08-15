#!/usr/bin/env python3
"""Regenerate ``core/cap_evolve/demo_session/`` — the keyless UI demo.

ILLUSTRATIVE SAMPLE. Every number below is hand-authored so ``cap-evolve replay
--demo`` can show the live UI with no API key and no spend. It is NOT a benchmark
result and must never be presented as one: the banner ``cap_evolve.tui.DEMO_BANNER``
says so, and so does the header of the generated ``events.jsonl``.

Byte-stable by construction: the timeline is built off ``_T0`` (a fixed epoch), so
regenerating produces an identical file. The event kinds and field names are imported
from / mirrored on the real producers (``cap_evolve.harness``, ``cap_evolve.rundir``)
and asserted against ``eventstream``'s renderer at the end, so the recording cannot
drift away from what the TUI actually consumes.

Usage:  python scripts/generate_demo_session.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "core"))

OUT = REPO / "core" / "cap_evolve" / "demo_session"

_HEADER = ("ILLUSTRATIVE SAMPLE — synthetic cap-evolve run used to replay the terminal "
           "UI with no API key. Not a benchmark result; makes no benchmark claim. "
           "Regenerate with scripts/generate_demo_session.py")

#: Fixed base epoch (2026-03-02T10:00:00Z) — no time.time(), so output is byte-stable.
_T0 = 1772445600.0

TASKS = ["invoice-totals", "pivot-refresh", "merged-cells", "date-coercion",
         "formula-audit", "chart-range"]

# (candidate, parent, val, accept, seconds, reason, extra events before the step)
ITERS = [
    ("cand_0001", "seed", 0.5000, True,
     "paired Δ̄=+0.1667 > 0.2·SE=0.0272 (SE=0.1361, n=6)"),
    ("cand_0002", "cand_0001", 0.4167, False,
     "paired Δ̄=-0.0833 <= 0.2·SE=0.0248 (SE=0.1242, n=6)"),
    ("cand_0003", "cand_0001", 0.6667, True,
     "paired Δ̄=+0.1667 > 0.2·SE=0.0236 (SE=0.1178, n=6)"),
    ("cand_0004", "cand_0003", 0.6667, False,
     # Kept under ~62 chars so it renders in FULL on one lineage row rather than being
     # ellipsized. This is the one reason string a reader most needs whole: it is what
     # distinguishes "we could not measure this" from "we measured it and it lost", and a
     # row that trails off at "— no …" teaches the opposite of the point.
     "indecisive: Δ̄=0 within noise (SE=0.105, n=6) — not a reject"),
    ("cand_0005", "cand_0003", 0.7500, True,
     "paired Δ̄=+0.0833 > 0.2·SE=0.0192 (SE=0.0962, n=6)"),
    ("cand_0006", "cand_0005", 0.5833, False,
     "paired Δ̄=-0.1667 <= 0.2·SE=0.0215 (SE=0.1077, n=6)"),
    ("cand_0007", "cand_0005", 0.8333, True,
     "paired Δ̄=+0.0833 > 0.2·SE=0.0167 (SE=0.0833, n=6)"),
]

_BASE_VAL = 0.3333333333333333

#: Trials per task. TWO, not three, because every per-task table below must average
#: EXACTLY to the val reward its ``evaluate`` event reports (0.4167 = 2.5/6 needs a half),
#: and a fixture whose per-task rows contradict its own means is not an honest fixture.
_N_TRIALS = 2

#: Per-task val reward per candidate. Each row's mean is exactly the val number the
#: matching ``evaluate``/``step`` event reports — see the assertion in :func:`main`.
#: cand_0004 deliberately has the SAME mean as its parent with the mass moved between
#: tasks: that is what "indecisive — no evidence either way" looks like per task.
PER_TASK_VAL = {
    "seed":      [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],   # 0.3333
    "cand_0001": [1.0, 0.5, 0.0, 1.0, 0.5, 0.0],   # 0.5000
    "cand_0002": [1.0, 0.5, 0.0, 1.0, 0.0, 0.0],   # 0.4167
    "cand_0003": [1.0, 1.0, 0.5, 1.0, 0.5, 0.0],   # 0.6667
    "cand_0004": [1.0, 1.0, 0.0, 1.0, 1.0, 0.0],   # 0.6667 — same mean, mass moved
    "cand_0005": [1.0, 1.0, 0.5, 1.0, 1.0, 0.0],   # 0.7500
    "cand_0006": [1.0, 1.0, 0.0, 1.0, 0.5, 0.0],   # 0.5833
    "cand_0007": [1.0, 1.0, 1.0, 1.0, 1.0, 0.0],   # 0.8333
}

_FB_PASS = "Task fully solved (all verifier tests passed; reward 1.0)."
_FB_FAIL = "Wrong total in the summary row; the merged header was skipped."
_FB_FLAKY = "Passed on one trial and failed on the other — unstable on this task."


def _feedback(r: float) -> str:
    return _FB_PASS if r >= 1.0 else (_FB_FAIL if r <= 0.0 else _FB_FLAKY)


def _trial_rewards(r: float) -> list[float]:
    """``_N_TRIALS`` trial outcomes whose mean is ``r`` (a half means one of each)."""
    if r >= 1.0 or r <= 0.0:
        return [r] * _N_TRIALS
    return [1.0, 0.0]


def _per_task(rewards):
    """A SplitResult-shaped ``per_task`` list (see harness.SplitResult.to_dict)."""
    return [{"task_id": t, "reward": r, "n": _N_TRIALS, "stderr": 0.0,
             "feedback": _feedback(r), "trial_rewards": _trial_rewards(r)}
            for t, r in zip(TASKS, rewards)]


def _pass_k(rewards) -> dict:
    """pass^1 / pass^2 computed from the trials, not asserted by hand.

    pass^k here is "solved on at least one of k trials", which for this fixture's
    two-trial tables is the fraction of tasks with any passing trial.
    """
    n = len(rewards) or 1
    return {"1": sum(rewards) / n,
            "2": sum(1 for r in rewards if max(_trial_rewards(r)) > 0) / n}


def _rollout_files(tag: str, rewards, split: str = "val") -> dict[str, str]:
    """``{relative path: json text}`` — one file per (task, trial), as harness writes them.

    This is the ONLY source the reducer has for a candidate's per-task rewards
    (``dashboard._per_task_from_rollouts``), so without these files the per-task heatmap
    can show the seed row (which comes from ``baseline.json``) and nothing else.
    """
    out: dict[str, str] = {}
    for task, r in zip(TASKS, rewards):
        for k, tr in enumerate(_trial_rewards(r)):
            rec = {"input": f"illustrative sample task {task} (no model was called)",
                   "rollout": {"output": "", "seconds": 0.0, "error": ""},
                   "score": {"task_id": task, "reward": tr, "feedback": _feedback(r),
                             "metrics": [], "raw": {}}}
            out[f"rollouts/{split}/{task}__{tag}__t{k}.json"] = json.dumps(rec, indent=1)
    return out


def build() -> tuple[list[dict], dict, dict]:
    ev: list[dict] = []
    t = _T0

    def add(kind: str, **fields):
        ev.append({"t": round(t, 3), "kind": kind, **fields})

    # Provenance, exactly as `cap-evolve run` records it: which spec/project/algorithm
    # produced this run. The live header reads it back, so the demo shows the field a
    # real operator uses to catch "--project X silently read Y's capevolve.yaml".
    # A ~/ path, deliberately: this fixture is illustrative, and an `examples/...` path would
    # read as a real directory in THIS repo. There is no examples/spreadsheet-agent, so a
    # viewer who went looking would find nothing -- and the provenance line exists precisely
    # to be trusted about which spec produced a run.
    add("run_config", spec="~/projects/spreadsheet-agent/capevolve.yaml",
        project="~/projects/spreadsheet-agent",
        algorithm="hill-climb", optimizer="claude-code",
        orchestration_mode="deterministic")
    add("splits", train=8, val=6, test=6, seed=0)
    t += 2.0
    add("target_profile", model="demo-runner-8b", tier="small",
        resolution_note="illustrative sample — no model was called")
    t += 118.0
    add("evaluate", split="val", tag="seed", reward=_BASE_VAL, stderr=0.1925,
        cost_usd=0.0180, tokens=14200, seconds=118.4)
    add("baseline", val=_BASE_VAL, stderr=0.1925)

    parent_val = {"seed": _BASE_VAL}
    for i, (cid, parent, val, accept, reason) in enumerate(ITERS, start=1):
        opt_secs = 42.0 + 6.0 * i
        run_secs = 95.0 + 11.0 * i
        t += opt_secs
        if cid == "cand_0004":
            # A real, common failure mode: the optimizer CLI died mid-iteration, the
            # retry produced an edit, and the gate came back indecisive.
            add("optimizer_error", candidate=cid,
                error="claude: transient 529 overloaded_error (retrying once)")
        t += run_secs
        add("evaluate", split="val", tag=cid, reward=val, stderr=0.1178 - 0.004 * i,
            cost_usd=0.0165 + 0.0004 * i, tokens=13100 + 220 * i, seconds=run_secs)
        if cid == "cand_0006":
            add("gate_warning", mode="paired",
                reason=("combined/paired SE is small relative to Δ — the significance gate "
                        "is near its resolution limit; increase n_trials for more power"),
                context="n=6")
        add("step", candidate=cid, accept=accept, reason=reason, val=val,
            parent=parent, parent_val=parent_val[parent],
            optimizer_seconds=opt_secs, runner_seconds=run_secs,
            cost_usd=0.0165 + 0.0004 * i, tokens=13100 + 220 * i,
            opt_cost_usd=0.2140 + 0.011 * i, opt_tokens=21000 + 900 * i)
        if not accept and "indecisive" in reason:
            add("step_indecisive", candidate=cid, reason=reason, val=val,
                n_scored=6, n_tasks=6)
        parent_val[cid] = val
        if i == 5:
            add("budget_warning", pct=80, metric="max_optimizer_usd",
                spent=1.62, limit=2.00)

    best_id = "cand_0007"
    t += 130.0
    add("evaluate", split="test", tag="FINAL", reward=0.8333333333333333, stderr=0.1667,
        cost_usd=0.0191, tokens=15050, seconds=130.2)
    t += 126.0
    add("evaluate", split="test", tag="FINAL_seed", reward=0.5, stderr=0.2236,
        cost_usd=0.0188, tokens=14800, seconds=126.5)
    add("finalize", test_reward=0.8333333333333333, test_baseline_reward=0.5,
        test_delta=0.333333, best_id=best_id)

    baseline = {"val": {"split": "val", "reward": _BASE_VAL, "stderr": 0.1925,
                        "pass_k": _pass_k(PER_TASK_VAL["seed"]),
                        "per_task": _per_task(PER_TASK_VAL["seed"]),
                        "cost_usd": 0.0180, "tokens": 14200, "seconds": 118.4},
                "best_id": "seed"}
    _TEST_PER_TASK = [1.0, 1.0, 1.0, 1.0, 0.0, 1.0]
    _BASE_TEST_PER_TASK = [1.0, 0.0, 1.0, 1.0, 0.0, 0.0]
    test = {"split": "test", "reward": 0.8333333333333333, "stderr": 0.1667,
            "pass_k": _pass_k(_TEST_PER_TASK),
            "per_task": _per_task(_TEST_PER_TASK),
            "cost_usd": 0.0191, "tokens": 15050, "seconds": 130.2}
    # pass_k recomputed, not inherited: dict(test, reward=0.5) used to keep the WINNER's
    # pass^k next to the seed's reward, which is a fabricated number.
    base_test = dict(test, reward=0.5, stderr=0.2236,
                     pass_k=_pass_k(_BASE_TEST_PER_TASK),
                     per_task=_per_task(_BASE_TEST_PER_TASK),
                     cost_usd=0.0188, tokens=14800, seconds=126.5)
    final = {"test": test, "best_id": best_id, "baseline_id": "seed",
             "test_baseline": base_test, "test_delta": 0.333333}
    return ev, baseline, final


def main() -> int:
    from cap_evolve import eventstream

    ev, baseline, final = build()
    # The recording must stay renderable by the code that consumes it: every event
    # either renders to a line or is deliberate bookkeeping.
    for e in ev:
        line = eventstream.format_event(e, {})
        assert line is not None or e["kind"] in eventstream.BOOKKEEPING_KINDS, e
    # Every per-task table must average EXACTLY to the val number its event reports.
    # A fixture that contradicts itself would teach the reader to distrust the panel.
    means = {"seed": _BASE_VAL, **{cid: val for cid, _p, val, _a, _r in ITERS}}
    for tag, rewards in PER_TASK_VAL.items():
        got = sum(rewards) / len(rewards)
        assert abs(got - means[tag]) < 5e-5, (tag, got, means[tag])
    OUT.mkdir(parents=True, exist_ok=True)
    # Rollouts: the per-candidate per-task rewards the heatmap reads. Written before the
    # JSON summaries so a partial regeneration can never leave a run dir claiming a
    # per-task row it has no rollout for.
    for stale in sorted((OUT / "rollouts").rglob("*.json")):
        stale.unlink()
    for tag, rewards in PER_TASK_VAL.items():
        for rel, text in _rollout_files(tag, rewards).items():
            path = OUT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    body = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in ev)
    (OUT / "events.jsonl").write_text(
        json.dumps({"kind": "log_note", "note": _HEADER}, ensure_ascii=False) + "\n" + body,
        encoding="utf-8")
    (OUT / "baseline.json").write_text(json.dumps(baseline, indent=1), encoding="utf-8")
    (OUT / "final.json").write_text(json.dumps(final, indent=1), encoding="utf-8")
    (OUT / "README.md").write_text(f"# demo_session\n\n{_HEADER}\n", encoding="utf-8")
    print(f"wrote {len(ev)} events → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
