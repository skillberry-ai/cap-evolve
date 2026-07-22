# Consuming-LLM awareness: target-model profiles

**Date:** 2026-07-20
**Status:** Design — approved for planning
**Related:** PR #55 (`feature/skill-tool-optimization-knowledge`, "teach how to optimize
skills & tools for the AI-agent reader") — this feature makes that *reader* an explicit,
declarable capability profile.

## Problem

cap-evolve optimizes the capabilities (system prompts, tool code/docs, MCP surfaces, skill
packages) that an agent *reads at runtime*. Today the framework has two distinct LLM roles
but treats only one of them as a first-class, configurable concept:

- **Optimizer LLM** — the "smart" model that *proposes edits* (e.g. `claude-opus-4-6`).
  First-class in `capevolve.yaml`: `optimizer_model`, `optimizer_max_turns`,
  `optimizer_usd_per_iter`.
- **Runner / consuming LLM** — the model the *agent under test uses at runtime* to read
  the capabilities (e.g. `gpt-oss-120b` in the tau2 example). **Not a first-class field** —
  it lives only as a credential/wiring detail inside the adapter's `run_target`, described
  in `skills/phases/intake/inputs/INPUTS.md`.

Two concrete consequences:

1. **The consuming model's capability level is never named to the optimizer.** The
   per-iteration optimizer prompt (`templates/project/optimizer/INSTRUCTIONS.md`) has
   template slots for `{{FAILURES}}`, `{{PASSING}}`, `{{CAP_BRIEF}}`, `{{FOCUS_SUMMARY}}`,
   etc. — but no slot naming *who the reader is and how capable they are*. The optimizer
   edits blind to the consuming model.
2. **The capability guidance implicitly assumes a strong, modern reader.** e.g.
   `skills/capabilities/system-prompt/references/concepts.md` advises "newer models
   over-comply, so soften your `MUST`s" and "prefer explaining the *why* over ALL-CAPS
   rules — modern models follow reasoning." That advice is often *backwards* for a weaker
   consuming model, which benefits from explicit imperative rules, worked few-shot
   examples, shorter decision chains, more literal slot-filling docs, and heavier
   deterministic tool-code enforcement.

**Goal:** let a user declare the runtime/consuming LLM — by concrete model id *or* by an
abstract capability tier — so the optimization process (optimizer prompt + capability
guidance) adapts its edits (text, slot-filling, tool docs, enforcement strategy) to that
reader. Optimize *for the reader, not for the optimizer*.

## Non-goals

- **No change to the honesty core.** The acceptance gate, split logic, and test seal
  (`gate.py`, `splits.py`, `rundir.py`) are untouched. The profile influences *what edits
  are proposed*, never *whether a candidate is accepted* — acceptance stays a val-only
  significance gate on measured reward.
- **Not binding the runner wiring to the profile.** The declared consuming model does not
  change which model the adapter actually drives; it *describes* it and (best-effort)
  *warns* on mismatch. Wiring the runner model stays the adapter's job.
- **No structured "dials."** The profile's steering content is a natural-language brief,
  not a set of machine-branchable knobs. (Rejected alternative — see below.)

## Chosen approach (Approach A: profile registry + template slot)

A small **profile registry** in the skill library holds built-in capability tiers, each
with a prose **reader brief**; a **name→tier lookup** resolves known model ids. New
`capevolve.yaml` fields let the user declare the consuming model. The loop resolves the
declaration to a brief and injects it into a new optimizer-prompt slot. The four capability
skills gain tier-conditional guidance. Intake asks for it; report/dashboard display it;
`cap-evolve check` warns (does not block) on a detected runner-model mismatch.

### Rejected alternatives
- **B — pure config prose, no registry.** User writes the brief straight into config; no
  built-in tiers or name mapping. Rejected: contradicts the name→tier requirement and
  hands every user a blank page.
- **C — profile as a heavy first-class object** owning runner wiring + gate presets as
  bound values. Rejected as the primary shape: over-couples honesty knobs to the profile.
  Presets survive only as *suggested defaults* the user may override.
- **Structured dials** for profile content. Rejected: rigid and verbose to cover nuance;
  a prose brief the optimizer interprets is simpler and matches how the capability skills
  already read.

## Data model

### 1. Library resource — `skills/_registry/target_profiles.yaml`

