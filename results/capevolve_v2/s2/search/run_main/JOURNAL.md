# JOURNAL — optimizer handover (append-only, whole run)

YOU (the optimizer) own this file. It is the running, accumulating handover across ALL iterations — accepted AND rejected — and it is NEVER reset. Each iteration you APPEND one new entry at the bottom (under the marker line); you do NOT edit or delete earlier entries. Read the whole journal before proposing, so you build on EVERY prior attempt (not just the last accepted one) and never re-test a refuted idea.

You CANNOT know your own gate result while you write — the harness scores you AFTER you stop and stamps a **RESULT** line (outcome + Δ + the tasks you measurably broke/fixed, plus the ones whose move was too small to resolve) right below your entry. So do NOT write 'what worked' as a guess. To learn what actually worked, READ the framework RESULT lines of prior entries (and LEDGER.md): an entry whose RESULT says `rejected` with `broke={...}` tells you which specific edits to drop or redesign — its diff.patch is in ./prior_iterations/<id>/.

Append your entry for THIS iteration below the marker, using this shape (INTENT only — the framework appends the RESULT):

    ## Iteration <your candidate id> — <one-line headline of what you tried>
    - Changes I made (1 line per edit; name the file/tool + cluster it targets):
    - Per change, the EXPECTED effect + why it's safe (which failing task it should fix;
      why no passing task changes behavior):
    - Building on prior RESULTS: which prior entries' broke/fixed I used, and what I
      did NOT re-try because a prior RESULT showed it regressed (cite ids):
    - Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test):
    - High-value clusters still NOT cracked (and the guard/tool designs already tried):
    - Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch
      to — e.g. a NEW composite tool instead of another guard, or prompt instead of code):
    - Cost-reduction opportunity (if `cost`/`latency`/`num_messages` is a declared objective,
      run `detect_loop_patterns.py --run-dir $R --tag $BEST --split val` — free, no extra
      eval — and check its `by_tool` map for a same-tool-called-N-times-in-a-row pattern. A
      hit names the exact tool + repeat count: propose a composite/bulk tool (capability
      `tools`), a bundled script entrypoint (`skills-package`), or upfront-batched
      instructions (`prompt`/`system-prompt`) that replace the N calls with one. No hit
      (or cost/latency not a declared objective): say so plainly, do not leave this blank):
    - Focus next iteration:

