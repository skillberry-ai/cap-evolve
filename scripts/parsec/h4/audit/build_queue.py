#!/usr/bin/env python3
"""Emit `task:trials-needed` for every task of a given arm short of 5 CLEAN trials.

Clean means the agent's own final event says success -- see audit_trials.py.
Trials the gateway killed are not counted, so re-running works as a top-up:
each pass only asks for the shortfall, and a task already at five is skipped.

Discrepancy tasks come first, so a pass that gets cut short still spends its
time on the rows that decide the T1-vs-George comparison rather than on tasks
whose e1/e2 values already agree inside the noise floor. Those PRIORITY ids
come from the original h4_t1 (George-matching) work; they're kept as-is since
they're still the tasks worth seeing first for h4_g2_e3 too.

Adapted from the original hand-off-from-mac-20261008/build_queue.py: that
version imported TASK_IDS from a scaffold_projects.py that was never copied
across (it encoded Mac-local paths) and hardcoded the h4_t1_e3_ prefix. Both
are parameterized here instead -- PREFIX below, and TASK_IDS is now the
literal 30-id list (confirmed via `ls h4_2026_10_06/bench-v4-*`), since no
scaffold_projects.py for the h4 held-out set exists anywhere to import from.

    python3 scripts/parsec/h4/audit/build_queue.py > /tmp/queue.txt
"""
from __future__ import annotations
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_trials import final_event  # noqa: E402

PREFIX = "h4_g2_e3"

#: The 30 h4_2026_10_06 held-out task ids.
TASK_IDS = [
    "061-capacity-manager-unused-cost-owner-lookup",
    "062-provisioning-job-trace",
    "063-babylon-namespace-missing-for-account",
    "064-reservation-release-active-job-check",
    "cloud-055-azure-subscription-not-found",
    "cloud-056-gcp-delete-in-progress-not-requested",
    "cloud-057-cloudtrail-select-only-refusal",
    "cloud-058-malformed-account-id",
    "cloud-059-blank-owner-email-fallback",
    "cloud-060-marketplace-usd-not-enriched",
    "cost-050-org-wide-aggregate-doubling",
    "cost-051-gcp-net-of-credits",
    "cost-052-azure-empty-cache-no-filter",
    "cost-053-capacity-dropped-reservations",
    "cost-054-monitor-no-dashboard-link",
    "icinga-045-hosts-search-filter",
    "icinga-046-services-search-cross-host",
    "icinga-047-downtime-similar-host-names",
    "icinga-048-comment-service-vs-host-scope",
    "icinga-049-downtime-already-expired",
    "platform-035-aap2-cross-controller-job-search",
    "platform-036-secret-redacted-not-absent",
    "platform-037-ocpv-healthy-vm-degraded-machineset",
    "platform-038-anarchy-subject-guid-cross-cluster",
    "platform-039-catalog-miss-pr-fallback",
    "platform-040-workshop-cross-cluster-name-search",
    "platform-041-resource-pool-unfiltered-list",
    "platform-042-deployment-via-resource-claim",
    "platform-043-multiworkshop-asset-failure",
    "platform-044-search-catalog-env-type",
]

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
    for run in sorted(glob.glob(f".capevolve/{PREFIX}_{task}/run_*")):
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
