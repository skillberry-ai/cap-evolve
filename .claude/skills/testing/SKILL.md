---
name: testing
description: Run the test tiers a code change in cap-evolve needs before review - the unit tier always, and a real end-to-end run (local zero-API or a dispatched CI benchmark/integration-test leg) when the change plausibly affects a real run. Use for every code change (core/cap_evolve, skills, dashboard backend, adapters, CI). Not for dashboard-frontend-only or docs-only changes - those have their own skills.
---

# Testing

Two tiers. Run tier 1 always. Run tier 2 whenever the change could plausibly alter
what a real optimization run does, scores, or costs — not just whenever you feel
like it, but err toward running it when in doubt.

## Tier 1 — unit (always)

The exact commands CI runs (`.github/workflows/ci.yml`, mirrored in
`.bob/rules/01-cap-evolve.md`):

```bash
pip install -e "./core[dev]" -e "./dashboard/backend[dev]"
python -m pytest core/tests -q
python -m pytest dashboard/backend/tests -q
python skills/_registry/build_manifest.py skills
python skills/_registry/lint_skills.py skills
cd dashboard/frontend && npm ci && npm run build && npm test
```

- A change under `core/cap_evolve/`, `skills/*/*/scripts/`,
  `dashboard/backend/capevolve_dashboard/`, or `dashboard/frontend/src/`
  **needs a new or updated test** in the matching `*/tests` dir. Flag its absence
  as a blocker, don't just note it.
- `dashboard/frontend/dist/` is committed — after any `dashboard/frontend/src/`
  change, `npm run build` and commit the new `dist/`. CI fails on a stale `dist/`.
- Any new/changed skill needs its own `scripts/check.py` green:
  `python skills/<component>/<skill>/scripts/check.py`.
- `python -m compileall core skills` as a cheap final syntax pass.

## Tier 2 — end-to-end (when the change can affect a real run)

Run this tier when the change touches: `core/cap_evolve/harness.py` or the
optimization loop, an adapter (`benchmarks/**`), the gate/seal/splits logic, the
CLI (`cap-evolve run`/`init`/`check`), or CI's benchmark dispatch
(`ci/benchmarks/**`, `.github/workflows/benchmarks.yml`,
`.github/workflows/integration-tests.yml`).

### Zero-API, always free — run this first

```bash
bash benchmarks/toy/examples/calc/run.sh
cap-evolve init -y && cap-evolve check .capevolve/project
bash ci/e2e_all_algorithms.sh                 # all 5 algorithms, deterministic + agent-mode handoff
```

These cost nothing and catch most regressions in the loop itself. Always run them
before a real dispatch, not instead of it, when the change is loop-adjacent.

### Real model runs — only when zero-API isn't enough

Some changes (a new adapter, a scoring fix, a provider-routing change) need a real
model to actually exercise. Dispatch from **Actions**, not by running the
benchmark harness by hand on your own machine with live credentials:

- **`Integration tests`** (`.github/workflows/integration-tests.yml`,
  `workflow_dispatch`): one cheap single task per leg (`tau2`, `tau2_sierra`,
  `tau2_sierra_blackbox`, `appworld`). Use this for "does the arm still land" after
  a wiring/adapter change — minutes, not dollars.
- **`Benchmarks`** (`.github/workflows/benchmarks.yml`, `workflow_dispatch`): the
  curated multi-task tiers (smoke/pilot/full) per benchmark. Use this when you need
  a real reward/latency/cost delta, not just "does it run".

```bash
gh workflow run "Integration tests" --repo skillberry-ai/cap-evolve -f bench=tau2_sierra
gh workflow run "Benchmarks" --repo skillberry-ai/cap-evolve -f bench=tau2 -f tier=smoke
gh run watch --repo skillberry-ai/cap-evolve   # or: gh run list, then gh run view <id>
```

**Model provider order** (apply this whenever you pick a model for either
workflow): **RITS** (`ibm-rits/…`, no budget) → **ETE-INT** (`ibm-ete-int/…`, the
team's main gateway) → **ETE** (`ibm-ete/…`, a second gateway with its own
budget) — use ETE only when ETE-INT can't serve the model or is over budget. Pick
a **plain model name** (e.g. `claude-opus-5`) and CI applies this order itself;
pick a prefixed id (`ibm-ete/aws/claude-opus-5`) only to pin one gateway
deliberately, and say why in the PR. The order and model list live in
`ci/benchmarks/model_catalog.txt` — read its header before adding a model. After a
run, the job summary and run record (`agent_provider`, `optimizer_provider`,
`*_provider_skipped`) show which provider actually served it; report spend per
provider from these. Full detail: `ci/benchmarks/README.md`, "Model providers and
their order".

### Report the evidence

Once a real run finishes, post a PR comment (or put it in the PR description
before opening) with: the workflow run link, the leg/tier, the provider that
served it, and the key numbers (`best_val`, `test_reward`, `test_delta`, cost).
Reviewers in `review-cycles` read this instead of re-running anything themselves.
