# Campaign metrics report

Generated 2026-10-13T02:32:38Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-13T02:32:56Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 417434 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 2,772,221,343 | 2,292,704,379 | 479,516,964 |
| rits_tokens | 2,604,611,331 | 1,638,423,825 | 966,187,506 |
| capped_tokens (non-RITS) | 165,517,167 | 92,349,003 | 73,168,164 |
| calls | 417434 | 417434 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 190737}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 1,005,221 | 59,797 | 5,213,084,944 | 5,212,894,207 | 2,605,825,575 | 165,566,210 | $1329.92 lb | 2,619,504,948 |
| suite - | 16,733 | 414 | 71,545,325 | 71,401,261 | 13,784,541 | 2,338,791 | $35.85 lb | 13,790,192 |
| suite A | 114,275 | 232 | 1,139,199,138 | 1,139,152,465 | 1,090,024,849 | 49,127,616 | $127.39 lb | 1,090,024,849 |
| suite A-E12 | 9,134 | 36 | 48,868,783 | 48,868,783 | 47,318,243 | 1,550,540 | $6.00 lb | 47,318,243 |
| suite B | 172,493 | 632 | 943,369,935 | 943,369,935 | 880,423,074 | 62,946,861 | $131.26 lb | 891,849,560 |
| suite B-E12 | 27,046 | 121 | 134,428,656 | 134,428,656 | 130,614,080 | 3,814,576 | $8.03 lb | 132,861,316 |
| suite C | 61,902 | 205 | 329,943,459 | 329,943,459 | 323,222,626 | 6,720,833 | $29.41 lb | 323,222,626 |
| suite C-E12 | 23,966 | 127 | 126,235,462 | 126,235,462 | 120,438,162 | 5,797,300 | $34.73 lb | 120,438,162 |
| suite D | 213,852 | 13,524 | 916,256,483 | 916,256,483 | 0 | 10,237,808 | $358.72 lb | 0 |
| suite D-E21 | 97,154 | 8,728 | 398,023,375 | 398,023,375 | 0 | 2,453,270 | $151.52 lb | 0 |
| suite D-null | 40,838 | 648 | 151,506,914 | 151,506,914 | 0 | 0 | $57.93 lb | 0 |
| suite E | 227,828 | 35,130 | 953,707,414 | 953,707,414 | 0 | 20,578,615 | $389.09 lb | 0 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 16,682 | 71,089,220 | 13,784,541 | $34.58 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A-E12|main | 9,134 | 48,868,783 | 47,318,243 | $6.00 |
| A|main | 109,021 | 1,099,544,686 | 1,054,341,830 | $116.62 |
| A|no_run_dir | 123 | 490,818 | 336,530 | $0.33 |
| A|restart_waste | 4,291 | 34,666,272 | 31,862,522 | $7.18 |
| A|smoke | 462 | 2,311,660 | 1,395,574 | $2.85 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B-E12|main | 25,152 | 126,591,423 | 122,922,985 | $8.03 |
| B-E12|restart_waste | 1,894 | 7,837,233 | 7,691,095 | $0.00 |
| B|chaser_eval | 11,673 | 50,535,207 | 49,792,884 | $0.00 |
| B|main | 133,566 | 737,825,403 | 694,123,351 | $92.04 |
| B|no_run_dir | 4,431 | 47,963,312 | 31,287,125 | $29.53 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C-E12|main | 23,966 | 126,235,462 | 120,438,162 | $34.73 |
| C|chaser_eval | 2,487 | 9,669,092 | 9,669,092 | $0.00 |
| C|main | 59,386 | 320,149,134 | 313,457,316 | $29.34 |
| C|smoke | 29 | 125,233 | 96,218 | $0.07 |
| D-E21|main | 97,154 | 398,023,375 | 0 | $151.52 |
| D-null|smoke | 40,838 | 151,506,914 | 0 | $57.93 |
| D|main | 213,850 | 916,256,463 | 0 | $358.72 |
| D|no_run_dir | 2 | 20 | 0 | $0.00 |
| E|main | 227,828 | 953,707,414 | 0 | $389.09 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 390 | 15.06 | 25.90 | 1742 | 0 | 27.82 | 0.00 | 3903 (97.6%) | $9.56 | 2/2/0 | 81346 |
| A | ace | 1 | 363 | 25.54 | 14.20 | 3374 | 0 | 69.65 | 0.00 | 3809 (95.2%) | $9.28 | 1/1/0 | 202369 |
| A | ace | 2 | 306 | 25.54 | 12.00 | 2594 | 0 | 48.49 | 0.00 | 3044 (76.1%) | $7.58 | 1/1/0 | 168398 |
| A | ao | 0 | 262 | 21.45 | 12.20 | 2687 | 1 | 24.74 | 0.00 | 3958 (99.0%) | $10.38 | 2/2/0 | 109553 |
| A | ao | 1 | 404 | 20.00 | 20.20 | 2547 | 1 | 15.96 | 0.00 | 991 (24.8%) | $2.92 | 2/2/0 | 41969 |
| A | ao | 2 | 380 | 20.58 | 18.50 | 2618 | 1 | 17.87 | 0.00 | 1602 (40.1%) | $4.47 | 2/2/0 | 51248 |
| A | evoskill | 0 | 332 | 12.28 | 27.00 | 1524 | 12 | 9.50 | 0.00 | 387 (9.7%) | $1.26 | 7/7/7 | 29773 |
| A | evoskill | 1 | 452 | 18.38 | 24.60 | 2601 | 18 | 21.31 | 0.00 | 786 (19.6%) | $2.33 | 10/10/8 | 48873 |
| A | evoskill | 2 | 452 | 17.10 | 26.40 | 2414 | 18 | 16.65 | 0.00 | 744 (18.6%) | $2.22 | 10/10/6 | 38475 |
| A | gepa | 0 | 600 | 26.07 | 23.00 | 2871 | 2 | 20.27 | 0.00 | 604 (15.1%) | $2.11 | 20/10/10 | 34796 |
| A | gepa | 1 | 600 | 29.11 | 20.60 | 3178 | 9 | 26.83 | 0.00 | 425 (10.6%) | $1.43 | 14/11/11 | 45421 |
| A | gepa | 2 | 600 | 25.77 | 23.30 | 2730 | 3 | 17.26 | 0.00 | 428 (10.7%) | $1.39 | 17/10/10 | 29487 |
| A | hc | 0 | 600 | 25.59 | 23.40 | 4992 | 4 | 36.77 | 0.00 | 207 (5.2%) | $0.81 | 5/9/1 | 61628 |
| A | hc | 1 | 600 | 21.20 | 28.30 | 3433 | 2 | 18.27 | 0.00 | 88 (2.2%) | $0.34 | 3/7/1 | 30603 |
| A | hc | 2 | 600 | 27.66 | 21.70 | 4340 | 15 | 30.39 | 0.00 | 649 (16.2%) | $2.47 | 14/13/0 | 51726 |
| A | metaharness | 0 | 600 | 19.61 | 30.60 | 3576 | 11 | 21.76 | 0.00 | 162 (4.0%) | $0.67 | 9/9/4 | 36536 |
| A | metaharness | 1 | 600 | 20.00 | 30.00 | 3619 | 6 | 22.76 | 0.00 | 175 (4.4%) | $0.77 | 9/9/5 | 38223 |
| A | metaharness | 2 | 600 | 22.39 | 26.80 | 3738 | 7 | 30.77 | 0.00 | 214 (5.4%) | $0.94 | 9/9/5 | 51645 |
| A | mipro | 0 | 401 | 37.53 | 10.70 | 8037 | 1 | 100.23 | 0.00 | 179 (4.5%) | $0.58 | 21/20/0 | 250389 |
| A | mipro | 1 | 459 | 37.51 | 12.20 | 8206 | 0 | 103.01 | 0.00 | 181 (4.5%) | $0.60 | 26/25/0 | 224817 |
| A | mipro | 2 | 461 | 37.52 | 12.30 | 8184 | 0 | 99.07 | 0.00 | 179 (4.5%) | $0.59 | 22/22/0 | 215289 |
| A | skillopt | 0 | 526 | 28.33 | 18.60 | 3385 | 7 | 26.21 | 0.00 | 3573 (89.3%) | $8.13 | 9/7/4 | 56626 |
| A | skillopt | 1 | 600 | 27.04 | 22.20 | 2894 | 5 | 26.80 | 0.00 | 4778 (119.5%) | $10.42 | 8/7/5 | 52636 |
| A | skillopt | 2 | 566 | 26.66 | 21.20 | 3276 | 13 | 27.16 | 0.00 | 5102 (127.6%) | $11.18 | 9/7/7 | 57000 |
| A | trace2skill | 0 | 200 | 15.63 | 12.80 | 1899 | 2 | 11.94 | 0.00 | 2202 (55.1%) | $6.82 | 3/3/0 | 70693 |
| A | trace2skill | 1 | 200 | 14.21 | 14.10 | 1668 | 13 | 8.30 | 0.00 | 2225 (55.6%) | $6.96 | 3/3/0 | 52636 |
| A | trace2skill | 2 | 200 | 16.14 | 12.40 | 1688 | 11 | 8.67 | 0.00 | 2086 (52.1%) | $6.49 | 3/3/0 | 53789 |
| A | wikiskill | 0 | 521 | 26.50 | 19.70 | 4196 | 0 | 31.71 | 0.00 | 779 (19.5%) | $1.21 | 5/5/3 | 62358 |
| A | wikiskill | 1 | 523 | 30.88 | 16.90 | 4411 | 0 | 51.18 | 0.00 | 862 (21.5%) | $1.31 | 5/5/3 | 99500 |
| A | wikiskill | 2 | 524 | 33.69 | 15.60 | 6599 | 0 | 82.98 | 0.00 | 881 (22.0%) | $1.40 | 5/5/4 | 160049 |
| A-E12 | hcstock | 0 | 600 | 16.97 | 35.40 | 3334 | 12 | 17.73 | 0.00 | 496 (12.4%) | $1.87 | 13/13/2 | 30383 |
| A-E12 | hcstock | 1 | 600 | 15.30 | 39.20 | 2888 | 12 | 14.98 | 0.00 | 534 (13.3%) | $2.16 | 13/13/2 | 25862 |
| A-E12 | hcstock | 2 | 600 | 15.39 | 39.00 | 2912 | 12 | 14.60 | 0.00 | 520 (13.0%) | $1.96 | 13/13/3 | 25203 |
| B | ao | 0 | 198 | 11.60 | 17.10 | 5078 | 37 | 19.59 | 2.19 | 1019 (25.5%) | $4.92 | 3/2/0 | 117217 |
| B | ao | 1 | 197 | 20.90 | 9.40 | 4795 | 27 | 19.01 | 2.09 | 843 (21.1%) | $4.70 | 2/1/0 | 113480 |
| B | ao | 2 | 613 | 37.90 | 16.20 | 19326 | 81 | 86.50 | 9.26 | 2229 (55.7%) | $9.64 | 1/0/0 | 162538 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 1530 | 4 | 5.45 | 0.67 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 1959 | 3 | 6.96 | 0.81 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 2682 | 30 | 11.77 | 1.02 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 973 | 5 | 3.93 | 0.41 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 941 | 7 | 3.59 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-gepa | 0 | n/a | n/a | n/a | 52 | 0 | 0.31 | 0.01 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-gepa | 1 | n/a | n/a | n/a | 304 | 1 | 1.46 | 0.12 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-hc | 0 | n/a | n/a | n/a | 859 | 4 | 3.09 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-hc | 1 | n/a | n/a | n/a | 900 | 1 | 3.28 | 0.43 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-hc | 2 | n/a | n/a | n/a | 774 | 1 | 2.72 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 6.51 | 15.00 | 2852 | 12 | 11.07 | 1.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 131225 |
| B | ctl-seed | 1 | 98 | 6.52 | 15.00 | 2762 | 6 | 10.66 | 1.39 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125731 |
| B | ctl-seed | 2 | 98 | 6.79 | 14.40 | 2914 | 9 | 11.40 | 1.53 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 134722 |
| B | gepa | 0 | 613 | 37.84 | 16.20 | 11526 | 39 | 62.34 | 5.51 | 998 (25.0%) | $3.67 | 37/37/13 | 114028 |
| B | gepa | 1 | 603 | 37.55 | 16.10 | 11077 | 38 | 56.95 | 5.63 | 990 (24.8%) | $3.60 | 39/39/13 | 107050 |
| B | gepa | 2 | 607 | 37.74 | 16.10 | 11201 | 58 | 54.25 | 5.36 | 884 (22.1%) | $3.06 | 37/37/13 | 101254 |
| B | harnesslens | 0 | 176 | 20.21 | 8.70 | 4652 | 0 | 27.92 | 4.09 | 8899 (222.5%) | $19.26 | 0/0/0 | 234310 |
| B | harnesslens | 1 | 173 | 17.53 | 9.90 | 4824 | 7 | 30.96 | 5.18 | 6845 (171.1%) | $14.64 | 0/0/0 | 250515 |
| B | harnesslens | 2 | 163 | 18.50 | 8.80 | 4483 | 4 | 28.52 | 4.30 | 8494 (212.4%) | $18.40 | 0/0/0 | 256122 |
| B | hc | 0 | 662 | 32.96 | 20.10 | 14005 | 47 | 59.78 | 7.28 | 348 (8.7%) | $2.01 | 3/2/0 | 103795 |
| B | hc | 1 | 564 | 27.27 | 20.70 | 11157 | 37 | 44.80 | 5.44 | 706 (17.6%) | $3.53 | 11/10/0 | 92212 |
| B | hc | 2 | 662 | 32.87 | 20.10 | 14112 | 39 | 60.39 | 8.16 | 249 (6.2%) | $1.46 | 3/2/0 | 105917 |
| B-E12 | hcstock | 0 | 343 | 10.52 | 32.60 | 7982 | 42 | 36.08 | 4.74 | 428 (10.7%) | $2.12 | 7/6/1 | 122309 |
| B-E12 | hcstock | 1 | 441 | 10.52 | 41.90 | 8713 | 37 | 36.77 | 4.87 | 497 (12.4%) | $2.63 | 9/8/0 | 97208 |
| B-E12 | hcstock | 2 | 392 | 10.52 | 37.30 | 8457 | 28 | 35.38 | 5.09 | 643 (16.1%) | $3.28 | 8/7/1 | 106557 |
| C | ao | 0 | 110 | 11.26 | 9.80 | 2495 | 3 | 10.37 | 1.40 | 554 (13.9%) | $2.75 | 1/0/0 | 112032 |
| C | ao | 1 | 110 | 7.70 | 14.30 | 2317 | 11 | 9.24 | 1.15 | 565 (14.1%) | $2.44 | 1/0/0 | 99610 |
| C | ao | 2 | 71 | 9.76 | 7.30 | 1370 | 3 | 5.06 | 0.66 | 523 (13.1%) | $1.97 | 2/1/0 | 87902 |
| C | chaser-ao | 0 | n/a | n/a | n/a | 334 | 0 | 1.06 | 0.16 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ao | 1 | n/a | n/a | n/a | 336 | 0 | 0.92 | 0.18 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ao | 2 | n/a | n/a | n/a | 368 | 1 | 0.99 | 0.21 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 278 | 0 | 1.19 | 0.16 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 330 | 1 | 1.22 | 0.20 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 249 | 0 | 0.91 | 0.14 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-hc | 0 | n/a | n/a | n/a | 321 | 0 | 1.15 | 0.22 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-hc | 2 | n/a | n/a | n/a | 271 | 0 | 0.83 | 0.13 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | ctl-oneshot | 0 | 60 | 5.67 | 10.60 | 1137 | 5 | 5.11 | 0.78 | 93 (2.3%) | $0.60 | 2/1/1 | 99713 |
| C | ctl-oneshot | 1 | 50 | 3.25 | 15.40 | 989 | 3 | 4.19 | 0.59 | 107 (2.7%) | $0.71 | 2/1/0 | 97669 |
| C | ctl-oneshot | 2 | 50 | 3.05 | 16.40 | 935 | 3 | 3.78 | 0.46 | 126 (3.1%) | $0.81 | 2/1/0 | 87286 |
| C | ctl-seed | 0 | 42 | 6.33 | 6.60 | 1256 | 9 | 4.88 | 0.71 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 133107 |
| C | ctl-seed | 1 | 40 | 4.05 | 9.90 | 999 | 0 | 3.50 | 0.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 100156 |
| C | ctl-seed | 2 | 42 | 5.32 | 7.90 | 1146 | 3 | 4.64 | 0.59 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 124557 |
| C | gepa | 0 | 382 | 32.20 | 11.90 | 6486 | 23 | 36.22 | 3.63 | 941 (23.5%) | $3.94 | 34/34/14 | 106786 |
| C | gepa | 1 | 297 | 32.19 | 9.20 | 5792 | 17 | 33.32 | 4.81 | 775 (19.4%) | $3.06 | 28/28/11 | 130995 |
| C | gepa | 2 | 369 | 32.19 | 11.50 | 6421 | 22 | 34.29 | 3.16 | 966 (24.2%) | $3.55 | 37/37/10 | 104088 |
| C | hc | 0 | 480 | 27.26 | 17.60 | 9534 | 33 | 42.60 | 4.86 | 794 (19.8%) | $3.72 | 11/10/1 | 100528 |
| C | hc | 1 | 460 | 32.20 | 14.30 | 11443 | 36 | 53.44 | 5.81 | 590 (14.7%) | $2.64 | 10/9/0 | 130078 |
| C | hc | 2 | 360 | 23.56 | 15.30 | 7066 | 31 | 30.22 | 3.49 | 658 (16.4%) | $3.13 | 11/10/1 | 95482 |
| C-E12 | bestofk | 0 | n/a | 13.58 | n/a | 3583 | 21 | 17.06 | 1.70 | 1328 (33.2%) | $8.78 | 7/6/0 | n/a |
| C-E12 | bestofk | 1 | n/a | 10.32 | n/a | 3192 | 28 | 15.27 | 1.48 | 1150 (28.8%) | $7.53 | 7/6/0 | n/a |
| C-E12 | bestofk | 2 | n/a | 10.31 | n/a | 3244 | 16 | 13.70 | 1.46 | 1172 (29.3%) | $7.79 | 8/7/0 | n/a |
| C-E12 | hcstock | 0 | 240 | 20.50 | 11.70 | 5217 | 18 | 24.95 | 2.73 | 664 (16.6%) | $3.14 | 11/10/1 | 118090 |
| C-E12 | hcstock | 1 | 230 | 16.81 | 13.70 | 4135 | 19 | 16.98 | 1.99 | 734 (18.4%) | $3.92 | 11/10/0 | 85660 |
| C-E12 | hcstock | 2 | 240 | 17.99 | 13.30 | 4595 | 25 | 20.54 | 2.58 | 749 (18.7%) | $3.58 | 11/10/2 | 99452 |
| D | CTL | 0 | 148 | 2.25 | 65.70 | 3022 | 74 | 10.59 | 1.00 | 110 (2.7%) | $0.68 | 2/1/1 | 80650 |
| D | CTL | 1 | 148 | 2.69 | 55.00 | 3453 | 54 | 12.68 | 1.20 | 102 (2.6%) | $0.65 | 2/1/1 | 96209 |
| D | CTL | 2 | 123 | 1.96 | 62.70 | 2750 | 56 | 10.24 | 0.88 | 113 (2.8%) | $0.69 | 2/1/0 | 93011 |
| D | GEPA | 0 | 564 | 8.11 | 69.50 | 12458 | 1378 | 55.98 | 3.33 | 643 (16.1%) | $2.58 | 26/26/14 | 107733 |
| D | GEPA | 1 | 575 | 8.10 | 71.00 | 12716 | 1535 | 51.47 | 3.39 | 666 (16.6%) | $2.40 | 30/30/14 | 98104 |
| D | GEPA | 2 | 556 | 8.23 | 67.50 | 12590 | 1365 | 47.96 | 3.60 | 756 (18.9%) | $2.61 | 34/34/12 | 95604 |
| D | NOHIST | 0 | 589 | 5.10 | 115.50 | 11913 | 165 | 46.55 | 3.84 | 972 (24.3%) | $6.26 | 11/10/2 | 88860 |
| D | NOHIST | 1 | 589 | 5.84 | 100.80 | 14529 | 1043 | 53.23 | 4.45 | 938 (23.5%) | $5.76 | 11/10/1 | 101213 |
| D | NOHIST | 2 | 589 | 6.24 | 94.30 | 16620 | 1529 | 73.35 | 4.90 | 913 (22.8%) | $5.98 | 11/10/2 | 136278 |
| D | P | 0 | 589 | 6.99 | 84.30 | 11370 | 90 | 50.40 | 3.66 | 528 (13.2%) | $2.52 | 11/10/3 | 94446 |
| D | P | 1 | 589 | 7.44 | 79.20 | 12124 | 106 | 50.36 | 3.89 | 478 (11.9%) | $2.18 | 11/10/1 | 94642 |
| D | P | 2 | 589 | 7.01 | 84.00 | 11374 | 80 | 43.81 | 3.70 | 500 (12.5%) | $2.27 | 11/10/1 | 83274 |
| D | PT | 0 | 589 | 7.37 | 80.00 | 11915 | 100 | 48.26 | 3.71 | 653 (16.3%) | $3.69 | 11/10/2 | 91118 |
| D | PT | 1 | 589 | 8.93 | 66.00 | 16384 | 1672 | 63.64 | 4.84 | 592 (14.8%) | $3.27 | 11/10/1 | 118892 |
| D | PT | 2 | 589 | 8.42 | 69.90 | 14214 | 1055 | 51.55 | 4.35 | 665 (16.6%) | $3.26 | 11/10/2 | 97763 |
| D | T | 0 | 589 | 9.41 | 62.60 | 19396 | 1995 | 65.09 | 6.29 | 624 (15.6%) | $3.76 | 11/10/1 | 123839 |
| D | T | 1 | 589 | 8.55 | 68.90 | 14853 | 1140 | 47.56 | 4.81 | 515 (12.9%) | $2.81 | 11/10/1 | 91557 |
| D | T | 2 | 564 | 7.31 | 77.20 | 12169 | 87 | 41.71 | 4.35 | 471 (11.8%) | $2.55 | 11/10/0 | 84265 |
| D-E21 | 1S | 0 | 589 | 7.44 | 79.20 | 13420 | 1068 | 49.39 | 4.31 | 537 (13.4%) | $2.64 | 11/10/2 | 93911 |
| D-E21 | 1S | 1 | 589 | 7.56 | 77.90 | 13491 | 1202 | 55.41 | 4.10 | 624 (15.6%) | $3.81 | 11/10/2 | 104066 |
| D-E21 | 1S | 2 | 589 | 8.15 | 72.30 | 16352 | 1839 | 62.09 | 4.78 | 563 (14.1%) | $3.25 | 11/10/2 | 116268 |
| D-E21 | ruleP | 0 | 687 | 7.83 | 87.80 | 13874 | 448 | 49.67 | 4.49 | 378 (9.5%) | $2.07 | 7/6/1 | 81259 |
| D-E21 | ruleP | 1 | 785 | 9.16 | 85.70 | 19106 | 2062 | 63.52 | 5.94 | 195 (4.9%) | $1.34 | 3/2/1 | 90479 |
| D-E21 | ruleP | 2 | 785 | 9.49 | 82.70 | 20911 | 2109 | 78.43 | 6.11 | 157 (3.9%) | $1.01 | 3/2/2 | 109659 |
| E | 1S | 0 | 240 | 1.98 | 121.30 | 7533 | 863 | 26.35 | 2.54 | 657 (16.4%) | $3.79 | 11/10/1 | 123088 |
| E | 1S | 1 | 230 | 2.08 | 110.70 | 7956 | 894 | 24.95 | 2.79 | 614 (15.4%) | $3.63 | 11/10/0 | 123285 |
| E | 1S | 2 | 240 | 1.99 | 120.80 | 7629 | 851 | 32.59 | 2.56 | 579 (14.5%) | $3.52 | 11/10/1 | 148871 |
| E | CTL | 0 | 50 | 0.37 | 136.10 | 1250 | 2 | 4.70 | 0.46 | 114 (2.8%) | $0.86 | 2/1/0 | 105498 |
| E | CTL | 1 | 60 | 0.41 | 147.10 | 1243 | 6 | 4.18 | 0.45 | 105 (2.6%) | $0.79 | 2/1/1 | 78958 |
| E | CTL | 2 | 60 | 0.42 | 142.80 | 1428 | 2 | 5.05 | 0.52 | 108 (2.7%) | $0.71 | 2/1/1 | 94616 |
| E | GEPA | 0 | 302 | 2.57 | 117.50 | 6581 | 724 | 30.08 | 2.01 | 704 (17.6%) | $2.71 | 27/27/12 | 108604 |
| E | GEPA | 1 | 309 | 2.53 | 122.10 | 6868 | 933 | 29.44 | 2.14 | 808 (20.2%) | $3.30 | 32/32/11 | 104801 |
| E | GEPA | 2 | 310 | 2.32 | 133.40 | 6558 | 799 | 28.42 | 1.91 | 770 (19.3%) | $2.97 | 29/29/12 | 100331 |
| E | NOHIST | 0 | 240 | 2.44 | 98.40 | 7798 | 225 | 30.45 | 2.98 | 853 (21.3%) | $5.81 | 11/10/1 | 142850 |
| E | NOHIST | 1 | 240 | 2.67 | 89.70 | 8670 | 572 | 34.54 | 2.89 | 799 (20.0%) | $5.28 | 11/10/1 | 159293 |
| E | NOHIST | 2 | 240 | 2.34 | 102.50 | 7133 | 101 | 32.71 | 2.79 | 848 (21.2%) | $5.78 | 11/10/1 | 151442 |
| E | P | 0 | 240 | 1.64 | 145.90 | 5152 | 553 | 18.81 | 1.79 | 475 (11.9%) | $2.27 | 11/10/1 | 87785 |
| E | P | 1 | 240 | 1.63 | 146.90 | 4790 | 484 | 19.05 | 1.62 | 600 (15.0%) | $2.95 | 11/10/3 | 88642 |
| E | P | 2 | 240 | 1.74 | 137.90 | 5145 | 471 | 20.03 | 1.61 | 566 (14.1%) | $2.74 | 11/10/1 | 92559 |
| E | PT | 0 | 240 | 2.70 | 88.90 | 8499 | 573 | 34.48 | 3.05 | 548 (13.7%) | $3.28 | 11/10/1 | 158642 |
| E | PT | 1 | 240 | 2.62 | 91.80 | 7259 | 454 | 30.81 | 2.64 | 811 (20.3%) | $5.01 | 11/10/1 | 142722 |
| E | PT | 2 | 230 | 2.71 | 84.80 | 7043 | 364 | 26.59 | 2.75 | 721 (18.0%) | $4.85 | 11/10/0 | 130700 |
| E | T | 0 | 240 | 2.67 | 90.00 | 8381 | 581 | 26.42 | 3.02 | 462 (11.6%) | $2.50 | 11/10/1 | 124582 |
| E | T | 1 | 240 | 2.66 | 90.20 | 8271 | 511 | 28.36 | 3.02 | 556 (13.9%) | $3.34 | 11/10/1 | 133082 |
| E | T | 2 | 240 | 2.95 | 81.50 | 9480 | 550 | 29.30 | 3.49 | 458 (11.4%) | $2.67 | 11/10/2 | 138542 |
| E | ace | 0 | 250 | 2.50 | 100.00 | 9460 | 3982 | 38.77 | 1.81 | 1344 (33.6%) | $3.84 | 4/4/0 | 167689 |
| E | ace | 1 | 264 | 2.49 | 106.00 | 9125 | 3506 | 41.44 | 2.07 | 1546 (38.7%) | $4.34 | 4/4/0 | 170678 |
| E | ace | 2 | 260 | 2.49 | 104.60 | 9099 | 3560 | 39.39 | 1.86 | 1474 (36.8%) | $4.16 | 4/4/0 | 164312 |
| E | ao | 0 | 30 | 0.15 | n/a | 620 | 77 | 1.59 | 0.21 | 52 (1.3%) | $0.20 | 1/0/0 | 61700 |
| E | ao | 1 | 30 | 0.15 | n/a | 672 | 132 | 1.66 | 0.20 | 25 (0.6%) | $0.12 | 1/0/0 | 62744 |
| E | ao | 2 | 30 | 0.15 | n/a | 653 | 133 | 1.55 | 0.19 | 24 (0.6%) | $0.11 | 1/0/0 | 58600 |
| E | gepafull | 0 | 232 | 2.48 | 93.60 | 8112 | 3244 | 28.89 | 1.53 | 680 (17.0%) | $2.88 | 21/21/8 | 134049 |
| E | gepafull | 1 | 260 | 2.47 | 105.10 | 8225 | 3227 | 24.70 | 1.64 | 784 (19.6%) | $3.31 | 26/26/9 | 104344 |
| E | gepafull | 2 | 238 | 2.47 | 96.50 | 8132 | 3368 | 23.57 | 1.56 | 641 (16.0%) | $2.85 | 21/21/9 | 108284 |
| E | mipro | 0 | 215 | 1.34 | 160.80 | 3789 | 569 | 12.39 | 1.10 | 90 (2.3%) | $0.29 | 27/27/0 | 63148 |
| E | mipro | 1 | 219 | 1.45 | 151.10 | 4042 | 688 | 12.85 | 1.15 | 101 (2.5%) | $0.33 | 27/27/0 | 64371 |
| E | mipro | 2 | 213 | 1.31 | 162.10 | 3689 | 535 | 11.99 | 1.11 | 108 (2.7%) | $0.33 | 24/24/0 | 62008 |
| E | ruleP | 0 | 320 | 2.55 | 125.60 | 7553 | 517 | 27.41 | 2.69 | 551 (13.8%) | $3.49 | 9/8/1 | 95783 |
| E | ruleP | 1 | 320 | 2.87 | 111.40 | 9643 | 572 | 35.68 | 3.61 | 455 (11.4%) | $2.70 | 9/8/1 | 124199 |
| E | ruleP | 2 | 400 | 3.16 | 126.70 | 10347 | 507 | 42.68 | 3.52 | 546 (13.7%) | $3.78 | 7/6/1 | 116857 |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 140556 | 140556 | 150704 | 3585165 | $8.81 |
| A | ao | 3 | 60331 | 60331 | 67590 | 2183859 | $5.92 |
| A | evoskill | 3 | 37523 | 37523 | 39040 | 639069 | $1.94 |
| A | gepa | 3 | 35759 | 35759 | 36568 | 485347 | $1.64 |
| A | hc | 3 | 47462 | 47462 | 47986 | 314561 | $1.20 |
| A | metaharness | 3 | 41829 | 41829 | 42135 | 183746 | $0.79 |
| A | mipro | 3 | 229755 | 229755 | 230165 | 179642 | $0.59 |
| A | skillopt | 3 | 47498 | 47498 | 55421 | 4484300 | $9.91 |
| A | trace2skill | 3 | 48184 | 48184 | 59039 | 2171196 | $6.76 |
| A | wikiskill | 3 | 105694 | 105694 | 107302 | 840733 | $1.31 |
| A-E12 | hcstock | 3 | 26288 | 26288 | 27149 | 516847 | $2.00 |
| B | ao | 3 | 112182 | 124428 | 131078 | 1363451 | $6.42 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 112694 | 127767 | 130559 | 0 | n/a |
| B | gepa | 3 | 95170 | 104222 | 107444 | 957590 | $3.44 |
| B | harnesslens | 3 | 170851 | 197368 | 246982 | 8079410 | $17.44 |
| B | hc | 3 | 86989 | 97978 | 100641 | 434218 | $2.33 |
| B-E12 | hcstock | 3 | 92934 | 105550 | 108691 | 522447 | $2.68 |
| C | ao | 3 | 83174 | 94001 | 99848 | 547361 | $2.39 |
| C | ctl-oneshot | 3 | 81484 | 92818 | 94889 | 108744 | $0.71 |
| C | ctl-seed | 3 | 104711 | 119273 | 119273 | 0 | n/a |
| C | gepa | 3 | 99977 | 111393 | 113956 | 894008 | $3.51 |
| C | hc | 3 | 96291 | 107108 | 108696 | 680493 | $3.17 |
| C-E12 | hcstock | 3 | 87791 | 98041 | 101067 | 715696 | $3.54 |
| D | CTL | 3 | 80170 | 87504 | 89957 | 108463 | $0.67 |
| D | GEPA | 3 | 91673 | 97761 | 100480 | 688231 | $2.53 |
| D | NOHIST | 3 | 97979 | 105442 | 108784 | 941011 | $6.00 |
| D | P | 3 | 81820 | 88185 | 90787 | 501732 | $2.32 |
| D | PT | 3 | 92501 | 99799 | 102591 | 636510 | $3.40 |
| D | T | 3 | 88402 | 97255 | 99887 | 536656 | $3.04 |
| D-E21 | 1S | 3 | 94446 | 101910 | 104748 | 574431 | $3.23 |
| D-E21 | ruleP | 3 | 84374 | 91665 | 93799 | 243325 | $1.48 |
| E | 1S | 3 | 118015 | 129142 | 131748 | 616692 | $3.65 |
| E | CTL | 3 | 82570 | 91083 | 93024 | 108871 | $0.79 |
| E | GEPA | 3 | 95520 | 102103 | 104579 | 760458 | $2.99 |
| E | NOHIST | 3 | 135687 | 147723 | 151195 | 833201 | $5.62 |
| E | P | 3 | 80412 | 87383 | 89662 | 547058 | $2.65 |
| E | PT | 3 | 129206 | 141088 | 144021 | 693381 | $4.38 |
| E | T | 3 | 116787 | 130018 | 132069 | 492061 | $2.84 |
| E | ace | 3 | 154519 | 161925 | 167560 | 1454706 | $4.11 |
| E | ao | 3 | 53316 | 59883 | 61015 | 33950 | $0.14 |
| E | gepafull | 3 | 106186 | 112678 | 115559 | 701940 | $3.01 |
| E | mipro | 3 | 57533 | 62713 | 63176 | 99829 | $0.32 |
| E | ruleP | 3 | 101276 | 110777 | 112280 | 517391 | $3.32 |

