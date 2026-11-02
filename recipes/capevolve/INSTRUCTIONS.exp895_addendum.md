## Surface contract (identical for every arm in this experiment)

You may edit **three surfaces**, and nothing else.

- `prompt.md`: the system prompt.
- `task_template.md`: the per-task user message.
  - Keep every placeholder it contains, exactly as written.
  - A candidate that breaks a placeholder scores 0 without running.
- `skills/<name>/SKILL.md` and `skills/<name>/scripts/*.py`: skills and their helper scripts.
  - Each `SKILL.md` is appended to the agent's system prompt.
  - Each script is importable inside the agent's kernel as `skills.<name>.<script>`. A hyphen in `<name>` becomes `_`, so `skills/spreadsheet-helpers/scripts/x.py` is imported as `skills.spreadsheet_helpers.x`.
  - Scripts cannot be run as a CLI: there is no `__main__`.

What the agent has:

- The agent's only tool is **Python code execution** in a Jupyter kernel.
- The task's input files are under `/mnt/data`, read-only.
- The answer must be written to the output workbook path given in the task message.

Rules for helper scripts:

- A helper must be **general, offline, deterministic and fast**.
- It must hold no task ids, no answer values and no task-specific branches.
- It must not use the network.
- It must never read gold files or the scorer.
- A lint and a smoke test enforce these rules before any rollout. A candidate that fails either scores 0 for that candidate and spends no agent rollouts.

**Prefer deterministic helpers for procedural failures.** When a recurring failure is a *procedure* the model gets wrong, move it into a helper and tell the agent when to call it. Examples are finding the header row, parsing dates or numbers, writing to the exact target range, and re-opening and checking the saved workbook. Do this rather than adding more prose. Keep prompt text for *judgment* calls.

## SpreadsheetBench facts for this run
- Each trace in `./trajectories/` is one agent episode: the system prompt (with every `SKILL.md` appended), the task message, each code cell the agent ran and its output, and the scorer's gold-safe feedback (which range was checked, how many test cases passed).
- **Scoring:** a task passes only if every cell in its answer range matches, after LibreOffice recalculates formulas. A formula that is correct but was never evaluated passes; a value written one cell off fails.
- **Each task is scored 3 times** (k=3) and the per-task score is the mean. A task at 1/3 or 2/3 is unstable, not solved.
- `./guidance/skill-package/SKILL.md` and `./guidance/system-prompt/SKILL.md` are the menus of edit types for your two surfaces.

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

