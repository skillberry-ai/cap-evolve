# Family 4 (F4): registered results (confirmatory replication of tool versus prose on new frozen champions; exploratory as to the framework)

champions present: ['nk2s0', 'k165s0', 'k165s1', 'k165s2']; tasks 20; infra_final rows by arm: {'seed-check': 0, 'F4-nk2s0-code': 0, 'F4-k165s1-prose_B': 0, 'F4-k165s0-prose_B': 0, 'F4-k165s2-prose_B': 0, 'F4-k165s1-code': 0, 'F4-k165s0-base': 0, 'F4-k165s1-prose_C': 0, 'seed': 0, 'F4-nk2s0-prose_C': 0, 'F4-k165s1-base': 0, 'F4-k165s1-prose_A': 0, 'F4-k165s0-code': 0, 'F4-nk2s0-prose_B': 0, 'F4-k165s2-base': 0, 'F4-k165s2-prose_A': 0, 'F4-k165s0-prose_A': 0, 'F4-k165s2-code': 0, 'F4-k165s2-prose_C': 0, 'F4-nk2s0-base': 0, 'F4-k165s0-prose_C': 0, 'F4-nk2s0-prose_A': 0}; seed mean 0.435, seed-check 0.495

## reward: pooled code - mean(prose A, B, C)
pooled +0.030; two-level bootstrap [-0.011, +0.071]; t over 4 champion means [-0.004, +0.064] (df 3) raw p 0.0666
per champion: nk2s0 +0.030 [-0.056, +0.116] p 0.477; k165s0 +0.043 [-0.046, +0.133] p 0.325; k165s1 +0.047 [-0.007, +0.100] p 0.083; k165s2 -0.000 [-0.082, +0.082] p 1.000
leave-one-champion-out pooled: without nk2s0 +0.030; without k165s0 +0.026; without k165s1 +0.024; without k165s2 +0.040
PRIMARY VERDICT (addendum 34 rule): not detected (the bootstrap interval includes 0)

## decision steps (n_llm_calls - 1): pooled code - mean(prose A, B, C)
pooled -1.554; two-level bootstrap [-2.188, -0.863]; t over 4 champion means [-2.412, -0.696] (df 3) raw p 0.0104
per champion: nk2s0 -1.483 [-2.786, -0.180] p 0.028; k165s0 -0.840 [-1.835, +0.155] p 0.093; k165s1 -1.787 [-2.776, -0.798] p 0.001; k165s2 -2.105 [-2.877, -1.333] p 0.000
leave-one-champion-out pooled: without nk2s0 -1.577; without k165s0 -1.792; without k165s1 -1.476; without k165s2 -1.370

## seed-tool calls: pooled code - mean(prose A, B, C)
pooled -2.132; two-level bootstrap [-2.769, -1.405]; t over 4 champion means [-3.165, -1.099] (df 3) raw p 0.0072
per champion: nk2s0 -2.327 [-3.475, -1.179] p 0.000; k165s0 -1.168 [-1.977, -0.360] p 0.007; k165s1 -2.553 [-3.544, -1.563] p 0.000; k165s2 -2.480 [-3.067, -1.893] p 0.000
leave-one-champion-out pooled: without nk2s0 -2.067; without k165s0 -2.453; without k165s1 -1.992; without k165s2 -2.016

## pass^5: pooled code - mean(prose A, B, C)
pooled +0.042; two-level bootstrap [-0.031, +0.116]; t over 4 champion means [-0.051, +0.135] (df 3) raw p 0.2446
per champion: nk2s0 +0.055 [-0.020, +0.130] p 0.139; k165s0 +0.090 [-0.067, +0.247] p 0.245; k165s1 +0.066 [-0.055, +0.186] p 0.269; k165s2 -0.043 [-0.147, +0.062] p 0.404
leave-one-champion-out pooled: without nk2s0 +0.038; without k165s0 +0.026; without k165s1 +0.034; without k165s2 +0.070

## prompt tokens: pooled code - mean(prose A, B, C)
pooled -23563; two-level bootstrap [-33102, -13301]; t over 4 champion means [-36140, -10986] (df 3) raw p 0.0094
per champion: nk2s0 -21168 [-41728, -609] p 0.044; k165s0 -13540 [-28818, +1738] p 0.079; k165s1 -31205 [-46574, -15836] p 0.000; k165s2 -28340 [-38828, -17852] p 0.000
leave-one-champion-out pooled: without nk2s0 -24362; without k165s0 -26904; without k165s1 -21016; without k165s2 -21971

## draft-to-draft spread (reward; champion-mean per draft)
nk2s0: drafts A 0.575, B 0.540, C 0.580; SD 0.022; max pairwise difference 0.040; code 0.595; base 0.585
k165s0: drafts A 0.545, B 0.580, C 0.590; SD 0.024; max pairwise difference 0.045; code 0.615; base 0.540
k165s1: drafts A 0.560, B 0.570, C 0.575; SD 0.008; max pairwise difference 0.015; code 0.615; base 0.525
k165s2: drafts A 0.585, B 0.595, C 0.620; SD 0.018; max pairwise difference 0.035; code 0.600; base 0.600

## code - base and prose_d - base (reward), pooled over champions: raw t over champion means
code - base: +0.044 [-0.028, +0.116] over champions; per champion [0.01, 0.075, 0.09, 0.0]
prose_A - base: +0.004 [-0.032, +0.040] over champions; per champion [-0.01, 0.005, 0.035, -0.015]
prose_B - base: +0.009 [-0.059, +0.076] over champions; per champion [-0.045, 0.04, 0.045, -0.005]
prose_C - base: +0.029 [-0.014, +0.071] over champions; per champion [-0.005, 0.05, 0.05, 0.02]