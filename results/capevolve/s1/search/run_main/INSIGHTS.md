# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## cand_0001 (iteration 1, pending gate)
- Diagnosis over all 49 failing tasks (5 parallel subagents): the two biggest reward sinks are NOT spreadsheet semantics — (1) the model intermittently emits `<|tool_call|>` pseudo-XML instead of a fenced ```python block (7 always-fail tasks executed ZERO code across all trials; 6 more flaky tasks lost their failing trials to it); (2) a degenerate loop resubmitting byte-identical code 10–30× to the 62-message cap (~16 tasks).
- Third sink: agents verify by printing and then ignore what they see — coverage holes, formula strings, numbers-as-text, and outside-range edits were all visible in the agent's own output before failing (12 tasks).
- Procedure errors (hard-coded header rows from the truncated preview, positional column mapping, pandas whole-sheet to_excel round-trips) account for another 7 tasks — classic helper-script territory.
- Shipped: format contract in prompt, anti-repeat rule, and locate_table/write_range/verify_output/range_utils scripts. All self-checks pass locally (openpyxl absent in optimizer env; tested against a minimal shim — future iterations can reuse that trick).

## cand_0002 (iteration 2, pending gate)
- Quantified the loop sink precisely: 2289 of the round replies in long failing traces are "[Code executed successfully with no output]" (~26 tasks) — the agent's blocks never print, so it resubmits near-identical code to the cap. Even when it DOES verify (22-47: sees F=None 15 rounds in a row) it never changes the write code. Rules shipped: print every block / never resubmit / same-defect-twice→change the write.
- The optimizer/lint env has NO openpyxl (confirmed by import). cand_0001's scripts imported it at module top — most plausible cause of its val=0.000 total collapse. ALL future helpers must lazy-import openpyxl inside functions and self-check with stdlib duck-typed stubs.
- prompt.md is format-substituted ({skills_root}): keep it brace-free except the two placeholders (str.format simulation passes). Never put tool-call special-token strings in agent-visible text — naming the forbidden syntax may make the reader emit it (cand_0001).

## cand_0005 (iteration 5, pending gate)
- Mechanical-kill signature, now with 4 data points: cand_0001/0002/0004 all scored EXACTLY 0.000 with byte-identical all-passing broke sets (no rollouts ran); the accepted cand_0003/seed changed nothing. Every rejected candidate had BOTH literal ``` fences in prompt.md/SKILL.md AND bundled scripts. cand_0005 is the bisect: prose-only, fences described in words, no scripts. Its gate result will (partially) identify the killer — read it before designing any future candidate.
- Loop sink re-confirmed on cand_0003 traces: ~15 controllable tasks burn all 30 assistant rounds resubmitting byte-identical no-print blocks ("[Code executed successfully with no output]" each time); 82-30 shows the variant where verify blocks print but write blocks never do.
- DO NOT ban pandas to_excel: 17 currently-passing tasks (10452, 108-24, 12864, 141-20, 170-13, 192-22, 250-20, 262-17, 2768, 30930, 31915, 325-44, 395-36, 47798, 48080, 48588, 577-40) write with it successfully; only a soft preference + rebuild-verification is safe.
