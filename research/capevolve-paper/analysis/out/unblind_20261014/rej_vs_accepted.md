# V3B1REJ: rejected vs accepted HC-stock candidates (descriptive; commissioned after the main results were seen, erratum 19)

Each candidate is one cell, expressed as its held-out test-20 delta against the seed of ITS OWN window (REJ, CHAIN or main window; different time blocks). The REJ window's in-window seed drift is flagged (5I: block range 0.269 vs SE of difference 0.072), so the REJ cells use the BLOCK-ADJUSTED delta (the seed's task-demeaned block effects subtracted from every trial); the CHAIN and main windows did not flag and use the plain delta. The unadjusted deltas are in rej_vs_accepted.json (`delta_raw`) and in the summary below. Accepted = the 9 CHAIN intermediates + the 3 final champions; rejected = the 45 REJ cells. One search seed = one stratum.

## Rejected minus accepted

- rejected: n = 45, mean delta +0.108 (SD 0.039)
- accepted: n = 12, mean delta +0.079 (SD 0.046)
- rejected minus accepted: +0.029, 95% percentile bootstrap over candidates stratified by search seed [0.001, 0.056] (20,000 draws; treats candidates as exchangeable within a seed, which they are not: candidates share ancestors; the interval is descriptive)

- seed 0: accepted n = 4, mean +0.076; rejected n = 15, mean +0.105; difference +0.029
- seed 1: accepted n = 4, mean +0.074; rejected n = 15, mean +0.104; difference +0.030
- seed 2: accepted n = 4, mean +0.088; rejected n = 15, mean +0.115; difference +0.027

Share of candidates above the in-window seed: rejected 45/45, accepted 12/12; share whose artifact-level CI excludes 0 (upward): rejected 22/45, accepted 3/12.

## Exploratory: gate score vs held-out delta (Spearman, candidates as units; permutation p, 20,000)

| set | n | gate = paired search-time delta (train mean minus parent) | gate z | search-time train mean |
|---|---|---|---|---|
| rejected only | 45 | rho +0.36 (p 0.013) | rho +0.34 (p 0.021) | rho +0.56 (p 0.000) |
| accepted only | 12 | rho -0.04 (p 0.910) | rho +0.01 (p 0.969) | rho +0.78 (p 0.004) |
| all candidates | 57 | rho +0.05 (p 0.737) | rho +0.03 (p 0.849) | rho +0.63 (p 0.000) |

## Per candidate

