# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## SpreadsheetBench seed failures (iteration 1 diagnosis; confirmation pending cand_0001 RESULT)
- What worked: TBD by gate.
- What didn't: n/a yet.
- Promising (diagnosed, not yet confirmed): (1) 12/50 failing tasks lost ALL reward to reply-format lock-in — the model emitted raw `<|tool_call|>call:python_code` text instead of a fenced ```python block, wasted every round, and never wrote output_path; the fix lever is a hard output contract naming the exact forbidden tokens plus a resend-fenced recovery rule. (2) ~5 tasks saved a file but never re-verified computed values, then resubmitted byte-identical code for ~30 rounds — a bundled verify_output helper is the structural fix. (3) Array/CSE formulas and AGGREGATE/XLOOKUP/IFNA-class functions evaluate to errors/empty under the LibreOffice recalc grader — literals or simple formulas only. (4) openpyxl returns Excel error cells as plain "#N/A" strings — they must be treated as missing, and blanks written as None, never "".

- Refuted (cand_0001 RESULT: val 0.000): the "hard output contract naming the exact forbidden tokens" lever above — the batch that named `<|tool_call|>`/`call:python_code` literals catastrophically failed (whole candidate 0.000, 30 passing tasks broke; possibly smoke-test failure on openpyxl-dependent script self-checks, possibly token-priming). cand_0003 redesigns the same cluster A with a POSITIVE worked example (no forbidden-token names) and scripts whose self-checks are stdlib-only with openpyxl imported lazily.
- Verified diagnosis correction (cand_0003 subagent pass over the seed traces): the agent almost always DOES re-open and print the saved output — its verification is non-assertive, not absent. The fix is an asserting verifier (verify_output), not "remember to check". Also: the formula-recalc cluster is the strongest flaky-task lever — tasks 52216/56274/56563/42354 fail only in trials that wrote live lookup/array formulas and pass in trials that wrote literals.

## Lint-death vs capability failure (iterations 1-4)
- What didn't (confirmed by LEDGER): cand_0001 and cand_0003 both scored EXACTLY 0.000 with all tasks at 0 and zero fixed — the stated lint/smoke-failure signature, not measured agent behavior. Both shipped new scripts + SKILL.md rewrites; cand_0002 shipped no capability diff (0.675 = seed noise). Prompt CONTENT has never been measured before cand_0004.
- What worked: TBD by cand_0004 RESULT — it is the first prompt-only candidate (worked-example reply contract + value/placement/type rules; no scripts, no SKILL.md edits, no new braces, placeholders untouched).
- Promising but not yet tried: helper scripts remain blocked on the lint question (optimizer env cannot import openpyxl; lint env may share that). Next accepted candidate should isolate with ONE minimal stdlib-only script.
- Cluster-A mechanism (verified by trace read this iteration): model emits raw chat-template tool-call text with CORRECT code embedded; harness corrective messages alone never break the lock-in; the lever is an in-prompt demonstration present before turn 1. Passing trials (39046-t1, 7902-t1, 45372) all emit single fenced blocks, so a positive worked example matches passing behavior. Do NOT name the forbidden tokens (priming risk; also the cand_0001 form).

## Residual failure map after cand_0004 (diagnosed iteration 5, confirmation pending cand_0005 RESULT)
- Diagnosed across all 39 sub-1.0 tasks with 7 parallel subagents: the dominant residual root causes are (1) no calibration against in-file evidence — worked examples, check values, and 'Manual/Desired Result' sheets are ignored (~12 tasks); (2) formula-text-only verification — agents confirm the formula string, never the evaluated value, and use functions the recalc engine doesn't implement (AGGREGATE, IFNA, array-constant criteria) (~8 tasks); (3) destructive over-writing — blanking unmatched lookups, clobbering pre-existing correct/total cells, padding rectangles (~9 tasks). cand_0005 ships prompt rules for all three.
- Verified pattern (flaky pairs): the PASSING trial of a flaky task almost always differs from the failing trial by exactly one of: reading the in-file example/result sheet, using a plain legacy formula construct, not adding an invented tie-break/secondary sort key, or printing parameter cells before use. Flakiness is interpretation variance, not nondeterminism — rules that pin the passing interpretation are the lever.
