# Latest agent-optimize tau2 candidate (c_win) fails full-val confirmation; evidence not committed

## Problem
`docs/RESULTS.md` (2042-2096, since #321) records that `c_win` is net harmful on full val. No per-task block data is committed, and no claim in the draft/post acknowledges it.

## Evidence
Pooled paired -0.0146 (SE 0.0181, z -0.81) from blocks +0.0041 (SE 0.0248) and -0.0333 (SE 0.0265) reproduces arithmetically; 2 replicated gains vs 7 replicated losses; control blocks differ by 0.0207 vs binomial SE 0.0262. Surrounding record: 5 of 10 TAU2_SUMMARY runs accepted nothing; the instrument needs ~178 trials/task to certify +0.02.

## Impact
Any statement that agent-optimize improves tau2 airline must be qualified; the earlier accepted guard edit (0.460 -> 0.545) is itself unaudited (draft 10).

## Correction
Commit the two block files and per-task deltas; cite the negative result in the paper.

## Acceptance
Block artifacts in `examples/tau2_airline/` with commit; paper states the null.
