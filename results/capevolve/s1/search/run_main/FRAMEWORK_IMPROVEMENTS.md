# FRAMEWORK-IMPROVEMENTS — suggestions for cap-evolve itself (cross-run)

NOT about this capability or this run's result — about what cap-evolve the FRAMEWORK should change so FUTURE runs (any capability, any project) go better: a confusing prompt section, a missing tool, a file you wished existed, a gate that felt wrong. Optional most iterations; add an entry whenever something about the framework itself (not the task) got in your way or surprised you.

- The `<|tool_call|>` format stall is a model-serialization failure the runtime already detects ("No python code block was found") but cannot repair; a runtime-side normalizer (extract the code from the pseudo-XML and execute it, or auto-retry with the format error prepended) would recover ~7 always-fail tasks deterministically — no prompt edit can fully guarantee it. Cap-evolve might expose a "reply normalizer" hook as an editable surface.
- The 62-message cap with byte-identical resubmissions (10–30 per trace on ~16 tasks) wastes large rollout budget; a harness-side dedup ("identical code → return previous output without a model call") would cut cost with zero behavior change.
- Scorer feedback truncation in the optimizer prompt makes cluster (a)/(b) lists incomplete; emitting the full failing-task list (or a path to it) would save re-derivation each iteration.

## Iteration cand_0002
- Recording the lint/smoke FAILURE REASON (not just val=0.000) in rejected.jsonl would have saved this iteration's forensics: the record was empty, so the root cause of cand_0001's collapse had to be inferred (openpyxl absent in lint env). A one-line "smoke: ImportError openpyxl" would make refuted-approach avoidance exact instead of guessed.
- Same for the runtime format stall (repeated from iter 1): a reply normalizer extracting code from pseudo-XML replies would deterministically recover the 7 always-fail stall tasks; prompt examples can only probabilistically nudge.

## From iteration cand_0005
- Three consecutive candidates (cand_0001/0002/0004) were killed mechanically (val=0.000, zero rollouts) with NO feedback about WHY — the optimizer had to infer the kill surface from broke-set byte-identity across rejected diffs. A one-line rejection reason in rejected.jsonl / the RESULT stamp (e.g. "lint failed: script X", "format substitution error") would have saved three iterations and ~1000 rollouts.
- The lint/smoke rules are stated prose-only ("a lint and a smoke test enforce these rules") with no visible spec of what they check; publishing the exact checks (or a local runnable lint) would let candidates be validated before spending the eval.
- With a 2160-rollout budget and 360-rollout evals, only ~6 full iterations ever fit; the run spent 4 of them on mechanical deaths. Consider a cheap "validation-only" dry-run gate that doesn't consume eval budget.
