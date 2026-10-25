# TRAINRS1: transfer ratio from one fresh train-30 session (addendum 18; descriptive; FIT-SET search scores)

Held-out gains are from MERGED (already scored; same for all arms); search gains are new, each arm against the TRAINRS1 seed. Train ids were every arm's search data: in-sample, a train-to-test gap, not generalisation. Fresh trials remove noise-selection, not task-selection. CapEvolve: three searches, one seed each; s2 excluded by name.

- TRAINRS1 train-30 seed mean 0.533 (k = 10); seed-check 0.567 (k = 5); difference +0.033

| arm | held-out gain (MERGED) | search gain (TRAINRS1) | gamma |
|---|---|---|---|
| gepafull | +0.057 | +0.193 | 0.29 |
| gepa | +0.045 | +0.156 | 0.29 |
| skillopt | +0.072 | +0.182 | 0.39 |
| wikiskill | +0.020 | +0.138 | 0.15 |
| metaharness | +0.030 | +0.153 | 0.20 |
| evoskill | +0.057 | +0.178 | 0.32 |
| mipro | +0.007 | +0.082 | 0.08 |
| trace2skill | +0.053 | +0.151 | 0.35 |
| GATE-K2-search1 | +0.130 | +0.347 | 0.38 |
| GATE-K2-search2 | +0.145 | +0.367 | 0.40 |
| GATE-K2-search3 | +0.125 | +0.273 | 0.46 |

- POOLED PUBLISHED gamma (8 arms): 0.28; arm bootstrap (10,000, seed 0) [0.21, 0.33]; per arm 0.08 to 0.39
- CAPEVOLVE gamma (ratio of means over searches 1, 2, 3): 0.41; per search 0.38, 0.40, 0.46
- CapEvolve minus pooled published gamma: +0.13 (descriptive)
- supplementary task bootstrap (test and train tasks resampled; 4000 of 4000 replicates kept): pooled published [-0.086, 0.806]; CapEvolve [0.153, 0.773]; difference [-0.203, 0.428]
- The earlier 0.28 (several sessions) and 0.41 (in-sample acceptance score) are not part of this table.
