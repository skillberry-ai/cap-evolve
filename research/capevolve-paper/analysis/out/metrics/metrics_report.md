# Campaign metrics report

Generated 2026-10-12T09:25:33Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-12T09:25:37Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 248103 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 1,495,201,754 | 1,474,967,118 | 20,234,636 |
| rits_tokens | 1,422,719,744 | 1,388,028,208 | 34,691,536 |
| capped_tokens (non-RITS) | 70,389,165 | 64,241,447 | 6,147,718 |
| calls | 248103 | 248103 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 190737}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 261,879 | 1,115 | 1,550,162,504 | 1,549,971,767 | 1,423,701,358 | 70,395,028 | $242.39 lb | 1,430,620,436 |
| suite - | 11,692 | 195 | 52,900,169 | 52,756,105 | 13,552,205 | 1,692,438 | $25.30 lb | 13,552,205 |
| suite A | 73,472 | 213 | 604,745,972 | 604,699,299 | 569,556,375 | 35,142,924 | $94.74 lb | 569,556,375 |
| suite A-E12 | 6,164 | 21 | 34,644,697 | 34,644,697 | 33,702,870 | 941,827 | $3.81 lb | 33,702,870 |
| suite B | 115,462 | 462 | 585,420,023 | 585,420,023 | 561,728,287 | 23,691,736 | $62.06 lb | 568,647,365 |
| suite C | 32,761 | 113 | 162,643,249 | 162,643,249 | 158,915,370 | 3,727,879 | $17.53 lb | 158,915,370 |
| suite C-E12 | 17,149 | 106 | 91,444,475 | 91,444,475 | 86,246,251 | 5,198,224 | $32.22 lb | 86,246,251 |
| suite D | 1,087 | 2 | 3,652,728 | 3,652,728 | 0 | 0 | $1.28 lb | 0 |
| suite D-E21 | 298 | 0 | 1,012,219 | 1,012,219 | 0 | 0 | $0.36 lb | 0 |
| suite D-null | 3,794 | 3 | 13,698,972 | 13,698,972 | 0 | 0 | $5.07 lb | 0 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 11,641 | 52,444,064 | 13,552,205 | $24.04 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A-E12|main | 6,164 | 34,644,697 | 33,702,870 | $3.81 |
| A|main | 68,218 | 565,091,520 | 533,873,356 | $83.97 |
| A|no_run_dir | 123 | 490,818 | 336,530 | $0.33 |
| A|restart_waste | 4,291 | 34,666,272 | 31,862,522 | $7.18 |
| A|smoke | 462 | 2,311,660 | 1,395,574 | $2.85 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 7,938 | 34,742,198 | 34,294,036 | $0.00 |
| B|main | 84,338 | 440,624,387 | 419,794,742 | $50.67 |
| B|no_run_dir | 363 | 3,007,425 | 2,419,795 | $1.69 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C-E12|main | 17,149 | 91,444,475 | 86,246,251 | $32.22 |
| C|chaser_eval | 1,895 | 7,343,177 | 7,343,177 | $0.00 |
| C|main | 30,837 | 155,174,839 | 151,475,975 | $17.46 |
| C|smoke | 29 | 125,233 | 96,218 | $0.07 |
| D-E21|main | 298 | 1,012,219 | 0 | $0.36 |
| D-null|smoke | 3,794 | 13,698,972 | 0 | $5.07 |
| D|main | 1,085 | 3,652,708 | 0 | $1.28 |
| D|no_run_dir | 2 | 20 | 0 | $0.00 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 151 | 8.43 | 17.90 | 771 | 0 | 7.21 | 0.00 | 1385 (34.6%) | $3.70 | 0/0/0 | 56891 |
| A | ace | 1 | 81 | 8.43 | 9.60 | 745 | 0 | 8.65 | 0.00 | 645 (16.1%) | $1.76 | 0/0/0 | 114805 |
| A | ace | 2 | 75 | 8.41 | 8.90 | 788 | 0 | 9.47 | 0.00 | 556 (13.9%) | $1.54 | 0/0/0 | 133710 |
| A | ao | 0 | 229 | 18.73 | 12.20 | 2153 | 1 | 18.82 | 0.00 | 2749 (68.7%) | $7.28 | 2/2/0 | 94188 |
| A | ao | 1 | 387 | 18.70 | 20.70 | 2300 | 1 | 13.77 | 0.00 | 991 (24.8%) | $2.92 | 2/2/0 | 38141 |
| A | ao | 2 | 353 | 18.71 | 18.90 | 2289 | 1 | 14.43 | 0.00 | 1602 (40.1%) | $4.47 | 2/2/0 | 45415 |
| A | evoskill | 0 | 332 | 12.28 | 27.00 | 1524 | 12 | 9.50 | 0.00 | 387 (9.7%) | $1.26 | 7/7/7 | 29773 |
| A | evoskill | 1 | 358 | 14.95 | 23.90 | 2037 | 14 | 15.14 | 0.00 | 585 (14.6%) | $1.73 | 7/7/7 | 43931 |
| A | evoskill | 2 | 352 | 14.95 | 23.50 | 1991 | 14 | 13.99 | 0.00 | 569 (14.2%) | $1.70 | 7/7/6 | 41368 |
| A | gepa | 0 | 578 | 25.07 | 23.10 | 2775 | 2 | 19.37 | 0.00 | 567 (14.2%) | $1.96 | 20/10/10 | 34492 |
| A | gepa | 1 | 432 | 25.07 | 17.20 | 2503 | 9 | 19.54 | 0.00 | 185 (4.6%) | $0.62 | 7/7/7 | 45662 |
| A | gepa | 2 | 588 | 25.07 | 23.50 | 2644 | 3 | 16.26 | 0.00 | 428 (10.7%) | $1.39 | 17/10/10 | 28379 |
| A | hc | 0 | 299 | 18.72 | 16.00 | 2738 | 3 | 21.25 | 0.00 | 147 (3.7%) | $0.54 | 4/4/0 | 71566 |
| A | hc | 1 | 457 | 18.74 | 24.40 | 2860 | 2 | 16.50 | 0.00 | 88 (2.2%) | $0.34 | 3/5/1 | 36303 |
| A | hc | 2 | 233 | 18.74 | 12.40 | 1801 | 5 | 13.11 | 0.00 | 197 (4.9%) | $0.79 | 4/2/0 | 57096 |
| A | metaharness | 0 | 600 | 19.61 | 30.60 | 3576 | 11 | 21.76 | 0.00 | 162 (4.0%) | $0.67 | 9/9/4 | 36536 |
| A | metaharness | 1 | 600 | 20.00 | 30.00 | 3619 | 6 | 22.76 | 0.00 | 175 (4.4%) | $0.77 | 9/9/5 | 38223 |
| A | metaharness | 2 | 600 | 22.39 | 26.80 | 3738 | 7 | 30.77 | 0.00 | 214 (5.4%) | $0.94 | 9/9/5 | 51645 |
| A | mipro | 0 | 137 | 20.41 | 6.70 | 2203 | 1 | 26.43 | 0.00 | 179 (4.5%) | $0.58 | 6/5/0 | 194253 |
| A | mipro | 1 | 157 | 20.39 | 7.70 | 2284 | 0 | 26.59 | 0.00 | 181 (4.5%) | $0.60 | 10/9/0 | 170506 |
| A | mipro | 2 | 145 | 20.40 | 7.10 | 2341 | 0 | 25.45 | 0.00 | 179 (4.5%) | $0.59 | 8/7/0 | 176783 |
| A | skillopt | 0 | 442 | 25.07 | 17.60 | 2932 | 7 | 22.22 | 0.00 | 2578 (64.4%) | $6.00 | 7/6/3 | 56113 |
| A | skillopt | 1 | 543 | 25.07 | 21.70 | 2647 | 5 | 24.05 | 0.00 | 4778 (119.5%) | $10.42 | 7/6/5 | 53096 |
| A | skillopt | 2 | 530 | 25.07 | 21.10 | 3100 | 13 | 25.60 | 0.00 | 4674 (116.9%) | $10.28 | 7/6/6 | 57123 |
| A | trace2skill | 0 | 200 | 15.63 | 12.80 | 1899 | 2 | 11.94 | 0.00 | 2202 (55.1%) | $6.82 | 3/3/0 | 70693 |
| A | trace2skill | 1 | 200 | 14.21 | 14.10 | 1668 | 13 | 8.30 | 0.00 | 2225 (55.6%) | $6.96 | 3/3/0 | 52636 |
| A | trace2skill | 2 | 200 | 16.14 | 12.40 | 1688 | 11 | 8.67 | 0.00 | 2086 (52.1%) | $6.49 | 3/3/0 | 53789 |
| A | wikiskill | 0 | 241 | 20.36 | 11.80 | 2154 | 0 | 17.23 | 0.00 | 199 (5.0%) | $0.30 | 2/2/1 | 72315 |
| A | wikiskill | 1 | 244 | 20.38 | 12.00 | 2111 | 0 | 20.17 | 0.00 | 178 (4.5%) | $0.30 | 2/2/2 | 83383 |
| A | wikiskill | 2 | 223 | 20.38 | 10.90 | 2339 | 0 | 24.91 | 0.00 | 127 (3.2%) | $0.25 | 2/2/2 | 112263 |
| A-E12 | hcstock | 0 | 331 | 12.02 | 27.50 | 1953 | 6 | 11.11 | 0.00 | 245 (6.1%) | $0.97 | 7/6/1 | 34291 |
| A-E12 | hcstock | 1 | 404 | 12.02 | 33.60 | 2090 | 8 | 11.46 | 0.00 | 362 (9.0%) | $1.48 | 8/7/2 | 29269 |
| A-E12 | hcstock | 2 | 391 | 12.01 | 32.60 | 2121 | 7 | 11.13 | 0.00 | 335 (8.4%) | $1.35 | 8/7/3 | 29334 |
| B | ao | 0 | 198 | 11.60 | 17.10 | 5078 | 37 | 19.59 | 2.19 | 1019 (25.5%) | $4.92 | 3/2/0 | 117217 |
| B | ao | 1 | 172 | 20.77 | 8.30 | 4784 | 27 | 18.95 | 2.08 | 843 (21.1%) | $4.70 | 2/1/0 | 129529 |
| B | ao | 2 | 172 | 17.62 | 9.80 | 6862 | 25 | 29.90 | 3.12 | 1039 (26.0%) | $6.46 | 1/0/0 | 200392 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 1530 | 4 | 5.45 | 0.67 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
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
| B | gepa | 0 | 262 | 20.78 | 12.60 | 4905 | 20 | 24.05 | 2.38 | 349 (8.7%) | $1.26 | 13/13/5 | 103899 |
| B | gepa | 1 | 283 | 20.78 | 13.60 | 5055 | 14 | 24.04 | 2.42 | 393 (9.8%) | $1.40 | 16/16/6 | 96412 |
| B | gepa | 2 | 296 | 20.78 | 14.20 | 5101 | 25 | 22.97 | 2.22 | 419 (10.5%) | $1.44 | 19/19/5 | 88000 |
| B | harnesslens | 0 | 108 | 10.77 | 10.00 | 3029 | 0 | 18.18 | 2.71 | 4358 (109.0%) | $10.63 | 0/0/0 | 236350 |
| B | harnesslens | 1 | 105 | 10.63 | 9.90 | 3167 | 2 | 20.30 | 3.37 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 227712 |
| B | harnesslens | 2 | 105 | 10.83 | 9.70 | 3052 | 3 | 18.45 | 2.56 | 4319 (108.0%) | $10.69 | 0/0/0 | 243659 |
| B | hc | 0 | 294 | 20.78 | 14.10 | 8548 | 35 | 36.39 | 4.19 | 278 (6.9%) | $1.65 | 2/1/0 | 141623 |
| B | hc | 1 | 392 | 20.78 | 18.90 | 8621 | 31 | 34.79 | 4.12 | 623 (15.6%) | $3.18 | 8/7/0 | 102929 |
| B | hc | 2 | 392 | 20.78 | 18.90 | 8806 | 33 | 37.50 | 5.04 | 205 (5.1%) | $1.20 | 2/1/0 | 111115 |
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
| C | gepa | 0 | 136 | 15.08 | 9.00 | 2218 | 8 | 10.46 | 1.17 | 246 (6.1%) | $1.00 | 11/11/5 | 87373 |
| C | gepa | 1 | 104 | 15.07 | 6.90 | 1953 | 4 | 10.07 | 1.54 | 232 (5.8%) | $0.94 | 10/9/4 | 113926 |
| C | gepa | 2 | 129 | 15.07 | 8.60 | 2162 | 6 | 9.85 | 1.12 | 269 (6.7%) | $0.98 | 12/12/4 | 87110 |
| C | hc | 0 | 200 | 15.08 | 13.30 | 4275 | 20 | 18.67 | 2.16 | 374 (9.3%) | $2.00 | 3/2/0 | 105981 |
| C | hc | 1 | 100 | 15.07 | 6.60 | 3562 | 18 | 17.51 | 1.83 | 286 (7.1%) | $1.56 | 4/3/0 | 196206 |
| C | hc | 2 | 180 | 15.07 | 11.90 | 4023 | 14 | 17.53 | 1.96 | 324 (8.1%) | $1.68 | 5/4/0 | 110054 |
| C-E12 | bestofk | 0 | n/a | 11.88 | n/a | 3003 | 20 | 14.22 | 1.40 | 1328 (33.2%) | $8.78 | 7/6/0 | n/a |
| C-E12 | bestofk | 1 | n/a | 8.61 | n/a | 2642 | 27 | 12.35 | 1.20 | 1150 (28.8%) | $7.53 | 7/6/0 | n/a |
| C-E12 | bestofk | 2 | n/a | 8.61 | n/a | 2700 | 13 | 11.24 | 1.21 | 1051 (26.3%) | $7.06 | 7/6/0 | n/a |
| C-E12 | hcstock | 0 | 120 | 12.37 | 9.70 | 2687 | 9 | 13.86 | 1.36 | 442 (11.1%) | $2.30 | 6/5/1 | 130557 |
| C-E12 | hcstock | 1 | 160 | 12.38 | 12.90 | 3053 | 16 | 12.32 | 1.43 | 629 (15.7%) | $3.51 | 8/7/0 | 89867 |
| C-E12 | hcstock | 2 | 140 | 12.38 | 11.30 | 3064 | 21 | 13.95 | 1.71 | 598 (14.9%) | $3.05 | 7/6/2 | 116168 |
| D | CTL | 0 | 0 | 0.05 | n/a | 74 | 1 | 0.21 | 0.02 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | CTL | 1 | 0 | 0.05 | n/a | 73 | 0 | 0.21 | 0.02 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | CTL | 2 | 0 | 0.05 | n/a | 65 | 0 | 0.20 | 0.02 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | P | 0 | 0 | 0.05 | n/a | 97 | 0 | 0.31 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | P | 1 | 0 | 0.05 | n/a | 81 | 0 | 0.27 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | P | 2 | 0 | 0.05 | n/a | 86 | 0 | 0.26 | 0.02 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | PT | 0 | 0 | 0.06 | n/a | 116 | 0 | 0.37 | 0.04 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | PT | 1 | 0 | 0.06 | n/a | 105 | 0 | 0.33 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | PT | 2 | 0 | 0.06 | n/a | 101 | 0 | 0.29 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | T | 0 | 0 | 0.05 | n/a | 94 | 0 | 0.27 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | T | 1 | 0 | 0.05 | n/a | 107 | 1 | 0.30 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D | T | 2 | 0 | 0.05 | n/a | 86 | 0 | 0.26 | 0.02 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D-E21 | ruleP | 0 | 0 | 0.06 | n/a | 109 | 0 | 0.33 | 0.04 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D-E21 | ruleP | 1 | 0 | 0.06 | n/a | 94 | 0 | 0.29 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| D-E21 | ruleP | 2 | 0 | 0.06 | n/a | 95 | 0 | 0.28 | 0.03 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 93620 | 93620 | 101802 | 862034 | $2.34 |
| A | ao | 3 | 52880 | 52880 | 59248 | 1780736 | $4.89 |
| A | evoskill | 3 | 36885 | 36885 | 38357 | 513720 | $1.56 |
| A | gepa | 3 | 35466 | 35466 | 36178 | 392981 | $1.32 |
| A | hc | 3 | 54479 | 54479 | 54988 | 143858 | $0.56 |
| A | metaharness | 3 | 41829 | 41829 | 42135 | 183746 | $0.79 |
| A | mipro | 3 | 179283 | 179283 | 180514 | 179642 | $0.59 |
| A | skillopt | 3 | 47627 | 47627 | 55444 | 4010037 | $8.90 |
| A | trace2skill | 3 | 48184 | 48184 | 59039 | 2171196 | $6.76 |
| A | wikiskill | 3 | 88611 | 88611 | 89320 | 168104 | $0.28 |
| A-E12 | hcstock | 3 | 30134 | 30134 | 30965 | 313942 | $1.27 |
| B | ao | 3 | 127641 | 141385 | 149046 | 966953 | $5.36 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 112694 | 127767 | 130559 | 0 | n/a |
| B | gepa | 3 | 84782 | 93166 | 96104 | 386875 | $1.37 |
| B | harnesslens | 3 | 179142 | 206319 | 235907 | 2892582 | $10.66 |
| B | hc | 3 | 102733 | 115273 | 118556 | 368538 | $2.01 |
| C | ao | 3 | 83174 | 94001 | 99848 | 547361 | $2.39 |
| C | ctl-oneshot | 3 | 81484 | 92818 | 94889 | 108744 | $0.71 |
| C | ctl-seed | 3 | 104711 | 119273 | 119273 | 0 | n/a |
| C | gepa | 3 | 83369 | 94095 | 96136 | 248958 | $0.97 |
| C | hc | 3 | 121934 | 135238 | 137414 | 327892 | $1.75 |
| C-E12 | hcstock | 3 | 97398 | 108235 | 112197 | 556366 | $2.95 |

