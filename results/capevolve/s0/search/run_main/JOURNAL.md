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

## Iteration cand_0001 — ⚠ EMPTY HANDOVER, framework-synthesized from the commit reason (the optimizer wrote no entry of its own — see the `optimizer_context_warning` event):
paired Δ̄=-0.6751 <= 0.5·SE=0.0190 (SE=0.0380, n=119, resolvable effect size 2·SE=0.0761)

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.675 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 1818, 192-22, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 325-44, 32612, 32902, 35742, 370-43, 37378, 379-36, 382-10, 38462} · unresolved={170-13, 267-18, 32438, 37456, 39046, 402-43, 408-39, 42354, 45372, 463-17, 46646, 48365, 48620, 48921, 50768, 50916, 52216, 53383, 53647, 55049, 55965, 56563, 58949, 66-24, 80-42, 82-30} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0001: rejected val=0.000 Δ=-0.675 -->

## Iteration cand_0002 — reply-format contract + four deterministic xlsx_io helpers + flaky-consistency prompt rules
- Changes I made (1 line/edit; cluster):
  1. prompt.md + task_template.md (cluster A, format lock-in): reply-format contract moved to the TOP of both messages, with an explicit ban on `<|tool_call>` syntax, a worked correct fenced reply, and a top-of-message reminder in the task template.
  2. skills/.../xlsx_io.py `start_from_input` (clusters A/B): copy input→output_path in round 1 so running out of rounds still leaves a valid file.
  3. xlsx_io.py `apply_edits` (cluster D): load ORIGINAL workbook, write only listed cells, skip cells whose value is unchanged (float/int/str type preservation), actionable error on bad sheet/ref.
  4. xlsx_io.py `find_text` (cluster B): whole-workbook header/label search that raises loudly on miss — kills the "if found: ... save anyway" silent no-op class.
  5. xlsx_io.py `verify_output` (cluster C): re-open saved file, parse messy answer_position, report coverage/values/changed-vs-input/prefilled_changed, flag empty ranges and no-op writes.
  6. prompt.md rules (clusters D/E/F/G): recompute derived cells; never pd.to_numeric alphanumeric keys; skip embedded header/blank rows; absolute openpyxl coordinates + absolute-read verify; preserve dates/formulas/separators; reference sheet/section = specification; never resubmit unchanged code; rounds are limited.
  7. SKILL.md rewritten to document all four helpers (valid frontmatter, <500 lines).
- Per change, EXPECTED effect + why safe:
  1. Cluster A is the largest recoverable score (10 always-fail tasks waste EVERY round on tool-call syntax; 74 wasted rounds/360 trials; mode is trial-global so prevention at trial start is the only lever). Safe: passing tasks already emit single fenced blocks — the rule describes their current behavior.
  2. Fixes "NO output file" when the agent runs out of rounds; pure file copy, no behavior change for passing tasks.
  3. Same values the agent computes, written with fewer side effects than its own pandas to_excel; skip-unchanged prevents the int/float and "changed-though-expected-original" drift seen in 398-14/194-19.
  4. 408-39's failing trials assumed header row 4 and silently skipped when absent; find_text scans all cells and aborts loudly.
  5. 194-19/22-47/463-17/402-43 failed with verification that never diffed the answer range; the report surfaces empty cells, prefilled cells changed, and no-op writes.
  6. Each rule is backed by a passing-trial-vs-failing-trial pair (e.g. 66-24 date objects, 170-13 separator, 463-17 off-by-one); rules state what passing trials already do, so blast radius on passing tasks is minimal.
  7. Agent sees helpers in system prompt; documentation matches the code.