## Overhead / waste (not in main tables; included in campaign totals)

| suite | arm | seed | category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---|---|---|---:|---:|---:|---:|
| B | hlext | all | no_run_dir | 4,068 | 44,955,887 | 28,867,330 | $27.84 |
| D-null | E22-null-c2 | all | smoke | 10,274 | 38,185,227 | 0 | $14.52 |
| D-null | E22-null-c0 | all | smoke | 10,270 | 38,041,398 | 0 | $14.55 |
| D-null | E22-null-c3 | all | smoke | 10,156 | 37,728,179 | 0 | $14.43 |
| D-null | E22-null-c1 | all | smoke | 10,138 | 37,552,110 | 0 | $14.43 |
| - | E00-azprobe | all | smoke | 8,292 | 34,823,214 | 0 | $17.39 |
| B | ao | all | restart_waste | 5,408 | 26,206,898 | 25,761,808 | $3.08 |
| B | hc | all | restart_waste | 4,476 | 21,189,920 | 20,850,489 | $2.04 |
| A | ace | all | restart_waste | 1,422 | 20,069,279 | 17,265,529 | $7.18 |
| B | ctl-oneshot | all | restart_waste | 4,210 | 19,472,780 | 19,160,701 | $1.95 |
| B | gepa | all | restart_waste | 3,214 | 14,958,308 | 14,814,038 | $0.48 |
| B | ctl-seed | all | restart_waste | 2,967 | 13,337,661 | 13,337,661 | $0.00 |
| B-E12 | hcstock | all | restart_waste | 1,894 | 7,837,233 | 7,691,095 | $0.00 |
| B | ao | all | pilot | 1,161 | 5,524,975 | 5,168,526 | $1.30 |
| A | metaharness | all | restart_waste | 705 | 4,245,257 | 4,245,257 | $0.00 |
| - | E00-azprobe-air | all | smoke | 1,148 | 3,899,213 | 0 | $1.38 |
| A | ao | all | restart_waste | 636 | 3,811,054 | 3,811,054 | $0.00 |
| A | hc | all | restart_waste | 615 | 3,410,547 | 3,410,547 | $0.00 |
| - | E26test-NOHIST-s99 | all | smoke | 885 | 3,164,034 | 0 | $1.20 |
| B | hl-trial | all | no_run_dir | 363 | 3,007,425 | 2,419,795 | $1.69 |
| B | hc | all | pilot | 619 | 2,777,762 | 2,641,597 | $0.54 |
| - | E00-azprobe-air41 | all | smoke | 704 | 2,574,104 | 0 | $2.83 |
| A | evoskill | all | restart_waste | 804 | 2,573,286 | 2,573,286 | $0.00 |
| B | gepa | all | pilot | 466 | 2,297,765 | 2,241,304 | $0.20 |
| - | FE-dry-hl | all | smoke | 305 | 2,192,207 | 2,192,207 | $0.00 |
| - | BL-gepa-smoke2 | all | smoke | 147 | 2,176,130 | 2,130,636 | $0.16 |
| - | BLsmoke-mipro-s0 | all | smoke | 458 | 1,806,342 | 1,734,479 | $0.22 |
| A | graphskillevo | all | stopped | 185 | 1,645,251 | 1,594,615 | $0.41 |
| - | FE-smoke-D-ctl-s0 | all | smoke | 232 | 1,164,283 | 0 | $0.32 |
| - | E26test-NOHIST-s97 | all | smoke | 304 | 1,116,597 | 0 | $0.79 |
| - | BL-wikiskill-smoke | all | smoke | 129 | 1,096,254 | 880,221 | $0.25 |
| - | BLsmoke-ace-s0 | all | smoke | 227 | 993,458 | 984,260 | $0.03 |
| - | SEdev-GEPA-s0 | all | smoke | 257 | 986,757 | 0 | $0.52 |
| - | E26test-NOHIST-s98 | all | smoke | 235 | 924,885 | 0 | $0.62 |
| - | FE-smoke-D-decomp-decomp-ctl-Ponly-s0 | all | smoke | 55 | 792,240 | 0 | $0.13 |
| B | smoke | all | smoke | 175 | 762,980 | 757,621 | $0.02 |
| - | BL-memento-smoke | all | smoke | 47 | 677,221 | 677,221 | $0.00 |
| - | BL-hl-smoke2 | all | smoke | 82 | 590,486 | 590,486 | $0.00 |
| A | E10-evosmoke | all | smoke | 78 | 578,784 | 578,784 | $0.00 |
| - | E32smoke-mipro-s0 | all | smoke | 178 | 561,788 | 0 | $0.36 |
| A | mipro | all | restart_waste | 109 | 556,849 | 556,849 | $0.00 |
| - | BL-mipro-smoke | all | smoke | 111 | 547,128 | 485,025 | $0.21 |
| - | BL-hl-smoke4 | all | smoke | 60 | 523,503 | 385,699 | $0.35 |
| - | SEdev-GEPA-s1 | all | smoke | 152 | 495,578 | 0 | $0.35 |
| B | ahe | all | smoke | 120 | 485,969 | 485,969 | $0.00 |
| - | E10E-hl-trial-s9 | all | smoke | 177 | 482,620 | 0 | $0.78 |
| A | ahe | all | smoke | 85 | 481,688 | 125,707 | $0.80 |
| - | BL-probe | all | smoke | 53 | 466,907 | 466,907 | $0.00 |
| - | E3xsmoke-mipro-s0 | all | smoke | 168 | 462,859 | 0 | $0.30 |
| A | smoke | all | smoke | 74 | 434,649 | 406,397 | $0.09 |
| A | rho | all | no_run_dir | 87 | 427,805 | 273,517 | $0.33 |
| - | BL-trace2skill-smoke | all | smoke | 62 | 378,630 | 159,469 | $0.70 |
| - | SEdev-GEPA-s2 | all | smoke | 101 | 356,352 | 0 | $0.28 |
| - | FE-dry-C-seed-s0 | all | smoke | 87 | 332,151 | 332,151 | $0.00 |
| A | mce | all | stopped | 111 | 328,338 | 328,338 | $0.00 |
| A | hc | all | smoke | 72 | 314,102 | 263,711 | $0.16 |
| - | untagged | all | untagged | 51 | 312,041 | 0 | $1.26 |
| - | BL-ace-smoke | all | smoke | 188 | 308,024 | 171,903 | $0.45 |
| - | E32smoke-ace-s0 | all | smoke | 94 | 301,113 | 0 | $0.17 |
| - | BL-hl-smoke5 | all | smoke | 28 | 296,477 | 94,782 | $0.57 |
| - | E3xsmoke-ace-s0 | all | smoke | 101 | 287,400 | 0 | $0.17 |
| - | BL-hl-smoke6 | all | smoke | 47 | 275,473 | 275,473 | $0.00 |
| - | BL-mce-smoke | all | smoke | 75 | 256,348 | 129,161 | $0.54 |
| - | E32-hl-fe-dry | all | smoke | 40 | 223,976 | 0 | $0.06 |
| - | FE-dry-B-hl-v0-s0 | all | smoke | 42 | 216,811 | 216,811 | $0.00 |
| - | BL-hl-smoke | all | smoke | 26 | 203,616 | 200,905 | $0.01 |
| - | FE-smoke-C-dry-canary-s0 | all | smoke | 52 | 196,485 | 0 | $0.22 |
| - | FE-dry-C-gepa-s1 | all | smoke | 43 | 192,071 | 192,071 | $0.00 |
| - | FE-smoke-B-dry-seed-s0 | all | smoke | 58 | 186,527 | 0 | $0.18 |
| - | FE-smoke-E-gepa-s1 | all | smoke | 43 | 185,231 | 0 | $0.06 |
| A | E10-cfprobe | all | smoke | 86 | 180,158 | 0 | $0.77 |
| - | BL-skillopt-smoke | all | smoke | 44 | 176,669 | 142,711 | $0.11 |
| - | BL-gepa-smoke | all | smoke | 56 | 169,581 | 169,581 | $0.00 |
| A | memento | all | stopped | 82 | 165,440 | 165,440 | $0.00 |
| - | FE-dry-B-hl-v0-nl-s0 | all | smoke | 21 | 159,778 | 154,127 | $0.00 |
| - | FE-dry-B-seed-s0 | all | smoke | 43 | 158,962 | 158,962 | $0.00 |
| - | SEdev-GEPA-s3 | all | smoke | 49 | 145,385 | 0 | $0.09 |
| - | FE-smoke-B-dry-oneshot-s0 | all | smoke | 33 | 135,702 | 0 | $0.18 |
| - | FE-smoke-C-dry-seed-s0 | all | smoke | 46 | 127,819 | 0 | $0.14 |
| - | FE-dry-B-gepa-s1 | all | smoke | 31 | 126,706 | 126,706 | $0.00 |
| - | FE-smoke-B-dry-gepa-end-s0 | all | smoke | 27 | 124,370 | 0 | $0.15 |
| - | BL-hl-smoke3 | all | smoke | 23 | 121,156 | 121,156 | $0.00 |
| - | BL-metaharness-smoke | all | smoke | 43 | 119,562 | 94,330 | $0.10 |
| - | FE-smoke-D-decomp-decomp-ctl-Ponly-s1 | all | smoke | 26 | 118,951 | 0 | $0.04 |
| - | FE-smoke-B-dry-oneshot-s2 | all | smoke | 33 | 117,678 | 0 | $0.14 |
| - | FE-smoke-D-ctl-s2 | all | smoke | 23 | 112,159 | 0 | $0.04 |
| - | FE-smoke-B-dry-gepa-s2 | all | smoke | 33 | 108,960 | 0 | $0.11 |
| - | FE-smoke-B-dry-gepa-s0 | all | smoke | 33 | 108,721 | 0 | $0.11 |
| - | FE-smoke-D-pt-s0 | all | smoke | 30 | 106,600 | 0 | $0.03 |
| - | FE-smoke-B-dry-gepa-end-s1 | all | smoke | 24 | 103,215 | 0 | $0.13 |
| - | FE-smoke-C-dry-gepa-s2 | all | smoke | 27 | 101,298 | 0 | $0.13 |
| C | E10C-s0-trial | all | smoke | 27 | 96,218 | 96,218 | $0.00 |
| - | FE-dry-B-gepa-s0 | all | smoke | 27 | 96,111 | 96,111 | $0.00 |
| - | FE-smoke-B-dry-canary-s0 | all | smoke | 28 | 86,660 | 0 | $0.11 |
| - | FE-smoke-B-dry-oneshot-s1 | all | smoke | 22 | 86,505 | 0 | $0.10 |
| A | E10-evomock | all | smoke | 11 | 84,378 | 0 | $0.28 |
| - | FE-dry-C-gepa-s0 | all | smoke | 19 | 81,537 | 81,537 | $0.00 |
| - | FE-smoke-D-decomp-decomp-ctl-Tonly-s0 | all | smoke | 22 | 81,072 | 0 | $0.03 |
| - | FE-dry-E-hl-v0-s0 | all | smoke | 18 | 79,883 | 0 | $0.03 |
| - | FE-smoke-D-decomp-decomp-ctl-Tonly-s1 | all | smoke | 19 | 78,007 | 0 | $0.03 |
| - | FE-smoke-D-ctl-s1 | all | smoke | 19 | 77,312 | 0 | $0.03 |
| - | BL-graphskillevo-smoke | all | smoke | 18 | 76,722 | 51,846 | $0.14 |
| - | FE-smoke-B-dry-gepa-s1 | all | smoke | 23 | 76,650 | 0 | $0.10 |
| - | FE-smoke-C-dry-gepa-s1 | all | smoke | 19 | 73,477 | 0 | $0.09 |
| - | FE-smoke-D-pt-s1 | all | smoke | 18 | 72,423 | 0 | $0.03 |
| - | FE-smoke-E-seed-s0 | all | smoke | 20 | 72,362 | 0 | $0.02 |
| - | FE-dry-B-gepa-s2 | all | smoke | 17 | 69,042 | 69,042 | $0.00 |
| A | E10-evoptest | all | smoke | 7 | 66,659 | 0 | $0.21 |
| A | evoskill-r2 | all | no_run_dir | 36 | 63,013 | 63,013 | $0.00 |
| - | FE-smoke-E-gepa-s2 | all | smoke | 19 | 62,724 | 0 | $0.03 |
| - | FE-smoke-C-dry-gepa-s0 | all | smoke | 22 | 62,376 | 0 | $0.08 |
| - | BL-memento-smokefake | all | smoke | 12 | 62,318 | 0 | $0.34 |
| - | FE-smoke-A-dry-skillopt-end-s2 | all | smoke | 6 | 51,710 | 0 | $0.03 |
| - | FE-dry-C-gepa-s2 | all | smoke | 15 | 51,201 | 51,201 | $0.00 |
| - | FE-smoke-A-dry-gepa-s0 | all | smoke | 13 | 51,023 | 0 | $0.04 |
| - | FE-smoke-A-dry-seed-s0 | all | smoke | 13 | 45,378 | 0 | $0.03 |
| - | FE-smoke-A-dry-skillopt-end-s1 | all | smoke | 6 | 42,988 | 0 | $0.02 |
| - | E00 | all | smoke | 6 | 41,475 | 41,475 | $0.00 |
| - | FE-dry-A-seed-s0 | all | smoke | 13 | 36,939 | 36,939 | $0.00 |
| - | FE-smoke-A-dry-gepa-end-s1 | all | smoke | 7 | 33,968 | 0 | $0.02 |
| A | E10-egressprobe | all | smoke | 7 | 31,676 | 0 | $0.09 |
| - | FE-smoke-A-dry-gepa-end-s0 | all | smoke | 6 | 30,703 | 0 | $0.02 |
| - | FE-smoke-A-dry-gepa-end-s2 | all | smoke | 6 | 30,691 | 0 | $0.02 |
| B | sbxtest | all | smoke | 1 | 30,614 | 0 | $0.08 |
| A | E10-tagprobe-api | all | smoke | 1 | 30,596 | 0 | $0.08 |
| C | negtest | all | smoke | 2 | 29,015 | 0 | $0.07 |
| - | FE-smoke-A-dry-gepa-s1 | all | smoke | 9 | 27,707 | 0 | $0.02 |
| A | E10-metaharness-smoke | all | smoke | 1 | 26,893 | 0 | $0.07 |
| A | E10-tagprobe-auth | all | smoke | 1 | 26,880 | 0 | $0.07 |
| - | FE-smoke-A-dry-skillopt-s0 | all | smoke | 7 | 25,564 | 0 | $0.02 |
| - | BL-diag51090 | all | smoke | 4 | 24,773 | 24,773 | $0.00 |
| A | E10-mh-negtest | all | smoke | 13 | 23,268 | 0 | $0.08 |
| - | FE-smoke-A-dry-skillopt-s1 | all | smoke | 6 | 21,292 | 0 | $0.02 |
| - | FE-dry-A-gepa-s1 | all | smoke | 9 | 21,264 | 21,264 | $0.00 |
| - | FE-smoke-A-dry-skillopt-s2 | all | smoke | 6 | 20,774 | 0 | $0.02 |
| - | FE-smoke-A-dry-gepa-s2 | all | smoke | 7 | 19,961 | 0 | $0.01 |
| A | injtest | all | smoke | 8 | 18,291 | 13,056 | $0.02 |
| - | FE-dry-A-gepa-s0 | all | smoke | 8 | 17,483 | 17,483 | $0.00 |
| - | FE-smoke-A-dry-canary-s0 | all | smoke | 6 | 11,268 | 0 | $0.01 |
| - | FE-dry-A-gepa-s2 | all | smoke | 5 | 10,262 | 10,262 | $0.00 |
| A | E10-tagprobe5 | all | smoke | 4 | 5,684 | 0 | $0.14 |
| - | BL-metrtest | all | smoke | 3 | 4,993 | 4,993 | $0.00 |
| A | E10-evodiag | all | smoke | 3 | 4,993 | 4,993 | $0.00 |
| - | BL-preflight | all | smoke | 3 | 4,847 | 4,847 | $0.00 |
| - | BL-egress | all | smoke | 3 | 4,843 | 4,843 | $0.00 |
| A | E10-evowd | all | smoke | 6 | 2,880 | 2,880 | $0.00 |
| - | BL-hl-egress | all | smoke | 1 | 2,711 | 0 | $0.01 |
| - | E01 | all | smoke | 25 | 2,161 | 294 | $0.02 |
| B | judgetest | all | smoke | 1 | 369 | 0 | $0.00 |
| - | BL-hl-chk | all | smoke | 1 | 100 | 100 | $0.00 |
| - | BL-hl-check | all | smoke | 3 | 91 | 91 | $0.00 |
| - | E00-webstrip-test | all | smoke | 1 | 65 | 0 | $0.00 |
| A | E10-evodiag2 | all | smoke | 2 | 46 | 46 | $0.00 |
| - | FE-smoke-probe-s0 | all | smoke | 3 | 28 | 0 | $0.00 |
| A | E10-memento-smoke | all | smoke | 1 | 28 | 0 | $0.00 |
| D | devcheck | all | no_run_dir | 2 | 20 | 0 | $0.00 |
| B | probe | all | smoke | 5 | 12 | 0 | $0.00 |
| - | E00-azonly-test | all | smoke | 1 | 11 | 0 | $0.00 |
| A | E10-tagprobe3 | all | smoke | 2 | 7 | 0 | $0.00 |

