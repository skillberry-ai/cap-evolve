# mde_observed: MDE from the observed per-task variance of the unmodified seed artifact

Data: search-split evaluations of the seed artifact only (no final-set data). Each row pools every re-measurement of the same seed artifact on that split. Binary-reward check: `within var` is the mean per-task unbiased trial variance (for 0/1 rewards it equals E[p(1-p)]); `SD p` and `kappa` are the true between-task SD of the pass rate and the matched Beta concentration after removing trial noise (the earlier plan assumed mu=.55, kappa=1.5, trial-pair noise 0.297/n, i.e. within var 0.149).

| split | tasks | trials/task (min, mean, max) | mu | within var/trial | SD of true p | kappa | frac non-binary rewards | SD of paired delta between 2 evals: observed vs sqrt(2*within) | SD of split mean across evals: observed vs sqrt(within/T) (n evals) |
|---|---|---|---|---|---|---|---|---|---|
| A val-40 | 40 | [3, 5.7, 6] | 0.567 | 0.088 | 0.403 | 0.51 | 0.00 | 0.396 vs 0.418 | 0.088 vs 0.047 (6) |
| B opt-49 | 49 | [13, 14.9, 15] | 0.597 | 0.148 | 0.308 | 1.53 | 0.00 | 0.550 vs 0.544 | 0.045 vs 0.055 (9) |
| B sel-25 | 25 | [6, 6.0, 6] | 0.600 | 0.091 | 0.395 | 0.54 | 0.00 | n/a | n/a |
| C opt-20 | 20 | [8, 8.9, 9] | 0.506 | 0.124 | 0.366 | 0.87 | 0.00 | 0.504 vs 0.497 | 0.047 vs 0.079 (9) |

## MDE (absolute reward points), alpha .05 two-sided, power .80, S=3 search seeds

Variance model as in sim_mde.py, but trial noise = 2 x observed within var / n. `tau` is the SD across tasks of the true per-task advantage; tau=0 is the noise-only FLOOR on the MDE (no real effect heterogeneity), 0.10-0.25 are plausible ranges that CANNOT be estimated from baselines alone. tau_int=.10, sigma_s=.03 as before (still placeholders, not identifiable from seed-only data). Suites B and C have no task families: clusters are tasks, DEFF=1, conditional MDE uses t(T-1). Suite A keeps DEFF=1.4 (family size 5, ICC .10; not re-estimated). `Holm m` = number of contrasts in the primary family (A 12, B 8, C 6); the Holm column is the first-step (smallest p) critical level alpha/m.

