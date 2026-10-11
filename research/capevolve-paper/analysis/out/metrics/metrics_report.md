# Campaign metrics report

Generated 2026-10-11T18:25:42Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-11T18:25:42Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 93970 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 476,378,574 | 476,378,574 | 0 |
| rits_tokens | 462,321,409 | 462,321,409 | 0 |
| capped_tokens (non-RITS) | 14,057,165 | 14,057,165 | 0 |
| calls | 93970 | 93970 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 144064}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 93,970 | 585 | 476,522,638 | 476,378,574 | 462,321,409 | 14,057,165 | $44.58 lb | 466,345,287 |
| suite - | 2,019 | 126 | 11,808,886 | 11,664,822 | 9,998,051 | 1,666,771 | $5.36 lb | 9,998,051 |
| suite A | 19,757 | 136 | 126,266,834 | 126,266,834 | 123,355,444 | 2,911,390 | $7.99 lb | 123,355,444 |
| suite B | 71,736 | 323 | 337,405,393 | 337,405,393 | 327,926,389 | 9,479,004 | $31.22 lb | 331,950,267 |
| suite C | 458 | 0 | 1,041,525 | 1,041,525 | 1,041,525 | 0 | $0.00 lb | 1,041,525 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 1,968 | 11,352,781 | 9,998,051 | $4.10 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A|main | 15,864 | 105,948,135 | 104,095,926 | $4.75 |
| A|no_run_dir | 95 | 443,146 | 288,858 | $0.33 |
| A|restart_waste | 3,004 | 15,610,998 | 15,499,749 | $0.35 |
| A|smoke | 416 | 2,125,526 | 1,382,518 | $2.15 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 4,300 | 18,102,761 | 17,815,882 | $0.00 |
| B|main | 44,604 | 212,232,848 | 204,867,022 | $21.53 |
| B|no_run_dir | 9 | 23,771 | 23,771 | $0.00 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C|main | 431 | 945,307 | 945,307 | $0.00 |
| C|smoke | 27 | 96,218 | 96,218 | $0.00 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 16 | 5.41 | 3.00 | 151 | 0 | 1.49 | 0.00 | 169 (4.2%) | $0.49 | 0/0/0 | 103568 |
| A | ace | 1 | 6 | 5.40 | 1.10 | 128 | 0 | 1.51 | 0.00 | 45 (1.1%) | $0.13 | 0/0/0 | 258514 |
| A | ace | 2 | 14 | 5.42 | 2.60 | 159 | 0 | 1.45 | 0.00 | 186 (4.7%) | $0.51 | 0/0/0 | 116923 |
| A | ao | 0 | 47 | 3.73 | 12.60 | 389 | 0 | 2.35 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 49983 |
| A | ao | 1 | 40 | 3.68 | 10.90 | 371 | 0 | 2.48 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 61899 |
| A | ao | 2 | 40 | 3.71 | 10.80 | 422 | 0 | 2.84 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 70959 |
| A | gepa | 0 | 147 | 10.06 | 14.60 | 822 | 2 | 4.52 | 0.00 | 68 (1.7%) | $0.24 | 5/3/3 | 31188 |
| A | gepa | 1 | 100 | 10.07 | 9.90 | 790 | 9 | 6.13 | 0.00 | 41 (1.0%) | $0.15 | 2/2/2 | 61735 |
| A | gepa | 2 | 199 | 10.06 | 19.80 | 867 | 3 | 4.70 | 0.00 | 123 (3.1%) | $0.38 | 6/4/4 | 24240 |
| A | hc | 0 | 55 | 3.72 | 14.80 | 401 | 0 | 2.22 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 40427 |
| A | hc | 1 | 40 | 3.73 | 10.70 | 396 | 0 | 2.73 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 68128 |
| A | hc | 2 | 52 | 3.74 | 13.90 | 386 | 0 | 2.15 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 41416 |
| A | metaharness | 0 | 120 | 7.49 | 16.00 | 969 | 7 | 6.48 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 54005 |
| A | metaharness | 1 | 119 | 7.49 | 15.90 | 1063 | 2 | 6.75 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 56722 |
| A | metaharness | 2 | 113 | 7.48 | 15.10 | 1054 | 3 | 7.15 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 63280 |
| A | mipro | 0 | 22 | 5.40 | 4.10 | 148 | 1 | 1.03 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 46724 |
| A | mipro | 1 | 18 | 5.38 | 3.30 | 135 | 0 | 1.22 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 68016 |
| A | mipro | 2 | 18 | 5.39 | 3.30 | 120 | 0 | 0.91 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 50550 |
| A | skillopt | 0 | 121 | 10.06 | 12.00 | 1018 | 7 | 6.65 | 0.00 | 417 (10.4%) | $0.97 | 2/2/1 | 58395 |
| A | skillopt | 1 | 120 | 10.06 | 11.90 | 926 | 5 | 6.30 | 0.00 | 437 (10.9%) | $1.00 | 1/1/1 | 56179 |
| A | skillopt | 2 | 148 | 10.06 | 14.70 | 1077 | 13 | 7.00 | 0.00 | 366 (9.2%) | $0.88 | 2/2/2 | 49769 |
| A | trace2skill | 0 | 111 | 9.57 | 11.60 | 867 | 2 | 5.67 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 51036 |
| A | trace2skill | 1 | 109 | 9.58 | 11.40 | 858 | 13 | 5.17 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 47463 |
| A | trace2skill | 2 | 111 | 9.56 | 11.60 | 829 | 11 | 4.99 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 44970 |
| A | wikiskill | 0 | 58 | 5.37 | 10.80 | 503 | 0 | 3.54 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 61014 |
| A | wikiskill | 1 | 69 | 5.38 | 12.80 | 534 | 0 | 3.36 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 48693 |
| A | wikiskill | 2 | 59 | 5.38 | 11.00 | 481 | 0 | 3.31 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 56106 |
| B | ao | 0 | 123 | 5.78 | 21.30 | 3254 | 23 | 12.23 | 1.40 | 621 (15.5%) | $3.75 | 2/1/0 | 117867 |
| B | ao | 1 | 123 | 5.49 | 22.40 | 3092 | 17 | 12.16 | 1.39 | 603 (15.1%) | $3.70 | 1/0/0 | 117191 |
| B | ao | 2 | 74 | 5.78 | 12.80 | 3337 | 10 | 13.67 | 1.36 | 602 (15.0%) | $4.61 | 1/0/0 | 213884 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 682 | 3 | 2.41 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 757 | 1 | 2.68 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 549 | 6 | 2.34 | 0.16 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 672 | 5 | 2.65 | 0.25 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 941 | 7 | 3.59 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 5.77 | 17.00 | 2726 | 12 | 10.59 | 1.45 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125672 |
| B | ctl-seed | 1 | 98 | 5.78 | 17.00 | 2689 | 6 | 10.30 | 1.25 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 120515 |
| B | ctl-seed | 2 | 98 | 5.78 | 17.00 | 2735 | 9 | 10.64 | 1.39 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125348 |
| B | gepa | 0 | 145 | 5.78 | 25.10 | 2558 | 13 | 11.53 | 1.16 | 171 (4.3%) | $0.61 | 7/7/3 | 90184 |
| B | gepa | 1 | 126 | 5.78 | 21.80 | 2128 | 7 | 9.12 | 0.98 | 169 (4.2%) | $0.62 | 8/8/2 | 82850 |
| B | gepa | 2 | 142 | 5.78 | 24.60 | 2462 | 17 | 10.65 | 1.06 | 139 (3.5%) | $0.47 | 7/7/2 | 84862 |
| B | hc | 0 | 147 | 5.78 | 25.40 | 3450 | 13 | 14.88 | 1.74 | 278 (6.9%) | $1.65 | 2/1/0 | 117026 |
| B | hc | 1 | 147 | 5.78 | 25.40 | 3697 | 18 | 15.18 | 1.74 | 378 (9.4%) | $2.06 | 3/2/0 | 120036 |
| B | hc | 2 | 98 | 5.78 | 17.00 | 3674 | 21 | 16.55 | 2.48 | 154 (3.9%) | $0.92 | 1/0/0 | 198980 |
| C | ao | 0 | 0 | 0.07 | n/a | 29 | 0 | 0.06 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ao | 1 | 0 | 0.07 | n/a | 32 | 0 | 0.08 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ao | 2 | 0 | 0.07 | n/a | 22 | 0 | 0.04 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 0 | 0 | 0.08 | n/a | 23 | 0 | 0.05 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 1 | 0 | 0.07 | n/a | 34 | 0 | 0.07 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 2 | 0 | 0.06 | n/a | 21 | 0 | 0.04 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-seed | 0 | n/a | 0.06 | n/a | 21 | 0 | 0.03 | 0.01 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | ctl-seed | 1 | n/a | 0.06 | n/a | 14 | 0 | 0.01 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | ctl-seed | 2 | n/a | 0.06 | n/a | 28 | 0 | 0.04 | 0.01 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | gepa | 0 | 10 | 0.08 | n/a | 44 | 0 | 0.08 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 9004 |
| C | gepa | 1 | 10 | 0.07 | n/a | 39 | 0 | 0.06 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 7318 |
| C | gepa | 2 | 10 | 0.07 | n/a | 33 | 0 | 0.05 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 6145 |
| C | hc | 0 | 0 | 0.08 | n/a | 32 | 0 | 0.07 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | hc | 1 | 0 | 0.08 | n/a | 34 | 0 | 0.08 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | hc | 2 | 0 | 0.07 | n/a | 25 | 0 | 0.05 | 0.01 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 149204 | 149204 | 159668 | 133424 | $0.38 |
| A | ao | 3 | 60947 | 60947 | 60947 | 0 | n/a |
| A | gepa | 3 | 38557 | 38557 | 39054 | 77460 | $0.26 |
| A | hc | 3 | 49990 | 49990 | 49990 | 0 | n/a |
| A | metaharness | 3 | 58002 | 58002 | 58002 | 0 | n/a |
| A | mipro | 3 | 55097 | 55097 | 55097 | 0 | n/a |
| A | skillopt | 3 | 51595 | 51595 | 54781 | 406519 | $0.95 |
| A | trace2skill | 3 | 47823 | 47823 | 47823 | 0 | n/a |
| A | wikiskill | 3 | 55271 | 55271 | 55271 | 0 | n/a |
| B | ao | 3 | 127655 | 141324 | 149647 | 608700 | $4.02 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 107270 | 121184 | 123845 | 0 | n/a |
| B | gepa | 3 | 75654 | 83409 | 85965 | 159663 | $0.57 |
| B | hc | 3 | 124455 | 140800 | 145347 | 269951 | $1.54 |
| C | gepa | 3 | 6458 | 7489 | 7489 | 0 | n/a |

