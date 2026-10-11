# Error-label parity: adapter label vs uniform classifier

Rule (all arms): infra = transport/timeout/sandbox-HTTP error string, or zero target-LLM calls with an error; otherwise candidate. Adapter label kept in `error_kind_adapter` of rollout_metrics.csv. Only rows with an adapter label or an error string are counted in `errors`.

| suite | arm | seed | cat | rollouts | errors | adapter infra | adapter cand. | uniform infra | uniform cand. | cand->infra | infra->cand. | unlabelled->infra | infra by 0 calls, no string | adapter-infra unverifiable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | ace | 1 | main | 28 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | ace | 2 | main | 24 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | ao | 0 | main | 40 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| A | ao | 1 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| A | ao | 2 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| A | evoskill | 0 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| A | evoskill | 1 | main | 36 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| A | evoskill | 2 | main | 31 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| A | gepa | 0 | main | 56 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 1 |
| A | gepa | 1 | main | 56 | 4 | 4 | 0 | 0 | 4 | 0 | 4 | 0 | 0 | 4 |
| A | gepa | 2 | main | 60 | 2 | 2 | 0 | 0 | 2 | 0 | 2 | 0 | 0 | 2 |
| A | hc | 0 | main | 40 | 2 | 2 | 0 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| A | hc | 1 | main | 40 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| A | hc | 2 | main | 40 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 3 | 0 |
| A | memento | 0 | stopped | 11 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | metaharness | 0 | main | 120 | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 6 | 0 |
| A | metaharness | 1 | main | 120 | 15 | 15 | 0 | 13 | 2 | 0 | 2 | 0 | 13 | 2 |
| A | metaharness | 2 | main | 120 | 9 | 9 | 0 | 8 | 1 | 0 | 1 | 0 | 8 | 1 |
| A | mipro | 0 | main | 45 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | mipro | 1 | main | 32 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 0 | main | 200 | 85 | 5 | 80 | 5 | 80 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 1 | main | 160 | 9 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 |
| A | skillopt | 2 | main | 200 | 53 | 13 | 40 | 13 | 40 | 0 | 0 | 0 | 0 | 0 |
| A | trace2skill | 0 | main | 93 | 7 | 0 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 |
| A | trace2skill | 1 | main | 93 | 6 | 0 | 6 | 5 | 1 | 5 | 0 | 0 | 0 | 0 |
| A | trace2skill | 2 | main | 92 | 14 | 0 | 14 | 14 | 0 | 14 | 0 | 0 | 0 | 0 |
| A | wikiskill | 0 | main | 52 | 3 | 0 | 3 | 3 | 0 | 3 | 0 | 0 | 3 | 0 |
| A | wikiskill | 1 | main | 50 | 2 | 0 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 0 |
| A | wikiskill | 2 | main | 49 | 3 | 0 | 3 | 3 | 0 | 3 | 0 | 0 | 3 | 0 |
| B | ao | 0 | main | 172 | 2 | 2 | 0 | 0 | 2 | 0 | 2 | 0 | 0 | 2 |
| B | ctl-oneshot | 0 | main | 123 | 7 | 7 | 0 | 6 | 1 | 0 | 1 | 0 | 6 | 1 |
| B | ctl-oneshot | 1 | main | 148 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 1 |
| B | hc | 0 | main | 147 | 2 | 2 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 1 |
| B | hc | 1 | main | 196 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 1 |
| B | hc | 2 | main | 98 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 1 |
| C | ctl-oneshot | 1 | main | 40 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| C | ctl-oneshot | 2 | main | 40 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 1 |
