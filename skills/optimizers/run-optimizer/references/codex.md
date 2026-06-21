# codex optimizer

OpenAI Codex CLI headless as the edit proposer.

    codex exec --sandbox workspace-write [-m <model>] "<instructions>"

run with `cwd=<workdir>`. `codex exec` is the non-interactive subcommand;
`--sandbox workspace-write` permits file writes with no network (`--full-auto` is
deprecated in favor of it).

- **Install:** https://developers.openai.com/codex
- **Auth:** `codex login`, or `OPENAI_API_KEY`.
- **JSON / cost:** `--json` emits a JSONL event stream; the runner parses the last
  JSON line for `total_cost_usd` / `usage` when called with `--json`. Add
  `--output-last-message <file>` to also capture the final assistant message on
  disk (handy when you want the proposer's summary, not just the diff).

## Native skills, instructions, and subagents

- **Native skills:** `.agents/skills/<name>/SKILL.md` (the agentskills.io convention —
  NOT `.codex/skills`). Discovery is path-based (scans cwd up to repo root); there is no
  CLI flag to add a skills dir. cap-evolve copies the capability + diagnose skills there.
- **Always-on instructions:** `AGENTS.md` (auto-read by `codex exec`; `AGENTS.override.md`
  blocks parent leakage). This is the doc-guaranteed headless channel — cap-evolve writes
  a pointer into it because skills use progressive disclosure.
- **Subagents / parallelism:** Codex natively supports **concurrent subagents** in
  `codex exec` (config `[agents]`: `max_threads` default 6, `max_depth` 1,
  `job_max_runtime_seconds` 1800; built-ins `default`/`worker`/`explorer`; custom agents
  as TOML in `.codex/agents/`). `spawn_agents_on_csv` fans out one worker per CSV row. No
  documented git-worktree per-subagent isolation. **Use this** to analyze each failure
  cluster in parallel (one worker per cluster), then have the parent consolidate the
  per-cluster edits into ONE candidate.