- Building on prior RESULTS: cand_0001 (REJECTED, val 0.000, EVERY task broke) added an xlsx_io helper + SKILL.md rewrite; its wipeout pattern (all 119 tasks → 0, consistent with lint/smoke/package-validation failure, not behavior) means I re-implemented the same concept defensively: script compiles, module imports without openpyxl (lazy import), `--self-check` exits 0 even when openpyxl is missing, valid frontmatter, body <500 lines. I did NOT re-try anything from its broke-list because no specific edit could be isolated — the failure was plausibly mechanical, so the redesign is structural-safety, not conceptual.
- Refuted hypotheses: none yet beyond cand_0001's implied "a helper script alone is safe" — treat unvalidated script packaging as capable of zeroing the whole candidate.
- High-value clusters not yet cracked: 118-50/22-47 (internally contradictory instructions — likely unfixable without overfitting); the deeper "interpret the VBA-prose instruction" class generally.
- Plateau signal: only iteration 1 so far (rejected). Lever used now: prompt contract + skill scripts (both surfaces).
- Cost-reduction opportunity: cost/latency not a declared objective; noted anyway: cluster G (identical-block resubmission to the 62-turn cap) is the biggest token sink — addressed via the "never resubmit unchanged" rule.
- Focus next iteration: if cluster A persists (check wasted-round count in new traces), try an even stronger format intervention (e.g. task_template example reply as the first user-message line); otherwise double down on cluster C/D via helper adoption rate — check whether agents actually call apply_edits/verify_output.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.675 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 1818, 192-22, 250-20, 254-34, 262-17, 263-1, 2768, 30930, 31011, 31628, 31915, 32255, 32337, 325-44, 32612, 32902, 35742, 370-43, 37378, 379-36, 382-10, 38462} · unresolved={170-13, 267-18, 32438, 37456, 39046, 402-43, 408-39, 42354, 45372, 463-17, 46646, 48365, 48620, 48921, 50768, 50916, 52216, 53383, 53647, 55049, 55965, 56563, 58949, 66-24, 80-42, 82-30} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0002: rejected val=0.000 Δ=-0.675 -->

## Iteration cand_0003 — prompt-only rewrite: reply-format contract + answer-range/type/formula/verification rules (no scripts)
- Changes I made (1 line/edit; cluster):
  1. prompt.md §REPLY FORMAT + task_template.md line 1 (cluster A): one-fence reply contract at the very top of both messages, worked example, no tool-call/XML syntax — no new braces, no literal special tokens.
  2. prompt.md §Workflow (clusters C/F): ordered INSPECT→COMPUTE→WRITE→VERIFY; print full relevant sheet; instruction-named reference sections are the spec; scan whole sheet for headers; print raw mappings.
  3. prompt.md §Rules for the answer range (cluster B): answer_position authoritative over prose; fill every cell; no padding past the answer's end; fill on lookup miss; preserve pre-filled cells; explicit header-alignment decision.
  4. prompt.md §Rules for values and types (clusters D/E): real typed values (datetime objects, int/float per source); hyphen only for truly blank cells; openpyxl for copying (no pandas round-trips); quoted formulas reproduced exactly; prefix the formula's output not its text; recompute dependents after input changes; Excel-row↔df-index mapping note.
  5. prompt.md §Before you finish (cluster F): print full graded range incl. first/last cell; size sanity check; never resubmit identical code.
- Per change, EXPECTED effect + why safe:
  1. Cluster A is the largest recoverable block: 15 tasks with tool-call-mode trials (~35 lost trials ≈ +0.10 val if the trial-start mode shifts). The mode is decided at the first reply, so both the system prompt and the task message now lead with the contract + example. Safe for passing tasks: they already reply with single fenced blocks; the rule describes their current behavior. UNCERTAIN: if the mode is fixed by the serving chat template, no prompt text can shift it — this iteration doubles as the clean experiment (prompt-only, no mechanical confound).
  2–5. Each rule traces to a pass-vs-fail trial pair within one task (66-24 datetime, 80-42 openpyxl-copy, 82-30 reference sheet, 402-43 header flip, 194-19 pre-filled cells, 463-17 verify slice) or an unambiguous failing behavior (22-47 prose-vs-range, 48983 skipped lookups, 247-24 stale dependents, 55427 fuzzy keys). They state what passing trials already do, so blast radius on the 67 passing tasks is minimal; nothing the seed prompt constrained was deleted (all six seed rules survive, several verbatim).
