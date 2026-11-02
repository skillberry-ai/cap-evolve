# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## Reference sheets / pre-filled answer cells are ground truth (cluster verified cand_0005 diagnosis)
- What worked: cand_0003's prompt-only single-surface discipline (ACCEPTED +0.120, cite cand_0003) — reply-format contract + write/verify discipline.
- What didn't (confirmed by RESULTs): bundling helper scripts + SKILL.md edits — cand_0001, cand_0002, cand_0004 all scored exactly 0.000 with total-collapse broke sets (pre-eval death); treat the scripts/SKILL.md surface as poison until a dedicated script-only bisect survives.
- Promising but not yet tried (shipped this iteration as prompt rules, gate result pending): (a) agents ignore in-workbook reference/"manual result" sheets and pre-filled example cells (82-30, 194-19, 48527) — mandate inspect-first + reverse-engineer-from-examples; (b) empty answer cells from None-propagation where Excel semantics demand 0/#N/A (48983, 55427) and destructive blanking of filled cells (48527, 48620); (c) "N decimal places" = number_format, never round the stored value (46646); (d) answer-range axes/sibling columns decide aggregation unit — counts not per-record flags (43436); (e) values that appear as identifiers in the target sheet mean key-match, not sequential placement (194-19).
