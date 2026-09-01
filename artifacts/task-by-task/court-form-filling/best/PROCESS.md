# PROCESS — what I did this iteration (explainability; REQUIRED)

Champion is the **seed** (val 0.300). cand_0001's whole batch was REVERTED (rejected, val 0.100).
The seed's 10 trials: t3,t6,t9 pass; t7 = infra timeout (noise, ignored); t0,t1,t2,t4,t5,t8 fail.
All failures are in the **PDF form-filling path (forms.md)**; the fill pipeline itself works
(passing trials prove it). All misses are KNOWLEDGE gaps, so the lever is prose in `pdf/forms.md`.

## Ranked issue list (clusters by # failing trials × recoverable score, biggest first)
| rank | cluster | trials | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Checkbox omission | t1,t2,t4 | Leaves REQUIRED yes/no questions (Q7 attorney-fee, Q8 public-entity, Q9, Q10) blank instead of checking "No" — over-applies "leave unmentioned fields empty" | KNOWLEDGE/BEHAVIORAL | BODY (forms.md) |
| 2 | Empty-field violation | t0,t2 | Fills page-1 court/clerk fields (`CaseName`="Joyce He vs. Zhi Chen", `CourtInfo`="Santa Clara") that the court fills | KNOWLEDGE | BODY (forms.md) |
| 3 | Content missing (verbatim) | t5,t8 | Reformats verbatim data — wrote phone `(412) 588-6066` but verifier requires exact `4125886066` | KNOWLEDGE | BODY (forms.md) |
| 4 | Wasted turn / timeout risk | all | `python scripts/check_fillable_fields` → exit-127 (`python` absent; also missing `.py`) | CAPABILITY-GAP (bug) | BODY (forms.md) |

Why prose, not a script: a script cannot decide "the answer is No" (cluster 1) or "don't reformat"
(cluster 3) without hardcoding the task's answers (overfitting). An auto-"answer every checkbox"
script would risk the `TestUncheckedCheckboxes` assertions (Checkbox11/14 & filing-options 5b-e must
stay unchecked). So each fix is a general FACT/criterion the agent cannot derive — exactly the
carve-out for prose. The mechanical fill (`fill_fillable_fields.py`) already works and is untouched.

## Changes made this iteration (all in `pdf/forms.md`, additive)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY | pdf/forms.md | Rule: answer every required yes/no (either-or) question; if facts don't support Yes, the answer is No — check the No option; never leave both options unset. Parenthetical: optional/"if yes" sub-boxes stay unchecked. Generalizes to any form's mandatory either-or fields. | t3,t6,t9 already answer all yes/no → no change. Parenthetical protects the "must stay unchecked" boxes. |
| 2 | BODY | pdf/forms.md | Rule: leave court-use/administrative fields blank (case number, case name/caption, court name/address, trial date/time/dept, clerk signature) and a non-existent second party's fields. General category, not task literals. | Passing runs already leave these blank → no change. |
| 3 | BODY | pdf/forms.md | Rule: copy data verbatim; do not reformat phones/IDs/amounts; apply a format only when the request asks (e.g. dates). Neutral example (`5551234567`), no task value. | Passing runs already enter verbatim → no change. |
| 4 | BODY | pdf/forms.md | Fix first command to `python3 scripts/check_fillable_fields.py`; one-line note "run every script with `python3`". Removes a guaranteed exit-127 (seen in every trace) → fewer wasted turns / timeout risk. | Pure correctness; agents already work around it, so behavior only improves. |

## Verify-the-fix (VERIFIED by running the real verifier on a guidance-conformant fill)
- Built `/tmp/fv.json` following the NEW rules (verbatim phones/amount, all 6 required yes/no answered
  — Q4/5a=/1, Q7/8/9/10=/2, court/second-party fields omitted), ran the deployed
  `pdf/scripts/fill_fillable_fields.py` on the real `sc100-blank.pdf`, then ran the task's actual
  `verifier/test_outputs.py`:
  - **TestCheckboxes: 6/6 PASSED** (cluster 1). **TestUncheckedCheckboxes: 6/6 PASSED** (guidance does
    NOT over-check — blast radius on unchecked boxes confirmed safe). **TestEmptyFields: 20/20 PASSED**
    (cluster 2). = 32 passed.
  - Content tests only ERRORED on missing `pdftotext` binary locally (infra, not content). Cluster 3
    corroborated directly: filled PDF stores `PlaintiffPhone1[0] -> '4125886066'` verbatim (the exact
    substring the content test requires); trace evidence shows reformatted `(412) 588-6066` is why
    t5/t8 failed and verbatim entry is why t3/t6/t9 passed.
- Interpreter fix: t4 trace shows `Exit code 127 /bin/bash: line 1: python: command not found`; the very
  next call used `python3` and succeeded → `python3` is present in the sandbox.

## Process & features used
- Serial (single skill, single failing task, huge but few trajectories) — subagents unnecessary;
  diagnosed all 6 real failing trials directly by extracting each run's `field_values.json` +
  checkbox assignments from the traces, and read the task's oracle + verifier to get ground truth.
- Read from ./prior_iterations/cand_0001 + JOURNAL + LEDGER: cand_0001 added `/TU` labels + a mandatory
  review loop + **"fill only the fields you have data for … leave every other field out"** — that last
  rule is the OPPOSITE of the cluster-1 fix (it tells the agent to omit unmentioned fields, worsening
  the dominant checkbox-omission failure) and the whole batch regressed 0.300→0.100. I did NOT re-add
  labels, the review loop, or the "fill only fields you have data for" rule.

## Good things to PRESERVE
- Do NOT re-introduce "fill only the fields you have data for / leave every other field out" — it
  directly causes cluster 1 (required yes/no left blank). The correct framing: required either-or
  questions get a definite "No", not a blank.
- The three value rules above (verbatim / answer-required-yes-no / leave-court-fields-blank) target all
  6 real failing trials; keep them.

## Deliberately skipped
- t7: infra timeout (explicitly "do not optimize against it").
- A checkbox-grouping "answer every either-or" SCRIPT: too risky — fragile grouping would false-positive
  on optional/multi-option boxes and could flip the `TestUncheckedCheckboxes` assertions. Prose lets the
  agent reason which questions are genuinely mandatory.
- Did not touch SKILL.md, reference.md, or any script body (pipeline works; changing it is unnecessary
  blast radius).
