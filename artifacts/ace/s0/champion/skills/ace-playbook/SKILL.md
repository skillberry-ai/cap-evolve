---
name: ace-playbook
description: Notes and deterministic helper scripts curated by ACE from earlier tasks. Cite a note's id when it helps.
---

# ace-playbook

## Scripts

- [misc-00012] `skills.ace_playbook.find_header`: Call locate_header(ws, text) to find the (row, col) of a header label anywhere in the used range using normalized comparison (str(v).strip() == text.strip()); returns None if not found. Use before any column move or lookup instead of assuming a header row.
- [code-00160] `skills.ace_playbook.robust_load`: Call load_workbook_robust(path) when openpyxl raises wildcard/defined-name sheet-access errors or a plain load fails; it tries openpyxl, then index-based sheet access, then python-calamine, and returns (wb, sheets_dict) where sheets_dict maps normalized sheet names to openpyxl worksheets or a lightweight cell-grid fallback.
- [code-00083] `skills.ace_playbook.validate_formula`: Call check_formula(formula_string) before writing any formula via openpyxl; returns (ok, message) checking quote parity, paren balance, and common corruption patterns.
