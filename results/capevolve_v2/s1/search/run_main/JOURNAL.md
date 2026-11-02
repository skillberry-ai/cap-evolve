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

## Iteration cand_0001 — pin reply format + move write/locate/verify procedures into bundled helpers
- Changes I made (1 line/edit + cluster):
  - prompt.md "HOW TO REPLY" + task_template reply-shape example → cluster A (reply-format waste, 11 always-fail tasks);
  - prompt.md workflow: write output EARLY, never re-run identical successful code → clusters A/E;
  - prompt.md "Common pitfalls": typed values, openpyxl-not-pandas, recompute dependents, keep header row, formula-result edits, no silent save after failed lookup → clusters B/D/E;
  - skills/spreadsheet-helpers/scripts/ranges.py (open_input, write_range, read_range, parse_answer_position incl. stray-quote ranges) → cluster B;
  - skills/spreadsheet-helpers/scripts/find_table.py (find_header_row, find_column raising with available headers, sheet_data_extent) → cluster C;
  - skills/spreadsheet-helpers/scripts/verify.py (save_and_verify with expected=, identical-to-input warning) + SKILL.md docs → clusters A/C/E.
- Per change, EXPECTED effect + why it's safe:
  - Format contract should flip the first-reply coin toward fenced blocks on the 12 format-waste tasks (they currently burn all ~6 rounds); safe because passing tasks already emit fenced blocks — no behavior change for them.
  - Helpers move deterministic procedures (range parsing, header location, save+verify) out of the model; safe because they only act on arguments the agent passes and never touch gold.
  - Pitfall rules each restate what the PASSING trials of the same flaky tasks already did (66-24 t0 wrote datetimes, 267-18 t0 rewrote the formula, 227-40 t0/t1 kept the header) — they codify observed passing behavior, and a softness clause allows judgment.
- Building on prior RESULTS: none exist (first iteration; RUNMAP/LEDGER empty, rejected.jsonl empty).
- Refuted hypotheses: none yet.
- High-value clusters not yet cracked: 80-42 (yellow-highlight column selection semantics), 118-50 (restrictive pattern semantics) — both judgment-only, no code lever found; 247-24 dependent-formula recomputation is only partially addressed (rule + openpyxl, no recalc engine).
- Plateau signal: n/a (iteration 1).
- Cost-reduction opportunity: cost/latency not a declared objective; not measured.
- Focus next iteration: check whether the format cluster actually flipped (it is ~9% of val reward); if 247-24-style tasks remain, consider a helper that evaluates dependent formulas (e.g. formulas lib) or keeps formulas intact.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.697 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 170-13, 1818, 192-22, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 32438, 325-44, 32612, 32902, 35742, 370-43, 37378, 379-36} · unresolved={227-40, 267-18, 36097, 416-15, 45372, 46646, 48365, 48620, 48921, 493-18, 53647, 54638, 56274, 58109, 66-24} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0001: rejected val=0.000 Δ=-0.697 -->

## Iteration cand_0002 — re-apply the diagnosed fixes behind hard structural safeguards
- Changes I made (1 line/edit + cluster):
  - prompt.md "HOW TO REPLY" with literal fenced-block example → cluster A (reply-format waste, 11 always-fail + 1 flaky task);
  - task_template.md "REPLY FORMAT" restatement + tiny example at the end of the task message → cluster A (recency);
  - prompt.md workflow 5-7 (write output EARLY, verify before finishing, never re-send identical code) → clusters A/D;
  - prompt.md "Common pitfalls" (typed values, openpyxl over pandas round-trip, recompute dependents, keep header row, never patch formula text, no silent save, exact range match) + softness clause → clusters B/C/D/E;
  - skills/spreadsheet-helpers/scripts/ranges.py (parse_answer_position incl. stray-quote ranges, open_input, write_range with spill guard, read_range) → clusters B/C;
  - skills/spreadsheet-helpers/scripts/find_table.py (find_header_row, find_column raising with available headers, sheet_data_extent) → cluster C;
  - skills/spreadsheet-helpers/scripts/verify.py (save_and_verify: makedirs + save to EXACT path + reopen + filled/formula/sample/mismatch report + identical-to-input no-op warning) → clusters A/C/D;
  - skills/spreadsheet-helpers/SKILL.md documenting every helper (zero braces, valid frontmatter).
