# Campaign metrics report

Generated 2026-10-11T19:38:32Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-11T19:38:32Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 107222 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 548,112,784 | 548,112,784 | 0 |
| rits_tokens | 531,794,446 | 531,794,446 | 0 |
| capped_tokens (non-RITS) | 16,318,338 | 16,318,338 | 0 |
| calls | 107222 | 107222 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 144064}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 107,225 | 626 | 548,269,714 | 548,125,650 | 531,807,312 | 16,318,338 | $52.16 lb | 536,141,606 |
| suite - | 2,019 | 126 | 11,808,886 | 11,664,822 | 9,998,051 | 1,666,771 | $5.36 lb | 9,998,051 |
| suite A | 23,430 | 139 | 152,250,256 | 152,250,256 | 148,028,659 | 4,221,597 | $11.79 lb | 148,028,659 |
| suite B | 76,344 | 334 | 360,685,171 | 360,685,171 | 350,810,027 | 9,875,144 | $31.59 lb | 355,144,321 |
| suite C | 5,432 | 27 | 23,525,401 | 23,525,401 | 22,970,575 | 554,826 | $3.42 lb | 22,970,575 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 1,968 | 11,352,781 | 9,998,051 | $4.10 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A|main | 19,507 | 131,883,845 | 128,721,429 | $8.55 |
| A|no_run_dir | 123 | 490,818 | 336,530 | $0.33 |
| A|restart_waste | 3,006 | 15,611,038 | 15,499,789 | $0.35 |
| A|smoke | 416 | 2,125,526 | 1,382,518 | $2.15 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 5,083 | 21,873,335 | 21,550,696 | $0.00 |
| B|main | 48,325 | 230,974,893 | 223,248,687 | $21.90 |
| B|no_run_dir | 113 | 790,930 | 790,930 | $0.00 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C|main | 5,405 | 23,429,183 | 22,874,357 | $3.42 |
| C|smoke | 27 | 96,218 | 96,218 | $0.00 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 17 | 6.62 | 2.60 | 188 | 0 | 2.12 | 0.00 | 189 (4.7%) | $0.54 | 0/0/0 | 135655 |
| A | ace | 1 | 14 | 6.61 | 2.10 | 181 | 0 | 1.81 | 0.00 | 165 (4.1%) | $0.46 | 0/0/0 | 141407 |
| A | ace | 2 | 23 | 6.57 | 3.50 | 210 | 0 | 1.84 | 0.00 | 343 (8.6%) | $0.92 | 0/0/0 | 94845 |
| A | ao | 0 | 56 | 4.94 | 11.30 | 535 | 0 | 3.72 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 66402 |
| A | ao | 1 | 58 | 4.92 | 11.80 | 515 | 0 | 3.46 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 59632 |
| A | ao | 2 | 53 | 4.92 | 10.80 | 545 | 0 | 3.73 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 70296 |
| A | evoskill | 0 | 31 | 1.16 | 26.70 | 165 | 0 | 0.82 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 26462 |
| A | evoskill | 1 | 29 | 1.16 | 24.90 | 144 | 0 | 0.52 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 18094 |
| A | evoskill | 2 | 22 | 1.16 | 19.00 | 149 | 0 | 0.81 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 36815 |
| A | gepa | 0 | 179 | 11.28 | 15.90 | 927 | 2 | 5.00 | 0.00 | 92 (2.3%) | $0.33 | 5/3/3 | 28454 |
| A | gepa | 1 | 135 | 11.27 | 12.00 | 919 | 9 | 6.72 | 0.00 | 41 (1.0%) | $0.15 | 3/3/3 | 50079 |
| A | gepa | 2 | 240 | 11.28 | 21.30 | 990 | 3 | 5.26 | 0.00 | 153 (3.8%) | $0.47 | 6/4/4 | 22558 |
| A | hc | 0 | 66 | 4.91 | 13.40 | 554 | 0 | 3.70 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 56120 |
| A | hc | 1 | 54 | 4.96 | 10.90 | 524 | 0 | 3.68 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 68172 |
| A | hc | 2 | 64 | 4.95 | 12.90 | 531 | 0 | 3.27 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 51170 |
| A | metaharness | 0 | 164 | 8.70 | 18.90 | 1192 | 8 | 7.57 | 0.00 | 50 (1.2%) | $0.21 | 3/1/1 | 46479 |
| A | metaharness | 1 | 144 | 8.70 | 16.50 | 1222 | 3 | 7.89 | 0.00 | 42 (1.0%) | $0.18 | 3/1/1 | 55108 |
| A | metaharness | 2 | 132 | 8.69 | 15.20 | 1189 | 4 | 8.10 | 0.00 | 46 (1.2%) | $0.20 | 3/1/1 | 61744 |
| A | mipro | 0 | 30 | 6.62 | 4.50 | 226 | 1 | 1.29 | 0.00 | 179 (4.5%) | $0.58 | 1/0/0 | 48923 |
| A | mipro | 1 | 21 | 6.56 | 3.20 | 163 | 0 | 1.37 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 65081 |
| A | mipro | 2 | 32 | 6.61 | 4.80 | 245 | 0 | 1.28 | 0.00 | 179 (4.5%) | $0.59 | 1/0/0 | 45436 |
| A | skillopt | 0 | 133 | 11.27 | 11.80 | 1115 | 7 | 7.41 | 0.00 | 881 (22.0%) | $2.04 | 3/3/1 | 62369 |
| A | skillopt | 1 | 149 | 11.28 | 13.20 | 1031 | 5 | 6.90 | 0.00 | 437 (10.9%) | $1.00 | 2/2/2 | 49212 |
| A | skillopt | 2 | 160 | 11.26 | 14.20 | 1160 | 13 | 8.07 | 0.00 | 366 (9.2%) | $0.88 | 2/2/2 | 52704 |
| A | trace2skill | 0 | 120 | 10.77 | 11.10 | 980 | 2 | 6.59 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 54902 |
| A | trace2skill | 1 | 120 | 10.77 | 11.10 | 995 | 13 | 6.28 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 52293 |
| A | trace2skill | 2 | 120 | 10.76 | 11.10 | 965 | 11 | 6.18 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 51468 |
| A | wikiskill | 0 | 73 | 6.58 | 11.10 | 651 | 0 | 4.72 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 64597 |
| A | wikiskill | 1 | 89 | 6.59 | 13.50 | 680 | 0 | 4.33 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 48652 |
| A | wikiskill | 2 | 78 | 6.60 | 11.80 | 616 | 0 | 4.29 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 54981 |
| B | ao | 0 | 123 | 6.99 | 17.60 | 3738 | 23 | 14.34 | 1.60 | 621 (15.5%) | $3.75 | 2/1/0 | 137058 |
| B | ao | 1 | 123 | 5.49 | 22.40 | 3092 | 17 | 12.16 | 1.39 | 603 (15.1%) | $3.70 | 1/0/0 | 117191 |
| B | ao | 2 | 74 | 7.00 | 10.60 | 3871 | 11 | 15.94 | 1.58 | 602 (15.0%) | $4.61 | 1/0/0 | 247616 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 682 | 3 | 2.41 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 757 | 1 | 2.68 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 1031 | 9 | 4.41 | 0.38 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 973 | 5 | 3.93 | 0.41 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 941 | 7 | 3.59 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 6.51 | 15.00 | 2852 | 12 | 11.07 | 1.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 131225 |
| B | ctl-seed | 1 | 98 | 6.52 | 15.00 | 2762 | 6 | 10.66 | 1.39 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125731 |
| B | ctl-seed | 2 | 98 | 6.79 | 14.40 | 2914 | 9 | 11.40 | 1.53 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 134722 |
| B | gepa | 0 | 154 | 7.00 | 22.00 | 2778 | 13 | 12.74 | 1.25 | 171 (4.3%) | $0.61 | 8/8/3 | 93452 |
| B | gepa | 1 | 151 | 6.99 | 21.60 | 2574 | 11 | 11.18 | 1.16 | 169 (4.2%) | $0.62 | 9/9/2 | 84150 |
| B | gepa | 2 | 154 | 6.99 | 22.00 | 2652 | 17 | 11.59 | 1.13 | 163 (4.1%) | $0.55 | 8/8/3 | 84980 |
| B | hc | 0 | 147 | 6.99 | 21.00 | 3974 | 14 | 17.18 | 1.98 | 278 (6.9%) | $1.65 | 2/1/0 | 134657 |
| B | hc | 1 | 196 | 6.99 | 28.00 | 4160 | 19 | 17.16 | 1.98 | 440 (11.0%) | $2.35 | 4/3/0 | 101897 |
| B | hc | 2 | 98 | 6.99 | 14.00 | 4156 | 22 | 18.65 | 2.73 | 154 (3.9%) | $0.92 | 1/0/0 | 223209 |
| C | ao | 0 | 20 | 1.29 | 15.50 | 405 | 1 | 1.37 | 0.18 | 122 (3.1%) | $0.91 | 1/0/0 | 83678 |
| C | ao | 1 | 0 | 1.28 | n/a | 359 | 1 | 1.46 | 0.17 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ao | 2 | 20 | 1.24 | 16.10 | 368 | 1 | 1.25 | 0.15 | 125 (3.1%) | $0.71 | 1/0/0 | 76340 |
| C | ctl-oneshot | 0 | 0 | 1.27 | n/a | 306 | 0 | 1.49 | 0.15 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 1 | 20 | 1.29 | 15.50 | 405 | 2 | 1.38 | 0.16 | 107 (2.7%) | $0.71 | 1/0/0 | 82515 |
| C | ctl-oneshot | 2 | 0 | 1.28 | n/a | 432 | 2 | 1.87 | 0.22 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-seed | 0 | n/a | 1.28 | n/a | 325 | 3 | 1.16 | 0.16 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | ctl-seed | 1 | n/a | 1.28 | n/a | 343 | 0 | 1.15 | 0.14 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | ctl-seed | 2 | n/a | 1.28 | n/a | 376 | 0 | 1.53 | 0.19 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | gepa | 0 | 10 | 1.29 | 7.70 | 236 | 0 | 0.75 | 0.23 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 98073 |
| C | gepa | 1 | 10 | 1.28 | 7.80 | 266 | 0 | 0.86 | 0.20 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 106232 |
| C | gepa | 2 | 26 | 1.29 | 20.20 | 314 | 0 | 1.03 | 0.13 | 20 (0.5%) | $0.07 | 2/2/0 | 45272 |
| C | hc | 0 | 0 | 1.28 | n/a | 429 | 9 | 1.73 | 0.21 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | hc | 1 | 20 | 1.29 | 15.50 | 397 | 2 | 1.53 | 0.18 | 82 (2.1%) | $0.47 | 1/0/0 | 89580 |
| C | hc | 2 | 20 | 1.29 | 15.60 | 444 | 6 | 1.66 | 0.18 | 98 (2.4%) | $0.54 | 1/0/0 | 97192 |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 111356 | 111356 | 123969 | 232441 | $0.64 |
| A | ao | 3 | 65443 | 65443 | 65443 | 0 | n/a |
| A | evoskill | 3 | 27124 | 27124 | 27124 | 0 | n/a |
| A | gepa | 3 | 33212 | 33212 | 33697 | 95243 | $0.32 |
| A | hc | 3 | 58487 | 58487 | 58487 | 0 | n/a |
| A | metaharness | 3 | 54129 | 54129 | 54444 | 45950 | $0.20 |
| A | mipro | 3 | 49299 | 49299 | 53147 | 119159 | $0.58 |
| A | skillopt | 3 | 50813 | 50813 | 54762 | 561345 | $1.31 |
| A | trace2skill | 3 | 52888 | 52888 | 52888 | 0 | n/a |
| A | wikiskill | 3 | 56077 | 56077 | 56077 | 0 | n/a |
| B | ao | 3 | 143624 | 158810 | 167288 | 608700 | $4.02 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 112694 | 127767 | 130559 | 0 | n/a |
| B | gepa | 3 | 77329 | 85056 | 87527 | 167432 | $0.59 |
| B | hc | 3 | 131567 | 148710 | 153254 | 290758 | $1.64 |
| C | ao | 2 | 65486 | 73816 | 80009 | 123873 | $0.81 |
| C | ctl-oneshot | 1 | 68917 | 77146 | 82515 | 107372 | $0.71 |
| C | gepa | 3 | 66749 | 82937 | 83192 | 6627 | $0.07 |
| C | hc | 2 | 79845 | 88890 | 93386 | 89914 | $0.51 |

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
| A | evoskill | all | restart_waste | 804 | 2,573,286 | 2,573,286 | $0.00 |
| B | gepa | all | pilot | 466 | 2,297,765 | 2,241,304 | $0.20 |
| - | BL-gepa-smoke2 | all | smoke | 147 | 2,176,130 | 2,130,636 | $0.16 |
| - | BLsmoke-mipro-s0 | all | smoke | 458 | 1,806,342 | 1,734,479 | $0.22 |
| A | graphskillevo | all | stopped | 185 | 1,645,251 | 1,594,615 | $0.41 |
| - | BL-wikiskill-smoke | all | smoke | 129 | 1,096,254 | 880,221 | $0.25 |
| A | ace | all | restart_waste | 137 | 1,014,045 | 902,796 | $0.35 |
| - | BLsmoke-ace-s0 | all | smoke | 227 | 993,458 | 984,260 | $0.03 |
| B | hl-trial | all | no_run_dir | 113 | 790,930 | 790,930 | $0.00 |
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
| A | evoskill-r2 | all | no_run_dir | 36 | 63,013 | 63,013 | $0.00 |
| - | BL-memento-smokefake | all | smoke | 12 | 62,318 | 0 | $0.34 |
| - | E00 | all | smoke | 6 | 41,475 | 41,475 | $0.00 |
| B | sbxtest | all | smoke | 1 | 30,614 | 0 | $0.08 |
| A | E10-tagprobe-api | all | smoke | 1 | 30,596 | 0 | $0.08 |
| A | E10-metaharness-smoke | all | smoke | 1 | 26,893 | 0 | $0.07 |
| A | E10-tagprobe-auth | all | smoke | 1 | 26,880 | 0 | $0.07 |
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

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, A/metaharness/s2, C/ao/s1, C/ctl-oneshot/s0, C/ctl-oneshot/s2, C/ctl-seed/s0, C/ctl-seed/s1, C/ctl-seed/s2, C/gepa/s0, C/gepa/s1, C/hc/s0
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