```yaml
# Built-in capability tiers and a known-model → tier lookup. Extensible.
tiers:
  frontier:
    brief: >
      The reader is a top-tier model (strong long-context reasoning, reliable
      instruction-following, tends to OVER-comply). Prefer concise policy that explains
      the WHY over piling on ALL-CAPS MUSTs; soften brittle imperatives; trust multi-step
      reasoning; minimal few-shot. Over-constraining HURTS this reader.
    suggested_num_trials: 1
    notes: e.g. claude-opus, gpt-4-class, gemini-2.5-pro-class
  strong:
    brief: >
      Capable general model but less robust than frontier on long/ambiguous context. Keep
      instructions clear and reasonably explicit; a worked example helps for tricky
      formats; prefer code enforcement for behavioral rules.
    suggested_num_trials: 3
    notes: default when a named model is unknown
  mid:
    brief: >
      Mid-capability model (e.g. ~100B open weights). Be EXPLICIT: imperative step-by-step
      rules, at least one worked few-shot example per non-trivial behavior, short decision
      chains, literal argument/slot-filling docs on every tool parameter. Lean HARD on
      deterministic tool-code enforcement — a behavioral rule it "knows" but skips must be
      enforced in code, not restated in prose.
    suggested_num_trials: 5
    notes: e.g. gpt-oss-120b
  weak:
    brief: >
      Smaller/weaker model. Assume it will miss anything not made mechanical. Maximize
      explicitness and examples; minimize reasoning it must do unaided; move as much
      correctness as possible into tool code/guards and rigid output contracts; keep each
      instruction short and single-purpose. Prose is the weakest lever here.
    suggested_num_trials: 5
    notes: e.g. gpt-oss-20b, small local models

model_map:
  claude-opus-4-6: frontier
  claude-opus-4-8: frontier
  claude-sonnet-5: strong
  claude-haiku-4-5: mid
  gpt-oss-120b: mid
  gpt-oss-20b: weak
  # ... extensible; unknown ids fall back to `strong` + a note.
```

Format note: this file is read by cap-evolve's tolerant zero-dependency YAML reader
(`specfile.read_yaml`), which supports one level of nesting and `key: scalar` / `key:
[list]`. Multi-line `brief:` values use the `>` folded-scalar form **only if PyYAML is
present**; to stay safe under the minimal reader, briefs are authored as single logical
lines (the minimal reader takes the scalar after the first `:`). The resolver treats a
missing/short brief gracefully. *(Implementation note for the plan: verify brief rendering
under BOTH readers; if the minimal reader cannot hold the briefs, store briefs as separate
`.md` files referenced by tier and keep only the scalar `model_map` + presets in YAML.)*

### 2. `capevolve.yaml` — two new fields (both optional, default = current behavior)

```yaml
# --- consuming (runtime) LLM the capabilities are optimized FOR --------------
# The model the AGENT UNDER TEST reads these capabilities with at runtime — distinct from
# optimizer_model (which PROPOSES edits). May be a concrete model id (resolved to a tier
# via the profile registry) OR a tier keyword directly: frontier | strong | mid | weak.
# Empty = profile-agnostic (exactly today's behavior).
target_model: ""
# Optional project-local brief that OVERRIDES the registry brief for the resolved tier.
target_profile_file: ""
```

### 3. Resolution rule

```
if target_model is blank                 -> neutral/empty profile (no {{TARGET_READER}} block; behavior unchanged)
elif target_model in {frontier,strong,mid,weak} -> that tier
elif target_model in model_map           -> model_map[target_model]
else (unknown id)                        -> tier = "strong" + note "unknown model id; set a tier explicitly"
# target_profile_file, if set, replaces the brief text for the resolved tier.
```

## Pipeline flow

1. **Load.** The spec loader reads `target_model` + `target_profile_file` using the
   existing tolerant reader — no new dependency.
2. **Resolve.** A new core module `core/cap_evolve/target_profile.py` exposes
   `resolve(target_model, target_profile_file, registry_path) -> TargetProfile` returning
   `{model, tier, brief, suggested_num_trials, notes, resolution_note}`. Blank input
   returns a sentinel "agnostic" profile whose brief is empty.