- Per change, EXPECTED effect + why it's safe:
  - Reply-format contract should flip the first-reply coin toward fenced blocks on the 12 format-waste tasks (~10% of val reward); safe because passing tasks already emit single fenced blocks — no behavior change for them.
  - Helpers move deterministic procedures (range parsing, header location, save+verify) out of the model; safe because they only act on arguments the agent passes, import lazily, and never touch anything but the given paths.
  - Pitfall/workflow rules each codify what the PASSING trials of the same flaky tasks already did; a softness clause allows judgment when a rule would hurt the saved output.
  - STRUCTURAL SAFETY (the cand_0001 lesson): val=0.000 with zero fixed tasks is the signature of rejection-before-any-rollout, not behavioral regression. This candidate adds NO new braces to prompt.md / task_template.md / SKILL.md (verified by simulating .format() on both templates — placeholder sets are exactly the seed's), uses lazy openpyxl imports so module import cannot fail in a bare environment, and keeps import-safe self-checks.
- Building on prior RESULTS: cand_0001's RESULT (rejected, val=0.000, broke=30 passing, fixed={}) — I treat it as a structural rejection of the BATCH, not evidence against any single edit's behavior; the seed traces still show every cluster unfixed, so I re-apply the same intent redesigned for structural safety rather than abandoning the clusters.
- Refuted hypotheses: none beyond the above interpretation; if this candidate ALSO scores exactly 0.000, the structural cause is something both iterations share (likely template formatting or script validation) and the next iteration should ship a prompt-ONLY edit with the seed task_template to bisect.
- High-value clusters still NOT cracked: 80-42 (yellow-highlight column selection semantics), 118-50 (restrictive pattern semantics) — judgment-only, no code lever; 247-24's dependent-formula recomputation is only addressed by a rule (no offline recalc engine available).
- Plateau signal: n/a (second iteration; first was structurally rejected).
- Cost-reduction opportunity: cost/latency not a declared objective; not measured.
- Focus next iteration: if the gate ACCEPTS, check whether cluster A actually flipped (it is ~9-10% of val reward) and whether helpers got called at all (grep trajectories for skills.spreadsheet_helpers imports); if REJECTED at 0.000 again, bisect the structural break with a prompt-only candidate.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.697 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 170-13, 1818, 192-22, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 32438, 325-44, 32612, 32902, 35742, 370-43, 37378, 379-36} · unresolved={227-40, 267-18, 36097, 416-15, 45372, 46646, 48365, 48620, 48921, 493-18, 53647, 54638, 56274, 58109, 66-24} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0002: rejected val=0.000 Δ=-0.697 -->

## Iteration cand_0003 — single-surface bisect: prompt.md-only (reply contract + workflow + pitfall rules), no scripts/templates after two structural 0.000s
- Changes I made (1 line/edit + cluster):
  - prompt.md "HOW TO REPLY" contract with literal worked fenced-block example at primacy → cluster A (12 format-waste tasks, ~6 always-fail + 2 flaky on val);
  - prompt.md workflow: write output EARLY then verify, never re-send an identical code block, stop only after re-opening output_path → clusters A/C/D;
  - prompt.md pitfall rules with reasons: typed values, openpyxl in-place over pandas round-trip, never patch formula text, recompute dependent totals, never save an unchanged workbook → clusters B/C/E;
  - prompt.md softness clause → all clusters.
