# Benchmark regression suite

Triggerable, real-model optimization regression over **tau2 · swebench · skillsbench ·
spreadsheetbench · rfe-creator**, plus the two tau2-airline **delivery arms**
(**tau2_sierra · tau2_sierra_blackbox**) and an **appworld** integration tier,
built on the [adapter templates](../../benchmarks/). Each benchmark runs a curated
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
- Each job publishes its own results to the [skillberry-runs dashboard](https://skillberry-runs.github.io/dashboard/)
  (see below), posts them as a sticky PR comment (metrics table + optimized-capability diff), and
  uploads its files as an artifact when it can (best-effort; publishing does not depend on it).

> **Also in this tree, but not part of the CI suite: [`parsec`](parsec/README.md)**
> (**local-only / internal-only**). Red Hat's LLM-agentic troubleshooting tool; tiers
> `smoke` (5) · `pilot` (30 v1 real-trace tasks) · `v2` (10 authored tasks, one isolated
> simulator each). `run_suite.sh` accepts it as a `<bench>`, so it runs the same code path
> locally, but it is deliberately absent from `benchmarks.yml`'s `BENCHES` and from every
> other dispatch list: neither its task trees (internal RH, not in the public
> `rhpds/parsec`) nor its kaegis simulators (`github.ibm.com/kaegis/simulation-harness`)
> exist outside IBM/RH, so a dispatched leg could only ever fail for infrastructure
> reasons. Nothing but per-tier `tasks.json` metadata is committed — the datasets are
> regenerated locally by `parsec/utils/`. See its README for the setup pipelines and the
> reasoning.

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

## The two tau2-airline delivery arms

`tau2_sierra` and `tau2_sierra_blackbox` are one benchmark measured twice, not two benchmarks.
Both run the **same** airline task ids with the **same** tools-only capability surface, sourced
from [`benchmarks/tau2/examples/sierra_airline/`](../../benchmarks/tau2/examples/sierra_airline/). The only difference
is how a candidate reaches the agent:

| | `tau2_sierra` (direct) | `tau2_sierra_blackbox` |
|---|---|---|
| delivery | the runner loads the candidate tools in its own process | the Skillberry **Store** serves the candidate skill and the **Proxy-Agent** injects it |
| tau2 agent model | the gateway model | the gateway model, reached through the `ibm/skillberry-local` sentinel and the Proxy-Agent |
| services started by the run | none | tau2 Environment Manager (`:8004`) + Store + Proxy-Agent, torn down on exit |
| rollout concurrency | 10 | 4 |

Both arms run **vanilla `sierra-research/tau2-bench`**, never edited, checked out at the
example's **`TAU2_REFERENCE_SHA`**: the commit the arms' adapters and `tau2_tailoring.py` were
created from when the benchmark was onboarded with
[`PROMPT.md`](../../benchmarks/tau2/examples/sierra_airline/PROMPT.md).
- `ci_setup.sh` reads that SHA from the arms' `setup.sh`, so CI keeps no copy of its own and has
  no override.
- It fails the job if the two arms disagree, or if the checkout is not at that commit.
- `run_suite.sh` checks it again before the first rollout.

Everything tau2 lacks for an arm is added from outside the benchmark by the arm's
`adapters/tau2_tailoring.py`.

Pick them with **`benchmark: tau2-sierra`** plus **`intervention: direct | blackbox`**, which maps
straight onto the spec key of the same name. `intervention` is ignored by every other benchmark —
they all run direct. Internally each arm stays its own leg (`tau2_sierra` /
`tau2_sierra_blackbox`) so each keeps its own tier task lists, history row and concurrency group.

Their rewards are comparable **to each other**, and *not* to the plain `tau2` leg. That one
also optimizes `policy.md`, and installs an unpinned checkout of the same public tau2.

Cheapest way to exercise an arm: **Integration tests** → Run workflow → `bench` =
`tau2_sierra_blackbox`. One task, 1 iteration, 1 trial.

## AppWorld (integration tier only)

`appworld` runs [`benchmarks/appworld/examples/react_agent/`](../../benchmarks/appworld/examples/react_agent/): AppWorld's official simplified
ReAct code agent, with its prompt, REPL helpers and API notes optimized. It has only an
`integration` tier, train task `82e2fac_1` (the example's own `scripts/itest.sh` task), and runs
only from **Integration tests** → Run workflow → `bench` = `appworld`. It is not in
`benchmarks.yml`'s `BENCHES`.

- **Setup on the runner:** `ci_setup.sh appworld` does the example's README Setup steps 1–2 in
  `$CAPEVOLVE_CI_CACHE/appworld` (= `AW_EVAL`). It clones AppWorld at `42b5bcf`, applies the
  example's header patch, installs into a Python 3.11 venv of its own, downloads the data, builds
  `root_opt` with the lint cache, and writes the reference docs. Each step is skipped when its
  output is already cached. It then runs the A4 injection check, which makes no model call. The
  runner needs `git-lfs` and `uv`.
- **Agent:** `gpt-oss-120b-a100` on RITS (the workflow sets it for this leg), reached through
  lite-rits with its bearer key. The key goes into a mode-600 file in the job's work dir that each
  episode worker reads and drops, never into the environment of the optimizer.
- **Optimizer isolation:** as in a local run, every optimizer call goes through the example's
  `sandbox/claude` shim, with the built-in sandbox by default (`AW_ISOLATION=namespace` for the
  fallback).
- **Gate:** `assert_run.py`, then the example's `scripts/assert_itest.py`, which also fails on an
  infra-errored or lint-rejected rollout and on a gold-bearing record.

## Trigger the suite

Runs come in several **tiers** (a first-class dimension in the workflow, same workflow + history page):
- **`smoke`** — a few representative tasks per benchmark (fast regression; the default).
- **`full`** — the whole/representative benchmark per bench (thorough; expensive). Its tasks
  live under `ci/benchmarks/<bench>/full/tasks.json`; a bench with an empty list simply runs
  zero tasks until populated (see below). Not every benchmark populates it yet. A whole-set run
  is long and can cost real money, so dispatch it deliberately, not routinely — the `bench` job
  carries a 1440min (`24h`) `timeout-minutes` for that reason.
- **`full_verified`** — a benchmark's **verified/curated re-release**, where upstream publishes
  one. Generic by design: any bench that gains such a release populates
  `ci/benchmarks/<bench>/full_verified/` and uses this same tier, rather than a name with that
  benchmark's task count baked in. Like `pilot` it runs only when named
  (`tier=full_verified`, or a `benchmark-full_verified-<bench>` label), never under `tier=all`
  — but unlike `pilot` that exclusion is about **cost**, not about the numbers being
  meaningless: a `full_verified` result is a real held-out number.
- **`canary`** — a minimal **pipeline check**: 1 task, 1 trial, 1 iteration. It exercises the whole
  run → live → publish path in minutes; its reward numbers mean **nothing**. Only runs
  when named (`tier=canary`, or a `benchmark-canary-<bench>` label), never under `all`.
- **`pilot`** — a cost/runtime measurement rig whose reward numbers are **not comparable to
  anything**. Explicit dispatch only.

> Tier **sizes, datasets, splits, turn budgets and costs are per-benchmark** and are documented
> in `ci/benchmarks/<bench>/README.md`. They deliberately do not appear here: a tier is a
> dimension of the suite, not a property of whichever benchmark needed it first. Which
> benchmarks populate which tier is likewise not listed here — it is exactly the set of
> `ci/benchmarks/<bench>/<tier>/tasks.json` files, which is what the planner reads.

  **`spreadsheetbench` runner prerequisites** (installed on `skillberry-1`):
  - **LibreOffice** (`sudo dnf install libreoffice-calc`). Scoring uses it to recalculate
    formula cells before comparing; without it a formula-only cell reads as empty and
    never matches, so solved tasks silently score 0. The adapter warns rather than fails,
    so treat `LibreOffice not found` in the log as a broken runner.
  - **A data dir the sandbox can write to.** The executor image runs as uid 1000 while the
    runner is uid 1004, so the adapter widens the mode of the output dirs it creates; see
    `_make_container_writable` in the adapter. A `PermissionError` on `*_output.xlsx` in
    the traces means that fix regressed.

  **`rfe-creator` runner prerequisites:**
  - `ci_setup.sh` clones `opendatahub-io/rfe-creator` + `opendatahub-io/agent-eval-harness`
    (public, unlicensed — see `ci/benchmarks/rfe-creator/utils/fetch_data.sh`) and installs
    `agent-eval-harness` editable into the shared venv. Neither is vendored, so an air-gapped
    runner needs its own mirror.
  - Same gateway/entitlement preflight as every other bench (whichever provider's secret pair
    the selected model's prefix resolves to — see "Populate the full tier" above); no extra
    credentials (the eval runs `--dry-run`, no Jira).

The tier surfaces everywhere: PR checks read **`<tier> / <bench>`** (e.g. `smoke / tau2`,
`full / swebench`), the report header reads **`## <Tier> suite — <bench>`**, and the history
page has a **Type** column + filter.

- **Manually:** Actions → **Benchmarks** → Run workflow → pick the **benchmark** (one of:
  `tau2` / `swebench` / `skillsbench` / `spreadsheetbench` / `rfe-creator` / `tau2-sierra`)
  and **tier** (`smoke` default / `full` / `all` / `pilot` / `full_verified`), plus any of these knobs
  (all optional, sensible defaults):

  | input | default | applies to |
  |---|---|---|
  | `iterations` | `10` | full tier only — smoke is always pinned to 3 |
  | `trials` | `10` | whichever tier(s) run in this dispatch |
  | `agent_model` | `aws/gpt-oss-120b` | the evaluation model (agent under test) — dropdown, populated from the `ete-litellm` gateway's registered aliases |
  | `optimizer_model` | `claude-opus-4-8` | the optimization model (Claude Code's model) — dropdown, same gateway-alias list as `agent_model` |
  | `optimizer_usd_per_iter` | `0` (unlimited) | per-iteration $ cap on the optimizer — `0` disables Claude Code's native `--max-budget-usd` cap entirely; set e.g. `4.0` to bound it |
  | `optimizer_max_turns` | `80` | per-iteration turn cap on the optimizer |
  | `gate_k_se` | `0.2` | acceptance-gate strictness (accept iff Δ > k_se·SE) |
  | `algorithm` | `hill-climb-all` | which optimization algorithm — see below |

  Overriding `agent_model` takes precedence over any per-task `agent` a curated `tasks.json`
  entry pins — `run_suite.sh` warns (doesn't fail) on a mismatch so you know it happened.

#### The `algorithm` input

One token names the algorithm and, for hill-climb, its focus schedule.

  | value | what runs |
  |---|---|
  | `hill-climb-all` (default) | deterministic loop, whole train set each iteration |
  | `hill-climb-cyclic` | deterministic loop, one task at a time |
  | `hill-climb-hardest-first` | deterministic loop, lowest-scoring task first |
  | `agent-optimize` | the fully-agentic loop (see below) |

`agent-optimize` is not just a fourth schedule. It has no deterministic loop at all: the run
switches to `orchestration_mode: agent`, where `cap-evolve run` does check + baseline, prints a
handoff and returns. There being no conversational agent in CI, `run_suite.sh` then hands the
loop to the algorithm's own headless host
(`skills/algorithms/agent-optimize/scripts/host.py` — see
[`docs/AGENT_ORCHESTRATION.md`](../../docs/AGENT_ORCHESTRATION.md)), which briefs a Claude Code
process to run the rounds itself and guarantees the run ends sealed even if that process stops
early.

Two consequences worth knowing before you compare numbers:

- **Its budget is a `stop_condition`, not a schedule.** `run_suite.sh` derives free-text prose
  from the same dispatch inputs (`iterations` → max rounds, `optimizer_usd_per_iter` × rounds →
  a whole-loop $ ceiling, `gate_k_se`/`trials` → the gate), so a given dispatch bounds both
  algorithms comparably. The agent may still stop earlier on its own `spend.py` reading.
- **`optimizer_max_turns` becomes a whole-loop cap.** The entire search is one agent process
  rather than one call per iteration, so the host multiplies the per-iteration turn cap by the
  round count.

`runmeta.json` records the `algorithm`, so the history page never compares a hill-climb number
against an agent-optimize one as though they were the same run type.
- **On a PR — labels:**
  - **`benchmark-smoke-<bench>`** / **`benchmark-full-<bench>`** (`tau2` · `swebench` ·
    `skillsbench` · `spreadsheetbench` · `rfe-creator` · `tau2_sierra` ·
    `tau2_sierra_blackbox`) → run just that one (combine labels to run a subset).

  (The tau2 pipeline regression is the **`integration-test`** label / **Integration tests**
  workflow — the same `run_suite.sh` path as above, scoped to a single-task `integration`
  tier: `ci/benchmarks/<bench>/integration/tasks.json`. The label always runs `tau2`; to run an
  arm's or `appworld`'s integration tier, dispatch that workflow with `bench` set.)

### Populate the `full` tier

Just add task ids to `<bench>/full/tasks.json` (same shape as `<bench>/smoke/tasks.json`):
```json
[{"id": "<task_id>", "tag": "full", "agent": "aws/gpt-oss-120b"}]
```
No baseline-freezing step — `run_suite.sh` computes the baseline fresh, in the same run, for
whatever ids are listed. Pick ids with headroom (baseline not already saturated) by running
`run_suite.sh` against a candidate list and checking the report.

Requires `IBM_ETE_INT_API_BASE`/`IBM_ETE_INT_API_KEY` (and, for an `ibm-ete/*` or
`ibm-rits/*` model, that provider's own pair — see below) set as repo secrets.

### Model providers and their order

**Rule: use RITS when it can serve the model, then `ibm-ete-int`, and `ibm-ete` only as the
last choice.** RITS has no budget. `ibm-ete-int` is the team's main gateway. `ibm-ete` is a
second gateway with its own budget; use it only when `ibm-ete-int` cannot serve the model or is
over budget (as on 2026-09-30, run 36711181652, #538).

The rule lives in one file, [`model_catalog.txt`](model_catalog.txt):

```text
order ibm-rits ibm-ete-int ibm-ete
model claude-opus-5   ibm-ete-int/aws/claude-opus-5   ibm-ete/aws/claude-opus-5
model gemma-4-31B-it  ibm-rits/google/gemma-4-31B-it
```

- **Plain name** (the first entries in both dropdowns, e.g. `claude-opus-5`): the preflight in
  `ci_setup.sh` tries the providers in `order`. It skips a provider that has no entry for the
  model or no secrets. For each remaining one it checks the gateway's `/models` listing (not
  for RITS) and sends one real completion. It keeps the first provider that lists the model,
  answers, and is not over budget. A 400 answer means our probe is wrong, not the provider, so
  it does not move on. The defaults (`gpt-oss-120b`, `claude-opus-4-8`) are plain names, so
  PR-label runs get the fallback too.
- **Prefixed id** (e.g. `ibm-ete/aws/claude-opus-5`): pins that provider. No fallback, and the
  same hard failures as before. Use it when an experiment must stay on one gateway.
- **One provider per run.** The choice is made once, before the run starts, and exported as
  `AGENT_MODEL_RESOLVED`/`OPTIMIZER_MODEL_RESOLVED`. `run_suite.sh`, the slot key and the run
  record all use the chosen prefixed id. If a budget runs out in the middle of a run, that run
  still fails; it does not switch gateways halfway, so baseline and candidates are never
  measured on different gateways.
- **Where to see the choice:** the job summary has a "Model providers" table. The run record
  (`records/<run>.json` in `skillberry-runs/dashboard`) has `agent_provider`, `optimizer_provider`,
  the `*_requested` names, and `*_provider_skipped` with the reason for each skipped provider
  (`over-budget`, `not-listed`, `not-entitled`, `unreachable`, `no-secrets`, `http-<code>`
  for any other non-200 answer such as 401, 404 or a rate-limit 429, and `probe-failed` for a
  RITS model that does not answer 200).
- **Editing the catalog:** list two ids under one name only when they are the same model,
  served the same way. The same name is not enough: `ibm-ete-int`'s `rits/google/gemma-4-31B`
  is the base model, and RITS's `google/gemma-4-31B-it` is the instruction-tuned one.
  `gpt-oss-120b` on RITS (`openai/gpt-oss-120b-a100`) is a separate name, so the default agent
  keeps its history; merge the two only after a side-by-side run. `sync_models.py` warns about
  catalog ids a gateway no longer serves and puts the catalog names first in the dropdowns,
  but never edits the catalog. `sync_models.py --validate` (run by `ci.yml`) fails when a
  plain dropdown entry is missing from the catalog.

### ibm-rits (skillberry-1 lite-rits proxy)

A second provider, reached only through an `ibm-rits/<vendor>/<model>` model id in either
dropdown. `resolve_provider.sh` strips the CI-only `ibm-rits/` prefix, rewrites it to the
`rits/<vendor>/<model>` wire-format lite-rits itself expects, and resolves it to
the `IBM_RITS_API_BASE`/`IBM_RITS_API_KEY` secrets — a LiteLLM proxy (`lite-rits`) running on
skillberry-1 itself (`http://localhost:4000`), talking directly to IBM RITS's own API. Since
the `ibm-vpc` self-hosted runner IS skillberry-1, this needs no new network path.

- **Repo secrets required:** `IBM_RITS_API_BASE` (`http://localhost:4000`), `IBM_RITS_API_KEY`.
- **Model ids** are the bare `<vendor>/<model>` strings in lite-rits's own scraped catalog
  (e.g. `google/gemma-4-31B-it`), prefixed with `ibm-rits/` for the dropdown only —
  `resolve_provider.sh` sends `rits/<vendor>/<model>` on the wire.
  `agent_model`/`optimizer_model` resolve independently, so a RITS agent with a
  gateway optimizer (or vice versa) is a normal, deliberate combination.
- **`agent_model`/`optimizer_model`'s curated RITS entries** are a general-purpose spread
  across lite-rits's catalog, granite family excluded on request. Only
  `ibm-rits/google/gemma-4-31B-it` is a genuine match to the WikiSkill paper's
  (arXiv 2608.27454v1) SpreadsheetBench model axis (Qwen-3.5-4B/9B, Qwen-3.6-27B,
  Gemma-4-31B, Gemini-3.5-Flash) — RITS carries no small Qwen or Gemini, so the rest of the
  list is not a reproduction of that axis.
- **Preflight:** `ci_setup.sh`'s gateway preflight is provider-aware — it skips the
  ete-litellm `/models` entitlement check for an `ibm-rits/*` model (lite-rits's own
  `/v1/models` is always empty by design: it builds routes dynamically per request rather
  than publishing a static `model_list`) and instead runs the same completion probe against
  `IBM_RITS_API_BASE`/`IBM_RITS_API_KEY`.
- **Caveat:** `OPTIMIZER_MODEL: ibm-rits/*` points the `claude-code` CLI's
  `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` at lite-rits. It is UNVERIFIED whether
  lite-rits speaks the Anthropic Messages API shape the CLI expects — a RITS
  `agent_model` with a gateway (Claude) `optimizer_model` is the combination actually
  exercised so far.

### ibm-ete (second ete-litellm gateway)

A second, separate ete-litellm gateway (`https://ete-litellm.ai-models.vpc.res.ibm.com`)
from the one `ibm-ete-int` uses — a different auth domain; an `IBM_ETE_INT_API_KEY` is not
recognized here and vice versa. Serves models `ibm-ete-int` doesn't (e.g. GLM), subject to
the team's LiteLLM budget on IBM's side.

Requires `IBM_ETE_API_BASE`/`IBM_ETE_API_KEY` as repo secrets. Use an `ibm-ete/<model>`
id in `agent_model`/`optimizer_model` — `resolve_provider.sh` strips the `ibm-ete/` prefix
and sends `<model>` on the wire verbatim.

The `ibm-ete/*` dropdown entries come from `sync-model-lists.yml`, which polls this gateway's
`/models`; nobody types them by hand, because a guessed spelling risks the prefix/case-drift
failure `check_models.py`'s docstring documents. Under the provider order above, `ibm-ete` is
the last choice for a plain name.

### Adding a fourth provider

Every provider follows the same shape: a CI-only dropdown prefix (e.g. `ibm-newprovider/`),
a secret pair named `IBM_<NAME>_API_BASE`/`IBM_<NAME>_API_KEY`, and a case arm in
`resolve_provider.sh` (`ci/benchmarks/lib/resolve_provider.sh`) that strips the prefix (or
rewrites it, if the provider needs a different wire-level id shape than its CI prefix, the
way `ibm-rits/*` does) and returns that provider's credentials. Add the prefix to
`provider_of`/`provider_has_creds` in the same file, to `PROVIDERS` in `sync_models.py`, and
to the `order` line in `model_catalog.txt` at the place it should be tried. `ci_setup.sh`'s
`check_listed`/`select_provider` and `sync_models.py`'s `--models PREFIX=PATH` polling key off
this same prefix. If it should be polled automatically, add a `fetch_one` call in
`sync-model-lists.yml`.

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
tau2/skillsbench runners do not surface usage (reads 0); swebench, spreadsheetbench, and
rfe-creator (all shell out to a real agent CLI) do.

## Adding / changing tasks

There's nothing to freeze or refresh — `run_suite.sh` always computes baseline and
optimized within the same run. To change what a tier covers, edit `<bench>/<tier>/tasks.json`
directly (id + tag + agent, same shape across `smoke`/`full`/`integration`) and re-run
`ci/benchmarks/lib/run_suite.sh <bench>` (set `TIER=<tier>` for anything other than `smoke`).

## Benchmark results: the skillberry-runs dashboard

Results are published to the [`skillberry-runs`](https://github.com/skillberry-runs) org and shown at
**<https://skillberry-runs.github.io/dashboard/>** (this site's `benchmarks.html` redirects there).
Since 2026-11 CI writes there directly; until then it wrote to this repo's `benchmark-history`
branch. Each `bench` job publishes its own results when it ends (step `Publish results to
skillberry-runs`, [`lib/publish_results.sh`](lib/publish_results.sh)), with plain git and the
`SKILLBERRY_RUNS_RESULTS_TOKEN` secret, which only that step receives:

| What | Where | Notes |
|---|---|---|
| one record per `(run × tier × bench)` | `skillberry-runs/dashboard`: `records/<run_id>__<tier>-<bench>.json` | the push deploys the dashboard, which renders `benchmarks.json` from `records/` (never committed) |
| the run's "Open UI" data (`export_static` output) | the benchmark's repo: `ci_ui/<run_id>__<tier>-<bench>/` | data only; one shared viewer on the dashboard opens it. Masked first with the dashboard's `scripts/mask_secrets.py` |
| the run's folder ([`lib/run_folder.py`](lib/run_folder.py)): README, `report.md`, `runmeta.json`, `metrics.jsonl`, `steps.jsonl`, `final.json`, `capability.diff`, `optimized_capability/`, `recipe/` (`capevolve.yaml`, `split_ids.json`, the tier's `overrides.env`) | the benchmark's repo: `ci_runs/<run_id>__<tier>-<bench>/`, in the same commit as the Open UI data | the record's `report_url` links its README, rendered on the dashboard (the row's **Report ↗**). SkillsBench gets a diffstat instead of the licensed skill content; anything over 20 MB is left out |

Which repo holds which bench is the dashboard's [`sections.json`](https://github.com/skillberry-runs/dashboard/blob/main/sections.json)
(`benches`). A bench that isn't listed still gets its record, and a `::warning::` says its run folder
and Open UI data were not published: add it there to keep future runs' data. Records are validated with
the dashboard's `scripts/check_records.py` before anything is pushed. The benchmark repo's commit (run
folder + Open UI data) goes first, and the record says `has_ui` and carries `report_url` only if it
was pushed; legs that publish at the same moment retry on a
fresh clone (each adds only its own files, so a retry never conflicts).

Until 2026-11-18 a separate GitHub-hosted `aggregate` job published from the bench jobs' uploaded
artifacts. After IBM's network change the self-hosted runners' artifact uploads time out
(CreateArtifact; slow DNS on the runner, see the job's `Check the runner's DNS` step) while git to
github.com still works, so publishing no longer goes through the artifact service.

To publish a run its bench job never published — one you resumed by hand, or drove directly on
the runner — follow [PUBLISHING.md](PUBLISHING.md); it runs these same scripts in the same order.

### Raw run data: uploaded to a CI raw-data area when the dispatch asks for it

What gets published is a summary. The raw run data, meaning the run dir with every candidate, trace and
rollout, plus the job's output dir, is lost when the next job's checkout cleans the workspace. A
dispatch that sets the input **`raw_data_location`** (an rclone path `<remote>:<path>`; empty by
default, and PR-label runs never set it) makes each bench job keep it (step `Keep the raw run data for
the full backup`, [`lib/backup_run.sh`](lib/backup_run.sh)): packed on the runner, outside the
workspace, then uploaded to `<path>/<run_id>__<tier>-<bench>/` with `rclone copy --immutable` and
checked with `rclone check`. Only when the check passes is the runner's copy removed; when the upload
fails, the capture stays on the runner and the step warns why.

- **`<remote>`** is defined by the repository secret **`RAW_DATA_RCLONE_CONFIG`**: the text of an rclone
  config section (`rclone config show <remote>`). Give it write access to the raw-data area only. The
  step writes it to a 0600 file in a private temp dir under `$RUNNER_TEMP` and removes it afterwards.
- **Use credentials that do not change when used, written in full in the config text:** object-store
  access keys (S3-style), an SFTP key, a password (for example WebDAV), a service account given
  inline (Google Drive: `service_account_credentials`), or a client-credentials setup (Box:
  `box_sub_type = enterprise`, `client_credentials = true`, and the app's `client_id` and
  `client_secret`). An option that names a file (`box_config_file`, `service_account_file`) works
  only when that file is on the runner. The rule holds for the remote and every remote it wraps
  (`crypt`, `alias`, `union`, ...). **A token from a browser login does not work:**
  rclone saves each refreshed token into the config file, which the step deletes, and some providers
  (Box among them) accept each refresh token only once, so the secret's token would stop working, in
  CI and on the machine it was copied from. The step refuses such a config, and warns when rclone
  rewrites a config anyway.
- **rclone** is installed by the step itself into `~/.local/bin`, pinned by version and sha256
  ([`lib/install_rclone.sh`](lib/install_rclone.sh)).
- The raw-data area holds **raw, unscanned data** (it can contain tokens from logs or `.env` files),
  so keep it private to the people who run the backup. Its path is not written into the published
  `ci_runs/` folder: `backup.json` there names only the leg's dir in it.
- A run dispatched without `raw_data_location` keeps no raw data: once the next job of that tier and
  bench cleans the workspace, only the published summary remains.

CI never runs the backup: the full backup procedure, [`docs/FULL_BACKUP.md`](../../docs/FULL_BACKUP.md),
is applied on demand by an agent a user asks, with read access to the raw-data area, which it reads as
one of its sources. Each capture, in the raw-data area and on the runner before its upload:

```
<run_id>__<tier>-<bench>/        (a re-run attempt N>1: <run_id>__<tier>-<bench>.a<N>/)
  <run_id>__<tier>-<bench>.tar.zst   the output dir, <out_dir>_proj/.capevolve/ and <out_dir>_proj.sealed/
  members.sha256                     sha256 of every file, taken before packing
  symlinks.txt                       every symlink and its target
  unreadable.txt                     every path the job could not read (left out, a gap for the backup)
  backup.json                        run, attempt, bench, tier, who triggered it, runner, archive sha256
```

A capture dir is written once and never overwritten. The run's `ci_runs/` folder gets a copy of
`backup.json`, with `staged` (the leg's dir in the raw-data area) and `kept_on_runner`, and its README says where
the capture is, so it can be found from the run's page.
The step is best-effort: it never fails a run, falls back to `.tar.gz` if `zstd` is missing, and skips
(with a warning) when the runner's disk would drop below 20 GB free.

**Moving it to the backup location** is done only by following `docs/FULL_BACKUP.md`, which lists this
tree as a source (§5.3(b)). The operator unpacks each archive into staging, checks it against
`backup.json` and `members.sha256`, scans it for secrets, organizes it into a run folder and uploads that.
**Never copy the raw-data area or `~/capevolve-ci-capture/` into the backup location as is**: it is not in the location's
layout, it was never scanned for secrets, and it has no `MANIFEST.json`. The backup never deletes a
source. Once a full backup's `BACKUP_RESULTS_<TS>.md` records a run as uploaded and checked, the
raw-data area's owner (or, for a capture left on a runner, the runner's admin) may remove it.

Runs from 2026-11-18 until this change were archived as
`~/skillberry-runs-backup/user/<who triggered the run>/<repo>/<run_id>__<tier>-<bench>.tar.zst`, with
`backup.json` (archive sha256, no per-file hashes) only in the run's `ci_runs/` folder. They are
captured the same way (FULL_BACKUP §5.3(b)).

### Live monitoring while a run is in progress

Each `bench` job backgrounds `ci/benchmarks/lib/live_push.sh` around "Run suite": every 5 minutes it
exports the in-progress run's dashboard data and force-pushes it, as a single fresh commit, to the
job's own branch `<run_id>__<tier>-<bench>` of [`skillberry-runs/live`](https://github.com/skillberry-runs/live)
(`data/` at the branch root). A branch never holds more than the latest snapshot. When the job ends
(any outcome) the branch is deleted; the permanent Open UI data lands moments later via `aggregate`.
The poller authenticates with `SKILLBERRY_RUNS_LIVE_TOKEN`, which can reach that repo only.

The dashboard's "Running now" panel polls the GitHub Actions API client-side (unauthenticated) for
in-progress `<tier> / <bench>` jobs and links each to the shared viewer on its live branch via
`?dataBase=`. "What's running" always comes from the Actions API, never from which branches exist,
so a leftover branch (a job killed before cleanup) is never linked to; the live repo's hourly
`sweep-stale-branches.yml` deletes any branch untouched for 26 hours.
