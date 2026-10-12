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
