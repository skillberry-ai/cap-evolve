# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## SpreadsheetBench reply-format lock-in
- What worked: (pending this iteration's RESULT) moving the one-fenced-```python-block contract to the top of the system prompt AND the task message, with an explicit ban on `<|tool_call>` syntax.
- What didn't: the harness's per-round error message ("Reply with exactly ONE ```python fenced code block") NEVER recovers a trial already in tool-call mode — recovery only happens between trials (confirmed across 360 seed trials: no trial ever mixed formats). So the fix must act at trial start, not mid-trial.
- Promising but not yet tried: if prompt text can't shift the trial-start mode, nothing on these surfaces can — the distribution is decided by the model's chat template.

## Helper packaging can zero a whole candidate
- What didn't: cand_0001 added a 346-line helper and EVERY task scored 0 (val 0.000) — consistent with lint/smoke/package validation failing, not with a behavioral regression.
- What worked (design rules going forward): lazy-import openpyxl inside functions; `--self-check` that exits 0 when openpyxl is unavailable; script compiles standalone; valid SKILL.md frontmatter; body <500 lines.

## Verification behavior
- Confirmed by trace reading (seed): agents verify only the clauses they implemented and never diff the whole answer range against the input; failing trials overwrite pre-filled correct cells (194-19) and accept partial coverage (22-47, 402-43). A full-range changed-vs-input report is the highest-value deterministic check for this benchmark.

## Iteration cand_0003 diagnosis (pending RESULT)
- Full-trial quantification (all 360 seed trials): 15 tasks have trials locked in native tool-call markup from the FIRST reply (9 tasks 3/3 trials; ~35 trials total ≈ 0.10 val reward). No trial ever mixes formats; the mode is chosen at trial start. Mid-trial "No python code block found" nudges NEVER recover a locked trial.
- Flaky tasks are decided by coin-flip procedural choices, each visible as a pass-vs-fail trial pair: datetime object vs strftime string (66-24); openpyxl copy vs pandas round-trip (80-42); reading the named reference sheet vs guessing order (82-30); '+' separator vs concatenation (170-13); header=True vs header=False on range re-interpretation (402-43). Prompt rules that name the passing choice should convert 0.33–0.67 tasks to 1.0.
- Always-fail cell-level tasks split into: partial fill from silently skipped lookups (48983, 48527), padding past the answer's end (54638, 194-19), quoted-formula semantics drift (55427, 47766, 58109, 267-18, 247-24), and genuinely ambiguous instructions (118-50, 11842, 6239 — likely unfixable without overfitting).
- "UNCHANGED / byte-identical" failures (408-39) are silent no-ops: the agent's lookup misses, an `if found:` guard swallows it, and it finishes despite its own verification showing wrong values.

## Iteration cand_0004 additions (pending RESULT)
- Flaky pass-vs-fail pairs are overwhelmingly SEMANTIC drift, not noise (from 4-subagent full-trace diagnosis): array/CSE formulas written as text never recalc in LibreOffice (52216, 31011, 54638); dict-lookup keeps LAST dup where Excel MATCH keeps FIRST (55427); float-boundary `>=` needs epsilon (51-12); datetime cells need `.time()` extraction (45372); "today" means `datetime.now()` (32023). Each now has a named rule or helper.
- The biggest always-fail classes this round: preserve-originals violations (gold keeps unasked cells at input value — 398-14, 433-47, 247-24, 58949) and extent/write-back discipline (truncation, blank-convention mismatch, one-row-off). Deterministic verify_output (coverage + changed-vs-input) is the countermeasure.
- Remaining hard ceiling: genuinely ambiguous instructions (118-50, 48527, 53647, 433-47, 194-19) — wrong reading in all trials; no general rule can select the gold reading without overfitting.

## Iteration cand_0005 diagnosis (pending RESULT)
- The 20 always-fail + 11 flaky tasks under cand_0003 decompose into 8 clusters; the single most widespread behavior is the DEGENERATE REPEAT LOOP: 8 always-fail tasks burn 10-28 of 30 rounds resubmitting byte-identical failing code after their own verification shows wrong/empty cells (56786, 54638-t2, 254-34, 48983, 50768, 11842, 433-47, 22-47). The seed's one-line "do not resubmit identical code" is ignored; shipped a strengthened contract (same result twice -> next reply must change code or inspect new data).
- Flaky pass-vs-fail pairs remain semantic, not noise: missing leading "=" stores formula as text (31011); CSE/_xlfn formulas recalc to #N/A (52216, 54638); None over a live formula (45372); retyped output path with a dropped char (35742); epsilon vs exact float >= (51-12); "today" hardcoded from examples (32023); header anchored one row off (46121, 53647).
- New always-fail mechanisms this round: row-1-assumed-header excluded the key value from a subset-sum (254-34, 971406 vs 994110); ws.max_row overrun wrote outside the graded range (80-42); inverted lookup key overwrote the fill column (194-19); blank-vs-0 lookup semantics split BOTH ways (48983 wants 0, 58949 wants empty) — fixed with a discriminating condition, not a global default.
- cand_0004's diff.patch records ONLY a DIAGNOSIS.json change (30 lines, cut mid-line) despite its journal describing prompt+script edits — suggests the capability snapshot may have failed to capture its edits, an alternative wipeout explanation worth flagging to the framework.
