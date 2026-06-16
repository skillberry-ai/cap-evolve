# CapEvolve v2 — Architecture & Redesign Plan

> Goal: make CapEvolve the best open-source platform for **agent-capability
> optimization** — general across algorithms × optimizers × capabilities, with an
> *abstract, extensible, deterministic* process where every step runs standalone
> (or as a slash command) **and** fully automatically. Grounded in a deep study of
> **evo**, **superpowers**, Anthropic's **skill-creator**, **GEPA**, and **SkillOpt**
> (see `docs/research/` notes). We adopt their *patterns*, not their code.

## 0. The one-sentence shape

**A deterministic Python ENGINE owns everything honesty- and state-critical
(splits, gate, seal, stats, run-state, candidate graph, parent-selection, eval
cache, backends); a markdown SKILL layer drives the engine via CLI verbs and
contains only the *agent-facing* judgment (what to optimize, how to reflect,
which edit to propose).** The engine never imports an agent; the agent never
re-implements scoring/gating. This is evo's split, applied to capability
optimization.

```
            ┌─────────────────────────── SKILLS (markdown + thin run.py) ──────────────────────────┐
 user / →   │  router → intake → implement-and-check → baseline → <algorithm> → finalize → report  │
 orchestr.  │  each: standalone slash command  +  orchestrator-callable  +  headless JSON           │
            └───────────────────────────────────────┬──────────────────────────────────────────────┘
                                                     │ CLI verbs (deterministic)
            ┌────────────────────────────────────────▼─────────────────────────────────────────────┐
 ENGINE     │ splits(seal-on-success) · gate(paired sig) · stats(real-trial pass^k) · rundir(atomic) │
 core/      │ graph(tree of candidates) · selection(registry) · backends(protocol) · eval-cache      │
 cap_evolve │ adapter contract: tasks / run_target(seed) / score / materialize + live(ctx)           │
            └────────────────────────────────────────────────────────────────────────────────────────┘
```

## 1. What's wrong today (from the self-assessment)

**Engine (mostly good, three real leaks):**
- `pass^k` is decorative for LLM agents — no per-trial seed is threaded, so a runner
  that hardcodes a seed (tau2 uses 42) produces identical trials → stderr 0 → gate
  silently degenerates to "any Δ>0". **High.**
- `consume_test()` flips the seal *before* scoring — a transient finalize crash
  permanently burns the headline number. **High.**
- `apply(candidate_dir)` is a global side-effect (and `check` calls it), so no two
  candidates can be evaluated concurrently and the safety check mutates the host. **High.**
- `gate.decide` treats candidate & current as *independent* samples though they share
  the same val tasks (a paired test is correct and far more powerful); infra-vs-capability
  failures are classified by substring-matching feedback prose (drops real "error" bugs);
  state.json is non-atomic; spec YAML fallback silently mis-parses block lists.

**Skills (good prose, bad engineering — a copy-paste lattice):**
- 8 optimizer skills are near-identical wrappers differing only by a command string —
  `generic` already subsumes them. → **one runner + `optimizers/registry.yaml`**.
- 3 hill-climb algorithms are byte-identical but a `FOCUS` constant (two keep the wrong
  docstring). → **one `hill-climb` skill with `--focus`**.
