# E22 null pool replay

Pool: 40 evaluations of the unmodified seed, 49 tasks, 1 trial per task per evaluation. Reps per gate 20000 (draws share a finite pool, so the Wilson CI is optimistic; see split-half).

Seed mean reward per evaluation: mean 0.564, SD 0.065 (binomial expectation about 0.071); first-half mean 0.548, second-half 0.580.

| gate | screen pass | false accept per candidate | Wilson 95% | P(>=1 false accept in 10 candidates) |
|---|---|---|---|---|
| one-stage / stock-unmasked (screen k_se=1) | 0.184 | 0.1844 | [0.1791, 0.1898] | 0.870 |
| screen k_se=2 | 0.048 | 0.0485 | [0.0456, 0.0515] | 0.391 |
| rule P as E10B (k1, n_conf3, z1.282, dmin0) | 0.185 | 0.0279 | [0.0258, 0.0303] | 0.247 |
| rule P frozen (k1, n_conf3, z2.0, dmin0.02) | 0.184 | 0.0077 | [0.0066, 0.0091] | 0.075 |
| rule P n_conf10 z1.645 dmin0.02 | 0.184 | 0.0157 | [0.0141, 0.0175] | 0.146 |

Split-half check, rule P as E10B (8 evaluations per draw): first half: 0.0118; second half: 0.0354.

Compare with analysis/out/sim_promotion.md (simulated: one-stage 0.57 and rule P 0.04 per 10-iteration search).
Scope: unmasked decision rules on null edits only. False reject needs true effects (E26).

## Bootstrap over the 40 evaluations (amendment 7F)

Script analysis/scripts/null_pool_bootstrap.py (B=200 resamples of the evaluations as positions, 2000 draws each, distinct positions within a decision). The point estimates differ slightly from the 20000-draw table above because of the smaller number of draws.

| gate | point (pool) | bootstrap 95% over evaluations | per 10 candidates (point; interval) |
|---|---|---|---|
| one-stage / stock-unmasked | 0.1950 | [0.1130, 0.2480] | 0.886; [0.699, 0.942] |
| screen k_se=2 | 0.0485 | [0.0145, 0.0895] | 0.392; [0.136, 0.608] |
| rule P as E10B (k1,n3,z1.282,dmin0) | 0.0300 | [0.0065, 0.0450] | 0.263; [0.063, 0.369] |
| rule P frozen (z2.0,dmin.02) | 0.0080 | [0.0010, 0.0210] | 0.077; [0.010, 0.191] |

Reading. Seed mean per evaluation 0.564, SD 0.065; 10 of 1960 rollouts errored (dropped from paired vectors, coverage far above 0.95). The one-stage screen passed a null candidate 18 to 19% of the time (one-sided z of 1 would give 16%), i.e. about 0.89 per 10 candidates [0.70, 0.94], against the simulated 0.57 per 10-iteration search (analysis/out/sim_promotion.md). Rule P as run in E10B (k 1, n_conf 3, z 1.282, dmin 0) accepted 3.0% of null candidates [0.7%, 4.5%], about 0.26 per 10 candidates [0.06, 0.37], against 0.04 simulated for B (sim_budget_B.md): about 6x the simulated rate, with a wide interval because 40 evaluations give few distinct fresh-trial draws (split halves 0.012 and 0.035). The frozen z 2.0 / dmin 0.02 version: 0.8% per candidate, 0.08 per 10. Not tested: the footprint-masked stock gate (a null edit has an empty footprint), false rejects (need true effects: E26 gate ROC), search dynamics (accepted candidates raise the incumbent bar).
