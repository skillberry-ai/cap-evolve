# Small-optimizer ablation (16.1 -> 29.6): control mislabelled, replicate omitted, E1 bundles two changes

## Problem
Draft calls run 37204406089 "E0 none (control)" and lists a control replicate as its top P0 gap. In issues #651/#652 that run is the pre-experiment "baseline", and the real E0 replicate `37345961613` (56.9, +13.4 [6.5, 19.9]) already existed from 2026-10-05 but is not in the draft. "Output guard" (E1) is `output_guard + no_subagents`.

## Evidence
`sb_recompute.py` on the artifacts: 37204406089 59.85 (+16.06); 37345961613 56.89 (+13.4); E1 72.99 (+29.56); E2 66.67; E3 65.09; E4 61.09; all draft CIs reproduce. Control-to-control spread 3.0; E1 vs controls +13.1 / +16.1. Each arm is n=1; CIs are task sampling only. Issue #651 final report: E3 64.9 from raw rollouts vs 65.1 here. Mechanism counts (179/166 oversized outputs) are from uncommitted transcripts.

## Impact
The draft overstates its own evidence gap and understates control noise; a single-feature attribution is not supported.

## Correction
Relabel runs; include 37345961613; report E1 as the bundle; commit transcript statistics or soften.

## Acceptance
Table lists baseline-none and E0 replicate separately; the mechanism claim cites a committed statistic or is removed.
