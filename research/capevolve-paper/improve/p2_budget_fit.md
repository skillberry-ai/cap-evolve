# P2 budget-fit rule (A 600, D 550, E 300)

Sim: `p2_budget_sim.py` (grid, calibration), `p2_verify.py` (final check of the registered rule); raw `p2_grid.json`, `p2_final2.json`, `p2_verify.json`. Null pool calibration as in `gate_budget_design.md`; pool sizes and budgets as given by the lead. Not code, not committed.

## Headline (read before registering)

The main defaults cannot run at these budgets: the A baseline alone is 248 of 600, a worst-case round is 523, so zero rounds are funded. A rule that funds 2 full rounds necessarily has low per-round power: **about 0.20–0.29 per round (A), 0.21–0.32 (D), 0.13–0.21 (E) for a true +0.10 edit**, 0.36–0.50, 0.38–0.53 and 0.25–0.38 over two rounds if each round contains one such edit. A negative result at these budgets is uninformative and must be labelled so. The only ways to more power are fewer candidates per search, a larger budget, or a looser FWER.

## Rule (function of B, |F|, |C|)

1. K = 4 candidates per round, survivors S = 1 (K = 6 and 8 and S = 2 were in the grid and lost once 2 rounds were required).
2. Rungs cumulative [8, 24] per candidate (rung 2 adds 16; keep top K/2 = 2 with mean > 0). If |F| < 24 use [8, 16]. Kill-only.
3. Baseline: incumbent_trials = 2 (ranking only, on F); use 3 when it still leaves 2 worst-case rounds (D).
4. Worst-case round cost W = K*r1 + (K/2)*(r2-r1) + (mc + tc)*|C|. Fix the number of C-trials per task n = floor( ((B - minc*|F|)/2 - 64 or 48) / |C| ), where 64 = 4*8 + 2*16 (rungs [8,24]) and 48 = 4*8 + 2*8 (rungs [8,16]). Split n as tc = ceil(n/2) confirmation trials per task for the single survivor, mc = floor(n/2) control trials per task.
5. Confirmation statistic: cluster-robust paired t over the |C| confirm tasks: d_t = mean confirm reward on task t minus mean control reward on task t; t = mean(d) / (sd(d)/sqrt|C|), df = |C| - 1. This uses the observed between-task spread, so it stays valid when a null edit helps some tasks and hurts others (the model-based SE of the design doc does not).
6. Accept iff t >= t_crit(one-sided alpha = 0.12, df = |C| - 1) AND mean(d) >= 0.02. t_crit: A (df 57) 1.187, D (df 35) 1.195, E (df 13) 1.231. The low critical value is deliberate: the rungs (top-half, mean > 0) and the single survivor already do most of the filtering. Do NOT use alpha = 0.05 (t about 1.7): it gives FWER 0.02–0.04 and about half the power.
7. Drop the in-search final-estimate reserve (2*4*|C|, 464 on A). With it zero rounds fit. The unbiased final estimate comes from the v2 held-out scoring. Keep a C-side leak diagnostic from the confirmation data you already collect.
8. Stop rule: a round needs its worst case W to fit in what remains; if not, shrink K by 1 down to 2, else stop.

## Resulting parameters, FWER, power, cost (24,000 sim rounds per cell, alpha 0.12)

| suite | B | F / C | incumbent trials | K | rungs | S | tc / mc | worst W | baseline | 2 x W + baseline |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 600 | 62 / 58 | 2 (124) | 4 | [8,24] | 1 | 2 / 1 | 238 | 124 | 600 |
| D | 550 | 38 / 36 | 3 (114) | 4 | [8,24] | 1 | 2 / 2 | 208 | 114 | 530 |
| E | 300 | 16 / 14 | 2 (32) | 4 | [8,16] | 1 | 3 / 3 | 132 | 32 | 296 |

| suite | round FWER, null het SD 0 / 0.1 / 0.2 | power for +0.10 (one +0.10 candidate among 3 nulls), SD 0 / 0.1 / 0.2 | expected rollouts per round | two-round FWER (<=) | power over two rounds, SD 0 / 0.1 / 0.2 |
|---|---|---|---|---|---|
| A | 0.086 / 0.073 / 0.064 | 0.29 / 0.26 / 0.20 | 198 | 0.17 | 0.50 / 0.45 / 0.36 |
| D | 0.096 / 0.089 / 0.072 | 0.32 / 0.28 / 0.21 | 188 | 0.18 | 0.54 / 0.48 / 0.38 |
| E | 0.083 / 0.077 / 0.067 | 0.21 / 0.18 / 0.13 | 110 | 0.16 | 0.38 / 0.33 / 0.25 |

