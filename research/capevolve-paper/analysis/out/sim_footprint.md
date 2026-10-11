# sim_footprint results

reps/row ~5600, T=40, n_trials=5, base mu=0.55 kappa=1.5.

## (c) Footprint masking (accept rates; `full` = no footprint, `masked_floor` = what the harness does)

### k_se = 0.2

| scenario | true net delta | mean obs delta (full) | mean obs delta (masked) | accept full | accept masked, no floor | accept masked + floor (harness) |
|---|---|---|---|---|---|---|
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.0 | +0.047 | +0.047 | +0.047 | 0.842 | 0.937 | 0.933 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.5 | +0.047 | +0.047 | +0.047 | 0.844 | 0.951 | 0.947 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=1.0 | +0.047 | +0.046 | +0.047 | 0.849 | 0.973 | 0.972 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.0 | -0.013 | -0.012 | -0.013 | 0.293 | 0.233 | 0.232 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.5 | -0.013 | -0.013 | +0.017 | 0.289 | 0.650 | 0.648 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=1.0 | -0.013 | -0.013 | +0.047 | 0.287 | 0.973 | 0.972 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.0 | -0.043 | -0.044 | -0.043 | 0.085 | 0.040 | 0.040 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.5 | -0.043 | -0.043 | +0.002 | 0.088 | 0.427 | 0.426 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=1.0 | -0.043 | -0.042 | +0.047 | 0.092 | 0.973 | 0.972 |
| NULL edit, footprint=12 tasks (independent of outcomes) | +0.000 | +0.001 | -0.000 | 0.426 | 0.430 | 0.422 |
| NULL edit, OUTCOME-DEPENDENT footprint (selected on observed delta sign) | +0.000 | +0.001 | +0.055 | 0.423 | 0.982 | 0.981 |

### k_se = 0.3

| scenario | true net delta | mean obs delta (full) | mean obs delta (masked) | accept full | accept masked, no floor | accept masked + floor (harness) |
|---|---|---|---|---|---|---|
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.0 | +0.047 | +0.047 | +0.047 | 0.814 | 0.927 | 0.927 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.5 | +0.047 | +0.047 | +0.047 | 0.812 | 0.939 | 0.939 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=1.0 | +0.047 | +0.046 | +0.047 | 0.817 | 0.965 | 0.964 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.0 | -0.013 | -0.012 | -0.013 | 0.254 | 0.190 | 0.190 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.5 | -0.013 | -0.013 | +0.017 | 0.245 | 0.611 | 0.611 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=1.0 | -0.013 | -0.013 | +0.047 | 0.246 | 0.966 | 0.963 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.0 | -0.043 | -0.044 | -0.043 | 0.066 | 0.027 | 0.027 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.5 | -0.043 | -0.043 | +0.002 | 0.072 | 0.380 | 0.380 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=1.0 | -0.043 | -0.042 | +0.047 | 0.074 | 0.965 | 0.964 |
| NULL edit, footprint=12 tasks (independent of outcomes) | +0.000 | +0.001 | -0.000 | 0.383 | 0.380 | 0.369 |
| NULL edit, OUTCOME-DEPENDENT footprint (selected on observed delta sign) | +0.000 | +0.001 | +0.055 | 0.386 | 0.976 | 0.976 |

### k_se = 1.0

| scenario | true net delta | mean obs delta (full) | mean obs delta (masked) | accept full | accept masked, no floor | accept masked + floor (harness) |
|---|---|---|---|---|---|---|
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.0 | +0.047 | +0.047 | +0.047 | 0.570 | 0.751 | 0.737 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.5 | +0.047 | +0.047 | +0.047 | 0.564 | 0.793 | 0.780 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=1.0 | +0.047 | +0.046 | +0.047 | 0.553 | 0.853 | 0.840 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.0 | -0.013 | -0.012 | -0.013 | 0.069 | 0.039 | 0.038 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.5 | -0.013 | -0.013 | +0.017 | 0.061 | 0.290 | 0.286 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=1.0 | -0.013 | -0.013 | +0.047 | 0.066 | 0.849 | 0.837 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.0 | -0.043 | -0.044 | -0.043 | 0.008 | 0.001 | 0.001 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.5 | -0.043 | -0.043 | +0.002 | 0.008 | 0.127 | 0.126 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=1.0 | -0.043 | -0.042 | +0.047 | 0.010 | 0.851 | 0.839 |
| NULL edit, footprint=12 tasks (independent of outcomes) | +0.000 | +0.001 | -0.000 | 0.156 | 0.167 | 0.137 |
| NULL edit, OUTCOME-DEPENDENT footprint (selected on observed delta sign) | +0.000 | +0.001 | +0.055 | 0.168 | 0.904 | 0.892 |

### k_se = 2.0

