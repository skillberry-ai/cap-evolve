# E22 null pool replay

Pool: 40 evaluations of the unmodified seed (tau2 retail opt-49, target azoai/gpt-4.1-mini, user simulator and judge azoai/gpt-4.1), 1 trial per task per evaluation, 1,960 rollouts, 10 errored rollouts dropped from paired vectors. Seed mean reward per evaluation 0.564, SD 0.065 (binomial expectation 0.071); first half 0.548, second half 0.580.

Method (amendment 7F). A null candidate is another seed evaluation; a screen uses one evaluation per side, a confirmation n_conf further DISTINCT evaluations per side (never reused within a decision). The real `cap_evolve.promotion.screen/decide` code is called (`analysis/scripts/null_pool_replay.py`, committed before the data at 7d5118190). The table below comes from ONE procedure (`analysis/scripts/null_pool_bootstrap.py`, v2): the point estimate is the full pool with 20,000 draws, each of 1,000 bootstrap replicates (evaluations resampled as positions with replacement, decisions draw distinct positions) uses the same estimator and 20,000 draws, so the inner Monte Carlo error is about 0.0012 for a rate near 0.03.

K = 40 evaluations, 49 tasks; point = full pool, 20000 draws; interval = percentile of 1000 bootstrap replicates, each 20000 draws (same estimator). Inner Monte Carlo error of one rate at p = 0.03: 0.0012.

| gate | per candidate (point) | bootstrap 95% over evaluations | per 10 candidates (point; interval) |
|---|---|---|---|
| one-stage / stock-unmasked (screen k_se=1) | 0.1839 | [0.1125, 0.2402] | 0.869; [0.697, 0.936] |
| screen k_se=2 | 0.0524 | [0.0155, 0.0906] | 0.416; [0.144, 0.613] |
| rule P as E10B (k1, n_conf3, z1.282, dmin0) | 0.0258 | [0.0082, 0.0464] | 0.230; [0.079, 0.378] |
| rule P frozen (k1, n_conf3, z2.0, dmin0.02) | 0.0076 | [0.0013, 0.0204] | 0.073; [0.013, 0.186] |
| rule P n_conf10 z1.645 dmin0.02 | 0.0164 | [0.0037, 0.0315] | 0.152; [0.036, 0.274] |

The earlier 20,000-draw replay in this file (one-stage 0.184, screen k 2 0.049, rule P E10B 0.028, frozen 0.008, n_conf 10 0.016) agrees with these points within Monte Carlo error; this table replaces it. "Per 10 candidates" is 1-(1-p)^10 and assumes independent candidates.

Reading. The one-stage screen passes a null candidate about 18% of the time (a one-sided z of 1 would give 16%), about 0.87 per 10 candidates [0.70, 0.94], against the simulated 0.57 per 10-iteration search (analysis/out/sim_promotion.md). Rule P as run in E10B accepts 2.6% of null candidates [0.8%, 4.6%], about 0.23 per 10 candidates [0.08, 0.38], against 0.04 simulated for B (sim_budget_B.md): about 6 times the simulated rate, with a wide interval because 40 evaluations give few distinct fresh-trial draws (earlier split halves of the pool gave 1.2% and 3.5%). The frozen z 2.0 / dmin 0.02 version accepts 0.8% per candidate, 0.07 per 10; the n_conf 10 variant 1.6%, 0.15 per 10.

Not tested: the footprint-masked stock gate (a null edit has an empty footprint), false rejects (need true effects: gate ROC), and search dynamics (an accepted candidate raises the incumbent bar).