## Overhead / waste (not in main tables; included in campaign totals)

| suite | arm | seed | category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---|---|---|---:|---:|---:|---:|
| B | ao | all | restart_waste | 5,408 | 26,206,898 | 25,761,808 | $3.08 |
| B | hc | all | restart_waste | 4,476 | 21,189,920 | 20,850,489 | $2.04 |
| B | ctl-oneshot | all | restart_waste | 4,210 | 19,472,780 | 19,160,701 | $1.95 |
| B | gepa | all | restart_waste | 3,214 | 14,958,308 | 14,814,038 | $0.48 |
| B | ctl-seed | all | restart_waste | 2,967 | 13,337,661 | 13,337,661 | $0.00 |
| B | ao | all | pilot | 1,161 | 5,524,975 | 5,168,526 | $1.30 |
| A | metaharness | all | restart_waste | 705 | 4,245,257 | 4,245,257 | $0.00 |
| A | ao | all | restart_waste | 636 | 3,811,054 | 3,811,054 | $0.00 |
| A | hc | all | restart_waste | 615 | 3,410,547 | 3,410,547 | $0.00 |
| B | hc | all | pilot | 619 | 2,777,762 | 2,641,597 | $0.54 |
| A | evoskill | all | restart_waste | 802 | 2,573,246 | 2,573,246 | $0.00 |
| B | gepa | all | pilot | 466 | 2,297,765 | 2,241,304 | $0.20 |
| - | BL-gepa-smoke2 | all | smoke | 147 | 2,176,130 | 2,130,636 | $0.16 |
| - | BLsmoke-mipro-s0 | all | smoke | 458 | 1,806,342 | 1,734,479 | $0.22 |
| A | graphskillevo | all | stopped | 185 | 1,645,251 | 1,594,615 | $0.41 |
| - | BL-wikiskill-smoke | all | smoke | 129 | 1,096,254 | 880,221 | $0.25 |
| A | ace | all | restart_waste | 137 | 1,014,045 | 902,796 | $0.35 |
| - | BLsmoke-ace-s0 | all | smoke | 227 | 993,458 | 984,260 | $0.03 |
| B | smoke | all | smoke | 175 | 762,980 | 757,621 | $0.02 |
| - | BL-memento-smoke | all | smoke | 47 | 677,221 | 677,221 | $0.00 |
| - | BL-hl-smoke2 | all | smoke | 82 | 590,486 | 590,486 | $0.00 |
| A | E10-evosmoke | all | smoke | 78 | 578,784 | 578,784 | $0.00 |
| A | mipro | all | restart_waste | 109 | 556,849 | 556,849 | $0.00 |
| - | BL-mipro-smoke | all | smoke | 111 | 547,128 | 485,025 | $0.21 |
| - | BL-hl-smoke4 | all | smoke | 60 | 523,503 | 385,699 | $0.35 |
| B | ahe | all | smoke | 120 | 485,969 | 485,969 | $0.00 |
| A | ahe | all | smoke | 85 | 481,688 | 125,707 | $0.80 |
| - | BL-probe | all | smoke | 53 | 466,907 | 466,907 | $0.00 |
| A | smoke | all | smoke | 74 | 434,649 | 406,397 | $0.09 |
| A | rho | all | no_run_dir | 87 | 427,805 | 273,517 | $0.33 |
| - | BL-trace2skill-smoke | all | smoke | 62 | 378,630 | 159,469 | $0.70 |
| A | mce | all | stopped | 111 | 328,338 | 328,338 | $0.00 |
| - | untagged | all | untagged | 51 | 312,041 | 0 | $1.26 |
| - | BL-hl-smoke5 | all | smoke | 28 | 296,477 | 94,782 | $0.57 |
| A | hc | all | smoke | 65 | 286,822 | 263,711 | $0.07 |
| - | BL-ace-smoke | all | smoke | 179 | 285,133 | 171,903 | $0.35 |
| - | BL-hl-smoke6 | all | smoke | 47 | 275,473 | 275,473 | $0.00 |
| - | BL-mce-smoke | all | smoke | 75 | 256,348 | 129,161 | $0.54 |
| - | BL-hl-smoke | all | smoke | 26 | 203,616 | 200,905 | $0.01 |
| A | E10-cfprobe | all | smoke | 86 | 180,158 | 0 | $0.77 |
| - | BL-skillopt-smoke | all | smoke | 44 | 176,669 | 142,711 | $0.11 |
| - | BL-gepa-smoke | all | smoke | 56 | 169,581 | 169,581 | $0.00 |
| A | memento | all | stopped | 82 | 165,440 | 165,440 | $0.00 |
| - | BL-hl-smoke3 | all | smoke | 23 | 121,156 | 121,156 | $0.00 |
| - | BL-metaharness-smoke | all | smoke | 43 | 119,562 | 94,330 | $0.10 |
| C | E10C-s0-trial | all | smoke | 27 | 96,218 | 96,218 | $0.00 |
| - | BL-graphskillevo-smoke | all | smoke | 18 | 76,722 | 51,846 | $0.14 |
| A | E10-evomock | all | smoke | 5 | 63,186 | 0 | $0.18 |
| - | BL-memento-smokefake | all | smoke | 12 | 62,318 | 0 | $0.34 |
| - | E00 | all | smoke | 6 | 41,475 | 41,475 | $0.00 |
| B | sbxtest | all | smoke | 1 | 30,614 | 0 | $0.08 |
| A | E10-tagprobe-api | all | smoke | 1 | 30,596 | 0 | $0.08 |
| A | E10-metaharness-smoke | all | smoke | 1 | 26,893 | 0 | $0.07 |
| A | E10-tagprobe-auth | all | smoke | 1 | 26,880 | 0 | $0.07 |
| B | hl-trial | all | no_run_dir | 9 | 23,771 | 23,771 | $0.00 |
| A | evoskill-r2 | all | no_run_dir | 8 | 15,341 | 15,341 | $0.00 |
| A | E10-mh-negtest | all | smoke | 6 | 7,916 | 0 | $0.03 |
| - | BL-metrtest | all | smoke | 3 | 4,993 | 4,993 | $0.00 |
| A | E10-evodiag | all | smoke | 3 | 4,993 | 4,993 | $0.00 |
| - | BL-preflight | all | smoke | 3 | 4,847 | 4,847 | $0.00 |
| A | E10-evowd | all | smoke | 6 | 2,880 | 2,880 | $0.00 |
| - | E01 | all | smoke | 25 | 2,161 | 294 | $0.02 |
| B | judgetest | all | smoke | 1 | 369 | 0 | $0.00 |
| - | BL-hl-chk | all | smoke | 1 | 100 | 100 | $0.00 |
| - | BL-hl-check | all | smoke | 3 | 91 | 91 | $0.00 |
| A | E10-evodiag2 | all | smoke | 2 | 46 | 46 | $0.00 |
| A | E10-memento-smoke | all | smoke | 1 | 28 | 0 | $0.00 |
| B | probe | all | smoke | 5 | 12 | 0 | $0.00 |
| A | E10-tagprobe3 | all | smoke | 2 | 7 | 0 | $0.00 |

