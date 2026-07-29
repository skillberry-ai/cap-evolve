# Benchmark regression suite

Triggerable, real-model optimization regression over **tau2 · swebench · skillsbench**,
built on the [adapter templates](../../templates/adapters/). Each benchmark runs a curated
set of **representative** tasks (calibrated for headroom — nonzero but not saturated at
baseline) and reports **reward / latency / cost** base→opt from a single run, plus the
optimizer's capability diffs — a reproducible end-to-end pipeline + metrics regression,
not a leaderboard.

> **Calibrated-headroom suite.** Curated tasks are picked to have room to improve at
> baseline — solvable often enough to be meaningful, not so saturated that optimization
> has nothing to move. These benchmarks are binary-scored, so a few optimization
> iterations on the prompt/policy/skill can plausibly flip some but not all trials. This
> suite mainly proves the pipeline runs end-to-end and reports honest non-regression
> metrics; the `iterations` knob gives the optimizer more budget to explore if you want
> to push harder.

- **Agent:** `aws/gpt-oss-120b` (default) · **Optimizer:** Claude Code @ `claude-opus-4-8` (default) ·
  **3 iterations** for smoke (fixed), **10** for full (default). All of this — agent/optimizer
  model, trials, full-tier iterations, optimizer budget, gate strictness, hill-climb focus — is
  controllable per `workflow_dispatch` run; see **Manually** below for the full input list.
