#!/usr/bin/env python3
"""Build results/v5/v5_t1_e1/results.json from
results/v5/v5_t1_e1/source_v5_t1_e1.json (the vendored, frozen copy of the
intake worktree's own collect.py output).

v5_t1_e1 is a T1 (original, unmodified PARSEC skill) zero-shot baseline sweep
across all 68 tasks of the v5 benchmark -- 5 trials/task, no optimization step.
Structurally this is v4_t4_e1/e2's shape (one eval per task), not v4_t_e1's
(which has seed/candidate/best/final optimization iterations) -- so this
ledger carries no `tranche`/`services`/optimization fields. `category` is
derived from the task id prefix; `origin` and the prior-arm comparison fields
come from the task-provenance mapping below, built by hand-matching v5's 68
task ids against v4's original 34-task set and h4's 30-task held-out set
during this benchmark's setup (see provenance.note for the full caveat).

Usage: python3 scripts/build_v5_t1_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_JSON = ROOT / "results" / "v5" / "v5_t1_e1" / "source_v5_t1_e1.json"
RESULTS_JSON = ROOT / "results" / "v5" / "v5_t1_e1" / "results.json"

TOTAL_TASKS = 68

# v4's original 34-task T1 zero-shot baseline, two independent repeats
# (results/v4/v4_t_e1/cost_time/v4_t4_e1_results_table.md / _e2_). Task ids are
# byte-identical to v5's.
V4_T4_E1 = {
    "cloud-024-guid-to-account": 1.0000, "cloud-026-gpu-abuse-triage": 0.6133,
    "cost-029-no-cost-rows-for-guid": 0.9600, "cost-030-threshold-not-an-anomaly": 0.7200,
    "icinga-010-stuck-anarchysubjects": 0.4390, "icinga-011-aap2-job-status-alert": 1.0000,
    "icinga-013-acknowledged-not-an-issue": 0.6400, "icinga-014-check-script-path-moved": 1.0000,
    "platform-001-ee-entrypoint-rca": 0.7600, "platform-002-collection-not-found-rca": 0.9567,
    "platform-003-tojson-dict-literal-rca": 1.0000, "platform-004-events-then-config": 1.0000,
    "platform-005-wrong-owner-trap": 0.9120, "platform-007-directory-path-fetch": 1.0000,
    "platform-008-log-does-not-say": 1.0000, "platform-022-job-on-no-controller": 1.0000,
    "platform-023-splunk-guid-no-events": 1.0000, "platform-031-helm-url-not-a-timeout": 0.8655,
    "platform-032-shared-secret-not-a-registry-outage": 0.6450,
    "platform-033-schema-change-not-the-oom": 1.0000, "platform-034-rate-limit-not-an-outage": 1.0000,
    "cloud-025-gcp-project-status": 1.0000, "cloud-027-azure-pool-database-trap": 1.0000,
    "cost-028-highest-spend-provider": 0.4000, "icinga-012-nodes-ready-threshold": 1.0000,
    "icinga-015-problems-by-severity": 1.0000, "icinga-016-hosts-most-problems": 1.0000,
    "icinga-017-invented-action-trap": 1.0000, "platform-006-version-tag-not-a-ref": 1.0000,
    "platform-009-catalog-item-no-config": 0.8250, "platform-018-find-jobs-window": 0.0280,
    "platform-019-anarchysubject-state": 0.3200, "platform-020-ocpv-vm-inventory": 0.3400,
    "platform-021-babylon-missing-cluster-trap": 1.0000,
}
V4_T4_E2 = {
    "cloud-024-guid-to-account": 1.0000, "cloud-026-gpu-abuse-triage": 0.9767,
    "cost-029-no-cost-rows-for-guid": 0.6400, "cost-030-threshold-not-an-anomaly": 1.0000,
    "icinga-010-stuck-anarchysubjects": 0.2430, "icinga-011-aap2-job-status-alert": 1.0000,
    "icinga-013-acknowledged-not-an-issue": 0.6400, "icinga-014-check-script-path-moved": 1.0000,
    "platform-001-ee-entrypoint-rca": 0.6960, "platform-002-collection-not-found-rca": 0.6900,
    "platform-003-tojson-dict-literal-rca": 1.0000, "platform-004-events-then-config": 1.0000,
    "platform-005-wrong-owner-trap": 0.7440, "platform-007-directory-path-fetch": 0.5950,
    "platform-008-log-does-not-say": 1.0000, "platform-022-job-on-no-controller": 1.0000,
    "platform-023-splunk-guid-no-events": 0.9600, "platform-031-helm-url-not-a-timeout": 0.9650,
    "platform-032-shared-secret-not-a-registry-outage": 0.7150,
    "platform-033-schema-change-not-the-oom": 1.0000, "platform-034-rate-limit-not-an-outage": 0.9844,
    "cloud-025-gcp-project-status": 1.0000, "cloud-027-azure-pool-database-trap": 1.0000,
    "cost-028-highest-spend-provider": 1.0000, "icinga-012-nodes-ready-threshold": 1.0000,
    "icinga-015-problems-by-severity": 1.0000, "icinga-016-hosts-most-problems": 1.0000,
    "icinga-017-invented-action-trap": 0.9720, "platform-006-version-tag-not-a-ref": 1.0000,
    "platform-009-catalog-item-no-config": 0.7700, "platform-018-find-jobs-window": 0.0280,
    "platform-019-anarchysubject-state": 1.0000, "platform-020-ocpv-vm-inventory": 0.2150,
    "platform-021-babylon-missing-cluster-trap": 1.0000,
}

# h4's 30-task held-out T1 sweep (reports/v4/h4/all-arms-per-trial.md), e1
# (Oct-04 drop) and e3 (Oct-06 drop, harder -- all 5 services declared per
# task). Task ids with no number prefix (061-064) were renumbered with a
# category prefix in v5; H4_ID_REMAP carries that rename.
H4_T1_E1 = {
    "061-capacity-manager-unused-cost-owner-lookup": 0.416, "062-provisioning-job-trace": 0.790,
    "063-babylon-namespace-missing-for-account": 0.300, "064-reservation-release-active-job-check": 0.455,
    "cloud-055-azure-subscription-not-found": 1.000, "cloud-056-gcp-delete-in-progress-not-requested": 0.767,
    "cloud-057-cloudtrail-select-only-refusal": 0.420, "cloud-058-malformed-account-id": 0.700,
    "cloud-059-blank-owner-email-fallback": 0.670, "cloud-060-marketplace-usd-not-enriched": 0.350,
    "cost-050-org-wide-aggregate-doubling": 0.615, "cost-051-gcp-net-of-credits": 0.813,
    "cost-052-azure-empty-cache-no-filter": 0.420, "cost-053-capacity-dropped-reservations": 0.755,
    "cost-054-monitor-no-dashboard-link": 0.513, "icinga-045-hosts-search-filter": 0.475,
    "icinga-046-services-search-cross-host": 0.700, "icinga-047-downtime-similar-host-names": 0.550,
    "icinga-048-comment-service-vs-host-scope": 0.700, "icinga-049-downtime-already-expired": 0.617,
    "platform-035-aap2-cross-controller-job-search": 1.000, "platform-036-secret-redacted-not-absent": 0.150,
    "platform-037-ocpv-healthy-vm-degraded-machineset": 0.767,
    "platform-038-anarchy-subject-guid-cross-cluster": 1.000, "platform-039-catalog-miss-pr-fallback": 0.650,
    "platform-040-workshop-cross-cluster-name-search": 0.965, "platform-041-resource-pool-unfiltered-list": 1.000,
    "platform-042-deployment-via-resource-claim": 0.875, "platform-043-multiworkshop-asset-failure": 1.000,
    "platform-044-search-catalog-env-type": 0.965,
}
H4_T1_E3 = {
    "061-capacity-manager-unused-cost-owner-lookup": 0.546, "062-provisioning-job-trace": 0.607,
    "063-babylon-namespace-missing-for-account": 0.300, "064-reservation-release-active-job-check": 0.413,
    "cloud-055-azure-subscription-not-found": 0.720, "cloud-056-gcp-delete-in-progress-not-requested": 0.767,
    "cloud-057-cloudtrail-select-only-refusal": 0.467, "cloud-058-malformed-account-id": 0.700,
    "cloud-059-blank-owner-email-fallback": 0.575, "cloud-060-marketplace-usd-not-enriched": 0.350,
    "cost-050-org-wide-aggregate-doubling": 0.606, "cost-051-gcp-net-of-credits": 0.767,
    "cost-052-azure-empty-cache-no-filter": 0.408, "cost-053-capacity-dropped-reservations": 0.825,
    "cost-054-monitor-no-dashboard-link": 0.620, "icinga-045-hosts-search-filter": 1.000,
    "icinga-046-services-search-cross-host": 0.583, "icinga-047-downtime-similar-host-names": 0.550,
    "icinga-048-comment-service-vs-host-scope": 0.500, "icinga-049-downtime-already-expired": 0.617,
    "platform-035-aap2-cross-controller-job-search": 1.000, "platform-036-secret-redacted-not-absent": 0.320,
    "platform-037-ocpv-healthy-vm-degraded-machineset": 0.860,
    "platform-038-anarchy-subject-guid-cross-cluster": 1.000, "platform-039-catalog-miss-pr-fallback": 0.475,
    "platform-040-workshop-cross-cluster-name-search": 1.000, "platform-041-resource-pool-unfiltered-list": 1.000,
    "platform-042-deployment-via-resource-claim": 0.875, "platform-043-multiworkshop-asset-failure": 1.000,
    "platform-044-search-catalog-env-type": 0.755,
}
H4_ID_REMAP = {  # h4 id (no category prefix) -> v5 id (renamed with one)
    "062-provisioning-job-trace": "platform-062-provisioning-job-trace",
    "064-reservation-release-active-job-check": "cost-064-reservation-release-active-job-check",
}
# v5 ids that kept their h4/v4 task NUMBER but got different content (confirmed
# via golden.json/seeds/verify.py diff during setup) -- excluded from the
# prior-arm comparison entirely; `origin` is "renamed" and prior_arm* stay null.
RENAMED_DIFFERENT_CONTENT = {"cloud-060-marketplace-cost-not-in-usd", "cost-050-partial-account-coverage"}

CATEGORY_PREFIXES = ("cloud", "cost", "icinga", "platform")


def category_of(task_id):
    for p in CATEGORY_PREFIXES:
        if task_id.startswith(p + "-"):
            return p
    raise ValueError(f"unrecognized category prefix for task id {task_id!r}")


def classify(task_id):
    """-> (origin, prior_arm, prior_arm_mean) for one v5 task id."""
    if task_id in RENAMED_DIFFERENT_CONTENT:
        return "renamed-content-changed", None, None
    if task_id in V4_T4_E1:
        mean = statistics.fmean([V4_T4_E1[task_id], V4_T4_E2[task_id]])
        return "v4-34", "v4_t4_e1/e2", round(mean, 4)
    h4_id = {v: k for k, v in H4_ID_REMAP.items()}.get(task_id, task_id)
    if h4_id in H4_T1_E1:
        mean = statistics.fmean([H4_T1_E1[h4_id], H4_T1_E3[h4_id]])
        return "h4-30", "h4_t1_e1/e3", round(mean, 4)
    return "new", None, None


def headroom_of(reward):
    return "saturated" if reward is not None and reward >= 0.95 else "ok"


def build_task_ledger(source_tasks):
    ledger = []
    for t in sorted(source_tasks, key=lambda x: x["task_id"]):
        task_id = t["task_id"]
        origin, prior_arm, prior_arm_mean = classify(task_id)
        reward = t["reward"]
        delta = round(reward - prior_arm_mean, 4) if prior_arm_mean is not None else None
        ledger.append({
            "task": task_id,
            "category": category_of(task_id),
            "origin": origin,
            "status": t["status"],
            "reward": reward,
            "stderr": t.get("stderr"),
            "trial_rewards": t.get("trial_rewards"),
            "errored_trials": t.get("errored_trials", 0),
            "valid_trials": t.get("valid_trials"),
            "n_trials": t.get("n_trials"),
            "cost_usd": t.get("cost_usd"),
            "tokens": t.get("tokens"),
            "seconds": t.get("seconds"),
            "headroom": headroom_of(reward),
            "report": f"reports/v5/v5_t1_e1/{task_id}.md",
            "prior_arm": prior_arm,
            "prior_arm_mean": prior_arm_mean,
            "delta_vs_prior_arm": delta,
        })
    return ledger


def build_category_summaries(ledger):
    rows = []
    by_cat = {}
    for row in ledger:
        by_cat.setdefault(row["category"], []).append(row)
    for cat in CATEGORY_PREFIXES:
        rows_c = by_cat.get(cat, [])
        if not rows_c:
            continue
        rows.append({
            "category": cat,
            "n_tasks": len(rows_c),
            "reward_mean": round(statistics.fmean(r["reward"] for r in rows_c), 4),
        })
    overall = {
        "category": "overall",
        "n_tasks": len(ledger),
        "reward_mean": round(statistics.fmean(r["reward"] for r in ledger), 4),
    }
    return [overall] + rows


def build_results(source):
    tasks = source["tasks"]
    assert len(tasks) == TOTAL_TASKS, f"expected {TOTAL_TASKS} tasks, got {len(tasks)}"
    assert all(t["status"] == "ok" for t in tasks), "a task is not status=='ok' -- investigate before vendoring"

    ledger = build_task_ledger(tasks)
    assert {r["task"] for r in ledger} == {t["task_id"] for t in tasks}, "ledger/source task id mismatch"

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_v5_t1_results_json.py",
        "benchmark": "parsec",
        "target": (
            "parsec multi-agent bundle (orchestrator.md + 6 domain agents + "
            "shared_context.md; capabilities: [system-prompt]) -- the T1 "
            "(original, unmodified) skill, zero-shot, no optimization step"
        ),
        "total_tasks": TOTAL_TASKS,
        "task_ledger": ledger,
        "sections": {
            "task": {"summaries": build_category_summaries(ledger)},
        },
        "provenance": {
            "source_v5_results": "results/v5/v5_t1_e1/source_v5_t1_e1.json",
            "source_v5_generator": (
                "parsec-intake_v5 worktree, scripts/parsec/v5/collect.py "
                "(gitignored there -- vendored here as a frozen snapshot)"
            ),
            "note": (
                "v5 is a from-scratch, physically isolated rebuild of the v4/h4 "
                "benchmark material (new task copies, renamed bench-v5- prefix, "
                "no shared code or content with any v4/h4 worktree) -- built "
                "this way at the user's explicit request after discovering v4's "
                "own 34-task set and h4's 30-task held-out set each had drifted "
                "from the copies used to build this repo's v4_t4_e1/e2 and "
                "h4_t1_e1/e3 tables. 34 of v5's 68 task ids are byte-identical "
                "to v4's original set, 21 more match an h4 held-out task "
                "(2 of those kept the task NUMBER but got different content, "
                "flagged as origin='renamed-content-changed' and excluded from "
                "the prior-arm comparison), and 11 are new. The seed skill "
                "bundle (artifacts/v5/seed/) is NOT byte-identical to v4's "
                "(artifacts/v4/seed/) -- the shared parsec-live orchestrator "
                "picked up unrelated routing-logic changes between the two "
                "snapshot dates -- so a v5_t1_e1-vs-v4_t4_e1 delta on a "
                "matched task reflects both the model/gateway and this skill "
                "drift, not a controlled A/B."
            ),
            "no_optimizer_stage": (
                "v5_t1_e1 is a zero-shot sweep (5 trials/task, no optimization "
                "iterations) -- there is no seed/candidate/best/final lineage "
                "here, unlike v4_t_e1."
            ),
        },
    }


def main():
    check_only = "--check" in sys.argv
    source = json.loads(SOURCE_JSON.read_text())
    new_results = build_results(source)

    old_text = RESULTS_JSON.read_text() if RESULTS_JSON.exists() else None
    old_results = json.loads(old_text) if old_text else None

    def without_timestamp(d):
        return {k: v for k, v in d.items() if k != "generated_at"}

    if old_results is not None and without_timestamp(old_results) == without_timestamp(new_results):
        print("results/v5/v5_t1_e1/results.json already up to date.")
        return 0
    if check_only:
        print("results/v5/v5_t1_e1/results.json is STALE relative to source_v5_t1_e1.json.", file=sys.stderr)
        return 1

    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(new_results, indent=2) + "\n")
    print(f"Wrote results/v5/v5_t1_e1/results.json ({len(new_results['task_ledger'])} tasks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
