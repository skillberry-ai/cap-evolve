# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

<!-- cap-evolve:meta-insights-append-below -->

## Iteration cand_0001 (iteration 1 of 5)
- Strategy tried, and whether it moved val (cite LEDGER rows): single non-passing task (019, 0.75) → read ONE full trace end-to-end (stdout), extract the internal review's issue list + the final artifacts from rollout.metadata.files, then verify every candidate edit's firing condition PROGRAMMATICALLY across all 8 trajectories' artifacts before keeping it. Gate RESULT pending (LEDGER row not yet stamped).
- Plateau/stall signal, if any: none yet — first iteration off a 0.969 baseline; the headroom is one flaky task (max realistic gain this cluster ≈ +0.03 val reward).
- What to try next iteration: if 019 flips to 5/5, the remaining leverage is defect classes the script doesn't cover (gate metadata completeness — with the 020 pre-revision equivalence check) and watching for NEW minors the mechanical checks can't see; if 019 stays 4/5, suspect the scorer's truncated rationale tail and shift to AC-specificity/summary-completeness dimensions. Discipline worth keeping: the programmatic blast-radius scan (run the proposed guard on ALL tasks' reconstructed artifacts) is what made every edit here verifiably BOUNDED — it costs ~5 turns and converts SAFE from an assertion into a measurement.

