# PROCESS — iteration cand_0004 (build on champion cand_0001)

Only the `xlsx` skill is deployed (docx/pptx/pdf absent). Sole val task:
`shock-analysis-supply`, 10 trials, BINARY all-or-nothing reward (a trial scores 1.0 only
if ALL 9 verifier tests pass, else 0.0). Champion cand_0001 = 0.20 = 2/10 trials pass.

## Per-trial ground truth (read from ./trajectories/ score.feedback)
| trial | reward | failing tests |
| --- | --- | --- |
| t5, t7 | 1.0 | none (full pass) |
| t3, t4 | 0.0 | ONLY `test_value_magnitudes` (near-miss — every other test passes) |
| t0,t1,t6,t8,t9 | 0.0 | 8/9 (catastrophic — only `test_required_sheets_exist` passes) |
| t2 | 0.0 | infra timeout (ignore) |

## Ranked cluster list
| rank | cluster | trials | root cause | tag | leverage |
| --- | --- | --- | --- | --- | --- |
| 1 | **Units/scale ×1000 not applied** | t3,t4 | Agent links Real GDP into `Production!E` WITHOUT `*1000` (keeps GDP in billions ~80 while capital K is in millions ~300k). TFP residual `lnZ=lnY−α·lnK` absorbs the offset so all formula tests pass, but `Ystar=EXP(lnZ_trend)·K^α` inherits GDP's units → H60:H65 ≈ 79–108 vs required 10 000–500 000. **Subagent confirmed both agents READ economic_models.md's explicit `*1000` rule and skipped it** → BEHAVIORAL miss, not knowledge gap. t3 also fails B3 depreciation 0.0051 (<0.01) from a tangled CFC/K currency conversion. | BEHAVIORAL | HIGH: flips 2/10 → +0.20 (val 0.20→0.40) |
| 2 | **Never reach build phase** | t6,t8,t9 | t6 ran out of turns during PWT ingestion; t8 entered plan mode → called unavailable AskUserQuestion → stalled waiting for user; t9 IMF-403 loop, never used Playwright, ran out of turns. Workbook left empty. | BEHAVIORAL/INFRA | HIGH but REFUTED levers (see below) |

## Kept edit (1 cluster fixed this iteration — cluster 1)
**Edit class: SCRIPT (+ small BODY/REFERENCE pointers).**

1. NEW `xlsx/scripts/check_econ_model.py` — a magnitude/units GATE the agent RUNS after
   recalc. Auto-locates the capital ("K") and output ("Real GDP"/"GDP"/"Y") columns by
   header label, computes the **capital-output ratio K/Y**, and FAILS (exit 1) with the exact
   remedy when K/Y is outside the economically-plausible ~1–30 band (a ×1000 error yields
   K/Y≈3000). Also checks the depreciation rate is in a plausible ~1–10% band. Reads only;
   writes nothing.
2. `xlsx/SKILL.md` body — added workflow **step 8**: for multi-source production-function
   models, RUN `python scripts/check_econ_model.py <file>` after recalc, do not reimplement,
   fix any FAIL and re-run before finishing. Added a concrete "capital-output ratio" numeric
   invariant to the multi-source section (K/Y must be ~1–30; if hundreds/thousands, scale GDP
   ×1000) — the specific knowledge the near-miss agents lacked.
3. `xlsx/references/economic_models.md` §3 — added the K/Y-ratio bullet as the single most
   reliable magnitude check, pointing at the script.

### VERIFY-THE-FIX + blast radius
- **Script VERIFIED by running** (`/tmp` tests): on the ORACLE workbook → prints `OK` exit 0
  (K/Y median 3.45, depreciation 1.52%). On a synthesized BROKEN copy (GDP ÷1000 into
  billions, B3=0.0051 = the exact t3 bug) → prints `FAIL` exit 1 with "multiply the GDP link
  by 1000" + "implausible depreciation" — i.e. it names the precise failed assertion of
  `test_value_magnitudes` (Ystar out of 10k–500k, B3 out of 0.01–0.03) and the fix.
- **Blast radius = bounded.** VERIFIED the script no-ops (NOTE, exit 0, no false alarm) on:
  (a) the empty `test-supply.xlsx` template (catastrophic trials that build nothing) →
  they are neither helped nor hurt; (b) the sibling `shock-analysis-demand` template (a
  demand-multiplier model with a "Real GDP" column but NO capital/depreciation) → gracefully
  finds no K-column and exits 0. Passing trials t5/t7 already have K/Y≈9 → script prints OK →
  no behavior change. So no currently-passing path is pushed off its route.
- **Generalizes** (non-overfit): keys on economic invariants (K/Y ratio band, depreciation
  band) and header labels, NOT on task-specific filenames/values/thresholds. No hardcoded
  answer. The ×1000 example is illustrative, not a literal rule.

## Deliberately skipped — cluster 2 (catastrophic t6/t8/t9)
Both plausible levers are REFUTED by prior RESULTS and I did not re-test them:
- cand_0002 shipped a bundled data-fetch script + concrete SDMX/ECB/PWT endpoints + closed-
  form HP filter → REJECTED (broke/fixed nothing). Endpoints/HP-math were not the bottleneck.
- cand_0003 shipped "build skeleton first / save early / don't enter plan mode / don't
  AskUserQuestion / finish autonomously" prose → REJECTED (reverted). Prose sequencing did
  not move the catastrophic trials.
The catastrophic failures are budget-exhaustion + plan-mode/AskUserQuestion stalls + IMF-403 +
Playwright-absence — an infra/agent-loop problem prose cannot fix and whose script lever was
already refuted. Adding another speculative edit here risks sinking a clean, verified cluster-1
win, so I focused this iteration on cluster 1 only (the instructions' "many fixes, each real
and safe" — here only one cluster has a real, safe, non-refuted fix).

## Process & features used
- **Subagents:** yes — 3 read-only `Explore` subagents in parallel over the large trajectory
  JSONs: one on near-miss t3/t4 (found the skipped `*1000`), one on passing t5/t7 (confirmed
  the winning `=WEO_Data!C10*1000` + K/Y≈9), one on catastrophic t6/t8/t9 (found the
  budget/plan-mode/403 stalls). Oracle + template inspected directly with openpyxl to fix the
  exact K/Y invariant band (correct 7–16 vs broken ~9200).

## Good things to PRESERVE
- `references/economic_models.md` unit-reconciliation rules 1–3 (from cand_0001, ACCEPTED).
- The new `scripts/check_econ_model.py` gate + workflow step 8 — the code-over-prose forcing
  function for the near-miss units cluster. Do not dilute.
- `recalc.py` untouched (on every passing path).
