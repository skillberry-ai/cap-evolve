# Attribution analyses

Stage: search-time only, final pending. All search-time numbers are on each run's own selection split, not held-out; selection-split gains are optimistic and noisy (A has one trial per task), and fixed/broke counts include noise flips. Final-set columns stay empty until `final_eval/{A,B,C}/results_long.csv` exists.

## Promotions per search and inert searches

| suite | arm | searches | cands | promotions | per search | inert | running | crashed |
|---|---|---|---|---|---|---|---|---|
| A | gepa | 3 | 48 | 28 | 9.33 | 0 | 0 | 0 |
| A | skillopt | 3 | 23 | 13 | 4.33 | 0 | 0 | 0 |
| A | metaharness | 3 | 24 | 11 | 3.67 | 0 | 0 | 0 |
| A | evoskill | 3 | 24 | 18 | 6.00 | 0 | 0 | 0 |
| A | wikiskill | 3 | 11 | 6 | 2.00 | 0 | 2 | 0 |
| A | trace2skill | 3 | 6 | 3 | 1.00 | 0 | 0 | 0 |
| A | ace | 3 | 1 | 0 | 0.00 | 2 | 2 | 0 |
| A | mipro | 3 | 39 | 0 | 0.00 | 0 | 3 | 0 |
| A | hc | 3 | 20 | 2 | 0.67 | 1 | 0 | 0 |
| A | ao | 3 | 3 | 0 | 0.00 | 3 | 0 | 0 |
| A-E12 | hcstock | 3 | 36 | 7 | 2.33 | 0 | 0 | 0 |
| B | oneshot | 3 | 3 | 1 | 0.33 | 2 | 0 | 0 |
| B | gepa | 3 | 76 | 24 | 8.00 | 0 | 3 | 0 |
| B | harnesslens | 3 | 0 | 0 | 0.00 | 0 | 0 | 0 |
| B | hc | 3 | 16 | 0 | 0.00 | 3 | 0 | 0 |
| B | ao | 3 | 3 | 0 | 0.00 | 3 | 1 | 0 |
| C | oneshot | 3 | 3 | 1 | 0.33 | 2 | 0 | 0 |
| C | gepa | 3 | 63 | 23 | 7.67 | 0 | 3 | 0 |
| C | hc | 3 | 24 | 2 | 0.67 | 1 | 2 | 0 |
| C | ao | 3 | 1 | 0 | 0.00 | 3 | 0 | 0 |
| C-E12 | hcstock | 3 | 30 | 3 | 1.00 | 1 | 0 | 0 |
| C-E12 | bestofk | 3 | 28 | 0 | 0.00 | 0 | 0 | 0 |
| D | E20-CTL | 3 | 3 | 2 | 0.67 | 1 | 0 | 0 |
| D | E20-GEPA | 3 | 87 | 40 | 13.33 | 0 | 0 | 0 |
| D | E20-P | 3 | 30 | 5 | 1.67 | 0 | 0 | 0 |
| D | E20-T | 3 | 30 | 2 | 0.67 | 1 | 0 | 0 |
| D | E20-PT | 3 | 30 | 5 | 1.67 | 0 | 0 | 0 |
| D-E21 | E21-1S | 3 | 30 | 6 | 2.00 | 0 | 0 | 0 |
| D-E21 | E21-ruleP | 3 | 10 | 4 | 1.33 | 0 | 0 | 0 |
| D-E26 | E26-NOHIST | 3 | 30 | 5 | 1.67 | 0 | 0 | 0 |
| E | E30-P | 3 | 10 | 3 | 1.00 | 1 | 3 | 0 |
| E | E30-T | 3 | 5 | 3 | 1.00 | 0 | 3 | 0 |
| E | E30-PT | 3 | 6 | 2 | 0.67 | 1 | 3 | 0 |
| E-E31 | E31-ruleP | 3 | 3 | 0 | 0.00 | 3 | 3 | 0 |

## Regressions (CapEvolve arms)

