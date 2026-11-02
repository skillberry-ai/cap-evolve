# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

## Iteration cand_0001 (run so far)
- Strategy: three parallel read-only diagnosis subagents (no-output, wrong-values, flaky-diff), then one merged candidate combining prompt contract + new helper module. No prior LEDGER rows to cite.
- Key process finding: the single biggest score leak (13 tasks, ~27 trials of hard zeros) was NOT a spreadsheet-skill failure at all but a response-format failure (native tool-call syntax instead of a fenced python block). The failure summary's "code never wrote output_path" label hid it; only reading traces revealed it. Always read traces for "no output" tasks before assuming a capability gap.
- Local validation trick: the run's venv (venv_k02) has openpyxl/pandas even though the default python does not — helper scripts can be genuinely executed before shipping. The self-check caught a real bug (_resolve_sheet returning a sheet name string).
- What to try next: check whether the format contract moved cluster A; if the gate accepts, keep the contract verbatim in any future prompt rewrite.

## Iteration cand_0002
- Strategy: minimal-diff rebuild after cand_0001's total collapse (LEDGER row 1: reject, val 0.000). One hypothesis for the collapse — the special-token tool-call string quoted as a "counterexample" poisoning the reader's generation — is unfalsifiable from the artifacts I have, which itself is the key process finding: see FRAMEWORK_IMPROVEMENTS. Shipped: positive-only format contract, save-discipline rules, optional self-checked verify.py.
- Lever discipline learned: when a prior RESULT is a catastrophic rejection with the whole batch reverted and the mechanism unknowable, the next candidate should change ONE dimension at a time (this one changes prompt-contract + optional script but no mandatory workflow, no special tokens, no rewrite of seed rules). If this too collapses, the next step is single-edit candidates to bisect.
- What to try next: per-trace reading of the judgment-value failures (247-24, 118-50, 47766, 82-30, 402-43) — the last big cluster with no code or rule coverage yet.

## Iteration cand_0003
- Strategy: single-surface bisect. Evidence: cand_0001 and cand_0002 (LEDGER rows 1-2) both
  rejected at val=0.000 with byte-identical broke/unresolved sets across 51 tasks —
  content-independent outcomes, i.e. the evals never ran the candidates (validation
  failure or all-errored infra). Shipped prompt.md-only (format contract + write/verify
  discipline), touching no other surface.
- Process finding: when two different candidates produce IDENTICAL per-task gate stats,
  stop reasoning about their content — the information is in the identity, not the edits.
  Bisect the surfaces (prompt -> skill-package -> task_template) one per iteration until
  one survives.
- What to try next: see JOURNAL cand_0003 "Focus next iteration".

## Iteration cand_0004
- Strategy: keep cand_0003's accepted prompt surface and extend it (fill-discipline rules from a 3-subagent diagnosis of all 17 failing/flaky tasks), while deliberately re-testing the scripts surface that both 0.000-rejected candidates carried — the acceptance of prompt-only cand_0003 means the gate itself works, so a script-bundling candidate is now a clean bisect of "scripts killed 0001/0002" vs "infra killed them".
- Diagnosis finding: across the 11 always-failing tasks, the scorer's most repeated signature is NOT wrong computation but WRONG SCOPE — cells blanked/overwritten that should keep their original input, writes past the answer range, silent None on unmatched lookups. That is enforceable in code (clamp + no-blank guard + saved-file verify), which is why sheet_ops.py exists.
- What to try next: see JOURNAL cand_0004 "Focus next iteration" — the 0.000-signature comparison is the key readout.

## Iteration 5 (cand_0005)
- What helped the search process: the single-surface bisect discipline — cross-comparing the LEDGER's rejection signatures (3/3 script-bundling candidates died at exactly val=0.000 with near-identical total-collapse broke sets; the one prompt-only candidate was accepted) decided the surface before any trace reading. Parallel read-only diagnosis subagents (4 groups over ~51 traces) produced the full cluster picture in ~3 minutes each.
- What stalled: nothing new this iteration; the code lever remains blocked by the undiagnosed scripts-surface death.
- What to try next: a dedicated script-only bisect candidate (one minimal helper, lint-conservative, prompt untouched) to determine whether the scripts surface can ever be scored in this run — it unlocks the highest-leverage lever (deterministic verify/write helpers) for the procedural clusters.
