# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

## Iteration cand_0002
- Strategy: 4 parallel read-only diagnosis subagents (one per failure group), then merged edits across BOTH surfaces (prompt contract + skill scripts). Prior iteration cand_0001 was rejected with a total wipeout (val 0.000) — likely mechanical (validation), so this iteration invested in structural safety of the script package.
- Plateau/stall signal: too early (iteration 2).
- What to try next iteration: measure cluster A (wasted rounds) and helper adoption rate (grep new traces for `apply_edits`/`verify_output`/`find_text`) before choosing the next lever; if format lock-in persists despite top-of-prompt contract, it is a chat-template property and effort should move entirely to clusters C/D.

## Iteration cand_0003
- Strategy: 5 parallel read-only diagnosis subagents (one per failure group), then a single prompt-only edit. Motivated by two consecutive val=0.000 wipeouts whose common factor was the script package — this iteration is the controlled experiment: prompt-only, structurally different from both rejected batches.
- Plateau/stall signal: two mechanical rejections in a row; the search had learned nothing behavioral because nothing ever ran. Strategy: remove the suspect surface entirely rather than redesign it a third time.
- What to try next iteration: read this candidate's RESULT first. If it RAN (any per-task movement), the script package was the killer → reintroduce one minimal script. If it wiped out again at 0.000, suspect prompt/template mechanical validation (fenced block in system prompt? new first line in template?) and bisect by shipping a near-seed prompt with one added sentence.

## Iteration cand_0004
- Strategy: after cand_0003's ACCEPT proved the pipeline runs, reintroduce the script surface in its safest possible form (one 352-line helper, all INSIGHTS design rules) + extend the accepted prompt with ~15 rules from a fresh 4-subagent diagnosis of ALL current failures. This is the controlled experiment for the cand_0001/0002 wipeout cause: if this candidate zeroes, the script package is confirmed as the killer; if it runs, the wipeouts were something else (e.g. the literal tool-call token in cand_0002's prompt).
- Plateau/stall signal: none — first accept last iteration.
- What to try next iteration: read this RESULT first. ACCEPTED -> measure helper adoption rate in traces and double down on code levers (find_header_row, consolidate). val=0.000 wipeout -> resubmit identical prompt with no script (clean bisect). Behavioral reject -> drop only the broke={} rules.

## Iteration cand_0005
- Strategy: 5 parallel read-only diagnosis subagents covering ALL 31 failing/flaky tasks (mechanical pass/fail extraction from all 360 traces first, to recover the full failing list the truncated feedback summary hid), then a single prompt-only candidate. Lever choice driven by ledger pattern: 3/3 script-bearing candidates wiped out at val=0.000; prompt-only is the only surface with a measured behavioral result.
- Plateau/stall signal: none behaviorally (cand_0003 +0.114); the stall is MECHANICAL — the script surface has never produced a measurable trial.
- What to try next iteration: if this runs, isolate the wipeout cause with a script-ONLY delta (no prompt change) so a reject names the script unambiguously; also investigate whether prior diff.patch snapshots actually captured the shipped capability files (cand_0004's did not).