Restart cutoffs used (gateway calls before this time with the run's tag are counted as restart_waste):

- A/ace/s0: 2026-10-12T00:59:23Z (derived: birth time of launcher.log)
- A/ace/s1: 2026-10-12T00:59:23Z (derived: birth time of launcher.log)
- A/ace/s2: 2026-10-12T00:59:23Z (derived: birth time of launcher.log)
- A/ao/s0: 2026-10-11T14:41:25Z (derived: birth time of manifest/negtest.txt)
- A/evoskill/s0: 2026-10-11T18:28:13Z (derived: birth time of negtest_before_launch.txt)
- A/evoskill/s1: 2026-10-11T18:28:13Z (derived: birth time of negtest_before_launch.txt)
- A/evoskill/s2: 2026-10-11T18:28:13Z (derived: birth time of negtest_before_launch.txt)
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
- B-E12/hcstock/s0: 2026-10-12T16:01:28Z (derived: birth time of manifest.json)
- B-E12/hcstock/s1: 2026-10-12T16:01:28Z (derived: birth time of manifest.json)
- B-E12/hcstock/s2: 2026-10-12T16:01:28Z (derived: birth time of manifest.json)

## Data-quality notes

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/injtest/s0, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, B/harnesslens/s0, B/harnesslens/s1, B/harnesslens/s2, B/harnesslens_ext/s0, B/harnesslens_ext_prefix_defect/s0, B/harnesslens_prefix_defect/s0, B/harnesslens_prefix_defect/s2, B/harnesslens_superseded_v0/s0, B/harnesslens_superseded_v0/s1, B/harnesslens_superseded_v0/s2, C-E12/bestofk/s0, C-E12/bestofk/s1, C-E12/bestofk/s2, C-E12/bestofk_pipeline_test_k1/s0
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
