# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | embedded-xlsx formulas not recalculated after openpyxl edit | exceltable-in-ppt (1/10 trials failed → flaky, reward 0.90) | Agent edited the embedded `.xlsx` with openpyxl and repacked WITHOUT recalculating. openpyxl drops the cached results of ALL formulas on save, so `pd.read_excel` (verifier) reads `NaN` for every formula cell. Agent's own final note was the misconception: "leaving formula cells unchanged so they recalculate automatically" (false). | KNOWLEDGE gap → BEHAVIORAL miss | BODY (pptx + xlsx) + SCRIPT (bundle recalc into pptx) |

Only one task is in the val set; 9/10 trials passed (they ran recalc/soffice), 1 failed (t3, skipped recalc). This is the entire recoverable signal.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT | `pptx/scripts/recalc.py` (new) | Byte-copy of the proven `xlsx/recalc.py`. Makes the pptx editing workflow self-contained so the agent that launched only the pptx skill can recalc an embedded workbook without hunting for the xlsx skill. | New file; no effect unless invoked. |
| 1 | BODY | `pptx/SKILL.md` | New "Editing an embedded spreadsheet (OLE object)" subsection under the existing edit workflow: embedded `.xlsx` lives in `ppt/embeddings/`; openpyxl save drops cached formula results (even untouched formulas → NaN); MANDATORY recalc with `scripts/recalc.py` before repacking; only edit value cells, leave formulas as formulas. Encodes the general rule, no task-specific values. | Conditional ("if the embedded workbook contains formulas"); other pptx paths (create / template / plain-XML edit) untouched. |
| 1 | BODY | `xlsx/SKILL.md` | Sharpened step 5 from "MANDATORY IF USING FORMULAS" to "MANDATORY WHENEVER THE FILE CONTAINS ANY FORMULA" + explicit note that a value-only edit still drops all cached formula results, so recalc is required. Fixes the exact misconception for any xlsx-with-formulas edit. | Purely additive clarification; tasks that already recalc are unaffected; recalc is idempotent/safe. |

## Verify-the-fix (trace → what the fix now does on those exact inputs)
- Reproduced t3 on the real embedded workbook: `openpyxl` load → set B3=7.02 → save → `pd.read_excel` shows CNY→USD, CNY→EUR, etc. all become `NaN` — exactly matching the two failed assertions (`test_inverse_rate_updated`: expected 0.142 got nan; `test_other_cells_unchanged`: (CNY,EUR) 0.127 → nan). The missing step is LibreOffice recalc, which the oracle runs via `recalc.py` and which the skill now mandates. (soffice is not installed in this optimizer workdir, so the recalc leg itself was not executed here; the oracle's `solve.sh` proves recalc produces the correct cached values, and passing trials t0/t4/t7 all ran recalc/soffice.)
- Script sanity: `python3 pptx/scripts/recalc.py` prints correct usage; `ast.parse` clean.

## Process & features used
- Serial (single task, single failing trial) — parallel subagents unnecessary for one cluster.
- Read: task.md, oracle/solve.sh (gold path = edit value cell → recalc.py → repack), verifier/test_outputs.py (reads values via pd.read_excel), all 10 trajectories (only t3 failed), pptx/xlsx SKILL.md + recalc.py. No prior iterations (this is the first).

## Good things to PRESERVE
- The recalc mandate wording in both skills and `pptx/scripts/recalc.py`. Do not weaken "recalc whenever the workbook has any formula" — value-only edits still need it.

## Deliberately skipped
- No other failing clusters exist (9/10 trials pass). Did not touch docx/pdf (absent) or any pptx create/template path (only passing behavior).
