# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_labels_not_covered` (edit-pdf, 1/10 trials → mean 0.90) | edit-pdf | Agent escalates ordinary value corrections (name/email/DOB) to `apply_redactions()`, and pads the redaction rect upward. On this form each value sits directly UNDER its label, so a padded redaction rect deletes the label above it. 9/10 trials white-cover corrections and pass; the 1 failing trial (t1) "redid it with true redaction" and lost a label. | KNOWLEDGE (mis-belief that extractable old text under a cover is a defect) → BEHAVIORAL (over-redaction) | BODY (decision rule + neutralize trigger) + SCRIPT (label-safe redaction helper) |

Only ONE task, ONE failure cluster exists this iteration (9/10 trials fully pass). No other clusters to fix; did not pad with speculative edits.

## Root-cause evidence (reproduced with Bash + PyMuPDF on the real input.pdf)
- Value boxes vertically abut their labels: e.g. `Yaya` y118.1 vs `STUDENT NAME:` y118.9 (0.8pt overlap); `A88888888` sits directly under `STUDENT PID#:`.
- `apply_redactions()` with the RAW `search_for` rect → labels preserved (missing=[]).
- `apply_redactions()` with the rect padded up 3pt → deletes `STUDENT NAME`,`STUDENT PID`; padded 5–8pt → also deletes `UCSD E-MAIL`,`DATE OF BIRTH`. **Padding upward is the trigger.**
- White-cover (`draw_rect`) never removes any label regardless of padding.
- t1 trace step 26: agent literally reasoned "old text still extractable underneath the cover … let me redo this using true redaction" → applied broad `apply_redactions()`. The skill's "pypdf can still extract the hidden text!" alarm is what triggered that detour.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| labels_not_covered | BODY | `pdf-editing/SKILL.md` CRITICAL RULES | Added decision rule: `apply_redactions()` ONLY for the field the instructions explicitly say to redact; white-COVER every other correction; NEVER pad/expand a redaction rect (esp. upward — deletes the label above). Generalizes to any form where values sit under labels. | Yes — endorses exactly what the 9 passing trials already do (white-cover corrections + shrunk PID redaction). |
| labels_not_covered | BODY | `pdf-editing/SKILL.md` TRUE REDACTION section | Scoped the "old text still extractable by pypdf" warning to the explicitly-sensitive field only, and stated plainly that extractable old text under a cover is EXPECTED/acceptable and NOT a reason to escalate to redaction. Removes the exact trigger for t1's destructive detour. | Yes — additive scoping; does not change the PID-redaction path. |
| labels_not_covered | SCRIPT | `pdf-editing/scripts/redact_value.py` (new) | Label-safe true-redaction helper: redacts the UNMODIFIED `search_for` rect (never padded) and re-inserts the masked value. CLI `OLD=NEW` + importable `redact_value()`. Body points at it with execute intent. Gives a safe one-liner for the one field that genuinely needs redaction, so the agent stops hand-rolling padded rects. | Yes — new file; only invoked on the redaction path, which still fully removes the PID. |

## Verify-the-fix (one line per change → what it does on the exact failing inputs)
- Decision-rule / never-pad BODY edit → targets t1's over-redaction; reproduced that padded redaction deletes `STUDENT NAME`/`STUDENT PID` while white-cover + raw-rect redaction keep all 7 labels. A full solution following the rule (white-cover name/email/DOB, shrunk-rect redact PID) passes ALL 9 verifier assertions locally.
- Trigger-neutralization edit → the sentence that produced t1 step-26 reasoning is now scoped so extractable-under-cover is declared acceptable; the agent has no reason to escalate corrections to redaction.
- `redact_value.py` → ran on real input.pdf with `"A88888888=****5678"`: no `A\d{8}` extractable, `5678` present, 0 labels missing. VERIFIED by running.

## Process & features used
- Serial (single task, single cluster) — no subagent fan-out needed; used Bash + PyMuPDF + pypdf to REPRODUCE the failure and VERIFY every edit against the real verifier assertions before shipping.
- Read from ./prior_iterations/ + RUNMAP: cand_0001 (rejected, Δ+0.000, broke={} fixed={}). It added a similar "prefer cover / never pad" prose + a `safe_redact.py` script, but LEFT the "pypdf can still extract!" alarm intact and buried the script at the bottom — so the agent's over-redaction TRIGGER remained and behavior didn't change. I redesigned: I NEUTRALIZE/scope that alarm (the actual trigger), put the decision rule in CRITICAL RULES (read first), and give a leaner helper. Did not re-add cand_0001's `safe_redact.py` verbatim.

## Good things to PRESERVE (do not let a future iteration undo these)
- The scoping that extractable old text under a white cover is ACCEPTABLE for ordinary corrections — this is what stops the label-deleting detour.
- The "never pad a redaction rect upward" rule and the raw-rect helper `redact_value.py`.
- white-cover as the default for value corrections; true redaction reserved for the one instructed sensitive field.

## Deliberately skipped (cluster + why)
- `text-parser` skill: no failures touch it; editing it would only add blast radius. Left untouched.
- No cosmetic/speculative edits: only one real cluster exists; padding the batch risks a regression that sinks the iteration.
