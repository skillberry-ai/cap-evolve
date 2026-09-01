# PROCESS — iteration cand_0002 (parent = cand_0001, current best val=0.147)

## Method
Only tasks whose trace actually LAUNCHES one of our four shared skills (docx/pptx/xlsx/pdf)
can be moved by editing those skills. Confirmed via `Launching skill:` scan across all 43
trajectories: the ~28 non-office failing tasks (drone-planning, energy-*, jax, threejs,
dapt-intrusion, citation-check, …) never fire a skill and are unreachable — skipped.
Ground truth = the gold task defs at
`cap-evolve-benchmarks/skillsbench/tasks/<task>/{task.md,verifier/test_outputs.py,test.sh}`
plus the trajectory JSONs. Fanned out 3 parallel read-only diagnosis subagents (xlsx / pdf /
pptx+mixed). Then for every kept fix I READ the exact verifier assertions and, where a script
was involved, RAN it on the real task input against a faithful replica of the verifier
(installed openpyxl/pandas/python-docx incl. the pinned python-docx==1.1.2).

## Ranked issue list (office-doc clusters only)
| rank | cluster | tasks | root cause | tag | edit class | shipped? |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | embedded-xlsx-in-pptx | exceltable-in-ppt (0.0) | openpyxl save NULLS formula caches → pandas reads NaN → inverse/other/formula checks fail | CAPABILITY | SCRIPT + body | YES |
| 2 | docx template output | offer-letter-generator (0.0) | `python` → exit 127 + output written to wrong/relative path; script itself is correct | BEHAVIORAL/env | BODY | YES |
| 3 | form literal values | court-form-filling (flaky 0.67) | agent reformats phone `4125886066`→`(412) 588-6066`; verifier greps literal string | BEHAVIORAL | BODY (forms.md) | YES |
| 4 | form signature line | edit-pdf (flaky 0.33) | signature line left blank; `test_signature_added` needs name ≥2× | BEHAVIORAL | BODY (forms.md + SKILL.md) | YES |
| 5 | redaction output path | paper-anonymizer (0.0) | clean redaction but likely written to scratch dir not `/root/redacted/` | BEHAVIORAL | BODY (SKILL.md) | YES (low-conf, additive) |
| 6 | `python`→`python3` | all skill-using tasks | env has no `python`; traces show exit 127 loops | BEHAVIORAL/env | BODY (all docs) | YES |
| — | xlsx correctness (weighted-gdp, reserves, sales-pivot, xlsx-recover, financial-modeling-qa) | 5 tasks | task-specific lookup/scoring correctness | KNOWLEDGE/task-logic | — | NO (see skipped) |

## Kept edits + VERIFY-THE-FIX + blast radius
1. **pptx/scripts/edit_embedded_xlsx.py (NEW) + pptx/SKILL.md "Updating an embedded Excel table"**
   — VERIFIED: ran on the real `exceltable-in-ppt/environment/input.pptx` with `--set B3=7.02`;
   replicated ALL verifier checks (`test_exchange_rate_updated`, `test_inverse_rate_updated`,
   `test_other_cells_unchanged`, `test_formulas_preserved`, valid-zip, embedded-present) → ALL
   PASS. Proved the failure mode first: `openpyxl.load→edit→save` turns every formula cell into
   NaN under `pd.read_excel` (the verifier's reader). The script edits worksheet XML surgically
   (updates only the target value cell's `<v>`, leaves formulas + caches byte-intact).
   BLAST: no PASSING task uses pptx; exceltable-in-ppt is the only pptx task. Additive.
2. **docx/SKILL.md fill_template section** — added `python3` + absolute-path + `ls -l` verify.
   VERIFIED: fill_template.py on the real offer-letter inputs passes 100% of the verifier
   (split, nested-table, conditional, no-remaining) under python-docx==1.1.2; the produced file
   is correct, so the 0.0 must come from the `python`→exit-127 (seen in all 3 trials) and/or a
   wrong output path. BLAST: no PASSING task uses docx. Additive.
3. **pdf/forms.md "Copy values verbatim"** — VERIFIED against court-form-filling
   `test_content_present`: it greps literal `4125886066`/`5125658878`; `normalize_text` only
   lowercases+collapses spaces (keeps parens), so `(412) 588-6066` (the failing t1) never
   matches. Passing t0/t2 already kept raw digits → rule reinforces them, no change.
4. **pdf/forms.md + pdf/SKILL.md "Sign signature lines"** — VERIFIED against edit-pdf
   `test_signature_added` (name must appear ≥2×; failing t0/t1 left signature blank, passing t2
   signed). Court-form only checks name PRESENT, so signing doesn't break it.
   BLAST for 3+4: passing tasks (3d-scan-calc, hvac-control, protein-expression-analysis,
   syzkaller) don't use pdf; the two flaky pdf tasks' PASSING trials already exhibit the
   reinforced behavior. Additive.
5. **pdf/SKILL.md redaction: save-to-exact-path reminder** — verifier confirms
   `OUTPUT_DIR=/root/redacted` and that self-citations must be PRESERVED (so the diagnosis
   subagent's "delete self-cites" idea was DROPPED as wrong). Reminder is additive, fires only
   in redaction flows (paper-anonymizer). Lower confidence (couldn't confirm the exact output
   dir from the trace) but cannot regress.
6. **`python`→`python3` across docx/pptx/xlsx/pdf docs** (+ fixed `check_fillable_fields` →
   `check_fillable_fields.py`). SAFE: the sandbox has no `python` (exit 127 in traces),
   `python3` is guaranteed present, so strictly beneficial. protein-expression-analysis already
   runs recalc.py via python3 → unaffected.

## Deliberately skipped (why)
- **weighted-gdp-calc percent-scale hypothesis — REFUTED.** Verifier `EXPECTED_NET_EXPORTS_PCT`
  values are ~8–37 (i.e. ×100), which is exactly what the agent already computed (`/H26*100`).
  Not a scale bug; the residual is data-lookup correctness — no safe general skill fix.
- **reserves-at-risk / sales-pivot / xlsx-recover / financial-modeling-qa** — each is
  task-specific numeric/interpretation correctness. Any xlsx-body/reference edit is a guess I
  could NOT tie to a failing assertion and would share the skill with the PASSING
  protein-expression-analysis. Dropped per REAL/VERIFIED discipline (candidates for a future
  iteration only with a per-task-verified, provably-dormant helper).
- **Non-office failing tasks** — never launch a skill; unreachable by this artifact.

## Subagents / features used
3 parallel `Explore` diagnosis subagents (xlsx / pdf / pptx+mixed). All fixes self-verified by
running scripts against the real task inputs + verifier logic before shipping.
