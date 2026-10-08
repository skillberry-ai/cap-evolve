#!/usr/bin/env python3
"""Emit `task:trials-needed` for every e3 task short of five CLEAN trials.

Clean means the agent's own final event says success -- see audit_trials.py.
Trials the gateway killed are not counted, so re-running works as a top-up:
each pass only asks for the shortfall, and a task already at five is skipped.

Discrepancy tasks come first, so a pass that gets cut short still spends its
time on the rows that decide the T1-vs-George comparison rather than on tasks
whose e1/e2 values already agree inside the noise floor.

    python3 scripts/h4_t1_e3/build_queue.py > /tmp/queue.txt
"""
from __future__ import annotations
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_trials import final_event  # noqa: E402
from scaffold_projects import TASK_IDS  # noqa: E402

#: Tasks where e3 disagrees with e1/e2 or with George's reference, hence the
#: ones worth measuring first.
PRIORITY = [
    "icinga-046-services-search-cross-host",
    "icinga-048-comment-service-vs-host-scope",
    "icinga-049-downtime-already-expired",
    "platform-036-secret-redacted-not-absent",
    "icinga-047-downtime-similar-host-names",
    "platform-039-catalog-miss-pr-fallback",
    "platform-043-multiworkshop-asset-failure",
    "platform-044-search-catalog-env-type",
    "cost-050-org-wide-aggregate-doubling",
    "cost-053-capacity-dropped-reservations",
    "platform-035-aap2-cross-controller-job-search",
    "cloud-060-marketplace-usd-not-enriched",
    "062-provisioning-job-trace",
]
TRIALS = 5


def clean_count(task: str) -> int:
    n = 0
    for run in sorted(glob.glob(f".capevolve/h4_t1_e3_{task}/run_*")):
        if not os.path.exists(run + "/baseline.json"):
            continue
        for f in glob.glob(run + "/rollouts/val/*.json"):
            ro = (json.load(open(f)).get("rollout") or {})
            md = ro.get("metadata") or {}
            rj = (md.get("trial_result") or {}).get("reward_json") or {}
            if isinstance(rj, str):
                try: rj = json.loads(rj)
                except ValueError: rj = {}
            if ro.get("error") or not (isinstance(rj, dict) and rj.get("reward") is not None):
                continue
            ev = final_event(md.get("trial_dir") or "")
            if ev is not None and ev.get("subtype") == "success" and not ev.get("is_error"):
                n += 1
    return n


def main() -> int:
    order = ([t for t in PRIORITY if t in TASK_IDS]
             + [t for t in TASK_IDS if t not in PRIORITY])
    short = 0
    for t in order:
        need = TRIALS - clean_count(t)
        if need > 0:
            print(f"{t}:{need}")
            short += need
    print(f"# {short} trials short of {TRIALS * len(TASK_IDS)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
