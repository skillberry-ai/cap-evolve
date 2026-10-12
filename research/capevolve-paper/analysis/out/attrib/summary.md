# Attribution analyses

Stage: search-time only, final pending. All search-time numbers are on each run's own selection split, not held-out; selection-split gains are optimistic and noisy (A has one trial per task), and fixed/broke counts include noise flips. Final-set columns stay empty until `final_eval/{A,B,C}/results_long.csv` exists.

## Promotions per search and inert searches

| suite | arm | searches | cands | promotions | per search | inert | running | crashed |
|---|---|---|---|---|---|---|---|---|
| A | gepa | 3 | 43 | 25 | 8.33 | 0 | 3 | 0 |
| A | skillopt | 3 | 19 | 11 | 3.67 | 0 | 3 | 0 |
| A | metaharness | 3 | 24 | 11 | 3.67 | 0 | 1 | 0 |
| A | evoskill | 3 | 20 | 17 | 5.67 | 0 | 2 | 0 |
| A | wikiskill | 3 | 4 | 2 | 0.67 | 1 | 3 | 0 |
| A | trace2skill | 3 | 6 | 3 | 1.00 | 0 | 0 | 0 |
| A | ace | 3 | 0 | 0 | 0.00 | 0 | 3 | 0 |
| A | mipro | 3 | 24 | 0 | 0.00 | 3 | 3 | 0 |
| A | hc | 3 | 8 | 1 | 0.33 | 2 | 3 | 0 |
| A | ao | 3 | 3 | 0 | 0.00 | 3 | 3 | 0 |
| A-E12 | hcstock | 3 | 22 | 6 | 2.00 | 0 | 3 | 0 |
| B | oneshot | 3 | 3 | 1 | 0.33 | 2 | 0 | 0 |
| B | gepa | 3 | 47 | 16 | 5.33 | 0 | 3 | 0 |
| B | harnesslens | 3 | 0 | 0 | 0.00 | 0 | 1 | 0 |
| B | hc | 3 | 11 | 0 | 0.00 | 3 | 3 | 0 |
| B | ao | 3 | 3 | 0 | 0.00 | 3 | 1 | 0 |
| C | oneshot | 3 | 3 | 1 | 0.33 | 2 | 0 | 0 |
| C | gepa | 3 | 31 | 14 | 4.67 | 0 | 3 | 0 |
| C | hc | 3 | 9 | 0 | 0.00 | 3 | 3 | 0 |
| C | ao | 3 | 1 | 0 | 0.00 | 3 | 0 | 0 |
| C-E12 | hcstock | 3 | 19 | 3 | 1.00 | 1 | 3 | 0 |
| C-E12 | bestofk | 3 | 19 | 0 | 0.00 | 0 | 3 | 0 |

## Regressions (CapEvolve arms)

| suite | arm | cands | promoted | fixed/prom | broke/prom | net/prom | broke/rejected | protect viol/prom | fresh confirm delta/prom |
|---|---|---|---|---|---|---|---|---|---|
| A | hc | 5 | 1 | 7.0 | 3.0 | 4.0 | 1.5 | 3.0 | 0.133 |
| A | hcstock | 19 | 6 | 8.3 | 2.5 | 5.8 | 3.6 | 2.2 | -- |
| B | hc | 12 | 0 | -- | -- | -- | 7.2 | -- | -- |
| B | oneshot | 3 | 1 | 11.0 | 4.0 | 7.0 | 8.0 | 4.0 | -- |
| C | hc | 12 | 0 | -- | -- | -- | 2.0 | -- | -- |
| C | hcstock | 19 | 3 | 4.7 | 1.3 | 3.3 | 3.6 | 1.0 | -- |
| C | oneshot | 3 | 1 | 5.0 | 1.0 | 4.0 | 2.5 | 1.0 | -- |

## Seed failure types (groups)

