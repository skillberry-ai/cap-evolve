# claude-code optimizer

Claude Code headless as the edit proposer.

    claude -p "<instructions>" --permission-mode acceptEdits [--model <id>]

run with `cwd=<workdir>`. `-p/--print` runs non-interactively and exits;
`--permission-mode acceptEdits` lets it write files without prompting.

- **Install:** https://docs.claude.com/claude-code
- **Auth:** a logged-in Claude Code session, or `ANTHROPIC_API_KEY`.
- **JSON / cost:** `--output-format json` makes the result a JSON object with
  `total_cost_usd`, `usage` (input/output tokens), and per-model cost under
  `modelUsage`. The runner appends this when called with `--json` and parses
  `total_cost_usd`. Add `--json-schema '<JSONSchema>'` (the runner forwards it
  when the row's json_flag contains `--output-format`) to also get
  `.structured_output` — useful for headless decision steps.

## What headless `-p` keeps and drops (the caveats)

The full agent loop, tools, and subagents all work under `-p`; what differs is
how prompts and budgets behave. Cap-evolve invokes exactly:

    claude -p {prompt_text} --permission-mode acceptEdits --model {model} \
      --output-format json --max-turns N --max-budget-usd N

- **`acceptEdits`** auto-approves file edits and common filesystem commands
  (`mkdir`, `touch`, `mv`, `cp`). Other shell commands and network requests
  still need an `--allowedTools` entry / `permissions.allow` rule, or the run
  aborts when one is attempted. Subagents inherit this mode and **cannot
  override it** to something weaker — good, since edits in the candidate workdir
  should never block on a prompt.
- **`--max-turns N`** caps total agentic turns and **`--max-budget-usd N`** caps
  spend; both are hard ceilings the CLI enforces and apply to the *whole* run
  including any subagents it spawns. Parallel fan-out spends the shared budget
  faster, so size the prompt's ambition to the cap.
- **No interaction:** `AskUserQuestion` / `ExitPlanMode` are unavailable, so the
  prompt must be self-contained — the agent can't ask for clarification.
- One iteration = one `claude -p` process. The agent does *all* its parallelism
  *inside* that single process via subagents (below); cap-evolve does not launch
  multiple `claude` processes per iteration.

## Use subagents to go parallel inside one iteration

*Verified against the subagents docs.* Each subagent runs in its **own context
window** with its own tool set and returns only a summary to the main agent —
so verbose trajectory text and dead-end exploration never bloat the main
context. The optimizer can be told (in its INSTRUCTIONS prompt) to:

- **Fan out exploration of trajectories + capability.** Spawn several read-only
  **Explore** subagents in parallel — e.g. one per failure-cluster or per
  capability file — to find recurring problems faster than one serial pass.
  Explore is the built-in read-only agent (Write/Edit denied) and runs on a fast
  model, so this is cheap. Phrase it as: *"Research the failures in clusters A,
  B, and C in parallel using separate subagents, then synthesize the root
  causes."*
- **One subagent per edit hypothesis or candidate tool.** Generate several
  **candidate edits in parallel** — one subagent drafts each hypothesis
  (different prompt wording, tool-doc fix, restructure, or — for the `tools`
  capability — a different **candidate code-bearing tool**: a validation/wrapper
  tool that enforces a rule then delegates, or a loop tool that collapses N calls
  into one, each with a real body). Then the main agent compares the returned
  diffs/rationales and **synthesizes the single best edit**, writing only that
  one. This turns "guess one edit serially" into "explore N edits, keep the best".
  Concretely: spawn one subagent per trajectory-failure cluster AND/OR one per
  candidate tool/edit hypothesis, explore in parallel, then synthesize and land
  exactly one edit.
- **Isolate high-volume work.** Delegate re-reading long rollouts or large logs
  to a subagent so only the relevant summary returns; keeps the main agent's
  budget focused on deciding and writing the edit.
- **Chain when steps depend.** diagnose → propose → self-review can each be a
  subagent in sequence (e.g. a read-only reviewer checks the drafted edit before
  it lands).

How to trigger it from the prompt: Claude auto-delegates based on task phrasing.
Explicit, parallel phrasing ("in parallel using separate subagents") is what
actually fans out. Independent investigations parallelize well; dependent ones
should be chained, not fanned out.

### Defining custom agent types headlessly

*Verified (`claude --help` shows `--agents <json>`; docs confirm the schema).*
Pass session-scoped agents inline — no files needed:

    claude -p "<instructions>" --permission-mode acceptEdits \
      --agents '{"edit-drafter":{"description":"Drafts one candidate edit to the capability and returns a diff + rationale. Use proactively, one per hypothesis.","prompt":"You propose a single targeted edit...","tools":["Read","Grep","Glob"],"model":"haiku"}}'

Useful frontmatter/JSON fields: `description` (drives auto-delegation — say "use
proactively"), `prompt` (system prompt), `tools` (allowlist; omit Write/Edit for
read-only explorers), `model` (route cheap exploration to `haiku`, keep `opus`
for the synthesis), `maxTurns`, and `isolation: "worktree"` (give a drafter an
isolated repo copy so competing edits don't collide). cap-evolve does not pass
`--agents` today, so to use custom types either bake them into the prompt as
behavioral instructions or add the flag via the `generic` optimizer escape
hatch / a project `.claude/agents/` dir.

## Caveats specific to fan-out

- **Results cost context.** When subagents finish, their summaries return to the
  main agent. Many subagents each returning detailed output can itself consume
  significant context and budget — ask each to return a *tight* summary, not raw
  dumps.
- **Background subagents auto-deny prompts.** A subagent run in the background
  uses only already-granted permissions and auto-denies anything that would
  prompt; under `acceptEdits` edits are fine, but a background subagent that
  needs a non-allowed Bash/network call will have that call fail. Keep such work
  in the foreground or pre-allow the tool.
- **Nested depth is bounded.** A subagent can spawn its own subagents, but depth
  is capped (a subagent at depth five gets no Agent tool). Don't design
  arbitrarily deep trees.
- **Shared budget.** All subagents draw on the single `--max-turns` /
  `--max-budget-usd` ceiling. Parallelism buys *latency*, not extra budget.

## Other headless knobs worth knowing

*Verified via `claude --help` unless noted.*

- **`--allowedTools "Bash,Read,Edit"`** / **`--disallowedTools`** — pre-approve
  or block specific tools (and `Agent(type)` to allow/deny specific subagent
  types). Use to let the agent run the eval/test command without it aborting.
- **`--bare`** — skips hooks, plugins, MCP autodiscovery, and CLAUDE.md for a
  reproducible, faster start; pass context explicitly with
  `--append-system-prompt` / `--add-dir` / `--agents`. Recommended for scripted
  runs that must behave identically on every machine. (Docs note it will become
  the `-p` default.)
- **`--append-system-prompt "<text>"`** — inject optimizer-specific guidance
  (e.g. "always draft >=2 edit hypotheses in parallel before writing") without
  replacing Claude Code's default behavior.
- **`--fallback-model <m>`** — auto-fall-back when the primary model is
  overloaded (only with `--print`); avoids a wasted iteration on transient
  capacity errors.
- **Background Bash at exit:** a background task the agent starts is killed ~5s
  after the final result, so a stray watcher won't hang the iteration.

### Beyond a single process (not used by cap-evolve, noted for completeness)

*Verified in docs.* **Background agents** (`claude agents`, `/en/agent-view`)
run many independent *sessions* and monitor them from one place, and **agent
teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, with `SendMessage`) let
sessions communicate. These operate across sessions, whereas cap-evolve runs one
`claude -p` per iteration — so prefer **subagents** (in-session, parallel) for
intra-iteration speedups. `/fork` subagents (inherit full conversation, reuse
the prompt cache) are an option for trying several approaches from the same
starting point but are gated behind `CLAUDE_CODE_FORK_SUBAGENT=1` and marked
experimental.