- **One project, one run:** all of a tier's tasks are optimized TOGETHER in a single
  `cap-evolve run` (`train == val == test == all tier tasks`, a no-holdout FIT — see
  `run_suite.sh`'s header). Baseline and optimized are both measured within that same run;
  nothing is pre-frozen or reused across runs.
- Results are uploaded as an artifact and posted as a sticky PR comment (metrics table +
  optimized-capability diff).

## Layout

```
ci/benchmarks/
  lib/
    run_suite.sh      # run a whole benchmark's tasks.json + emit metrics + capabilities
    metrics.py         # per-task + suite reward report (Markdown + jsonl)
    assert_run.py      # completion + non-regression gate
    ci_setup.sh         # idempotent runner venv + deps/clones (cached outside the checkout)
    measure_2x.sh       # run the suite twice (reproducibility) + assemble RESULTS.md
    results_md.py       # RESULTS.md assembly from a measure_2x.sh run
  runner/arm-runner.sh  # register THIS host as an ephemeral self-hosted runner (label ibm-vpc)
  <bench>/<tier>/tasks.json  # curated task ids per tier (smoke|full|integration); id + tag + agent
  RESULTS.md             # the 2x local measurement of the finalized suite
```

Seed capabilities are **not committed** (skillsbench skills are Anthropic-licensed); each
run reconstructs the seed capability from the adapter templates / examples at runtime.

## Why a self-hosted runner (IBM VPC)

The model gateway (`…vpc-int.res.ibm.com`) is **VPC-internal** — reachable only from a host
already on the IBM network. GitHub-hosted runners cannot reach it, so the workflows target a
self-hosted runner labelled `ibm-vpc` (e.g. **skillberry-1**).

### Register / arm the runner (on skillberry-1)

skillberry-1 has no `gh`, so mint a registration token on a repo-admin machine and pass it in:

```bash
# on a repo-admin machine (gh authed):
TOKEN=$(gh api -X POST repos/skillberry-ai/cap-evolve/actions/runners/registration-token --jq .token)

# on skillberry-1 (Docker running, on the IBM network):
RUNNER_TOKEN=$TOKEN bash ci/benchmarks/runner/arm-runner.sh   # ephemeral: one job, then exits
```

Re-run to arm again (each `workflow_dispatch` job needs one arm; a 3-benchmark matrix needs 3,
or drop `--ephemeral` in the script for a persistent runner). The runner package + credentials
live under `~/.cache/capevolve-gh-runner/` (outside the repo). Confirm it appears under
repo → Settings → Actions → Runners with the `ibm-vpc` label.

## Trigger the suite

Runs come in two **tiers** (a first-class dimension in the workflow, same workflow + history page):
- **`smoke`** — a few representative tasks per benchmark (fast regression; the default).
- **`full`** — the whole/representative benchmark per bench (thorough; expensive). Its tasks
  live under `ci/benchmarks/<bench>/full/tasks.json`; a bench with an empty list simply runs
  zero tasks until populated (see below). `tau2/full/tasks.json` is already populated (50
  tasks); `swebench` and `skillsbench` are not yet.

The tier surfaces everywhere: PR checks read **`<tier> / <bench>`** (e.g. `smoke / tau2`,
`full / swebench`), the report header reads **`## <Tier> suite — <bench>`**, and the history page
has a **Type** column + filter.

- **Manually:** Actions → **Benchmarks** → Run workflow → pick the **benchmark** (`all` / one) and
  **tier** (`smoke` default / `full` / `all`), plus any of these knobs (all optional, sensible
  defaults):

  | input | default | applies to |
  |---|---|---|
  | `iterations` | `10` | full tier only — smoke is always pinned to 3 |
  | `trials` | `10` | whichever tier(s) run in this dispatch |
  | `agent_model` | `aws/gpt-oss-120b` | the evaluation model (agent under test) — dropdown, populated from the `ete-litellm` gateway's registered aliases |
  | `optimizer_model` | `claude-opus-4-8` | the optimization model (Claude Code's model) — dropdown, same gateway-alias list as `agent_model` |
  | `optimizer_usd_per_iter` | `0` (unlimited) | per-iteration $ cap on the optimizer — `0` disables Claude Code's native `--max-budget-usd` cap entirely; set e.g. `4.0` to bound it |
  | `optimizer_max_turns` | `80` | per-iteration turn cap on the optimizer |
  | `gate_k_se` | `1.0` | acceptance-gate strictness (accept iff Δ > k_se·SE) |
  | `algorithm_focus` | `all` | hill-climb schedule: `all` \| `cyclic` \| `hardest-first` |

  Overriding `agent_model` takes precedence over any per-task `agent` a curated `tasks.json`
  entry pins — `run_suite.sh` warns (doesn't fail) on a mismatch so you know it happened.
- **On a PR — labels:**
  - **`benchmark-smoke`** / **`benchmark-full`** → run all three benchmarks of that tier.
  - **`benchmark-smoke-<bench>`** / **`benchmark-full-<bench>`** (`tau2` · `swebench` · `skillsbench`)
    → run just that one (combine labels to run a subset).

  (The tau2 pipeline regression is the **`integration-test`** label / **Integration tests**
  workflow — the same `run_suite.sh` path as above, scoped to a single-task `integration`
  tier: `ci/benchmarks/tau2/integration/tasks.json`.)

### Populate the `full` tier

Just add task ids to `<bench>/full/tasks.json` (same shape as `<bench>/smoke/tasks.json`):
```json
[{"id": "<task_id>", "tag": "full", "agent": "aws/gpt-oss-120b"}]
```
No baseline-freezing step — `run_suite.sh` computes the baseline fresh, in the same run, for
whatever ids are listed. Pick ids with headroom (baseline not already saturated) by running
`run_suite.sh` against a candidate list and checking the report.

Repo secrets required: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`.

> **Note:** GitHub only exposes `workflow_dispatch` (and evaluates `pull_request`
> workflows) from the **default branch**, so `benchmarks.yml` becomes triggerable
> once it lands on `main`. Until then, run the suite directly on the runner host with
> `ci/benchmarks/lib/run_suite.sh <bench>` (what the workflow calls). Validated on
> skillberry-1: the `ibm-vpc` runner registers/listens and `run_suite` completes
> end-to-end against the VPC gateway.

## Metrics

Per task: `reward (base→opt)`, `Δ` — that's it. Latency/cost are never per-task in a
whole-suite run (every task is scored in the same eval call); instead they're reported
per **suite iteration** (baseline → each hill-climb step → finalize): `optimizer $`/time
and `eval $`/time. **Latency** is wall-time and hardware-dependent (baseline and
optimized are both measured on the same run's runner host; treat cross-host/cross-run
comparisons as indicative only). **Cost/tokens** are hardware-independent, but the
tau2/skillsbench runners do not surface usage (reads 0); swebench (litellm) does.

## Adding / changing tasks

There's nothing to freeze or refresh — `run_suite.sh` always computes baseline and
optimized within the same run. To change what a tier covers, edit `<bench>/<tier>/tasks.json`
directly (id + tag + agent, same shape across `smoke`/`full`/`integration`) and re-run
`ci/benchmarks/lib/run_suite.sh <bench>` (set `TIER=<tier>` for anything other than `smoke`).

## Benchmark history page

Every run appends a per-`(run×bench)` record to the **`benchmark-history`** orphan branch
(`records/<run_id>__<bench>.json`) and regenerates `benchmarks.json` + `meta.json` there
(single-writer `aggregate` job → no races). The Pages page `site/benchmarks.html` fetches
`benchmarks.json` at load and renders a sortable/filterable table (rollup rows expand to
per-task detail). Bootstrap the branch once:

```bash
git switch --orphan benchmark-history
mkdir -p records && : > records/.gitkeep
echo '[]' > benchmarks.json
echo '{"count":0,"runs":0,"updated":null}' > meta.json
git add records/.gitkeep benchmarks.json meta.json
git commit -m "chore: init benchmark-history branch" && git push origin benchmark-history
```

### Per-run CapEvolve UI snapshots

Each `bench` job also best-effort-exports its raw `.capevolve` run directory as a static
CapEvolve dashboard snapshot (`export_static.py` + a `VITE_STATIC=1` Vite build), assembled
by the `aggregate` job into `runs/<run_id>__<tier>-<bench>/ui/` on `benchmark-history`
alongside its record, which gets `"has_ui": true`. `pages.yml` redeploys on every Benchmarks
completion and folds `benchmark-history`'s `runs/**` into the deployed site under
`benchmark-ui/runs/**`, so `benchmarks.html` can link "Open UI" straight to a specific run's
dashboard. Records/snapshots are **kept forever by default** — there is no automatic expiry.

To reclaim space, run **Actions → "Prune benchmark-history" → Run workflow** with a `days`
input (default `30`) — it deletes any record (and its paired UI snapshot) older than that
many days, directly on `benchmark-history`. This only removes files from the branch's current
tree; it does not rewrite git history, so it doesn't reclaim `.git` object storage — that's
an accepted tradeoff for keeping "keep forever unless a human explicitly prunes" simple.