| scenario | true net delta | mean obs delta (full) | mean obs delta (masked) | accept full | accept masked, no floor | accept masked + floor (harness) |
|---|---|---|---|---|---|---|
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.0 | +0.047 | +0.047 | +0.047 | 0.190 | 0.314 | 0.291 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=0.5 | +0.047 | +0.047 | +0.047 | 0.193 | 0.352 | 0.328 |
| gain+0.25 on 8 / loss-0.00 on 8, P(miss R)=1.0 | +0.047 | +0.046 | +0.047 | 0.187 | 0.430 | 0.400 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.0 | -0.013 | -0.012 | -0.013 | 0.003 | 0.001 | 0.001 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=0.5 | -0.013 | -0.013 | +0.017 | 0.004 | 0.037 | 0.035 |
| gain+0.25 on 8 / loss-0.30 on 8, P(miss R)=1.0 | -0.013 | -0.013 | +0.047 | 0.005 | 0.418 | 0.388 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.0 | -0.043 | -0.044 | -0.043 | 0.000 | 0.000 | 0.000 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=0.5 | -0.043 | -0.043 | +0.002 | 0.000 | 0.012 | 0.012 |
| gain+0.25 on 8 / loss-0.45 on 8, P(miss R)=1.0 | -0.043 | -0.042 | +0.047 | 0.000 | 0.435 | 0.404 |
| NULL edit, footprint=12 tasks (independent of outcomes) | +0.000 | +0.001 | -0.000 | 0.027 | 0.021 | 0.012 |
| NULL edit, OUTCOME-DEPENDENT footprint (selected on observed delta sign) | +0.000 | +0.001 | +0.055 | 0.030 | 0.613 | 0.552 |

## (d) Missingness and min_coverage=0.6 (k_se=1 for the indecisive column)

### accept rate at k_se = 0.2

| scenario | mean coverage (cand) | P(indecisive) | bias of observed delta (current policy) | accept: drop errors (current) | accept: errors=failure |
|---|---|---|---|---|---|
| trial_fail_triggered gamma=0.0, edit true -0.03 | 1.00 | 0.000 | -0.002 | 0.162 | 0.162 |
| trial_fail_triggered gamma=0.0, NULL edit | 1.00 | 0.000 | +0.000 | 0.426 | 0.426 |
| trial_fail_triggered gamma=0.25, edit true -0.03 | 1.00 | 0.000 | +0.045 | 0.561 | 0.160 |
| trial_fail_triggered gamma=0.25, NULL edit | 1.00 | 0.000 | +0.042 | 0.801 | 0.418 |
| trial_fail_triggered gamma=0.5, edit true -0.03 | 0.99 | 0.000 | +0.109 | 0.950 | 0.168 |
| trial_fail_triggered gamma=0.5, NULL edit | 0.99 | 0.000 | +0.098 | 0.978 | 0.408 |
| trial_fail_triggered gamma=0.75, edit true -0.03 | 0.96 | 0.000 | +0.204 | 0.999 | 0.163 |
| trial_fail_triggered gamma=0.75, NULL edit | 0.96 | 0.000 | +0.190 | 1.000 | 0.421 |
| trial_mcar gamma=0.2, NULL edit | 1.00 | 0.000 | +0.000 | 0.426 | 0.003 |
| task_hard gamma=0.2, edit true -0.03 | 0.94 | 0.000 | -0.001 | 0.168 | 0.121 |
| trial_mcar gamma=0.5, NULL edit | 0.97 | 0.000 | -0.000 | 0.417 | 0.000 |
| task_hard gamma=0.5, edit true -0.03 | 0.86 | 0.000 | -0.004 | 0.164 | 0.069 |
| trial_mcar gamma=0.8, NULL edit | 0.67 | 0.125 | -0.002 | 0.365 | 0.000 |
| task_hard gamma=0.8, edit true -0.03 | 0.77 | 0.004 | -0.007 | 0.154 | 0.034 |

### accept rate at k_se = 0.3

| scenario | mean coverage (cand) | P(indecisive) | bias of observed delta (current policy) | accept: drop errors (current) | accept: errors=failure |
|---|---|---|---|---|---|
| trial_fail_triggered gamma=0.0, edit true -0.03 | 1.00 | 0.000 | -0.002 | 0.132 | 0.132 |
| trial_fail_triggered gamma=0.0, NULL edit | 1.00 | 0.000 | +0.000 | 0.382 | 0.382 |
| trial_fail_triggered gamma=0.25, edit true -0.03 | 1.00 | 0.000 | +0.045 | 0.525 | 0.134 |
| trial_fail_triggered gamma=0.25, NULL edit | 1.00 | 0.000 | +0.042 | 0.773 | 0.377 |
| trial_fail_triggered gamma=0.5, edit true -0.03 | 0.99 | 0.000 | +0.109 | 0.938 | 0.141 |
| trial_fail_triggered gamma=0.5, NULL edit | 0.99 | 0.000 | +0.098 | 0.973 | 0.364 |
| trial_fail_triggered gamma=0.75, edit true -0.03 | 0.96 | 0.000 | +0.204 | 0.999 | 0.140 |
| trial_fail_triggered gamma=0.75, NULL edit | 0.96 | 0.000 | +0.190 | 1.000 | 0.378 |
| trial_mcar gamma=0.2, NULL edit | 1.00 | 0.000 | +0.000 | 0.391 | 0.001 |
| task_hard gamma=0.2, edit true -0.03 | 0.94 | 0.000 | -0.001 | 0.141 | 0.100 |
| trial_mcar gamma=0.5, NULL edit | 0.97 | 0.000 | -0.000 | 0.378 | 0.000 |
| task_hard gamma=0.5, edit true -0.03 | 0.86 | 0.000 | -0.004 | 0.138 | 0.054 |
| trial_mcar gamma=0.8, NULL edit | 0.67 | 0.125 | -0.002 | 0.330 | 0.000 |
| task_hard gamma=0.8, edit true -0.03 | 0.77 | 0.004 | -0.007 | 0.133 | 0.028 |