| suite | arm | type | n |
|---|---|---|---|
| A | ao | infra | 5 |
| A | ao | no_output_file | 26 |
| A | ao | wrong_result | 28 |
| A | hc | infra | 6 |
| A | hc | no_output_file | 27 |
| A | hc | wrong_result | 21 |
| A | hcstock | infra | 5 |
| A | hcstock | no_output_file | 26 |
| A | hcstock | wrong_result | 26 |
| B | ao | communication | 5 |
| B | ao | infra | 1 |
| B | ao | missing_action | 18 |
| B | ao | other | 5 |
| B | ao | state_side_effect | 5 |
| B | ao | wrong_argument | 24 |
| B | hc | communication | 3 |
| B | hc | infra | 1 |
| B | hc | missing_action | 23 |
| B | hc | other | 7 |
| B | hc | state_side_effect | 4 |
| B | hc | wrong_argument | 25 |
| B | oneshot | communication | 5 |
| B | oneshot | infra | 1 |
| B | oneshot | missing_action | 17 |
| B | oneshot | other | 6 |
| B | oneshot | state_side_effect | 4 |
| B | oneshot | wrong_argument | 27 |
| C | ao | missing_action | 10 |
| C | ao | other | 3 |
| C | ao | state_side_effect | 5 |
| C | ao | wrong_argument | 11 |
| C | hc | communication | 2 |
| C | hc | missing_action | 12 |
| C | hc | other | 3 |
| C | hc | state_side_effect | 1 |
| C | hc | wrong_argument | 13 |
| C | hcstock | communication | 2 |
| C | hcstock | infra | 1 |
| C | hcstock | missing_action | 9 |
| C | hcstock | other | 3 |
| C | hcstock | state_side_effect | 1 |
| C | hcstock | wrong_argument | 12 |
| C | oneshot | infra | 1 |
| C | oneshot | missing_action | 10 |
| C | oneshot | other | 7 |
| C | oneshot | wrong_argument | 11 |

## Attribution by surface

| suite | arm | surface | touching/total | promoted | mean delta | fixed | broke | rho | note |
|---|---|---|---|---|---|---|---|---|---|
| A | hc | system_prompt | 5/5 | 1 | 0.175 | 8.8 | 2.2 | 0.05 | surface touched by every candidate: no contrast available |
| A | hc | task_template | 5/5 | 1 | 0.175 | 8.8 | 2.2 | 0.71 | surface touched by every candidate: no contrast available |
| A | hcstock | system_prompt | 19/19 | 6 | 0.040 | 4.8 | 3.3 | -0.60 | surface touched by every candidate: no contrast available |
| A | hcstock | task_template | 19/19 | 6 | 0.040 | 4.8 | 3.3 | -0.29 | surface touched by every candidate: no contrast available |
| B | hc | system_prompt | 8/12 | 0 | 0.000 | 7.1 | 7.1 | 0.38 |  |
| B | hc | tool_code | 11/12 | 0 | -0.007 | 6.8 | 7.2 | -0.22 |  |
| B | oneshot | system_prompt | 3/3 | 1 | 0.017 | 7.7 | 6.7 | -- | surface touched by every candidate: no contrast available |
| B | oneshot | tool_code | 3/3 | 1 | 0.017 | 7.7 | 6.7 | -- | surface touched by every candidate: no contrast available |
| C | hc | system_prompt | 9/12 | 0 | 0.057 | 3.1 | 2.0 | -0.33 |  |
| C | hc | tool_code | 9/12 | 0 | 0.057 | 3.1 | 2.0 | -0.14 |  |
| C | hcstock | system_prompt | 19/19 | 3 | -0.052 | 2.3 | 3.3 | -0.29 | surface touched by every candidate: no contrast available |
| C | hcstock | tool_code | 19/19 | 3 | -0.052 | 2.3 | 3.3 | -0.31 | surface touched by every candidate: no contrast available |
| C | oneshot | system_prompt | 3/3 | 1 | 0.088 | 3.7 | 2.0 | -- | surface touched by every candidate: no contrast available |
| C | oneshot | tool_code | 3/3 | 1 | 0.088 | 3.7 | 2.0 | -- | surface touched by every candidate: no contrast available |

## Shrinkage and cost per point

See shrinkage.csv and cost_per_point.csv (final columns empty until the final evaluation).