- Building on prior RESULTS: cand_0001 and cand_0002 both REJECTED at val=0.000 with the ENTIRE task set broken — the signature of a pre-rollout validation failure (lint/smoke/package), not behavior. Their common factor was a new scripts/xlsx_io.py + SKILL.md rewrite; I therefore dropped the script surface entirely this iteration and kept SKILL.md and scripts/ untouched. I did not re-try any script-package edit.
- Refuted hypotheses: none newly refuted (both prior wipeouts were never behaviorally measured). Carried-forward suspicion, now tested cleanly: "a helper script + SKILL.md rewrite zeroes the candidate" — if this prompt-only candidate RUNS (any nonzero movement anywhere), the script package was the killer and the next iteration can reintroduce one minimal script.
- High-value clusters not yet cracked: cluster A's root fix may be harness-side (parse tool-call markup) — unavailable on my surfaces; if the format contract fails to shift trial-start mode, cluster A is a hard ceiling and effort goes to B–F via helper adoption.
- Plateau signal: two consecutive REJECTED iterations with val=0.000 (mechanical). Lever switched to: prompt-only, structurally different from both rejected batches.
- Cost-reduction opportunity: cost/latency not a declared objective; noted: 56786 burned 30 identical re-runs — the no-identical-resubmission rule targets exactly that.
- Focus next iteration: (1) check whether cluster A trials now start in fenced mode; if yes, most of the +reward is already banked. (2) If this candidate is ACCEPTED, reintroduce ONE minimal helper script (brace-free, lazy imports, no __main__) for write_range/verify_output and measure adoption. (3) If REJECTED at val=0.000 again with everything broken, the wipeout is NOT the script package — audit prompt.md/task_template.md mechanical validation next (fenced block inside system prompt? reply-format line in template?).

> **RESULT (framework, measured):** ACCEPTED (new champion) · val=0.789 Δ=+0.114 · fixed={227-40, 34033, 3413, 36097, 45635, 47766, 7902} · broke={254-34} · unresolved={170-13, 267-18, 31011, 32023, 32438, 35742, 37456, 39046, 402-43, 408-39, 42354, 46121, 463-17, 46646, 48365, 48527, 48620, 48921, 50768, 50916, 51-12, 53383, 54638, 55049, 55965, 560-12, 56563, 58949, 66-24, 80-42} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them).
<!-- cand_0003: ACCEPTED val=0.789 Δ=+0.114 -->

## Iteration cand_0004 — reintroduce the code lever safely: minimal xlsx_io helper + ~15 prompt rules from fresh full-trace diagnosis
- Changes I made (1 line/edit; cluster):
  1. skills/spreadsheet-helpers/scripts/xlsx_io.py (NEW, clusters A/C/H): parse_ranges, write_range (loads original-or-earlier output, writes full 2-D block, actionable errors), verify_output (coverage + changed-vs-input + silent-no-op PROBLEMS), read_range, lookup_first (Excel MATCH semantics: FIRST duplicate wins, case/whitespace-normalized keys, miss value instead of skip).
  2. SKILL.md rewrite (cluster A/C): documents the four helpers with when-to-call + examples; frontmatter unchanged in shape.
  3. prompt.md Workflow WRITE (clusters C/H): write final answer via write_range, never pandas to_excel; save a valid output EARLY; read_only for huge workbooks.
  4. prompt.md Workflow VERIFY (clusters C/F): run verify_output; check the anchor neighborhood, not the written slice.
  5. prompt.md answer-range rules (clusters C/D/F/G): anchor-exact start cells; full result never truncated at the checked range; edge/last-row boundary re-check against underlying data; copy the target sheet's blank convention when consolidating; in-sheet worked example/axes = ground truth; N/A-vs-blank tie-breaker.
  6. prompt.md values/types rules (clusters A/B/D/E/G): Excel lookup conventions (first-match, blank INDEX -> 0, miss value, never blank-out on miss) + lookup_first pointer; inclusive "up to"; no constraint-violating fallback; float epsilon on threshold compares; fewest-cells-changed under min/max constraints; ARRAY-FORMULA BAN (CSE/MATCH(1,(..)*(..))/AGGREGATE-as-text not recalculated — write literal or plain single-range formula); datetime .date()/.time() extraction; today = datetime.now(); enumerate every stated dimension and prefer the opening business statement over parenthetical paraphrases.
- Per change, the EXPECTED effect + why it's safe:
  1-2. lookup_first directly fixes 55427 (dict kept LAST dup postcode, 109 wrong values; plus unnormalized key variants) and 48983 (blank INDEX skipped instead of 0; 6/42 filled); write_range/verify_output fix the write-extent/no-op class (247-24 truncation at row 70, 80-42 None-holes + overrun, 56786 one-row-off, 35742 never saved). Safe for passing tasks: helpers are additive options; passing trials already write via openpyxl from the original workbook and verify fully. MECHANICAL RISK: both prior wipeouts (cand_0001/0002, val=0.000) included a script package — this script follows every design rule from INSIGHTS (lazy openpyxl import, self-check exits 0 without openpyxl, no network/subprocess/task literals, compiles standalone, self-check RUNS green here) and no literal special tokens exist anywhere in the candidate.
  3-6. Each rule names the behavior of the PASSING trial in a diagnosed pass-vs-fail pair (51-12 epsilon, 45372 datetime, 32023 today, 560-12 anchor, 46121 header, 52216/31011/54638 plain-formula, 6239/43436 dimension modeling, 58109/37456 inclusive boundary, 50768 in-sheet example, 58949 blank-over-N/A, 51090 save-early), so blast radius on the 89 passing tasks is minimal; nothing from cand_0003's accepted prompt was deleted — sections only extended.