| seed | candidate | status | window | search rollouts | gate paired delta | gate z | held-out delta | 95% CI |
|---|---|---|---|---|---|---|---|---|
| 0 | cand_0001 | accepted | CHAIN | 300 | +0.107 | 2.01 | +0.055 | [-0.041, 0.151] |
| 0 | cand_0002 | accepted | CHAIN | 450 | +0.047 | 1.10 | +0.005 | [-0.082, 0.092] |
| 0 | cand_0003 | rejected | REJ | 600 | +0.013 | 0.27 | +0.071 | [-0.044, 0.186] |
| 0 | cand_0004 | rejected | REJ | 750 | -0.033 | -0.68 | +0.039 | [-0.085, 0.163] |
| 0 | cand_0005 | accepted | CHAIN | 900 | +0.073 | 1.73 | +0.125 | [0.029, 0.221] |
| 0 | cand_0006 | rejected | REJ | 1050 | -0.027 | -0.60 | +0.109 | [-0.034, 0.252] |
| 0 | cand_0007 | rejected | REJ | 1200 | -0.073 | -2.01 | +0.064 | [-0.072, 0.200] |
| 0 | cand_0008 | rejected | REJ | 1350 | +0.013 | 0.29 | +0.157 | [0.036, 0.279] |
| 0 | cand_0009 | rejected | REJ | 1500 | +0.000 | 0.00 | +0.070 | [-0.067, 0.207] |
| 0 | cand_0010 | rejected | REJ | 1650 | +0.027 | 0.52 | +0.135 | [0.013, 0.257] |
| 0 | cand_0011 | rejected | REJ | 1800 | +0.040 | 0.86 | +0.133 | [0.017, 0.249] |
| 0 | cand_0012 | accepted (final) | main | 1950 | +0.067 | 1.84 | +0.118 | [-0.007, 0.242] |
| 0 | cand_0013 | rejected | REJ | 2100 | +0.020 | 0.68 | +0.118 | [-0.018, 0.254] |
| 0 | cand_0014 | rejected | REJ | 2250 | -0.107 | -2.64 | +0.079 | [-0.055, 0.214] |
| 0 | cand_0015 | rejected | REJ | 2400 | +0.000 | 0.00 | +0.083 | [-0.035, 0.201] |
| 0 | cand_0016 | rejected | REJ | 2550 | -0.047 | -1.42 | +0.155 | [0.019, 0.291] |
| 0 | cand_0017 | rejected | REJ | 2700 | -0.033 | -0.78 | +0.115 | [0.007, 0.224] |
| 0 | cand_0018 | rejected | REJ | 2850 | -0.053 | -1.44 | +0.122 | [0.012, 0.231] |
| 0 | cand_0019 | rejected | REJ | 3000 | -0.040 | -1.29 | +0.123 | [0.008, 0.238] |
| 1 | cand_0001 | accepted | CHAIN | 300 | +0.100 | 1.56 | +0.035 | [-0.046, 0.116] |
| 1 | cand_0002 | accepted | CHAIN | 450 | +0.060 | 1.80 | +0.065 | [-0.029, 0.159] |
| 1 | cand_0003 | rejected | REJ | 600 | -0.013 | -0.29 | +0.089 | [-0.001, 0.180] |
| 1 | cand_0004 | rejected | REJ | 750 | -0.033 | -1.00 | +0.065 | [-0.048, 0.179] |
| 1 | cand_0005 | rejected | REJ | 900 | +0.013 | 0.30 | +0.062 | [-0.045, 0.168] |
| 1 | cand_0006 | rejected | REJ | 1050 | +0.047 | 0.96 | +0.062 | [-0.047, 0.171] |
| 1 | cand_0007 | rejected | REJ | 1200 | -0.020 | -0.44 | +0.079 | [-0.008, 0.167] |
| 1 | cand_0008 | rejected | REJ | 1350 | +0.000 | 0.00 | +0.053 | [-0.029, 0.136] |
| 1 | cand_0009 | accepted | CHAIN | 1500 | +0.047 | 1.42 | +0.050 | [-0.037, 0.137] |
| 1 | cand_0010 | rejected | REJ | 1650 | +0.000 | 0.00 | +0.083 | [-0.022, 0.187] |
| 1 | cand_0011 | rejected | REJ | 1800 | +0.013 | 0.39 | +0.045 | [-0.053, 0.143] |
| 1 | cand_0012 | rejected | REJ | 1950 | -0.060 | -1.61 | +0.115 | [0.006, 0.223] |
| 1 | cand_0013 | rejected | REJ | 2100 | +0.013 | 0.40 | +0.119 | [0.036, 0.202] |
| 1 | cand_0014 | rejected | REJ | 2250 | +0.013 | 0.35 | +0.122 | [0.045, 0.198] |
| 1 | cand_0015 | rejected | REJ | 2400 | +0.033 | 0.68 | +0.153 | [0.059, 0.248] |
| 1 | cand_0016 | rejected | REJ | 2550 | +0.027 | 0.63 | +0.173 | [0.046, 0.300] |
| 1 | cand_0017 | rejected | REJ | 2700 | +0.027 | 0.58 | +0.177 | [0.089, 0.266] |
| 1 | cand_0018 | accepted (final) | main | 2850 | +0.060 | 1.25 | +0.148 | [0.045, 0.250] |
| 1 | cand_0019 | rejected | REJ | 3000 | +0.027 | 0.85 | +0.168 | [0.073, 0.264] |
| 2 | cand_0001 | accepted | CHAIN | 300 | +0.100 | 1.63 | +0.025 | [-0.050, 0.100] |
| 2 | cand_0002 | accepted | CHAIN | 450 | +0.047 | 1.36 | +0.100 | [0.005, 0.195] |
| 2 | cand_0003 | rejected | REJ | 600 | -0.020 | -0.49 | +0.095 | [0.001, 0.188] |
| 2 | cand_0004 | rejected | REJ | 750 | +0.013 | 0.30 | +0.035 | [-0.064, 0.134] |
| 2 | cand_0005 | rejected | REJ | 900 | -0.007 | -0.17 | +0.082 | [-0.022, 0.187] |
| 2 | cand_0006 | rejected | REJ | 1050 | -0.027 | -0.60 | +0.047 | [-0.080, 0.175] |
| 2 | cand_0007 | rejected | REJ | 1200 | -0.007 | -0.13 | +0.125 | [-0.014, 0.264] |
| 2 | cand_0008 | rejected | REJ | 1350 | +0.000 | 0.00 | +0.132 | [0.018, 0.246] |
| 2 | cand_0009 | rejected | REJ | 1500 | +0.040 | 0.86 | +0.160 | [0.015, 0.306] |
| 2 | cand_0010 | rejected | REJ | 1650 | +0.053 | 0.97 | +0.126 | [-0.009, 0.261] |
| 2 | cand_0011 | accepted | CHAIN | 1800 | +0.100 | 2.10 | +0.100 | [-0.020, 0.220] |
| 2 | cand_0012 | rejected | REJ | 1950 | -0.020 | -0.39 | +0.131 | [-0.014, 0.276] |
| 2 | cand_0013 | rejected | REJ | 2100 | +0.000 | 0.00 | +0.178 | [0.053, 0.304] |
| 2 | cand_0014 | rejected | REJ | 2250 | +0.027 | 0.63 | +0.131 | [0.003, 0.259] |
| 2 | cand_0015 | rejected | REJ | 2400 | +0.027 | 0.54 | +0.121 | [0.004, 0.239] |
| 2 | cand_0016 | rejected | REJ | 2550 | +0.013 | 0.30 | +0.124 | [0.015, 0.233] |
| 2 | cand_0017 | rejected | REJ | 2700 | -0.040 | -1.00 | +0.123 | [0.003, 0.243] |
| 2 | cand_0018 | rejected | REJ | 2850 | -0.027 | -0.66 | +0.115 | [-0.003, 0.232] |
| 2 | cand_0019 | accepted (final) | main | 3000 | +0.053 | 1.35 | +0.128 | [-0.020, 0.275] |

Sensitivity, unadjusted deltas: rejected +0.097, accepted +0.079, difference +0.018; REJ-window block effects of the in-window seed (hour blocks from the window start): {0: 0.038, 1: 0.024, 2: 0.067, 3: -0.187, 4: 0.031, 5: 0.026, 6: -0.122, 7: 0.024, 8: 0.082}.
