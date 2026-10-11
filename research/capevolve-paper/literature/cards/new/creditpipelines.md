# creditpipelines (SHORT, extra find)
- Title: The Harness as the Only Mutable Surface: Compliance-Bounded Self-Evolution of LLM Agents in Credit Pipelines, with a Measured Admission Gate
- Author: Ravil Akhtyamov (Digital Economy Lab; single author). arXiv 2610.10629 v1; 2026-10-07. Venue: none.
- Surface: instruction text, tool-call logic, typed primitives (harness only); dual loop (local edit one primitive / global replace primitives) with one admission gate writing a hash-chained record.
- Evaluation: SIMULATION only (simulated agent, seeded-search proposer, no LLMs); 3 shift families x 3 severities x 10 seeds; gate admitted 144 of 7,449 candidates, none worsened held-out error; ungated "recent traces" check admitted 309 harmful changes (abstract p.1).
- RELEVANCE: LOW. Admission-gate accounting (7,449 proposed vs 144 admitted) is a nice example of reporting rejected search; no LLM evidence. Weakly relevant to (d).
