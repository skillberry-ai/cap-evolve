#!/usr/bin/env python3
"""Flag trials that FAILED but were scored anyway.

A trial whose agent is cancelled mid-run still writes a reward.json, so Harbor
books it as a completed trial with reward 0.0 and leaves `errored_trials` at
zero. Averaged in, it is indistinguishable from a task the agent genuinely got
wrong -- which is how 062 came to look like a capability regression.

The authority is the agent's own final event, exactly as the task verifier
reads it (tests/verify.py:55):

    ok = event["subtype"] == "success" and not event["is_error"]

and `expected.json`'s completion gate multiplies the whole reward by zero when
that `ok` is false. So a dead trial is identifiable with certainty, and nothing
has to be inferred from the reward's value.

Do NOT substitute a text search of the transcript for this check. Grepping for
API-layer strings (ReadTimeout, docs.anthropic, "dropped connection") misses a
structured `error_during_execution` result entirely, and its silence then reads
as proof the trial was sound.
"""
from __future__ import annotations
import glob, json, os, sys


def final_event(trial_dir: str) -> dict | None:
    """The agent's last `result` event, or None if it never wrote one."""
    pats = (f"{trial_dir}/*/*/agent/*.jsonl", f"{trial_dir}/*/*/agent.jsonl",
            f"{trial_dir}/*/*/*/agent*.jsonl")
    out = None
    for pat in pats:
        for p in glob.glob(pat):
            for line in open(p, errors="replace"):
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "result":
                    out = ev
    return out


def audit(prefix: str):
    rows = []
    for base in sorted(glob.glob(f".capevolve/{prefix}_*")):
        if not os.path.isdir(base):
            continue
        task = os.path.basename(base)[len(prefix) + 1:]
        for run in sorted(glob.glob(base + "/run_*")):
            if not os.path.exists(run + "/baseline.json"):
                continue
            for f in sorted(glob.glob(run + "/rollouts/val/*.json")):
                ro = (json.load(open(f)).get("rollout") or {})
                md = ro.get("metadata") or {}
                rj = (md.get("trial_result") or {}).get("reward_json") or {}
                if isinstance(rj, str):
                    try: rj = json.loads(rj)
                    except ValueError: rj = {}
                rew = rj.get("reward") if isinstance(rj, dict) else None
                ev = final_event(md.get("trial_dir") or "")
                tag = os.path.basename(f).split("__")[-1].replace(".json", "")
                if ro.get("error"):
                    state = "harness-error"       # already counted by errored_trials
                elif ev is None:
                    state = "no-result-event"     # cannot prove it ran to completion
                elif ev.get("subtype") == "success" and not ev.get("is_error"):
                    state = "ok"
                else:
                    state = f"AGENT-FAILED:{ev.get('subtype')}"
                rows.append((task, os.path.basename(run), tag, rew, state,
                             (ev or {}).get("result")))
    return rows


def main() -> int:
    bad_total = 0
    for prefix in sys.argv[1:] or ["h4_t1_e1", "h4_t1_e2", "h4_t1_e3"]:
        rows = audit(prefix)
        if not rows:
            continue
        bad = [r for r in rows if r[4] != "ok"]
        scored_bad = [r for r in bad if r[3] is not None]
        bad_total += len(scored_bad)
        print(f"{prefix}: {len(rows)} trials, {len(bad)} not-ok, "
              f"{len(scored_bad)} SCORED DESPITE FAILING")
        for task, run, tag, rew, state, msg in bad:
            mark = "  <== counted as a real score" if rew is not None else ""
            print(f"   {task[:40]:<40} {run[:18]} {tag} reward={rew} {state}{mark}")
            if msg:
                print(f"      {str(msg)[:110]}")
        print()
    print(f"TOTAL trials scored despite agent failure: {bad_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
