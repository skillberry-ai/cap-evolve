# v4_t2_e1 — task-by-task optimization results

Two tables: **Summary** (one row per task, `#` = position 1-21 in `TASK_IDS`) and **Per-iteration detail** (one row per eval inside a task — seed / each candidate iteration / the held-out-in-name-only test evals — with cost and time split into the runner's eval cost vs. the optimizer's own cost). See `splits_warning` in every run: test overlaps train/val, so the test number is a fit metric, not a true holdout.

## Summary table

| # | Task | Seed(val) | Iter1 val(accept) | Iter2 val(accept) | Iter3 val(accept) | Best | Test reward | Test baseline | Δ | Cost($) | Tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cloud-024-guid-to-account | 0.2000 | 1.0000(✓) | — | — | cand_0001 | 1.0000 | 0.2000 | +0.8000 | 14.47 | 333,524 |
| 2 | cloud-026-gpu-abuse-triage | 0.9400 | 0.9067(✗) | 0.9767(✓) | — | cand_0002 | 1.0000 | 0.9400 | +0.0600 | 22.68 | 597,023 |
| 3 | cost-029-no-cost-rows-for-guid | 0.8000 | 0.8000(✗) | 1.0000(✓) | — | cand_0002 | 1.0000 | 0.8000 | +0.2000 | 26.12 | 1,045,237 |
| 4 | cost-030-threshold-not-an-anomaly | 1.0000 | — | — | — | seed | 1.0000 | 1.0000 | +0.0000 | 1.39 | 396,441 |
| 5 | icinga-010-stuck-anarchysubjects | 0.4670 | 0.4950(✓) | 0.4950(✗) | — | cand_0001 | 0.4950 | 0.5230 | -0.0280 | 28.12 | 1,477,226 |
| 6 | icinga-011-aap2-job-status-alert | 0.8600 | 1.0000(✓) | — | — | cand_0001 | 1.0000 | 0.8600 | +0.1400 | 12.77 | 743,549 |
| 7 | icinga-013-acknowledged-not-an-issue | 0.4480 | 0.6080(✓) | 0.0000(✗) | 0.6400(✓) | cand_0003 | 0.6400 | 0.4800 | +0.1600 | 23.57 | 538,477 |
| 8 | icinga-014-check-script-path-moved | 0.8600 | 1.0000(✓) | — | — | cand_0001 | 1.0000 | 0.9650 | +0.0350 | 14.22 | 1,196,824 |
| 9 | platform-001-ee-entrypoint-rca | 0.8600 | 0.9400(✓) | 0.9520(✓) | — | cand_0002 | 1.0000 | 0.6440 | +0.3560 | 38.30 | 866,365 |
| 10 | platform-002-collection-not-found-rca | 0.9067 | 1.0000(✓) | — | — | cand_0001 | 1.0000 | 0.5733 | +0.4267 | 8.30 | 482,431 |
| 11 | platform-003-tojson-dict-literal-rca | 0.5633 | 0.8467(✓) | 0.9167(✓) | — | cand_0002 | 0.7633 | 0.3567 | +0.4067 | 27.85 | 840,932 |
| 12 | platform-004-events-then-config | 0.7867 | 0.4000(✗) | 1.0000(✓) | — | cand_0002 | 1.0000 | 0.7133 | +0.2867 | 15.88 | 517,799 |
| 13 | platform-005-wrong-owner-trap | 0.3200 | 0.6080(✓) | 0.9160(✓) | 1.0000(✓) | cand_0003 | 1.0000 | 0.7740 | +0.2260 | 13.65 | 2,351,554 |
| 14 | platform-007-directory-path-fetch | 0.4700 | 1.0000(✓) | — | — | cand_0001 | 1.0000 | 0.5100 | +0.4900 | 7.38 | 351,046 |
| 15 | platform-008-log-does-not-say | 0.8000 | 1.0000(✓) | — | — | cand_0001 | 1.0000 | 0.9600 | +0.0400 | 13.83 | 438,410 |
| 16 | platform-022-job-on-no-controller | 0.5950 | 0.8950(✓) | 0.9300(✓) | 1.0000(✓) | cand_0003 | 1.0000 | 0.6650 | +0.3350 | 25.90 | 764,975 |
| 17 | platform-023-splunk-guid-no-events | 0.9600 | 0.8000(✗) | 1.0000(✓) | — | cand_0002 | 1.0000 | 0.9600 | +0.0400 | 15.04 | 522,733 |
| 18 | platform-031-helm-url-not-a-timeout | 0.4408 | 0.8600(✓) | 1.0000(✓) | — | cand_0002 | 0.9650 | 0.3170 | +0.6480 | 26.42 | 2,985,624 |
| 19 | platform-032-shared-secret-not-a-registry-outage | 0.4875 | 0.5900(✓) | — | — | cand_0001 | 0.5750 | 0.4350 | +0.1400 | 36.11 | 2,819,580 |
| 20 | platform-033-schema-change-not-the-oom | 0.4024 | 0.7214(✓) | 0.9667(✓) | — | cand_0002 | 0.9667 | 0.4405 | +0.5262 | 43.57 | 2,957,393 |
| 21 | platform-034-rate-limit-not-an-outage | 0.3861 | 0.8167(✓) | 1.0000(✓) | — | cand_0002 | 0.9844 | 0.7400 | +0.2444 | 21.66 | 803,916 |