3. **Inject.** The loop (`loop.py`, where `optimizer/INSTRUCTIONS.md` is rendered) fills a
   new **`{{TARGET_READER}}`** slot placed near the top of the template, e.g.:

   ```
   THE READER (who consumes what you edit): at runtime these capabilities are read by
   `<model>` — capability tier: <tier>. <brief>
   Optimize your edits for THIS reader's capability level, not for your own. When the
   reader is weaker than you, prefer explicit rules, worked examples, and code enforcement
   over terse prose you would personally infer.
   ```

   When the profile is agnostic, `{{TARGET_READER}}` renders empty → **byte-identical
   prompt to today** (backward-compat guarantee, covered by a test).
4. **Record.** The resolved profile is written to run metadata (the run dir's manifest /
   meta) so `report` and `dashboard` can display it.

## Capability-skill changes (the knowledge work)

Each capability skill gains a short reference section **"Adapting to the reader's
capability tier"** that makes its *existing* advice tier-conditional. Concretely:

- **`skills/capabilities/system-prompt/`** — the current "soften MUSTs / explain the why /
  newer models over-comply" guidance in `references/concepts.md` is explicitly labeled a
  **frontier/strong** tactic; a **mid/weak** counterpart is added: explicit imperative
  rules, mandatory worked few-shot example(s), shorter decision chains, rigid output
  contracts.
- **`skills/capabilities/tools/`** — for weaker readers, push harder on the skill's
  already-preferred code enforcement (in-body guards, composite atomic-write tools) and on
  **literal per-parameter slot-filling docs**; add explicit-example argument docs.
- **`skills/capabilities/mcp-tool/`** — client-side re-description guidance gains a tier
  note: weaker readers need more literal, example-bearing parameter descriptions and a
  tighter exposed toolset (fewer, less-confusable tools).
- **`skills/capabilities/skill-package/`** — tier note on SKILL.md body density and
  example count; weaker readers need more worked steps and less inference.

Each section is short and points back to the single source of truth (the brief), so the
tier framing is stated once conceptually and applied per capability.

## Intake / report / dashboard / honesty

- **`skills/phases/intake/`** — `inputs/INPUTS.md` adds `target_model` as a RECOMMENDED
  input (ask the user for the runtime/consuming model or a tier; default blank = agnostic,
  noted in `PROJECT.md`). `SKILL.md` mentions writing it into `capevolve.yaml`. Optionally
  seed `num_trials` from the tier's `suggested_num_trials` as a *default the user may
  override* (not bound).
- **`cap-evolve check`** — best-effort: if the adapter exposes/declares its runner model
  (e.g. an optional `adapter.runner_model()` hook or a declared field) and it resolves to a
  different tier than `target_model`, print a **prominent warning** — "optimizing FOR
  `<declared>` (tier X) but eval appears to run on `<actual>` (tier Y)" — and proceed. No
  block. If the adapter exposes nothing, no warning (trust the declaration).
- **`report`** — surface the declared consuming model + tier next to the optimizer model,
  so the two LLM roles are visibly distinct in the run summary.
- **`dashboard`** — display the declared consuming model + tier in the run header/metadata
  panel alongside `optimizer_model`.

## Testing

- **Resolver unit tests** — blank → agnostic; tier keyword passthrough; known id → tier;
  unknown id → `strong` + note; `target_profile_file` override replaces the brief.
- **Backward-compat test** — blank `target_model` renders a `{{TARGET_READER}}`-free
  prompt byte-identical to the pre-feature template output.
- **Check-warning test** — adapter declaring a mismatching runner model triggers the
  warning and still returns success (non-blocking).
- **YAML-reader test** — the registry file parses correctly under BOTH PyYAML and the
  minimal reader (or, per the format note, the `.md`-brief fallback parses).
- **Existing suites** (`test_core.py`, `test_gepa.py`, `test_native_skills.py`,
  `test_skillopt.py`) stay green — no honesty-core behavior changes.

## Backward compatibility

Every new field is optional and defaults to blank/agnostic. With no `target_model`, the
optimizer prompt, capability guidance behavior, gate, splits, and reports are unchanged.
Existing projects and examples run identically until they opt in.

## Rollout in examples (optional, low-risk)

Set `target_model: gpt-oss-120b` in `examples/tau2_airline/capevolve.yaml` so the flagship
example demonstrates the feature against its real `gpt-oss-120b` runner (tier `mid`) — a
faithful showcase, since the tau2 docs already document that runner.
