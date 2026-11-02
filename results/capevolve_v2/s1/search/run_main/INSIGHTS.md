# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## SpreadsheetBench seed failures (iteration cand_0001, pending gate confirmation)
- What worked: (unconfirmed this iteration — gate result pending) pinning the fenced-python reply format with a literal worked example in both system prompt and task message; the 12 format-waste tasks burn every round on "No python code block was found".
- What didn't: (n/a, first iteration)
- Promising but not yet tried: deterministic recalculation of dependent formula cells for rate-change tasks (247-24); semantic column-selection by cell fill color (80-42).

## Structural-rejection signature (cand_0001 RESULT)
- What didn't: shipping a whole batch (prompt + task_template + 3 scripts + SKILL.md) at once scored val=0.000 with fixed={} — consistent with rejection-before-any-rollout (placeholder/brace or script validation), NOT behavioral regression (30 broken tasks would land ~0.45, not 0.000). Confirmed by cand_0001's RESULT line.
- What worked: (pending gate) the same edits behind zero-brace discipline — simulated .format() on prompt.md and the stripped task_template.md body, lazy openpyxl imports, import-safe self-checks (cand_0002).
- Promising but not yet tried: if a future candidate also scores exactly 0.000, bisect with a prompt-only edit on the seed task_template to isolate the structural check that fires.

## Reply-format cluster is the dominant lever (seed traces)
- What worked: (pending gate) literal worked fenced-block example at BOTH primacy (system prompt) and recency (end of task message).
- What didn't: the harness's own per-round correction message ("No python code block was found…") does NOT recover the model — 12 tasks burn every round despite it; prose correction alone is insufficient.

## Structural rejection, narrowed (cand_0003, pending gate)
- What didn't: two full batches (cand_0001, cand_0002) each rejected at val=0.000 with fixed={} — no rollouts ran. The common denominator beyond prompt prose: task_template.md edits, SKILL.md edits, and NEW bundled scripts.
- Promising but not yet tried: prompt.md-only candidate (cand_0003) as the bisect. Leading structural suspect: the bundled scripts — skill-package validate() runs each script's --self-check, and the prior scripts were module-style (no CLI self-check) and contained a task-specific literal ('Main!'A2:M70) a task-specificity lint would flag.

## Helper-surface bisect (cand_0004, pending gate)
- What worked: (pending gate) shipping the three helpers with zero task-specific literals, lazy openpyxl imports, real CLI self-check entries and a brace-free SKILL.md on top of the accepted cand_0003 prompt — the exact shape cand_0001/0002 lacked.
- What didn't: (confirmed by cand_0001/0002 RESULTs) module-style scripts whose self-check referenced a task-specific range literal get rejected before any rollout.
- Promising but not yet tried: deterministic INDEX/MATCH grid-fill helper (blank→0) for 48983-class tasks; soft out-of-range-change warning in verify_output.

## Verification blindness is the dominant non-format failure mode (cand_0004 diagnosis, pending gate)
- In 8 of the 11 non-infra failing/flaky tasks the agent's own verification output already displayed the symptom (sparse fills, blank rows, formula strings, truncated prints hiding a doubled separator) and it finished anyway, or its check could only confirm what it wrote (re-reading formula strings). A loud, untruncated, input-diffing save audit (verify_output) plus class rules for the knowledge gaps (blank→0, grouped aggregates, printed anchors) is the shipped bet.
- Reference material inside the workbook (Manual Result sheet, seeded example pair, pre-filled summary column) went unread on 4 tasks despite instructions pointing at it — list-every-sheet-first is cheap and general.

## Skill-package surface is structurally dead in this run (cand_0004 RESULT)
- What didn't: three batches shipping bundled scripts (cand_0001, 0002, 0004) all rejected at val=0.000 with fixed={}, including cand_0004 which followed every documented lint rule (CLI --self-check, lazy imports, zero task-specific literals, brace-free SKILL.md). Confirmed by three RESULT lines. Do not ship scripts again without new information about what the validator actually runs.
- What worked: prompt.md-only candidates run and can be ACCEPTED (cand_0003, +0.123). The prompt surface carries the whole run so far.
- Promising but not yet tried: task_template.md alone (confounded in the two early rejections, never tested in isolation — low expected value, only as a bisect if prompt edits ever 0.000).

## Verification blindness confirmed first-hand (cand_0005 spot-checks)
- 48527 t0: agent printed "D2: None D4: None D5: None" in its own verification and declared it "matches the logic" while the expected output had 4 values; it also overwrote a valued cell with None. 48983 t0: 7 of 42 grid cells filled, finished. 57113 t2: retyped output_path dropping one character of a hash and "verified" at the wrong path. These are the exact behaviors cand_0005's workflow-8 grader-audit and verbatim-path rules target.
- The trailing 3 "No python code block was found" rounds on nearly every task are the normal end-of-episode completion pattern, not a defect; only mid-episode occurrences (leading blank line before the fence, 57113) are real waste.