Total expected rollouts for 2 rounds plus baseline: A 520, D 489, E 252 (worst case equals the budget, so a 3rd round is unaffordable in the worst case; at expected cost A has about 80 spare, not enough for a round).
Per-round FWER is at most 0.10 under all three heterogeneity levels; it is highest at SD 0 (discrete rewards) and falls with heterogeneity because the robust t-test then uses a larger observed SD. Calibrating at SD 0.2 alone, as I first did, gave 0.11–0.14 at SD 0; the table is from the corrected check (max over SD 0 and 0.2 during calibration, then verified at all three).

## Comparisons

| design (suite A) | worst round | FWER (SD 0 / 0.1 / 0.2) | power +0.10 (SD 0 / 0.1 / 0.2) | rounds funded |
|---|---|---|---|---|
| registered rule | 238 | 0.086 / 0.073 / 0.064 | 0.29 / 0.26 / 0.20 | 2 |
| runner alternative (inc 1, K 6, rungs [8,24], ctrl m 1, conf 1 per task, 214/round) | 212 | 0.092 / 0.081 / 0.070 | 0.20 / 0.17 / 0.14 | 2 |
| main defaults shape (inc 4, K 6, [12,36], tc 3, mc 4) | 550 | 0.104 / 0.091 / 0.073 | 0.47 / 0.42 / 0.32 | 0 after a 248 baseline (1 if baseline cut to 50) |

The runner's rough alternative is valid (FWER fine under the robust t) but has about 30% lower power than the registered rule for the same rollouts: its 58-task confirmation uses 1 trial per task on each side, the registered rule moves rollouts from K (6 to 4) and baseline (4 to 2 trials) into confirmation. The main-defaults shape has the best per-round power (0.47) but does not fit.

## Search notes and what is unverified

- Grid: incumbent trials 1–4, K 4/6/8, rungs [8,16]/[8,24]/[12,36], S 1/2, tc 1–6, mc 1–4, restricted to configs with at least 2 worst-case rounds (A 33, D 178, E 154 feasible); D and E were subsampled to about 250 configs, A fully enumerated. Top 4 per suite were calibrated; the three above were then re-verified at the single registered alpha = 0.12. Differences among the top 4 are within about 0.02 power (Monte Carlo SE about 0.004 at 24,000 rounds, but config selection from a grid adds optimism of about 0.01–0.02).
- Power is defined as P(crown that +0.10 candidate) in a round with 3 nulls; edits are diffuse. Sparse edits lose more power through the 8-rollout rung 1 (it can miss all affected tasks). Not simulated.
- The heterogeneity is a per-task random effect N(0, SD) on the candidate's task success rate; the pool-derived task base rates are bootstrap-resampled into F and C sizes (so tasks repeat when |F| or |C| > 49). Real pools for A, D, E have different difficulty mixes.
- The control is assumed concurrent, so time drift cancels; the F baseline (2–3 trials) is for ranking only and its staleness cannot create a false accept.
- No second look in the same round and no re-use of rung rollouts in the confirmation (fresh seeds required, as before).
- The mean >= 0.02 requirement is part of the registered rule and was in all simulations.
- Suite E (|C| = 14, df 13) is the least reliable: the robust t with 14 tasks and discrete data is approximate; the FWER check passed (0.067–0.083) but power is 0.13–0.21 per round. The registered k_small 4, rungs [8,24], confirm 4 x |C| per side fallback was not simulated; its rung 2 (24 > |F| = 16) repeats tasks.

## Addendum: larger effects, and a 2x budget arm (non-matched)

Source: `p2_verify2.py`, `p2_verify2.json`. Same sim and same alpha 0.12 as above; 12,000 rounds per cell (SD about 0.004). Heterogeneity SD 0 / 0.1 / 0.2 in every cell. "Per search" = 1 - (1 - p)^R, which assumes every round contains one candidate of that true effect and rounds are independent. That is the optimistic reading; if the good edit appears in only one round, per-search power equals the per-round figure for that round.

### 1. Matched-budget rule at larger true effects (the primary rule, unchanged)

Power per round (K=4, one true-effect candidate among 3 nulls) and over the 2 rounds. Numbers are SD 0 / 0.1 / 0.2.