| suite | arm | cands | promoted | fixed/prom | broke/prom | net/prom | broke/rejected | protect viol/prom | fresh confirm delta/prom |
|---|---|---|---|---|---|---|---|---|---|
| A | hc | 15 | 2 | 8.0 | 3.0 | 5.0 | 1.0 | 3.0 | 0.125 |
| A | hcstock | 36 | 7 | 7.7 | 2.3 | 5.4 | 3.1 | 1.9 | -- |
| B | hc | 14 | 0 | -- | -- | -- | 7.1 | -- | -- |
| B | oneshot | 3 | 1 | 11.0 | 4.0 | 7.0 | 8.0 | 4.0 | -- |
| C | hc | 24 | 2 | 3.0 | 0.5 | 2.5 | 2.0 | 0.5 | 0.121 |
| C | hcstock | 30 | 3 | 4.7 | 1.3 | 3.3 | 3.4 | 1.0 | -- |
| C | oneshot | 3 | 1 | 5.0 | 1.0 | 4.0 | 2.5 | 1.0 | -- |
| D | E20-CTL | 3 | 2 | 9.5 | 4.5 | 5.0 | 8.0 | 4.5 | -- |
| D | E20-P | 30 | 5 | 9.0 | 3.8 | 5.2 | 9.2 | 4.2 | -- |
| D | E20-PT | 30 | 5 | 10.2 | 3.8 | 6.4 | 6.3 | 3.0 | -- |
| D | E20-T | 30 | 2 | 10.5 | 4.0 | 6.5 | 7.5 | 4.0 | -- |
| D | E21-1S | 30 | 6 | 9.3 | 3.2 | 6.2 | 6.3 | 2.0 | -- |
| D | E21-ruleP | 10 | 4 | 11.8 | 5.5 | 6.2 | 6.7 | 4.5 | 0.099 |
| D | E26-NOHIST | 30 | 5 | 10.4 | 5.0 | 5.4 | 8.0 | 4.8 | -- |
| E | E30-P | 10 | 3 | 4.0 | 0.7 | 3.3 | 3.1 | 1.0 | -- |
| E | E30-PT | 6 | 2 | 4.5 | 0.0 | 4.5 | 1.5 | 0.0 | -- |
| E | E30-T | 5 | 3 | 4.7 | 1.0 | 3.7 | 2.0 | 1.0 | -- |
| E | E31-ruleP | 3 | 0 | -- | -- | -- | 0.3 | -- | -- |

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
| D | E20-CTL | communication | 5 |
| D | E20-CTL | infra | 1 |
| D | E20-CTL | missing_action | 16 |
| D | E20-CTL | other | 10 |
| D | E20-CTL | state_side_effect | 3 |
| D | E20-CTL | wrong_argument | 23 |
| D | E20-P | communication | 6 |
| D | E20-P | infra | 2 |
| D | E20-P | missing_action | 22 |
| D | E20-P | other | 12 |
| D | E20-P | state_side_effect | 3 |
| D | E20-P | wrong_argument | 19 |
| D | E20-PT | communication | 5 |
| D | E20-PT | missing_action | 28 |
| D | E20-PT | other | 10 |
| D | E20-PT | state_side_effect | 3 |
| D | E20-PT | wrong_argument | 22 |
| D | E20-T | communication | 4 |
| D | E20-T | missing_action | 24 |
| D | E20-T | other | 6 |
| D | E20-T | state_side_effect | 5 |
| D | E20-T | wrong_argument | 23 |
| D | E21-1S | communication | 10 |
| D | E21-1S | infra | 2 |
| D | E21-1S | missing_action | 23 |
| D | E21-1S | other | 6 |
| D | E21-1S | state_side_effect | 2 |
| D | E21-1S | wrong_argument | 24 |
| D | E21-ruleP | communication | 4 |
| D | E21-ruleP | infra | 1 |
| D | E21-ruleP | missing_action | 22 |
| D | E21-ruleP | other | 11 |
| D | E21-ruleP | state_side_effect | 4 |
| D | E21-ruleP | wrong_argument | 25 |
| D | E26-NOHIST | communication | 7 |
| D | E26-NOHIST | missing_action | 20 |
| D | E26-NOHIST | other | 7 |
| D | E26-NOHIST | state_side_effect | 2 |
| D | E26-NOHIST | wrong_argument | 25 |
| E | E30-P | communication | 3 |
| E | E30-P | missing_action | 7 |
| E | E30-P | other | 4 |
| E | E30-P | state_side_effect | 12 |
| E | E30-P | wrong_argument | 11 |
| E | E30-PT | communication | 4 |
| E | E30-PT | missing_action | 8 |
| E | E30-PT | other | 1 |
| E | E30-PT | state_side_effect | 12 |
| E | E30-PT | wrong_argument | 10 |
| E | E30-T | communication | 2 |
| E | E30-T | missing_action | 6 |
| E | E30-T | other | 3 |
| E | E30-T | state_side_effect | 16 |
| E | E30-T | wrong_argument | 14 |
| E | E31-ruleP | communication | 3 |
| E | E31-ruleP | missing_action | 9 |
| E | E31-ruleP | other | 2 |
| E | E31-ruleP | state_side_effect | 17 |
| E | E31-ruleP | wrong_argument | 12 |

## Attribution by surface