## Overhead / waste (not in main tables; included in campaign totals)

| suite | arm | seed | category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---|---|---|---:|---:|---:|---:|
| - | E00-azprobe | all | smoke | 8,292 | 34,823,214 | 0 | $17.39 |
| B | ao | all | restart_waste | 5,408 | 26,206,898 | 25,761,808 | $3.08 |
| B | hc | all | restart_waste | 4,476 | 21,189,920 | 20,850,489 | $2.04 |
| A | ace | all | restart_waste | 1,422 | 20,069,279 | 17,265,529 | $7.18 |
| B | ctl-oneshot | all | restart_waste | 4,210 | 19,472,780 | 19,160,701 | $1.95 |
| B | gepa | all | restart_waste | 3,214 | 14,958,308 | 14,814,038 | $0.48 |
| B | ctl-seed | all | restart_waste | 2,967 | 13,337,661 | 13,337,661 | $0.00 |
| B | ao | all | pilot | 1,161 | 5,524,975 | 5,168,526 | $1.30 |
| A | metaharness | all | restart_waste | 705 | 4,245,257 | 4,245,257 | $0.00 |
| A | ao | all | restart_waste | 636 | 3,811,054 | 3,811,054 | $0.00 |
| D-null | E22-null-c3 | all | smoke | 981 | 3,493,682 | 0 | $1.33 |
| D-null | E22-null-c2 | all | smoke | 948 | 3,485,889 | 0 | $1.29 |
| D-null | E22-null-c0 | all | smoke | 939 | 3,413,385 | 0 | $1.24 |
| A | hc | all | restart_waste | 615 | 3,410,547 | 3,410,547 | $0.00 |
| D-null | E22-null-c1 | all | smoke | 926 | 3,306,016 | 0 | $1.21 |
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
| - | FE-smoke-D-ctl-s0 | all | smoke | 48 | 218,872 | 0 | $0.06 |
| - | BL-hl-smoke | all | smoke | 26 | 203,616 | 200,905 | $0.01 |
| - | FE-smoke-C-dry-canary-s0 | all | smoke | 52 | 196,485 | 0 | $0.22 |
| - | FE-dry-C-gepa-s1 | all | smoke | 43 | 192,071 | 192,071 | $0.00 |
| - | FE-smoke-B-dry-seed-s0 | all | smoke | 58 | 186,527 | 0 | $0.18 |
| A | E10-cfprobe | all | smoke | 86 | 180,158 | 0 | $0.77 |
| - | BL-skillopt-smoke | all | smoke | 44 | 176,669 | 142,711 | $0.11 |
| - | BL-gepa-smoke | all | smoke | 56 | 169,581 | 169,581 | $0.00 |
| A | memento | all | stopped | 82 | 165,440 | 165,440 | $0.00 |
| - | FE-dry-B-seed-s0 | all | smoke | 43 | 158,962 | 158,962 | $0.00 |
| - | FE-dry-B-hl-v0-s0 | all | smoke | 25 | 138,602 | 138,602 | $0.00 |
| - | FE-smoke-B-dry-oneshot-s0 | all | smoke | 33 | 135,702 | 0 | $0.18 |
| - | FE-smoke-C-dry-seed-s0 | all | smoke | 46 | 127,819 | 0 | $0.14 |
| - | FE-dry-B-gepa-s1 | all | smoke | 31 | 126,706 | 126,706 | $0.00 |
| - | FE-smoke-B-dry-gepa-end-s0 | all | smoke | 27 | 124,370 | 0 | $0.15 |
| - | BL-hl-smoke3 | all | smoke | 23 | 121,156 | 121,156 | $0.00 |
| - | BL-metaharness-smoke | all | smoke | 43 | 119,562 | 94,330 | $0.10 |
| - | FE-smoke-B-dry-oneshot-s2 | all | smoke | 33 | 117,678 | 0 | $0.14 |
| - | FE-smoke-D-ctl-s2 | all | smoke | 23 | 112,159 | 0 | $0.04 |
| - | FE-smoke-B-dry-gepa-s2 | all | smoke | 33 | 108,960 | 0 | $0.11 |
| - | FE-smoke-B-dry-gepa-s0 | all | smoke | 33 | 108,721 | 0 | $0.11 |
| - | FE-smoke-B-dry-gepa-end-s1 | all | smoke | 24 | 103,215 | 0 | $0.13 |
| - | FE-smoke-C-dry-gepa-s2 | all | smoke | 27 | 101,298 | 0 | $0.13 |
| - | FE-smoke-D-pt-s0 | all | smoke | 28 | 97,973 | 0 | $0.03 |
| C | E10C-s0-trial | all | smoke | 27 | 96,218 | 96,218 | $0.00 |
| - | FE-dry-B-gepa-s0 | all | smoke | 27 | 96,111 | 96,111 | $0.00 |
| - | FE-smoke-B-dry-canary-s0 | all | smoke | 28 | 86,660 | 0 | $0.11 |
| - | FE-smoke-B-dry-oneshot-s1 | all | smoke | 22 | 86,505 | 0 | $0.10 |
| A | E10-evomock | all | smoke | 11 | 84,378 | 0 | $0.28 |
| - | FE-dry-C-gepa-s0 | all | smoke | 19 | 81,537 | 81,537 | $0.00 |
| - | FE-smoke-D-ctl-s1 | all | smoke | 19 | 77,312 | 0 | $0.03 |
| - | BL-graphskillevo-smoke | all | smoke | 18 | 76,722 | 51,846 | $0.14 |
| - | FE-smoke-B-dry-gepa-s1 | all | smoke | 23 | 76,650 | 0 | $0.10 |
| - | FE-smoke-C-dry-gepa-s1 | all | smoke | 19 | 73,477 | 0 | $0.09 |
| - | FE-smoke-D-pt-s1 | all | smoke | 18 | 72,423 | 0 | $0.03 |
| - | FE-dry-B-gepa-s2 | all | smoke | 17 | 69,042 | 69,042 | $0.00 |
| A | E10-evoptest | all | smoke | 7 | 66,659 | 0 | $0.21 |
| A | evoskill-r2 | all | no_run_dir | 36 | 63,013 | 63,013 | $0.00 |
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

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/injtest/s0, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, B/harnesslens/s0, B/harnesslens/s1, B/harnesslens/s2, B/harnesslens_ext/s0, B/harnesslens_superseded_v0/s0, B/harnesslens_superseded_v0/s1, B/harnesslens_superseded_v0/s2, C-E12/bestofk/s0, C-E12/bestofk/s1, C-E12/bestofk/s2, C-E12/bestofk_pipeline_test_k1/s0, D/CTL/s0, D/CTL/s1, D/CTL/s2, D/P/s0, D/P/s1, D/P/s2, D/PT/s0, D/PT/s1, D/PT/s2, D/T/s0, D/T/s1, D/T/s2, D-E21/ruleP/s0, D-E21/ruleP/s1, D-E21/ruleP/s2
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
