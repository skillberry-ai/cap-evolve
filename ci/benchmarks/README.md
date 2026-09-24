# Benchmark regression suite

Triggerable, real-model optimization regression over **tau2 · swebench · skillsbench ·
spreadsheetbench · rfe-creator**, plus the two tau2-airline **delivery arms**
(**tau2_custom_direct · tau2_custom_spa**),
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

`tau2_custom_direct` and `tau2_custom_spa` are one benchmark measured twice, not two
benchmarks. Both run the **same** airline task ids with the **same** tools-only capability
surface, sourced from [`examples/tau2_custom/`](../../examples/tau2_custom/);
the only difference is how a candidate reaches the agent:

| | `tau2_custom_direct` | `tau2_custom_spa` |
|---|---|---|
| delivery | the runner imports the candidate tools in its own process | the Skillberry **Store** serves the candidate skill and the **Proxy-Agent** uses it |
| tau2 agent model | the gateway model itself | the `ibm/skillberry-local` sentinel, which routes through the proxy to that same model |
| services started by the run | none | tau2 Environment Manager (`:8004`) + Store + Proxy-Agent, torn down on exit |
| rollout concurrency | 10 | 4 |

Pick them with **`benchmark: tau2-custom`** plus **`intervention: direct | spa`**, which maps
straight onto the spec key of the same name. `intervention` is ignored by every other benchmark —
they all run direct. Internally each arm stays its own leg (`tau2_custom_direct` /
`tau2_custom_spa`) so it keeps its own tier task lists, history row and concurrency group, and
`benchmark=all` sweeps both regardless of `intervention`.

Their rewards are comparable **to each other**, and *not* to the plain `tau2` leg: that one
also optimizes `policy.md` and installs the public `sierra-research/tau2-bench`, while the arms
install `skillberry-ai/skillberry-benchmarks` at the pin their own `setup.sh` uses (a test
asserts the two pins stay equal). The `spa` arm additionally needs that build's
`airline_skillberry` domain, which the public checkout does not have.

Cheapest way to exercise an arm: **Integration tests** → Run workflow → `bench` =
`tau2_custom_spa`. One task, 1 iteration, 1 trial.

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
  - **`benchmark-smoke`** / **`benchmark-full`** → run every benchmark of that tier, the two
    delivery arms included.
  - **`benchmark-smoke-<bench>`** / **`benchmark-full-<bench>`** (`tau2` · `swebench` ·
    `skillsbench` · `spreadsheetbench` · `rfe-creator` · `tau2_custom_direct` ·
    `tau2_custom_spa`) → run just that one (combine labels to run a subset).

  (The tau2 pipeline regression is the **`integration-test`** label / **Integration tests**
  workflow — the same `run_suite.sh` path as above, scoped to a single-task `integration`
  tier: `ci/benchmarks/<bench>/integration/tasks.json`. The label always runs `tau2`; to run an
  arm's integration tier, dispatch that workflow with `bench` set.)

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

The `agent_model`/`optimizer_model` dropdowns ship with **zero seeded `ibm-ete/*`
options** — the catalog isn't reliably queryable yet (currently budget-capped), and
hand-typing a guessed model-id spelling risks the exact prefix/case-drift failure
`check_models.py`'s docstring documents. `sync-model-lists.yml` populates real entries
automatically the first time it successfully polls this gateway; until then, dispatching
an `ibm-ete/*` model requires typing the exact id `workflow_dispatch` will still accept
only if it's already one of the enumerated `options:` — i.e. not at all, until the sync
workflow adds it.

### Adding a fourth provider

Every provider follows the same shape: a CI-only dropdown prefix (e.g. `ibm-newprovider/`),
a secret pair named `IBM_<NAME>_API_BASE`/`IBM_<NAME>_API_KEY`, and a case arm in
`resolve_provider.sh` (`ci/benchmarks/lib/resolve_provider.sh`) that strips the prefix (or
rewrites it, if the provider needs a different wire-level id shape than its CI prefix, the
way `ibm-rits/*` does) and returns that provider's credentials. `ci_setup.sh`'s
`classify_provider`/`check_entitlement` and `sync_models.py`'s `--models PREFIX=PATH`
polling both key off this same prefix, so a new provider needs no changes to their
matching logic — only a new case arm and, if it should be polled automatically, a new
`fetch_one` call in `sync-model-lists.yml`.

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

To publish a run the `aggregate` job never handled — one you resumed by hand, or drove directly on
the runner — follow [PUBLISHING.md](PUBLISHING.md); it runs these same scripts in the same order.

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

### Live monitoring while a run is in progress

Each `bench` job also backgrounds `ci/benchmarks/lib/live_push.sh` around "Run suite":
every 5 minutes it exports the in-progress run's static dashboard data and overwrites
`live/<run_id>__<tier>-<bench>/data/` on `benchmark-history` — always the latest
snapshot only, never a history of intermediate ones. When the job ends (any outcome),
it deletes that `live/` entry; the permanent snapshot lands moments later via the
`aggregate` job's `runs/<slug>/` write, same as always.

`benchmarks.html` polls the GitHub Actions API client-side (unauthenticated, no new
CI-side status reporting) to show a "Running now" panel with a "Watch live" link per
in-progress `<tier>/<bench>` job. Unlike the finished-run UI (a full shell+data copy
committed per run), the live view points one generic dashboard shell — built once per
Pages deploy at `site/dashboard-ui/` — at the live data via a `?dataBase=` query param,
so no Pages redeploy is needed while a run is in progress.

Orphaned `live/` entries (e.g. a hard runner crash before cleanup runs) are harmless:
"what's running" is always derived from the GitHub Actions API, never from `live/`'s
existence, so an orphan is simply never linked to.
