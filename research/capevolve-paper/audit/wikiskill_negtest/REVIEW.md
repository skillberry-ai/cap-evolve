# Review of the WikiSkill s0 gold-isolation negative test (commit 1865ca56b)

Reviewer: provenance-auditor. Read-only except this file. Evidence re-derived from `runs/E10/wikiskill/s{0,1,2}/study` and the SpreadsheetBench data trees.

## Verdict
1. **Flagged items: all 343 are genuine false positives.** Accept the audit.
2. **Narrowed marker set: sufficient for what WikiSkill s0 can reach (verified_400), but it has three gaps** for other SpreadsheetBench gold locations used in this campaign. None changes the s0 result. Fix them before the test is reused for other baselines or the 912 tier.
3. **Overall: the s0 pass stands.** An independent rescan with a wider marker set also finds nothing real in the staged inputs of s0, s1 and s2.

## 1. Flagged-item audit (`negative_test.flagged_audit.json`)
- 339 items matched `_output.xlsx`. I re-checked every context with a regex for the exact shape `/mnt/data/outputs/<task>_<n>_<hash>/1_<task>_output.xlsx`; all 339 match. That is the agent's own output path in its transcript code, which is the writable `outputs/` dir that `make_agent_view.py` creates, not a gold file. Gold names in verified_400 are `1_<id>_golden.xlsx` (395 tasks) and bare `golden.xlsx` (5); `_output.xlsx` never occurs among them.
- 4 items matched bare `gold`. All four are the same task (40892, proposer traces of iterations 001 to 004) and all four contexts are the colour value `'Gold'` printed from the workbook (`['Red','Gold','Red',...]`, `B3: Gold`). Cell data, not a path.
- Weakness of the audit file: it records the first match per (file, marker), so a real hit later in the same file would be masked. I closed that gap with the independent rescan below.
- Procedural note: markers were dropped after seeing hits. That is fine here because each drop is justified by the evidence above, but the safer pattern is to keep the broad marker and whitelist the specific benign context (path shape, quoted cell value). The first-run raw file and audit are kept, which makes the change reviewable.

## 2. Does the narrowed set still catch the real gold locations?
Real gold in this campaign (from `bench/data/extracted/*`, `make_agent_view.py`, `sb_eval_lib.py`):

| gold location | caught by narrowed set? |
|---|---|
| `1_<id>_golden.xlsx`, bare `golden.xlsx` (verified_400, 400 tasks) | yes, `golden` (case-insensitive) |
| tree `bench/data/extracted/spreadsheetbench_verified_400/...` | yes, `spreadsheetbench_verified_400` and `/data/extracted` |
| env var `SPREADSHEETBENCH_GOLD_DIR` | yes, `SPREADSHEETBENCH_GOLD` and `gold_dir` |
| `{n}_{id}_answer.xlsx` (912 and sample_200 tiers) | **no** |
| trees `all_data_912_v0.1`, `sample_data_200` | partly: only under `/data/extracted` |
| host cache `~/.cache/capevolve-ci/spreadsheetbench-data/...` (where optimizer sessions read golds in earlier runs) | **no** unless the path also contains `spreadsheetbench_verified_400` |
| sealed-test artefacts (`reused_seed_run`, `rollouts/test`, `final.json`, `test_per_task`) | **no** (separate leak found in the gold scan) |
| `gold.xlsx`, `solution.xlsx`, `/gold/` | not real SpreadsheetBench names; harmless extras |

The authoritative gold-name pattern is the one `make_agent_view.py` uses to withhold files: `(_answer|_golden|^golden|^answer)`. The narrowed list should be a superset of it. Also note that in the CI sandbox gold sits in the same directory as the input (`/mnt/data/spreadsheet/<id>/`), so a directory marker cannot discriminate; names are the only usable signal, which makes the `_answer` gap matter.

Recommended additions: `_answer.xlsx`, `answer.xlsx`, `all_data_912`, `sample_data_200`, `spreadsheetbench-data`, `capevolve-ci`, `reused_seed_run`, `rollouts/test`, `test_per_task`.

