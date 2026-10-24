# BRIDGE1 window (addendum 17; exploratory). First arm: NC-1SHOT; reference: GATE-K2-s0

One champion per arm; no pipeline-level interval; no claim about Claude Code or CapEvolve in general. NC-1SHOT never ran its own edit, exposes 19 tools against 14, and is a single Claude Code session; K2 search 1 is a single CapEvolve search. Earlier score of NC-1SHOT (ABL-W2): +0.040 over its seed. Raw p only.

- means: NC-1SHOT 0.610, GATE-K2-s0 0.585, seed 0.472 (n = 20), seed-check 0.450 (k = 10)
- drift (5I, in-window seed, task-demeaned, hour blocks): 0: -0.008 (SE 0.019, n=319); 1: +0.031 (SE 0.039, n=81). Range 0.039, SE of difference 0.043, flag (>2 SE): False.

| contrast | delta | 95% CI (artifact, CR1 t19) | raw p | 
|---|---|---|---|
| NC-1SHOT minus seed | +0.138 | [0.015, 0.260] | 0.030 |
| NC-1SHOT minus GATE-K2-s0 (same window, task-paired) | +0.025 | [-0.099, 0.149] | 0.678 |
| GATE-K2-s0 minus seed (window check; earlier windows +0.145, +0.130, +0.130) | +0.113 | [-0.006, 0.231] | 0.062 |
| seed-check minus seed | -0.022 | [-0.064, 0.019] | 0.267 |

Planning detectability (80% power, within-variance 0.1236, tau 0.15): 0.149 against the seed at n = 20; 0.158 against another single champion. Differences below these are inconclusive.
