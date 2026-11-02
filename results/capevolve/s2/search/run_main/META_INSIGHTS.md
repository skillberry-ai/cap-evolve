# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

## Iteration 1 (cand_0001)
- Strategy: 4 parallel read-only Explore subagents over the 50 failing/flaky traces (grouped by failure signature), then serial edit of prompt + template + two new bundled scripts. No prior RESULTs to build on (seed).
- Plateau/stall signal: none yet.
- What to try next: if cluster A (format lock-in) only partially flips, the residual is stochastic first-token behavior — try a literal worked example of a valid first reply inside task_template, or move the contract into the very first user message line. Keep diagnosis fan-out: it cost ~4 subagents and produced the full cluster map in one pass.

- cand_0003: after a candidate scores exactly 0.000, suspect validation/lint/smoke failure (scripts whose self-check needs packages missing from the validator env) BEFORE prompt content — write self-checks that exercise only stdlib paths and lazy-import heavy deps. Also: re-verify a rejected batch's diagnosis claims with fresh eyes before reusing them; cand_0001's cluster B/D descriptions were partly wrong (verification happens but is non-assertive; pandas round-trip corruption mostly unsupported), and building on the corrected diagnosis changes which edits are worth shipping.

## Iteration 4 (cand_0004)
- Strategy: after two 0.000 lint-deaths and one no-op re-measurement, switched the lever from "add code helpers" to "measurement hygiene": a single-surface (prompt.md + brace-free template sentences) candidate that cannot plausibly fail lint/smoke, so prompt content gets measured for the first time. Diagnosis re-verified with 4 parallel read-only subagents over the seed traces (the champion is still the seed, so iteration-1's traces remain current).
- Plateau/stall signal: three rejections with zero accepted candidates — but two were infrastructure deaths, not search results. The search has effectively had ONE real data point (the seed baseline).
- What to try next: if cand_0004 is accepted, add exactly ONE minimal stdlib-only script next iteration to isolate the script-lint question; if rejected with a normal score, read the per-task deltas to see which rule class moved and push that class. Never batch scripts with prompt edits again until the lint mechanism is understood.

## Iteration 5 (cand_0005)
- Strategy: 7 parallel read-only Explore subagents over ALL 39 sub-1.0 tasks (cand_0004 trajectories), then a single-surface prompt-only candidate. Deliberately NOT the "isolate the script-lint question with one minimal script" plan from iteration 4's handover: rollout budget is 83% spent, so the last full iteration went to the proven lever instead of an experiment with a known 0.000 failure mode.
- Lesson for future runs: check the remaining rollout budget BEFORE committing to a diagnostic-experiment iteration; an isolation test costs a full iteration's rollouts and has no fallback if it lint-dies.
- What to try next: if accepted, per-task deltas name which rule class moved; interpretation-level residuals (ambiguous prose with no in-file example) are the asymptote of prompt edits — stop stacking prose there.
