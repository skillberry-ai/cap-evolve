Deterministic helper scripts for spreadsheet manipulation tasks. No scripts yet; the optimizer adds them under scripts/.
---

# spreadsheet-helpers

This skill package holds deterministic helper scripts for spreadsheet manipulation tasks. Its purpose is to make
procedural spreadsheet operations reliable, reproducible, and independent of the agent's prose reasoning. When the
same procedure goes wrong across multiple tasks — not a judgment call, but a mechanical step the model keeps
fumbling — the fix belongs here as code, not as more prompt text.

## When a script belongs here

Add a script when a procedure **recurs across tasks** in one of these categories:

- **Parse** — converting messy cell values to typed values (dates, numbers with currency symbols or thousands
  separators, percentages, strings that look empty or blank, mixed-type columns).
- **Locate** — robustly finding the true header row, matching column names despite casing, whitespace, or merged
  cells, and resolving an answer position (e.g. `"B2"` or `"A1:C10"`) to exact openpyxl/pandas coordinates.
- **Normalise** — applying a consistent canonical form to values before computing (trim whitespace, unify date
  formats, treat empty strings as empty rather than errors).
- **Compute** — deterministic arithmetic, lookups, conditional row filters, and tiered/thresholded calculations
  driven by parameters supplied as arguments.
- **Validate** — re-opening a saved workbook and checking that values, and only the values, landed in the target
  cells or range, with nothing outside it modified.

## Rules every script must follow

- **General**: no task ids, no hard-coded answer values, no task-specific branches or filename checks. All
  specificity comes in through arguments.
- **Offline**: no network access of any kind.
- **Deterministic and fast**: same inputs, same outputs, every time; runs in seconds.
- **Safe**: writes only to the path it is given, never to the read-only inputs under `/mnt/data`, and never reads
  gold files or the scorer.
- **Importable, not runnable**: scripts expose functions/classes only; there is no `__main__` and no CLI. They are
  imported inside the agent's kernel as `skills.spreadsheet_helpers.<script>` (hyphens in the package name become
  underscores).
- **Documented**: each public function has a short docstring stating what it does, its arguments, and when to call it.

## Current contents

No helper scripts exist yet. When the optimizer adds one under `scripts/`, it must be listed below with exactly one
line stating when to call it, e.g.:

- `scripts/<name>.py` — call when …

Until scripts are listed here, do not attempt to import anything from this package; solve the task directly with
pandas/openpyxl in your own code, following the agent system prompt's rules about answer positions, literal
computed values, and saving to the exact output path.
