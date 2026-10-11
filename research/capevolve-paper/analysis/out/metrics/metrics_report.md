# Campaign metrics report

Generated 2026-10-11T18:09:09Z UTC from `/home/dev/projects2/campaign-scratch/logs/gateway_calls.jsonl` (newest call 2026-10-11T18:09:10Z). Re-run: `refresh_metrics.sh --once`.
USD = proxy Anthropic list prices, Claude models only; RITS/Azure/GCP/gpt-oss are unpriced (tokens only, never $0); `lb` = priced sum is a lower bound.

## Reconciliation with gateway /health

| quantity | /health | recomputed from log (first 90193 calls) | diff |
|---|---:|---:|---:|
| total_tokens | 457,069,666 | 457,069,666 | 0 |
| rits_tokens | 443,248,930 | 443,248,930 | 0 |
| capped_tokens (non-RITS) | 13,820,736 | 13,820,736 | 0 |
| calls | 90193 | 90193 | 0 |

Gateway ledger counts usage.total_tokens when the upstream supplies it; for non-streamed Anthropic calls total_tokens = input+output and omits cache_creation tokens, so those cache writes are in the usage fields but not in the ledger (see naive_sum_... for the size).
Naive Anthropic sum (input+output+cache_creation) minus ledger, by model/api/stream: `{"('claude-sonnet-5', 'anthropic', False)": 144064}`

## Campaign totals

| scope | calls | errors | ledger tokens | RITS tokens | non-RITS tokens | proxy USD (priced) | unpriced non-cache tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| overall | 90,195 | 577 | 457,071,995 | 443,251,259 | 13,820,736 | $43.85 lb | 447,278,383 |
| suite - | 2,019 | 126 | 11,664,822 | 9,998,051 | 1,666,771 | $4.98 lb | 10,142,610 |
| suite A | 18,665 | 136 | 118,269,539 | 115,411,989 | 2,857,550 | $7.81 lb | 115,411,989 |
| suite B | 69,511 | 315 | 327,137,634 | 317,841,219 | 9,296,415 | $31.06 lb | 321,723,784 |

By suite and category (overhead = everything except main/chaser_eval):

| suite|category | calls | ledger tokens | RITS tokens | proxy USD |
|---|---:|---:|---:|---:|
| -|smoke | 1,968 | 11,352,781 | 9,998,051 | $3.97 |
| -|untagged | 51 | 312,041 | 0 | $1.01 |
| A|main | 14,812 | 98,003,836 | 96,205,467 | $4.57 |
| A|no_run_dir | 87 | 427,805 | 273,517 | $0.33 |
| A|restart_waste | 2,977 | 15,578,382 | 15,467,133 | $0.35 |
| A|smoke | 411 | 2,120,487 | 1,377,479 | $2.15 |
| A|stopped | 378 | 2,139,029 | 2,088,393 | $0.41 |
| B|chaser_eval | 3,856 | 15,943,566 | 15,694,124 | $0.00 |
| B|main | 42,832 | 204,148,055 | 196,927,381 | $21.37 |
| B|pilot | 2,246 | 10,600,502 | 10,051,427 | $2.04 |
| B|restart_waste | 20,275 | 95,165,567 | 93,924,697 | $7.56 |
| B|smoke | 302 | 1,279,944 | 1,243,590 | $0.09 |

## Per arm x seed (main + chaser evaluation)

