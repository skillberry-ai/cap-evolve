# Attribution analyses

Stage: search-time only, final pending. All search-time numbers are on each run's own selection split, not held-out; selection-split gains are optimistic and noisy (A has one trial per task), and fixed/broke counts include noise flips. Final-set columns stay empty until `final_eval/{A,B,C}/results_long.csv` exists.

## Promotions per search and inert searches

| suite | arm | searches | cands | promotions | per search | inert | running | crashed |
|---|---|---|---|---|---|---|---|---|
| A | gepa | 3 | 48 | 28 | 9.33 | 0 | 0 | 3 |
| A | skillopt | 3 | 23 | 13 | 4.33 | 0 | 0 | 1 |
| A | metaharness | 3 | 24 | 11 | 3.67 | 0 | 0 | 0 |
| A | evoskill | 3 | 24 | 18 | 6.00 | 0 | 0 | 0 |
| A | wikiskill | 3 | 9 | 5 | 1.67 | 0 | 3 | 0 |
| A | trace2skill | 3 | 6 | 3 | 1.00 | 0 | 0 | 0 |
| A | ace | 3 | 1 | 0 | 0.00 | 1 | 3 | 0 |
| A | mipro | 3 | 29 | 0 | 0.00 | 2 | 3 | 0 |
| A | hc | 3 | 15 | 2 | 0.67 | 1 | 2 | 0 |
| A | ao | 3 | 3 | 0 | 0.00 | 3 | 0 | 0 |
| A-E12 | hcstock | 3 | 36 | 7 | 2.33 | 0 | 0 | 0 |
| B | oneshot | 3 | 3 | 1 | 0.33 | 2 | 0 | 0 |
| B | gepa | 3 | 62 | 20 | 6.67 | 0 | 3 | 0 |
| B | harnesslens | 3 | 0 | 0 | 0.00 | 0 | 3 | 0 |
| B | hc | 3 | 14 | 0 | 0.00 | 3 | 3 | 0 |
| B | ao | 3 | 3 | 0 | 0.00 | 3 | 1 | 0 |
| C | oneshot | 3 | 3 | 1 | 0.33 | 2 | 0 | 0 |
| C | gepa | 3 | 47 | 20 | 6.67 | 0 | 3 | 0 |
| C | hc | 3 | 16 | 2 | 0.67 | 1 | 3 | 0 |
| C | ao | 3 | 1 | 0 | 0.00 | 3 | 0 | 0 |
| C-E12 | hcstock | 3 | 29 | 3 | 1.00 | 1 | 1 | 0 |
| C-E12 | bestofk | 3 | 19 | 0 | 0.00 | 0 | 0 | 0 |

## Regressions (CapEvolve arms)

| suite | arm | cands | promoted | fixed/prom | broke/prom | net/prom | broke/rejected | protect viol/prom | fresh confirm delta/prom |
|---|---|---|---|---|---|---|---|---|---|
| A | hc | 11 | 2 | 8.0 | 3.0 | 5.0 | 1.1 | 3.0 | 0.125 |
| A | hcstock | 36 | 7 | 7.7 | 2.3 | 5.4 | 3.1 | 1.9 | -- |
| B | hc | 16 | 0 | -- | -- | -- | 7.1 | -- | -- |
| B | oneshot | 3 | 1 | 11.0 | 4.0 | 7.0 | 8.0 | 4.0 | -- |
| C | hc | 16 | 2 | 3.0 | 0.5 | 2.5 | 1.9 | 0.5 | 0.121 |
| C | hcstock | 29 | 3 | 4.7 | 1.3 | 3.3 | 3.4 | 1.0 | -- |
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
| A | hc | system_prompt | 11/11 | 2 | 0.218 | 9.6 | 1.5 | 0.84 | surface touched by every candidate: no contrast available |
| A | hc | task_template | 11/11 | 2 | 0.218 | 9.6 | 1.5 | 0.40 | surface touched by every candidate: no contrast available |
| A | hcstock | system_prompt | 36/36 | 7 | 0.017 | 3.6 | 2.9 | -0.53 | surface touched by every candidate: no contrast available |
| A | hcstock | task_template | 36/36 | 7 | 0.017 | 3.6 | 2.9 | -0.25 | surface touched by every candidate: no contrast available |
| B | hc | system_prompt | 9/16 | 0 | 0.010 | 7.3 | 6.9 | 0.22 |  |
| B | hc | tool_code | 14/16 | 0 | -0.007 | 6.8 | 7.1 | -0.16 |  |
| B | oneshot | system_prompt | 3/3 | 1 | 0.017 | 7.7 | 6.7 | -- | surface touched by every candidate: no contrast available |
| B | oneshot | tool_code | 3/3 | 1 | 0.017 | 7.7 | 6.7 | -- | surface touched by every candidate: no contrast available |
| C | hc | system_prompt | 16/16 | 2 | 0.072 | 3.1 | 1.7 | 0.55 | surface touched by every candidate: no contrast available |
| C | hc | tool_code | 16/16 | 2 | 0.072 | 3.1 | 1.7 | 0.61 | surface touched by every candidate: no contrast available |
| C | hcstock | system_prompt | 28/29 | 3 | -0.059 | 2.0 | 3.1 | -0.25 |  |
| C | hcstock | tool_code | 29/29 | 3 | -0.062 | 2.0 | 3.2 | -0.29 | surface touched by every candidate: no contrast available |
| C | oneshot | system_prompt | 3/3 | 1 | 0.088 | 3.7 | 2.0 | -- | surface touched by every candidate: no contrast available |
| C | oneshot | tool_code | 3/3 | 1 | 0.088 | 3.7 | 2.0 | -- | surface touched by every candidate: no contrast available |

## Shrinkage and cost per point

See shrinkage.csv and cost_per_point.csv (final columns empty until the final evaluation).
