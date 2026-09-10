# PROCESS — what I did this iteration (explainability; REQUIRED)

## Key finding: the val "task" is a MIXED pool, not one task
The 10 trials named `energy-ac-optimal-power-flow` are actually different SkillsBench tasks:
- t0,t1,t2,t3,t4 = the real ACOPF task; t5,t8 = employee-record diff; t6,t7 = PDF form-fill;
  t9 = **invoice-fraud-detection**.
- Outcomes (champion cand_0001): pass = t1,t5,t6,t7,t8; fail = t0,t2,t3,t4 (ACOPF verifier
  240s timeouts — infra), t9 (real content failure). Mean reward 0.50.

## Ranked issue list (clusters by recoverable score, biggest first)
| rank | cluster | trials | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Invoice-fraud: unresolved PO echoed instead of `null` | t9 (1/10) | Agent wrote `po_number:"PO-INVALID"` for an Invalid-PO row; GT = `null`. Task says *"If the PO is missing, set it to null"* + *"Invalid PO: the PO number doesn't exist in purchase_orders.csv"*. Agent read "missing" as *blank on invoice* not *not-found-in-lookup*. `::TestOutputs::test_content` asserts `act["po_number"]==exp["po_number"]` → `'PO-INVALID'==None` fails on page 4. | KNOWLEDGE (output convention) | DESCRIPTION + BODY (new tightly-scoped skill) |
| — | ACOPF verifier timeouts | t0,t2,t3,t4 (4/10) | Verifier re-solves the 300-bus ACOPF in-test; on 2 CPUs exceeds 240s → "no verifier reward (rc=0/1) … verifier timed out". Independent of agent/skills. | INFRA NOISE | SKIPPED (uncontrollable) |

t9 is otherwise fully correct (no vendor false-positives/negatives, all other pages match) —
only the null-PO convention flips it.

## Change made this iteration (ONE surgical edit)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | NEW SKILL (description + body) | `fuzzy-match/SKILL.md` | New tightly-scoped skill for reconciling transactional records against authoritative reference tables. Core rule: **an unresolved foreign key (not in the lookup / malformed) is reported as `null`, never the raw string** — with an illustrative (non-hardcoded) validate-then-membership snippet. Plus normalize-before-match and priority-order rules, and difflib/rapidfuzz how-to (the task explicitly says "use fuzzy matching"). General to any invoice/vendor/PO reconciliation — no task filename/value/answer hardcoded. | Trigger scoped to invoice/reference-table reconciliation → does NOT fire on employee-diff (t5/t8) or PDF forms (t6/t7); ACOPF skills untouched (t0–t4). |

## Verify-the-fix
- **REAL**: ties to `::TestOutputs::test_content` assertion `'PO-INVALID' == None` on page 4 (t9 trace, this iteration's trajectories).
- **VERIFIED**: reproduced the rule on the Invalid-PO case — `PO-INVALID` / malformed / absent keys → `None`, valid keys preserved (matches GT page 4 = null). Frontmatter parses (YAML ok), name matches dir, desc 483 chars, 75-line body, zero links (no broken refs).
- **SAFE / blast radius**: the description front-loads "reconcile invoices/transactions/line-items against approved-vendor lists, purchase-order registers, customer masters; fuzzy vendor-name matching; foreign-key validation" — it matches t9's wording ("approved vendors", "purchase orders", "fuzzy matching", "invoice fraud") but NOT "find deleted/modified employees between two spreadsheet versions" (t5/t8) or "fill this PDF form" (t6/t7). Even if it loaded on an employee diff, the null-key rule is conditional (only when a foreign key fails to resolve) and inert there. ACOPF trials (t0–t4) don't match the description at all.

## Building on prior RESULTS
- Built on cand_0001 (ACCEPTED): kept all 3 ACOPF skills + `build_report.py` intact.
- cand_0002 (REJECTED, val 0.300) added `pdf/` AND `fuzzy-match/`. The `pdf/` package is a
  broad trigger that fires on the passing PDF-form tasks (t6/t7) → the likely regressor.
  I therefore did **NOT** re-add `pdf/` (or `xlsx/`), and shipped ONLY the reconciliation
  skill, with a tighter trigger than cand_0002's generic "matching entity names across
  datasets" so it won't pull in the employee-diff tasks.

## Deliberately skipped
- t0/t2/t3/t4 ACOPF verifier timeouts — uncontrollable (verifier's own in-test solve exceeds
  240s). No skill edit can change it. This caps achievable reward around 0.6.
- Did not add pdf/xlsx skill packages (refuted by cand_0002's rejection; passing office
  tasks already succeed without them).

## Process & features used
- Serial (single agent). Small diagnosis surface (1 addressable failure). Read all 10
  trajectory ctrf metadata + the exact test_content assertion + the t9 task prompt + all
  prior diffs/journal. No subagents needed.