| suite | +0.10 round / search | +0.15 round / search | +0.20 round / search | +0.25 round / search |
|---|---|---|---|---|
| A (600) | 0.30 / 0.26 / 0.21 ; 0.51 / 0.45 / 0.37 | 0.53 / 0.49 / 0.41 ; 0.78 / 0.74 / 0.65 | 0.72 / 0.68 / 0.60 ; 0.92 / 0.90 / 0.84 | 0.83 / 0.80 / 0.75 ; 0.97 / 0.96 / 0.94 |
| D (550) | 0.31 / 0.27 / 0.21 ; 0.52 / 0.47 / 0.38 | 0.56 / 0.50 / 0.42 ; 0.81 / 0.75 / 0.66 | 0.75 / 0.72 / 0.63 ; 0.94 / 0.92 / 0.86 | 0.87 / 0.85 / 0.78 ; 0.98 / 0.98 / 0.95 |
| E (300) | 0.21 / 0.18 / 0.13 ; 0.37 / 0.33 / 0.25 | 0.41 / 0.35 / 0.26 ; 0.65 / 0.57 / 0.46 | 0.62 / 0.55 / 0.45 ; 0.86 / 0.80 / 0.69 | 0.79 / 0.73 / 0.61 ; 0.95 / 0.93 / 0.85 |

Round FWER on these runs: A 0.082 / 0.076 / 0.064, D 0.093 / 0.087 / 0.071, E 0.084 / 0.079 / 0.070 (all at most 0.10).
Reading: for the Suite A format-fix scale (+0.20 to +0.25) the matched rule finds the edit within the search with 0.84 to 0.97 on A and D, and 0.69 to 0.95 on E (the heterogeneity-SD-0.2 column is the pessimistic end). Whether a +0.15 or smaller edit is found is close to a coin flip on E and 0.65 to 0.81 on A and D. These are still "if present" probabilities, not guarantees: a round with no such edit crowns a null with probability up to 0.10.

### 2. Same rule at 2x budget (A 1200, D 1100, E 600), labelled non-matched

Baseline unchanged (A 124, D 114, E 32). The rule's n formula is re-solved for the number of rounds R; K is held at 4 except one K=8 variant. Worst-case cost W per round and rounds that fit:

| suite | variant | tc / mc | K | W | rounds fit | FWER (SD 0 / 0.1 / 0.2) |
|---|---|---|---|---|---|---|
| A | same shape as matched | 2 / 1 | 4 | 238 | 4 | 0.082 / 0.076 / 0.064 |
| A | rule n, R = 3 | 3 / 2 | 4 | 354 | 3 | 0.085 / 0.068 / 0.058 |
| A | rule n, R = 2 | 4 / 4 | 4 | 528 | 2 | 0.088 / 0.067 / 0.055 |
| A | rule n, R = 2, K = 8 | 4 / 3 | 8 | 534 | 2 | 0.107 / 0.086 / 0.074 |
| D | same shape | 2 / 2 | 4 | 208 | 4 | 0.093 / 0.087 / 0.071 |
| D | rule n, R = 3 | 4 / 3 | 4 | 316 | 3 | 0.100 / 0.079 / 0.068 |
| D | rule n, R = 2 | 6 / 5 | 4 | 460 | 2 | 0.098 / 0.082 / 0.066 |
| D | rule n, R = 2, K = 8 | 5 / 5 | 8 | 488 | 2 | 0.112 / 0.099 / 0.081 |
| E | same shape | 3 / 3 | 4 | 132 | 4 | 0.084 / 0.079 / 0.070 |
| E | rule n, R = 3 | 5 / 5 | 4 | 188 | 3 | 0.086 / 0.078 / 0.064 |
| E | rule n, R = 2 | 8 / 8 | 4 | 272 | 2 | 0.086 / 0.073 / 0.066 |
| E | rule n, R = 2, K = 8 | 7 / 6 | 8 | 278 | 2 | 0.107 / 0.087 / 0.076 |

The K=8 variants exceed 0.10 at alpha 0.12 (0.107 to 0.112 at SD 0); they would need alpha about 0.10 and are not recommended.

Power per round / per search (R rounds as listed; SD 0 / 0.1 / 0.2):

