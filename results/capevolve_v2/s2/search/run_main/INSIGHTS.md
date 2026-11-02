# INSIGHTS — summarized, verified findings (accumulate across the whole run)

The JOURNAL is your per-iteration diary; THIS file is the distilled, VERIFIED takeaway a future iteration should read instead of re-reading the whole journal or old sessions/traces. Update it whenever you have a genuinely NEW, confirmed finding (an accepted/rejected RESULT counts as confirmation; a guess does not) — not every iteration needs a new entry. Structure each addition as:

    ## <task or mechanism name>
    - What worked (confirmed by a RESULT, cite the candidate id):
    - What didn't (confirmed by a RESULT, cite the candidate id):
    - Promising but not yet tried:

## cand_0001 (iteration 1, result pending)
- Largest single zero-score cluster was NOT spreadsheet skill: ~11 tasks died because the model
  replied in <|tool_call> markup instead of a fenced ```python block and the harness executed
  nothing ("never wrote output_path"). The wrapped code was often complete and correct. (Pending
  gate confirmation that a prompt-side format contract can move a trained-in decoding habit.)
- Second largest: degenerate loops — code with no print() gets "[Code executed successfully with
  no output]", and the model then resubmits byte-identical code for all 30 rounds. Passing trials
  always had inspect -> targeted write -> comparative-verify; failing trials skipped one.
- pandas df.to_excel() whole-workbook rewrites caused type coercion (int->float, #N/A->blank) and
  lost formats on 3-4 tasks; openpyxl in-place editing is the majority pattern among passers.
- answer_position strings have quoting quirks ('Main!'A2:M70, Sheet1'!A1:F14) that break naive
  parsing; a tolerant parser + sheet resolver is worth having as a helper.
- Several "flaky" tasks are infra timeouts in disguise (80-42, 39931 and one trial each of
  50916/54638/55965) — check rollout.error before diagnosing behavior.

## cand_0002 (iteration 2, result pending)
- cand_0001's rejection (val exactly 0.000, fixed={}) is most consistent with a MECHANICAL failure
  (placeholder break or lint/smoke failure), not behavior: no prompt edit zeros all 120 tasks while
  ~41 previously-passing tasks reportedly stayed passing. Its stored diff.patch is truncated at 90
  lines, so the cause is not recoverable — treat whole-file rewrites of prompt.md/task_template.md
  as high-risk and verify placeholders programmatically after every edit.
- Flaky-task diagnosis method that worked: diff the FAILING trial against a PASSING trial of the
  same task. In 8/9 flaky failures the difference was a single procedural choice (strftime vs
  datetime; header=False rewrite after a correct write; anchors at I2 vs I3; '+' separator invented;
  to_excel placeholder headers). The passer's procedure, stated as a general rule, is the fix.
- Cross-cutting flaky pattern: the agent's own verification print often DISPLAYED the wrong value
  ('2023-06-30', 'Unnamed: 3', headers in row 2) without triggering a fix — verification without
  comparison-to-intent is decoration. Rules must say "read what it prints; wrong type/cell = failure".
- 402-43/267-18: the most expensive flaky failure mode is DAMAGING an already-correct file by
  re-writing it with different options. "STOP when verification passes" is a load-bearing rule.

## cand_0004 diagnosis (mechanism findings; behavioral effect pending gate)
- CONFIRMED root cause for two always-fail formula tasks (42354, 56563) and one flaky (48365):
  openpyxl stores formula strings verbatim, and Excel requires post-2007 functions (IFNA, AGGREGATE,
  XLOOKUP, ...) to carry a `_xlfn.` prefix in XLSX. Bare names recalculate to #NAME? under the
  scorer's LibreOffice pass — the agent's logic was CORRECT, the delivery mechanism was fatal.
  Also under this cluster: quoted-number criteria ("5551234" vs a numeric column → never matches,
  58484) and array-criteria SUMIFS(…,C11:C13) → error string (48365 t1).
- CONFIRMED: pd.read_excel round-trip freezes formula results at pre-edit values (247-24: changing
  Bill Rate then saving pandas-parsed literals left 12 dependent cells stale — "number LOWER than
  expected" with identical coverage). Edit in place with openpyxl instead.
- CONFIRMED: blank-vs-zero semantics decide pass/fail in both directions — lookup over a blank source
  cell yields 0 (48983: 35 cells written None where gold has 0), while ambiguous "fill N/A" wording
  must stay EMPTY (58949: 20 'N/A' texts where gold is blank). Excel treats blanks as 0 in
  comparisons (45372: blank Time cell → "before 09:45" branch, not a blank output).
- CONFIRMED flaky-fix lever: on 59595/53647/54144 the passing vs failing trial of the SAME task
  differed only in boundary/operand semantics (inclusive vs exclusive date window; numerator/denominator
  order; header parse). Pre-filled sample cells inside the target range pin the convention — the
  agent never used them as a check. Rule: recompute sample rows first, require exact agreement.
- The agent's own verification often PRINTS the wrong state and it finishes anyway (48983 printed
  7/42 filled; 54144 t2 printed all zeros and saved). Verification without reading-and-reacting is
  decoration — hence a verify_output helper whose output is explicit flagged warnings.
- cand_0003 RESULT (accepted +0.133) validated: verbal (no literal fences) reply-format contract +
  additive discipline rules. The optimizer machine lacks openpyxl — module-level `import openpyxl`
  in a bundled script is a plausible mechanical-zero cause for cand_0001/0002; sheetkit now imports
  it lazily inside every function.

## cand_0005 (text-only reship of the cand_0004 semantics, result pending gate)
- cand_0004's mechanical 0.000 despite lazy imports and defensive packaging strengthens the
  bisection: 3/3 script-bearing batches died at exactly 0.000; 1/1 text-only batch was accepted.
  With ~1 eval of rollout budget left, the script surface is effectively fenced off for this run.
- Fresh trace findings folded into rules (confirmed at mechanism level, behavioral effect pending):
  (a) agents "verify" formulas by re-reading the STRING (42354/56563/58484) — verification must be
  defined as comparing evaluated values; (b) the sibling example column pins output GRANULARITY
  (43436: counts incl. a 2 in a column the agent filled with 0/1 flags) — extend the sample-cells
  rule beyond answer_position to the neighboring completed column of the same block; (c) "from X to
  Y" windows are inclusive of both endpoints (59595 t0 vs t2); (d) "X per Y" = X/Y (53647);
  (e) exact-character prefix edits — no embellishment (267-18 t1 vs t2).
- 433-47 classified UNDECIDABLE (residual sign + distribution rule absent from the instruction);
  both readings are defensible, so any prompt rule is a coin flip that risks the mirror-image
  reading. Do not spend an edit on it.