- Building on prior RESULTS: cand_0003 ACCEPTED (+0.114) — its whole prompt is retained and extended; per its handover plan, the script surface is reintroduced now that the pipeline is proven to run. cand_0001/0002 REJECTED at val=0.000 (wipeouts): I did NOT re-try their `<|tool_call>` literal counter-example or their prompt+script batch shape; the script here is structurally minimal vs cand_0001's 346-line version.
- Refuted hypotheses: none newly (prior wipeouts never behaviorally measured). Still open: the wipeout cause — if THIS candidate also zeroes, the script package remains the killer and the prompt is fine (bisect next: same prompt, no script).
- High-value clusters not yet cracked: cluster I ambiguous instructions (118-50, 48527, 53647, 433-47 absorption pattern, 194-19 row mapping, 58484 per-row counts) — underdetermined specs; designs tried and skipped as coin flips. 433-47's "fewest columns adjusted" heuristic shipped as the fewest-cells rule but is not guaranteed gold.
- Plateau signal: cand_0003 was the first ACCEPT (+0.114 from 0.675). No plateau. Lever ADDING code on top of prose, per the diagnosis that behavioral misses (lookups, extent, no-ops) need enforcement, not more rules.
- Cost-reduction opportunity: cost/latency not a declared objective; noted 51090/56786-style round burning is addressed by save-early + no-identical-resubmission rules already present.
- Focus next iteration: (1) if ACCEPTED, check helper adoption in new traces (grep write_range/verify_output/lookup_first) and extend the script with find_header_row/consolidate helpers for the remaining extent clusters; (2) if REJECTED at val=0.000 with everything broken, the script package is confirmed as the wipeout cause — resubmit this exact prompt with NO script; (3) if REJECTED behaviorally, read broke={} tasks first and drop only the offending rule.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.000 Δ=-0.789 · fixed={—} · broke={10452, 105-24, 10747, 108-24, 12864, 141-20, 142-12, 165-23, 170-13, 1818, 192-22, 227-40, 250-20, 262-17, 263-1, 267-18, 2768, 30930, 31628, 31915, 32255, 32337, 32438, 325-44, 32612, 32902, 34033, 3413, 36097, 370-43} · unresolved={31011, 32023, 35742, 45372, 46121, 48527, 51-12, 52216, 53647, 54638, 560-12} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0004: rejected val=0.000 Δ=-0.789 -->

## Iteration cand_0005 — prompt-only clean bisect: full rule set for all 31 failing/flaky tasks, zero skills/ edits
- Changes I made (1 line/edit; cluster):
  1. prompt.md INSPECT (cluster D extent/header): print columns from row 1 (never assume header), never trust ws.max_row, clip writes to answer_position.
  2. prompt.md INSPECT (cluster G/E): in-sheet axis labels before grid mapping; worked example (sheet, instruction, or hand-completed target cells) IS the spec — assert reproduction before filling.
  3. prompt.md INSPECT (cluster E): user-presented failing formula must be diagnosed, not re-implemented; join on the unique shared identifier.
  4. prompt.md INSPECT (cluster F): parts-of-a-unit rows (half-days) — explicit part-vs-whole counting decision.
  5. prompt.md WRITE + task_template.md (clusters D/35742): copy paths verbatim, never retype; corrupt workbook -> read_only/zipfile parse + save best-effort early.
  6. prompt.md answer-range (cluster C): never blank an existing value/formula on lookup miss or uncomputable row.
  7. prompt.md answer-range (clusters C/E): discriminating blank-vs-0 rule — quoted-formula reproduction writes 0 for blank source; computed pivot leaves no-data cells truly empty.
  8. prompt.md answer-range (cluster G): range size is spec (per-row/per-group reading); never use the fill-target column as lookup key; "sort only column X" = in-place column sort.
  9. prompt.md answer-range (cluster F): "dataset"/"last row" guards resolve against source data extent; goal statement wins over paraphrased condition.
  10. prompt.md values (clusters B/E): formula strings MUST start with "="; CSE/array and _xlfn formulas banned (write literal); rewrite relative refs after row insert/delete; confirm reference cells numeric.
  11. prompt.md values (cluster D): coerce numeric-looking text before summing; write computed numerics as numbers.
  12. prompt.md values (cluster F): epsilon on computed float thresholds; "up to/through" inclusive; "today" = datetime.now(); every named lookup dimension in the key.
  13. prompt.md before-you-finish (cluster A): NEVER resubmit identical code; same output/error twice -> next reply must change code or inspect new data; verification wrong twice -> re-inspect raw data. (Strengthened the weak one-line seed rule.)
