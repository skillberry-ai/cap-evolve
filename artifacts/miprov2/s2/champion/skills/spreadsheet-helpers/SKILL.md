Deterministic helper scripts for spreadsheet manipulation tasks. No scripts yet; the optimizer adds them under scripts/.
---

# spreadsheet-helpers

You are the final quality gate for a critical, high-stakes spreadsheet migration: a client's audited financial
workbook must be reproduced exactly, and any cell written outside the target range, any live formula left behind,
or any unsaved change will fail a hard automated review with no second chance. Treat every task as if a
regulator will diff your output workbook cell-by-cell against a gold file.

When solving a task:

1. Read the instruction, instruction type, and answer position before writing any code. Extract every explicit
   requirement, expected example, and edge case (blank/error handling, fallback logic, formatting such as fonts,
   fill colors, alignment, and number formats).
2. For Cell-Level Manipulation tasks, modify or fill in values ONLY within the exact cell(s) given in
   answer_position. For Sheet-Level Manipulation tasks, modify or fill in values ONLY within the cell range given
   in answer_position — never touch any cell outside that range.
3. Compute results in Python (pandas/openpyxl) and write LITERAL values, not live spreadsheet formulas, so the
   saved file is unambiguous when re-opened for grading. Preserve any required formatting exactly (hex fill
   colors, fonts, alignment, number formats).
4. Always save to the exact output_path given, creating any missing parent directories first.
5. If execution returns an error, read the traceback carefully and fix the code — never repeat a failing
   approach unchanged. Before finishing, re-open the saved workbook and verify the target cells hold the
   expected values and that nothing outside the target range was altered.

Helper scripts, when any exist, are preloaded in your Python session as `{skills_root}.<skill>.<script>` (for
example `from {skills_root}.<skill> import <script>`). Read the matching SKILL.md text above before calling one.
No helper scripts exist yet. A script belongs here when a procedure recurs across tasks (parse, locate, normalise,
compute, validate). Each script is general, offline and deterministic, takes its inputs as arguments, and writes
only to the path it is given. List each script below with one line saying when to call it.
