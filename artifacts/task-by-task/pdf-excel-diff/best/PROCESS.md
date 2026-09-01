# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Multi-page PDF table extraction drops rows | pdf-excel-diff (1 flaky trial of 10: t9) | The `pdf` skill teaches the fragile per-page pattern `pd.DataFrame(table[1:], columns=table[0])`. The header prints ONLY on page 0 of this 229-page table, so slicing `table[1:]` on every page deletes the first *data* row of pages 1–228 → 228 lost employees (10500 → 10272). 2 truly-modified employees (EMP05566, EMP07590) were among the lost rows, and the 228 losses were mislabeled "added". Result: 18 modifications reported vs 20 expected. | CAPABILITY-GAP (agent knows to extract tables but has no robust, row-loss-safe helper) | SCRIPT + BODY |

Only one task is in the val set and its only failure mode is the extraction row-loss above; deleted-employee detection and the comparison logic already pass in all trials, so no other cluster exists to fix.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (new) | `pdf/scripts/extract_table.py` | Robust multi-page table extractor: learns the header once, drops ONLY rows equal to the header, keeps every data row, prints the recovered row count. General (no task-specific IDs/columns/filenames); works whether the header appears once or repeats per page. | Additive — new file changes no existing behavior. |
| 1 | BODY | `pdf/SKILL.md` "Advanced Table Extraction" → "Large / Multi-Page Table Extraction" | Replaced the buggy `table[1:]`-per-page example (the exact anti-pattern that caused the loss) with: a warning, an execute-intent pointer to the script, a "sanity-check the row count" step, and a corrected inline snippet that learns the header once. | The old snippet was wrong for multi-page tables and only accidentally right for single-page ones; the new snippet is correct for both, so any pdf task is same-or-better. |
| 1 | BODY | `pdf/SKILL.md` Quick Reference table | Added a row pointing large/multi-page table extraction at the script. | Additive row. |

## Verify-the-fix (targets → verified on the real inputs)
- t9 `TestModifiedEmployees::test_correct_modified_count` / `test_correct_modified_ids` / `TestIntegration::test_full_comparison` (got 18 mods / 10272 rows). Downloaded the real `employees_backup.pdf` (229 pages) + `employees_current.xlsx`. Ran `extract_table.py` → **header correct, 10500 data rows** (not 10272). Ran the straightforward diff over the extracted CSV vs the Excel → **15 deleted, 0 added, 20 modified**, and both the deleted set and the modified-ID set **exactly match** `verifier/expected_output.json` (missing=∅, extra=∅). This is the same result the 9 passing trials produced, so the fix makes the good behavior deterministic.
- Blast radius: the pdf skill is shared, but the ONLY val task using it is pdf-excel-diff (which was flaky, not passing-solid). The script is purely additive; the body edit strictly improves correctness (verified on both header-once and header-every-page layouts via unit test → all rows preserved in both). No passing task is pushed onto a worse path.

## Process & features used
- Serial (single-model) analysis: only one failing task / one cluster, so fan-out subagents were unnecessary. Read the oracle `solve.sh` to confirm the intended row count (10,500) and the robust extraction contract, then reproduced the bug directly (naive extract_tables → 10501 rows incl. 1 header; per-page `table[1:]` → 10272) and verified the fix on the actual downloaded inputs.
- Prior iterations: none — this is the first iteration after seed (RUNMAP/LEDGER empty).

## Good things to PRESERVE
- `pdf/scripts/extract_table.py` and the corrected multi-page guidance — do not revert to any per-page `table[1:]` pattern; that is the exact cause of the row loss.

## Deliberately skipped
- xlsx skill: Excel reading (`pd.read_excel`) worked in all trials; no failure signal → editing it would be speculative.
- No full "diff" script shipped: the comparison logic already passes in 9/10 trials; the only defect is extraction. A diff script would drift toward task-specific/overfit. The general table extractor is the correct altitude.
