# Purpose

## Origin
Iteration 1. Training traces show 7 failing task families (22-47, 247-24, 398-14, 46121, 47766, 48983, 6239) all scoring 0, while the wiki index already catalogues the patterns. Rejected proposals: none (skill-impact.md is empty).

## Patterns Addressed
- text-instead-of-typed-values (398-14: str '-' and int where float expected): `as_number` coerces; the skill mandates number formats for hyphen/zero display.
- assume-extent-from-preview (48983: filled 6 of 42 cells): `read_region`/`show_region` print the true grid with types before solving; `verify_output` counts non-empty cells against TARGET SIZE.
- Rebuilding the workbook with pandas `to_excel` (22-47, 247-24: header/index shifts, dropped formatting, 'written past where the answer ends', 'changed although expected is the cell's own original input'): `open_output` + `write_block` edit the original workbook in place via openpyxl and save to output_path, leaving untouched cells intact.
- tool-call-format-no-output-file (46121: three wasted rounds of pseudo XML): reinforced as the first rule in Instructions.
- Unverified finishing (6239, 47766: self-confirming wrong buckets): `verify_output` and `diff_region` make the agent re-open the file and see typed values and unintended changes before finishing.

## Evolution History
- v1 (this proposal): single general helper module `iolib.py` (open_output, as_number, write_block, read_region, show_region, verify_output, diff_region). No task-specific branches, no network, no scorer access.
