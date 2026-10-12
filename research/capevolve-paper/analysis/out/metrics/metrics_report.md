# Campaign metrics report

Generated 2026-10-12T02:15:33Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-12T02:15:34Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 176489 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 984,104,175 | 983,952,873 | 151,302 |
| rits_tokens | 942,907,542 | 942,796,047 | 111,495 |
| capped_tokens (non-RITS) | 39,103,788 | 41,156,826 | -2,053,038 |
| calls | 176489 | 176489 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 190737}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 176,640 | 842 | 985,176,156 | 984,985,419 | 943,782,923 | 41,202,496 | $124.39 lb | 951,609,635 |
| suite - | 3,254 | 128 | 17,456,779 | 17,312,715 | 13,527,432 | 3,785,283 | $5.47 lb | 15,620,277 |
| suite A | 45,733 | 170 | 336,019,166 | 335,972,493 | 316,435,444 | 19,537,049 | $54.19 lb | 316,435,444 |
| suite A-E12 | 2,282 | 0 | 15,734,056 | 15,734,056 | 15,734,056 | 0 | $0.00 lb | 15,734,056 |
| suite B | 97,821 | 419 | 479,801,366 | 479,801,366 | 466,613,223 | 13,188,143 | $38.32 lb | 472,347,090 |
| suite C | 22,566 | 90 | 110,062,661 | 110,062,661 | 107,314,854 | 2,747,807 | $14.12 lb | 107,314,854 |
| suite C-E12 | 4,984 | 35 | 26,102,128 | 26,102,128 | 24,157,914 | 1,944,214 | $12.29 lb | 24,157,914 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 3,203 | 17,000,674 | 13,527,432 | $4.20 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A-E12|main | 2,282 | 15,734,056 | 15,734,056 | $0.00 |
| A|main | 40,487 | 296,383,005 | 280,765,481 | $43.44 |
| A|no_run_dir | 123 | 490,818 | 336,530 | $0.33 |
| A|restart_waste | 4,291 | 34,666,272 | 31,862,522 | $7.18 |
| A|smoke | 454 | 2,293,369 | 1,382,518 | $2.83 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 7,641 | 33,516,168 | 33,093,341 | $0.00 |
| B|main | 66,994 | 336,231,760 | 325,880,373 | $26.94 |
| B|no_run_dir | 363 | 3,007,425 | 2,419,795 | $1.69 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C-E12|main | 4,984 | 26,102,128 | 24,157,914 | $12.29 |
| C|chaser_eval | 999 | 4,142,480 | 4,142,480 | $0.00 |
| C|main | 21,538 | 105,794,948 | 103,076,156 | $14.05 |
| C|smoke | 29 | 125,233 | 96,218 | $0.07 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 18 | 1.27 | 14.20 | 94 | 0 | 0.59 | 0.00 | 90 (2.3%) | $0.29 | 0/0/0 | 37643 |
| A | ace | 1 | 7 | 1.23 | 5.70 | 106 | 0 | 1.10 | 0.00 | 39 (1.0%) | $0.11 | 0/0/0 | 162643 |
| A | ace | 2 | 13 | 1.25 | 10.40 | 131 | 0 | 0.93 | 0.00 | 78 (1.9%) | $0.23 | 0/0/0 | 77688 |
| A | ao | 0 | 120 | 9.25 | 13.00 | 1043 | 0 | 7.70 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 64203 |
| A | ao | 1 | 120 | 9.44 | 12.70 | 1017 | 0 | 7.28 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 60677 |
| A | ao | 2 | 120 | 11.43 | 10.50 | 1119 | 0 | 9.24 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 76969 |
| A | evoskill | 0 | 196 | 7.78 | 25.20 | 955 | 6 | 5.23 | 0.00 | 203 (5.1%) | $0.64 | 4/4/4 | 27727 |
| A | evoskill | 1 | 167 | 7.78 | 21.50 | 999 | 6 | 6.29 | 0.00 | 240 (6.0%) | $0.72 | 3/3/3 | 39086 |
| A | evoskill | 2 | 100 | 7.76 | 12.90 | 848 | 2 | 6.30 | 0.00 | 68 (1.7%) | $0.20 | 2/2/2 | 63634 |
| A | gepa | 0 | 356 | 17.90 | 19.90 | 1757 | 2 | 10.21 | 0.00 | 179 (4.5%) | $0.66 | 9/7/7 | 29183 |
| A | gepa | 1 | 255 | 17.90 | 14.20 | 1481 | 9 | 10.98 | 0.00 | 92 (2.3%) | $0.32 | 5/5/5 | 43404 |
| A | gepa | 2 | 444 | 17.90 | 24.80 | 1815 | 3 | 9.69 | 0.00 | 278 (7.0%) | $0.90 | 13/8/8 | 22452 |
| A | hc | 0 | 160 | 11.55 | 13.90 | 1461 | 1 | 10.79 | 0.00 | 57 (1.4%) | $0.21 | 2/1/0 | 67792 |
| A | hc | 1 | 251 | 11.58 | 21.70 | 1442 | 1 | 8.81 | 0.00 | 49 (1.2%) | $0.16 | 2/2/0 | 35284 |
| A | hc | 2 | 160 | 11.56 | 13.80 | 1456 | 1 | 10.82 | 0.00 | 46 (1.1%) | $0.22 | 2/1/0 | 67927 |
| A | metaharness | 0 | 327 | 15.32 | 21.30 | 2345 | 9 | 16.02 | 0.00 | 85 (2.1%) | $0.35 | 5/3/3 | 49261 |
| A | metaharness | 1 | 351 | 15.31 | 22.90 | 2470 | 4 | 15.09 | 0.00 | 104 (2.6%) | $0.45 | 5/4/2 | 43288 |
| A | metaharness | 2 | 360 | 15.31 | 23.50 | 2390 | 5 | 16.45 | 0.00 | 100 (2.5%) | $0.44 | 5/4/3 | 45983 |
| A | mipro | 0 | 83 | 13.24 | 6.30 | 996 | 1 | 9.20 | 0.00 | 179 (4.5%) | $0.58 | 2/2/0 | 112963 |
| A | mipro | 1 | 92 | 13.21 | 7.00 | 984 | 0 | 9.47 | 0.00 | 181 (4.5%) | $0.60 | 4/3/0 | 104922 |
| A | mipro | 2 | 88 | 13.23 | 6.70 | 1083 | 0 | 10.35 | 0.00 | 179 (4.5%) | $0.59 | 4/3/0 | 119683 |
| A | skillopt | 0 | 278 | 17.90 | 15.50 | 2050 | 7 | 13.98 | 0.00 | 1794 (44.9%) | $4.22 | 4/4/1 | 56732 |
| A | skillopt | 1 | 360 | 17.87 | 20.10 | 1843 | 5 | 13.62 | 0.00 | 2438 (61.0%) | $5.48 | 4/4/4 | 44616 |
| A | skillopt | 2 | 286 | 17.88 | 16.00 | 1928 | 13 | 15.36 | 0.00 | 2400 (60.0%) | $5.39 | 4/4/3 | 62093 |
| A | trace2skill | 0 | 200 | 15.63 | 12.80 | 1899 | 2 | 11.94 | 0.00 | 2202 (55.1%) | $6.82 | 3/3/0 | 70693 |
| A | trace2skill | 1 | 200 | 14.21 | 14.10 | 1668 | 13 | 8.30 | 0.00 | 2225 (55.6%) | $6.96 | 3/3/0 | 52636 |
| A | trace2skill | 2 | 200 | 16.14 | 12.40 | 1688 | 11 | 8.67 | 0.00 | 2086 (52.1%) | $6.49 | 3/3/0 | 53789 |
| A | wikiskill | 0 | 120 | 13.19 | 9.10 | 1181 | 0 | 9.10 | 0.00 | 44 (1.1%) | $0.12 | 1/1/1 | 76199 |
| A | wikiskill | 1 | 126 | 13.21 | 9.50 | 1089 | 0 | 7.54 | 0.00 | 178 (4.5%) | $0.30 | 2/1/1 | 61257 |
| A | wikiskill | 2 | 120 | 13.20 | 9.10 | 1149 | 0 | 9.72 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 80988 |
| A-E12 | hcstock | 0 | 99 | 4.85 | 20.40 | 768 | 0 | 5.19 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 52474 |
| A-E12 | hcstock | 1 | 92 | 4.85 | 19.00 | 761 | 0 | 5.35 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 58176 |
| A-E12 | hcstock | 2 | 85 | 4.85 | 17.50 | 753 | 0 | 5.19 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 61022 |
| B | ao | 0 | 198 | 11.60 | 17.10 | 5078 | 37 | 19.59 | 2.19 | 1019 (25.5%) | $4.92 | 3/2/0 | 117217 |
| B | ao | 1 | 123 | 13.60 | 9.00 | 4044 | 27 | 16.36 | 1.79 | 763 (19.1%) | $4.43 | 1/0/0 | 156548 |
| B | ao | 2 | 123 | 13.61 | 9.00 | 6076 | 15 | 26.25 | 2.77 | 929 (23.2%) | $6.13 | 1/0/0 | 246051 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 1233 | 4 | 4.39 | 0.54 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 1113 | 2 | 3.89 | 0.47 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 2682 | 30 | 11.77 | 1.02 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 973 | 5 | 3.93 | 0.41 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 941 | 7 | 3.59 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 6.51 | 15.00 | 2852 | 12 | 11.07 | 1.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 131225 |
| B | ctl-seed | 1 | 98 | 6.52 | 15.00 | 2762 | 6 | 10.66 | 1.39 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125731 |
| B | ctl-seed | 2 | 98 | 6.79 | 14.40 | 2914 | 9 | 11.40 | 1.53 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 134722 |
| B | gepa | 0 | 220 | 13.61 | 16.20 | 4012 | 19 | 19.48 | 1.87 | 234 (5.9%) | $0.84 | 10/10/5 | 99843 |
| B | gepa | 1 | 231 | 13.61 | 17.00 | 3646 | 12 | 16.39 | 1.75 | 282 (7.0%) | $1.00 | 13/13/4 | 81168 |
| B | gepa | 2 | 196 | 13.60 | 14.40 | 3498 | 19 | 15.77 | 1.54 | 339 (8.5%) | $1.17 | 14/14/3 | 91615 |
| B | harnesslens | 0 | 99 | 3.99 | 24.80 | 1501 | 0 | 9.57 | 1.24 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 110629 |
| B | harnesslens | 1 | 98 | 3.99 | 24.50 | 1504 | 2 | 9.53 | 1.16 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 110434 |
| B | harnesslens | 2 | 100 | 3.99 | 25.00 | 1560 | 3 | 9.46 | 1.01 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 106306 |
| B | hc | 0 | 147 | 13.59 | 10.80 | 6153 | 22 | 27.04 | 3.01 | 278 (6.9%) | $1.65 | 2/1/0 | 210086 |
| B | hc | 1 | 294 | 13.61 | 21.60 | 6240 | 26 | 25.64 | 2.92 | 528 (13.2%) | $2.73 | 6/5/0 | 100925 |
| B | hc | 2 | 245 | 13.60 | 18.00 | 6352 | 27 | 27.78 | 3.81 | 154 (3.9%) | $0.92 | 1/0/0 | 131914 |
| C | ao | 0 | 60 | 7.90 | 7.60 | 2185 | 3 | 9.14 | 1.08 | 313 (7.8%) | $2.04 | 1/0/0 | 175474 |
| C | ao | 1 | 110 | 7.70 | 14.30 | 2317 | 11 | 9.24 | 1.15 | 565 (14.1%) | $2.44 | 1/0/0 | 99610 |
| C | ao | 2 | 41 | 7.90 | 5.20 | 1104 | 2 | 4.10 | 0.52 | 354 (8.8%) | $1.54 | 1/0/0 | 121510 |
| C | chaser-ao | 0 | n/a | n/a | n/a | 32 | 0 | 0.05 | 0.01 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ao | 1 | n/a | n/a | n/a | 75 | 0 | 0.16 | 0.02 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ao | 2 | n/a | n/a | n/a | 35 | 0 | 0.07 | 0.01 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 278 | 0 | 1.19 | 0.16 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 330 | 1 | 1.22 | 0.20 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 249 | 0 | 0.91 | 0.14 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| C | ctl-oneshot | 0 | 60 | 5.67 | 10.60 | 1137 | 5 | 5.11 | 0.78 | 93 (2.3%) | $0.60 | 2/1/1 | 99713 |
| C | ctl-oneshot | 1 | 50 | 3.25 | 15.40 | 989 | 3 | 4.19 | 0.59 | 107 (2.7%) | $0.71 | 2/1/0 | 97669 |
| C | ctl-oneshot | 2 | 50 | 3.05 | 16.40 | 935 | 3 | 3.78 | 0.46 | 126 (3.1%) | $0.81 | 2/1/0 | 87286 |
| C | ctl-seed | 0 | 42 | 6.33 | 6.60 | 1256 | 9 | 4.88 | 0.71 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 133107 |
| C | ctl-seed | 1 | 40 | 4.05 | 9.90 | 999 | 0 | 3.50 | 0.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 100156 |
| C | ctl-seed | 2 | 42 | 5.32 | 7.90 | 1146 | 3 | 4.64 | 0.59 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 124557 |
| C | gepa | 0 | 76 | 7.91 | 9.60 | 1272 | 6 | 5.34 | 0.75 | 144 (3.6%) | $0.57 | 7/6/3 | 82126 |
| C | gepa | 1 | 54 | 7.84 | 6.90 | 1089 | 3 | 5.25 | 0.79 | 94 (2.3%) | $0.37 | 5/4/2 | 113635 |
| C | gepa | 2 | 73 | 7.90 | 9.20 | 1177 | 4 | 5.03 | 0.55 | 136 (3.4%) | $0.50 | 7/6/2 | 78365 |
| C | hc | 0 | 60 | 7.90 | 7.60 | 2136 | 17 | 9.65 | 1.08 | 234 (5.9%) | $1.44 | 2/1/0 | 182706 |
| C | hc | 1 | 60 | 7.87 | 7.60 | 1738 | 5 | 8.50 | 0.93 | 229 (5.7%) | $1.35 | 3/2/0 | 161030 |
| C | hc | 2 | 100 | 7.90 | 12.70 | 2058 | 14 | 9.20 | 1.02 | 324 (8.1%) | $1.68 | 5/4/0 | 105461 |
| C-E12 | bestofk | 0 | n/a | 4.71 | n/a | 726 | 12 | 2.76 | 0.29 | 483 (12.1%) | $2.97 | 1/0/0 | n/a |
| C-E12 | bestofk | 1 | n/a | 1.44 | n/a | 368 | 3 | 1.50 | 0.13 | 338 (8.4%) | $2.29 | 1/0/0 | n/a |
| C-E12 | bestofk | 2 | n/a | 1.44 | n/a | 409 | 6 | 1.60 | 0.14 | 320 (8.0%) | $2.16 | 1/0/0 | n/a |
| C-E12 | hcstock | 0 | 40 | 5.20 | 7.70 | 1149 | 4 | 5.71 | 0.52 | 238 (6.0%) | $1.39 | 2/1/1 | 161660 |
| C-E12 | hcstock | 1 | 40 | 5.20 | 7.70 | 1085 | 7 | 4.52 | 0.48 | 246 (6.2%) | $1.68 | 2/1/0 | 131189 |
| C-E12 | hcstock | 2 | 60 | 5.21 | 11.50 | 1247 | 3 | 5.70 | 0.81 | 320 (8.0%) | $1.81 | 3/2/2 | 113852 |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 87123 | 87123 | 92658 | 69047 | $0.21 |
| A | ao | 3 | 67283 | 67283 | 67283 | 0 | n/a |
| A | evoskill | 3 | 42429 | 42429 | 43482 | 170609 | $0.52 |
| A | gepa | 3 | 31182 | 31182 | 31680 | 183284 | $0.62 |
| A | hc | 3 | 56720 | 56720 | 57001 | 50855 | $0.19 |
| A | metaharness | 3 | 45899 | 45899 | 46177 | 96216 | $0.41 |
| A | mipro | 3 | 110470 | 110470 | 112523 | 179642 | $0.59 |
| A | skillopt | 3 | 47274 | 47274 | 54480 | 2210877 | $5.03 |
| A | trace2skill | 3 | 48184 | 48184 | 59039 | 2171196 | $6.76 |
| A | wikiskill | 3 | 72221 | 72221 | 72815 | 74116 | $0.21 |
| A-E12 | hcstock | 3 | 57224 | 57224 | 57224 | 0 | n/a |
| B | ao | 3 | 148466 | 164504 | 173272 | 903813 | $5.16 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 112694 | 127767 | 130559 | 0 | n/a |
| B | gepa | 3 | 79987 | 87975 | 90875 | 285074 | $1.00 |
| B | harnesslens | 3 | 96167 | 107626 | 109123 | 0 | n/a |
| B | hc | 3 | 128184 | 143502 | 147642 | 319935 | $1.77 |
| C | ao | 3 | 112127 | 125874 | 132198 | 410352 | $2.01 |
| C | ctl-oneshot | 3 | 81484 | 92818 | 94889 | 108744 | $0.71 |
| C | ctl-seed | 3 | 104711 | 119273 | 119273 | 0 | n/a |
| C | gepa | 3 | 78799 | 89547 | 91375 | 124387 | $0.48 |
| C | hc | 3 | 131489 | 146074 | 149732 | 262782 | $1.49 |
| C-E12 | hcstock | 3 | 116888 | 129754 | 135567 | 268053 | $1.62 |

