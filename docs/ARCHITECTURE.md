# Architecture

cap-evolve is a library of Agent Skills over a tiny pure-stdlib core (`core/cap_evolve`).
The pipeline is:

```text
intake → implement-and-check → baseline → algorithm → finalize → report
```

## The phases

- **intake** — does the whole benchmark integration *before any budget is spent*. It
  interviews you (or reads your brief), installs the benchmark, and wires the **adapter**
  (`tasks` / `run_target`-or-`run_batch` / `score`), the **trajectory** path
  (`adapter.trajectories(split)` → the runner's native traces), the optional batched
  `run_trials` fast path, and `capability_sources` (the data-model/types files the tools
  import). It then authors a **capability-scoped** optimizer prompt
  (`optimizer/INSTRUCTIONS.md`). Missing NEEDED inputs are asked for, never fabricated.
- **implement-and-check — the HARD GATE.** `cap-evolve check` refuses to proceed until
  every required adapter method is real and `score()` is deterministic, so no spend
  happens against a stub.
- **baseline** — freezes the seeded train/val/test split (written once; **test sealed**)
  and scores the unmodified seed on val: the candidate every iteration must beat.
- **algorithm** (`hill-climb` / `gepa` / `skillopt`) — each iteration: **diagnose** failing
  val traces into failure clusters → the **optimizer proposes** a large, multi-part edit →
  the candidate is **evaluated** on val (each of N trials gets its own seed, so pass^k
  measures real variance) → a **paired significance gate** (Δ > k·SE, val-only) accepts or
  rejects → the iteration is git-committed and memory updated.
- **finalize** — scores the best candidate on the **sealed test split exactly once** (the
  run dir enforces the seal).
- **report** — writes `report.md` and a self-contained `dashboard.html`.

See [`HONEST_EVAL.md`](HONEST_EVAL.md) for the splitting / gating / sealing guarantees and
[`ADAPTER_CONTRACT.md`](ADAPTER_CONTRACT.md) for the adapter.

## What the optimizer receives each iteration

The harness assembles a **capability-scoped** working dir per iteration, then runs your
chosen coding-agent CLI in it:

- **The selected capability skill(s)** — both as `./guidance/<cap>/` *and* placed natively
  in the agent's own skills dir (e.g. `.claude/skills/`) so a headless agent auto-loads
  them. Each carries a "What you can change here" menu and edit boundaries.
- **The diagnose method** (`./guidance/diagnose/`) — how to cluster failures into a
  reflective dataset (per failing task: Inputs, Generated Outputs, Feedback).
- **Only the current best step's full trajectories** (`./trajectories/`) — the runner's
  verbatim traces of the candidate it builds on, never the seed + every rejected attempt.
- **Supporting sources / data model** (`./guidance/sources/`) — the `capability_sources`
  files, copied verbatim so new tool code is written against the real types.
- **Per-task IMPACT of prior candidates** — which task ids each prior edit BROKE (were
  passing) and FIXED, plus the **currently-passing set to protect** — causal feedback so a
  known regression is never re-introduced.

## Cross-iteration files (clean ownership)

| File | Owner | Purpose |
|---|---|---|
| `LEDGER.md` | framework | FACTS: every iteration's outcome + the exact tasks it broke/fixed |
| `JOURNAL.md` | optimizer | append-only HANDOVER across the run (tried / worked / regressed / refuted / focus-next) |
| `PROCESS.md` | optimizer | EXPLAINABILITY, snapshotted per candidate |
| `RUNMAP.md` + `prior_iterations/` | framework | a manifest plus every prior iteration's PROCESS.md and capability diff, for real prior-work access |

Because it sees all failure clusters, the protect-set, and the prior causal impact at once,
the optimizer produces **one bold, multi-part candidate per iteration that addresses every
cluster without regressing the wins** — not a one-line tweak.

## What the optimizer can change

The **prompt** and the **tools** are equally fair game:
- **Prompt** ([`system-prompt`](../skills/capabilities/system-prompt/SKILL.md)) —
  rewrite/consolidate/add rules, add examples, tighten the output contract, but **never
  drop a needed rule** (change / consolidate / add, don't delete).
- **Tools** ([`tools`](../skills/capabilities/tools/SKILL.md)) — add/replace/wrap tools,
  **edit tool CODE** for deterministic enforcement, improve docs **and return values**
  (actionable errors), add loop/workflow/composite tools, and **swap via a safe wrapper —
  never bare-remove** a primitive. A tool body the model cannot skip beats a sentence it
  can forget; a knowledge-gap failure still belongs in the prompt.

## Speed + observability

All N trials of a candidate run in **one concurrent pass** when the adapter implements
`run_trials(tasks, ctx, *, n_trials, base_seed)` (per-trial persistence and pass^k/SE are
byte-for-byte unchanged). The **live dashboard** shows intake cost/time, per-iteration
optimizer & runner cost + time, the cumulative-best stair, a tasks × iterations pass/fail
heatmap, per-iteration git diffs, the lineage tree, and gate decisions.

## Skill library

18 skills over the core. Extending is one folder or one registry row — see
[`EXTENDING.md`](EXTENDING.md).

| Component | Skills |
|---|---|
| orchestrate | `orchestrate` · `using-cap-evolve` |
| phases | `intake` · `implement-and-check` · `baseline` · `evaluate` · `diagnose` · `gate` · `finalize` · `report` |
| capabilities | `system-prompt` · `skill-package` · `tools` · `mcp-tool` |
| algorithms | `hill-climb` (`--focus all\|cyclic\|hardest-first`) · `gepa` · `skillopt` |
| optimizers | `run-optimizer` + `optimizers/registry.yaml` (14 backends incl. `mock`) |

**Claude Code plugin:** `claude --plugin-dir ./plugins/cap-evolve` exposes every skill as
`/cap-evolve:<skill>` and arms honesty **hooks** (PreToolUse denies edits to the sealed
test/gold; Stop/SubagentStop block finishing until `cap-evolve check` and the gate are
green) — all in core-owned scripts, never in editable skill markdown.