| suite | arm | seed | counted rollouts | wall h | rollouts/h | calls | err | target Mtok | user Mtok | optimizer non-cache ktok (cap 4M) | optimizer USD (proxy) | cand created/eval/acc | tok per rollout (all roles) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | ace | 0 | 16 | 5.12 | 3.10 | 139 | 0 | 1.36 | 0.00 | 169 (4.2%) | $0.49 | 0/0/0 | 95381 |
| A | ace | 1 | 6 | 5.13 | 1.20 | 111 | 0 | 1.38 | 0.00 | 45 (1.1%) | $0.13 | 0/0/0 | 238132 |
| A | ace | 2 | 14 | 5.14 | 2.70 | 145 | 0 | 1.16 | 0.00 | 186 (4.7%) | $0.51 | 0/0/0 | 95811 |
| A | ao | 0 | 40 | 3.44 | 11.60 | 363 | 0 | 2.14 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 53606 |
| A | ao | 1 | 40 | 3.42 | 11.70 | 354 | 0 | 2.30 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 57608 |
| A | ao | 2 | 37 | 3.44 | 10.80 | 367 | 0 | 2.53 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 68285 |
| A | evoskill | 0 | 40 | 0.12 | n/a | 9 | 0 | 0.01 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 344 |
| A | evoskill | 1 | 44 | 0.07 | n/a | 6 | 0 | 0.00 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 90 |
| A | evoskill | 2 | 44 | 0.11 | n/a | 12 | 0 | 0.01 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 338 |
| A | gepa | 0 | 140 | 9.79 | 14.30 | 800 | 2 | 4.44 | 0.00 | 54 (1.3%) | $0.17 | 3/2/2 | 32067 |
| A | gepa | 1 | 89 | 9.80 | 9.10 | 756 | 9 | 6.01 | 0.00 | 27 (0.7%) | $0.09 | 1/1/1 | 67847 |
| A | gepa | 2 | 193 | 9.77 | 19.70 | 837 | 3 | 4.53 | 0.00 | 98 (2.5%) | $0.32 | 5/4/4 | 23963 |
| A | hc | 0 | 45 | 3.45 | 13.10 | 339 | 0 | 1.97 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 43755 |
| A | hc | 1 | 40 | 3.46 | 11.60 | 369 | 0 | 2.37 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 59300 |
| A | hc | 2 | 45 | 3.45 | 13.00 | 326 | 0 | 1.92 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 42599 |
| A | metaharness | 0 | 120 | 7.20 | 16.70 | 947 | 7 | 6.11 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 50887 |
| A | metaharness | 1 | 113 | 7.21 | 15.70 | 985 | 2 | 6.04 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 53485 |
| A | metaharness | 2 | 109 | 7.21 | 15.10 | 957 | 3 | 6.43 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 58981 |
| A | mipro | 0 | 20 | 5.13 | 3.90 | 134 | 1 | 0.97 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 48337 |
| A | mipro | 1 | 14 | 5.10 | 2.70 | 120 | 0 | 1.15 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 82302 |
| A | mipro | 2 | 14 | 5.12 | 2.70 | 108 | 0 | 0.86 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 61369 |
| A | skillopt | 0 | 114 | 9.80 | 11.60 | 979 | 7 | 6.42 | 0.00 | 417 (10.4%) | $0.97 | 2/2/1 | 59982 |
| A | skillopt | 1 | 115 | 9.79 | 11.70 | 885 | 5 | 6.05 | 0.00 | 437 (10.9%) | $1.00 | 1/1/1 | 56398 |
| A | skillopt | 2 | 145 | 9.79 | 14.80 | 1029 | 13 | 6.23 | 0.00 | 366 (9.2%) | $0.88 | 2/2/2 | 45492 |
| A | trace2skill | 0 | 103 | 9.30 | 11.10 | 806 | 2 | 5.35 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/0/0 | 51919 |
| A | trace2skill | 1 | 102 | 9.30 | 11.00 | 798 | 13 | 4.96 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 48662 |
| A | trace2skill | 2 | 103 | 9.30 | 11.10 | 770 | 11 | 4.77 | 0.00 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 46334 |
| A | wikiskill | 0 | 56 | 5.08 | 11.00 | 451 | 0 | 2.81 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 50159 |
| A | wikiskill | 1 | 59 | 5.10 | 11.60 | 472 | 0 | 3.04 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 51466 |
| A | wikiskill | 2 | 56 | 5.10 | 11.00 | 438 | 0 | 2.88 | 0.00 | 0 (0.0%) | n/a (unpriced) | 1/1/1 | 51481 |
| B | ao | 0 | 123 | 5.50 | 22.30 | 3057 | 23 | 11.39 | 1.33 | 621 (15.5%) | $3.75 | 2/1/0 | 110492 |
| B | ao | 1 | 123 | 5.49 | 22.40 | 3092 | 17 | 12.16 | 1.39 | 603 (15.1%) | $3.70 | 1/0/0 | 117191 |
| B | ao | 2 | 74 | 5.51 | 13.40 | 3115 | 9 | 12.63 | 1.27 | 602 (15.0%) | $4.61 | 1/0/0 | 198593 |
| B | chaser-ao | 0 | n/a | n/a | n/a | 682 | 3 | 2.41 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 1 | n/a | n/a | n/a | 757 | 1 | 2.68 | 0.32 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ao | 2 | n/a | n/a | n/a | 699 | 0 | 2.43 | 0.29 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 0 | n/a | n/a | n/a | 338 | 6 | 1.38 | 0.09 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 1 | n/a | n/a | n/a | 474 | 3 | 1.83 | 0.17 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | chaser-ctl-oneshot | 2 | n/a | n/a | n/a | 906 | 7 | 3.41 | 0.36 | 0 (0.0%) | n/a (unpriced) | n/a/n/a/n/a | n/a |
| B | ctl-oneshot | 0 | 123 | 5.12 | 24.00 | 3188 | 4 | 13.65 | 1.42 | 174 (4.4%) | $1.00 | 2/1/0 | 125651 |
| B | ctl-oneshot | 1 | 148 | 4.94 | 30.00 | 2945 | 12 | 11.77 | 1.32 | 199 (5.0%) | $1.37 | 2/1/1 | 91399 |
| B | ctl-oneshot | 2 | 123 | 4.41 | 27.90 | 2669 | 5 | 10.60 | 1.19 | 141 (3.5%) | $0.77 | 2/1/0 | 99074 |
| B | ctl-seed | 0 | 98 | 5.50 | 17.80 | 2588 | 12 | 10.16 | 1.39 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 120550 |
| B | ctl-seed | 1 | 98 | 5.51 | 17.80 | 2559 | 6 | 9.79 | 1.16 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 114320 |
| B | ctl-seed | 2 | 98 | 5.51 | 17.80 | 2592 | 7 | 10.19 | 1.32 | 0 (0.0%) | n/a (unpriced) | 0/0/0 | 120008 |
| B | gepa | 0 | 139 | 5.50 | 25.20 | 2479 | 13 | 11.20 | 1.12 | 149 (3.7%) | $0.53 | 7/7/2 | 91228 |
| B | gepa | 1 | 120 | 5.51 | 21.80 | 2059 | 7 | 8.88 | 0.95 | 150 (3.7%) | $0.54 | 7/7/2 | 84500 |
| B | gepa | 2 | 142 | 5.50 | 25.80 | 2278 | 16 | 9.81 | 0.98 | 139 (3.5%) | $0.47 | 7/7/2 | 78188 |
| B | hc | 0 | 98 | 5.50 | 17.80 | 3255 | 11 | 14.03 | 1.67 | 278 (6.9%) | $1.65 | 2/1/0 | 166086 |
| B | hc | 1 | 147 | 5.50 | 26.70 | 3481 | 18 | 14.42 | 1.66 | 378 (9.4%) | $2.06 | 3/2/0 | 114181 |
| B | hc | 2 | 98 | 5.50 | 17.80 | 3475 | 21 | 15.68 | 2.40 | 154 (3.9%) | $0.92 | 1/0/0 | 188942 |