- Per change, the EXPECTED effect + why it's safe:
  - Reply contract should flip the first-reply coin toward fenced blocks on the format-waste tasks (they burn every round on "No python code block was found"; the harness's own correction arrives after the wasted round, the contract arrives before the first reply). Safe: passing tasks already emit single fenced blocks — no behavior change.
  - Pitfall/workflow rules each codify what the PASSING trials of the same flaky tasks already did (66-24 t0 datetimes, 227-40 t0 header kept, 267-18 t0 literal, 118-50 needs early write). Safe for the same reason.
  - STRUCTURAL SAFETY (the cand_0001/0002 lesson): this candidate touches prompt.md ONLY — no task_template.md change, no SKILL.md change, no new scripts. Both prior batches were rejected at val=0.000 with fixed={} (rejection-before-rollout); the scripts they added are the most likely culprit (skill-package validate() runs each bundled script's --self-check; those scripts were module-style and contained a task-specific literal). Verified: only the {skills_root} placeholder remains in prompt.md, .format() simulation passes, every seed constraint survives in the workflow list.
- Building on prior RESULTS: cand_0001 + cand_0002 RESULTs (both rejected 0.000, same 30-task broke set, fixed={}) — I treat them as STRUCTURAL rejections of the batches, not behavioral evidence against any rule; the seed traces still show every cluster unfixed, so the same diagnosed fixes ship on the one surface both rejections' shared riskiest elements do not include.
- Refuted hypotheses: "the 0.000 was behavioral regression of 30 passing tasks" — refuted by the exact-0.000-with-zero-fixed signature (30 breaks alone would land ≈0.45). If THIS candidate also scores exactly 0.000, the structural break lives in prompt.md itself (fence/brace) and the next iteration must ship a prose-only, fence-free prompt edit.
- High-value clusters still NOT cracked: 80-42 (yellow-highlight column semantics), 118-50 (restrictive pattern semantics) — judgment-only; 247-24 dependent-formula recalc has only the prose rule (no offline recalc engine).
- Plateau signal: two consecutive structural 0.000s — lever switched to single-surface bisect (prompt-only), per cand_0002's own prescription.
- Cost-reduction opportunity: cost/latency not a declared objective; not measured.
- Focus next iteration: if ACCEPTED, re-add helpers ONE surface at a time (scripts written with a real --self-check CLI entry point, zero task-specific literals) and grep new trajectories for helper adoption; if REJECTED at 0.000 again, ship a fence-free prose-only prompt edit to isolate the structural check.

> **RESULT (framework, measured):** ACCEPTED (new champion) · val=0.820 Δ=+0.123 · fixed={37456, 402-43, 45635, 47766, 50916, 51-12, 55965, 59595} · broke={250-20, 2768, 32902, 35742, 56427} · unresolved={170-13, 227-40, 267-18, 36097, 416-15, 45372, 46121, 46646, 48080, 48365, 48620, 48921, 493-18, 53647, 54638, 56274, 57113, 58109, 66-24} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them).
<!-- cand_0003: ACCEPTED val=0.820 Δ=+0.123 -->

## Iteration cand_0004 — re-add the helper surface on the champion: guarded writes, content-matched location, loud save-audit + verification/reference/anchor rules
- Changes I made (1 line/edit + cluster):
  - skills/spreadsheet-helpers/scripts/ranges.py (parse_answer_position incl. sheet-qualified/stray-quote/multi-range, open_input, read_range, write_range with exact-shape SPILL guard + None-never-clears DESTRUCTIVE guard) → cluster C3 destructive blanking/spill (48527, 48080-t2, 118-50);
  - skills/spreadsheet-helpers/scripts/verify.py (verify_output: reopens SAVED file at exact path, prints FULL untruncated answer values, PROBLEMS list: MISSING FILE / EMPTY / EXCEL ERROR / FORMULA / CLEARED / UNCHANGED) → clusters C1 self-confirming verification, C4 formula blindness, C5 silent-None, C7 path typo (48983, 45372, 53647, 46121-t1, 170-13-t2, 57113);
  - skills/spreadsheet-helpers/scripts/find_table.py (list_sheets, find_header_row/find_column by CONTENT with loud misses, rows_as_dicts with _row, sheet_data_extent) → clusters C2 reference blindness, C6 anchor assumptions (82-30, 118-50, 43436, 46121-t1, 48080-t2);
  - skills/spreadsheet-helpers/SKILL.md documenting every helper, brace-free → all;
  - prompt.md workflow 2/5/7/8 (list EVERY sheet + use in-workbook examples; no changes outside the range incl. no source re-sorting; copy output_path verbatim; final verify_output call) → C1/C2/C7;
  - prompt.md five new pitfall rules (printed anchors, pandas row 0 = Excel row 2; empty-because-unparsed is a bug; lookup blank→0; summary table ⇒ grouped aggregate; concatenation boundary check) → C5/C6/C8/C9/C10;
  - prompt.md helper import line naming the three modules.
- Per change, the EXPECTED effect + why it's safe:
  - verify_output converts the recurring "agent saw the symptom in its own output and finished anyway" pattern (48983 7/42 filled, 45372 two blank rows, 53647 formula strings, 170-13 truncated ++ prints) into a loud PROBLEMS list the model must fix or justify; safe because it is a read-only audit replacing the manual re-open-and-print step the prompt already required, and every PROBLEM is advisory with the softness clause intact.
  - write_range's None-never-clears guard directly prevents 48527's destruction of D2='Apple' and 48080-t2's overwrite pattern; safe because it is opt-in and allow_clear exists for explicit delete instructions.
  - list_sheets + workflow-2 rule pushes reading the Manual Result sheet (82-30) and the seeded example pair (118-50) the instructions explicitly reference; safe because passing tasks already inspect the workbook.
  - The five knowledge rules each restate what the PASSING trials of the same flaky tasks already did; the softness clause allows judgment.
  - STRUCTURAL SAFETY (the cand_0001/0002 lesson, followed per cand_0003's prescription): scripts have real `python <script>.py` self-check entry points, lazy openpyxl imports, guarded self-checks, and ZERO task-specific literals (scrubbed every 'Main!'A2:M70-style example; generic sheet names in self-checks). prompt.md keeps only {skills_root} (.format() simulation passes); SKILL.md is brace-free; task_template.md is byte-untouched. Scripts tested bare AND against an openpyxl stub end-to-end, incl. package-style import.
- Building on prior RESULTS: cand_0003's ACCEPT (+0.123, prompt-only) is the base — its prompt structure is preserved and extended, nothing removed. cand_0001/0002 RESULTs (structural 0.000): I did NOT re-ship their task-specific self-check literal or module-style scripts; the scripts are redesigned per the lint rules (general, offline, self-checking). I did not re-try any task_template.md edit.
- Refuted hypotheses: "30 passing tasks were behaviorally broken by the rules" (refuted by cand_0003's ACCEPT of the same rules); "helpers are inherently unshippable" (untested until now — this iteration is the bisect step).
- High-value clusters still NOT cracked: 433-47 residual-balancing sign/allocation semantics and 118-50's word-pattern definition — ambiguous VBA paraphrases where both independent trials pick the same wrong reading; no general lever found (reference-sheet rule helps 118-50 only partially). 82-30's column-major ordering is covered only if the agent actually diffs against the Manual Result sheet.
- Plateau signal: one ACCEPT after two structural rejects; not flat. Lever used this iteration: code (bundled scripts) on top of the accepted prose — the strongest available for the verification/blanking procedures.
- Cost-reduction opportunity: cost/latency not a declared objective; not measured. (Note for future iterations: several passing trials burn 20+ rounds re-sending identical verified code — 48080-t1, 170-13-t1 — a "stop after verify passes" nudge may be worth testing if cost ever becomes an objective.)
- Focus next iteration: if ACCEPTED, grep new trajectories for `skills.spreadsheet_helpers` adoption and verify_output PROBLEM handling; then extend verify_output with a soft out-of-range-change WARNING and consider a deterministic INDEX/MATCH grid-fill helper (blank→0) if 48983-class tasks recur. If REJECTED at 0.000, the structural break is in the scripts/SKILL.md themselves — bisect by shipping SKILL.md + verify.py only.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.820 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 1818, 192-22, 254-34, 262-17, 263-1, 267-18, 30930, 31011, 31628, 31915, 32255, 32337, 32438, 325-44, 32612, 36097, 370-43, 37378, 37456, 379-36, 382-10, 38462} · unresolved={170-13, 46121, 48080, 57113} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0004: rejected val=0.000 Δ=-0.820 -->

## Iteration cand_0005 — prompt-only re-ship of cand_0004's diagnosed fixes (its scripts tripped validation; its prompt edits never ran)
- Changes I made (1 line/edit + cluster):
  - prompt.md HOW TO REPLY: opening fence must be the FIRST characters of the reply (no leading blank line) → cluster H reply-parser waste (57113 mid-episode rounds);
  - prompt.md workflow 2: list EVERY sheet + REAL data extent; read in-workbook reference material the instruction points at FIRST → clusters B/E reference + extent (82-30, 118-50, 43436, 48080, 48983);
  - prompt.md workflow 5: never sort/rewrite/reformat/blank source data outside the answer range → cluster B (118-50 sorted col A);
  - prompt.md workflow 7: copy output_path character-for-character, never retype → cluster D path typo (57113);
  - prompt.md workflow 8 rewritten as a grader-style audit: print EVERY answer cell coordinate + repr(), count filled vs blank, blank-in-a-fill-task = wrong (unmatched lookup means 0), formula-string/#N/A = unverified, None-over-valued-cell = destroyed → clusters A/C/E/G verification blindness (48983, 45372, 48527, 53647, 43436, 48080, 46121, 170-13);
  - prompt.md four new pitfall rules (never None over a valued cell + no-match-is-a-bug; anchor on PRINTED cells / pandas row 0 = Excel row 2; summary grid ⇒ grouped aggregate; concatenation boundary + repr) → clusters C/E/F/G.
- Per change, the EXPECTED effect + why it's safe:
  - The audit rule converts the dominant failure mode (agent saw blanks/sparse fills/formula strings in its own output and finished anyway — verified directly in 48527 t0 and 48983 t0) into an explicit must-fix checklist; expected to flip several of the 8 verification-blind failing/flaky tasks. Safe: passing tasks already re-open and print answer values; the audit is that step made more explicit, the softness clause is retained verbatim, and every rule codifies what passing trials of the same flaky tasks already did.
  - Verbatim-path + fence-first rules are pure additions targeting observed waste; no passing task retypes paths correctly-and-suffers.
  - STRUCTURAL SAFETY: prompt.md is the ONLY edited surface — the one combination the gate has accepted (cand_0003). Only {skills_root} brace token remains, .format() simulation verified, task_template.md and skills/ byte-untouched.
- Building on prior RESULTS: cand_0003's ACCEPT (+0.123) is the base prompt, extended not restructured. cand_0004's REJECT (val=0.000, fixed={}) is treated as structural rejection of its SCRIPTS, not its prompt edits — those prompt edits are exactly what I re-ship, minus the helper-import line (no helpers exist). I did NOT re-try any script, SKILL.md or task_template.md edit (cand_0001/0002/0004 all died at 0.000 with them).
- Refuted hypotheses: "scripts can pass validation if lint-clean with CLI self-checks" — refuted by cand_0004's 0.000 despite following every documented lint rule. Do not ship scripts again without new information about the validator.
- High-value clusters still NOT cracked: 433-47 / 118-50 core semantics (ambiguous VBA paraphrases, both trials same wrong reading; no lever found by cand_0004 or me). 82-30 column-major ordering only covered if the reference-sheet rule is followed.
- Plateau signal: prompt-only lever has one ACCEPT; scripts lever is dead (3 structural rejects). If this candidate is rejected at ~0.000, the remaining suspect is prompt length/structure itself — bisect by shipping only the workflow-8 audit rule. If accepted but small, the remaining always-fail tasks are judgment-bound; consider whether any prompt lever can disambiguate VBA paraphrases (e.g. "when an instruction paraphrases a macro, enumerate the plausible readings and pick the one consistent with the workbook's reference material").
- Cost-reduction opportunity: cost/latency not a declared objective; not measured. (Noted: nearly every episode ends with 3 wasted 'No python code block was found' rounds — the agent's completion reply pattern; harmless to reward but a cost lever if ever needed.)
- Focus next iteration: grep new trajectories for whether the workflow-8 audit changed final replies on the verification-blind tasks; if 433-47/118-50 remain, try the enumerate-plausible-readings rule above.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.818 Δ=-0.003 · fixed={250-20, 2768, 32902, 34033, 3413, 35742, 39046, 408-39, 416-15, 56427, 66-24} · broke={263-1, 37456, 51-12} · unresolved={170-13, 194-19, 227-40, 32023, 32337, 46121, 47766, 48080, 48527, 51090, 53647, 54144, 55965, 57113, 58949, 80-42} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0005: rejected val=0.818 Δ=-0.003 -->
