# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Invalid-PO reported as raw token instead of `null` | invoice-fraud-detection (7/10 trials fail, ALL identical) | Agent interprets "if PO missing set to null" as *field-absent only*; when the invoice carries a PO that is absent from `purchase_orders.csv` ("PO-INVALID") it echoes the string. GT expects `null`: an invalid/not-found key == missing. | KNOWLEDGE (interpretation of a reconciliation convention) | BODY (fuzzy-match) — code-forward idiom + pointer |

There is exactly ONE failure cluster: all 10 trials' `::TestOutputs::test_content` fail on
`assert 'PO-INVALID' == None` (page 4). 3/10 pass (they null it); 7/10 echo the token. The
verifier trace confirms: `Expected 'None', Got 'PO-INVALID'`. Smoking gun — failing trial t0's
own script comment: *"'missing' -- interpret as invoice not carrying a PO number at all ... so we
keep it unless truly absent."* Passing trial t3: `po_out = None if (... po_out not in pos)`.

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY | fuzzy-match/SKILL.md | Added a concise, copyable idiom `report_key(source_key, reference_keys) -> key or None` under a new "Reporting reconciled keys (missing vs. present)" subsection in Entity Resolution, plus a one-line pointer in Overview. States the general convention: a lookup key absent from the reference table is *missing* → emit `null`, never echo a placeholder ("INVALID"/"N/A"/"NONE"/"-"/"UNKNOWN"). No task literals — pure reconciliation rule. | Yes — 3/10 passing trials already do exactly this; the idiom returns valid keys unchanged, so it cannot flip a correctly-reported PO. Only val task is this one; pdf/xlsx skills untouched. |

## Verify-the-fix
- Cluster 1 (fuzzy-match idiom): reproduced `report_key("PO-INVALID", valid_pos)` → `None` (matches
  GT `Expected 'None'` for page 4); `report_key("PO-1001", valid_pos)` → `"PO-1001"` (valid POs
  preserved, so no regression on correctly-reported rows); `report_key(None, ...)` → `None`
  (truly-absent field still null). Anchor link `#reporting-reconciled-keys-missing-vs-present`
  resolves. Body 153 lines (within budget), one-level structure, valid frontmatter.

## Process & features used
- Serial (no subagents): single, unambiguous cluster; the whole val set is one task, so fan-out
  offered no coverage gain and would only add regression risk.
- Read ./prior_iterations/cand_0001 (PROCESS + diff) + JOURNAL RESULT + LEDGER: cand_0001 targeted
  this SAME correct cluster but with a verbose 4-bullet prose block in fuzzy-match's Overview and
  was REJECTED (val 0.200, Δ-0.100, broke={} fixed={}) — i.e. it regressed nothing, just too weak
  to flip a flaky interpretation the agent actively rationalizes against. I REDESIGNED the lever:
  code idiom (agents copy code more faithfully than prose) placed in the code section the agent
  lifts reconciliation logic from, and dropped cand_0001's off-target extra bullets (criteria
  order / report-original-source / exact-before-fuzzy) to keep blast radius tight.

## Good things to PRESERVE
- The Invalid-PO→null diagnosis is CONFIRMED by the verifier assertion itself — never re-question it.
- Do NOT reintroduce cand_0001's verbose Overview prose block (rejected, weak). Keep the fix as a
  tight code idiom.

## Deliberately skipped (cluster + why)
- pdf/ and xlsx/ skills: NO failing signal touches them (PDF extraction, xlsx read, vendor fuzzy
  match all succeed in every trial). Editing them would fail the REAL test and only risk regressing
  the passing path. No second cluster exists to fix this iteration.
