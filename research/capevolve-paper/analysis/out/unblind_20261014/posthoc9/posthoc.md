# POST HOC re-analysis (addendum 21 part 0; no new data; methods chosen after the registered results were seen)

## (A) tau2: CapEvolve (3 searches) minus each of nine comparators, task-paired

| comparator | delta [95% CI, CR1 t19] | raw p | Holm p, m = 9 | sign-flip maxT adjusted p (POST HOC) |
|---|---|---|---|---|
| Meta-Harness | +0.103 [0.038, 0.169] | 0.004 | 0.034 | 0.011 |
| GEPA | +0.088 [0.026, 0.150] | 0.008 | 0.060 | 0.023 |
| MIPROv2 | +0.127 [0.038, 0.216] | 0.008 | 0.060 | 0.024 |
| WikiSkill | +0.113 [0.028, 0.199] | 0.012 | 0.071 | 0.038 |
| ACE | +0.095 [0.008, 0.182] | 0.035 | 0.174 | 0.110 |
| GEPA (full) | +0.077 [0.006, 0.148] | 0.035 | 0.174 | 0.113 |
| EvoSkill | +0.077 [0.003, 0.150] | 0.042 | 0.174 | 0.137 |
| SkillOpt | +0.062 [-0.001, 0.124] | 0.053 | 0.174 | 0.177 |
| Trace2Skill | +0.080 [-0.004, 0.164] | 0.061 | 0.174 | 0.194 |

Comparisons with adjusted p < 0.05: Holm 1 of 9; sign-flip maxT 4 of 9 (exact enumeration of 1,048,576 sign vectors; studentised statistic).

## (B) tau2 pooled: CapEvolve minus the equal-weight mean of the comparators (POST HOC)

| comparator set | delta [95% CI, CR1 t19] | raw p |
|---|---|---|
| nine non-inert comparators (primary of this part) | +0.091 [0.025, 0.158] | 0.010 |
| eight published optimizers without ACE (sensitivity) | +0.091 [0.026, 0.155] | 0.008 |

## (C) AppWorld one session (test_normal, 5 trials, 168 tasks): Holm over CapEvolve's nine comparisons (POST HOC; from PUBLISHED raw p to four decimals)

| comparator | published (other minus CapEvolve) TGC [CI] | raw p | Holm p, m = 9 | published Holm over 78 pairs |
|---|---|---|---|---|
| metaharness | -14.9 [-21.2, -8.6] | 0.0000 | <0.001 | yes |
| miprov2 | -9.8 [-16.1, -3.8] | 0.0014 | 0.011 | no |
| wikiskill | -8.8 [-14.9, -2.5] | 0.0066 | 0.046 | no |
| evoskill | -6.7 [-11.9, -1.7] | 0.0108 | 0.065 | no |
| gepa | -5.1 [-10.1, -0.4] | 0.0380 | 0.190 | no |
| skillopt | -4.0 [-9.3, 0.8] | 0.1098 | 0.439 | no |
| ace | -4.0 [-9.9, 1.3] | 0.1440 | 0.439 | no |
| gepa_full | -2.1 [-7.3, 2.9] | 0.4018 | 0.804 | no |
| trace2skill | 0.7 [-4.8, 6.2] | 0.8106 | 0.811 | no |

AppWorld comparisons with Holm (m = 10) < 0.05: 2 computed from nonzero published p plus 1 with published p 0.0000. A published p is a bootstrap value to four decimals; a Holm p near 0.05 is sensitive to that rounding.

The AppWorld pooled test and an AppWorld permutation test need the per-task data and are not computed here.
