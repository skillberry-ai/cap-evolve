## SpreadsheetBench: move procedure into code

Each candidate should make the agent **fail less by moving work from the model into deterministic code**, wherever code can fix the failure. Prompt edits alone are not enough.

### 1. Diagnose first
For every recurring failure cluster in `./trajectories/`, decide which of two kinds it is.

- A **procedure** the model gets wrong. Code can fix these. Typical procedures:
  - finding the right sheet, header row or data range;
  - parsing dates, numbers or currency stored as text;
  - writing to the exact answer range given in the task;
  - preserving formulas versus writing values;
  - copying formats;
  - handling merged cells;
  - re-opening the saved output workbook and checking it.
- A **judgment** call. These need prompt text.

### 2. Prefer code for procedures
Write a general helper under `skills/spreadsheet-helpers/scripts/<name>.py`, or create a new skill, so the agent calls it instead of re-deriving the steps every time. Examples:

- `locate_table(ws)` and `find_header_row(ws)`;
- `normalize_number(s)` and `parse_date(s)`;
- `write_range(ws, answer_position, values)`;
- `verify_output(path, answer_position)`, which re-opens the file and checks that every target cell is filled and has the right type.

### 3. Document every helper in `SKILL.md`
For each helper, write what it does, its signature, **when** to call it, and an example call. The agent sees `SKILL.md` in its system prompt and imports the helper as `skills.spreadsheet_helpers.<script>`.

### 4. Point the system prompt at the helpers
Say when to call which helper, and add a verify-before-finish step. Keep the prompt short and move procedure into code.

### 5. Requirements for every helper
- General across tasks: no task ids, no answer values, no task-specific branches.
- Offline, deterministic and fast.
- A pure function of its arguments that writes only to the path it is given.
- Safe on bad input: return or raise a clear error, and never crash the kernel.
- Passes the helper lint and the smoke test.
- Has a small self-check on synthetic input, guarded by `if __debug__` or an equivalent.

### 6. Combining edits
One candidate may combine edits to `prompt.md`, `task_template.md`, `SKILL.md` and scripts, as long as each edit targets a diagnosed failure cluster.
