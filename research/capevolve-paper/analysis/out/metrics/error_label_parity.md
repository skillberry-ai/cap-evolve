# Error-label parity: adapter label vs uniform classifier

Rule (all arms): infra = transport/timeout/sandbox-HTTP error string, or zero target-LLM calls with an error; otherwise candidate. Adapter label kept in `error_kind_adapter` of rollout_metrics.csv. Only rows with an adapter label or an error string are counted in `errors`.

| suite | arm | seed | cat | rollouts | errors | adapter infra | adapter cand. | uniform infra | uniform cand. | uniform unverifiable | cand->infra | infra->cand. | unlabelled->infra | infra by 0 calls, no string | adapter-infra unverifiable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | ace | 0 | main | 163 | 16 | 16 | 0 | 16 | 0 | 0 | 0 | 0 | 0 | 16 | 0 |
| A | ace | 1 | main | 79 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| A | ace | 2 | main | 80 | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 0 |
| A | ao | 0 | main | 160 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | ao | 1 | main | 160 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | ao | 2 | main | 160 | 9 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | evoskill | 0 | main | 336 | 14 | 14 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 14 | 0 |
| A | evoskill | 1 | main | 354 | 9 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 0 |
| A | evoskill | 2 | main | 357 | 17 | 17 | 0 | 17 | 0 | 0 | 0 | 0 | 0 | 17 | 0 |
| A | gepa | 0 | main | 243 | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| A | gepa | 1 | main | 191 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 7 | 0 |
| A | gepa | 2 | main | 174 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |
| A | hc | 0 | main | 240 | 12 | 12 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | hc | 1 | main | 160 | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | hc | 2 | main | 160 | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | memento | 0 | stopped | 11 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 0 | main | 600 | 19 | 19 | 0 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 1 | main | 600 | 37 | 37 | 0 | 37 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 2 | main | 540 | 30 | 30 | 0 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | mipro | 0 | main | 134 | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | mipro | 1 | main | 152 | 7 | 7 | 0 | 6 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |
| A | mipro | 2 | main | 141 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 0 | main | 480 | 97 | 17 | 80 | 17 | 80 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 1 | main | 520 | 21 | 20 | 1 | 20 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 2 | main | 520 | 67 | 27 | 40 | 27 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 0 | main | 200 | 15 | 15 | 0 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 1 | main | 200 | 15 | 15 | 0 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 2 | main | 202 | 21 | 21 | 0 | 19 | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| A | wikiskill | 0 | main | 196 | 26 | 23 | 3 | 26 | 0 | 0 | 3 | 0 | 0 | 26 | 0 |
| A | wikiskill | 1 | main | 194 | 20 | 18 | 2 | 20 | 0 | 0 | 2 | 0 | 0 | 20 | 0 |
| A | wikiskill | 2 | main | 156 | 5 | 2 | 3 | 5 | 0 | 0 | 3 | 0 | 0 | 5 | 0 |
| A-E12 | hcstock | 0 | main | 320 | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A-E12 | hcstock | 1 | main | 440 | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A-E12 | hcstock | 2 | main | 360 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | ao | 0 | main | 173 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | ctl-oneshot | 0 | main | 123 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | ctl-oneshot | 1 | main | 148 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | hc | 0 | main | 294 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | hc | 1 | main | 392 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | hc | 2 | main | 392 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ao | 0 | main | 110 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ao | 2 | main | 71 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ctl-oneshot | 0 | main | 60 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ctl-oneshot | 1 | main | 50 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ctl-oneshot | 2 | main | 50 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | gepa | 2 | main | 126 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| C | hc | 0 | main | 200 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | hc | 1 | main | 119 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | hc | 2 | main | 180 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C-E12 | hcstock | 0 | main | 120 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C-E12 | hcstock | 2 | main | 160 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
