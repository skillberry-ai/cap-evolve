# opencode optimizer

opencode headless as the edit proposer.

    opencode run --dangerously-skip-permissions [-m provider/model] "<instructions>"

run with `cwd=<workdir>`. `opencode run` is the headless mode (bare `opencode` is
the TUI); `-m provider/model` pins the model.

- **Install:** https://opencode.ai/docs/cli
- **Auth:** per opencode's provider config.

## Native skills, instructions, and subagents

- **Native skills:** `.opencode/skills/<name>/SKILL.md` (project paths walked cwd→git
  root). opencode also auto-reads the **Claude-compatible** `.claude/skills/<name>/SKILL.md`
  and the `.agents/skills/` alias. cap-evolve copies the capability + diagnose skills into
  `.opencode/skills/`. Skill activation is gated by `permission.skill`, auto-approved under
  `--dangerously-skip-permissions`.
- **Always-on instructions:** `AGENTS.md` (auto-read, walked up from cwd; `CLAUDE.md` is a
  fallback used only when no `AGENTS.md` is present in that dir). cap-evolve writes its
  pointer into `AGENTS.md`. The `instructions` array in `opencode.json` can add more files.
- **Subagents / parallelism:** primary vs subagent model. Subagent built-ins **General**
  (explicitly suited to running multiple units of work in parallel), **Explore** (read-only
  code), **Scout** (read-only docs); custom agents in `.opencode/agents/<name>.md` with a
  `mode` (`primary`/`subagent`/`all`). Invoked via `@agent`, auto-delegation, or the **Task
  tool** (spawns subagent child sessions, gated by `permission.task`). `opencode run --agent
  <name>` selects an agent. Subagents are session-isolated (concurrent child sessions); **no
  documented git-worktree isolation** and no explicit concurrency-limit knob. **Use** the
  General subagent / Task tool to analyze failure clusters in parallel, then merge to one
  candidate.
