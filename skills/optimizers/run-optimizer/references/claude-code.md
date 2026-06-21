# claude-code optimizer

Claude Code headless as the edit proposer.

    claude -p "<instructions>" --permission-mode acceptEdits [--model <id>]

run with `cwd=<workdir>`. `-p/--print` runs non-interactively and exits;
`--permission-mode acceptEdits` lets it write files without prompting.

- **Install:** https://docs.claude.com/claude-code
- **Auth:** a logged-in Claude Code session, or `ANTHROPIC_API_KEY`.
- **Native skills:** `.claude/skills/<name>/SKILL.md`; agents: `.claude/agents/`; instructions: `CLAUDE.md`. cap-evolve copies the capability + diagnose skills there and writes a pointer into `CLAUDE.md` so headless `-p` runs load them natively.
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

Run the iteration as **TWO explicit fan-out phases** — diagnose in parallel, then
implement in parallel — with a dedup/merge step on the main agent between and after.
This is the primary parallel pattern and the strong default for an iteration that
must address ALL recurring clusters at once.

**Phase 1 — DIAGNOSE in parallel (read-only).** Spawn one read-only **Explore**
subagent per trajectory-group (e.g. one per failure cluster, per trajectory
directory, or per capability file). Each returns a **tight issue list** — the
specific rules violated and which EXISTING tool/prompt-rule owns each — not raw
trajectory dumps. Explore is the built-in read-only agent (Write/Edit denied) on a
fast model, so this is cheap. The **main agent then DEDUPS the returned issues into
clusters** (collapsing the same root cause seen across groups) so Phase 2 gets one
issue per distinct fix. Trigger phrasing: *"Diagnose the failures in trajectory
groups A, B, and C in parallel using separate read-only Explore subagents; each
returns a tight list of violated rules and the existing tool or prompt rule that
owns each. Then dedup all issues into clusters."*

**Phase 2 — IMPLEMENT in parallel (one edit-subagent per ISSUE).** Spawn one
edit-subagent per deduped ISSUE, **each in its own git worktree**
(`isolation: "worktree"`, below) so competing edits don't collide while drafting.
Tell each subagent to PREFER **editing the EXISTING tool's code body** to enforce
the rule deterministically (an in-body precondition / normalization / actionable
refusal on the tool that already owns the rule) — **not** merely adding a new tool
or rewording docstrings, and never a one-task patch. (Adding a new tool, a loop
tool that collapses N calls into one, or a composite WRITE tool — each with a real
body — is for the cases where no existing tool owns the rule.) The **main agent
then MERGES all per-issue edits into ONE coherent candidate**, resolving overlap so
the combined diff applies cleanly with **no conflicts**, and writes that single
merged candidate. One iteration thus fixes every cluster, not just the biggest —
while each edit stays general because it was reasoned about in isolation. Trigger
phrasing: *"Spawn one edit-subagent per issue cluster, each in its own worktree;
each PREFERS editing the existing tool's code body to enforce its rule in code (not
just adding a tool or rewording docs) and returns a general edit; then merge all
edits into a single candidate with no conflicts."*
- **One subagent per edit hypothesis or candidate tool (explore-then-pick).** When
  a *single* cluster has several plausible fixes, generate the **candidate edits
  in parallel** — one subagent drafts each hypothesis (different prompt wording,
  tool-doc fix, restructure, or a different candidate code-bearing tool, each with
  a real body). Then the main agent compares the returned diffs/rationales and
  **synthesizes the single best edit** for that cluster. This turns "guess one edit
  serially" into "explore N edits, keep the best", and composes with the
  per-cluster pattern above (best-of-N within a cluster, then merge across clusters).
- **Isolate high-volume work.** Delegate re-reading long rollouts or large logs
  to a subagent so only the relevant summary returns; keeps the main agent's
  budget focused on deciding and writing the edit.
- **Chain when steps depend.** diagnose → propose → self-review can each be a
  subagent in sequence (e.g. a read-only reviewer checks the drafted edit before
  it lands).

How to trigger it from the prompt: Claude auto-delegates based on task phrasing.
Explicit, parallel phrasing ("in parallel using separate subagents") is what
actually fans out. The two phases are sequenced (Phase 2 depends on Phase 1's
deduped clusters), but each phase fans out internally; use the per-phase trigger
phrasings above. Independent investigations within a phase parallelize well;
dependent steps across phases should be chained, not fanned out together.

> Generic note: this is Claude Code's realization of the cap-evolve flow where one
> iteration addresses ALL failure clusters at once via TWO fan-out phases (Phase 1
> diagnose in parallel → dedup into clusters; Phase 2 implement in parallel, one
> edit-subagent per issue → merge into one candidate). Every other optimizer's
> reference file (`./guidance/optimizer/<name>.md`) should document its OWN
> equivalent two-phase parallelism / isolation / merge features (or note their
> absence) — including whatever it supports for a read-only diagnose fan-out and an
> isolated implement fan-out — so the authored INSTRUCTIONS can lean on what that
> agent actually supports.

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
