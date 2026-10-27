# GATE2 window (addendum 20; exploratory)

One search per arm; each gate arm differs from K2 search 1 only in the gate rule (naive: accept iff the mean paired delta is >= 0; none: accept every decisive scored candidate). No pipeline-level interval; no claim about the gate in general. Raw p only.

- means: GATE-NAIVE-K2 0.525, GATE-NONE-K2 0.605, GATE-K2-search1 0.655, seed 0.470 (n = 20), seed-check 0.455 (k = 10)
- drift (5I, in-window seed, task-demeaned, hour blocks): 0: -0.000 (SE 0.016, n=400). Range 0.000, SE of difference 0.023, flag (>2 SE): False.

| contrast | delta | 95% CI (artifact, CR1 t19) | raw p | 
|---|---|---|---|
| PRIMARY: GATE-NAIVE-K2 minus GATE-K2-search1 (task-paired) | -0.130 | [-0.266, 0.006] | 0.060 |
| PRIMARY: GATE-NONE-K2 minus GATE-K2-search1 (task-paired) | -0.050 | [-0.106, 0.006] | 0.076 |
| GATE-NAIVE-K2 minus seed | +0.055 | [-0.074, 0.184] | 0.384 |
| GATE-NONE-K2 minus seed | +0.135 | [0.009, 0.261] | 0.037 |
| GATE-NAIVE-K2 minus GATE-NONE-K2 | -0.080 | [-0.186, 0.026] | 0.130 |
| GATE-K2-search1 minus seed (window check; earlier windows +0.145, +0.130, +0.130, +0.113, +0.153) | +0.185 | [0.042, 0.328] | 0.014 |
| seed-check minus seed | -0.015 | [-0.054, 0.024] | 0.428 |

Planning detectability (80% power, within-variance 0.1236, tau 0.15): 0.149 against the seed at n = 20; 0.158 against another single champion. Differences below these are inconclusive.
