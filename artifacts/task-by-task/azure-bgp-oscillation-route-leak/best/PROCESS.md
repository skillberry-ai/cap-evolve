# PROCESS — what I did this iteration (explainability; REQUIRED)

Note: the single deployed skill in this candidate is `azure-bgp/` (the office-doc template
text in INSTRUCTIONS.md is generic; the real editable artifact is `azure-bgp/SKILL.md`).

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | RPKI mis-classification | azure-bgp (10/10 seeds t0–t9) | Agent classifies "Enable RPKI origin validation…" as `route_leak_resolved=False`, reasoning that since the origin ASN (65007) is legitimately authorized RPKI would not catch this leak. Ground truth = `(oscillation_resolved=False, route_leak_resolved=True)`. Skill mentioned RPKI as a Tier-2 leak fix but not emphatically enough to stop the agent overriding it. This is the ONLY wrong classification in every seed (18/19 correct). | KNOWLEDGE (classification criterion) | BODY (additive, RPKI-scoped) |

Diagnosis method: parsed all 10 trajectory outputs, extracted each `oscillation_report.json`,
diffed every solution's `(oscillation_resolved, route_leak_resolved)` against the verifier's
`SOLUTION_EXPECTATIONS`. Only the RPKI solution was wrong — identically in all 10 seeds.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| RPKI mis-classification | BODY | `azure-bgp/SKILL.md` (Tier-2 RPKI bullet) | Rewrote the RPKI bullet to state its classification explicitly: origin/route-validation control → `route_leak_resolved=true`, `oscillation_resolved=false`, and "classify by control class, not by whether this scenario's origin is legitimate." Generalizes as a mechanism-class fact (RPKI = leak-mitigation control), not a task literal. | Yes — text mentions only RPKI/origin-validation, so it cannot alter the other 18 (correct) classifications. |
| RPKI mis-classification | BODY | `azure-bgp/SKILL.md` (Common Pitfalls) | Added a pitfall bullet naming the exact wrong reasoning ("RPKI is ineffective when the origin is already legitimate") and the correct classification. Catches the trap where the agent looks for pitfalls. | Yes — RPKI-scoped only. |

## Verify-the-fix
- `TestSolutionEvaluation::test_solution_classification[Enable RPKI origin validation…]`:
  trace shows agent output `route_leak_resolved=False` (its message: "RPKI … origin is
  legitimately 65007, so it wouldn't reject this leak"). Verifier expects `True`. The new
  RPKI bullet + pitfall both state `route_leak_resolved=true` and explicitly forbid the
  "origin is legitimate → ineffective" override, so the agent should now emit `True`. This
  was the sole failing assertion across all 10 seeds → fixing it should flip the task.
- Blast radius: the edits reference ONLY RPKI/origin-validation. The other 18 classifications
  (all already correct, including the subtle osc-only export filter #12 vs leak-only export
  block #14) are untouched — I deliberately did NOT add a broad rubric that could confuse them.

## Process & features used
- Serial (single tightly-isolated cluster); no subagents needed — diagnosis by scripted diff
  of all 10 trajectories against the verifier answer key was decisive.
- Prior iterations: none (this is the seed; RUNMAP/LEDGER/JOURNAL empty of results).

## Good things to PRESERVE
- The 18 currently-correct classifications and the existing Tier-1/2/3 fix taxonomy — do NOT
  replace with a generic mechanism→category rubric; the subtle export-filter distinctions
  (osc-only vs leak-only) are already right and a broad table risks regressing them.

## Deliberately skipped
- No other cluster exists — 18/19 classifications and all detection tests already pass in
  every seed. Adding speculative edits would only risk regression, so none were made.
