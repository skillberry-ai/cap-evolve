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