## Deployment cost per task (target tokens per counted rollout) and cost per rollout, mean over seeds

Deployment cost per task = metered target(-role) tokens per counted rollout (incl. failed and retried attempts); tau2 also lists user-simulator tokens.

| suite | arm | seeds | target tok/rollout | target+user tok/rollout | all-role tok/rollout | optimizer non-cache tok per search | optimizer USD per search (proxy) |
|---|---|---:|---:|---:|---:|---:|---:|
| A | ace | 3 | 132644 | 132644 | 143108 | 133424 | $0.38 |
| A | ao | 3 | 59833 | 59833 | 59833 | 0 | n/a |
| A | evoskill | 3 | 257 | 257 | 257 | 0 | n/a |
| A | gepa | 3 | 40895 | 40895 | 41292 | 59514 | $0.20 |
| A | hc | 3 | 48551 | 48551 | 48551 | 0 | n/a |
| A | metaharness | 3 | 54451 | 54451 | 54451 | 0 | n/a |
| A | mipro | 3 | 64003 | 64003 | 64003 | 0 | n/a |
| A | skillopt | 3 | 50631 | 50631 | 53957 | 406519 | $0.95 |
| A | trace2skill | 3 | 48972 | 48972 | 48972 | 0 | n/a |
| A | wikiskill | 3 | 51035 | 51035 | 51035 | 0 | n/a |
| B | ao | 3 | 120717 | 133794 | 142092 | 608700 | $4.02 |
| B | ctl-oneshot | 3 | 92234 | 102285 | 105375 | 171421 | $1.05 |
| B | ctl-seed | 3 | 102527 | 115684 | 118293 | 0 | n/a |
| B | gepa | 3 | 74542 | 82168 | 84639 | 145905 | $0.51 |
| B | hc | 3 | 133741 | 151356 | 156403 | 269951 | $1.54 |

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
| A | evoskill | all | restart_waste | 775 | 2,540,630 | 2,540,630 | $0.00 |
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
| - | untagged | all | untagged | 51 | 312,041 | 0 | $1.01 |
| - | BL-hl-smoke5 | all | smoke | 28 | 296,477 | 94,782 | $0.57 |
| A | hc | all | smoke | 65 | 286,822 | 263,711 | $0.07 |
| - | BL-ace-smoke | all | smoke | 179 | 285,133 | 171,903 | $0.35 |
| - | BL-hl-smoke6 | all | smoke | 47 | 275,473 | 275,473 | $0.00 |
| - | BL-mce-smoke | all | smoke | 75 | 256,348 | 129,161 | $0.41 |
| - | BL-hl-smoke | all | smoke | 26 | 203,616 | 200,905 | $0.01 |
| A | E10-cfprobe | all | smoke | 86 | 180,158 | 0 | $0.77 |
| - | BL-skillopt-smoke | all | smoke | 44 | 176,669 | 142,711 | $0.11 |
| - | BL-gepa-smoke | all | smoke | 56 | 169,581 | 169,581 | $0.00 |
| A | memento | all | stopped | 82 | 165,440 | 165,440 | $0.00 |
| - | BL-hl-smoke3 | all | smoke | 23 | 121,156 | 121,156 | $0.00 |
| - | BL-metaharness-smoke | all | smoke | 43 | 119,562 | 94,330 | $0.10 |
| - | BL-graphskillevo-smoke | all | smoke | 18 | 76,722 | 51,846 | $0.14 |
| A | E10-evomock | all | smoke | 5 | 63,186 | 0 | $0.18 |
| - | BL-memento-smokefake | all | smoke | 12 | 62,318 | 0 | $0.34 |
| - | E00 | all | smoke | 6 | 41,475 | 41,475 | $0.00 |
| B | sbxtest | all | smoke | 1 | 30,614 | 0 | $0.08 |
| A | E10-tagprobe-api | all | smoke | 1 | 30,596 | 0 | $0.08 |
| A | E10-metaharness-smoke | all | smoke | 1 | 26,893 | 0 | $0.07 |
| A | E10-tagprobe-auth | all | smoke | 1 | 26,880 | 0 | $0.07 |
| A | E10-mh-negtest | all | smoke | 6 | 7,916 | 0 | $0.03 |
| - | BL-metrtest | all | smoke | 3 | 4,993 | 4,993 | $0.00 |
| - | BL-preflight | all | smoke | 3 | 4,847 | 4,847 | $0.00 |
| A | E10-evowd | all | smoke | 6 | 2,880 | 2,880 | $0.00 |
| - | E01 | all | smoke | 25 | 2,161 | 294 | $0.02 |
| B | judgetest | all | smoke | 1 | 369 | 0 | $0.00 |
| - | BL-hl-chk | all | smoke | 1 | 100 | 100 | $0.00 |
| - | BL-hl-check | all | smoke | 3 | 91 | 91 | $0.00 |
| A | E10-memento-smoke | all | smoke | 1 | 28 | 0 | $0.00 |
| B | probe | all | smoke | 5 | 12 | 0 | $0.00 |
| A | E10-tagprobe3 | all | smoke | 2 | 7 | 0 | $0.00 |

Restart cutoffs used (gateway calls before this time with the run's tag are counted as restart_waste):

- A/ace/s0: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/ace/s1: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/ace/s2: 2026-10-11T12:59:42Z (derived: birth time of launcher.log)
- A/ao/s0: 2026-10-11T14:41:25Z (derived: birth time of manifest/negtest.txt)
- A/evoskill/s0: 2026-10-11T13:05:19Z (derived: birth time of negtest_before_launch.txt)
- A/evoskill/s1: 2026-10-11T13:05:19Z (derived: birth time of negtest_before_launch.txt)
- A/evoskill/s2: 2026-10-11T13:05:20Z (derived: birth time of negtest_before_launch.txt)
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

- Runs without a per-rollout record: A/graphskillevo/s0, A/graphskillevo/s1, A/graphskillevo/s2, A/mce/s0, A/mce/s1, A/mce/s2, A/memento/s1, A/memento/s2, A/metaharness/s0, A/metaharness/s1, A/metaharness/s2
- Restart attribution is by time (tag is reused across attempts); cutoffs derived from file birth times are heuristics and are listed above.
- Gateway cannot attribute Claude Code optimizer calls whose tag was not forwarded; see `untagged` category.