## Iteration cand_0001 — fix reply-format aborts + identical-resubmit loops; move load/locate/write/verify procedure into a sheetkit helper
- Changes I made:
  1. prompt.md + task_template.md: explicit reply-format contract with a literal ```python worked
     example (cluster A: ~11 always-fail tasks die emitting <|tool_call> markup that is never
     executed).
  2. prompt.md rules 9-10 + task_template rules: print-state-every-block, never-resubmit-identical,
     explicit "reply WITHOUT a code block to finish" (cluster B: 4 tasks burn all 30 rounds
     resubmitting byte-identical no-print code).
  3. NEW skills/spreadsheet-helpers/scripts/sheetkit.py: open_copy/save_workbook (in-place openpyxl
     edit, kills pandas to_excel rewrites), write_range/read_range (exact A1-range writes),
     parse_answer_position/resolve_sheet (handles 'Main!'A2:M70-style quirks), find_label (loud
     not-found), vlookup_first (Excel first-match), diff_ranges (verify vs reference sheet),
     verify_output (reopen + report answer range) — clusters C/D/E/H.
  4. skills/spreadsheet-helpers/SKILL.md rewritten to document every helper (when-to-call +
     examples); prompt.md workflow rules 1-8 cover inspect-before-write, openpyxl-over-pandas,
     stay-inside-answer_position, no placeholder writes, dates-as-datetime, instruction-anchor
     precedence, save-early, verify-by-diff — clusters C/F/G/I.
- Per change, EXPECTED effect + why safe:
  1. Format contract: 51-12/433-47/34033/45635/32023/3413/36097/46121/58484/56786/247-24 contained
     complete correct code inside the wrong wrapper — converting the wrapper to a fence converts
     0s to passes. Safe: passing tasks already emit fenced blocks only; the rule matches their
     behavior.
  2. Anti-loop rules: give the missing feedback discipline + terminal action; safe for passers who
     already verify and stop.
  3-4. Helpers + rules are the majority passing pattern (57/66 passers use openpyxl); verification
     is additive; all helpers raise actionable errors instead of no-op'ing. Softness clause added
     (agent may bypass a helper when it judges it hurts).
- Building on prior RESULTS: none (first iteration; LEDGER/JOURNAL/RUNMAP empty, no rejected.jsonl).
- Refuted hypotheses: none yet.
- High-value clusters NOT cracked: instruction-semantics judgment (11842 day-vs-half-day,
  43436 month-end boundary, 58109 inclusive reference date, 227-40 dedupe replace-vs-shift) — only
  a generic "pin the inclusion rule first" nudge; if the gate accepts this batch, next lever is a
  worked example of boundary-restatement in the prompt, NOT more helpers.
- Plateau signal: n/a (iteration 1).
- Cost-reduction opportunity: no cost/latency objective declared; not run. (Side observation: loop
  tasks burn 30 rounds each — the anti-loop rules should also cut rollout cost.)
- Focus next iteration: re-measure cluster A first — if format aborts persist, the fix must move
  into the harness (a `<|tool_call>`-to-fence translator), which is outside our surface; then
  cluster B residuals; then judgment-cluster prompt examples.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.709 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 1818, 192-22, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 32438, 325-44, 32612, 32902, 35742, 370-43, 37378, 379-36, 382-10} · unresolved={170-13, 267-18, 402-43, 42354, 46646, 47766, 48365, 48620, 493-18, 50916, 53647, 54638, 55965, 560-12, 56274, 56563, 59595, 66-24} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0001: rejected val=0.000 Δ=-0.709 -->

## Iteration cand_0002 — additive discipline rules + sheetkit helper; structurally defensive after cand_0001's 0.000
- Changes I made:
  1. prompt.md: REPLY FORMAT contract at primacy (entire reply = one plain ```python fence; other wrappers never executed) — cluster A (51-12/433-47/34033/45635 + 48365 flaky).
  2. prompt.md: working-discipline rules 1-9 (inspect-first + loud not-found; read in-workbook reference sheets; state expected shape; touch-only-asked / no to_excel rewrite / no coerce; right types + literal anchors + whole-formula rewrites; STOP when verification passes; print-every-block; never-resubmit-identical; verify-and-read-before-finish) — clusters B/D/F/G.
  3. task_template.md: fence clarification + anti-loop + verify-then-finish lines at recency — clusters A/B/E.
  4. NEW skills/spreadsheet-helpers/scripts/sheetkit.py: parse_answer_position (tolerant of 'Main!'A2:M70-style quirks), resolve_sheet, write_range (shape-checked exact-range), read_range, find_label (all-sheets scan, loud miss), verify_output (reopen saved file, report answer range + empties), self_check — clusters C/D/G/B.
  5. skills/spreadsheet-helpers/SKILL.md rewritten to document every helper (when-to-call + examples + typical flow); prompt.md points at the import.
