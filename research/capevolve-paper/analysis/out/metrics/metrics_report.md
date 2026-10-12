# Campaign metrics report

Generated 2026-10-12T16:48:32Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-12T16:48:44Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 320588 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 2,048,464,317 | 1,823,303,211 | 225,161,106 |
| rits_tokens | 1,929,113,562 | 1,503,797,967 | 425,315,595 |
| capped_tokens (non-RITS) | 117,257,910 | 79,049,687 | 38,208,223 |
| calls | 320588 | 320588 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 190737}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 613,719 | 4,541 | 3,327,579,486 | 3,327,388,749 | 1,930,182,835 | 117,314,942 | $806.89 lb | 1,938,988,422 |
| suite - | 54,942 | 661 | 251,370,065 | 251,226,001 | 26,712,733 | 5,267,714 | $106.90 lb | 26,948,063 |
| suite A | 95,891 | 230 | 863,506,786 | 863,460,113 | 818,946,929 | 44,513,184 | $117.17 lb | 818,946,929 |
| suite A-E12 | 9,134 | 36 | 48,868,783 | 48,868,783 | 47,318,243 | 1,550,540 | $6.00 lb | 47,318,243 |
| suite B | 139,263 | 551 | 745,757,447 | 745,757,447 | 699,197,930 | 46,559,517 | $106.28 lb | 707,768,187 |
| suite C | 44,063 | 147 | 223,213,492 | 223,213,492 | 218,384,205 | 4,829,287 | $21.99 lb | 218,384,205 |
| suite C-E12 | 23,770 | 126 | 125,420,095 | 125,420,095 | 119,622,795 | 5,797,300 | $34.73 lb | 119,622,795 |
| suite D | 137,384 | 1,347 | 612,690,880 | 612,690,880 | 0 | 6,546,772 | $237.81 lb | 0 |
| suite D-E21 | 68,434 | 795 | 305,245,024 | 305,245,024 | 0 | 2,250,628 | $118.09 lb | 0 |
| suite D-null | 40,838 | 648 | 151,506,914 | 151,506,914 | 0 | 0 | $57.93 lb | 0 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 54,891 | 250,913,960 | 26,712,733 | $105.63 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A-E12|main | 9,134 | 48,868,783 | 47,318,243 | $6.00 |
| A|main | 90,637 | 823,852,334 | 783,263,910 | $106.40 |
| A|no_run_dir | 123 | 490,818 | 336,530 | $0.33 |
| A|restart_waste | 4,291 | 34,666,272 | 31,862,522 | $7.18 |
| A|smoke | 462 | 2,311,660 | 1,395,574 | $2.85 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 8,376 | 36,477,839 | 36,006,780 | $0.00 |
| B|main | 105,430 | 576,843,444 | 539,606,615 | $82.13 |
| B|no_run_dir | 2,634 | 25,390,151 | 18,364,821 | $14.46 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C-E12|main | 23,770 | 125,420,095 | 119,622,795 | $34.73 |
| C|chaser_eval | 1,895 | 7,343,177 | 7,343,177 | $0.00 |
| C|main | 42,139 | 215,745,082 | 210,944,810 | $21.92 |
| C|smoke | 29 | 125,233 | 96,218 | $0.07 |
| D-E21|main | 68,434 | 305,245,024 | 0 | $118.09 |
| D-null|smoke | 40,838 | 151,506,914 | 0 | $57.93 |
| D|main | 137,382 | 612,690,860 | 0 | $237.81 |
| D|no_run_dir | 2 | 20 | 0 | $0.00 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 390 | 15.06 | 25.90 | 1742 | 0 | 27.82 | 0.00 | 3903 (97.6%) | $9.56 | 2/2/0 | 81346 |
| A | ace | 1 | 181 | 15.81 | 11.40 | 1525 | 0 | 21.69 | 0.00 | 1772 (44.3%) | $4.59 | 0/0/0 | 129608 |
| A | ace | 2 | 149 | 15.77 | 9.40 | 1501 | 0 | 21.70 | 0.00 | 1346 (33.7%) | $3.58 | 0/0/0 | 154662 |
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
| A | hc | 2 | 534 | 26.12 | 20.40 | 3910 | 13 | 27.59 | 0.00 | 544 (13.6%) | $2.10 | 12/10/0 | 52681 |
| A | metaharness | 0 | 600 | 19.61 | 30.60 | 3576 | 11 | 21.76 | 0.00 | 162 (4.0%) | $0.67 | 9/9/4 | 36536 |
| A | metaharness | 1 | 600 | 20.00 | 30.00 | 3619 | 6 | 22.76 | 0.00 | 175 (4.4%) | $0.77 | 9/9/5 | 38223 |
| A | metaharness | 2 | 600 | 22.39 | 26.80 | 3738 | 7 | 30.77 | 0.00 | 214 (5.4%) | $0.94 | 9/9/5 | 51645 |
| A | mipro | 0 | 221 | 27.78 | 8.00 | 4059 | 1 | 50.55 | 0.00 | 179 (4.5%) | $0.58 | 10/10/0 | 229525 |
| A | mipro | 1 | 273 | 27.77 | 9.80 | 4397 | 0 | 53.09 | 0.00 | 181 (4.5%) | $0.60 | 15/14/0 | 195123 |
| A | mipro | 2 | 221 | 27.78 | 8.00 | 4252 | 0 | 50.19 | 0.00 | 179 (4.5%) | $0.59 | 10/9/0 | 227920 |
| A | skillopt | 0 | 526 | 28.33 | 18.60 | 3385 | 7 | 26.21 | 0.00 | 3573 (89.3%) | $8.13 | 9/7/4 | 56626 |
| A | skillopt | 1 | 600 | 27.04 | 22.20 | 2894 | 5 | 26.80 | 0.00 | 4778 (119.5%) | $10.42 | 8/7/5 | 52636 |
| A | skillopt | 2 | 566 | 26.66 | 21.20 | 3276 | 13 | 27.16 | 0.00 | 5102 (127.6%) | $11.18 | 9/7/7 | 57000 |
| A | trace2skill | 0 | 200 | 15.63 | 12.80 | 1899 | 2 | 11.94 | 0.00 | 2202 (55.1%) | $6.82 | 3/3/0 | 70693 |
| A | trace2skill | 1 | 200 | 14.21 | 14.10 | 1668 | 13 | 8.30 | 0.00 | 2225 (55.6%) | $6.96 | 3/3/0 | 52636 |
| A | trace2skill | 2 | 200 | 16.14 | 12.40 | 1688 | 11 | 8.67 | 0.00 | 2086 (52.1%) | $6.49 | 3/3/0 | 53789 |
| A | wikiskill | 0 | 521 | 26.50 | 19.70 | 4196 | 0 | 31.71 | 0.00 | 779 (19.5%) | $1.21 | 5/5/3 | 62358 |
| A | wikiskill | 1 | 426 | 27.76 | 15.30 | 3483 | 0 | 38.27 | 0.00 | 629 (15.7%) | $0.96 | 4/4/3 | 91320 |
| A | wikiskill | 2 | 364 | 27.77 | 13.10 | 4234 | 0 | 50.84 | 0.00 | 339 (8.5%) | $0.60 | 3/3/2 | 140607 |
| A-E12 | hcstock | 0 | 600 | 16.97 | 35.40 | 3334 | 12 | 17.73 | 0.00 | 496 (12.4%) | $1.87 | 13/13/2 | 30383 |
| A-E12 | hcstock | 1 | 600 | 15.30 | 39.20 | 2888 | 12 | 14.98 | 0.00 | 534 (13.3%) | $2.16 | 13/13/2 | 25862 |
| A-E12 | hcstock | 2 | 600 | 15.39 | 39.00 | 2912 | 12 | 14.60 | 0.00 | 520 (13.0%) | $1.96 | 13/13/3 | 25203 |
| B | ao | 0 | 198 | 11.60 | 17.10 | 5078 | 37 | 19.59 | 2.19 | 1019 (25.5%) | $4.92 | 3/2/0 | 117217 |
| B | ao | 1 | 197 | 20.90 | 9.40 | 4795 | 27 | 19.01 | 2.09 | 843 (21.1%) | $4.70 | 2/1/0 | 113480 |
| B | ao | 2 | 172 | 28.17 | 6.10 | 10181 | 42 | 45.32 | 4.62 | 1500 (37.5%) | $7.74 | 1/0/0 | 303299 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 1530 | 4 | 5.45 | 0.67 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 1113 | 2 | 3.89 | 0.47 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 2682 | 30 | 11.77 | 1.02 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 973 | 5 | 3.93 | 0.41 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 941 | 7 | 3.59 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-hc | 1 | n/a | n/a | n/a | 438 | 1 | 1.54 | 0.18 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 6.51 | 15.00 | 2852 | 12 | 11.07 | 1.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 131225 |
| B | ctl-seed | 1 | 98 | 6.52 | 15.00 | 2762 | 6 | 10.66 | 1.39 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125731 |
| B | ctl-seed | 2 | 98 | 6.79 | 14.40 | 2914 | 9 | 11.40 | 1.53 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 134722 |
| B | gepa | 0 | 338 | 28.15 | 12.00 | 6425 | 34 | 32.31 | 3.15 | 574 (14.4%) | $2.07 | 21/21/6 | 108380 |
| B | gepa | 1 | 389 | 28.17 | 13.80 | 6887 | 30 | 33.83 | 3.28 | 532 (13.3%) | $1.92 | 22/22/8 | 98296 |
| B | gepa | 2 | 344 | 28.16 | 12.20 | 6388 | 43 | 29.39 | 3.13 | 567 (14.2%) | $1.93 | 24/24/6 | 97800 |
| B | harnesslens | 0 | 123 | 18.54 | 6.60 | 4275 | 0 | 25.68 | 3.76 | 6948 (173.7%) | $15.66 | 0/0/0 | 298188 |
| B | harnesslens | 1 | 173 | 17.53 | 9.90 | 4824 | 7 | 30.96 | 5.18 | 6845 (171.1%) | $14.64 | 0/0/0 | 250515 |
| B | harnesslens | 2 | 163 | 18.50 | 8.80 | 4483 | 4 | 28.52 | 4.30 | 8494 (212.4%) | $18.40 | 0/0/0 | 256122 |
| B | hc | 0 | 490 | 28.16 | 17.40 | 11756 | 43 | 50.62 | 6.22 | 348 (8.7%) | $2.01 | 3/2/0 | 118952 |
| B | hc | 1 | 564 | 27.27 | 20.70 | 11157 | 37 | 44.80 | 5.44 | 706 (17.6%) | $3.53 | 11/10/0 | 92212 |
| B | hc | 2 | 490 | 28.16 | 17.40 | 11851 | 36 | 50.92 | 6.71 | 249 (6.2%) | $1.46 | 3/2/0 | 120384 |
| C | ao | 0 | 110 | 11.26 | 9.80 | 2495 | 3 | 10.37 | 1.40 | 554 (13.9%) | $2.75 | 1/0/0 | 112032 |
| C | ao | 1 | 110 | 7.70 | 14.30 | 2317 | 11 | 9.24 | 1.15 | 565 (14.1%) | $2.44 | 1/0/0 | 99610 |
| C | ao | 2 | 71 | 9.76 | 7.30 | 1370 | 3 | 5.06 | 0.66 | 523 (13.1%) | $1.97 | 2/1/0 | 87902 |
| C | chaser-ao | 0 | n/a | n/a | n/a | 334 | 0 | 1.06 | 0.16 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ao | 1 | n/a | n/a | n/a | 336 | 0 | 0.92 | 0.18 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ao | 2 | n/a | n/a | n/a | 368 | 1 | 0.99 | 0.21 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 278 | 0 | 1.19 | 0.16 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 330 | 1 | 1.22 | 0.20 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 249 | 0 | 0.91 | 0.14 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | ctl-oneshot | 0 | 60 | 5.67 | 10.60 | 1137 | 5 | 5.11 | 0.78 | 93 (2.3%) | $0.60 | 2/1/1 | 99713 |
| C | ctl-oneshot | 1 | 50 | 3.25 | 15.40 | 989 | 3 | 4.19 | 0.59 | 107 (2.7%) | $0.71 | 2/1/0 | 97669 |
| C | ctl-oneshot | 2 | 50 | 3.05 | 16.40 | 935 | 3 | 3.78 | 0.46 | 126 (3.1%) | $0.81 | 2/1/0 | 87286 |
| C | ctl-seed | 0 | 42 | 6.33 | 6.60 | 1256 | 9 | 4.88 | 0.71 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 133107 |
| C | ctl-seed | 1 | 40 | 4.05 | 9.90 | 999 | 0 | 3.50 | 0.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 100156 |
| C | ctl-seed | 2 | 42 | 5.32 | 7.90 | 1146 | 3 | 4.64 | 0.59 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 124557 |
| C | gepa | 0 | 207 | 22.46 | 9.20 | 3366 | 15 | 17.01 | 1.77 | 431 (10.8%) | $1.77 | 18/17/8 | 92792 |
| C | gepa | 1 | 166 | 22.46 | 7.40 | 3145 | 4 | 16.89 | 2.65 | 400 (10.0%) | $1.58 | 16/15/6 | 120105 |
| C | gepa | 2 | 203 | 22.45 | 9.00 | 3410 | 9 | 15.91 | 1.73 | 508 (12.7%) | $1.85 | 21/20/6 | 89427 |
| C | hc | 0 | 320 | 22.45 | 14.30 | 7011 | 25 | 31.34 | 3.61 | 450 (11.3%) | $2.38 | 4/3/1 | 110627 |
| C | hc | 1 | 240 | 22.46 | 10.70 | 5906 | 22 | 27.64 | 2.99 | 385 (9.6%) | $1.91 | 6/5/0 | 129242 |
| C | hc | 2 | 320 | 22.46 | 14.30 | 6657 | 29 | 28.54 | 3.25 | 658 (16.4%) | $3.13 | 10/9/1 | 101397 |
| C-E12 | bestofk | 0 | n/a | 13.58 | n/a | 3583 | 21 | 17.06 | 1.70 | 1328 (33.2%) | $8.78 | 7/6/0 | n/a |
| C-E12 | bestofk | 1 | n/a | 10.32 | n/a | 3192 | 28 | 15.27 | 1.48 | 1150 (28.8%) | $7.53 | 7/6/0 | n/a |
| C-E12 | bestofk | 2 | n/a | 10.31 | n/a | 3244 | 16 | 13.70 | 1.46 | 1172 (29.3%) | $7.79 | 8/7/0 | n/a |
| C-E12 | hcstock | 0 | 220 | 19.76 | 11.10 | 5021 | 17 | 24.31 | 2.55 | 664 (16.6%) | $3.14 | 11/10/1 | 125119 |
| C-E12 | hcstock | 1 | 230 | 16.81 | 13.70 | 4135 | 19 | 16.98 | 1.99 | 734 (18.4%) | $3.92 | 11/10/0 | 85660 |
| C-E12 | hcstock | 2 | 240 | 17.99 | 13.30 | 4595 | 25 | 20.54 | 2.58 | 749 (18.7%) | $3.58 | 11/10/2 | 99452 |
| D | CTL | 0 | 148 | 2.25 | 65.70 | 3022 | 74 | 10.59 | 1.00 | 110 (2.7%) | $0.68 | 2/1/1 | 80650 |
| D | CTL | 1 | 148 | 2.69 | 55.00 | 3453 | 54 | 12.68 | 1.20 | 102 (2.6%) | $0.65 | 2/1/1 | 96209 |
| D | CTL | 2 | 123 | 1.96 | 62.70 | 2750 | 56 | 10.24 | 0.88 | 113 (2.8%) | $0.69 | 2/1/0 | 93011 |
| D | GEPA | 0 | 402 | 6.43 | 62.60 | 7930 | 85 | 39.16 | 2.38 | 433 (10.8%) | $1.77 | 17/17/10 | 105820 |
| D | GEPA | 1 | 394 | 6.42 | 61.30 | 7728 | 79 | 34.58 | 2.34 | 487 (12.2%) | $1.76 | 21/21/9 | 96479 |
| D | GEPA | 2 | 393 | 6.42 | 61.20 | 7899 | 85 | 32.68 | 2.48 | 463 (11.6%) | $1.58 | 21/21/9 | 92252 |
| D | P | 0 | 589 | 6.99 | 84.30 | 11370 | 90 | 50.40 | 3.66 | 528 (13.2%) | $2.52 | 11/10/3 | 94446 |
| D | P | 1 | 589 | 7.44 | 79.20 | 12122 | 106 | 50.36 | 3.89 | 478 (11.9%) | $2.18 | 11/10/1 | 94627 |
| D | P | 2 | 589 | 7.01 | 84.00 | 11374 | 80 | 43.81 | 3.70 | 500 (12.5%) | $2.27 | 11/10/1 | 83274 |
| D | PT | 0 | 589 | 7.37 | 80.00 | 11915 | 100 | 48.26 | 3.71 | 653 (16.3%) | $3.69 | 11/10/2 | 91118 |
| D | PT | 1 | 392 | 7.44 | 52.70 | 11195 | 117 | 48.44 | 3.64 | 498 (12.5%) | $2.92 | 8/7/1 | 135892 |
| D | PT | 2 | 490 | 7.44 | 65.80 | 11308 | 124 | 44.09 | 3.70 | 665 (16.6%) | $3.26 | 10/9/2 | 100696 |
| D | T | 0 | 392 | 7.44 | 52.70 | 11657 | 116 | 43.82 | 4.14 | 558 (14.0%) | $3.40 | 8/7/0 | 125495 |
| D | T | 1 | 441 | 7.44 | 59.30 | 11490 | 94 | 39.48 | 4.01 | 488 (12.2%) | $2.71 | 9/8/1 | 101716 |
| D | T | 2 | 564 | 7.31 | 77.20 | 12169 | 87 | 41.71 | 4.35 | 471 (11.8%) | $2.55 | 11/10/0 | 84265 |
| D-E21 | 1S | 0 | 441 | 6.42 | 68.60 | 10453 | 103 | 41.50 | 3.64 | 500 (12.5%) | $2.47 | 9/8/1 | 105566 |
| D-E21 | 1S | 1 | 441 | 6.42 | 68.70 | 10115 | 147 | 45.22 | 3.32 | 585 (14.6%) | $3.64 | 9/8/2 | 113620 |
| D-E21 | 1S | 2 | 392 | 6.42 | 61.00 | 10335 | 145 | 43.84 | 3.36 | 435 (10.9%) | $2.44 | 8/7/1 | 123359 |
| D-E21 | ruleP | 0 | 637 | 7.44 | 85.60 | 12864 | 137 | 47.27 | 4.26 | 378 (9.5%) | $2.07 | 7/6/1 | 83432 |
| D-E21 | ruleP | 1 | 441 | 7.44 | 59.30 | 12315 | 132 | 46.87 | 4.18 | 195 (4.9%) | $1.34 | 2/1/0 | 118449 |
| D-E21 | ruleP | 2 | 441 | 7.44 | 59.30 | 12352 | 131 | 49.73 | 4.04 | 157 (3.9%) | $1.01 | 2/1/1 | 124366 |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 112261 | 112261 | 121872 | 2340390 | $5.91 |
| A | ao | 3 | 60331 | 60331 | 67590 | 2183859 | $5.92 |
| A | evoskill | 3 | 37523 | 37523 | 39040 | 639069 | $1.94 |
| A | gepa | 3 | 35759 | 35759 | 36568 | 485347 | $1.64 |
| A | hc | 3 | 47801 | 47801 | 48304 | 279398 | $1.08 |
| A | metaharness | 3 | 41829 | 41829 | 42135 | 183746 | $0.79 |
| A | mipro | 3 | 216762 | 216762 | 217523 | 179642 | $0.59 |
| A | skillopt | 3 | 47498 | 47498 | 55421 | 4484300 | $9.91 |
| A | trace2skill | 3 | 48184 | 48184 | 59039 | 2171196 | $6.76 |
| A | wikiskill | 3 | 96794 | 96794 | 98095 | 582526 | $0.92 |
| A-E12 | hcstock | 3 | 26288 | 26288 | 27149 | 516847 | $2.00 |
| B | ao | 3 | 152967 | 169140 | 177999 | 1120548 | $5.79 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 112694 | 127767 | 130559 | 0 | n/a |
| B | gepa | 3 | 89326 | 98270 | 101492 | 557510 | $1.97 |
| B | harnesslens | 3 | 187565 | 216520 | 268275 | 7428973 | $16.24 |
| B | hc | 3 | 95557 | 107571 | 110516 | 434218 | $2.33 |
| C | ao | 3 | 83174 | 94001 | 99848 | 547361 | $2.39 |
| C | ctl-oneshot | 3 | 81484 | 92818 | 94889 | 108744 | $0.71 |
| C | ctl-seed | 3 | 104711 | 119273 | 119273 | 0 | n/a |
| C | gepa | 3 | 87429 | 98444 | 100775 | 446308 | $1.73 |
| C | hc | 3 | 100763 | 112066 | 113755 | 497678 | $2.48 |
| C-E12 | hcstock | 3 | 89976 | 100300 | 103410 | 715696 | $3.54 |
| D | CTL | 3 | 80170 | 87504 | 89957 | 108463 | $0.67 |
| D | GEPA | 3 | 89451 | 95507 | 98184 | 461091 | $1.70 |
| D | P | 3 | 81816 | 88180 | 90782 | 501732 | $2.32 |
| D | PT | 3 | 98495 | 106203 | 109235 | 605277 | $3.29 |
| D | T | 3 | 91761 | 100883 | 103825 | 505694 | $2.88 |
| D-E21 | 1S | 3 | 102828 | 110948 | 114182 | 506884 | $2.85 |
| D-E21 | ruleP | 3 | 97753 | 106193 | 108749 | 243325 | $1.48 |

