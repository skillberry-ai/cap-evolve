# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

<!-- cap-evolve:meta-insights-append-below -->

## Iteration cand_0001 (first real edit round)
- Strategy tried: diagnose every failing trial individually (per-trial rewards, not task means — the flaky tasks each failed for a DIFFERENT reason per trial), cross-read each failure against the benchmark's judge source (`epic-creator/eval/epic-decompose.yaml`) to learn the exact mechanically-decidable contract, then convert the four mechanical clusters into one bundled validator verified flag-for-flag against all 33 trial artifacts extracted from the trajectories. The two LLM-judgment clusters (redundant HLRs, soft AC) got worked-example prose at the decision point plus matching review-criterion checks. No val movement measurable yet (gate pending).
- Plateau/stall signal: none yet.
- What to try next iteration: the corpus-extraction + judge-parity verification loop is the reusable method — before shipping ANY validator/prose contract edit, run it against every trial's actual artifacts and require zero flags on passing trials. Also: per-trial reward decomposition (reward = (dq-1)/4 − 0.1·softgates) tells you exactly which judge each trial lost points to — cheaper than re-reading feedback prose.

