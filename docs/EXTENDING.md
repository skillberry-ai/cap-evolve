# Extending AgentCapTune

Everything user-facing is a skill, so extending the harness never means editing
core. Adding a capability, algorithm, or optimizer is the same three steps.

## Add a skill in 3 steps

1. **Clone the template.**
   ```bash
   cp -R templates/skill skills/<component>/<your-skill>
   ```
   `<component>` is one of `phases`, `capabilities`, `algorithms`, `optimizers`,
   `orchestrate`.

2. **Fill it in.**
   - `SKILL.md` (required) — frontmatter (`name`, `description`, `component`, `needs`,
     `provides`, `sources`) + high-level instructions. Ground claims in real
     sources and cite them.
   - `references/*.md` (optional) — add real grounding docs when you have them; the SKILL.md body is the primary documentation. Don't ship empty placeholders.
   - `prompt/PROMPT.md` (optional) — only if the skill drives a bespoke LLM step.
   - `inputs/INPUTS.md` (optional) — needed/recommended inputs; the central one is `phases/intake`'s.
   - `scripts/abstract.py` — the methods the optimizer agent implements.
   - `scripts/check.py` — a real smoke test that fails on stubs and on
     non-determinism.
   - `scripts/run.py` — performs the step; prints one JSON object.
   - `meta.yaml` — keep `name`/`component` in sync; set `needs`/`provides` and
     `compatible_with`.

3. **Register + verify.**
   ```bash
   python skills/_registry/build_manifest.py skills    # discovers your skill
   python skills/<component>/<your-skill>/scripts/check.py   # must be green
   ```

## How wiring works

`build_manifest.py` walks `meta.yaml` files into `manifest.json`. The
`orchestrate` skill reads the manifest and connects skills by matching
`provides` tokens to `needs` tokens (e.g. `evaluate` provides `scores`+`traces`,
which `diagnose` and the algorithm skills need). `compatible_with` glob lists
declare valid pairings; `*` means "any", which is what gives you
any-capability × any-algorithm × any-optimizer.

## Token vocabulary (keep these consistent)

| Token | Produced by | Consumed by |
|-------|-------------|-------------|
| `tasks` | intake / adapter | evaluate, baseline |
| `candidate` | capabilities, algorithms | evaluate, gate |
| `scores` | evaluate | diagnose, gate, algorithms |
| `traces` | evaluate | diagnose |
| `reflective_dataset` | diagnose | algorithms |
| `decision` | gate | algorithms |
| `report` | finalize / report | (terminal) |

Introducing a new token is fine — just make sure some skill `provides` it before
another `needs` it, or the orchestrator will flag an unsatisfied dependency.