Restart cutoffs used (gateway calls before this time with the run's tag are counted as restart_waste):

- A/ace/s0: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/ace/s1: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/ace/s2: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/ao/s0: 2026-10-11T14:41:25Z (derived: birth time of manifest/negtest.txt)
- A/evoskill/s0: 2026-10-11T18:24:01Z (derived: birth time of negtest_before_launch.txt)
- A/evoskill/s1: 2026-10-11T18:24:01Z (derived: birth time of negtest_before_launch.txt)
- A/evoskill/s2: 2026-10-11T18:24:01Z (derived: birth time of negtest_before_launch.txt)
- A/hc/s0: 2026-10-11T14:41:25Z (derived: birth time of manifest/negtest.txt)
- A/metaharness/s0: 2026-10-11T10:56:11Z (derived: birth time of isolation_negtest.txt)
- A/metaharness/s1: 2026-10-11T10:56:11Z (derived: birth time of isolation_negtest.txt)
- A/metaharness/s2: 2026-10-11T10:56:11Z (derived: birth time of isolation_negtest.txt)
- A/mipro/s0: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/mipro/s1: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/mipro/s2: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- B/ao/s0: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ao/s1: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ao/s2: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ctl-oneshot/s0: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ctl-oneshot/s1: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ctl-oneshot/s2: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ctl-seed/s0: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ctl-seed/s1: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/ctl-seed/s2: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/gepa/s0: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/gepa/s1: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/gepa/s2: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/hc/s0: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/hc/s1: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))
- B/hc/s2: 2026-10-11T12:38:38Z (runs/E10B/superseded_v1/README: v1 searches stopped 12:38:38 UTC (v2 relaunched ~12:44))

## Data-quality notes

- Runs without a per-rollout record: A/evoskill/s0, A/evoskill/s1, A/evoskill/s2, A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, A/metaharness/s0, A/metaharness/s1, A/metaharness/s2, C/ao/s0, C/ao/s1, C/ao/s2, C/ctl-oneshot/s0, C/ctl-oneshot/s1, C/ctl-oneshot/s2, C/ctl-seed/s0, C/ctl-seed/s1, C/ctl-seed/s2, C/gepa/s0, C/gepa/s1, C/gepa/s2, C/hc/s0, C/hc/s1, C/hc/s2
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
