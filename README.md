<p align="center">
  <img src="docs/assets/cap-evolve-logo.png" alt="cap-evolve" width="200"/>
</p>

<h1 align="center">cap-evolve</h1>

<p align="center"><em>watch capability evolve</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/status-beta%20(0.x)-orange" alt="status">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
  <img src="https://img.shields.io/badge/runtime%20deps-0%20(stdlib)-success" alt="deps">
  <img src="https://img.shields.io/badge/license-Apache--2.0-informational" alt="license">
  <img src="https://img.shields.io/badge/agent%20skills-18-7c5cff" alt="skills">
</p>

**cap-evolve is a skills-based, host-agnostic harness that optimizes *any* agent
capability — a system prompt, its tools/MCP, or a whole skill package — against
*your* eval, with honesty enforced in code and every iteration git-versioned.**

You wire a tiny adapter once (or let a coding agent write it for you). cap-evolve
runs the loop: evaluate → diagnose failures → propose an edit → keep it only if it
beats a held-out split by a significant margin → commit → report a single honest
number. It optimizes what your agent *reads*, not its weights.

**Contents:** [Why](#why-cap-evolve) · [Install](#install) ·
[Toy example](#toy-example-zero-api) · [tau2-bench example](#tau2-bench-example-real) ·
[Optimize your own](#optimize-your-own) · [How it works](#how-it-works) ·
[Comparison](#how-it-compares) · [Skill library](#skill-library) ·
[Results](#results) · [How-to guides](#how-to-guides) · [License](#license)

## Why cap-evolve

- **Optimizes prompts, tools/MCP, *and* skill packages** — not just prompts.
  Pick one or several (`[system-prompt, tools, mcp-tool, skill-package]`) and
  optimize them jointly.
- **Code-bearing optimization, not just reword.** For `tools`, the optimizer can
  edit tool *code* — add validation/loop/composite tools that enforce a rule or
  perform a stalled action in code (the fix for a behavioral failure prose can't
  reach) — and safely swap, never bare-remove, a primitive.
- **Onboard any benchmark/agent from a single prompt.** Paste one intake brief to
  your coding agent; **intake does the full integration** — installs the benchmark,
  wires the adapter (incl. trajectories + a batched fast path), authors a
  capability-scoped optimizer prompt, and passes the `cap-evolve check` gate —
  before any budget is spent. No pre-integration.
- **Per-task causal feedback.** Each iteration the optimizer sees which task ids a
  prior edit BROKE and FIXED plus the currently-passing set to protect — so it
  makes large, multi-cluster edits that don't regress the wins.
- **Honesty enforced in code, not docs.** The sealed test split is scored exactly
  once and a paired, val-only significance gate (Δ > k·SE) decides every
  acceptance — both live in the `cap_evolve` core, the only place rewards are
  aggregated.
- **Host- and agent-agnostic.** The optimizer is *any* coding-agent CLI
  (claude-code, codex, gemini, opencode, ibm-bob, …) resolved by one registry row.
  No framework lock-in.
- **Git-versioned iterations + optimizer memory** — every candidate is a commit;
  rejected approaches are remembered and never re-proposed.
- **Per-iteration optimizer $ budget**, enforced by the optimizer CLI itself
  (e.g. claude `--max-budget-usd`), plus hard total caps and a dry-run estimate.
- **Live dashboard** — per-iteration optimizer & runner cost + time, intake cost,
  lineage tree, per-iteration diffs, and a tasks × iterations pass/fail heatmap.
- **Skills-native & trivially extensible** — a new capability, algorithm, or
  optimizer is one folder or one registry row.
- **Zero runtime dependencies** — the core is pure Python stdlib.

## Install

Requires **Python 3.10+** and **git**.

```bash
git clone <repo> cap-evolve && cd cap-evolve
python3 -m venv .venv && source .venv/bin/activate   # recommended (isolated env)
pip install ./core                  # the honest-eval core (package: cap-evolve-core, CLI: cap-evolve)
pip install ./dashboard/backend     # optional: the live dashboard UI (cap-evolve run --dashboard auto)
./install.sh                        # optional: copy skills into your agent host's skills dir
cap-evolve version                  # verify the install
```

> **If your default pip index requires auth**, append `--index-url https://pypi.org/simple`
> to the `pip install` lines (cap-evolve-core itself has zero runtime deps).

Optimizing a real agent additionally needs: a coding-agent CLI to act as the
**optimizer** (e.g. `claude`, `codex`, `gemini`) with its credentials, and your
**runner**'s model credentials — all in a repo-root `.env` (e.g. `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `RITS_API_KEY`, `WATSONX_*`). The toy example below needs **none** of this.

## Toy example (zero-API)

Verify the install with a deterministic, no-key run. `toy_calc` is a stand-in
agent that only answers correctly when its system prompt contains a `[CALC]`
marker; the `mock` optimizer adds it, so the score provably rises — no model is
called.

```bash
bash examples/toy_calc/run.sh
```

Expected: the seed prompt scores `0.0` on val; the optimized prompt is gate-accepted
and scores `1.0` on the sealed test split.

```text
baseline_val 0.0  ->  test_reward 1.0   (gate-accepted, test sealed) + dashboard.html
```

This is exactly what `core/tests/test_e2e_slice.py` asserts. Open the printed
`dashboard.html` in any browser to see the run.

## tau2-bench example (real)

The bundled [`examples/tau2_airline`](examples/tau2_airline) takes a **brand-new
benchmark** from one prompt to an honest, optimized result. It optimizes the
airline **policy + tools together** with a `claude-opus-4-6` optimizer, using
`gpt-oss-120b` over IBM RITS as **both** the agent and the user simulator. The
committed run lifted val reward **0.496 → 0.702 (+0.206, ≈ +41% relative)**; see
the headline numbers and walkthrough below, or just open the full interactive
dashboard (all 15 iterations, no backend needed) committed under
[`run_full/ui/`](examples/tau2_airline/run_full/ui/) — serve it with
`cd examples/tau2_airline/run_full/ui && python3 -m http.server 8000` (then
http://localhost:8000), or host it on GitHub Pages / any static host.

```bash
# RITS creds in repo-root .env (RITS_API_KEY, RITS_API_URL); be logged into Claude Code.
bash examples/tau2_airline/setup.sh   # intake: clone + pip install -e tau2-bench, scaffold
                                      # the project, wire adapter + RITS shim + seed,
                                      # then cap-evolve check (the hard gate)
bash examples/tau2_airline/run.sh     # cap-evolve run --dashboard auto: full loop + live UI
```

This two-command path is simply the executable transcript of pasting
[`PROMPT.md`](examples/tau2_airline/PROMPT.md) to your coding agent and saying
*"follow [`RUN.md`](RUN.md)."* Intake onboards tau2-bench (recording the resolved
commit), wires the adapter — including `run_batch` → tau2's runner, the batched
`run_trials` fast path, `trajectories()` (native tau2 traces), and `score()`
(reads `reward_info`) — and authors a capability-scoped optimizer prompt, then
passes `cap-evolve check`. It optimizes the airline policy + tools over all 50
tasks (10 trials each) under a per-iteration `--max-budget-usd` cap, with a paired
significance gate and a git commit per iteration. `--dashboard auto` serves the
live capybara UI; the `setup.sh` flag `--dashboard` / `--no-dashboard` toggles
installing that server. Full walkthrough: [`DEMO.md`](examples/tau2_airline/DEMO.md);
reproduce from zero: [`docs/REPRODUCE_tau2.md`](docs/REPRODUCE_tau2.md).

This is the exact prompt that produced this example (the full text, verbatim from
[`PROMPT.md`](examples/tau2_airline/PROMPT.md)) — paste it to your coding agent and
say *"follow RUN.md"*:

```text
Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL it (not assume it
exists). Here is everything intake needs:

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- type:         [system-prompt, tools]      # the airline POLICY and the TOOLS, jointly
- tools means:  edit tool docstrings/descriptions; edit tool behavior/code; and
                ADD/REMOVE tools, including composite tools that call existing tools
- seed:         tau2-bench's canonical airline policy + its airline tool set
- seed tools:   the seed tools file must be CLEAN, runnable code as intake would
                produce it — real tool bodies, no baked-in optimizer/editing
                instructions in its docstrings (what the optimizer may change to the
                tools lives in the tools capability SKILL.md, not in the seed file)
- capability_sources:  set `capability_sources` to the benchmark's data-model/types
                module(s) the tools import (here tau2's airline data_model — the source
                of FlightDB, Reservation, Passenger, Payment, etc.). cap-evolve copies
                these verbatim into the optimizer's workdir so it can write correct
                new-tool code against the real types.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL IT DURING INTAKE
- benchmark:    tau2-bench, airline domain
- repo:         https://github.com/sierra-research/tau2-bench   (latest main; record the resolved commit)
- install:      git clone as a sibling dir ../tau2-bench, then `pip install -e ../tau2-bench`
- tasks:        "adapter" — the adapter loads all 50 airline tasks from tau2
                (tau2.domains.airline.environment.get_tasks)
- splits:       all 50 tasks as train = val = test  (no-holdout fit metric; the engine
                logs a splits_warning and the report flags the test number as a fit metric)

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- how to run:   tau2's own batch runner (adapter.run_batch -> tau2.runner.run_tasks)
- fast eval:    ALSO implement the optional adapter method
                run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id: [Rollout, ...]}.
                Run ALL num_trials in ONE tau2 run_tasks call with num_trials=N (grouped by
                sim.trial) at TAU2_MAX_CONCURRENCY=125, and return {task_id: [trial0, trial1, ...]}
                (len n_trials, trial-ordered). When present, cap-evolve calls it ONCE per candidate
                instead of looping run_batch per trial; per-trial persistence
                (rollouts/<split>/<task>__<tag>__t<k>.json) is UNCHANGED so pass^k / SE / resume
                keep working. This collapses N sequential eval passes into one batched run.
- agent AND user simulator:  openai/gpt-oss-120b  via IBM RITS
- RITS wiring:  litellm model "hosted_vllm/openai/gpt-oss-120b" + per-call api_base +
                extra_headers {"RITS_API_KEY": ...}  (NO litellm monkeypatch, NO tau2 fork)
- credentials:  RITS_API_KEY (+ RITS_API_URL) in the repo-root .env
- concurrency:  TAU2_MAX_CONCURRENCY=125

# 4. SCORER  (what to optimize against) — and WHERE the metric comes from
- metric:       tau2's own task reward in [0,1] (required actions performed + info communicated)
- metric source: tau2 computes it per simulation as `sim.reward_info.reward`; the per-check
                breakdown is in `sim.reward_info` (db_check / action_checks / communicate_checks /
                nl_assertions / env_assertions). Implement adapter.score() to read the reward +
                reward_info that run_batch stashes from each simulation, and verify score() is
                deterministic on a fixed rollout (the `cap-evolve check` gate enforces this).
- feedback:     gold-AWARE but gold-SAFE — which required actions/info were missed (the learning
                signal), derived from reward_info checks; never leak the gold answer.
- objective:    maximize mean reward on the VAL split

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads) — PATH IS AN INPUT
- where:        tau2's batch runner can persist its native per-task simulation results
                (full message transcript + reward_info) to a directory via run_tasks(save_path=...).
                Point run_batch's save_path at a per-eval dir UNDER THE RUN, e.g.
                <run_dir>/trajectories/val/  (any structure/format tau2 writes is fine).
- expose:       implement adapter.trajectories(split) to return that directory. cap-evolve copies
                it VERBATIM into the optimizer's working dir as ./trajectories/ each iteration, so
                the optimizer reads the complete, unmodified traces (not a lossy summary).
                (If you cannot persist native files, return None — cap-evolve falls back to copying
                its own per-rollout JSON, which already embeds each rollout's full message trace.)

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS + CONTEXT
- optimizer:    claude-code
- model:        claude-opus-4-6
- credentials:  a logged-in Claude Code session (or ANTHROPIC_API_KEY)
- runner_repo_path:  ../tau2-bench  (the cloned checkout — surfaced to the optimizer as
                read-only context so it can consult tau2's tools/scoring/task structure)
- optimizer instructions: author .capevolve/project/optimizer/INSTRUCTIONS.md from the scaffolded
                template (keep its {{...}} placeholders intact — the harness fills them per
                iteration), tailoring the guidance + the "READ THESE" pointers (./trajectories/,
                ./guidance/<cap>/, ./guidance/diagnose/SKILL.md, ./guidance/optimizer/claude-code.md,
                ./LEDGER.md, ./JOURNAL.md, ./RUNMAP.md + ./prior_iterations/, ./PROCESS.md,
                ../tau2-bench) to this benchmark. The authored INSTRUCTIONS must follow the flow: READ
                the cross-iteration files FIRST (LEDGER facts, the whole JOURNAL handover, RUNMAP +
                prior_iterations diffs) and never re-propose a rejected approach; address ALL failure
                clusters each iteration (fan out one subagent per cluster, each in its own worktree,
                then merge all edits into ONE candidate), shipping MULTIPLE edit classes and a NEW
                code-bearing tool for any capability-gap/stall cluster; fill ./PROCESS.md (required
                explainability) and APPEND to ./JOURNAL.md each iteration. For the tools capability,
                code-bearing tools are the primary edit — a validation tool that enforces a rule in
                code then calls the existing tool and removes the raw one; a workflow tool that
                collapses a recurring sequence; and a composite WRITE tool that performs a stalled
                multi-step
                action in code (then removes the raw write primitives) so the agent cannot analyze,
                confirm, and then fail to execute — not docstring prose.

# 6. BUDGET / GATE
- algorithm:        hill-climb  (--focus all)
- max_iterations:   10          num_trials: 10
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 40   (claude --max-budget-usd, enforced by the CLI itself)
- optimizer_max_turns: 400      (generous; the $ cap is the real per-iteration ceiling)
- max_usd: 400      max_optimizer_usd: 400
- gate:             significant (paired), k_se 0.2
- store:            git          (every iteration committed for an inspectable process)
```

The bundled `examples/tau2_airline/` is the **result** of running this prompt: the
adapter (incl. `run_batch`/`run_trials`/`trajectories`/`score`), the RITS shim, the
editable seed (`seed_capability/` = `policy/` + `tools/` + `reference/data_model.py`),
and the capability-scoped `optimizer/INSTRUCTIONS.md` are exactly what the
intake / implement-and-check flow produced.

## Optimize your own

To optimize **your** capability against **your** benchmark, you wire one small
**adapter** ([`docs/ADAPTER_CONTRACT.md`](docs/ADAPTER_CONTRACT.md)) — three
required methods plus optional hooks:

```python
tasks(split)                   -> list[Task]   # your eval cases for 'train'|'val'|'test'|'all'
run_target(task, ctx, *, seed) -> Rollout      # run your agent with the candidate LIVE as ctx;
                                               #   forward `seed` if stochastic; set Rollout.error on infra failure
score(task, rollout)           -> Score        # reward in [0,1] + feedback (never leak the gold)

# optional (working defaults provided):
materialize(cand_dir, edits)   -> None         # PURE write of edits into cand_dir
live(cand_dir)                 -> ctx (CM)      # make the candidate live for ONE eval
run_batch(tasks, ctx, *, seed) -> ...           # implement INSTEAD of run_target to drive a
                                               #   benchmark's OWN batch runner (as tau2 does)
run_trials(tasks, ctx, *, n_trials, base_seed) # batched fast path: ALL trials in ONE run
  -> {task_id: [Rollout, ...]}                 #   (collapses N eval passes; pass^k/SE unchanged)
trajectories(split)            -> Path|None    # the runner's NATIVE trace dir for the last eval;
                                               #   copied verbatim to the optimizer's ./trajectories/
```

Everything else — splits, trials, gating, pass^k, the sealed test, memory, and the
dashboard — is provided by the core and must not be reimplemented (that is what
keeps eval honest). Two ways to get there:

**A — let your coding agent build it (no Python from you).** Open the coding agent
you already use at the repo root and tell it to follow `RUN.md`. It loads the
`intake` skill, asks for anything missing (never fabricating a NEEDED input),
writes the adapter, runs `cap-evolve check`, then the full loop.
[`examples/tau2_airline/PROMPT.md`](examples/tau2_airline/PROMPT.md) is a complete
worked brief (also embedded verbatim in the
[tau2-bench section](#tau2-bench-example-real) above).

Fill this in and paste it to your coding agent with *"follow RUN.md"* — intake asks
for anything you omit and never fabricates a needed input:

```text
Follow RUN.md to run a cap-evolve optimization on MY benchmark/agent. If the
benchmark is not installed yet, the intake/integration step should CLONE + INSTALL
it. Here is everything intake needs (fill each field; leave a field blank only if
you want intake to ask):

# 1. CAPABILITY  (what gets optimized — a COPY is edited each iteration; the original is never touched)
- type:    <one or a list of: system-prompt | tools | mcp-tool | skill-package>
           # system-prompt = a prompt/policy text file; tools = the agent's OWN tools;
           # mcp-tool = tools served by an EXTERNAL MCP server (only docs/exposed-set edits);
           # skill-package = an Agent Skill dir (SKILL.md + refs + scripts). Combine, e.g. [system-prompt, tools].
- seed:    <path to the seed artifact to optimize, e.g. policy/policy.md | tools.json | skills/<name>/>
- NOTE for `tools`: the optimizer may edit tool docstrings/descriptions AND tool
           behavior/code, AND add/remove COMPOSITE tools that call existing tools
           (wrapping rules, loops, argument normalization) — not just reword docs.

# 2. BENCHMARK / DATASET  (the eval)
- benchmark:  <name, e.g. my-bench / SWE-bench-lite / a homegrown suite>
- repo:       <local path OR git URL>            # where the benchmark code/data lives
- install:    <how to install it, e.g. `pip install -e ../<bench>`; RECORD the resolved commit for reproducibility>
- tasks:      <path to tasks.jsonl  OR  "adapter">   # "adapter" = adapter.tasks(split) builds them in-code
- task format: each task = id + input + gold/criterion
              # one JSON object per line: {"id": ..., "input": ..., "target"/"criterion": ...}
- splits:     <one of:>
              #  seeded ratio   -> split_seed + split_train/val/test (default 0.5/0.25/0.25)
              #  explicit       -> split_ids.json  {"train":[...],"val":[...],"test":[...]} (e.g. an official split)
              #  no-holdout fit -> train == val == test == all ids (report FLAGS the test number as a fit metric)

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- how to run one task:  <in-process call | subprocess | HTTP endpoint
                         | the benchmark's OWN batch runner -> implement adapter.run_batch instead of run_target>
- runner model(s):      <model id(s) the agent under test uses>
- credentials:          <env vars / repo-root .env keys, e.g. OPENAI_API_KEY, WATSONX_*, RITS_API_KEY — never hardcode a secret>
- custom/OpenAI-compatible endpoint (vLLM, IBM RITS, a gateway):
                        <api_base + any custom auth header>
                        # pass via the runner's LLM config (most benchmarks forward extra kwargs to litellm);
                        # prefer PER-CALL config — no monkeypatch, no benchmark fork
- concurrency knob:     <e.g. an env var / max-concurrency setting the runner honors>

# 4. SCORER  (what to optimize against)
- metric:     <exact-match | reward in [0,1] | rubric | pass/fail rule>
- source:     <the benchmark's own verifier  OR  your score() function in adapter.py>
- feedback:   must be GENERAL and gold-SAFE — it is the learning signal; never leak the gold answer
- objective:  maximize mean reward on the VAL split

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS
- optimizer:   <claude-code | codex | gemini-cli | opencode | cursor | droid | copilot | kimi | pi | antigravity | openclaw | ibm-bob | generic | mock>
- model:       <backend-specific model id>
- credentials: <e.g. ANTHROPIC_API_KEY or a logged-in Claude Code session; BOBSHELL_API_KEY for ibm-bob>

# 6. BUDGET / GATE
- algorithm:            <hill-climb (--focus all|cyclic|hardest-first) | gepa | skillopt>
- max_iterations:       <N — dominant cost knob>
- num_trials:           <>=3 for a stochastic agent; 1 only for a deterministic one>   # enables pass^k
- max_metric_calls:     <0 = unlimited; else stop after N runner evals>
- max_usd:              <total $ cap over runner + optimizer + intake; 0 = unlimited>
- max_optimizer_usd:    <cumulative optimizer-only $ cap; 0 = unlimited>
- optimizer_usd_per_iter: <PER-ITERATION $ cap enforced by the optimizer CLI itself, e.g. claude `--max-budget-usd N`>
- optimizer_max_turns:  <per-iteration WORK cap passed to the agent CLI, e.g. claude `--max-turns N`>
- gate:                 <significant (k_se) | strict | threshold>
                        # significant: accept only if Δ > k_se · SE — k_se is how many standard errors
                        # the val gain must clear (e.g. 0.2 = lenient, 1.0 = strict) so noise isn't mistaken for progress
- stall:                <stop after N consecutive rejects; 0 = run all max_iterations>
- store:                git          # versions every iteration as a commit for an inspectable process
```

**B — drive the `cap-evolve` CLI yourself.**

```bash
python3 skills/phases/intake/scripts/run.py --base .capevolve   # scaffold adapter STUB + capevolve.yaml
# 1. implement tasks / run_target (or run_batch) / score in
#    .capevolve/project/adapters/adapter.py  (copy the closest example below)
# 2. set capabilities / optimizer / algorithm / splits in capevolve.yaml
cap-evolve check .capevolve/project                              # hard gate — must print {"ok": true}
cap-evolve estimate --spec .capevolve/project/capevolve.yaml     # dry-run cost preview (spends nothing)
cap-evolve run   --spec .capevolve/project/capevolve.yaml --project .capevolve/project
open .capevolve/run_*/dashboard.html
```

Start from the closest example and edit its `adapter.py`:

| You want to optimize…                       | Copy                                              | `capabilities:`          |
|---------------------------------------------|---------------------------------------------------|--------------------------|
| a **prompt** (zero-API proof)               | [`examples/toy_calc`](examples/toy_calc)          | `[system-prompt]`        |
| a **system prompt + tools** (real agent)    | [`examples/tau2_airline`](examples/tau2_airline)  | `[system-prompt, tools]` |

**Swapping the optimizer is one word** in `capevolve.yaml` — one runner
(`run-optimizer`) resolves the name via `skills/optimizers/registry.yaml`:

```yaml
capabilities:    [system-prompt, tools]   # any of: system-prompt | tools | mcp-tool | skill-package
optimizer_skill: claude-code              # ← swap: codex | gemini-cli | opencode | cursor | droid | copilot | kimi | pi | antigravity | openclaw | ibm-bob | generic | mock
algorithm_skill: hill-climb               # hill-climb (--focus all|cyclic|hardest-first) | gepa | skillopt
num_trials: 4
store: git                                # versions every iteration
```

**Extending is just as small:** a new capability, algorithm, or optimizer is one
folder or one `optimizers/registry.yaml` row — see
[`docs/EXTENDING.md`](docs/EXTENDING.md).

## How it works

**intake → implement-and-check → baseline → algorithm → finalize → report.**

**Intake does the whole benchmark integration — before any budget is spent.** It
interviews you (or reads your brief), installs the benchmark, and wires the
**adapter** (tasks / run_target-or-run_batch / score), the **trajectory** path
(`adapter.trajectories(split)` → the runner's native traces), the optional batched
**run_trials** fast path, and `capability_sources` (the data-model/types files the
tools import). It then authors a **capability-scoped** optimizer prompt
(`optimizer/INSTRUCTIONS.md`) — guidance and editable artifacts for *only* the
selected capabilities. Missing NEEDED inputs are asked for, never fabricated.

**implement-and-check is the HARD GATE.** `cap-evolve check` refuses to proceed
until every adapter method (and any selected skill's abstract methods) is real and
`score()` is deterministic — so no spend happens against a stub.

**baseline** freezes the seeded train/val/test split (written once; test
**sealed**) and scores the unmodified seed on val — the candidate every iteration
must beat.

**Each algorithm iteration** (`hill-climb` / `gepa` / `skillopt`): **diagnose**
failing val traces into failure clusters → the **optimizer proposes** a large,
multi-part edit → the candidate is **evaluated** on val (each of N trials gets its
own seed, so pass^k measures real variance) → a **paired significance gate**
(Δ > k·SE, val-only) accepts or rejects → the iteration is git-committed and memory
updated.

**finalize** scores the best candidate on the **sealed test split exactly once**
(the run dir enforces the seal); **report** writes `report.md` and a self-contained
`dashboard.html`.

### What the optimizer receives each iteration (and why edits are large + non-regressing)

The harness assembles a **capability-scoped** working dir per iteration, then runs
your chosen coding-agent CLI in it:

- **The selected capability skill(s)** — both as `./guidance/<cap>/` *and* placed
  **natively** in the agent's own skills dir (e.g. `.claude/skills/`, `.codex/…`)
  so a headless agent auto-loads them. Each carries a "What you can change here"
  menu and edit boundaries.
- **The diagnose method** (`./guidance/diagnose/`) — how to cluster failures into a
  reflective dataset (per failing task: Inputs, Generated Outputs, Feedback).
- **ONLY the current best step's full trajectories** (`./trajectories/`) — the
  runner's verbatim traces of the candidate it builds on, never the seed + every
  rejected attempt.
- **Supporting sources / data model** (`./guidance/sources/`) — the
  `capability_sources` files, copied verbatim so new tool code is written against
  the real types.
- **Per-task IMPACT of prior candidates** — which task ids each prior edit BROKE
  (were passing) and FIXED, plus the **currently-passing set to protect** — causal
  feedback so a known regression is never re-introduced.
- **Cross-iteration files with clean ownership** — `LEDGER.md` (framework-owned
  FACTS: every iteration's outcome + the exact tasks it broke/fixed), `JOURNAL.md`
  (optimizer-owned, append-only HANDOVER across the whole run: tried/worked/regressed/
  refuted/focus-next), `PROCESS.md` (optimizer-owned EXPLAINABILITY, snapshotted per
  candidate), and `RUNMAP.md` + `prior_iterations/` (a manifest plus every prior
  iteration's PROCESS.md and capability diff, copied in for real prior-work access).

Because it sees all failure clusters, the protect-set, and the prior causal impact
at once, the optimizer produces **one bold, multi-part candidate per iteration that
addresses every cluster without regressing the wins** — not a one-line tweak.

### What the optimizer can change

The **prompt** and the **tools** are equally fair game — pick whatever fixes the
most clusters:

- **Prompt** ([`system-prompt`](skills/capabilities/system-prompt/SKILL.md)):
  rewrite/consolidate/add rules, add examples, tighten the output contract — but
  **never drop a needed rule** (change / consolidate / add, don't delete).
- **Tools** ([`tools`](skills/capabilities/tools/SKILL.md)): add/replace/wrap tools,
  **edit tool CODE** for deterministic enforcement, improve docs **and RETURN
  VALUES** (actionable errors) for recovery, add loop/workflow/composite tools, and
  **swap via a safe wrapper — never bare-remove** a primitive. Code-bearing tool
  edits are emphasized (a tool body the model cannot skip beats a sentence it can
  forget — the fix for a *behavioral* failure the agent "knows" but doesn't do),
  but a knowledge-gap failure still belongs in the prompt.

> **Honesty is enforced in code, not docs.** Splitting, reward aggregation, the
> val-only significance gate (paired, `k_se` standard errors), and sealing test all
> live in `cap_evolve` ([`docs/HONEST_EVAL.md`](docs/HONEST_EVAL.md)). Every
> iteration is git-versioned. Infra-vs-capability failures are distinguished by a
> structured `Rollout.error` signal, never by string-matching feedback prose.

### Speed + observability

All N trials of a candidate run in **one concurrent pass** when the adapter
implements `run_trials(tasks, ctx, *, n_trials, base_seed)` (collapsing N
sequential eval passes into one batched run; per-trial persistence and pass^k/SE
are byte-for-byte unchanged). The **live dashboard** launches first and shows the
intake cost/time/output, per-iteration optimizer & runner cost + time, the
cumulative-best stair, a tasks × iterations pass/fail heatmap, the git diff per
iteration, the lineage tree, and gate decisions.

## How it compares

| | cap-evolve | DSPy | GEPA | promptfoo |
|---|:--:|:--:|:--:|:--:|
| Optimizes prompts | ✅ | ✅ | ✅ | ❌ (eval only) |
| Optimizes tools/MCP + skill packages | ✅ | ➖ | ➖ | ❌ |
| Sealed test + significance gate enforced in code | ✅ | ➖ | ➖ | ➖ |
| Host- & agent-agnostic (no framework lock-in) | ✅ | ❌ | ❌ | ➖ |
| Onboard a benchmark from a single prompt | ✅ | ❌ | ❌ | ➖ |
| Git-versioned iterations + optimizer memory | ✅ | ❌ | ❌ | ❌ |
| Live cost-aware dashboard | ✅ | ❌ | ❌ | ➖ |
| Zero runtime dependencies | ✅ | ❌ | ❌ | ❌ |

Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Skill library

cap-evolve is a library of **18** [Agent Skills](https://www.anthropic.com/news/skills)
over a tiny stdlib core. The 8 per-CLI optimizers collapsed into one
`run-optimizer` skill + a one-row-per-optimizer registry; the three hill-climb
variants collapsed into one `hill-climb` skill with `--focus`.

| Component | Skills |
|-----------|--------|
| orchestrate  | `orchestrate` · `using-cap-evolve` (session-start router) |
| phases       | `intake` · `implement-and-check` · `baseline` · `evaluate` · `diagnose` · `gate` · `finalize` · `report` |
| capabilities | `system-prompt` · `skill-package` · `tools` · `mcp-tool` |
| algorithms   | `hill-climb` (`--focus all\|cyclic\|hardest-first`) · `gepa` · `skillopt` |
| optimizers   | `run-optimizer` + `optimizers/registry.yaml` (`claude-code`, `codex`, `gemini-cli`, `opencode`, `cursor`, `droid`, `copilot`, `kimi`, `pi`, `antigravity`, `openclaw`, `ibm-bob`, `generic`, `mock`) |

`gepa` (real GEPA — reflective Pareto search, two-stage minibatch-then-full-val
economy; arXiv:2507.19457) and `skillopt` (epochs × mini-batches with a decaying
textual learning rate; arXiv:2605.23904) are the sample-efficient **flagships**;
`hill-climb` is the simple global-best baseline climber.

**Claude Code plugin:** `claude --plugin-dir ./plugins/cap-evolve` exposes every
skill as `/cap-evolve:<skill>` and arms honesty **hooks** (PreToolUse denies edits
to the sealed test/gold; Stop/SubagentStop block finishing until `cap-evolve check`
and the gate are green) — all in **core-owned scripts**, never in editable skill
markdown.

## Results

Real [tau2-bench](https://github.com/sierra-research/tau2-bench) airline run —
optimizing the airline **policy + tools together** with a `claude-opus-4-6`
optimizer and `gpt-oss-120b` (agent **and** user simulator, via IBM RITS) over
all 50 airline tasks (10 trials each). **Metric:** mean tau2 task reward in
`[0,1]`.

| | val reward (50 tasks · 10 trials) | Δ vs baseline |
|---|---|---|
| **Baseline** (seed policy + tools) | **0.496** | — |
| **Best candidate** (`cand_0013`) | **0.702** | **+0.206 (≈ +41% relative)** |

The gain accretes across iterations behind the paired significance gate — gains
small enough to be noise are rejected. Acceptances: iter 1 `+0.110`
(0.496→0.606), iter 2 `+0.054` (→0.660), iter 9 `+0.020` (→0.680), iter 13
`+0.022` (→0.702); the other 11 iterations were rejected by the gate. A 10-iteration
finalize scored its best candidate (`cand_0009`) **once** on the sealed split at
**0.676 pass@1** (pass^2 0.556).

**What actually changed.** Every accepted iteration makes deep, in-code edits to
the tools — not just prompt tweaks. Driven by argument-level feedback from the
failing rollouts, the optimizer turns prose policy rules into executable guards
inside the existing tool bodies: e.g. iter 1 alone converted 5 of 6 rule
violations into in-code guards (cancel/update/baggage eligibility checks) plus a
`get_all_reservation_details` loop tool; `tools.py` grows 593 → 982 lines and the
policy grows 166 → 212 lines across the run. See the curated story in
[`examples/tau2_airline/DEMO.md`](examples/tau2_airline/DEMO.md).

**See it before you run it.** Open the committed full interactive dashboard (all 15
iterations, no backend needed) — the static UI export at
[`examples/tau2_airline/run_full/ui/`](examples/tau2_airline/run_full/ui/) — by running
`cd examples/tau2_airline/run_full/ui && python3 -m http.server 8000` (then visit
http://localhost:8000), or host it on GitHub Pages / any static host (KPIs, evaluations,
per-iteration git diffs, cost/intake panel, lineage, memory). Raw numbers:
[`run_full/final.json`](examples/tau2_airline/run_full/final.json). Reproduce from
zero: [`docs/REPRODUCE_tau2.md`](docs/REPRODUCE_tau2.md). Every iteration is a git
commit.

> Note: this example pins train = val = test = all 50 tasks (no-holdout), so val
> **is** the fit metric and the sealed-test number is reported as a **fit metric**
> (the engine logs a `splits_warning`); for a held-out result, pin a 30/10/10
> split via `split_ids.json`.

## How-to guides

Step-by-step recipes for specific harness + benchmark combinations:

| Guide | What it covers |
|---|---|
| [cap-evolve with Exgentic / tau2-bench](docs/how-to/cap-evolve-with-exgentic-tau2.md) | Optimize airline `policy.md` + `tools.py` via the exgentic harness and a LiteLLM proxy |

More guides will be added here over time.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
Report security issues via [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Citation

```bibtex
@software{cap-evolve,
  title  = {cap-evolve: a skills-native, host-agnostic harness for honestly
            optimizing AI-agent capabilities},
  year   = {2026},
  note   = {https://github.com/skillberry-ai/cap-evolve}
}
```

**Acknowledgements.** The `gepa` and `skillopt` skills are independent
implementations of the GEPA (arXiv:2507.19457) and SkillOpt (arXiv:2605.23904)
papers — no third-party code is included; both reference projects are MIT-licensed.
cap-evolve also draws on ideas from DSPy, tau-bench/tau2-bench, and the Agent Skills
standard. Full citations: [docs/sources.bib](docs/sources.bib).

## License

Apache-2.0.