## 3. Independent rescan (my check, not the author's)
Scanned every file under `study/**/input/` of s0 (453 files), s1 (343) and s2 (340) with: `golden`, `answer.xlsx`/`_answer.xlsx`, `SPREADSHEETBENCH_GOLD|GOLD_DIR`, `data/extracted|spreadsheetbench_verified_400|all_data_912|sample_data_200|spreadsheetbench-data|capevolve-ci`, `make_agent_view|agent_view_verified400`, `reused_seed_run|rollouts/test|test_per_task|sealed_test|splits_sbx`, and gold-as-concept phrases.
- Real-marker hits: **0** in all three seeds.
- Remaining hits: the `'Gold'` cell value (task 40892) and the phrase "the 'Desired outcome' sheet is the ground truth" in task 250-20, which is an agent comment about a sheet inside the task, not a gold file.
- Split leakage: every staged trace is a train id (352, 264, 264), no file is named after a val or test id, and a looser task-id regex finds no val or test id in any file. The test's own check (`Task {i}\n`) is format-specific and would miss other formats; my check does not depend on that format.
- Agent view: `agent_view_verified400` has 0 golden/answer files out of 935; the gold tree holds 395 `*_golden.xlsx` + 5 `golden.xlsx` separately.
- The committed `negative_test.json` and script are byte-identical to the copies in `runs/E10/wikiskill/s0`.

## 4. Scope limits to state in the paper
- The probes exercise proposer-mode `read_file` and the `bash` tool on a proposer role (refused because the tool is not offered). The role with a shell is `spreadsheet` mode (the target agent), which is not probed here; in this campaign target rollouts go through `sb_eval_lib` with the gold-free agent view, which I verified above, so that is the control that matters.
- The test shows no gold or split leakage into the staged files; it cannot show absence of gold-derived facts distilled into text, which is the issue seen in the Opus-optimizer runs.
- Only s0 is attested by the committed result; s1 and s2 pass my independent scan but have no committed negative-test record.

---

# Addendum: review of the v3 whitelist (commit 3ee2ddd7f)

## Verdict
The v3 test is sound. Every whitelist reason is narrow enough that it cannot hide a gold file name, gold tree or sealed artefact, and each of the 2274 + 1241 + 1378 recorded matches (s0, s1, s2) is correctly whitelisted on re-inspection. W4 is legitimate. Recommended hardening items are small and listed at the end.

## What I checked
- Re-read `negative_test_v3_whitelist.py` and all three result files (every occurrence is logged, with offset and context). All 5 pass, 0 unwhitelisted, 0 val or test ids, 8/8 probes refused.
- All nine markers I asked for are present and **matched zero times** in s0, s1 and s2 (only `gold` and `_output.xlsx` ever match). So no `golden`, `_answer.xlsx`, `answer.xlsx`, tree names, cache path or sealed-artefact string occurs in any staged input.

## Reason by reason
| reason | scope in code | count s0/s1/s2 | verdict |
|---|---|---|---|
| W0 `gold-free` / `gold_free` label | 10-char window around the match | 352/264/264 (one per trace, always `scorer_feedback_gold_free`) | narrow in practice. The check is not tied to a marker, but the only marker that can occur inside that label is `gold`; golden and answer names cannot. |
| W1 agent's own `/mnt/data/outputs/<task>_<n>_<hash>/1_<task>_output.xlsx` | only marker `_output.xlsx`, full path regex, first occurrence after the path | 1908/944/1103 | safe: `_output.xlsx` is not a gold name in any tier, and the gold markers can never be whitelisted by W1. |
| W2 `1_<task>_output.xlsx` variants and the `<id>` placeholder | only marker `_output.xlsx`, filename must end at the match | 1/14/5 | safe for the same reason. I read all 20 contexts: truncated paths, `os.path.join` forms, and the skill text "e.g. `/mnt/data/outputs/<task>/1_<id>_output.xlsx`". |
| W3 task 40892 colour cell "Gold" | marker `gold` only, file name `40892.md`, pattern in a 160-char window | 12/19/5 | correct on all 36 contexts (`['Red','Gold',...]`, `B3: Gold`, `Jumper Gold`). Residual looseness: it is window-based, so a real `gold` word within 100 chars of a colour cell in that one file would be masked. The `golden` marker is not covered by W3 and still fires independently. Low risk; tighten by requiring a capital `Gold` as a whole word inside quotes or after `: `. |
| W4 wiki prose "described the gold" | marker `gold` only, exact file name and exact 18-char phrase at that offset | 0/0/1 | legitimate, see below. |
| W5 tail after the 15000-char truncation marker | only marker `_output.xlsx`, within 12 chars of the marker | 1/0/0 | safe (filename tail only). |

