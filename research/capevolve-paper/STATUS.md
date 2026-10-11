# Campaign status (plain language)

_Last updated: 2026-10-11 ~05:00 UTC — coordinator_

## What is known (evidence-backed)
- **Historical SpreadsheetBench gains are largely scorer compliance.** The reward reads workbooks as saved (no recalculation). Re-scored with recalculation, Gemma's historical gain shrinks from +33.0 to +18.7 points and GPT-5.5's from +49.1 to about +10 (`audit/historical_results.md`, #767).
- **Gold answers are visible inside the agent sandbox** (#782, critical). The historical trajectory scan is running; an isolation patch PR is in progress.
- **Every task set used before is development-exposed**: SpreadsheetBench verified test-280, tau2 airline test-20 and all 87 SkillsBench tasks (#769). The confirmatory evaluation needs fresh tasks.
- **Default gate behaviour inflates acceptances** (simulation on the real code, `analysis/out/`):
  - The one-SE gate accepts at least one null edit in 54–58 % of 10-iteration searches.
  - Footprint masking (on by default) accepts a truly harmful edit 84 % of the time when its regressions fall outside the footprint.
  - Dropping errored trials turns null edits into 52–89 % acceptances.
  - Filed as #755–#766.
- **The prior-art screen leaves only narrow claims.** No broad feature-level novelty claim survives; the novelty matrix covers 71 papers. Six narrow hypotheses remain (`literature/novelty_matrix.md`).
- **Local execution works.** SpreadsheetBench and tau2 run on this host. The campaign gateway meters every call. One Gemma SpreadsheetBench rollout costs about 41k tokens and about 3 minutes.

## What is uncertain
- Whether any historical rollout actually read gold files.
- Whether official GEPA and SkillOpt can be run on matched terms.
- Which fresh final set to use for each suite.
- **The budget.** The 100M-token cap funds roughly 2,000 target rollouts in total, so the full 24-search matrix does not fit (see decisions.md).

## Running now
- PR #779 (paper-mode gate switches) is under independent review.
- Gold-isolation PR (bench-steward).
- Gold-access trajectory scan and fresh-test exposure checks (provenance-auditor).
- Title verification of every citation (lit-lead).
- Official GEPA and SkillOpt adapters (baseline-eng).

## Next
- Freeze the in-cap protocol and run the scorer-compliance diagnostic (seed vs one-line "write values" instruction vs historical champion, both scorers).
- Dev pilots for hill-climb, agent-optimize, GEPA and SkillOpt.