| suite | arm | surface | touching/total | promoted | mean delta | fixed | broke | rho | note |
|---|---|---|---|---|---|---|---|---|---|
| A | hc | system_prompt | 15/15 | 2 | 0.215 | 9.3 | 1.3 | 0.48 | surface touched by every candidate: no contrast available |
| A | hc | task_template | 15/15 | 2 | 0.215 | 9.3 | 1.3 | -0.38 | surface touched by every candidate: no contrast available |
| A | hcstock | system_prompt | 36/36 | 7 | 0.017 | 3.6 | 2.9 | -0.53 | surface touched by every candidate: no contrast available |
| A | hcstock | task_template | 36/36 | 7 | 0.017 | 3.6 | 2.9 | -0.25 | surface touched by every candidate: no contrast available |
| B | hc | system_prompt | 9/14 | 0 | 0.010 | 7.3 | 6.9 | 0.59 |  |
| B | hc | tool_code | 14/14 | 0 | -0.007 | 6.8 | 7.1 | 0.25 | surface touched by every candidate: no contrast available |
| B | oneshot | system_prompt | 3/3 | 1 | 0.017 | 7.7 | 6.7 | -- | surface touched by every candidate: no contrast available |
| B | oneshot | tool_code | 3/3 | 1 | 0.017 | 7.7 | 6.7 | -- | surface touched by every candidate: no contrast available |
| C | hc | system_prompt | 24/24 | 2 | 0.058 | 3.0 | 1.9 | 0.33 | surface touched by every candidate: no contrast available |
| C | hc | tool_code | 24/24 | 2 | 0.058 | 3.0 | 1.9 | 0.37 | surface touched by every candidate: no contrast available |
| C | hcstock | system_prompt | 29/30 | 3 | -0.059 | 2.0 | 3.1 | -0.26 |  |
| C | hcstock | tool_code | 30/30 | 3 | -0.062 | 2.0 | 3.2 | -0.29 | surface touched by every candidate: no contrast available |
| C | oneshot | system_prompt | 3/3 | 1 | 0.088 | 3.7 | 2.0 | -- | surface touched by every candidate: no contrast available |
| C | oneshot | tool_code | 3/3 | 1 | 0.088 | 3.7 | 2.0 | -- | surface touched by every candidate: no contrast available |
| D | E20-CTL | system_prompt | 3/3 | 2 | 0.069 | 9.0 | 5.7 | -- | surface touched by every candidate: no contrast available |
| D | E20-CTL | tool_code | 3/3 | 2 | 0.069 | 9.0 | 5.7 | -- | surface touched by every candidate: no contrast available |
| D | E20-P | system_prompt | 30/30 | 5 | -0.054 | 5.7 | 8.3 | -0.21 | surface touched by every candidate: no contrast available |
| D | E20-PT | system_prompt | 30/30 | 5 | 0.002 | 6.1 | 5.9 | -0.17 | surface touched by every candidate: no contrast available |
| D | E20-PT | tool_code | 30/30 | 5 | 0.002 | 6.1 | 5.9 | -0.24 | surface touched by every candidate: no contrast available |
| D | E20-T | tool_code | 29/30 | 2 | -0.016 | 6.4 | 7.2 | 0.13 |  |
| D | E21-1S | system_prompt | 30/30 | 6 | 0.018 | 6.5 | 5.7 | -0.50 | surface touched by every candidate: no contrast available |
| D | E21-1S | tool_code | 30/30 | 6 | 0.018 | 6.5 | 5.7 | -0.37 | surface touched by every candidate: no contrast available |
| D | E21-ruleP | system_prompt | 10/10 | 4 | 0.076 | 9.9 | 6.2 | 0.56 | surface touched by every candidate: no contrast available |
| D | E21-ruleP | tool_code | 10/10 | 4 | 0.076 | 9.9 | 6.2 | 0.40 | surface touched by every candidate: no contrast available |
| D | E26-NOHIST | system_prompt | 30/30 | 5 | -0.003 | 7.5 | 7.5 | -0.34 | surface touched by every candidate: no contrast available |
| D | E26-NOHIST | tool_code | 30/30 | 5 | -0.003 | 7.5 | 7.5 | -0.35 | surface touched by every candidate: no contrast available |
| E | E30-P | system_prompt | 10/10 | 3 | 0.055 | 3.5 | 2.4 | -0.40 | surface touched by every candidate: no contrast available |
| E | E30-PT | system_prompt | 6/6 | 2 | 0.071 | 2.3 | 1.0 | -0.18 | surface touched by every candidate: no contrast available |
| E | E30-PT | tool_code | 6/6 | 2 | 0.071 | 2.3 | 1.0 | -0.43 | surface touched by every candidate: no contrast available |
| E | E30-T | tool_code | 5/5 | 3 | 0.142 | 3.6 | 1.4 | -0.21 | surface touched by every candidate: no contrast available |
| E | E31-ruleP | system_prompt | 3/3 | 0 | 0.365 | 6.7 | 0.3 | -- | surface touched by every candidate: no contrast available |
| E | E31-ruleP | tool_code | 3/3 | 0 | 0.365 | 6.7 | 0.3 | -- | surface touched by every candidate: no contrast available |

## Shrinkage and cost per point

See shrinkage.csv and cost_per_point.csv (final columns empty until the final evaluation).
