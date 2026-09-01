# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # real trials × score recoverable, biggest first)
| rank | cluster | tasks / trials | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Mismatched delimiter fence — WRONG bracket kept in the *fixed* formula** | latex-formula-extraction — the 3 failing cand_0003 rollouts (seed0/8/9) ALL fail `TestFormulaContent::test_formulas_render_match_expected` on the SAME single missing formula | The PDF's F3/F5 has a typo: an inner fence `\left[ a_m + a_m^\dagger \right)` (open **bracket**, close **paren**). The task asks for a *fixed* version. Gold fixes it to matched **parens** `\left(a_m+a_m^\dagger\right)`. Failing runs "fix" it to matched **brackets** `\left[…\right]` instead — so the render misses gold. Passing runs happen to pick parens. Pure coin-flip: the cand_0003 prose ("the fixed formula pairs them") never says WHICH delimiter to keep, so the agent guesses and is right ~7/10. | BEHAVIORAL (deterministic step the agent botches inconsistently) | SCRIPT + BODY (marker/) |

Only one task exists (latex-formula-extraction); it uses only the `marker` skill (`pdf` untouched → zero
cross-task blast radius). Of the 10 current-champion (cand_0003) rollouts, 7 pass and 3 fail — and all 3
fail on the identical missing formula above (verified from each seed's `verifier/test-stdout.txt`
assertion). There is exactly ONE real failing cluster this iteration; I did not manufacture others.

## Changes made this iteration
| cluster | edit class | file | what & why it GENERALIZES | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (new) | `marker/scripts/fix_delimiters.py` | Deterministic repair of any mismatched `\left…\right` fence: adopts the CLOSING delimiter and rewrites the opener to match it (`\left[…\right)` → `\left(…\right)`); no-op on already-matched fences and on plain (non-`\left`) brackets. Stack-pairs `\left`/`\right`, only rewrites the mismatched opener. General LaTeX transform — NO task literals/filenames/values. Agent runs it to emit the *fixed* line instead of guessing the bracket. | Yes |
| 1 | BODY | `marker/SKILL.md` | Clarified the mismatched-fence rule: keep the mismatched pair VERBATIM in the *original* formula (reproduces the PDF), and added a new "Fixing a mismatched delimiter fence" section that points the agent to **run `scripts/fix_delimiters.py`** (execute intent, "do not hand-edit") to produce the fixed line, with the adopt-closing rationale. Replaced the old vague "…only the *fixed* formula pairs them" (which never said which delimiter). | Yes |

## Verify-the-fix (one line per change)
- **Script, on the ACTUAL failing input:** ran `python scripts/fix_delimiters.py` on the exact mismatched
  F5 `…\exp\left[i\eta_{i,m}\left[a_m + a_m^\dagger\right)\right]` → output is CHARACTER-IDENTICAL to the
  gold *fixed* formula in `verifier/rendered_formulas/expected_formulas.md`
  (`…\exp\left[i\eta_{i,m}\left(a_m + a_m^\dagger\right)\right]`). This is precisely the single formula the
  3 failing seeds' assertions report as `Missing` — so producing it makes `test_formulas_render_match_expected`
  pass. Also verified: no-op on an already-matched fence (`P_e` line unchanged), plain-paren formula
  (`\rho_c`) unchanged, and a reverse mismatch `\left( … \right]` → `\left[ … \right]` (adopt-closing holds).
- **Body:** the new section ties the execute-`fix_delimiters.py` step to the mismatched-fence typo; the
  original line is explicitly kept verbatim (gold's expected list contains BOTH the mismatched original and
  the parens-fixed version, so normalizing the original would newly-break it — the guidance forbids that).
- **Blast radius / SAFE:** `marker` is used only by latex-formula-extraction. The script is NEW code the
  agent opts into; it cannot change any currently-passing task (none other use marker) and is a verified
  no-op on correct formulas, so the 7 passing rollouts (which already emit parens) are unaffected. The body
  edit is additive/clarifying, not a rewrite of a rule the agent already follows.

## Process & features used
- Serial (one task, one skill, one cluster). Diagnosed from the champion's own rollouts: pulled every
  `cand_0003/seed*/verifier/{comparison_table.md,test-stdout.txt,reward.txt}` + the gold
  `expected_formulas.md`, and isolated that all 3 reward=0 seeds miss the identical parens-fixed formula
  while the auto-sized-sgn (F1) text diffs are render-neutral (only 1 missing in the render assertion).
- Verified the fix by RUNNING the new script on the real failing string and byte-comparing to gold.

## Good things to PRESERVE
- All cand_0002/cand_0003 render-fidelity prose (operator/tall → `\left`; short/subscript-only → plain;
  `\substack` verbatim; `\rho_1(\tau)` plain protection) — kept intact; this iteration only ADDS the
  mismatch-fix path and clarifies the fixed-formula step.
- `fix_delimiters.py` adopt-closing rule (marker misreads OPENING delimiters more; avoids `[[…]]` nesting).

## Deliberately skipped
- A blanket "normalize ALL fences" post-processor: would rewrite the mismatched ORIGINAL too, which gold's
  expected list still contains verbatim → would newly break it. The script + body are scoped to the *fixed*
  line only.
- The prior-iteration auto-*wrap* script idea (cand_0003 skipped it): different concern (over-application on
  held-out). My script does NOT add/remove `\left` on matched fences — it only repairs mismatched pairs, so
  that risk does not apply.
- marker CPU timeouts (infra noise): not a skill defect; not optimized.