- Per change, EXPECTED effect + why safe: (1) the failing replies contained complete correct code inside the wrapper — a fenced reply executes it; passers already emit pure fences. (2) each rule is the behavior of the PASSING trial of the same flaky task (66-24 t1 writes datetime; 402-43 t0 stops after correct write; 560-12 t0 anchors at I3) — so passing tasks keep their behavior while failing trials get the passer's procedure. (3) recency reinforcement of what the seed already said; placeholders verified programmatically. (4) turns 408-39's silent `if col_idx:` no-op into a loud error and makes verify/print mechanical; helpers are opt-in, purely additive to agents that don't call them. (5) SKILL.md is appended to the system prompt, so documentation reaches the agent without extra round-trips.
- Building on prior RESULTS: cand_0001 (only prior iteration) was REJECTED at val=0.000 with fixed={} — consistent with a MECHANICAL failure (broken placeholder or failed lint/smoke), since per-task behavior cannot zero 120 tasks at once. I did NOT re-try its wholesale prompt.md rewrite or its import-time self-check pattern; this candidate keeps every original prompt.md line (additive edits only), keeps both {skills_root} uses, verifies all 7 template placeholders programmatically, and ships a script that compiles, imports with zero side effects, and passes self_check under the run venv. The behavioral IDEAS from cand_0001 (format contract, anti-loop, helpers) are retained in redesigned, additive form per the gate's instruction to keep non-broke edits.
- Refuted hypotheses: none beyond cand_0001's batch-level rejection (cause unidentifiable — stored diff.patch is truncated at 90 lines; recording this as a framework gap).
- High-value clusters still NOT cracked: in-workbook reference extraction (82-30, 227-40) only gets a prompt rule — a general reference-locator helper is the next design; instruction-semantics judgment (118-50's pair-matching, 247-24's lookup semantics) remains judgmental.
- Plateau signal: n/a (second iteration; first was mechanically rejected, so no behavioral signal exists yet).
- Cost-reduction opportunity: no cost/latency objective declared; not run. (The anti-loop rules should cut the 30-round burn on 118-50/493-18/402-43/47766 pass trials.)
- Focus next iteration: if this batch is accepted, measure whether cluster A (format aborts) actually moved — if not, the fix likely needs harness-side translation and should be dropped; then build the reference-locator helper for cluster F.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.709 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 1818, 192-22, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 32438, 325-44, 32612, 32902, 35742, 370-43, 37378, 379-36, 382-10} · unresolved={170-13, 267-18, 402-43, 42354, 46646, 47766, 48365, 48620, 493-18, 50916, 53647, 54638, 55965, 560-12, 56274, 56563, 59595, 66-24} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0002: rejected val=0.000 Δ=-0.709 -->

## Iteration cand_0003 — mechanical-failure bisection: text-only additive edits to prompt.md + task_template.md (no scripts, no SKILL.md rewrite, no root DIAGNOSIS.json, no literal fences)
- Changes I made:
  1. prompt.md: REPLY FORMAT contract at primacy, described VERBALLY (no literal backticks): entire
     reply = one fenced python block, tool-call/XML/JSON wrappers never executed — cluster A
     (51-12/433-47/34033/45635, flaky 48365/47766).
  2. prompt.md: Working discipline rules 1-9 with softness clause (inspect-first + loud not-found,
     read in-workbook references, openpyxl in-place over pandas to_excel, touch only
     answer_position, proper types, instruction anchors override range shape, save-early,
     print-every-block + never-resubmit-identical, verify-reopen-before-finish) — clusters B/C/D/F/G
     (408-39, 118-50, 493-18, 402-43, 247-24, 82-30, 227-40, 66-24, 560-12).
  3. task_template.md: one recency reminder paragraph (fence shape verbally, print/anti-loop/save-
     early/verify) — clusters A/B/E. All 7 placeholders verified programmatically, no stray braces.
- Per change, EXPECTED effect + why safe: (1) failing replies contained complete code inside the
  wrong wrapper and the harness's mid-episode correction alone doesn't break format lock-in — the
  contract at primacy should prevent the FIRST tool-call-formatted reply; passers already emit pure
  fenced blocks so their behavior is unchanged. (2) each rule restates the behavior of the PASSING
  trial of the same flaky task, so passers keep behavior while failing trials get the passer's
  procedure. (3) recency reinforcement of rules the seed already implies; purely additive.
