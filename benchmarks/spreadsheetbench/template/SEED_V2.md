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
`CAPEVOLVE_HELPER_GATE=0`). They use the candidate's real parent. This adapter has a second gate for optimizers
that call `run_target` themselves, without a cap-evolve loop.

- **Inside a cap-evolve run the adapter gate is off.** `cap_evolve.check.load_adapter` sets
  `CAPEVOLVE_DRIVER=cap-evolve` before it imports the adapter. Then only the loop gate runs, `CAPEVOLVE_HELPERS_SPEC`
  is ignored, and the adapter prints one line saying so. Any other value, or no value, means an external caller. An
  external harness may set its own value, for example `external:<name>`.
- **How an external optimizer turns it on.** Set `CAPEVOLVE_HELPERS_SPEC` (the run's `capevolve.yaml`),
  `CAPEVOLVE_HELPERS_SEED` (the seed capability dir) and `CAPEVOLVE_HELPERS=1`. Import the adapter directly, not
  through `cap_evolve.check.load_adapter`: that function sets `CAPEVOLVE_DRIVER=cap-evolve` for the whole process
  and its subprocesses, and the adapter gate is then off.
- **The seed is the parent.** `run_target(task, ctx, seed)` has no parameter for the candidate's parent, and one
  process can evaluate several candidates at the same time, so an environment variable cannot carry it. The verdict
  can therefore differ from the loop gate's:
  - Lint can be less strict. A candidate that adds back a violation which the seed has and its parent had removed
    passes, because it adds no new finding against the seed.
  - Smoke can be more strict. It imports every helper that differs from the seed, including helpers that earlier
    candidates added.
  - Smoke replays no fixtures from rollout traces, because an external caller gives none. It does replay a fixtures
    file declared in `helpers.fixtures`.
- **A refused candidate** scores 0 on each rollout (`error_kind=candidate`, no LLM call). The caller still pays its
  own budget for those rollouts.
- **A config the gate cannot run on** raises `HelperGateConfigError` from `Adapter()`, `live()` and `run_target`: the
  spec enables helpers but `CAPEVOLVE_HELPERS` is unset, no seed, an unreadable `ids_file`. It is never returned as
  an infra rollout, which a caller would retry and then drop as missing data. It derives from `BaseException`, so a
  caller that catches every `Exception` (GEPA with `raise_on_exception=False`, EvoSkill) does not swallow it or score
  it 0.