## Overhead / waste (not in main tables; included in campaign totals)

| suite | arm | seed | category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---|---|---|---:|---:|---:|---:|
| - | E26-nohist-s2 | all | smoke | 11,672 | 63,550,544 | 0 | $24.21 |
| - | E26-nohist-s0 | all | smoke | 11,723 | 51,848,364 | 0 | $23.78 |
| - | E26-nohist-s1 | all | smoke | 11,637 | 51,267,961 | 0 | $23.06 |
| D-null | E22-null-c2 | all | smoke | 10,274 | 38,185,227 | 0 | $14.52 |
| D-null | E22-null-c0 | all | smoke | 10,270 | 38,041,398 | 0 | $14.55 |
| D-null | E22-null-c3 | all | smoke | 10,156 | 37,728,179 | 0 | $14.43 |
| D-null | E22-null-c1 | all | smoke | 10,138 | 37,552,110 | 0 | $14.43 |
| - | E00-azprobe | all | smoke | 8,292 | 34,823,214 | 0 | $17.39 |
| B | ao | all | restart_waste | 5,408 | 26,206,898 | 25,761,808 | $3.08 |
| B | hlext | all | no_run_dir | 2,271 | 22,382,726 | 15,945,026 | $12.76 |
| B | hc | all | restart_waste | 4,476 | 21,189,920 | 20,850,489 | $2.04 |
| A | ace | all | restart_waste | 1,422 | 20,069,279 | 17,265,529 | $7.18 |
| B | ctl-oneshot | all | restart_waste | 4,210 | 19,472,780 | 19,160,701 | $1.95 |
| B | gepa | all | restart_waste | 3,214 | 14,958,308 | 14,814,038 | $0.48 |
| B | ctl-seed | all | restart_waste | 2,967 | 13,337,661 | 13,337,661 | $0.00 |
| B | ao | all | pilot | 1,161 | 5,524,975 | 5,168,526 | $1.30 |
| - | E12B-hcstock-s1 | all | smoke | 1,090 | 4,476,607 | 4,398,572 | $0.00 |
| - | E12B-hcstock-s0 | all | smoke | 1,059 | 4,353,511 | 4,274,497 | $0.00 |
| - | E12B-hcstock-s2 | all | smoke | 1,030 | 4,327,753 | 4,255,123 | $0.00 |
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
| - | BL-ace-smoke | all | smoke | 186 | 308,024 | 171,903 | $0.45 |
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

## Data-quality notes

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/injtest/s0, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, B/harnesslens/s0, B/harnesslens/s1, B/harnesslens/s2, B/harnesslens_ext/s0, B/harnesslens_ext_prefix_defect/s0, B/harnesslens_prefix_defect/s0, B/harnesslens_prefix_defect/s2, B/harnesslens_superseded_v0/s0, B/harnesslens_superseded_v0/s1, B/harnesslens_superseded_v0/s2, C-E12/bestofk/s0, C-E12/bestofk/s1, C-E12/bestofk/s2, C-E12/bestofk_pipeline_test_k1/s0
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
