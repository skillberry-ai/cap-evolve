# PROCESS — what I did this iteration (explainability; REQUIRED)

Single flaky task in val: `weighted-gdp-calc` (mean reward 0.80 over 10 trials). 8/10 trials
pass (reward 1.0), 2/10 fail (t6, t8 → reward 0.0). Only the `xlsx` skill is deployed. I
diagnosed both failing trials against passing t0 (3 parallel read-only subagents) and found
TWO independent, general root causes for the flakiness. Both fixed additively.

## Ranked issue list (clusters by # failing trials × score recoverable, biggest first)
| rank | cluster | trials | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | recalc-ordering / cached-values wiped | t8 (and any run that re-saves after recalc) | Agent recalc'd a *disposable copy* / re-saved via openpyxl for a post-recalc format-restore, so the DELIVERED gdp.xlsx had formulas but NO cached values. Verifier reads `data_only=True` → sees None/0 → even Step1 lookups fail. | BEHAVIORAL + KNOWLEDGE | SCRIPT (new `verify_values.py`) + BODY |
| 2 | "percent of GDP" scale ambiguity | t6 | Agent stored the ratio (0.1974) instead of the percentage magnitude (19.74). Verifier reads the raw cell value and expects ~19.74 (confirmed: passing t0 = 19.74, failing t6 = 0.1974, exactly ×100). Step1 passes; net-exports + all stats + SUMPRODUCT weighted mean fail. | KNOWLEDGE | BODY |

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT | `xlsx/verify_values.py` (new) | Loads workbook with formulas and `data_only=True`; reports every formula cell missing a cached value → `status: stale` (exit 1) vs `ok`. General openpyxl behavior, no task specifics. Agent runs it as final gate; `stale` tells it to re-run recalc. | Yes — new file; only adds a check. |
| 1 | BODY | `xlsx/SKILL.md` | Added workflow step 7 + a "CRITICAL: recalc must be the LAST write" section: do all openpyxl edits (incl. formatting) before recalc; if you re-save after recalc you MUST recalc again; never recalc a throwaway copy; end by running `verify_values.py`. | Yes — passing trials already recalc last; rule only steers away from the post-recalc-resave trap. |
| 2 | BODY | `xlsx/SKILL.md` | Added "'Percent of' values: match stored value to the cell's number format" rule under Formula Construction Rules: if cell is plain-number formatted store ratio×100, if `%`-formatted store the ratio; graders read the raw value. Format-driven → general, no hardcoded value/marker/filename. | Yes — objectively-correct Excel convention; a run already writing the right scale is unaffected. |

## Verify-the-fix (one line per change)
- `verify_values.py`: RAN on an openpyxl-only file → `status: stale`, flagged both formula cells (exactly the t8 delivered-file state); after injecting cached `<v>` values → `status: ok`. Both branches proven. (soffice absent in this workdir so recalc round-trip couldn't run here, but the traces show recalc.py succeeds in the task runtime.)
- recalc-ordering body rule: ties to t8 — the delivered gdp.xlsx (154KB vs 84KB passing) had no cached values after the format-restore re-save; the new rule + gate would have caught it and re-run recalc.
- percent-scale body rule: ties to t6 — computed row35 = 0.1974 vs verifier-expected 19.74 (passing t0). Rule instructs ×100 when target cells are plain-number formatted.

## Process & features used
- Subagents: 3 parallel read-only `general-purpose` subagents (diagnose t6, t8, and golden t0). Then serial edits (single skill, no merge conflicts). Verified script by running it in Bash.
- Prior iterations: none (fresh run; LEDGER/JOURNAL/RUNMAP empty).

## Good things to PRESERVE
- `verify_values.py` and the "recalc must be last" section — they close a general, high-blast-radius correctness gap for ALL formula tasks, not just this one.

## Deliberately skipped
- No percentile-function (PERCENTILE vs .INC/.EXC/QUARTILE) edit: t6/t8 fail net-exports row itself, so the miss is scale, not percentile choice; adding a percentile rule would be speculative.
- No frontmatter/description edit: the correct skill (`xlsx`) already fires in every trial.