## Overhead / waste (not in main tables; included in campaign totals)

| suite | arm | seed | category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---|---|---|---:|---:|---:|---:|
| B | ao | all | restart_waste | 5,408 | 26,206,898 | 25,761,808 | $3.08 |
| B | hc | all | restart_waste | 4,476 | 21,189,920 | 20,850,489 | $2.04 |
| A | ace | all | restart_waste | 1,422 | 20,069,279 | 17,265,529 | $7.18 |
| B | ctl-oneshot | all | restart_waste | 4,210 | 19,472,780 | 19,160,701 | $1.95 |
| B | gepa | all | restart_waste | 3,214 | 14,958,308 | 14,814,038 | $0.48 |
| B | ctl-seed | all | restart_waste | 2,967 | 13,337,661 | 13,337,661 | $0.00 |
| B | ao | all | pilot | 1,161 | 5,524,975 | 5,168,526 | $1.30 |
| A | metaharness | all | restart_waste | 705 | 4,245,257 | 4,245,257 | $0.00 |
| A | ao | all | restart_waste | 636 | 3,811,054 | 3,811,054 | $0.00 |
| A | hc | all | restart_waste | 615 | 3,410,547 | 3,410,547 | $0.00 |
| B | hl-trial | all | no_run_dir | 363 | 3,007,425 | 2,419,795 | $1.69 |
| B | hc | all | pilot | 619 | 2,777,762 | 2,641,597 | $0.54 |
| A | evoskill | all | restart_waste | 804 | 2,573,286 | 2,573,286 | $0.00 |
| B | gepa | all | pilot | 466 | 2,297,765 | 2,241,304 | $0.20 |
| - | FE-dry-hl | all | smoke | 305 | 2,192,207 | 2,192,207 | $0.00 |
| - | BL-gepa-smoke2 | all | smoke | 147 | 2,176,130 | 2,130,636 | $0.16 |
| - | BLsmoke-mipro-s0 | all | smoke | 458 | 1,806,342 | 1,734,479 | $0.22 |
| A | graphskillevo | all | stopped | 185 | 1,645,251 | 1,594,615 | $0.41 |
| - | BL-wikiskill-smoke | all | smoke | 129 | 1,096,254 | 880,221 | $0.25 |
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
| - | FE-dry-C-seed-s0 | all | smoke | 87 | 332,151 | 332,151 | $0.00 |
| A | mce | all | stopped | 111 | 328,338 | 328,338 | $0.00 |
| A | hc | all | smoke | 72 | 314,102 | 263,711 | $0.16 |
| - | untagged | all | untagged | 51 | 312,041 | 0 | $1.26 |
| - | BL-ace-smoke | all | smoke | 186 | 308,024 | 171,903 | $0.45 |
| - | BL-hl-smoke5 | all | smoke | 28 | 296,477 | 94,782 | $0.57 |
| - | BL-hl-smoke6 | all | smoke | 47 | 275,473 | 275,473 | $0.00 |
| - | BL-mce-smoke | all | smoke | 75 | 256,348 | 129,161 | $0.54 |
| - | BL-hl-smoke | all | smoke | 26 | 203,616 | 200,905 | $0.01 |
| - | FE-smoke-C-dry-canary-s0 | all | smoke | 52 | 196,485 | 0 | $0.00 |
| - | FE-dry-C-gepa-s1 | all | smoke | 43 | 192,071 | 192,071 | $0.00 |
| - | FE-smoke-B-dry-seed-s0 | all | smoke | 58 | 186,527 | 0 | $0.00 |
| A | E10-cfprobe | all | smoke | 86 | 180,158 | 0 | $0.77 |
| - | BL-skillopt-smoke | all | smoke | 44 | 176,669 | 142,711 | $0.11 |
| - | BL-gepa-smoke | all | smoke | 56 | 169,581 | 169,581 | $0.00 |
| A | memento | all | stopped | 82 | 165,440 | 165,440 | $0.00 |
| - | FE-dry-B-seed-s0 | all | smoke | 43 | 158,962 | 158,962 | $0.00 |
| - | FE-dry-B-hl-v0-s0 | all | smoke | 25 | 138,602 | 138,602 | $0.00 |
| - | FE-smoke-B-dry-oneshot-s0 | all | smoke | 33 | 135,702 | 0 | $0.00 |
| - | FE-smoke-C-dry-seed-s0 | all | smoke | 46 | 127,819 | 0 | $0.00 |
| - | FE-dry-B-gepa-s1 | all | smoke | 31 | 126,706 | 126,706 | $0.00 |
| - | FE-smoke-B-dry-gepa-end-s0 | all | smoke | 27 | 124,370 | 0 | $0.00 |
| - | BL-hl-smoke3 | all | smoke | 23 | 121,156 | 121,156 | $0.00 |
| - | BL-metaharness-smoke | all | smoke | 43 | 119,562 | 94,330 | $0.10 |
| - | FE-smoke-B-dry-oneshot-s2 | all | smoke | 33 | 117,678 | 0 | $0.00 |
| - | FE-smoke-B-dry-gepa-s2 | all | smoke | 33 | 108,960 | 0 | $0.00 |
| - | FE-smoke-B-dry-gepa-s0 | all | smoke | 33 | 108,721 | 0 | $0.00 |
| - | FE-smoke-B-dry-gepa-end-s1 | all | smoke | 24 | 103,215 | 0 | $0.00 |
| - | FE-smoke-C-dry-gepa-s2 | all | smoke | 27 | 101,298 | 0 | $0.00 |
| C | E10C-s0-trial | all | smoke | 27 | 96,218 | 96,218 | $0.00 |
| - | FE-dry-B-gepa-s0 | all | smoke | 27 | 96,111 | 96,111 | $0.00 |
| - | FE-smoke-B-dry-canary-s0 | all | smoke | 28 | 86,660 | 0 | $0.00 |
| - | FE-smoke-B-dry-oneshot-s1 | all | smoke | 22 | 86,505 | 0 | $0.00 |
| A | E10-evomock | all | smoke | 11 | 84,378 | 0 | $0.28 |
| - | FE-dry-C-gepa-s0 | all | smoke | 19 | 81,537 | 81,537 | $0.00 |
| - | BL-graphskillevo-smoke | all | smoke | 18 | 76,722 | 51,846 | $0.14 |
| - | FE-smoke-B-dry-gepa-s1 | all | smoke | 23 | 76,650 | 0 | $0.00 |
| - | FE-smoke-C-dry-gepa-s1 | all | smoke | 19 | 73,477 | 0 | $0.00 |
| - | FE-dry-B-gepa-s2 | all | smoke | 17 | 69,042 | 69,042 | $0.00 |
| A | E10-evoptest | all | smoke | 7 | 66,659 | 0 | $0.21 |
| A | evoskill-r2 | all | no_run_dir | 36 | 63,013 | 63,013 | $0.00 |
| - | FE-smoke-C-dry-gepa-s0 | all | smoke | 22 | 62,376 | 0 | $0.00 |
| - | BL-memento-smokefake | all | smoke | 12 | 62,318 | 0 | $0.34 |
| - | FE-smoke-A-dry-skillopt-end-s2 | all | smoke | 6 | 51,710 | 0 | $0.00 |
| - | FE-dry-C-gepa-s2 | all | smoke | 15 | 51,201 | 51,201 | $0.00 |
| - | FE-smoke-A-dry-seed-s0 | all | smoke | 13 | 45,378 | 0 | $0.00 |
| - | FE-smoke-A-dry-skillopt-end-s1 | all | smoke | 6 | 42,988 | 0 | $0.00 |
| - | E00 | all | smoke | 6 | 41,475 | 41,475 | $0.00 |
| - | FE-smoke-A-dry-gepa-s0 | all | smoke | 10 | 40,978 | 0 | $0.00 |
| - | FE-dry-A-seed-s0 | all | smoke | 13 | 36,939 | 36,939 | $0.00 |
| - | FE-smoke-A-dry-gepa-end-s1 | all | smoke | 7 | 33,968 | 0 | $0.00 |
| A | E10-egressprobe | all | smoke | 7 | 31,676 | 0 | $0.09 |
| - | FE-smoke-A-dry-gepa-end-s0 | all | smoke | 6 | 30,703 | 0 | $0.00 |
| - | FE-smoke-A-dry-gepa-end-s2 | all | smoke | 6 | 30,691 | 0 | $0.00 |
| B | sbxtest | all | smoke | 1 | 30,614 | 0 | $0.08 |
| A | E10-tagprobe-api | all | smoke | 1 | 30,596 | 0 | $0.08 |
| C | negtest | all | smoke | 2 | 29,015 | 0 | $0.07 |
| A | E10-metaharness-smoke | all | smoke | 1 | 26,893 | 0 | $0.07 |
| A | E10-tagprobe-auth | all | smoke | 1 | 26,880 | 0 | $0.07 |
| - | FE-smoke-A-dry-skillopt-s0 | all | smoke | 7 | 25,564 | 0 | $0.00 |
| A | E10-mh-negtest | all | smoke | 13 | 23,268 | 0 | $0.08 |
| - | FE-smoke-A-dry-skillopt-s1 | all | smoke | 6 | 21,292 | 0 | $0.00 |
| - | FE-dry-A-gepa-s1 | all | smoke | 9 | 21,264 | 21,264 | $0.00 |
| - | FE-smoke-A-dry-gepa-s1 | all | smoke | 6 | 21,086 | 0 | $0.00 |
| - | FE-smoke-A-dry-skillopt-s2 | all | smoke | 6 | 20,774 | 0 | $0.00 |
| - | FE-smoke-A-dry-gepa-s2 | all | smoke | 7 | 19,961 | 0 | $0.00 |
| - | FE-dry-A-gepa-s0 | all | smoke | 8 | 17,483 | 17,483 | $0.00 |
| - | FE-smoke-A-dry-canary-s0 | all | smoke | 6 | 11,268 | 0 | $0.00 |
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
| - | E00-azprobe | all | smoke | 1 | 13 | 0 | $0.00 |
| B | probe | all | smoke | 5 | 12 | 0 | $0.00 |
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

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, B/harnesslens/s0, B/harnesslens/s1, B/harnesslens/s2, B/harnesslens_superseded_v0/s0, B/harnesslens_superseded_v0/s1, B/harnesslens_superseded_v0/s2, C-E12/bestofk/s0, C-E12/bestofk/s1, C-E12/bestofk/s2, C-E12/bestofk_pipeline_test_k1/s0
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