### accept rate at k_se = 1.0

| scenario | mean coverage (cand) | P(indecisive) | bias of observed delta (current policy) | accept: drop errors (current) | accept: errors=failure |
|---|---|---|---|---|---|
| trial_fail_triggered gamma=0.0, edit true -0.03 | 1.00 | 0.000 | -0.002 | 0.039 | 0.039 |
| trial_fail_triggered gamma=0.0, NULL edit | 1.00 | 0.000 | +0.000 | 0.161 | 0.161 |
| trial_fail_triggered gamma=0.25, edit true -0.03 | 1.00 | 0.000 | +0.045 | 0.256 | 0.039 |
| trial_fail_triggered gamma=0.25, NULL edit | 1.00 | 0.000 | +0.042 | 0.518 | 0.159 |
| trial_fail_triggered gamma=0.5, edit true -0.03 | 0.99 | 0.000 | +0.109 | 0.783 | 0.038 |
| trial_fail_triggered gamma=0.5, NULL edit | 0.99 | 0.000 | +0.098 | 0.893 | 0.154 |
| trial_fail_triggered gamma=0.75, edit true -0.03 | 0.96 | 0.000 | +0.204 | 0.994 | 0.037 |
| trial_fail_triggered gamma=0.75, NULL edit | 0.96 | 0.000 | +0.190 | 0.999 | 0.160 |
| trial_mcar gamma=0.2, NULL edit | 1.00 | 0.000 | +0.000 | 0.164 | 0.000 |
| task_hard gamma=0.2, edit true -0.03 | 0.94 | 0.000 | -0.001 | 0.037 | 0.021 |
| trial_mcar gamma=0.5, NULL edit | 0.97 | 0.000 | -0.000 | 0.169 | 0.000 |
| task_hard gamma=0.5, edit true -0.03 | 0.86 | 0.000 | -0.004 | 0.035 | 0.009 |
| trial_mcar gamma=0.8, NULL edit | 0.67 | 0.125 | -0.002 | 0.140 | 0.000 |
| task_hard gamma=0.8, edit true -0.03 | 0.77 | 0.004 | -0.007 | 0.035 | 0.006 |

### accept rate at k_se = 2.0

| scenario | mean coverage (cand) | P(indecisive) | bias of observed delta (current policy) | accept: drop errors (current) | accept: errors=failure |
|---|---|---|---|---|---|
| trial_fail_triggered gamma=0.0, edit true -0.03 | 1.00 | 0.000 | -0.002 | 0.004 | 0.004 |
| trial_fail_triggered gamma=0.0, NULL edit | 1.00 | 0.000 | +0.000 | 0.023 | 0.023 |
| trial_fail_triggered gamma=0.25, edit true -0.03 | 1.00 | 0.000 | +0.045 | 0.056 | 0.003 |
| trial_fail_triggered gamma=0.25, NULL edit | 1.00 | 0.000 | +0.042 | 0.173 | 0.025 |
| trial_fail_triggered gamma=0.5, edit true -0.03 | 0.99 | 0.000 | +0.109 | 0.404 | 0.003 |
| trial_fail_triggered gamma=0.5, NULL edit | 0.99 | 0.000 | +0.098 | 0.603 | 0.026 |
| trial_fail_triggered gamma=0.75, edit true -0.03 | 0.96 | 0.000 | +0.204 | 0.933 | 0.002 |
| trial_fail_triggered gamma=0.75, NULL edit | 0.96 | 0.000 | +0.190 | 0.972 | 0.025 |
| trial_mcar gamma=0.2, NULL edit | 1.00 | 0.000 | +0.000 | 0.028 | 0.000 |
| task_hard gamma=0.2, edit true -0.03 | 0.94 | 0.000 | -0.001 | 0.004 | 0.002 |
| trial_mcar gamma=0.5, NULL edit | 0.97 | 0.000 | -0.000 | 0.026 | 0.000 |
| task_hard gamma=0.5, edit true -0.03 | 0.86 | 0.000 | -0.004 | 0.002 | 0.000 |
| trial_mcar gamma=0.8, NULL edit | 0.67 | 0.125 | -0.002 | 0.025 | 0.000 |
| task_hard gamma=0.8, edit true -0.03 | 0.77 | 0.004 | -0.007 | 0.002 | 0.000 |
