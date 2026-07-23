# Benchmark regression suite

Triggerable, real-model optimization regression over **tau2 · swebench · skillsbench**,
built on the [adapter templates](../../templates/adapters/). Each benchmark runs a curated
set of **hard** tasks (baseline reward 0) and reports **reward / latency / cost** vs a frozen
baseline, plus the optimizer's capability diffs — a reproducible end-to-end pipeline + metrics
regression, not a leaderboard.

> **On flips (0→1 after optimization).** We searched extensively for tasks that would flip
> 0→1 after optimization — ~55 task-runs across `aws/gpt-oss-120b` (1 and 3 iterations) and
> `aws/claude-sonnet-5` (1 iteration), on all three benchmarks — and found **none**. These
> benchmarks are **binary-scored**; a task a model fails at baseline is capability-bound, and a
> few optimization iterations on the prompt/policy/skill don't carry a hard failure to a pass.
> The suite therefore ships **hard-only**: it proves the loop runs and reports honest metrics
> (reward stays 0, non-regression), and the `iterations` knob lets you give the optimizer more
> budget to explore. The `flip`/`hard` tagging + agent-per-task are kept in the harness for
> future use with a different model or a non-binary scorer.

- **Agent:** `aws/gpt-oss-120b` (all benchmarks) · **Optimizer:** Claude Code @ `claude-opus-4-8` · **3 iterations** (default; configurable via the `iterations` workflow input or `ITERATIONS` env).
- **Baselines are frozen** (committed under `<bench>/<task>/baseline/`) and reused via
  `cap-evolve run --reuse-baseline` — the baseline agent is **never re-run**; CI only
  optimizes + evaluates.
- Results are uploaded as an artifact and posted as a sticky PR comment (metrics table +
  optimized-capability diff).

## Layout

```
ci/benchmarks/
  lib/
    run_task.sh       # drive ONE task: baseline | full | optimize | check
    run_suite.sh      # run a whole benchmark's tasks.json + emit metrics + capabilities
    select_tasks.sh   # sweep candidate ids to pick 2 flips + 2 hard
    metrics.py        # reward/latency/cost extraction + Markdown table
    assert_run.py     # completion + non-regression (+ optional flip) gate
    ci_setup.sh       # idempotent runner venv + deps/clones (cached outside the checkout)
  runner/arm-runner.sh  # register THIS host as an ephemeral self-hosted runner (label ibm-vpc)
  <bench>/tasks.json    # the curated task ids (id + tag: flip|hard)
  <bench>/<task>/baseline/  # frozen splits.json + baseline.json + rollouts/val (NO seed capability)
  baselines.json        # recorded baseline reward/latency/cost per task
  RESULTS.md            # the 2x local measurement of the finalized suite
```

Seed capabilities are **not committed** (skillsbench skills are Anthropic-licensed); the
frozen baseline stores only metrics + trajectories, and the seed is reconstructed at runtime.

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

- **Manually:** Actions → **Benchmarks** → Run workflow → pick `all` or one benchmark.
- **On a PR:** add the **`benchmark-test`** label (the tau2 pipeline regression is the
  **`integration-test`** label / **Integration tests** workflow).

Repo secrets required: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`.

> **Note:** GitHub only exposes `workflow_dispatch` (and evaluates `pull_request`
> workflows) from the **default branch**, so `benchmarks.yml` becomes triggerable
> once it lands on `main`. Until then, run the suite directly on the runner host with
> `ci/benchmarks/lib/run_suite.sh <bench>` (what the workflow calls). Validated on
> skillberry-1: the `ibm-vpc` runner registers/listens and `run_suite` completes
> end-to-end against the VPC gateway.

## Metrics

Per task: `reward (base→opt)`, `flip`, `latency base→opt (s)`, `runner cost base→opt`,
`optimizer $`, `iters`. **Latency** is wall-time and hardware-dependent (the frozen baseline
was recorded on the runner host; treat cross-host comparisons as indicative). **Cost/tokens**
are hardware-independent, but the tau2/skillsbench runners do not surface usage (reads 0);
swebench (litellm) does.

## Refresh the frozen baselines (when the model/config changes)

```bash
source ci/benchmarks/.creds   # ANTHROPIC_* + CAPEVOLVE_PY + SKILLSBENCH_SRC (local, gitignored)
# 1. sweep candidates and pick tasks (baseline==0; classify flip/hard)
bash ci/benchmarks/lib/select_tasks.sh <bench> baseline <ids...>
bash ci/benchmarks/lib/select_tasks.sh <bench> full <zero-baseline ids...>
# 2. freeze the chosen tasks' baselines
bash ci/benchmarks/lib/freeze_baseline.sh <bench> <task_id>
# 3. update <bench>/tasks.json and re-measure (RESULTS.md)
```

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
