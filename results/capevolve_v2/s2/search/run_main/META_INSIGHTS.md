# META-INSIGHTS — about the optimization PROCESS itself (this run)

Not about the capability — about HOW this run is searching for it: which strategies/edit classes/algorithms are helping vs stalling, and what to try next iteration. Update at the end of the run at minimum; sooner if a plateau or a clear strategy shift is worth recording now. Structure each addition as:

    ## Iteration <id> (or 'run so far')
    - Strategy tried, and whether it moved val (cite LEDGER rows):
    - Plateau/stall signal, if any, and the lever switched to:
    - What to try next iteration:

## cand_0001 (iteration 1)
- Reading trajectories programmatically first (grep for the harness's "No python code block was
  found" string, count messages per episode) found the biggest cluster in minutes — before any
  semantic reading. Do the mechanical scan first every iteration.
- Three parallel read-only diagnosis subagents (value-mismatch / flaky-variance / loop groups)
  worked well and merged cleanly into one candidate; keep this fan-out shape.
- The trace's `score.raw`/feedback strings plus rollout.error are enough to triage infra-vs-
  behavioral without opening files; 7 of 31 "failures" were pure infra noise.

## Iteration cand_0002
- cand_0001's catastrophic 0.000 (LEDGER row 1) taught the run's first process lesson: a candidate
  can die mechanically (placeholder/lint), and the framework gives no error message for it — the
  rejected diff is even truncated, so the cause is unfindable. Countermeasure adopted this
  iteration: additive-only edits to prompt/task_template, programmatic placeholder verification,
  and script testing under the actual run venv before shipping. Keep this checklist every iteration.
- Pass-vs-fail trial diffing within one flaky task is the highest-yield diagnosis move so far: it
  isolates the exact procedural difference and simultaneously supplies the general rule (the
  passer's procedure) and the safety argument (passers already follow it).

## cand_0003 (iteration 3)
- Two consecutive val=0.000 rejections with identical full-val "broke" sets are almost certainly
  MECHANICAL (structural candidate invalidity), not behavioral — no prompt edit zeros 120 tasks.
  When the gate reports val=0.000, treat it as "candidate never ran", not "candidate regressed".
- Correct response: BISECT the structural surface. Ship the smallest safe subset of edits (here:
  additive text to prompt.md/task_template.md, verified placeholders, no new files, no scripts,
  no literal fences) and re-add the dropped elements one per iteration until the killer is found.
  Full-batch retries after a mechanical zero burn iterations without producing information.
- Framework gap (also in FRAMEWORK_IMPROVEMENTS.md): the gate gives no reason string for
  mechanical rejections — rejected.jsonl/diff truncation hides which check failed.

## cand_0004
- The two mechanical 0.000 rejections (cand_0001/0002) consumed 2 of 4 iterations with zero signal.
  What finally produced signal: cand_0003's deliberate single-element bisection (text-only). Keep
  bisection discipline — add ONE structural element per iteration after a mechanical zero, and
  verify every mechanical precondition locally (placeholders, braces, fences, module import in an
  openpyxl-less env) before shipping.
- Parallel read-only diagnosis subagents (one per trajectory group) recovered full root-cause detail
  on 17 tasks in ~3 minutes of wall time — cheap and high-fidelity. The flaky-task diff method
  (passing trial vs failing trial of the SAME task) remains the highest-yield diagnostic.
- Environment observation worth remembering: the optimizer box has no openpyxl and no network, so
  helper code can only be tested against a hand-stubbed openpyxl — the stub found one real bug
  (hasattr(str, 'title') is True) that reading alone missed. Stub-testing new helpers is worth the
  10 minutes.

## Iteration cand_0005
- Strategy: with 83% of rollout budget spent (≈ one full eval left), optimize for
  probability-of-a-real-gain, not information gain — ship the VALIDATED surface (additive text)
  carrying the fully-diagnosed rule set, and refuse the script surface that produced three
  mechanical zeros. When budget is nearly exhausted, bisection for its own sake is negative-EV.
- The 3-subagent fan-out (formula/coverage group, semantic group, flaky pass-vs-fail group) again
  produced a complete per-task root-cause table in ~3 minutes; the flaky pass-vs-fail diff remains
  the single highest-yield diagnostic (it supplied the rule AND the safety argument).
- cand_0004's text rules were recoverable despite its rejection: a mechanical 0.000 means behavior
  was never measured, so the text portion was safe to reship minus the reverted-script references.