- `tools` and `mcp-tool` duplicate 108 lines differing by one policy line (with a
  docstring that's false for one). → **shared tool-surface module**.
- `_bootstrap.py` copied into 25 skills; `check.py` is an import-smoke no-op in ~18;
  `meta.yaml` ↔ frontmatter dual source of truth (already drifted); manifest validates
  nothing (dead `COMPONENTS`, singular/plural mismatch).
- `diagnose` mislabels `Inputs` with the task id and clusters on "first 6 words".
- `orchestrate` *claims* DAG validation but just prints a hardcoded list; intake +
  implement-and-check are not part of `cap-evolve run` at all.

## 2. Target architecture

### 2.1 Engine (core/cap_evolve)
| module | change |
|---|---|
| `adapter.py` | `run_target(task, ctx, *, seed)` / `run_batch(tasks, ctx, *, seed)`; split `apply` → pure `materialize(dir, edits)` + `live(dir)` **context manager** yielding a `ctx` the runner uses. Single live slot is no longer assumed. |
| `stats.py` | unchanged math; now fed real per-trial variance. |
| `gate.py` | add **paired** significance mode (per-task Δ vs its own SE) as default; emit a `gate_warning` event when SE collapses to 0 instead of silently acting "strict". |
| `splits.py`/`rundir.py` | **seal-on-success** (`reserve_test()`+`commit_test()`); **atomic** writes (`tmp`+`os.replace`) + advisory lock; event log is the source of truth, state.json a derived cache. |
| `graph.py` *(new)* | persisted candidate tree `{root,next_id,nodes:{id→{parent,children,status,val,test,gate,dir,hypothesis,epoch,created_at}}}`; `update_node(run_dir,id,mutator)` locks+atomic-writes; `frontier(graph)`=gated leaves w/ no live child. |
| `selection.py` *(new)* | registry-of-pickers (`STRATEGIES` data + `PICKERS` callables): `best`/`top_k`/`epsilon_greedy`/`softmax`/`pareto`/`pareto_per_instance`; `pick(cands,strategy,seed)→(ranked,seed)` logs the seed. Params declared as data → drives validation **and** dashboard picker. |
| `backends/` *(new)* | `Backend` Protocol (`allocate_candidate_dir(ctx)`, `discard`, `reset`) + `_construct_backend(name,cfg)` + precedence `load_backend`. Default `LocalDirBackend` = today's snapshot. (worktree/sandbox later, lazy-imported.) |
| `cache.py` *(new)* | `(hash(candidate files), task_id) → reward/feedback` eval cache in the run dir; checked before a rollout. |
| `types.py` | `Rollout.error` becomes the *only* infra signal (remove substring `_UNCONTROLLABLE`); `Candidate.components` (editable files / md sections) used by reflection + merge. |
| `cli.py` | `run` sequence becomes **intake → check → baseline → <algorithm> → finalize → report**, built from the manifest + spec (not a hardcoded list); add verbs `frontier`, `scratchpad`, `report`, `dashboard`. |

### 2.2 Skill library (collapse the lattice; raise the bar)
- **One** `optimizers/run-optimizer` skill + `optimizers/registry.yaml`
  (`name → {command_template, env_keys, install_url, auth_notes, json_flag}`). Per-CLI
  prose becomes a short `references/<name>.md`. Adding an optimizer = one YAML row.
- **One** `algorithms/hill-climb` skill (`--focus all|cyclic|hardest-first`) replacing the
  three clones. Keep `gepa` and `skillopt` as genuinely-distinct sibling skills.
- Shared `cap_evolve._bootstrap` (importable) replaces 25 copies; shared
  `capabilities/_tool_surface.py` for `tools`/`mcp-tool`.
- Every `check.py` asserts a **behavioral** contract (gate refuses train; baseline freezes
  a seeded split; diagnose emits a well-formed reflective dataset) via a shared check harness.
- `meta.yaml` is the **sole** source of name/component/description; `build_manifest.py`
  validates component ∈ vocab, needs/provides spelling, and that entry/abstract/check files
  exist — failing the build on a typo. Frontmatter is generated/checked against it.
- Each phase skill is **dual-mode**: frontmatter `argument-hint`+`arguments` so it is
  `/cap-evolve:<phase>` standalone; same SKILL.md is what the orchestrator calls headlessly
  (`--output-format json --json-schema` for decision steps). Descriptions rewritten to
  "<what>. Use when <triggers>" (<1024 chars, third person); bodies <500 lines; references
  one level deep with a Contents block.
- `intake` becomes the real **Phase 0 + integration**: capture-intent (mine existing
  artifacts first), scaffold, **implement the adapter abstract methods**, then **run
  `cap-evolve check` + the per-skill checks** and refuse to advance until green.
- `diagnose` carries the actual task input through the rollout and uses a pluggable
  clustering fn (default normalized-feedback signature) — the reflective dataset GEPA/SkillOpt consume.

### 2.3 New algorithms (detailed scripts)
- **`gepa`** — two-stage economy: sample a minibatch → eval parent w/ traces → optimizer
  proposes → eval child on the *same* minibatch → cheap local gate (sum child > sum parent)
  → **only on pass** pay for full-val + the honest significance gate + frontier update.
  Per-**instance** Pareto frontier with frequency-weighted parent sampling; trajectory in
  the reflective dataset (written as `REFLECTION.md` in the optimizer workdir); round-robin
  component focus (`FOCUS.md`); system-aware **merge** across two complementary lineages
  sharing an ancestor; **rollout/metric-call budget**; eval cache. (arXiv:2507.19457)
- **`skillopt`** — epochs × minibatches with a **textual learning rate** = integer
  edit-budget on a `constant|linear|cosine` schedule (`core/lr_schedule.py`); strict
  single-lineage climb (parent = current best); within-epoch **rejected-edit buffer** +
  failure-pattern block injected into the optimizer prompt; **epoch-boundary slow update**
  (longitudinal improved/regressed/persistent categorization → one extra *gated* step).
  Gated on val, test sealed. (arXiv:2605.23904)

### 2.4 Observability (rich, static, portable — no server)
Reduce the jsonl event log → candidate graph, render a **self-contained** `dashboard.html`:
KPI strip (best / baseline / %Δ / counts by status / frontier / epoch);
**cumulative-best stair** over a per-iteration score scatter (champion star);
**tasks×iterations pass/fail heatmap** (regressions & specialists the mean hides);
per-iteration **diff** view (split/unified); **lineage tree** (parents→children, merges =
multi-parent); **cost / tokens / latency** per-iter + cumulative, split **optimizer vs
runner**; per-task trace drill-down; annotations/diagnoses stream; secret redaction.
Plus a terminal **ANSI report** (`cap-evolve report`) for in-chat progress (CLAUDECODE
margin-aware). Optional panels degrade silently.

### 2.5 Claude Code (and friends) integration
Ship a namespaced **plugin** (`plugins/cap-evolve/`): all phase + algorithm + optimizer
skills under `skills/`; **hooks** (`hooks/hooks.json`) enforcing the honesty rules in
core-owned scripts (PreToolUse denies edits to the sealed-test/gold files; Stop/SubagentStop
exit-2 until `cap-evolve check`/gate passes); `agents/` (a read-only diagnoser via
`context:fork`+`agent:Explore`, a writing proposer); a session-start **router** skill
(`using-cap-evolve`) so the pipeline auto-triggers; dynamic context injection (`` !`cmd` ``,
`${CLAUDE_SKILL_DIR}`) to inline run-dir data. Headless JSON (`claude -p … --output-format
json --json-schema`, `codex exec --json`, `gemini -p --output-format json`) feeds exact
`total_cost_usd` to the report. Generic optimizer keeps a sequential prose fallback so the
pipeline still runs where these features are absent.

## 3. Execution plan (waves; reviewer agent after each)

- **W1 — Engine correctness & abstraction** *(foundation; do first, mostly in-repo)*:
  seed threading + check-warns-on-degenerate-trials; seal-on-success; paired gate +
  SE=0 warning; structured `Rollout.error`; atomic state writes; `materialize`/`live`
  split; `graph.py`; `selection.py` registry; `cache.py`. Update tau2 adapter to the new
  contract. Unit tests for each honesty invariant.
- **W2 — Skill library refactor**: optimizer registry collapse; hill-climb `--focus`
  merge; shared `_bootstrap` + `_tool_surface`; behavioral `check.py` + shared check
  harness; `meta.yaml` single-source + validating manifest; dual-mode slash-command
  frontmatter; description/body/reference rewrites; intake-implements-and-tests; orchestrate
  real DAG validation; diagnose fix.
- **W3 — New algorithms**: `gepa` (real) + `skillopt`, each with detailed `run.py`,
  `references/concepts.md`, behavioral `check.py`, and a tiny mock-optimizer e2e test.
- **W4 — Observability**: rich static `dashboard.html` builder + `cap-evolve report` ANSI.
- **W5 — Plugin & headless**: `plugins/cap-evolve/` with hooks/agents/router/marketplace;
  headless JSON cost capture.
- **W6 — Validation**: `pytest core/tests`; per-skill `check.py`; manifest build;
  mock-optimizer e2e (zero-API); then **tau2 airline end-to-end from scratch**, fully
  autonomous (asks the user only when not in YOLO mode), fix-and-rerun until the whole
  pipeline completes and emits the dashboard.

Each wave ends with a **reviewer subagent** (adversarial: correctness + honesty-not-leaked
+ no-new-duplication + docs-match-code) whose confirmed findings are fixed before the next
wave. Commits are authored as **Osher Elhadad**.
