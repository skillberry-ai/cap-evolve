# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

## Iteration cand_0001 (run so far)
- Strategy tried: scripted scan of ALL 360 trajectories for the harness's wasted-round marker ("No python code block was found") found the single biggest cluster (12 tasks) in minutes — cheaper and more complete than reading traces. Two parallel read-only subagents then diagnosed the value-mismatch clusters. Result on val: pending gate.
- Plateau/stall signal: none yet.
- What to try next iteration: reuse the scripted scan (count wasted-round markers, no-output-file feedback) as a cheap recurrence check; diff passing vs failing trials of the SAME flaky task — the passing trial is a free specification of the fix (used for 66-24, 267-18, 227-40).

## Iteration cand_0002
- Strategy tried: re-verify cand_0001's diagnosis with a scripted scan (wasted-round marker counts across all 360 trajectories) + direct code-cell extraction instead of trusting the prior PROCESS; then rebuild the same edits under explicit structural validation (placeholder-set equality, .format() simulation, compile/import/self-check runs). Result on val: pending gate.
- Plateau/stall signal: none yet, but a second consecutive 0.000 would mean a structural check both batches share — switch lever to a minimal single-surface candidate to bisect.
- What to try next iteration: after any ACCEPT, grep new trajectories for `skills.spreadsheet_helpers` imports to measure helper adoption separately from rule adherence; adoption rate tells whether to invest in more helpers or in prompt rules.

## Iteration cand_0003
- Strategy tried: single-surface bisect. Both prior RESULTs (cand_0001, cand_0002) show val=0.000, fixed={}, identical 30-task broke set — the rejection-before-rollout signature, so the search has burned 2 iterations on an unlocated structural check. This iteration changes prompt.md ONLY (the one surface whose edit content is plain text with a verified placeholder set), holding everything else at seed, to isolate the failure domain. Result on val: pending gate.
- Plateau/stall signal: yes — 0.000 twice. Lever switched: from full-batch (prompt+template+SKILL+scripts) to single-surface bisect.
- What to try next iteration: if accepted, re-add surfaces one at a time (scripts last, written with a real --self-check CLI entry point and zero task-specific literals — the lint's likely tripwire); if rejected at 0.000 again, the break is in prompt.md itself — ship a fence-free, brace-free minimal prose edit to bisect within the surface.

## Iteration cand_0004
- The two-step recovery from structural rejection worked as a process: prompt-only bisect (cand_0003, ACCEPT +0.123) then re-add the risky surface incrementally with the lint rules baked in. Lesson: when a batch is rejected at exactly 0.000 with fixed={}, treat it as a validation failure and bisect by surface rather than abandoning the diagnosis.
- Parallel read-only diagnosis subagents (one per task group) over full traces were high-value: they surfaced per-trial pass/fail diffs (what the passing trial did differently) that per-task summaries hide — the flaky tasks' fixes came entirely from those diffs.
- The scorer feedback's COVERAGE/MISMATCH lines under-determine root causes; the decisive signal was reading the agent's own verification output in the trace and seeing it ignore visible anomalies.

## Iteration cand_0005
- Strategy tried: after cand_0004's third structural 0.000, stop re-attempting the skill-package surface entirely; re-ship that iteration's prompt-only edits (never executed) on the accepted cand_0003 prompt. Result on val: pending gate.
- Plateau/stall signal: the scripts lever is exhausted (3 rejects); the search is now effectively prompt-only. If prompt-only gains flatten too, the honest options are judgment-disambiguation prose for the VBA-paraphrase tasks or accepting the plateau.
- What to try next iteration: measure whether the workflow-8 grader-audit rule actually changes final replies (grep new traces for coordinate+repr prints); consider an "enumerate plausible readings of an ambiguous instruction and pick the one consistent with in-workbook reference material" rule for 433-47/118-50.
