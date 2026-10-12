# Error-label parity: adapter label vs uniform classifier

Rule (all arms): infra = transport/timeout/sandbox-HTTP error string, or zero target-LLM calls with an error; otherwise candidate. Adapter label kept in `error_kind_adapter` of rollout_metrics.csv. Only rows with an adapter label or an error string are counted in `errors`.

| suite | arm | seed | cat | rollouts | errors | adapter infra | adapter cand. | uniform infra | uniform cand. | uniform unverifiable | cand->infra | infra->cand. | unlabelled->infra | infra by 0 calls, no string | adapter-infra unverifiable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | ace | 2 | main | 15 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |
| A | ao | 0 | main | 120 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | ao | 1 | main | 120 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | ao | 2 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | evoskill | 0 | main | 191 | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| A | evoskill | 1 | main | 160 | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 0 |
| A | evoskill | 2 | main | 96 | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 0 |
| A | gepa | 0 | main | 57 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | gepa | 1 | main | 57 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | gepa | 2 | main | 62 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | hc | 0 | main | 120 | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | hc | 1 | main | 160 | 10 | 10 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | hc | 2 | main | 120 | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | memento | 0 | stopped | 11 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 0 | main | 240 | 11 | 11 | 0 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 1 | main | 300 | 29 | 29 | 0 | 29 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 2 | main | 300 | 25 | 25 | 0 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | mipro | 0 | main | 78 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | mipro | 1 | main | 89 | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | mipro | 2 | main | 83 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 0 | main | 320 | 92 | 12 | 80 | 12 | 80 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 1 | main | 320 | 17 | 17 | 0 | 17 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 2 | main | 280 | 57 | 17 | 40 | 17 | 40 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 0 | main | 200 | 15 | 15 | 0 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 1 | main | 200 | 15 | 15 | 0 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 2 | main | 202 | 21 | 21 | 0 | 19 | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| A | wikiskill | 0 | main | 59 | 6 | 3 | 3 | 6 | 0 | 0 | 3 | 0 | 0 | 6 | 0 |
| A | wikiskill | 1 | main | 65 | 8 | 6 | 2 | 8 | 0 | 0 | 2 | 0 | 0 | 8 | 0 |
| A | wikiskill | 2 | main | 59 | 4 | 1 | 3 | 4 | 0 | 0 | 3 | 0 | 0 | 4 | 0 |
| A-E12 | hcstock | 0 | main | 40 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A-E12 | hcstock | 1 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| A-E12 | hcstock | 2 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | ao | 0 | main | 173 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | ctl-oneshot | 0 | main | 123 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | ctl-oneshot | 1 | main | 148 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | hc | 0 | main | 147 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | hc | 1 | main | 294 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | hc | 2 | main | 245 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ao | 2 | main | 41 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ctl-oneshot | 0 | main | 60 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ctl-oneshot | 1 | main | 50 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | ctl-oneshot | 2 | main | 50 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C | gepa | 2 | main | 70 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| C | hc | 0 | main | 60 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C-E12 | hcstock | 0 | main | 40 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C-E12 | hcstock | 2 | main | 60 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
