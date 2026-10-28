# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

<!-- cap-evolve:insights-append-below -->

## Judge-parity validator as the primary lever (confirmed)
- What worked (cand_0001 RESULT: ACCEPT, Δ+0.064, fixed case-015, broke nothing): converting mechanically-decidable contract rules into bundled-validator checks wired as a precondition of `decompose_complete` + review Step 1.7 + revise playbook. The gate accepted with zero regressions — corpus-verified no-op on passing trials is the safety mechanism.
- What didn't: nothing refuted yet; but the LLM-judgment clusters (redundant HLRs, soft AC) needed worked-example prose at the decision point, and case-020 t0 shows a worked example scoped too narrowly (schedule-only) misses sibling patterns (availability preconditions) — enumerate the CLASS, not one instance.
- Promising but not yet tried: extending the validator to the mandated-AC rules (24/25) once that judge leaves its thresholdless staging (B9) and becomes REAL.

## Per-trial reward decomposition (confirmed method)
- What worked (cand_0001's diagnosis + this iteration's): reward = (dq−1)/4 − 0.1·softgates per trial; extracting `score.raw.quality` + `score.raw.soft_failed` from every trajectory JSON pinpoints the exact failing trial and judge in one scripted pass — cheaper and more precise than reading feedback prose. This iteration: exactly 3 imperfect trials of 33, each a different cluster.
- What didn't: n/a.

## The review→revise phase machine decides where review-side fixes must fire (confirmed by trace analysis)
- The first REVISE pass is UNCONDITIONAL and fixes every `issues` list entry, minor or major; a further revise runs only if the RE-REVIEW fails. Consequence (case-020 t0): a defect the FIRST review accepts (or flags only at re-review) survives as a passing-review minor. Review-side checks must be calibrated to fire at the FIRST review — and minor severity is sufficient there; major only zeroes criteria on borderline cases for no extra fix.
- What didn't: assuming the reviewer will apply a stated rule — the case-013 t0 review ENUMERATED Rule 10 and then invented two exemptions ("not the same component's general implementation", "package contents ≠ image digest"). LLM reviewers rationalize; only a non-zero validator exit is immune. Close loopholes by naming the exact rationalization and denying it, and add the symmetric rule (don't demand the edge back) to prevent validator/review oscillation.

## Grading facts worth remembering
- dq is an LLM grade where ONE misfiled soft AC or ONE declared-expectation miss = 4/5 (−0.25 reward): "one minor gap" is the grader's stated 4-definition. Both observed 4s (case-014 t1 architecture_claims, case-020 t0 availability AC) were annotation-declared expectations.
- implementation_type_rules is mechanical and admits NO justification: any direct edge between konflux-onboarding and general (either direction, any component) fails, while the dq grader may simultaneously PRAISE the edge as a genuine artifact dependency (case-013 t0 did). When the two judges disagree, the mechanical one wins on expectation — always satisfy it.
- The dq grader PRAISES the no-edge + AC-gate konflux∥general shape (case-020 all trials) — removing an illegal edge does not cost dq points.

