# v5_t1_e1 vs v4/h4 baselines -- T1 (original skill) comparison

Generated from [`results/v5/v5_t1_e1/results.json`](../results/v5/v5_t1_e1/results.json) (v5, 68 tasks) and the v4/h4 numbers already committed in this repo ([`results/v4/v4_t_e1/cost_time/v4_t4_e1_results_table.md`](../results/v4/v4_t_e1/cost_time/v4_t4_e1_results_table.md) / `v4_t4_e2_results_table.md`, [`reports/v4/h4/all-arms-per-trial.md`](v4/h4/all-arms-per-trial.md)). All arms run the **unmodified, original PARSEC skill (T1)**, 5 trials/task, no optimization.

**Caveat (read before trusting a delta):** task content differs between v4's own 34-task set, h4's 30-task held-out set, and v5's new copies of the "same" tasks (different `golden.json`/seeds/`verify.py` in several cases) -- confirmed during this benchmark's setup, not discovered here. The **seed skill itself also differs** -- `artifacts/v5/seed/` is not byte-identical to `artifacts/v4/seed/` (the shared `orchestrator.md` picked up unrelated routing-logic changes between the two snapshot dates). Every delta below reflects both the model/gateway and this content/skill drift, not a single controlled variable -- read as orientation, not as proof of a behavior change, especially where the single-run noise floor (v4's own e1-vs-e2 repeat: ±0.025; h4's e1-vs-e3: ±0.01) is itself larger than the delta.

## Headline: mean reward by arm

| arm | tasks | mean reward | description |
|---|--:|--:|---|
| `v4_t4_e1` | 34 | 0.8360 | v4 original 34-task set, T1, run 1 ([`results/v4/v4_t_e1/`](../results/v4/v4_t_e1/)) |
| `v4_t4_e2` | 34 | 0.8481 | v4 original 34-task set, T1, run 2 (noise-floor pair) |
| `h4_t1_e1` | 30 | 0.6799 | h4 held-out 30-task set (Oct-04 drop), T1 ([`reports/v4/h4/`](v4/h4/)) |
| `h4_t1_e3` | 30 | 0.6735 | h4 held-out 30-task set (Oct-06 drop, harder), T1 |
| **`v5_t1_e1`** | 68 | **0.8885** | v5 full 68-task set, T1 -- [`results/v5/v5_t1_e1/`](../results/v5/v5_t1_e1/) |

## Matched: the 34 v4-identical tasks

| task | v4_t4_e1/e2 (mean) | v5_t1_e1 | Δ |
|---|--:|--:|--:|
| `cloud-024-guid-to-account` | 1.000 | 1.000 | +0.000 |
| `cloud-025-gcp-project-status` | 1.000 | 0.973 | -0.027 |
| `cloud-026-gpu-abuse-triage` | 0.795 | 1.000 | +0.205 |
| `cloud-027-azure-pool-database-trap` | 1.000 | 1.000 | +0.000 |
| `cost-028-highest-spend-provider` | 0.700 | 1.000 | +0.300 |
| `cost-029-no-cost-rows-for-guid` | 0.800 | 0.880 | +0.080 |
| `cost-030-threshold-not-an-anomaly` | 0.860 | 1.000 | +0.140 |
| `icinga-010-stuck-anarchysubjects` | 0.341 | 0.495 | +0.154 |
| `icinga-011-aap2-job-status-alert` | 1.000 | 1.000 | +0.000 |
| `icinga-012-nodes-ready-threshold` | 1.000 | 1.000 | +0.000 |
| `icinga-013-acknowledged-not-an-issue` | 0.640 | 0.512 | -0.128 |
| `icinga-014-check-script-path-moved` | 1.000 | 0.550 | -0.450 |
| `icinga-015-problems-by-severity` | 1.000 | 1.000 | +0.000 |
| `icinga-016-hosts-most-problems` | 1.000 | 1.000 | +0.000 |
| `icinga-017-invented-action-trap` | 0.986 | 1.000 | +0.014 |
| `platform-001-ee-entrypoint-rca` | 0.728 | 0.884 | +0.156 |
| `platform-002-collection-not-found-rca` | 0.823 | 0.883 | +0.060 |
| `platform-003-tojson-dict-literal-rca` | 1.000 | 0.930 | -0.070 |
| `platform-004-events-then-config` | 1.000 | 1.000 | +0.000 |
| `platform-005-wrong-owner-trap` | 0.828 | 1.000 | +0.172 |
| `platform-006-version-tag-not-a-ref` | 1.000 | 1.000 | +0.000 |
| `platform-007-directory-path-fetch` | 0.797 | 1.000 | +0.203 |
| `platform-008-log-does-not-say` | 1.000 | 0.920 | -0.080 |
| `platform-009-catalog-item-no-config` | 0.797 | 1.000 | +0.203 |
| `platform-018-find-jobs-window` | 0.028 | 1.000 | +0.972 |
| `platform-019-anarchysubject-state` | 0.660 | 1.000 | +0.340 |
| `platform-020-ocpv-vm-inventory` | 0.278 | 1.000 | +0.723 |
| `platform-021-babylon-missing-cluster-trap` | 1.000 | 1.000 | +0.000 |
| `platform-022-job-on-no-controller` | 1.000 | 0.965 | -0.035 |
| `platform-023-splunk-guid-no-events` | 0.980 | 0.960 | -0.020 |
| `platform-031-helm-url-not-a-timeout` | 0.915 | 0.870 | -0.045 |
| `platform-032-shared-secret-not-a-registry-outage` | 0.680 | 1.000 | +0.320 |
| `platform-033-schema-change-not-the-oom` | 1.000 | 0.731 | -0.269 |
| `platform-034-rate-limit-not-an-outage` | 0.992 | 0.785 | -0.207 |
| **MEAN** | **0.842** | **0.922** | **+0.080** |

