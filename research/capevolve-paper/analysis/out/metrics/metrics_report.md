# Campaign metrics report

Generated 2026-10-11T19:08:27Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-11T19:08:28Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 101693 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 517,492,056 | 517,492,056 | 0 |
| rits_tokens | 502,321,173 | 502,321,173 | 0 |
| capped_tokens (non-RITS) | 15,170,883 | 15,170,883 | 0 |
| calls | 101693 | 101693 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 144064}`

## Campaign totals

| scope | calls | errors | component non-cache tokens (basis for all sums) | ledger tokens (gateway basis) | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 101,702 | 607 | 517,679,253 | 517,535,189 | 502,364,306 | 15,170,883 | $47.18 lb | 506,555,268 |
| suite - | 2,019 | 126 | 11,808,886 | 11,664,822 | 9,998,051 | 1,666,771 | $5.36 lb | 9,998,051 |
| suite A | 22,029 | 137 | 142,418,060 | 142,418,060 | 138,583,341 | 3,834,719 | $10.51 lb | 138,583,341 |
| suite B | 74,227 | 325 | 350,150,536 | 350,150,536 | 340,481,143 | 9,669,393 | $31.30 lb | 344,672,105 |
| suite C | 3,427 | 19 | 13,301,771 | 13,301,771 | 13,301,771 | 0 | $0.00 lb | 13,301,771 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 1,968 | 11,352,781 | 9,998,051 | $4.10 |
| -|untagged | 51 | 312,041 | 0 | $1.26 |
| A|main | 18,106 | 122,051,649 | 119,276,111 | $7.27 |
| A|no_run_dir | 123 | 490,818 | 336,530 | $0.33 |
| A|restart_waste | 3,006 | 15,611,038 | 15,499,789 | $0.35 |
| A|smoke | 416 | 2,125,526 | 1,382,518 | $2.15 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 4,769 | 20,346,341 | 20,042,829 | $0.00 |
| B|main | 46,522 | 221,967,252 | 214,427,670 | $21.61 |
| B|no_run_dir | 113 | 790,930 | 790,930 | $0.00 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |
| C|main | 3,400 | 13,205,553 | 13,205,553 | $0.00 |
| C|smoke | 27 | 96,218 | 96,218 | $0.00 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 17 | 6.13 | 2.80 | 177 | 0 | 1.93 | 0.00 | 189 (4.7%) | $0.54 | 0/0/0 | 124952 |
| A | ace | 1 | 10 | 6.03 | 1.70 | 157 | 0 | 1.71 | 0.00 | 93 (2.3%) | $0.27 | 0/0/0 | 180166 |
| A | ace | 2 | 20 | 6.12 | 3.30 | 189 | 0 | 1.67 | 0.00 | 295 (7.4%) | $0.79 | 0/0/0 | 98024 |
| A | ao | 0 | 54 | 4.44 | 12.20 | 483 | 0 | 2.95 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 54621 |
| A | ao | 1 | 55 | 4.42 | 12.50 | 464 | 0 | 2.96 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 53746 |
| A | ao | 2 | 50 | 4.40 | 11.40 | 487 | 0 | 3.36 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 67205 |
| A | evoskill | 0 | 21 | 0.66 | 31.90 | 100 | 0 | 0.36 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 17342 |
| A | evoskill | 1 | 21 | 0.66 | 31.90 | 83 | 0 | 0.24 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 11526 |
| A | evoskill | 2 | 20 | 0.65 | 30.70 | 91 | 0 | 0.28 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 14123 |
| A | gepa | 0 | 162 | 10.74 | 15.10 | 871 | 2 | 4.77 | 0.00 | 92 (2.3%) | $0.33 | 5/3/3 | 30026 |
| A | gepa | 1 | 128 | 10.78 | 11.90 | 890 | 9 | 6.57 | 0.00 | 41 (1.0%) | $0.15 | 2/2/2 | 51674 |
| A | gepa | 2 | 223 | 10.79 | 20.70 | 934 | 3 | 5.00 | 0.00 | 153 (3.8%) | $0.47 | 6/4/4 | 23087 |
| A | hc | 0 | 59 | 4.43 | 13.30 | 497 | 0 | 3.29 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 55714 |
| A | hc | 1 | 54 | 4.45 | 12.10 | 469 | 0 | 3.11 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 57633 |
| A | hc | 2 | 59 | 4.45 | 13.30 | 476 | 0 | 2.95 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 50009 |
| A | metaharness | 0 | 150 | 8.20 | 18.30 | 1115 | 8 | 7.09 | 0.00 | 50 (1.2%) | $0.21 | 3/1/1 | 47587 |
| A | metaharness | 1 | 120 | 8.20 | 14.60 | 1122 | 2 | 7.54 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 62854 |
| A | metaharness | 2 | 120 | 8.15 | 14.70 | 1139 | 3 | 7.88 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 65665 |
| A | mipro | 0 | 25 | 6.00 | 4.20 | 173 | 1 | 1.22 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 48918 |
| A | mipro | 1 | 21 | 6.10 | 3.40 | 149 | 0 | 1.30 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 62070 |
| A | mipro | 2 | 28 | 6.10 | 4.60 | 199 | 0 | 1.03 | 0.00 | 179 (4.5%) | $0.59 | 1/0/0 | 43333 |
| A | skillopt | 0 | 130 | 10.75 | 12.10 | 1071 | 7 | 7.00 | 0.00 | 881 (22.0%) | $2.04 | 3/3/1 | 60587 |
| A | skillopt | 1 | 137 | 10.78 | 12.70 | 984 | 5 | 6.69 | 0.00 | 437 (10.9%) | $1.00 | 2/2/2 | 52047 |
| A | skillopt | 2 | 160 | 10.78 | 14.80 | 1148 | 13 | 7.96 | 0.00 | 366 (9.2%) | $0.88 | 2/2/2 | 52037 |
| A | trace2skill | 0 | 120 | 10.25 | 11.70 | 965 | 2 | 6.47 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 53921 |
| A | trace2skill | 1 | 117 | 10.27 | 11.40 | 950 | 13 | 5.84 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 49885 |
| A | trace2skill | 2 | 118 | 10.29 | 11.50 | 932 | 11 | 5.89 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 49921 |
| A | wikiskill | 0 | 67 | 6.07 | 11.00 | 592 | 0 | 4.32 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 64451 |
| A | wikiskill | 1 | 86 | 6.08 | 14.10 | 628 | 0 | 3.84 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 44613 |
| A | wikiskill | 2 | 75 | 6.08 | 12.30 | 571 | 0 | 4.05 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 53980 |
| B | ao | 0 | 123 | 6.49 | 18.90 | 3483 | 23 | 13.25 | 1.48 | 621 (15.5%) | $3.75 | 2/1/0 | 127115 |
| B | ao | 1 | 123 | 5.49 | 22.40 | 3092 | 17 | 12.16 | 1.39 | 603 (15.1%) | $3.70 | 1/0/0 | 117191 |
| B | ao | 2 | 74 | 6.50 | 11.40 | 3590 | 10 | 14.77 | 1.47 | 602 (15.0%) | $4.61 | 1/0/0 | 230252 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 682 | 3 | 2.41 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 757 | 1 | 2.68 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 770 | 7 | 3.25 | 0.27 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 920 | 5 | 3.73 | 0.38 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 941 | 7 | 3.59 | 0.37 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 6.48 | 15.10 | 2850 | 12 | 11.06 | 1.51 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 131102 |
| B | ctl-seed | 1 | 98 | 6.46 | 15.20 | 2758 | 6 | 10.64 | 1.37 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 125252 |
| B | ctl-seed | 2 | 98 | 6.49 | 15.10 | 2845 | 9 | 11.10 | 1.49 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 131125 |
| B | gepa | 0 | 148 | 6.49 | 22.80 | 2658 | 13 | 12.09 | 1.20 | 171 (4.3%) | $0.61 | 8/8/3 | 92463 |
| B | gepa | 1 | 151 | 6.49 | 23.20 | 2328 | 8 | 10.06 | 1.05 | 169 (4.2%) | $0.62 | 9/9/2 | 75873 |
| B | gepa | 2 | 148 | 6.48 | 22.80 | 2549 | 17 | 11.09 | 1.10 | 163 (4.1%) | $0.55 | 7/7/3 | 84769 |
| B | hc | 0 | 147 | 6.50 | 22.60 | 3715 | 13 | 16.09 | 1.88 | 278 (6.9%) | $1.65 | 2/1/0 | 126376 |
| B | hc | 1 | 147 | 6.49 | 22.60 | 3942 | 18 | 16.26 | 1.89 | 378 (9.4%) | $2.06 | 3/2/0 | 128435 |
| B | hc | 2 | 98 | 6.49 | 15.10 | 3910 | 21 | 17.52 | 2.59 | 154 (3.9%) | $0.92 | 1/0/0 | 210136 |
| C | ao | 0 | 0 | 0.79 | n/a | 238 | 0 | 0.84 | 0.11 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ao | 1 | 0 | 0.79 | n/a | 259 | 1 | 0.98 | 0.12 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ao | 2 | 0 | 0.78 | n/a | 245 | 0 | 0.82 | 0.10 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 0 | 0 | 0.79 | n/a | 243 | 0 | 0.84 | 0.10 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 1 | 0 | 0.78 | n/a | 242 | 1 | 0.83 | 0.12 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-oneshot | 2 | 0 | 0.78 | n/a | 255 | 1 | 0.96 | 0.11 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | ctl-seed | 0 | n/a | 0.78 | n/a | 167 | 1 | 0.59 | 0.09 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | ctl-seed | 1 | n/a | 0.78 | n/a | 173 | 0 | 0.57 | 0.06 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | ctl-seed | 2 | n/a | 0.78 | n/a | 186 | 0 | 0.67 | 0.10 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | n/a |
| C | gepa | 0 | 10 | 0.79 | 12.60 | 196 | 0 | 0.54 | 0.10 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 64273 |
| C | gepa | 1 | 10 | 0.79 | 12.70 | 222 | 0 | 0.69 | 0.11 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 79947 |
| C | gepa | 2 | 13 | 0.78 | 16.60 | 193 | 0 | 0.50 | 0.08 | 0 (0.0%) | n/a (unpriced) | 1/1/0 | 44145 |
| C | hc | 0 | 0 | 0.79 | n/a | 246 | 9 | 0.81 | 0.11 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | hc | 1 | 0 | 0.79 | n/a | 262 | 1 | 1.01 | 0.11 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |
| C | hc | 2 | 0 | 0.78 | n/a | 273 | 5 | 1.02 | 0.11 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | n/a |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 122662 | 122662 | 134381 | 192394 | $0.53 |
| A | ao | 3 | 58524 | 58524 | 58524 | 0 | n/a |
| A | evoskill | 3 | 14330 | 14330 | 14330 | 0 | n/a |
| A | gepa | 3 | 34405 | 34405 | 34929 | 95243 | $0.32 |
| A | hc | 3 | 54452 | 54452 | 54452 | 0 | n/a |
| A | metaharness | 3 | 58591 | 58591 | 58702 | 16589 | $0.21 |
| A | mipro | 3 | 49311 | 49311 | 51440 | 59609 | $0.59 |
| A | skillopt | 3 | 50805 | 50805 | 54890 | 561345 | $1.31 |
| A | trace2skill | 3 | 51242 | 51242 | 51242 | 0 | n/a |
| A | wikiskill | 3 | 54348 | 54348 | 54348 | 0 | n/a |
| B | ao | 3 | 135389 | 149758 | 158186 | 608700 | $4.02 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 111539 | 126395 | 129160 | 0 | n/a |
| B | gepa | 3 | 74403 | 81898 | 84368 | 167432 | $0.59 |
| B | hc | 3 | 132939 | 150274 | 154982 | 269951 | $1.54 |
| C | gepa | 3 | 53644 | 62788 | 62788 | 0 | n/a |

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

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, A/metaharness/s1, A/metaharness/s2, C/ao/s0, C/ao/s1, C/ao/s2, C/ctl-oneshot/s0, C/ctl-oneshot/s1, C/ctl-oneshot/s2, C/ctl-seed/s0, C/ctl-seed/s1, C/ctl-seed/s2, C/gepa/s0, C/gepa/s1, C/hc/s0, C/hc/s1, C/hc/s2
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
