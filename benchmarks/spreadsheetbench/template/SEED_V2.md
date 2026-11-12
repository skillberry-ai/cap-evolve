# v2 seed layout (capabilities `[system-prompt, skill]`)

```
prompt.md  task_template.md                       # same contract as seed_capability/
skills/<name>/SKILL.md                            # frontmatter (name, description) + when to call each script
skills/<name>/scripts/*.py                        # empty here; the optimizer writes task-agnostic helpers
```

Run with `helpers.enabled: true` (or `CAPEVOLVE_HELPERS=1`) and `surface.executable_dirs: ["skills/*/scripts"]`.
The adapter then runs only the current candidate's `skills/*/scripts/*.py` once, as text, in the rollout's own
kernel (modules `skills.<skill>.<script>`), appends each `SKILL.md` to the system prompt, and substitutes
`{skills_root}` (= `skills`) in `prompt.md` / `task_template.md`. Nothing is mounted and nothing sits under the
data view, so only that candidate's code is ever visible. A script cannot be run as a CLI (`__main__`) in this
carrier. With helpers off this directory behaves as v1 plus an inert `skills/` tree. It is a different editable
surface from `seed_capability/`: register it as its own experiment, never pool its rows with v1.

**The helper gate.** cap-evolve's own algorithms check every candidate's helper scripts before any rollout of it
(`cap_evolve.helper_gate`: surface, lint, smoke; on whenever helpers are, off only with `helpers.gate: false` or
`CAPEVOLVE_HELPER_GATE=0`). An optimizer that calls this adapter's `run_target` itself gets the same check by
setting `CAPEVOLVE_HELPERS_SPEC` (the run's `capevolve.yaml`) and `CAPEVOLVE_HELPERS_SEED` (the seed capability
dir), with `CAPEVOLVE_HELPERS=1`. A refused candidate then scores 0 on each rollout (`error_kind=candidate`, no
LLM call); the caller still pays its own budget for those rollouts. A config the gate cannot run on (the spec
enables helpers but `CAPEVOLVE_HELPERS` is unset, no seed, an unreadable `ids_file`) raises
`HelperGateConfigError` when the adapter is created.