- Building on prior RESULTS: cand_0001 and cand_0002 BOTH rejected at val=0.000 with the whole val
  set broke — mechanical zero, not behavioral. Both shared: new script + SKILL.md rewrite + root
  DIAGNOSIS.json + literal ``` fences + text edits. I kept ONLY the text edits and dropped the
  other four elements to isolate the killer. I did NOT re-try: sheetkit script, SKILL.md rewrite,
  root DIAGNOSIS.json, literal fences (all shared suspects, not individually refuted — bisection,
  not abandonment).
- Refuted hypotheses: none new. cand_0001/0002's batch-level 0.000 refutes "ship script+SKILL+
  DIAGNOSIS+fences+text together" as a PACKAGE, cause unidentified (diffs stored truncated).
- High-value clusters NOT cracked: reply-format abort may be harness/model-template-bound (if this
  candidate's primacy contract still doesn't fix 51-12 etc., the fix is outside our surface — say
  so and stop spending edits on it); sheetkit-style helpers (write_range/verify_output/find_label)
  remain the strongest deferred lever for clusters C/D/G.
- Plateau signal: two consecutive mechanical 0.000s — no behavioral signal exists yet. This
  iteration IS the lever switch: minimal-surface bisection instead of full batches.
- Cost-reduction opportunity: no cost/latency objective declared; not run.
- Focus next iteration: if cand_0003 scores > 0 → killer was script/SKILL/DIAGNOSIS/fences; add
  back ONE element (sheetkit script with a --self-check CLI entry, since skill-package validate()
  runs scripts) and keep the text edits. If cand_0003 also zeros → suspect braces/fence wording in
  text; ship a near-no-op single-line prompt edit to pin the failure further.

> **RESULT (framework, measured):** ACCEPTED (new champion) · val=0.842 Δ=+0.133 · fixed={227-40, 3413, 36097, 39046, 408-39, 45635, 46121, 56427, 82-30} · broke={10747, 325-44, 52216, 58949, 7902, 80-42} · unresolved={170-13, 267-18, 402-43, 42354, 46646, 47766, 48620, 493-18, 50916, 53647, 54144, 54638, 55965, 560-12, 56274, 56563, 66-24} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them).
<!-- cand_0003: ACCEPTED val=0.842 Δ=+0.133 -->

## Iteration cand_0004 — bisection step 2: ship the sheetkit helper script (lazy openpyxl) + verify_output, plus semantics rules for blank-cells/_xlfn/stale-pandas/sample-answers
- Changes I made:
  1. NEW skills/spreadsheet-helpers/scripts/sheetkit.py — verify_output (reopen saved file; flag empty
     target cells, formula cells, placeholder texts, changed-from-init, uniform all-same value,
     empty-cells-in-data-rows), write_range/read_range (shape-checked exact-range), open_workbook
     (formulas preserved), save_workbook, parse_target (tolerant 'Main!'A2:M70-style refs),
     resolve_sheet (loud), find_label, data_extent, set_formula/fix_formula (_xlfn. auto-prefix for
     post-2007 functions), self_check — clusters 1/2/4 (9+ failing traces).
  2. skills/spreadsheet-helpers/SKILL.md rewritten to document every helper + Excel-semantics notes —
     cluster 1/3.
  3. prompt.md: extended prefer-literals bullet (LibreOffice recalc; _xlfn./#NAME?; quoted-number
     criteria; array-criteria → expand per criterion) + new discipline rules 10 (blank cell = 0:
     lookup blank→0 not None; blank condition ≠ blank output; ambiguous fill → EMPTY not 'N/A'),
     11 (never source from pd.read_excel for formula sheets — cached stale values), 12 (pre-filled
     sample cells pin boundary/operand semantics; recompute them first; suspect your computation
     unless the instruction names the cell), 13 (run verify_output before finishing) + rule 8
     anti-loop sharpening + sheetkit pointer in the helper paragraph — clusters 2/3/4/5/6.
  4. task_template.md: reminder line extended (literals, don't overwrite correct pre-filled cells,
     empty-not-placeholder, verify_output call) — cluster 1 recency.
- Per change, the EXPECTED effect + why safe:
  1-2. verify_output names exactly what each failing trace's own verification displayed but the
     agent ignored or never checked: 48983's 35/42 empties, 58949's 20 'N/A' placeholders,
     45372's empty-in-data-row, 54144 t2's all-zeros, 58484's unevaluated formulas. set_formula
     fixes 42354/56563's #NAME? (bare IFNA/AGGREGATE recalc to errors under LibreOffice —
     openpyxl stores post-2007 names without the required _xlfn. prefix). Safe: helpers are opt-in
     imports; passing tasks already verify correctly. MECHANICAL safety: openpyxl imported lazily
     inside functions (this optimizer box has NO openpyxl — if the lint env matches, a module-level
     import alone explains cand_0001/0002's 0.000); no __main__ side effects; self_check runs on
     synthetic in-memory/temp input and SKIPs cleanly without openpyxl; no fences/braces anywhere.
  3. Each rule restates the PASSING trial's behavior of the same flaky task (59595 t0 inclusive
     date window; 54144 t0 correct parse; 48365 t0 expanded SUMIFS) so passers keep behavior while
     failing trials get the passer's procedure. Rule 12 softened to "suspect your computation
     first… unless the instruction explicitly tells you to change that cell" so it cannot block
     instruction-driven edits (247-24's Bill Rate change). All edits additive; seed lines retained.
  4. Recency reinforcement of rules the accepted cand_0003 already implies; placeholders verified
     programmatically (exactly the 7, no other braces; no ``` in either file).
