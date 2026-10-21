# m2_nonconflict — merge log

Kept: hunks no other task's hunk overlaps. Dropped: every contested hunk.

| file | hunks | kept | dropped |
|---|--:|--:|--:|
| orchestrator.md | 11 | 7 | 4 |
| shared_context.md | 43 | 10 | 33 |
| aap2_agent.md | 71 | 37 | 34 |
| babylon_agent.md | 12 | 7 | 5 |
| cost_agent.md | 11 | 9 | 2 |
| icinga_agent.md | 28 | 13 | 15 |
| ocpv_agent.md | 0 | 0 | 0 |
| security_agent.md | 12 | 8 | 4 |
| **all** | 188 | 91 | 97 |

Per task (kept / total hunks):

| task | kept | total |
|---|--:|--:|
| cloud-057-cloudtrail-select-only-refusal | 0 | 4 |
| cloud-058-malformed-account-id | 3 | 6 |
| cloud-317-namesake-user-other-account | 4 | 7 |
| cost-051-gcp-net-of-credits | 1 | 2 |
| cost-402-unused-cost-preset-has-no-utilisation | 1 | 3 |
| cost-407-aws-historical-query-came-back-org-wide | 3 | 4 |
| cost-408-three-cloud-total-gcp-query-failed | 5 | 6 |
| cost-418-capacity-window-starts-mid-review | 2 | 5 |
| icinga-045-hosts-search-filter | 1 | 2 |
| icinga-201-soft-critical-not-yet-hard | 1 | 6 |
| icinga-204-downtime-window-expired | 0 | 3 |
| icinga-206-stale-ok-check | 2 | 5 |
| icinga-212-fix-on-main-not-on-pinned-ref | 5 | 8 |
| icinga-215-ack-comment-author-and-expiry | 2 | 4 |
| icinga-216-flexible-downtime-duration | 0 | 2 |
| icinga-222-lag-check-runs-on-satellite | 2 | 4 |
| platform-004-events-then-config | 4 | 13 |
| platform-005-wrong-owner-trap | 1 | 6 |
| platform-007-directory-path-fetch | 6 | 9 |
| platform-032-shared-secret-not-a-registry-outage | 3 | 7 |
| platform-101-vcpu-quota-from-catalog-sizing | 1 | 3 |
| platform-104-cfn-dependency-and-what-changed | 2 | 6 |
| platform-112-exec-pool-disk-not-the-bastion | 5 | 9 |
| platform-116-timeout-headroom-from-history | 7 | 14 |
| platform-121-near-miss-pick-partner-repo | 2 | 3 |
| platform-124-event-accounts-not-returned | 1 | 2 |
| platform-126-stop-job-from-tower-jobs | 4 | 4 |
| platform-136-provision-key-mode-too-open | 1 | 2 |
| platform-137-generated-password-forbidden-chars | 2 | 4 |
| platform-148-precheck-caches-nxdomain | 7 | 10 |
| platform-152-path-search-cannot-find-variable-uses | 2 | 2 |
| platform-153-override-uses-removed-variable-name | 0 | 3 |
| platform-155-order-time-was-queue-wait | 1 | 6 |
| platform-158-lab-instances-outside-default-region | 10 | 14 |