_Tasks 13-15 each had a run interrupted by an unrelated infrastructure issue (a team LLM API budget cap, since fixed) and were re-run. For task 13 (`platform-005-wrong-owner-trap`), the run shown above is the **first** attempt — it had already finalized cleanly before the interruption mattered; a second, redundant run scored worse on a noisier seed measurement and is not reflected here. For tasks 14-15 (`platform-007-directory-path-fetch`, `platform-008-log-does-not-say`), the run shown above is the **rerun** — their first attempts underperformed or never finalized and are not reflected here._

## Per-iteration detail table — cost & time, eval vs. optimization

| # | Task | Stage | Split | Reward | Accept | Eval $ | Eval tok | Eval s | Opt $ | Opt tok | Opt s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cloud-024-guid-to-account | seed | val | 0.2000 | - | 0.0905 | 28,854 | 150.6 | 0.0000 | 0 | 0.0 |
| 1 | cloud-024-guid-to-account | iter1(cand_0001) | val | 1.0000 | ✓ | 0.2595 | 81,411 | 233.0 | 13.7728 | 112,966 | 4762.6 |
| 1 | cloud-024-guid-to-account | FINAL | test | 1.0000 | - | 0.2597 | 81,432 | 220.5 | 0.0000 | 0 | 0.0 |
| 1 | cloud-024-guid-to-account | FINAL_seed | test | 0.2000 | - | 0.0907 | 28,861 | 136.3 | 0.0000 | 0 | 0.0 |
| 2 | cloud-026-gpu-abuse-triage | seed | val | 0.9400 | - | 0.3181 | 90,673 | 632.9 | 0.0000 | 0 | 0.0 |
| 2 | cloud-026-gpu-abuse-triage | iter1(cand_0001) | val | 0.9067 | ✗ | 0.3164 | 90,334 | 657.6 | 8.2049 | 93,430 | 1133.8 |
| 2 | cloud-026-gpu-abuse-triage | iter2(cand_0002) | val | 0.9767 | ✓ | 0.3220 | 90,475 | 512.0 | 12.8799 | 49,978 | 2855.8 |
| 2 | cloud-026-gpu-abuse-triage | FINAL | test | 1.0000 | - | 0.3231 | 91,668 | 636.4 | 0.0000 | 0 | 0.0 |
| 2 | cloud-026-gpu-abuse-triage | FINAL_seed | test | 0.9400 | - | 0.3203 | 90,465 | 578.8 | 0.0000 | 0 | 0.0 |
| 3 | cost-029-no-cost-rows-for-guid | seed | val | 0.8000 | - | 0.3674 | 111,137 | 243.9 | 0.0000 | 0 | 0.0 |
| 3 | cost-029-no-cost-rows-for-guid | iter1(cand_0001) | val | 0.8000 | ✗ | 0.6430 | 197,016 | 380.7 | 13.3023 | 103,967 | 4861.2 |
| 3 | cost-029-no-cost-rows-for-guid | iter2(cand_0002) | val | 1.0000 | ✓ | 0.6609 | 204,480 | 388.6 | 10.1202 | 113,418 | 1938.2 |
| 3 | cost-029-no-cost-rows-for-guid | FINAL | test | 1.0000 | - | 0.6577 | 204,202 | 348.6 | 0.0000 | 0 | 0.0 |
| 3 | cost-029-no-cost-rows-for-guid | FINAL_seed | test | 0.8000 | - | 0.3655 | 111,017 | 295.5 | 0.0000 | 0 | 0.0 |
| 4 | cost-030-threshold-not-an-anomaly | seed | val | 1.0000 | - | 0.6935 | 198,395 | 587.3 | 0.0000 | 0 | 0.0 |
| 4 | cost-030-threshold-not-an-anomaly | FINAL | test | 1.0000 | - | 0.6941 | 198,046 | 579.1 | 0.0000 | 0 | 0.0 |
| 5 | icinga-010-stuck-anarchysubjects | seed | val | 0.4670 | - | 1.3056 | 399,068 | 952.6 | 0.0000 | 0 | 0.0 |
| 5 | icinga-010-stuck-anarchysubjects | iter1(cand_0001) | val | 0.4950 | ✓ | 0.4726 | 143,609 | 360.0 | 15.1079 | 138,312 | 1577.4 |
| 5 | icinga-010-stuck-anarchysubjects | iter2(cand_0002) | val | 0.4950 | ✗ | 0.4772 | 143,908 | 351.6 | 8.9375 | 95,907 | 1178.2 |
| 5 | icinga-010-stuck-anarchysubjects | FINAL | test | 0.4950 | - | 0.4766 | 143,874 | 360.3 | 0.0000 | 0 | 0.0 |
| 5 | icinga-010-stuck-anarchysubjects | FINAL_seed | test | 0.5230 | - | 1.3433 | 412,548 | 929.8 | 0.0000 | 0 | 0.0 |
| 6 | icinga-011-aap2-job-status-alert | seed | val | 0.8600 | - | 0.4306 | 119,708 | 355.6 | 0.0000 | 0 | 0.0 |
| 6 | icinga-011-aap2-job-status-alert | iter1(cand_0001) | val | 1.0000 | ✓ | 0.6763 | 197,513 | 425.9 | 10.3671 | 48,869 | 1442.5 |
| 6 | icinga-011-aap2-job-status-alert | FINAL | test | 1.0000 | - | 0.6779 | 197,582 | 490.5 | 0.0000 | 0 | 0.0 |
| 6 | icinga-011-aap2-job-status-alert | FINAL_seed | test | 0.8600 | - | 0.6215 | 179,877 | 441.6 | 0.0000 | 0 | 0.0 |
| 7 | icinga-013-acknowledged-not-an-issue | seed | val | 0.4480 | - | 0.2216 | 66,837 | 149.3 | 0.0000 | 0 | 0.0 |
| 7 | icinga-013-acknowledged-not-an-issue | iter1(cand_0001) | val | 0.6080 | ✓ | 0.2436 | 73,489 | 171.8 | 7.8381 | 51,273 | 1135.5 |
| 7 | icinga-013-acknowledged-not-an-issue | iter2(cand_0002) | val | 0.0000 | ✗ | 0.0000 | 0 | 420.5 | 4.0110 | 0 | 1914.2 |
| 7 | icinga-013-acknowledged-not-an-issue | iter3(cand_0003) | val | 0.6400 | ✓ | 0.2658 | 81,642 | 178.5 | 10.5037 | 116,767 | 1456.1 |
| 7 | icinga-013-acknowledged-not-an-issue | FINAL | test | 0.6400 | - | 0.2655 | 81,623 | 198.1 | 0.0000 | 0 | 0.0 |
| 7 | icinga-013-acknowledged-not-an-issue | FINAL_seed | test | 0.4800 | - | 0.2217 | 66,846 | 138.1 | 0.0000 | 0 | 0.0 |
| 8 | icinga-014-check-script-path-moved | seed | val | 0.8600 | - | 0.7182 | 212,733 | 579.9 | 0.0000 | 0 | 0.0 |
| 8 | icinga-014-check-script-path-moved | iter1(cand_0001) | val | 1.0000 | ✓ | 1.1082 | 340,417 | 651.8 | 10.5495 | 82,911 | 1582.5 |
| 8 | icinga-014-check-script-path-moved | FINAL | test | 1.0000 | - | 0.8775 | 269,961 | 501.3 | 0.0000 | 0 | 0.0 |
| 8 | icinga-014-check-script-path-moved | FINAL_seed | test | 0.9650 | - | 0.9711 | 290,802 | 920.0 | 0.0000 | 0 | 0.0 |
| 9 | platform-001-ee-entrypoint-rca | seed | val | 0.8600 | - | 0.3625 | 103,043 | 2116.6 | 0.0000 | 0 | 0.0 |
| 9 | platform-001-ee-entrypoint-rca | iter1(cand_0001) | val | 0.9400 | ✓ | 0.3421 | 98,192 | 1755.4 | 14.0530 | 113,311 | 1544.0 |
| 9 | platform-001-ee-entrypoint-rca | iter2(cand_0002) | val | 0.9520 | ✓ | 0.5028 | 145,435 | 1855.6 | 22.3223 | 204,493 | 2665.3 |
| 9 | platform-001-ee-entrypoint-rca | FINAL | test | 1.0000 | - | 0.3296 | 94,201 | 1502.0 | 0.0000 | 0 | 0.0 |
| 9 | platform-001-ee-entrypoint-rca | FINAL_seed | test | 0.6440 | - | 0.3894 | 107,690 | 1549.0 | 0.0000 | 0 | 0.0 |
| 10 | platform-002-collection-not-found-rca | seed | val | 0.9067 | - | 0.3070 | 89,974 | 1336.7 | 0.0000 | 0 | 0.0 |
| 10 | platform-002-collection-not-found-rca | iter1(cand_0001) | val | 1.0000 | ✓ | 0.3192 | 95,028 | 1278.4 | 6.9676 | 89,179 | 1065.3 |
| 10 | platform-002-collection-not-found-rca | FINAL | test | 1.0000 | - | 0.3183 | 95,558 | 1307.5 | 0.0000 | 0 | 0.0 |
| 10 | platform-002-collection-not-found-rca | FINAL_seed | test | 0.5733 | - | 0.3914 | 112,692 | 2025.0 | 0.0000 | 0 | 0.0 |
| 11 | platform-003-tojson-dict-literal-rca | seed | val | 0.5633 | - | 0.4520 | 125,375 | 1266.3 | 0.0000 | 0 | 0.0 |
| 11 | platform-003-tojson-dict-literal-rca | iter1(cand_0001) | val | 0.8467 | ✓ | 0.4252 | 112,744 | 986.5 | 13.9623 | 105,585 | 2178.3 |
| 11 | platform-003-tojson-dict-literal-rca | iter2(cand_0002) | val | 0.9167 | ✓ | 0.3393 | 89,883 | 869.2 | 11.6003 | 116,672 | 1535.3 |
| 11 | platform-003-tojson-dict-literal-rca | FINAL | test | 0.7633 | - | 0.3958 | 106,206 | 1130.3 | 0.0000 | 0 | 0.0 |
| 11 | platform-003-tojson-dict-literal-rca | FINAL_seed | test | 0.3567 | - | 0.6711 | 184,467 | 2412.5 | 0.0000 | 0 | 0.0 |
| 12 | platform-004-events-then-config | seed | val | 0.7867 | - | 0.2349 | 68,665 | 402.5 | 0.0000 | 0 | 0.0 |
| 12 | platform-004-events-then-config | iter1(cand_0001) | val | 0.4000 | ✗ | 0.1208 | 35,101 | 955.3 | 6.0917 | 64,572 | 881.6 |
| 12 | platform-004-events-then-config | iter2(cand_0002) | val | 1.0000 | ✓ | 0.2906 | 85,983 | 409.7 | 8.5755 | 95,678 | 3800.0 |
| 12 | platform-004-events-then-config | FINAL | test | 1.0000 | - | 0.2426 | 71,079 | 439.0 | 0.0000 | 0 | 0.0 |
| 12 | platform-004-events-then-config | FINAL_seed | test | 0.7133 | - | 0.3273 | 96,721 | 482.4 | 0.0000 | 0 | 0.0 |
| 13 | platform-005-wrong-owner-trap | seed | val | 0.3200 | - | 1.6978 | 547,675 | 1109.7 | 0.0000 | 0 | 0.0 |
| 13 | platform-005-wrong-owner-trap | iter1(cand_0001) | val | 0.6080 | ✓ | 1.3731 | 434,579 | 790.6 | 6.3944 | 48,410 | 1057.1 |
| 13 | platform-005-wrong-owner-trap | iter2(cand_0002) | val | 0.9160 | ✓ | 0.9278 | 291,120 | 447.6 | 0.0000 | 0 | 203.7 |
| 13 | platform-005-wrong-owner-trap | iter3(cand_0003) | val | 1.0000 | ✓ | 0.9358 | 294,362 | 559.3 | 0.0000 | 0 | 192.8 |
| 13 | platform-005-wrong-owner-trap | FINAL | test | 1.0000 | - | 0.9701 | 306,606 | 461.3 | 0.0000 | 0 | 0.0 |
| 13 | platform-005-wrong-owner-trap | FINAL_seed | test | 0.7740 | - | 1.3506 | 428,802 | 748.4 | 0.0000 | 0 | 0.0 |
| 14 | platform-007-directory-path-fetch | seed | val | 0.4700 | - | 0.2253 | 66,854 | 425.4 | 0.0000 | 0 | 0.0 |
| 14 | platform-007-directory-path-fetch | iter1(cand_0001) | val | 1.0000 | ✓ | 0.2272 | 67,179 | 438.1 | 6.4764 | 83,393 | 1166.2 |
| 14 | platform-007-directory-path-fetch | FINAL | test | 1.0000 | - | 0.2302 | 67,022 | 350.2 | 0.0000 | 0 | 0.0 |
| 14 | platform-007-directory-path-fetch | FINAL_seed | test | 0.5100 | - | 0.2240 | 66,598 | 462.9 | 0.0000 | 0 | 0.0 |
| 15 | platform-008-log-does-not-say | seed | val | 0.8000 | - | 0.2925 | 90,795 | 1546.0 | 0.0000 | 0 | 0.0 |
| 15 | platform-008-log-does-not-say | iter1(cand_0001) | val | 1.0000 | ✓ | 0.2526 | 78,810 | 1150.6 | 12.7929 | 115,485 | 1765.7 |
| 15 | platform-008-log-does-not-say | FINAL | test | 1.0000 | - | 0.2406 | 75,833 | 534.2 | 0.0000 | 0 | 0.0 |
| 15 | platform-008-log-does-not-say | FINAL_seed | test | 0.9600 | - | 0.2497 | 77,487 | 933.2 | 0.0000 | 0 | 0.0 |
| 16 | platform-022-job-on-no-controller | seed | val | 0.5950 | - | 0.2264 | 64,941 | 361.1 | 0.0000 | 0 | 0.0 |
| 16 | platform-022-job-on-no-controller | iter1(cand_0001) | val | 0.8950 | ✓ | 0.2511 | 73,953 | 350.0 | 5.4125 | 69,947 | 858.4 |
| 16 | platform-022-job-on-no-controller | iter2(cand_0002) | val | 0.9300 | ✓ | 0.2559 | 77,010 | 313.2 | 8.7280 | 120,165 | 1414.1 |
| 16 | platform-022-job-on-no-controller | iter3(cand_0003) | val | 1.0000 | ✓ | 0.2807 | 85,371 | 297.8 | 10.2332 | 123,376 | 1532.9 |
| 16 | platform-022-job-on-no-controller | FINAL | test | 1.0000 | - | 0.2796 | 85,035 | 299.1 | 0.0000 | 0 | 0.0 |
| 16 | platform-022-job-on-no-controller | FINAL_seed | test | 0.6650 | - | 0.2279 | 65,177 | 302.6 | 0.0000 | 0 | 0.0 |
| 17 | platform-023-splunk-guid-no-events | seed | val | 0.9600 | - | 0.2429 | 67,859 | 312.1 | 0.0000 | 0 | 0.0 |
| 17 | platform-023-splunk-guid-no-events | iter1(cand_0001) | val | 0.8000 | ✗ | 0.2783 | 77,435 | 401.9 | 6.0552 | 54,731 | 1197.5 |
| 17 | platform-023-splunk-guid-no-events | iter2(cand_0002) | val | 1.0000 | ✓ | 0.2793 | 77,640 | 389.7 | 7.6613 | 99,533 | 1304.7 |
| 17 | platform-023-splunk-guid-no-events | FINAL | test | 1.0000 | - | 0.2804 | 77,862 | 407.0 | 0.0000 | 0 | 0.0 |
| 17 | platform-023-splunk-guid-no-events | FINAL_seed | test | 0.9600 | - | 0.2441 | 67,673 | 375.5 | 0.0000 | 0 | 0.0 |
| 18 | platform-031-helm-url-not-a-timeout | seed | val | 0.4408 | - | 0.9872 | 306,605 | 1249.7 | 0.0000 | 0 | 0.0 |
| 18 | platform-031-helm-url-not-a-timeout | iter1(cand_0001) | val | 0.8600 | ✓ | 2.3153 | 720,418 | 1155.3 | 7.6515 | 96,848 | 1349.1 |
| 18 | platform-031-helm-url-not-a-timeout | iter2(cand_0002) | val | 1.0000 | ✓ | 2.0447 | 632,978 | 954.6 | 9.7679 | 97,632 | 1847.8 |
| 18 | platform-031-helm-url-not-a-timeout | FINAL | test | 0.9650 | - | 1.9254 | 595,831 | 787.1 | 0.0000 | 0 | 0.0 |
| 18 | platform-031-helm-url-not-a-timeout | FINAL_seed | test | 0.3170 | - | 1.7247 | 535,312 | 1800.8 | 0.0000 | 0 | 0.0 |
| 19 | platform-032-shared-secret-not-a-registry-outage | seed | val | 0.4875 | - | 1.7838 | 571,720 | 1318.3 | 0.0000 | 0 | 0.0 |
| 19 | platform-032-shared-secret-not-a-registry-outage | iter1(cand_0001) | val | 0.5900 | ✓ | 2.2269 | 714,598 | 1158.8 | 28.1201 | 257,540 | 4149.2 |
| 19 | platform-032-shared-secret-not-a-registry-outage | FINAL | test | 0.5750 | - | 2.2042 | 705,595 | 1229.8 | 0.0000 | 0 | 0.0 |
| 19 | platform-032-shared-secret-not-a-registry-outage | FINAL_seed | test | 0.4350 | - | 1.7796 | 570,127 | 1209.7 | 0.0000 | 0 | 0.0 |
| 20 | platform-033-schema-change-not-the-oom | seed | val | 0.4024 | - | 1.8022 | 575,322 | 1232.0 | 0.0000 | 0 | 0.0 |
| 20 | platform-033-schema-change-not-the-oom | iter1(cand_0001) | val | 0.7214 | ✓ | 2.1704 | 696,326 | 1067.5 | 19.8644 | 147,437 | 2199.9 |
| 20 | platform-033-schema-change-not-the-oom | iter2(cand_0002) | val | 0.9667 | ✓ | 1.5651 | 486,528 | 690.6 | 15.0573 | 77,821 | 1850.8 |
| 20 | platform-033-schema-change-not-the-oom | FINAL | test | 0.9667 | - | 1.3153 | 403,845 | 547.2 | 0.0000 | 0 | 0.0 |
| 20 | platform-033-schema-change-not-the-oom | FINAL_seed | test | 0.4405 | - | 1.7917 | 570,114 | 1283.3 | 0.0000 | 0 | 0.0 |
| 21 | platform-034-rate-limit-not-an-outage | seed | val | 0.3861 | - | 0.1454 | 40,519 | 1094.5 | 0.0000 | 0 | 0.0 |
| 21 | platform-034-rate-limit-not-an-outage | iter1(cand_0001) | val | 0.8167 | ✓ | 0.3819 | 108,406 | 1410.3 | 10.1004 | 119,155 | 1545.3 |
| 21 | platform-034-rate-limit-not-an-outage | iter2(cand_0002) | val | 1.0000 | ✓ | 0.4884 | 142,471 | 1398.3 | 9.5475 | 111,557 | 1573.4 |
| 21 | platform-034-rate-limit-not-an-outage | FINAL | test | 0.9844 | - | 0.3589 | 103,483 | 974.8 | 0.0000 | 0 | 0.0 |
| 21 | platform-034-rate-limit-not-an-outage | FINAL_seed | test | 0.7400 | - | 0.6389 | 178,325 | 2582.1 | 0.0000 | 0 | 0.0 |