- Building on prior RESULTS: cand_0003 (ACCEPTED, +0.133) is the parent — I kept its full text and
  only added to it. cand_0001/0002 (both REJECTED val=0.000, mechanical) shared script+SKILL
  rewrite+DIAGNOSIS.json+literal fences; per cand_0003's PROCESS bisection plan I re-introduce ONLY
  the script+SKILL element, redesigned defensively (lazy openpyxl import — my new prime suspect for
  the mechanical zero, since the optimizer environment itself lacks openpyxl; no root DIAGNOSIS.json;
  no literal fences; indented code blocks in SKILL.md).
- Refuted hypotheses: "ship script+SKILL+DIAGNOSIS+fences+text together" as a package (cand_0001/0002
  0.000) — never re-test as a package. Text-only edits are VALIDATED (cand_0003 accepted).
- High-value clusters still NOT cracked: 433-47 residual-sign convention (undecidable from the
  instruction; both readings supported — a prompt rule would be a coin-flip guess, skipped);
  43436's blank-closed-date gold semantics (rule 12's sample-answer check is my best general lever);
  anti-loop resubmission (prompt rule ignored 25x in 48983 t2 — only a harness-side guard could
  truly fix it, outside our surface).
- Plateau signal: none — first accepted iteration was cand_0003 (+0.133); this builds directly on it.
- Cost-reduction opportunity: no cost/latency objective declared; not run. (verify_output should also
  cut the 25-round identical-resubmit burns by giving a terminal check to converge on.)
- Focus next iteration: if ACCEPTED → the script surface is exonerated; next levers are (a) a
  recalc-semantics helper (evaluate written formulas the way LibreOffice will, e.g. via a
  formula-evaluation sanity check), (b) the 433-47/43436 judgment clusters with worked boundary
  examples in the prompt. If REJECTED at 0.000 → the killer is script/SKILL-structural after all;
  bisect further by shipping SKILL.md documentation pointing at a TRIVIAL one-function script.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.842 · fixed={—} · broke={10452, 105-24, 108-24, 12864, 141-20, 142-12, 165-23, 170-13, 1818, 192-22, 227-40, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 32438, 32612, 32902, 3413, 35742, 36097, 370-43, 37378} · unresolved={267-18, 48365, 53647, 54144, 59595} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0004: rejected val=0.000 Δ=-0.842 -->