| suite | final tasks T | trials n | tau | MDE conditional (the 3 champions) | same, Holm first step | MDE pipeline-level t(2) | same, Holm first step |
|---|---|---|---|---|---|---|---|
| A | 60 | 1 | 0.0 | 0.108 | 0.145 | 0.224 | 0.688 |
| A | 60 | 1 | 0.1 | 0.116 | 0.157 | 0.238 | 0.733 |
| A | 60 | 1 | 0.15 | 0.126 | 0.170 | 0.255 | 0.785 |
| A | 60 | 1 | 0.25 | 0.153 | 0.206 | 0.303 | 0.933 |
| A | 70 | 1 | 0.0 | 0.100 | 0.134 | 0.210 | 0.646 |
| A | 70 | 1 | 0.1 | 0.108 | 0.144 | 0.223 | 0.687 |
| A | 70 | 1 | 0.15 | 0.117 | 0.156 | 0.239 | 0.735 |
| A | 70 | 1 | 0.25 | 0.142 | 0.190 | 0.283 | 0.871 |
| A | 80 | 1 | 0.0 | 0.093 | 0.125 | 0.199 | 0.613 |
| A | 80 | 1 | 0.1 | 0.100 | 0.134 | 0.211 | 0.651 |
| A | 80 | 1 | 0.15 | 0.109 | 0.146 | 0.226 | 0.695 |
| A | 80 | 1 | 0.25 | 0.132 | 0.177 | 0.267 | 0.821 |
| B | 40 | 1 | 0.0 | 0.145 | 0.189 | 0.286 | 0.728 |
| B | 40 | 1 | 0.1 | 0.152 | 0.198 | 0.298 | 0.760 |
| B | 40 | 1 | 0.15 | 0.160 | 0.209 | 0.313 | 0.797 |
| B | 40 | 1 | 0.25 | 0.184 | 0.240 | 0.356 | 0.906 |
| B | 40 | 2 | 0.0 | 0.104 | 0.136 | 0.216 | 0.549 |
| B | 40 | 2 | 0.1 | 0.114 | 0.148 | 0.232 | 0.589 |
| B | 40 | 2 | 0.15 | 0.125 | 0.162 | 0.250 | 0.637 |
| B | 40 | 2 | 0.25 | 0.154 | 0.201 | 0.302 | 0.769 |
| B | 40 | 3 | 0.0 | 0.086 | 0.113 | 0.186 | 0.474 |
| B | 40 | 3 | 0.1 | 0.098 | 0.127 | 0.205 | 0.521 |
| B | 40 | 3 | 0.15 | 0.110 | 0.143 | 0.225 | 0.574 |
| B | 40 | 3 | 0.25 | 0.143 | 0.186 | 0.282 | 0.718 |
| C | 20 | 1 | 0.0 | 0.193 | 0.249 | 0.363 | 0.809 |
| C | 20 | 1 | 0.1 | 0.204 | 0.263 | 0.383 | 0.852 |
| C | 20 | 1 | 0.15 | 0.217 | 0.280 | 0.405 | 0.903 |
| C | 20 | 1 | 0.25 | 0.254 | 0.328 | 0.471 | 1.049 |
| C | 20 | 2 | 0.0 | 0.139 | 0.180 | 0.270 | 0.601 |
| C | 20 | 2 | 0.1 | 0.154 | 0.199 | 0.295 | 0.657 |
| C | 20 | 2 | 0.15 | 0.171 | 0.220 | 0.324 | 0.722 |
| C | 20 | 2 | 0.25 | 0.216 | 0.278 | 0.403 | 0.898 |
| C | 20 | 3 | 0.0 | 0.116 | 0.149 | 0.230 | 0.512 |
| C | 20 | 3 | 0.1 | 0.133 | 0.172 | 0.259 | 0.578 |
| C | 20 | 3 | 0.15 | 0.152 | 0.196 | 0.292 | 0.651 |
| C | 20 | 3 | 0.25 | 0.202 | 0.260 | 0.378 | 0.842 |

## Suite A evaluation-batch effect

The six seed-artifact evaluations on Suite A val-40 (3 hill-climb, 3 agent-optimize runs, same artifact) have split means 0.579, 0.590, 0.568, 0.462, 0.447, 0.684: SD 0.088 against a binomial prediction of 0.047. The excess is an evaluation-batch SD of about 0.075 (5 df, very imprecise; likely gateway load / time of day on the single Gemma deployment). Suites B and C show no excess (observed at or below prediction). If arms are scored in different batches, the contrast variance gains sig_b^2 (1 + 1/S); interleaving all arms in randomized order within one window cancels it, so the protocol requires it. MDE at T=70, n=1, S=3 with and without the batch term:

| suite | T | n | tau | flavour | MDE no batch effect | MDE with sig_b=0.075 |
|---|---|---|---|---|---|---|
| A | 70 | 1 | 0.1 | conditional | 0.108 | 0.268 |
| A | 70 | 1 | 0.1 | pipeline | 0.223 | 0.515 |
| A | 70 | 1 | 0.15 | conditional | 0.117 | 0.272 |
| A | 70 | 1 | 0.15 | pipeline | 0.239 | 0.521 |
| A | 70 | 1 | 0.25 | conditional | 0.142 | 0.284 |
| A | 70 | 1 | 0.25 | pipeline | 0.283 | 0.543 |