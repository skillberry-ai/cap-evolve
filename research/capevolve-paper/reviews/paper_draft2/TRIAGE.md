# Draft 2 review triage (coordinator, 2026-10-11 22:50 UTC)

Five fresh independent reviews (R1 to R5) plus a verification of the draft-1 issues (VERIFY_draft1_issues.md; pending).

## S. Story: the crux (coordinator decision, R5 and R1)
The paper is a measurement study, not a method paper. One crux:
"Measured on held-out tasks at a matched rollout budget, with gold isolated and one error classifier, how much do frozen-weight agent optimizers actually gain, and what does the acceptance gate cost or buy?"
- Working title (author to confirm): "What Do Agent Optimizers Gain When Measured Carefully? An Audit and a Matched Comparison of Ten Optimizers".
- Contribution order:
  - (1) an audit showing that a deployed optimizer's historical gains were inflated, with the decomposition stated per model (Gemma: 43% of the reported gain was scorer compliance; GPT-5.5: 80%; use the exact computed values, never "most" without a number);
  - (2) the measurement protocol (gold isolation, uniform error classifier, matched B*, pre-registered families, interleaved final window);
  - (3) the matched comparison using official repositories;
  - (4) the gate trade-off: rule P vs stock gate on Suites A and C (E12A, E12C) as a finding, not a footnote.
- CapEvolve is "the optimizer we audited and also the system we ran". Never call it "widely used".
- Every section must serve this crux. Cut Sec 5.5 (it duplicates Sec 2) and most of Sec 6.

## G. Gate inertness (R1 R2 R4; decided 22:40)
- Frame CapEvolve+rule P as a deliberately conservative configuration. Report promotions per search for every arm (analysis plan 5M).
- E12A (Suite A, stock gate, launching) and E12C (Suite C) show the other side.
- Equivalence rule (TOST, pre-specified margin) from 5M. Use "inconclusive" otherwise.
- The abstract and conclusion must not frame the paper as answering "which optimizer is best". Claims are artifact-level.

## O. Over-claims and contradictions (R1 R2 R4 R5)
- Remove "final sets that search never uses", "fresh final sets" and "removes each problem". State each suite's exposure exactly (A score-only exposed, B sealed, C development-exposed), consistently in Sec 3.4, 4.1 and 5.6.
- Proposer isolation: state per arm what was isolated. Suite B agent-optimize had residual opt/sel gold visibility (disclosed in decisions.md), so "negative test for every proposer" must be qualified per arm.
- Absence-of-evidence scans: describe them as scans with stated coverage, not as proof. Say so in limitations.
- "Nine competitors": give exact counts per suite (A 8 plus 2 stock-gate/controls, B: GEPA plus HarnessLens, C: GEPA).
- The +33.0 to +18.7 decomposition: separate the estimator change (pooled vs paired) from the scorer change, or use one estimator throughout.
- Rule P headline: the false-promotion figure is per search under trial noise. Also state the same-split adaptivity caveat (D_opt = D_sel for CapEvolve), and compare against the stock gate rather than a strawman.

## F. Fairness disclosures (R2 R4)
- Add an appendix table of competitor adapter deviations from decisions.md (one row per arm: change, reason, expected direction).
- Hang rule per suite: the appendix says it is shared, while decisions.md records a Suite B difference. Make the text match the logs and state the difference.
- Pre-13:11 infra zeros stayed in competitor search histories (search-time feedback, native handling), while CapEvolve dropped errored trials. State this asymmetry explicitly.

## N. Numbers and consistency (R1 R2 R3 R5)
- Final sizes are pinned (decisions 22:30): A 70x1 (seed x2), B 40x3, C 20x3. Every table and text must use them (mock T macros included).
- Mock B* values must be multiples of 50 and realistic (about 250 to 400).
- One simulation setup is quoted in the body (10 candidates, the real task counts); others go only in the appendix, labelled.
- Table 10 expected gain: explain the trade (rule P gives up expected gain for a 5 to 10x lower false-promotion rate).
- 5.4's 0.41/0.54 vs Table 10: reconcile from one macro source.
- Table 2 vs Table 3: there is no one-shot control on Suite A. Remove the A row or explain it.
- Units: percentage points everywhere in the body text; fractions only in tables, stated in the caption.

## T. Terms (R3 R5)
- Rename the budget symbol so "B" is not overloaded with Suite B (e.g., N for the rollout budget, N* for the matched checkpoint), or call the suites "Spreadsheet", "Retail", "Airline".
- Use k_se consistently. Define opt/sel/val once in a table.
- Define digest, footprint and judge at first use, or remove them from the body.
- Define seed artifact / baseline / arm / HC / AO once.

## V. Figures (R3 R5)
- tau renders as "¿" (font encoding). Fig 6 log axis has one tick. Fig 8 legend has undefined variants. Fig 2 row order must match Table 3.
- Fig 1 text is tiny. Fig 5 must state its y-axis set. Fig 6 has a clipped label. Figs 7 and 9 need consistent fonts and legends.

## Owners
- paper-core: S, G (text), O, F (text), N (text), T.
- paper-results: G (promotion-count table, mock), F (deviation table from decisions.md), N (tables and mocks), V.
- paper-lit: check the new title and contributions against the literature for novelty overlap. Verify any new cites.
- stats-reviewer: amendment 5M (in progress), plus the rule-P same-split adaptivity caveat in one sentence for the paper.
