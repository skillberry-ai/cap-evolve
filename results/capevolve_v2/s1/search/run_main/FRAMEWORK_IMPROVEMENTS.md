# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

- The scorer feedback lines are the fastest failure signal, but the wasted-round marker ("No python code block was found") only appears inside trajectory user-messages, not in score feedback — a derived per-task "wasted_rounds" field in the rollout record would surface the dominant cluster without a custom scan.
- Flaky tasks would be easier to diagnose if the feedback line named which trial it came from (it says LAST trial, but the mean is what matters).

- A rejected candidate's val=0.000 (exactly, with fixed={}) is indistinguishable in the LEDGER from a behavioral wipeout, but the two demand opposite next-iteration strategies. Stamping the rejection REASON (lint/smoke/placeholder failure vs measured regression) into the RESULT line would prevent the next iteration from re-litigating it.
- prior_iterations/<id>/diff.patch was truncated mid-file (8034 bytes, ends mid-line), so the exact structural break of the rejected candidate could not be recovered — copying full artifacts (or the whole candidate dir) would make rejected iterations actually diagnosable.

## Iteration cand_0003
- The rejected.jsonl gate reasons were not materialized in this work dir (empty .capevolve/run_main), so two iterations were spent guessing why candidates scored exactly 0.000. Surfacing the lint/smoke failure reason (or even "failed validation: <check name>") in the RESULT line would let an optimizer fix the structural break in one iteration instead of bisecting blind.

## Iteration cand_0004
- rejected.jsonl / history.jsonl were referenced in the instructions but do not exist in this working directory (.capevolve/run_main is also absent here) — the rejection record had to be reconstructed from JOURNAL/LEDGER. Copying them into the candidate dir (or stating they may be absent early in the run) would save a search.
- The surface contract says bundled scripts "cannot be run as a CLI: there is no __main__" while the skill-package guidance says validation RUNS each script's --self-check — these two statements conflict; clarify which one the lint enforces (I satisfied both: importable module + __main__ self-check entry).
- The failure summary block in INSTRUCTIONS.md duplicates large parts of CLAUDE.md verbatim (the whole trajectories section is pasted twice inside INSTRUCTIONS.md); deduplicating would shorten the prompt without losing signal.
