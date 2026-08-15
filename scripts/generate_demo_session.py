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
     "indecisive: paired Δ̄=+0.0000 within noise (SE=0.1054, n=6) — no evidence either way"),
    ("cand_0005", "cand_0003", 0.7500, True,
     "paired Δ̄=+0.0833 > 0.2·SE=0.0192 (SE=0.0962, n=6)"),
    ("cand_0006", "cand_0005", 0.5833, False,
     "paired Δ̄=-0.1667 <= 0.2·SE=0.0215 (SE=0.1077, n=6)"),
    ("cand_0007", "cand_0005", 0.8333, True,
     "paired Δ̄=+0.0833 > 0.2·SE=0.0167 (SE=0.0833, n=6)"),
]

_BASE_VAL = 0.3333333333333333


def _per_task(rewards):
    """A SplitResult-shaped ``per_task`` list (see harness.SplitResult.to_dict)."""
    return [{"task_id": t, "reward": r, "n": 3, "stderr": 0.0,
             "feedback": ("Task fully solved (all verifier tests passed; reward 1.0)."
                          if r >= 1.0 else
                          "Wrong total in the summary row; the merged header was skipped."),
             "trial_rewards": [r, r, r]}
            for t, r in zip(TASKS, rewards)]


def build() -> tuple[list[dict], dict, dict]:
    ev: list[dict] = []
    t = _T0

    def add(kind: str, **fields):
        ev.append({"t": round(t, 3), "kind": kind, **fields})

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
                        "pass_k": {"1": _BASE_VAL, "2": 0.4444},
                        "per_task": _per_task([1.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
                        "cost_usd": 0.0180, "tokens": 14200, "seconds": 118.4},
                "best_id": "seed"}
    test = {"split": "test", "reward": 0.8333333333333333, "stderr": 0.1667,
            "pass_k": {"1": 0.8333333333333333, "2": 0.8333333333333333},
            "per_task": _per_task([1.0, 1.0, 1.0, 1.0, 0.0, 1.0]),
            "cost_usd": 0.0191, "tokens": 15050, "seconds": 130.2}
    base_test = dict(test, reward=0.5, stderr=0.2236,
                     per_task=_per_task([1.0, 0.0, 1.0, 1.0, 0.0, 0.0]),
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
    OUT.mkdir(parents=True, exist_ok=True)
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