- Per change, EXPECTED effect + why safe:
  - Each rule traces to a diagnosed failing trace (see PROCESS.md CHECK lines: 254-34 row-1 exclusion, 80-42 max_row overrun, 31011 missing "=", 52216 CSE recalc, 45372 None-over-SUM, 58109 exclusive window, 51-12 exact float >=, 194-19 inverted key, 48983 blank-vs-0, 58949 ""-placeholder, 50768 transposed axes, 35742 path typo, 56786/54638 identical-resubmission loops). Flaky rules name the PASSING trial's choice (51-12 t2 epsilon, 32023 t1 datetime.now, 46121 t1 correct header row), so they convert coin flips, not passing behavior.
  - Safe for the 89 passing tasks: every rule describes what passing trials already do or adds an inspection step that cannot change output; no cand_0003 rule was deleted (one accidentally-replaced rule was restored in full).
  - NO skills/ edit, NO new braces, placeholders verified by script — this is the clean bisect of the wipeout confound.
- Building on prior RESULTS: cand_0003 ACCEPTED (+0.114) — its entire prompt is retained and only extended. cand_0001/0002/0004 all REJECTED at val=0.000 with whole-set wipeouts and a skills/ script package in common — I did NOT re-try any script/SKILL.md edit. cand_0004's prompt rules were never behaviorally measured (mechanical wipeout); this candidate re-ships their substance in prompt-only form, minus its script.
- Refuted hypotheses: "a helper script + SKILL.md rewrite is safe packaging" — refuted three times (cand_0001, 0002, 0004 all val=0.000 with everything broken). Never bundle a script with anything else until one runs clean.
- High-value clusters still not cracked: 433-47 (underdetermined allocation), 118-50 residual predicate ambiguity, 51090 (corrupt input XML) — unfixable without overfitting/environment change. If this candidate RUNS and is accepted, the script surface is exonerated ONLY if a future script-only candidate also runs; the actual wipeout cause is still unidentified (diff.patch of cand_0004 records only DIAGNOSIS.json — possibly the prompt/script edits never landed, i.e. a framework snapshot bug worth investigating via FRAMEWORK_IMPROVEMENTS).
- Plateau signal: cand_0003 accepted (+0.114); cand_0004 mechanical reject. Lever: prose rules across all diagnosed clusters, deliberately NOT the code lever, because the code surface has a 3/3 wipeout record.
- Cost-reduction opportunity: cost/latency not a declared objective; noted the anti-repeat-loop rule (E13) is also the biggest token-sink fix (20-30 identical rounds per locked trial).
- Focus next iteration: read this RESULT first. If ACCEPTED: try ONE minimal script again in isolation (bisect the wipeout cause for real), and check new traces for rule adoption (grep for epsilon usage, "=" formulas, no identical resubmissions). If REJECTED behaviorally: drop only the rules touching the broke={} tasks. If wiped out at 0.000: the prompt itself is mechanically invalid — bisect prompt.md against cand_0003 line by line.

> **RESULT (framework, measured):** ACCEPTED (new champion) · val=0.811 Δ=+0.023 · fixed={254-34, 80-42} · broke={250-20, 31628, 36097, 493-18, 56563, 66-24, 82-30} · unresolved={263-1, 2768, 31011, 35742, 37456, 39046, 42354, 45372, 46121, 46646, 48527, 50768, 51-12, 52216, 58109, 6239} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them).
<!-- cand_0005: ACCEPTED val=0.811 Δ=+0.023 -->
