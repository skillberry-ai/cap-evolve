# openclaw optimizer

OpenClaw as the edit proposer. OpenClaw's headless CLI flags are less
standardized than claude/codex/gemini, so this row reads the command from the
environment:

```bash
export CAPEVOLVE_OPENCLAW_CMD='openclaw run --workspace {workdir} "{prompt_text}"'
```

- **Install / auth:** per your OpenClaw build. Verify the headless flags against
  your installed version.

## Native skills, instructions, and subagents

OpenClaw's native skill/instruction mechanism is **UNVERIFIED**. Web evidence is thin and
self-contradictory; it is best read as an orchestrator that *drives* Claude Code as a
managed subprocess (NOT a Claude Code fork), so it does not automatically inherit
`.claude/skills/` conventions. Claimed-but-unconfirmed: `SKILL.md`-style skills under a
workspace/home dir (e.g. `~/.openclaw/workspace/skills/`), background-worker "subagents",
and reading both `CLAUDE.md` and `AGENTS.md` at repo root — none authoritatively confirmed.

Because there is no reliable native skills path, the registry leaves `skills_dir` /
`instructions_file` **blank** for openclaw, and cap-evolve falls back to its guaranteed
channel: the capability + diagnose skills under `./guidance/` plus an explicit pointer in
the `./INSTRUCTIONS.md` prompt. Verify your installed build's actual conventions before
relying on any native placement; if confirmed, set the two registry fields for your build.
