# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_growth_values` FLAKY (fails 3/10 trials: t4,t5,t9) | xlsx-recover-data | Growth Analysis **B8 "Avg Annual Budget"** is the only unstable cell. Verifier expects **7444.4** = mean of the **N=5 base years** FY2019–FY2023 (endpoint FY2024 excluded; oracle `(B8+B9+B10+B11+B12)/5`). In the failing trials the agent numerically **cross-checks the pre-filled peer cells** (C8=859.3 … J8=44.8), finds they are **6-year** means (FY2019–2024), "confirms" that convention, and writes **7610.3** → assertion `abs(7610.3−7444.4)=165.9 < 0.5` fails. Prior iteration's prose Principle #5 (cand_0001, ACCEPTED) states the 5-year rule but the agent **overrides prose with its own peer verification** in ~30% of trials. | BEHAVIORAL (agent knows the rule, discards it under peer evidence) | SCRIPT + BODY (data-reconciliation) |

Only ONE failing cluster exists in this val set. The other 3 cells in `test_growth_values` (B7=1534, E4=8.58, E5=5047) and all 11 budget/YoY/shares cells pass in every trial — I did NOT touch them (regression risk, no signal).

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT | `data-reconciliation/scripts/recover_growth_avg.py` (NEW) | Deterministic helper: locates the growth block, reads **N** from the CAGR exponent / "N-Year" label (fallback #FY-cols−1), maps each metric column to the primary source table, and for every `???` Average/Avg cell computes `mean(FY_start … FY_start+N−1)` — recovering any still-`???` source year from the YoY sheet first (order-independent). No hardcoded filename/value/marker — pure structural derivation. Prints `Sheet!Cell = value`. | Yes — only writes/reports `???` **Average/Avg** cells; skips pre-filled peers and every other cell. Verified it changes ONLY B8 (7444.4) and leaves C8..J8 + all other cells byte-identical. |
| 1 | BODY | `data-reconciliation/SKILL.md` (Principle #5) | (a) Points the agent at the script with **execute intent** via a CWD-robust `find`-based command; (b) adds a decisive **anti-peer conflict rule** that names the exact rationalization from the failing traces: "Do NOT infer the window from peer cells… numerically confirming against peers steers you to the WRONG window… when peers and the N-year definition disagree, the N-year definition wins." (c) keeps the hand-computable `mean(FY_start … FY_end−1)` definition as a fallback. | Yes — additive; concerns only Average/Avg cells and tells the agent to recover all other cells with the unchanged principles. Body 118 lines (well under 500). |

## Verify-the-fix
- **Script, run on the RAW incomplete workbook** (B9 still `???`): prints exactly `Growth Analysis!B8 = 7444.4 (mean of 5 base years 2019-2023, endpoint excluded)` — matches the verifier's expected 7444.4 (tol 0.5). Recovers B9=7139 internally via YoY (6906×1.0337), so it does not depend on the agent having filled the budget sheet first.
- **Blast radius (script):** diffed `--write` output vs input — the ONLY changed cell is Growth!B8; peers `[859.3,1100.2,6721.8,4227.7,131,2970.2,430.2,44.8]` and every other sheet/cell are untouched.
- **Runtime path:** simulated the agent's environment (workbook at CWD, skill copied under `skills/`) — the `find`-based command resolved and ran the script to 7444.4, exit 0. If the path ever fails, the agent falls back to the strengthened prose (no worse than status quo → cannot regress).
- **Body edit ties to the failed assertion:** the failing traces (t4/t5/t9) explicitly say "confirmed 6yr via peers → 7610.3"; the new anti-peer rule + execute-intent script remove that judgement from the loop.

## Process & features used
- Serial (single well-scoped flaky cluster; fan-out unnecessary). Read all 10 trajectories, isolated the 3 failing ones, confirmed the divergence value (7610.3 vs 7444.4) and the agent's peer-confirmation reasoning; read the verifier, oracle, answers, both editable skills, and prior PROCESS/diff/JOURNAL/LEDGER.
- Deployable editable skills here are `data-reconciliation/` + `xlsx/` (not docx/pptx/pdf from the generic boilerplate). Edited only `data-reconciliation` (the skill the agent actually launches for this task).

## Good things to PRESERVE
- Prior Principle #5 5-year definition (cand_0001) — kept and reinforced.
- The new `scripts/recover_growth_avg.py` + the execute-intent pointer + anti-peer conflict rule. Do not revert.
- Do NOT convert B7/E4/E5 or any budget/YoY/shares cell — they pass as-is.

## Deliberately skipped
- Any edit to `xlsx/SKILL.md`: the agent launches it but never runs its scripts and follows its guidance where used; editing it is off-path and risks over-trigger.
- A full 15-value auto-solver: high regression risk on the held-out gate (different workbooks) and the agent's inline-coding style — the surgical avg-window helper is the minimal deterministic fix for the only unstable cell.

## Lever switch (plateau reasoning)
- cand_0001 already tried PROSE for this cluster and was ACCEPTED but left it FLAKY (0.70). Per guidance, for a BEHAVIORAL miss where the agent has the rule but discards it, I switched the lever to CODE (a verified, runnable script) rather than adding another prose paragraph it would override the same way.