## Iteration cand_0005 — text-only reship of cand_0004's trace-verified semantic rules (minus all script references) + fresh rules from this iteration's diagnosis
- Changes I made (all additive text; prompt.md + task_template.md ONLY — no scripts, no SKILL.md, no DIAGNOSIS.json, no fences):
  1. prompt.md "prefer literals" bullet extended → cluster formula-recalc: LibreOffice recalc at grading, _xlfn. prefix for post-2007 functions (or legacy equivalents), never quoted-number criteria, never range/array criteria, never "" branch where gold is empty (42354/56563/58484/48365).
  2. prompt.md rule 9 sharpened → cluster fake-verification: compare evaluated VALUES not formula strings; empty/placeholder/uniform/wrong-type in the printout = failure; never save a demonstrably failed computation (42354/56563/58484/48983/58949/45372/54144).
  3. prompt.md rule 10 new → blank=0 semantics, no placeholder text where gold is empty, unparseable input = inspect not blank (48983/58949/45372).
  4. prompt.md rule 11 new → never pd.read_excel for formula sheets (stale cached values) (247-24/54144).
  5. prompt.md rule 12 new → pre-filled cells/sibling example column are sample answers pinning granularity/boundary/operand-order; don't overwrite correct cells (43436/53647/59595/42354/58484).
  6. prompt.md rule 13 new → coverage discipline: filled-count vs expected, miss-rate = wrong anchors, don't write past data end (48983/42354).
  7. prompt.md rule 14 new → inclusive endpoints for "from X to Y"; exact-character minimal edits (59595/267-18/53647).
  8. task_template.md Reminders extended (recency reinforcement of 1-6, no script references).
- Per change, EXPECTED effect + why safe: each rule restates the PASSING trial's behavior of the same flaky task or the delivery convention the scorer enforces; passers already follow them (59595 t0 inclusive, 53647 t1 operand order, 48365 t0 expanded SUMIFS, 267-18 t1 minimal replace). Target fixes: 42354, 56563, 58484, 48983, 58949, 45372, 247-24, 43436 (always-fail) + 48365, 54144, 53647, 59595, 267-18 (flaky). Mechanical safety: additive-only, placeholders verified programmatically (identical sets to accepted cand_0003), no fences, no files outside the two text surfaces.
- Building on prior RESULTS: cand_0003 (ACCEPTED +0.133) is the parent — full text retained. cand_0004's semantic rules were never behaviorally tested (its rejection was a mechanical 0.000 from the script/SKILL element), so I reship its TEXT minus every helper reference. I did NOT re-try: any skills/spreadsheet-helpers script or SKILL.md rewrite (killed cand_0001/0002/0004 mechanically), root DIAGNOSIS.json, literal fences.
- Refuted hypotheses: "ship script+SKILL+text as a package" (3x mechanical 0.000 — cand_0001/0002/0004). Text-only additive edits are VALIDATED (cand_0003 accepted).
- High-value clusters still NOT cracked: 433-47 residual sign/distribution convention (undecidable from instruction — skipped deliberately); identical-resubmit loops (prompt rule ignored 25x in 48983 t2 — needs a harness-side guard, outside our surface); the ~11 tool-call-format aborts from iteration 1 appear mostly resolved by cand_0003's contract.
- Plateau signal: cand_0003 accepted (+0.133); cand_0004 mechanical zero. Lever unchanged: text rules; the script lever is fenced off by three mechanical zeros and ~1 eval of rollout budget left (1800/2160).
- Cost-reduction opportunity: no cost/latency objective declared; not run.
- Focus next iteration: if ACCEPTED, remaining failing set is likely 433-47 + infra; if the gate still shows mechanical 0.000 on a text-only candidate, suspect the two extended lines and revert to pure additions of new lines only.

> **RESULT (framework, measured):** ACCEPTED (new champion) · val=0.843 Δ=+0.001 · fixed={10747, 32023, 325-44, 34033, 42354, 45372, 47766, 48620, 52216, 55965, 58949, 7902} · broke={141-20, 142-12, 227-40, 250-20, 254-34, 39046, 39903, 408-39, 45635} · unresolved={105-24, 267-18, 2768, 46646, 48365, 48527, 54144, 56563, 59595, 80-42} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them).
<!-- cand_0005: ACCEPTED val=0.843 Δ=+0.001 -->
