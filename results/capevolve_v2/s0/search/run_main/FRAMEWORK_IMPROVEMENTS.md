# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

- The failure summaries label format-loop failures as "the code never wrote output_path", which points the optimizer at write-procedure work; the actual cause (assistant emits tool-call syntax the executor rejects, then repeats it) is only visible in traces. Consider having the runner detect "No python code block was found" rejections and surface them as a distinct failure category — or normalize the tool-call payload in the harness, which would fix ~27 trials deterministically where a prompt edit can only shift sampling probability.
- Trajectory JSON in ./trajectories/ has no field naming the per-round executor rejection messages; they must be extracted from trace contents by hand. A structured `round_errors` field would make this cluster mechanically detectable by the diagnose skill.

## cand_0002 — rejection forensics are unavailable to the next iteration
- cand_0001 was rejected at val 0.000 with ~30 tasks broken, but nothing in the workdir explains WHY: rejected.jsonl does not exist in the candidate dir, the copied diff.patch is truncated mid-file, and the RESULT line gives no gate reason. The next optimizer therefore cannot know whether the batch failed lint/smoke (mechanical) or genuinely regressed (behavioral) — and those two cases demand opposite responses. Suggestion: when a candidate fails validation or scores 0.000, persist (a) the lint/smoke/placeholder validation output, (b) the full untruncated diff, and (c) one line of gate reason into prior_iterations/<id>/, so successors can drop the fatal edit instead of guessing (I had to infer the special-token-poisoning hypothesis from the val pattern alone).

## cand_0003 — identical rejection stats across different candidates are undiagnosable
- cand_0001 and cand_0002 were both rejected at val=0.000 Δ=-0.700 with byte-identical
  broke (30 tasks) and unresolved (21 tasks) sets, despite structurally different edits.
  Identical per-task stats for different inputs means the evaluation never depended on the
  candidate — yet nothing in the workdir says WHICH mechanical check failed (or whether the
  eval infra errored). This forced iteration 3 into a surface-bisect instead of behavior
  work, spending a rollout-budgeted iteration on validation archaeology. Suggestion: when a
  candidate scores a uniform 0.000, record in prior_iterations/<id>/ whether zero rollouts
  were spent (validation reject) vs rollouts all errored (infra), plus the failing check's
  name and message. One line would have saved this iteration.

## Iteration 5 (cand_0005)
- The surface contract says bundled scripts "cannot be run as a CLI: there is no __main__" while the skill-package guidance says each script "must have a --self-check entry point, because validation RUNS it". These two requirements contradict; a candidate author cannot satisfy both confidently, and 3 script-bundling candidates in this run died at exactly val=0.000 pre-eval. The framework should state which validation actually runs on SpreadsheetBench scripts and return the lint/smoke failure reason in the rejection record (rejected.jsonl was empty/unreadable in this work dir, so the death cause was never observable).
- The gate's 0.000 total-collapse rejections are indistinguishable from infra noise in the provided stats; including a "candidate failed validation: <rule>" line in the RESULT stamp would save entire bisect iterations.