## Matched: the 21 h4 held-out tasks with usable data in both drops

| task | v5 id (if renamed) | h4_t1_e1/e3 (mean) | v5_t1_e1 | Δ |
|---|---|--:|--:|--:|
| `cloud-055-azure-subscription-not-found` | -- | 0.860 | 1.000 | +0.140 |
| `cloud-057-cloudtrail-select-only-refusal` | -- | 0.444 | 0.440 | -0.004 |
| `cloud-058-malformed-account-id` | -- | 0.700 | 0.600 | -0.100 |
| `cloud-059-blank-owner-email-fallback` | -- | 0.623 | 1.000 | +0.378 |
| `cost-051-gcp-net-of-credits` | -- | 0.790 | 0.968 | +0.178 |
| `cost-053-capacity-dropped-reservations` | -- | 0.790 | 0.904 | +0.114 |
| `cost-054-monitor-no-dashboard-link` | -- | 0.567 | 0.957 | +0.391 |
| `064-reservation-release-active-job-check` | `cost-064-reservation-release-active-job-check` | 0.434 | 0.760 | +0.326 |
| `icinga-045-hosts-search-filter` | -- | 0.738 | 0.960 | +0.223 |
| `icinga-046-services-search-cross-host` | -- | 0.641 | 1.000 | +0.358 |
| `icinga-047-downtime-similar-host-names` | -- | 0.550 | 1.000 | +0.450 |
| `icinga-048-comment-service-vs-host-scope` | -- | 0.600 | 0.975 | +0.375 |
| `platform-036-secret-redacted-not-absent` | -- | 0.235 | 1.000 | +0.765 |
| `platform-037-ocpv-healthy-vm-degraded-machineset` | -- | 0.814 | 1.000 | +0.186 |
| `platform-038-anarchy-subject-guid-cross-cluster` | -- | 1.000 | 1.000 | +0.000 |
| `platform-040-workshop-cross-cluster-name-search` | -- | 0.983 | 0.675 | -0.307 |
| `platform-041-resource-pool-unfiltered-list` | -- | 1.000 | 1.000 | +0.000 |
| `platform-042-deployment-via-resource-claim` | -- | 0.875 | 0.972 | +0.097 |
| `platform-043-multiworkshop-asset-failure` | -- | 1.000 | 1.000 | +0.000 |
| `platform-044-search-catalog-env-type` | -- | 0.860 | 1.000 | +0.140 |
| `062-provisioning-job-trace` | `platform-062-provisioning-job-trace` | 0.699 | 1.000 | +0.301 |
| **MEAN** | | **0.724** | **0.915** | **+0.191** |

**Both matched sets, pooled (55 tasks):** prior arm mean **0.797**, v5_t1_e1 mean **0.919**, Δ **+0.122**.

## Known content-changed tasks (same task number, different content -- not compared directly)

| v5 task id | v5_t1_e1 reward |
|---|--:|
| `cloud-060-marketplace-cost-not-in-usd` | 0.360 |
| `cost-050-partial-account-coverage` | 0.860 |

## New in v5: 11 tasks with no v4 or h4 counterpart

| task | v5_t1_e1 reward | errored trials |
|---|--:|--:|
| `cloud-074-assigned-account-still-billing` | 0.667 | 0 |
| `cost-073-end-exclusive-alert-day` | 1.000 | 0 |
| `cost-075-vm-count-not-in-billing` | 1.000 | 0 |
| `icinga-072-alert-output-not-decoy-metrics` | 0.000 | 0 |
| `platform-065-other-guid-job-not-the-failure` | 0.804 | 0 |
| `platform-066-per-guid-cluster-and-lifespan` | 0.965 | 0 |
| `platform-067-branch-name-not-the-cause` | 1.000 | 0 |
| `platform-068-deprecation-warning-not-the-fatal` | 0.828 | 0 |
| `platform-069-typo-variable-not-located` | 1.000 | 0 |
| `platform-070-invented-fix-variables` | 1.000 | 0 |
| `platform-071-unmonitored-proxy-not-esxi-alert` | 0.383 | 0 |

## Reading this

- v5's full-sweep mean (0.8885) sits above both the v4 34-task mean (~0.84) and the h4 30-task mean (~0.68), but the three sets are not the same tasks and the skill itself drifted between snapshots (see the caveat above) -- not a claim that v5 is an easier benchmark. 13 of the 68 tasks have no usable prior baseline at all.
- On the 34 v4-identical tasks, read v5_t1_e1 against v4_t4_e1/e2 directly -- see the matched table for per-task deltas worth a closer look (anything outside the ±0.025 noise band).
- On the h4 held-out overlap, `h4_t1_e3` (Oct-06 drop) is the harder drop (all 5 services declared per task), so v5_t1_e1 vs. `h4_t1_e3` alone is the fairer single comparison.
- The h4-matched delta (+0.191) is noticeably larger than the v4-matched delta (+0.080) -- worth asking whether that's h4-30 having more headroom, or something specific to that drop.

