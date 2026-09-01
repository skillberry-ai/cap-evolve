# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | invalid-STATE-in-SourceData | sales-pivot-analysis (10/10 trials, only failing test) | Agent joins the population PDF data with income.xlsx using a **left/outer** join (`how="left"`), keeping ALL population rows. The PDF contains 4 "Other Territories" regions (Christmas Island, Cocos, Jervis Bay, Norfolk Island) that are NOT in income.xlsx and NOT valid Australian states. A left join keeps them (income cols become NaN), so the STATE column contains "Other Territories" → `TestSourceDataContent::test_state_values_are_valid` asserts states ⊆ 8 valid states and fails. Oracle uses `how="inner"`, which drops them. | KNOWLEDGE | BODY (xlsx) |

Only ONE cluster exists: every other verifier test (row count, quarter values, aggregations, join coverage, pivot config) already passes in all 10 traces. No padding edits.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| invalid-STATE-in-SourceData | BODY | xlsx/SKILL.md | Added a "Combining Data from Multiple Sources (Joins / Data Integration)" section before "Creating Excel Files": when enriching one dataset with another on a shared key for a report, use an **inner** join (not left/outer) so only records present in both sources remain; explains that unmatched rows produce NaN-filled cells that corrupt pivot aggregations and leave category values valid in only one source; adds a post-join sanity check (key non-null + print unique categories). General principle (no task-specific names/values). | Additive new section; does not alter the pivot-table or reading guidance the passing tests rely on. |

## Verify-the-fix (trace → corrected behavior)
- `test_state_values_are_valid` (all 10 traces show STATE contains "Other Territories" via `how="left"`, output 2454 rows w/ 49 NaN income): Re-ran the full pipeline (PDF extract → `merge(inc, on="SA2_CODE", how="inner")` → quartiles) on the real task inputs. Result: 2450 rows, `invalid states = set()` (state test PASS), row-count 2000–3000 PASS, quarters ⊆ {Q1..Q4} PASS. Inner join drops exactly the 4 "Other Territories" rows.

## Process & features used
- Serial (single failing task, single cluster — parallel fan-out not warranted). Inspected all 10 trajectories' traces (confirmed "Other Territories" + left-join in 10/10), read the task.md, verifier test_outputs.py, and oracle solve.sh, and re-ran the join on the actual PDF/xlsx to confirm the assertion flips to pass.
- Prior iterations: none (this is the first iteration on the seed baseline; LEDGER/JOURNAL/RUNMAP empty).

## Good things to PRESERVE
- xlsx pivot-table guidance (cacheId=0, field-index matching) — all pivot-config tests pass; do not disturb.
- The new inner-join section — it is the fix for the only failing cluster.

## Deliberately skipped
- All other verifier tests already pass in every trace; no other cluster exists to fix. Did not add a bundled join script: the enrichment (Quarter/Total columns) is task-specific, so a generic script would be rigid; the failure is a modeling/knowledge gap (agents deliberately chose left join), which prose in the loaded skill body addresses directly and generally.