Because W1, W2 and W5 apply only to `_output.xlsx`, and W3 and W4 only to `gold` in named files, no whitelist can suppress `golden`, `answer.xlsx`, `_answer.xlsx`, `answer_key`, `ground_truth`, `reference_path`, `SPREADSHEETBENCH_GOLD`, `all_data_912`, `sample_data_200`, `spreadsheetbench-data`, `capevolve-ci`, `reused_seed_run`, `rollouts/test`, `test_per_task` or `spreadsheetbench_verified_400`. Those markers are all unconditional.

## W4 in detail
The sentence is in `wiki/patterns/ambiguous-blank-spec-na-vs-empty-string.md` (s2, iteration 003 proposer input): "the explicit note about the empty string described the gold". I read the whole note. It cites task 58949 (a train id; val and test do not contain it), and its numbers ("12 of 32 cells", "20 cells hold a value where the expected output has none") are verbatim from the trace's `scorer_feedback_gold_free`: "COVERAGE: ... the expected output has a value in 12. MISMATCH: 20 of 32 cell(s) ... hold a value where the expected output has none". The note contains no cell value, path or file name from the gold. "The gold" there is the maintainer's inference that blanks are the expected missing marker, derived from the "expected has none" class.

## Is that feedback the campaign's registered gold-safe channel, and does it leak values?
- Yes. It is `score.feedback` produced by the spreadsheetbench adapter's `_localize_failure` and `_mismatch_classes` (`templates/adapters/spreadsheetbench/adapter.py`), recorded as the protocol channel in `protocol/scorer_audit.md` ("per-range counts/types of mismatches (not values) to the optimizer"). The docstring states the gold-safety contract: three signals open the gold, each is a count, a type or a category, and "No cell VALUE is ever emitted". The contract is asserted by `core/tests/test_spreadsheetbench_failure_localization.py::test_no_gold_value_leaks_through_the_mismatch_note`, which I ran: passes. The only literal that can appear (`#N/A`) is the agent's own text.
- It does disclose categorical facts about the gold, by design and identically for every arm: the expected fill count per range, whether expected cells are empty, numeric direction (lower or higher), text-vs-number type, prefix or extension relation, whether the expected value is the cell's own original input, and whether an expected value is an Excel error marker. Papers should list these explicitly as the optimizer-visible gold signal; they are what the wiki note used.
- Caveat for the scope of this test: it scans staged files for names and paths. A value leak would not show up as a marker, so the unit test above and the "no values" property of the adapter are what carry that claim. I found no literal gold value in the staged files I read (W4 note, the contexts above).

## Hardening suggestions (none blocking)
1. Tie W0 to marker `gold` explicitly.
2. Tighten W3 to whole-word capital `Gold` inside quotes or after `: ` in `40892.md`, and fail if a lowercase `gold` appears in that file.
3. For W4, also require that the file lies under `wiki/` and bind the phrase to a hash of the sentence, so a later wiki rewrite re-triggers review.
4. s1 and s2 were still running at scan time; re-run the v3 script after they finish and re-check that no new unwhitelisted reason appears (the whitelist was extended after seeing hits, W2/W4/W5, so a late new context should be reviewed rather than auto-extended).

## Addendum 2: W3 "Jumper Gold" row condition (commit 115cffdb3)
Checked: acceptable. Task 40892 asks the agent to extract the colour named in each column-A cell ("Dress with red details" -> "Red"; allowed colours are in column D). The row in the s1 trace is `1  Jumper Gold ... Gold`: the product name "Jumper Gold" and the extracted colour "Gold", both workbook data printed by pandas without quotes (s0 and s2 show the same value quoted). Neither is a gold-answer reference. The condition is still narrow: it applies only to marker `gold` in a file named `40892.md`, requires a whole-word capital `Gold` (a lowercase `gold` or `Golden` is never whitelisted, and `golden` is a separate unconditional marker), and the line must contain `Jumper Gold`, quoted, or follow `: `. The refreshed s0, s1, s2 records still pass (2274, 1241, 1378 matches, 0 unwhitelisted). No further action.