| suite, variant | +0.10 round ; search | +0.15 round ; search | +0.20 round ; search | +0.25 round ; search |
|---|---|---|---|---|
| A same shape x4 | 0.30 / 0.26 / 0.21 ; 0.76 / 0.70 / 0.60 | 0.53 / 0.49 / 0.41 ; 0.95 / 0.93 / 0.88 | 0.72 / 0.68 / 0.60 ; 0.99 / 0.99 / 0.98 | 0.83 / 0.80 / 0.75 ; 1.00 |
| A rule n, R=3 | 0.38 / 0.33 / 0.25 ; 0.76 / 0.69 / 0.57 | 0.59 / 0.55 / 0.47 ; 0.93 / 0.91 / 0.85 | 0.73 / 0.71 / 0.65 ; 0.98 / 0.97 / 0.96 | 0.83 / 0.81 / 0.75 ; 0.99 / 0.99 / 0.98 |
| A rule n, R=2 | 0.42 / 0.37 / 0.30 ; 0.67 / 0.61 / 0.50 | 0.60 / 0.57 / 0.51 ; 0.84 / 0.82 / 0.76 | 0.73 / 0.71 / 0.65 ; 0.93 / 0.92 / 0.88 | 0.83 / 0.80 / 0.75 ; 0.97 / 0.96 / 0.94 |
| D same shape x4 | 0.31 / 0.27 / 0.21 ; 0.77 / 0.72 / 0.61 | 0.56 / 0.50 / 0.42 ; 0.96 / 0.94 / 0.89 | 0.75 / 0.72 / 0.63 ; 1.00 / 0.99 / 0.98 | 0.87 / 0.85 / 0.78 ; 1.00 |
| D rule n, R=3 | 0.40 / 0.35 / 0.25 ; 0.79 / 0.73 / 0.58 | 0.63 / 0.59 / 0.48 ; 0.95 / 0.93 / 0.86 | 0.78 / 0.75 / 0.68 ; 0.99 / 0.98 / 0.97 | 0.88 / 0.85 / 0.80 ; 1.00 / 1.00 / 0.99 |
| D rule n, R=2 | 0.46 / 0.41 / 0.29 ; 0.71 / 0.65 / 0.49 | 0.65 / 0.62 / 0.53 ; 0.88 / 0.86 / 0.78 | 0.78 / 0.76 / 0.70 ; 0.95 / 0.94 / 0.91 | 0.87 / 0.85 / 0.81 ; 0.98 / 0.98 / 0.96 |
| E same shape x4 | 0.21 / 0.18 / 0.13 ; 0.60 / 0.55 / 0.44 | 0.41 / 0.35 / 0.26 ; 0.88 / 0.82 / 0.70 | 0.62 / 0.55 / 0.45 ; 0.98 / 0.96 / 0.91 | 0.79 / 0.73 / 0.61 ; 1.00 / 1.00 / 0.98 |
| E rule n, R=3 | 0.26 / 0.21 / 0.16 ; 0.60 / 0.51 / 0.40 | 0.48 / 0.42 / 0.31 ; 0.86 / 0.81 / 0.68 | 0.68 / 0.63 / 0.50 ; 0.97 / 0.95 / 0.88 | 0.82 / 0.78 / 0.67 ; 0.99 / 0.99 / 0.96 |
| E rule n, R=2 | 0.32 / 0.27 / 0.17 ; 0.54 / 0.46 / 0.32 | 0.54 / 0.48 / 0.35 ; 0.79 / 0.73 / 0.58 | 0.70 / 0.67 / 0.54 ; 0.91 / 0.89 / 0.79 | 0.83 / 0.80 / 0.71 ; 0.97 / 0.96 / 0.91 |

Expected rollouts per round: A 218 (x4), 322 (R=3), 478 (R=2); D 198, 301, 438; E 120, 170, 244.

Reading and recommendation for the scaling arm:
- Doubling the budget fits 4 rounds of the matched shape (A, D, E), or 3 rounds with larger confirmation, or 2 rounds with a much larger one.
- For the question "is the edit found at all during the search" (+0.15 and larger), more rounds of the matched shape win: A 0.88 to 0.95, D 0.89 to 0.96 and E 0.70 to 0.88 at +0.15, and 0.91 to 1.00 at +0.20. The R=3 version is a close second and has higher per-round power (about +0.08 at +0.10 and +0.06 at +0.15).
- For a single-round decision on small effects (+0.10), larger confirmation helps: 0.42 / 0.37 / 0.30 per round on A versus 0.30 / 0.26 / 0.21, but only 2 rounds fit, so search-level power at +0.10 is lower (0.50 to 0.67) than four small rounds (0.60 to 0.76).
- Suggested scaling arm: "same shape, rounds scale with budget" (R = floor((B - baseline) / W)), because it keeps FWER per round identical (at most 0.093) and only adds rounds; the cost is that the family-wise error over the whole search rises with R (4 rounds at 0.093 is up to about 0.32 for at least one false crown). State that in the label. If the user wants a per-search FWER near 0.10 or below, tighten alpha to about 0.03 at R = 4, which this addendum did not simulate.
- Not simulated: K=8 with recalibrated alpha, and rounds that reuse the same incumbent after a crown (here every round is independent and starts from the same incumbent).
