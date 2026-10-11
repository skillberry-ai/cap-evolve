# Campaign status (plain language)

_Last updated: 2026-10-11 ~00:30 UTC — coordinator_

## What is known
- Repository main has not moved since the reviewed SHA `e3cb513`; campaign branch created from it.
- Provider access works from this host: the LiteLLM gateway serves Claude (opus-5-5, sonnet-5-5, haiku-4-5), GPT-5.5, GLM-5.3-Flash, DeepSeek-V4-Flash, Gemini-3.6-flash and gpt-oss-120b; RITS serves Qwen3.6-35B-A3B and gpt-oss-120b quickly; several RITS aliases are slow, time out or do not exist (see `protocol/model_registry.json` once written). Azure direct deployment names are still being discovered.
- All 64 supplied PDFs match their catalog SHA256.

## What is uncertain
- Whether the historical SpreadsheetBench / SkillsBench / SWE numbers can be recomputed from surviving artifacts (provenance audit running).
- Whether the historical spreadsheet scorer under-scores formula outputs (scorer audit running).
- Which competitors' official code can run against our endpoints.

## Running now
- literature/novelty lead, repository/algorithm auditor, provenance auditor, benchmark/scorer steward, methodology/statistics reviewer (subagents).
- Provider preflight (coordinator).

## Next
- File the GitHub campaign index + backlog issues; write the measurement protocol draft; select models after preflight; local smoke runs once the steward provides commands.
